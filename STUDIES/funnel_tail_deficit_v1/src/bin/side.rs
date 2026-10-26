//! WP66 side check: the cost of each arm on two ordinary targets, as in
//! `STUDIES/funnel_defaults_v1` (WP28): noncentered Eight Schools (explicit
//! starts `log_tau in {-2, -1, 0, 1}`) and a 100-D standard Gaussian
//! (`Init::uniform()`), 4 chains x 1,000 / 1,000, four threads.
//!
//! Usage: `side <eight|gauss100> <arm> <seed> <out.json>`
//!
//! Statistic: minimum bulk ESS over all coordinates per target call, warmup
//! included (the house efficiency statistic), plus the house health gates.
#![forbid(unsafe_code)]

use funnel_tail_deficit_v1::arm;
use owalnuts::diagnostics::{ess_bulk, ess_tail, rhat};
use owalnuts::sampler::{Init, Limits, Metric, Posterior, Sampler, Target, TargetError};
use serde_json::json;
use std::{env, error::Error, fs, path::Path, time::Instant};

const LOG_2PI: f64 = 1.837_877_066_409_345_3;
const SCHOOL_Y: [f64; 8] = [28., 8., -3., 7., -1., 1., 18., 12.];
const SCHOOL_SE: [f64; 8] = [15., 10., 16., 11., 9., 11., 10., 18.];

fn normal_log_density(x: f64, mean: f64, sd: f64) -> f64 {
    -0.5 * LOG_2PI - sd.ln() - 0.5 * ((x - mean) / sd).powi(2)
}

/// Noncentered Eight Schools as in `STUDIES/funnel_defaults_v1/src/main.rs`.
struct EightSchoolsNoncentered;

impl Target for EightSchoolsNoncentered {
    fn dimension(&self) -> usize {
        10
    }
    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        let mu = q[0];
        let log_tau = q[1];
        let tau = log_tau.exp();
        let z = &q[2..];
        let mut value = normal_log_density(mu, 0., 5.)
            + (2. / (std::f64::consts::PI * 5. * (1. + (tau / 5.).powi(2)))).ln()
            + log_tau;
        gradient.fill(0.);
        gradient[0] = -mu / 25.;
        gradient[1] = 1. - 2. * tau * tau / (25. + tau * tau);
        for j in 0..8 {
            let theta = mu + tau * z[j];
            let residual = SCHOOL_Y[j] - theta;
            let likelihood_gradient = residual / SCHOOL_SE[j].powi(2);
            value += normal_log_density(SCHOOL_Y[j], theta, SCHOOL_SE[j])
                + normal_log_density(z[j], 0., 1.);
            gradient[0] += likelihood_gradient;
            gradient[1] += likelihood_gradient * tau * z[j];
            gradient[j + 2] = -z[j] + likelihood_gradient * tau;
        }
        if value.is_finite() && gradient.iter().all(|g| g.is_finite()) {
            Ok(value)
        } else {
            Err(TargetError::recoverable("nonfinite target evaluation"))
        }
    }
}

struct Gaussian(usize);

impl Target for Gaussian {
    fn dimension(&self) -> usize {
        self.0
    }
    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        for (g, x) in gradient.iter_mut().zip(q) {
            *g = -*x;
        }
        Ok(-0.5 * q.iter().map(|x| x * x).sum::<f64>())
    }
}

fn column(posterior: &Posterior, k: usize) -> Vec<Vec<f64>> {
    let dimension = posterior.dimension();
    (0..posterior.chain_count())
        .map(|c| {
            posterior
                .chain_draws(c)
                .expect("chain")
                .chunks(dimension)
                .map(|row| row[k])
                .collect()
        })
        .collect()
}

