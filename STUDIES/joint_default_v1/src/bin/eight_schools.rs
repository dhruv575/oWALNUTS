//! The noncentered Eight Schools strict track of
//! `STUDIES/eight_schools_v9_rebench_v1` (target, starts, tuning, warmup and
//! timing boundary copied verbatim) under one of the four arms of the joint
//! default study (`arms.rs`: U-turn rule and diagonal-metric regularisation;
//! the regularisation enters through
//! `WarmupConfig::with_metric_regularization` on the strict track's
//! `WarmupConfig::new(0.95).with_mass_adaptation(true)`).
//!
//! Usage: `eight-schools <da|rhosum|stanreg|joint> <seed> <reps> <out.json>`
//!
//! Each seed is sampled `reps` times; samples must be bit-identical across
//! repetitions and only wall time varies.
#![forbid(unsafe_code)]

#[path = "../arms.rs"]
mod arms;

use arms::Arm;
use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DiagonalMass, KernelTuning, RunConfig, Target, TargetError,
    TargetEvaluationAdmissionLimit, TargetEvaluationBudget, WarmupConfig,
    preflight_chains_with_target_budget, sample_chains_with_target_budget,
};
use serde_json::json;
use sha2::{Digest, Sha256};
use std::{
    env,
    error::Error,
    fs,
    num::NonZeroUsize,
    path::Path,
    sync::atomic::{AtomicUsize, Ordering},
    time::Instant,
};

const CHAINS: usize = 4;
const CAP: usize = 10_000_000;
const LOG_2PI: f64 = 1.837_877_066_409_345_3;
const Y: [f64; 8] = [28., 8., -3., 7., -1., 1., 18., 12.];
const SE: [f64; 8] = [15., 10., 16., 11., 9., 11., 10., 18.];
const SEEDS: [u64; 3] = [86_101, 86_102, 86_103];

fn normal_log_density(x: f64, mean: f64, sd: f64) -> f64 {
    -0.5 * LOG_2PI - sd.ln() - 0.5 * ((x - mean) / sd).powi(2)
}

fn noncentered_log_density_gradient(q: &[f64], gradient: &mut [f64]) -> f64 {
    assert_eq!(q.len(), 10);
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
        let residual = Y[j] - theta;
        let likelihood_gradient = residual / SE[j].powi(2);
        value += normal_log_density(Y[j], theta, SE[j]) + normal_log_density(z[j], 0., 1.);
        gradient[0] += likelihood_gradient;
        gradient[1] += likelihood_gradient * tau * z[j];
        gradient[j + 2] = -z[j] + likelihood_gradient * tau;
    }
    value
}

struct CountingTarget {
    calls: AtomicUsize,
}

impl Target for CountingTarget {
    fn dimension(&self) -> usize {
        10
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        let n = self.calls.fetch_add(1, Ordering::Relaxed) + 1;
        if n > CAP {
            return Err(TargetError::new(
                "runtime target-evaluation budget exhausted",
            ));
        }
        let value = noncentered_log_density_gradient(q, g);
        if value.is_finite() && g.iter().all(|x| x.is_finite()) {
            Ok(value)
        } else {
            Err(TargetError::new("nonfinite target evaluation"))
        }
    }
}

fn starts() -> Vec<Vec<f64>> {
    [-2., -1., 0., 1.]
        .map(|x| {
            let mut q = vec![0.; 10];
            q[1] = x;
            q
        })
        .to_vec()
}

fn config(seed: u64, arm: &Arm) -> Result<RunConfig, Box<dyn Error>> {
    Ok(RunConfig::new(1000, NonZeroUsize::new(1000).unwrap(), seed)
        .with_tuning(
            KernelTuning::new(
                0.3,
                NonZeroUsize::new(8).unwrap(),
                NonZeroUsize::new(1).unwrap(),
                NonZeroUsize::new(8).unwrap(),
                1.,
            )?
            .with_divergence_threshold(1000.)?
            .with_options(arm.kernel_options()),
        )
        .with_warmup(
            WarmupConfig::new(0.95)?
                .with_mass_adaptation(true)
                .with_metric_regularization(arm.regularization),
        ))
}

