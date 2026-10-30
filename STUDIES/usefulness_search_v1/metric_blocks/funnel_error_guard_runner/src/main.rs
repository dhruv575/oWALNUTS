//! Research-only fresh funnel guard; derived from WP63, with Gaussian control and raw draws.
#![forbid(unsafe_code)]

use owalnuts::diagnostics::{ess_bulk, ess_tail, mcse_mean, rhat};
use owalnuts::sampler::{Adaptation, Limits, Metric, Sampler, Target, TargetError, Tuning};
use serde_json::json;
use std::{env, error::Error, fs, path::Path, time::Instant};

const DIMENSION: usize = 10;
const EXACT_TAIL_MASS: f64 = 0.047_790_352_272_814_7;
const EXACT_TAIL_MASS_6: f64 = 0.022_750_131_948_179_2;
const EXACT_OMEGA_VARIANCE: f64 = 9.0;
const BATCHES_PER_CHAIN: usize = 40;

struct Funnel { noncentered: bool }

impl Target for Funnel {
    fn dimension(&self) -> usize {
        DIMENSION
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let omega = position[0];
        if self.noncentered {
            gradient[0] = -omega / 9.0;
            for (g,x) in gradient[1..].iter_mut().zip(&position[1..]) { *g = -x; }
            let value = -omega*omega/18.0 - 0.5*position[1..].iter().map(|x|x*x).sum::<f64>();
            return if value.is_finite() && gradient.iter().all(|x|x.is_finite()) { Ok(value) }
                else { Err(TargetError::recoverable("nonfinite Gaussian evaluation")) };
        }
        let inverse_variance = (-omega).exp();
        if !inverse_variance.is_finite() {
            return Err(TargetError::recoverable("exp(-omega) overflowed"));
        }
        let sum_squares: f64 = position[1..].iter().map(|x| x * x).sum();
        let tail = (DIMENSION - 1) as f64;
        gradient[0] = -omega / 9.0 - 0.5 * tail + 0.5 * inverse_variance * sum_squares;
        for (g, x) in gradient[1..].iter_mut().zip(&position[1..]) {
            *g = -inverse_variance * x;
        }
        let value =
            -omega * omega / 18.0 - 0.5 * tail * omega - 0.5 * inverse_variance * sum_squares;
        if value.is_finite() && gradient.iter().all(|g| g.is_finite()) {
            Ok(value)
        } else {
            Err(TargetError::recoverable("nonfinite funnel evaluation"))
        }
    }
}

fn arm_delta(arm: &str) -> Result<f64, Box<dyn Error>> {
    match arm {
        "default" => Ok(1.0),
        "permissive" => Ok(1000.0),
        "delta0.5" => Ok(0.5),
        other => Err(format!("unknown arm {other:?} (default, delta2, delta0.5)").into()),
    }
}

