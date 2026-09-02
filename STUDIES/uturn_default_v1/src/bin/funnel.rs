//! Neal's 10-D funnel tail-mass check under a U-turn rule, at the paper
//! tuning or the sampler defaults.
//!
//! Usage: `funnel <paper|defaults> <endpoints|rhosum|cross> <seed> <out.json>`
//!
//! * `paper`: the `examples/funnel_kernel_options.rs` protocol (Appendix C
//!   warmup, identity metric, `h = 0.1`, `delta = 1`, eight refinement
//!   levels, depth 10).
//! * `defaults`: the `STUDIES/freeze_mode_v1` `checks funnel` protocol
//!   (`Tuning::default()`, adapted diagonal metric, dual averaging at 0.8).
//!
//! Both: four starts `omega in {-3, -1, 1, 3}`, 2,000 warmup and 20,000
//! retained draws per chain, `P(omega < -5)` (exact 0.0478) with a
//! batch-means standard error (batches of 500 draws per chain).
#![forbid(unsafe_code)]

use owalnuts::diagnostics::{ess_bulk, rhat};
use owalnuts::sampler::{
    Adaptation, Limits, Metric, PaperAdaptationConfig, Sampler, Target, TargetError, Tuning,
};
use owalnuts::walnutpie::{KernelOptions, UTurnRule};
use serde_json::json;
use std::{env, error::Error, fs, path::Path};

const DIMENSION: usize = 10;
const EXACT_TAIL_MASS: f64 = 0.047_790_352_272_814_7;
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
        Ok(-omega * omega / 18.0 - 0.5 * tail * omega - 0.5 * inverse_variance * sum_squares)
    }
}

fn run(tuning_name: &str, rule_name: &str, seed: u64, out: &Path) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    let u_turn = match rule_name {
        "endpoints" => UTurnRule::Endpoints,
        "rhosum" => UTurnRule::MomentumSum,
        "cross" => UTurnRule::EndpointsWithCross,
        other => return Err(format!("unknown rule {other:?}").into()),
    };
    let options = KernelOptions { u_turn, ..KernelOptions::default() };
    let sampler = Sampler::new()
        .warmup(WARMUP)
        .draws(DRAWS)
        .chains(4)
        .threads(4)
        .seed(seed)
        .limits(Limits::new().admit_worst_case());
    let sampler = match tuning_name {
        "paper" => sampler
            .metric(Metric::Identity)
            .adaptation(Adaptation::Paper(PaperAdaptationConfig::default()))
            .tuning(
                Tuning::new()
                    .step_size(0.1)
                    .max_depth(10)
                    .max_refinement_levels(8)
                    .max_error(1.0)
                    .kernel_options(options),
            ),
        "defaults" => sampler
            .metric(Metric::diagonal())
            .adaptation(Adaptation::default())
            .tuning(Tuning::default().kernel_options(options)),
        other => return Err(format!("unknown tuning {other:?}").into()),
    };
    let starts: Vec<Vec<f64>> = [-3.0, -1.0, 1.0, 3.0]
        .into_iter()
        .map(|omega| {
            let mut q = vec![0.0; DIMENSION];
            q[0] = omega;
            q
        })
        .collect();
    let posterior = sampler.run(&Funnel, &starts)?;

    let mut below = 0usize;
    let mut total = 0usize;
    let mut batch_means: Vec<f64> = Vec::new();
    let mut chains_json = Vec::new();
    let mut omega_columns: Vec<Vec<f64>> = Vec::new();
    for chain in posterior.chains() {
        let tuning = chain.metadata().tuning();
        let work = chain.telemetry().total();
        let retained = chain.telemetry().retained();
        chains_json.push(json!({
            "final_max_error": tuning.max_error(),
            "final_step_size": tuning.step_size(),
            "target_calls": work.target_calls_total(),
            "retained_target_calls": retained.target_calls_total(),
            "depth_caps": retained.maximum_depth_stops(),
            "divergences": retained.divergences(),
            "refinement_exhaustions": retained.refinement_exhaustion_stops(),
        }));
        let mut in_batch = 0usize;
        let mut omegas = Vec::with_capacity(DRAWS);
        for draw in 0..chain.retained() {
            let omega = chain.sample(draw).expect("draw")[0];
            omegas.push(omega);
            total += 1;
            if omega < -5.0 {
                below += 1;
                in_batch += 1;
            }
            if (draw + 1) % BATCH == 0 {
                batch_means.push(in_batch as f64 / BATCH as f64);
                in_batch = 0;
            }
        }
        omega_columns.push(omegas);
    }
    let estimate = below as f64 / total as f64;
    let batches = batch_means.len() as f64;
    let batch_variance = batch_means
        .iter()
        .map(|mean| (mean - estimate) * (mean - estimate))
        .sum::<f64>()
        / (batches - 1.0);
    let standard_error = (batch_variance / batches).sqrt();
    let z = (estimate - EXACT_TAIL_MASS) / standard_error;
    let refs: Vec<&[f64]> = omega_columns.iter().map(Vec::as_slice).collect();
    let calls: usize = posterior
        .chains()
        .iter()
        .map(|c| c.telemetry().total().target_calls_total())
        .sum();
    let payload = json!({
        "schema": "uturn-default-v1-funnel",
        "tuning": tuning_name, "u_turn": format!("{u_turn:?}"), "seed": seed,
        "chains": 4, "warmup": WARMUP, "draws": DRAWS,
        "tail_mass": {"estimate": estimate, "batch_means_se": standard_error,
                      "exact": EXACT_TAIL_MASS, "z": z, "below": below, "total": total,
                      "batches": batch_means.len()},
        "batch_means": batch_means,
        "omega_bulk_ess": ess_bulk(&refs), "omega_rhat": rhat(&refs),
        "target_calls_total": calls,
        "chains_data": chains_json,
        "algorithm_revision": posterior.algorithm_revision(),
    });
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    eprintln!(
        "funnel {tuning_name} {rule_name} seed {seed}: P(omega < -5) {estimate:.4} +- {standard_error:.4} \
         (z {z:+.2}), {calls} target calls"
    );
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [tuning, rule, seed, out] => match seed.parse::<u64>() {
            Ok(s) => run(tuning, rule, s, Path::new(out)),
            Err(_) => Err("seed must be an integer".into()),
        },
        _ => Err("usage: <paper|defaults> <endpoints|rhosum|cross> <seed> <out.json>".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