fn run_seed(arm_name: &str, seed: u64, reps: usize, out: &Path) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    if !SEEDS.contains(&seed) {
        return Err("seed outside protocol".into());
    }
    if reps == 0 {
        return Err("reps must be positive".into());
    }
    let arm = Arm::parse(arm_name)?;
    let config = config(seed, &arm)?;
    let exact = config.worst_case_target_evaluations(NonZeroUsize::new(CHAINS).unwrap())?;
    let admission = TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap());
    let diagonal = DiagonalMass::identity(NonZeroUsize::new(10).unwrap());
    {
        let target = CountingTarget {
            calls: AtomicUsize::new(0),
        };
        let budget = TargetEvaluationBudget::new(NonZeroUsize::new(CAP).unwrap());
        preflight_chains_with_target_budget(
            &target,
            &starts(),
            &diagonal,
            &config,
            admission,
            &budget,
        )?;
        if target.calls.load(Ordering::Relaxed) != 0 || budget.started() != 0 {
            return Err("preflight entered target".into());
        }
    }
    let mut walls = Vec::with_capacity(reps);
    let mut works = Vec::with_capacity(reps);
    let mut hashes = Vec::with_capacity(reps);
    let mut first = None;
    for _ in 0..reps {
        let target = CountingTarget {
            calls: AtomicUsize::new(0),
        };
        let budget = TargetEvaluationBudget::new(NonZeroUsize::new(CAP).unwrap());
        let begin = Instant::now();
        let sampled = sample_chains_with_target_budget(
            &target,
            &starts(),
            &diagonal,
            &config,
            NonZeroUsize::new(1).unwrap(),
            admission,
            &budget,
        )?;
        walls.push(begin.elapsed().as_secs_f64());
        works.push(target.calls.load(Ordering::Relaxed));
        let mut hasher = Sha256::new();
        for chain in sampled.chains() {
            for i in 0..1000 {
                for x in chain.sample(i).unwrap() {
                    hasher.update(x.to_le_bytes());
                }
            }
        }
        hashes.push(format!("{:x}", hasher.finalize()));
        if first.is_none() {
            first = Some(sampled);
        }
    }
    if hashes.iter().any(|h| h != &hashes[0]) {
        return Err("samples differ across repetitions".into());
    }
    let sampled = first.unwrap();
    let chains = sampled
        .chains()
        .iter()
        .map(|chain| {
            let retained = chain.telemetry().retained();
            let discarded = chain.telemetry().discarded();
            json!({
                "samples": (0..1000).map(|i| chain.sample(i).unwrap()).collect::<Vec<_>>(),
                "divergences": retained.divergences(),
                "maximum_depth_stops": retained.maximum_depth_stops(),
                "invalid_stops": retained.invalid_evaluation_stops(),
                "recoverable_stops": retained.recoverable_target_failures(),
                "refinement_exhaustions": retained.refinement_exhaustion_stops(),
                "retained_target_calls": retained.target_calls_total(),
                "warmup_target_calls": discarded.target_calls_total(),
                "final_step_size": chain.metadata().tuning().step_size(),
            })
        })
        .collect::<Vec<_>>();
    let payload = json!({
        "schema": "joint-default-v1-eight-schools-cell",
        "arm": arm.name,
        "u_turn": format!("{:?}", arm.u_turn),
        "metric_regularization": format!("{:?}", arm.regularization),
        "seed": seed,
        "starts": starts(),
        "warmup": 1000, "retained": 1000, "chains": CHAINS,
        "target_accept": 0.95, "depth": 8, "metric": "adapted diagonal", "threads": 1,
        "tuning": {"step_size": 0.3, "max_depth": 8, "min_micro_steps": 1,
                   "max_refinement_levels": 8, "max_error": 1.0, "divergence_threshold": 1000.0},
        "callback_cap": CAP,
        "constructor_admission_bound": exact,
        "timing_estimand": "strict_sampler_call_wall_before_telemetry_and_serialization",
        "repetitions": reps,
        "wall_seconds": walls,
        "callbacks_started": works,
        "sample_sha256": hashes[0],
        "chains_data": chains,
        "algorithm_revision": ALGORITHM_REVISION,
    });
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [arm, seed, reps, out] => match (seed.parse::<u64>(), reps.parse::<usize>()) {
            (Ok(s), Ok(r)) => run_seed(arm, s, r, Path::new(out)),
            _ => Err("seed and reps must be integers".into()),
        },
        _ => Err("usage: <da|rhosum|stanreg|joint> <seed> <reps> <out.json>".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