fn run(which: &str, arm_name: &str, seed: u64, out: &Path) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    let (tuning, adaptation) = arm(arm_name)?;
    let sampler = Sampler::new()
        .warmup(1000)
        .draws(1000)
        .chains(4)
        .threads(4)
        .seed(seed)
        .metric(Metric::diagonal())
        .adaptation(adaptation)
        .tuning(tuning)
        .limits(Limits::new().admit_worst_case());
    let begin = Instant::now();
    let posterior = match which {
        "eight" => {
            let starts: Vec<Vec<f64>> = [-2.0, -1.0, 0.0, 1.0]
                .iter()
                .map(|log_tau| {
                    let mut q = vec![0.0; 10];
                    q[1] = *log_tau;
                    q
                })
                .collect();
            sampler.run(&EightSchoolsNoncentered, &starts)?
        }
        "gauss100" => sampler.run_with_init(&Gaussian(100), &Init::uniform())?,
        other => return Err(format!("unknown target {other:?}").into()),
    };
    let wall = begin.elapsed().as_secs_f64();
    let dimension = posterior.dimension();
    let mut bulk = Vec::with_capacity(dimension);
    let mut tail = Vec::with_capacity(dimension);
    let mut rhats = Vec::with_capacity(dimension);
    for k in 0..dimension {
        let cols = column(&posterior, k);
        let refs: Vec<&[f64]> = cols.iter().map(Vec::as_slice).collect();
        bulk.push(ess_bulk(&refs));
        tail.push(ess_tail(&refs));
        rhats.push(rhat(&refs));
    }
    let fmin = |v: &[f64]| v.iter().copied().fold(f64::INFINITY, f64::min);
    let fmax = |v: &[f64]| v.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    let calls: usize = posterior
        .chains()
        .iter()
        .map(|c| c.telemetry().total().target_calls_total())
        .sum();
    let mut divergences = 0usize;
    let mut depth_caps = 0usize;
    let mut exhaustions = 0usize;
    let mut top_level = 0usize;
    let mut refined = 0usize;
    let mut retained_transitions = 0usize;
    for chain in posterior.chains() {
        let r = chain.telemetry().retained();
        divergences += r.divergences();
        depth_caps += r.maximum_depth_stops();
        exhaustions += r.refinement_exhaustion_stops();
        let levels = chain.metadata().max_refinement_levels();
        let first = chain.diagnostics().len() - chain.retained();
        for d in &chain.diagnostics()[first..] {
            retained_transitions += 1;
            match d.selected_refinement_level() {
                Some(l) if l + 1 == levels => {
                    top_level += 1;
                    refined += 1;
                }
                Some(l) if l > 0 => refined += 1,
                _ => {}
            }
        }
    }
    let steps: Vec<f64> = posterior
        .chains()
        .iter()
        .map(|c| c.metadata().tuning().step_size())
        .collect();
    let min_bulk = fmin(&bulk);
    let min_tail = fmin(&tail);
    let max_rhat = fmax(&rhats);
    let payload = json!({
        "schema": "funnel-tail-deficit-v1-side",
        "target": which, "arm": arm_name, "seed": seed,
        "chains": 4, "warmup": 1000, "draws": 1000,
        "algorithm_revision": posterior.algorithm_revision(),
        "target_calls_total": calls,
        "min_bulk_ess": min_bulk, "min_tail_ess": min_tail, "max_rhat": max_rhat,
        "min_bulk_ess_per_gradient": min_bulk / calls as f64,
        "retained_divergences": divergences,
        "retained_depth_caps": depth_caps,
        "retained_refinement_exhaustions": exhaustions,
        "retained_refined_transitions": refined,
        "retained_top_level_transitions": top_level,
        "retained_transitions": retained_transitions,
        "final_step_sizes": steps,
        "house_health": max_rhat <= 1.01 && min_bulk >= 400.0 && min_tail >= 400.0 && divergences == 0,
        "wall_seconds_pinned_cotenanted": wall,
    });
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    eprintln!(
        "side {which} {arm_name} seed {seed}: min bulk {min_bulk:.0} tail {min_tail:.0} R-hat {max_rhat:.4} \
         calls {calls} ESS/grad {:.3e} div {divergences} caps {depth_caps} wall {wall:.1}s",
        min_bulk / calls as f64
    );
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [which, arm, seed, out] => match seed.parse::<u64>() {
            Ok(s) => run(which, arm, s, Path::new(out)),
            Err(_) => Err("seed must be an integer".into()),
        },
        _ => Err("usage: side <eight|gauss100> <arm> <seed> <out.json>".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
