//! Neal's 10-D funnel tail-mass check under one of the arms of the
//! second reverse-coarser policy study at the sampler defaults (adapted-step arms only).
//!
//! Usage: `funnel defaults <arm> <seed> <out.json>`
//!
//! `defaults`: `Tuning::default()` (eight levels, `MomentumSum`), adapted
//! diagonal metric with the Stan regularisation, plus the arm's
//! `reverse_coarser_policy` (`arms.rs`). Four starts `omega in {-3, -1, 1, 3}`, 2,000 warmup and 20,000
//! retained draws per chain, `P(omega < -5)` (exact 0.0478) with two
//! standard errors: the ArviZ-style MCSE of the indicator
//! (`diagnostics::mcse_mean`, the WP28 statistic; the preregistered gate)
//! and the batch-means s.e. over batches of 500 draws per chain (the WP26
//! statistic, reported).
#![forbid(unsafe_code)]

#[path = "../arms.rs"]
mod arms;

use arms::Arm;
use owalnuts::diagnostics::{ess_bulk, ess_tail, mcse_mean, rhat};
use owalnuts::sampler::{Limits, Metric, Sampler, Target, TargetError};
use serde_json::json;
use std::{env, error::Error, fs, path::Path, time::Instant};

const DIMENSION: usize = 10;
const EXACT_TAIL_MASS: f64 = 0.047_790_352_272_814_7;
const EXACT_OMEGA_VARIANCE: f64 = 9.0;
const WARMUP: usize = 2_000;
const DRAWS: usize = 20_000;
const BATCH: usize = 500;

struct Funnel;

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

fn run(tuning_name: &str, arm_name: &str, seed: u64, out: &Path) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    let arm = Arm::parse(arm_name)?;
    let sampler = Sampler::new()
        .warmup(WARMUP)
        .draws(DRAWS)
        .chains(4)
        .threads(4)
        .seed(seed)
        .limits(Limits::new().admit_worst_case());
    let sampler = match tuning_name {
        "defaults" => sampler
            .metric(Metric::diagonal())
            .adaptation(arm.adaptation()?)
            .tuning(arm.tuning(None)?),
        other => return Err(format!("unknown tuning {other:?} (expected defaults)").into()),
    };
    let starts: Vec<Vec<f64>> = [-3.0, -1.0, 1.0, 3.0]
        .into_iter()
        .map(|omega| {
            let mut q = vec![0.0; DIMENSION];
            q[0] = omega;
            q
        })
        .collect();
    let begin = Instant::now();
    let posterior = sampler.run(&Funnel, &starts)?;
    let wall = begin.elapsed().as_secs_f64();

    let mut below = 0usize;
    let mut total = 0usize;
    let mut batch_means: Vec<f64> = Vec::new();
    let mut chains_json = Vec::new();
    let mut omega_columns: Vec<Vec<f64>> = Vec::new();
    let mut indicator_columns: Vec<Vec<f64>> = Vec::new();
    let mut per_chain_tail = Vec::new();
    for chain in posterior.chains() {
        let tuning = chain.metadata().tuning();
        let work = chain.telemetry().total();
        let retained = chain.telemetry().retained();
        chains_json.push(json!({
            "final_max_error": tuning.max_error(),
            "final_step_size": tuning.step_size(),
            "mass_diagonal": chain.metadata().mass_diagonal(),
            "target_calls": work.target_calls_total(),
            "retained_target_calls": retained.target_calls_total(),
            "depth_caps": retained.maximum_depth_stops(),
            "divergences": retained.divergences(),
            "refinement_exhaustions": retained.refinement_exhaustion_stops(),
            "reverse_coarser_stops": retained.reverse_coarser_stops(),
            "reverse_coarser_rejections": retained.reverse_coarser_rejections(),
            "reverse_coarser_continuations": retained.reverse_coarser_continuations(),
            "zero_weight_leaves": retained.zero_weight_leaves(),
            "leaves_built": retained.leaves_built(),
        }));
        let mut in_batch = 0usize;
        let mut chain_below = 0usize;
        let mut omegas = Vec::with_capacity(DRAWS);
        let mut indicator = Vec::with_capacity(DRAWS);
        for draw in 0..chain.retained() {
            let omega = chain.sample(draw).expect("draw")[0];
            omegas.push(omega);
            total += 1;
            let is_below = omega < -5.0;
            indicator.push(f64::from(is_below));
            if is_below {
                below += 1;
                in_batch += 1;
                chain_below += 1;
            }
            if (draw + 1) % BATCH == 0 {
                batch_means.push(in_batch as f64 / BATCH as f64);
                in_batch = 0;
            }
        }
        per_chain_tail.push(chain_below as f64 / chain.retained() as f64);
        omega_columns.push(omegas);
        indicator_columns.push(indicator);
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
    let refs: Vec<&[f64]> = omega_columns.iter().map(Vec::as_slice).collect();
    let flat_n = total as f64;
    let omega_mean = omega_columns.iter().flatten().sum::<f64>() / flat_n;
    let omega_variance = omega_columns
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
    let payload = json!({
        "schema": "reverse-coarser-policy-v2-funnel",
        "tuning": tuning_name, "arm": arm.name,
        "warmup_config": arm.json(None),
        "seed": seed,
        "chains": 4, "warmup": WARMUP, "draws": DRAWS,
        "tail_mass": {"estimate": estimate, "mcse": mcse, "z": z,
                      "batch_means_se": batch_se, "z_batch_means": z_batch,
                      "exact": EXACT_TAIL_MASS, "below": below, "total": total,
                      "batches": batch_means.len(), "per_chain": per_chain_tail},
        "batch_means": batch_means,
        "omega": {"mean": omega_mean, "variance": omega_variance,
                  "exact_variance": EXACT_OMEGA_VARIANCE,
                  "bulk_ess": ess_bulk(&refs), "tail_ess": ess_tail(&refs), "rhat": rhat(&refs)},
        "omega_bulk_ess": ess_bulk(&refs), "omega_rhat": rhat(&refs),
        "target_calls_total": calls,
        "retained_target_calls": retained_calls,
        "wall_seconds": wall,
        "chains_data": chains_json,
        "algorithm_revision": posterior.algorithm_revision(),
    });
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    eprintln!(
        "funnel {tuning_name} {arm_name} seed {seed}: P(omega < -5) {estimate:.4} +- {mcse:.4} \
         (z {z:+.2}; batch-means z {z_batch:+.2}), {calls} target calls, wall {wall:.1}s"
    );
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [tuning, arm, seed, out] => match seed.parse::<u64>() {
            Ok(s) => run(tuning, arm, s, Path::new(out)),
            Err(_) => Err("seed must be an integer".into()),
        },
        _ => Err("usage: defaults <arm> <seed> <out.json>".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