fn run(
    target: &str,
    arm: &str,
    warmup: usize,
    draws: usize,
    seed: u64,
    out: &Path,
) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    assert!(target == "centered" || target == "noncentered");
    let delta = arm_delta(arm)?;
    let tuning = if arm == "default" {
        Tuning::default()
    } else {
        Tuning::default().max_error(delta)
    };
    let kernel = tuning.to_kernel()?;
    assert_eq!(kernel.max_refinement_levels(), 8);
    let sampler = Sampler::new()
        .warmup(warmup)
        .draws(draws)
        .chains(4)
        .threads(4)
        .seed(seed)
        .metric(Metric::diagonal())
        .adaptation(Adaptation::default())
        .tuning(tuning)
        .limits(Limits::new().admit_worst_case());
    let starts: Vec<Vec<f64>> = [-3.0, -1.0, 1.0, 3.0]
        .into_iter()
        .map(|omega| {
            let mut q = vec![0.0; DIMENSION];
            q[0] = omega;
            q
        })
        .collect();
    let begin = Instant::now();
    let posterior = sampler.run(&Funnel { noncentered: target == "noncentered" }, &starts)?;
    let wall = begin.elapsed().as_secs_f64();

    let batch = (draws / BATCHES_PER_CHAIN).max(1);
    let mut below = 0usize;
    let mut total = 0usize;
    let mut batch_means: Vec<f64> = Vec::new();
    let mut chains_json = Vec::new();
    let mut columns: Vec<Vec<Vec<f64>>> = vec![Vec::new(); DIMENSION];
    let mut indicator_columns: Vec<Vec<f64>> = Vec::new();
    let mut indicator6_columns: Vec<Vec<f64>> = Vec::new();
    let mut per_chain_tail = Vec::new();
    let mut nonfinite = 0usize;
    for chain in posterior.chains() {
        let chain_tuning = chain.metadata().tuning();
        let work = chain.telemetry().total();
        let retained = chain.telemetry().retained();
        let warmup_end = chain.telemetry().warmup_end();
        chains_json.push(json!({
            "final_max_error": chain_tuning.max_error(),
            "final_step_size": chain_tuning.step_size(),
            "warmup_end_step_size": warmup_end.map(|w| w.step_size()),
            "warmup_end_median_log_density": warmup_end.map(|w| w.median_log_density()),
            "mass_diagonal": chain.metadata().mass_diagonal(),
            "target_calls": work.target_calls_total(),
            "retained_target_calls": retained.target_calls_total(),
            "depth_caps": retained.maximum_depth_stops(),
            "divergences": retained.divergences(),
            "refinement_exhaustions": retained.refinement_exhaustion_stops(),
            "invalid_stops": retained.invalid_evaluation_stops(),
            "warmup_divergences": chain.telemetry().discarded().divergences(),
            "refinement_level_built": retained.refinement_level_built(),
            "reverse_coarser_stops": retained.reverse_coarser_stops(),
            "nonfinite_position_rejections_retained": retained.nonfinite_position_rejections(),
            "nonfinite_position_rejections_warmup": chain.telemetry().discarded().nonfinite_position_rejections(),
        }));
        let mut in_batch = 0usize;
        let mut chain_below = 0usize;
        let mut chain_columns: Vec<Vec<f64>> = vec![Vec::with_capacity(draws); DIMENSION];
        let mut indicator = Vec::with_capacity(draws);
        let mut indicator6 = Vec::with_capacity(draws);
        for draw in 0..chain.retained() {
            let sample = chain.sample(draw).expect("draw");
            if sample.iter().any(|v| !v.is_finite()) {
                nonfinite += 1;
            }
            for (col, v) in chain_columns.iter_mut().zip(sample) {
                col.push(*v);
            }
            let omega = sample[0];
            total += 1;
            let is_below = omega < -5.0;
            indicator.push(f64::from(is_below));
            indicator6.push(f64::from(omega < -6.0));
            if is_below {
                below += 1;
                in_batch += 1;
                chain_below += 1;
            }
            if (draw + 1) % batch == 0 {
                batch_means.push(in_batch as f64 / batch as f64);
                in_batch = 0;
            }
        }
        per_chain_tail.push(chain_below as f64 / chain.retained() as f64);
        for (all, col) in columns.iter_mut().zip(chain_columns) {
            all.push(col);
        }
        indicator_columns.push(indicator);
        indicator6_columns.push(indicator6);
    }
    let estimate = below as f64 / total as f64;
    let batches = batch_means.len() as f64;
    let batch_variance = batch_means
        .iter()
        .map(|mean| (mean - estimate) * (mean - estimate))
        .sum::<f64>()
        / (batches - 1.0);
    let batch_se = (batch_variance / batches).sqrt();
    let z_batch = (estimate - EXACT_TAIL_MASS) / batch_se;
    let indicator_refs: Vec<&[f64]> = indicator_columns.iter().map(Vec::as_slice).collect();
    let mcse = mcse_mean(&indicator_refs);
    let z = (estimate - EXACT_TAIL_MASS) / mcse;
    let indicator6_refs: Vec<&[f64]> = indicator6_columns.iter().map(Vec::as_slice).collect();
    let estimate6 = indicator6_columns.iter().flatten().sum::<f64>() / total as f64;
    let mcse6 = mcse_mean(&indicator6_refs);

    let mut coord = Vec::with_capacity(DIMENSION);
    for col in &columns {
        let refs: Vec<&[f64]> = col.iter().map(Vec::as_slice).collect();
        coord.push((ess_bulk(&refs), ess_tail(&refs), rhat(&refs)));
    }
    let min_bulk = coord.iter().map(|c| c.0).fold(f64::INFINITY, f64::min);
    let min_tail = coord.iter().map(|c| c.1).fold(f64::INFINITY, f64::min);
    let max_rhat = coord.iter().map(|c| c.2).fold(f64::NEG_INFINITY, f64::max);
    let omega_cols = &columns[0];
    let flat_n = total as f64;
    let omega_mean = omega_cols.iter().flatten().sum::<f64>() / flat_n;
    let omega_variance = omega_cols
        .iter()
        .flatten()
        .map(|w| (w - omega_mean).powi(2))
        .sum::<f64>()
        / (flat_n - 1.0);
    let calls: usize = posterior
        .chains()
        .iter()
        .map(|c| c.telemetry().total().target_calls_total())
        .sum();
    let retained_calls: usize = posterior
        .chains()
        .iter()
        .map(|c| c.telemetry().retained().target_calls_total())
        .sum();
    let warnings = posterior.chain_warnings();
    let warnings_json: Vec<serde_json::Value> = warnings
        .iter()
        .map(|w| {
            let debug = format!("{w:?}");
            let kind = debug.split([' ', '{']).next().unwrap_or("").to_string();
            json!({"chain": w.chain(), "kind": kind, "message": w.to_string(), "debug": debug})
        })
        .collect();
    let payload = json!({
        "schema": "delta2-confirmation-v1-funnel",
        "arm": arm,
        "max_error": delta,
        "u_turn": format!("{:?}", kernel.options().u_turn),
        "exhaustion_retained": format!("{:?}", kernel.options().exhaustion),
        "metric_regularization": format!("{:?}", owalnuts::sampler::DEFAULT_METRIC_REGULARIZATION),
        "warmup_exhaustion_rule": format!("{:?}", owalnuts::sampler::DEFAULT_WARMUP_EXHAUSTION),
        "kernel_tuning": {"step_size": kernel.step_size(), "max_depth": kernel.max_depth(),
                          "max_refinement_levels": kernel.max_refinement_levels(),
                          "max_error": kernel.max_error()},
        "starts": starts,
        "seed": seed,
        "chains": 4, "threads": 4, "warmup": warmup, "draws": draws,
        "tail_mass": {"estimate": estimate, "mcse": mcse, "z": z,
                      "batch_means_se": batch_se, "z_batch_means": z_batch, "batch": batch,
                      "exact": EXACT_TAIL_MASS, "below": below, "total": total,
                      "batches": batch_means.len(), "per_chain": per_chain_tail},
        "tail_mass_6": {"estimate": estimate6, "mcse": mcse6,
                        "z": (estimate6 - EXACT_TAIL_MASS_6) / mcse6, "exact": EXACT_TAIL_MASS_6},
        "omega": {"mean": omega_mean, "variance": omega_variance,
                  "exact_variance": EXACT_OMEGA_VARIANCE,
                  "bulk_ess": coord[0].0, "tail_ess": coord[0].1, "rhat": coord[0].2},
        "min_bulk_ess": min_bulk,
        "min_tail_ess": min_tail,
        "max_rhat": max_rhat,
        "per_coordinate": coord.iter().map(|c| json!({"bulk_ess": c.0, "tail_ess": c.1, "rhat": c.2})).collect::<Vec<_>>(),
        "nonfinite_draws": nonfinite,
        "target_calls_total": calls,
        "retained_target_calls": retained_calls,
        "min_bulk_ess_per_gradient": min_bulk / calls as f64,
        "chain_warnings": warnings_json,
        "chain_warning_lines": owalnuts::diagnostics::ChainWarning::lines(&warnings),
        "wall_seconds_contended": wall,
        "chains_data": chains_json,
        "target": target, "columns": columns,
        "algorithm_revision": posterior.algorithm_revision(),
    });
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    let divergences: usize = posterior
        .chains()
        .iter()
        .map(|c| c.telemetry().retained().divergences())
        .sum();
    eprintln!(
        "funnel {arm} {warmup}/{draws} seed {seed}: P(omega < -5) {estimate:.4} +- {mcse:.4} \
         (z {z:+.2}; batch-means z {z_batch:+.2}), divergences {divergences}, min bulk ESS {min_bulk:.0}, \
         {calls} target calls, warnings {}, wall {wall:.1}s",
        warnings.len()
    );
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [target, arm, warmup, draws, seed, out] => {
            match (warmup.parse::<usize>(), draws.parse::<usize>(), seed.parse::<u64>()) {
                (Ok(w), Ok(d), Ok(s)) => run(target, arm, w, d, s, Path::new(out)),
                _ => Err("warmup, draws and seed must be integers".into()),
            }
        }
        _ => Err("usage: funnel <default|delta2|delta0.5> <warmup> <draws> <seed> <out.json>".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn gradients_and_change_of_variables() {
        for omega in [-6.0, -1.0, 3.0] {
            let z: Vec<f64> = (0..10).map(|i| if i==0 {omega} else {i as f64 / 10.0}).collect();
            let mut x=z.clone(); for v in &mut x[1..] { *v *= (omega/2.0).exp(); }
            let mut g=vec![0.;10];
            let lc=Funnel{noncentered:false}.log_density_gradient(&x,&mut g).unwrap();
            let ln=Funnel{noncentered:true}.log_density_gradient(&z,&mut g).unwrap();
            assert!((lc+4.5*omega-ln).abs()<1e-10);
            for (nc,q) in [(false,x),(true,z)] {
                let target=Funnel{noncentered:nc}; target.log_density_gradient(&q,&mut g).unwrap();
                for i in 0..10 { let mut p=q.clone(); let mut m=q.clone(); p[i]+=1e-6; m[i]-=1e-6;
                    let mut scratch=vec![0.;10];
                    let fd=(target.log_density_gradient(&p,&mut scratch).unwrap()-target.log_density_gradient(&m,&mut scratch).unwrap())/2e-6;
                    assert!((fd-g[i]).abs()<1e-5*(1.0+g[i].abs()));
                }
            }
        }
    }
}
