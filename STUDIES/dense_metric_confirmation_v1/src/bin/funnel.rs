//! Neal's 10-D funnel side check of WP51 (`STUDIES/dense_metric_confirmation_v1`),
//! the WP48 / posteriordb_bench_v6 funnel protocol with the metric arm as an argument.
//!
//! Usage: `funnel <diag|dense-legacy|dense-candidate|dense-default> <seed> <out.json>`
//! or `funnel selfcheck`.
//!
//! Four starts `omega in {-3, -1, 1, 3}`, 2,000 warmup and 20,000 retained
//! draws per chain, `P(omega < -5)` (exact 0.0478) with the ArviZ-style MCSE
//! z (the gate, `|z| <= 2` per seed) and a batch-means z (reported). Arms are
//! defined exactly as in `src/main.rs`.
#![forbid(unsafe_code)]

use owalnuts::diagnostics::{ess_bulk, ess_tail, mcse_mean, rhat};
use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_WARMUP_EXHAUSTION, Limits, Metric, Sampler,
    Target, TargetError, Tuning, WarmupConfig,
};
use owalnuts::walnutpie::{
    ChainRescueOutcome, DenseMetricRegularization, DenseWarmupSeeding, MetricUpdateOutcome,
    RunTelemetry,
};
use serde_json::json;
use std::{env, error::Error, fs, path::Path, time::Instant};

const DIMENSION: usize = 10;
const EXACT_TAIL_MASS: f64 = 0.047_790_352_272_814_7;
const EXACT_OMEGA_VARIANCE: f64 = 9.0;
const WARMUP: usize = 2_000;
const DRAWS: usize = 20_000;
const BATCH: usize = 500;

struct Funnel;

fn rescues_json(telemetry: &RunTelemetry) -> Vec<serde_json::Value> {
    telemetry
        .chain_rescues()
        .iter()
        .map(|update| {
            let outcome = match update.outcome() {
                ChainRescueOutcome::Kept => json!({"kind": "kept"}),
                ChainRescueOutcome::Skipped(reason) => {
                    json!({"kind": "skipped", "reason": format!("{reason:?}")})
                }
                ChainRescueOutcome::Restarted {
                    source,
                    criterion,
                    source_position,
                    step_after,
                } => json!({
                    "kind": "restarted",
                    "source": source,
                    "criterion": format!("{criterion:?}"),
                    "source_position": source_position,
                    "step_after": step_after
                }),
                ChainRescueOutcome::Pooled {
                    step_after,
                    pooled_sample_count,
                } => json!({
                    "kind": "pooled",
                    "step_after": step_after,
                    "pooled_sample_count": pooled_sample_count
                }),
                _ => json!({"kind": "other"}),
            };
            json!({
                "window_index": update.window_index(),
                "transition": update.transition(),
                "chain": update.chain(),
                "window_transitions": update.window_transitions(),
                "step_before": update.step_before(),
                "median_log_density": update.median_log_density(),
                "log_density_iqr": update.log_density_iqr(),
                "outcome": outcome,
            })
        })
        .collect()
}

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

fn arm_config(arm: &str) -> Result<(Metric, Adaptation), Box<dyn Error>> {
    let custom = |seeding, regularization, symmetrize| -> Result<Adaptation, Box<dyn Error>> {
        Ok(Adaptation::Custom(
            WarmupConfig::new(0.8)?
                .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
                .with_dense_metric_regularization(regularization)
                .with_dense_warmup_seeding(seeding)
                .with_dense_symmetrized_precision(symmetrize),
        ))
    };
    match arm {
        "diag" => Ok((Metric::diagonal(), Adaptation::default())),
        // Whatever the library currently ships for Metric::dense().
        "dense-default" => Ok((Metric::dense(), Adaptation::default())),
        "dense-legacy" => Ok((
            Metric::dense(),
            custom(
                DenseWarmupSeeding::Legacy,
                DenseMetricRegularization::MeanVarianceShrinkage,
                false,
            )?,
        )),
        "dense-candidate" => Ok((
            Metric::dense(),
            custom(
                DenseWarmupSeeding::PerTransition,
                DenseMetricRegularization::Stan,
                true,
            )?,
        )),
        other => Err(format!("unknown arm {other:?}").into()),
    }
}

fn starts() -> Vec<Vec<f64>> {
    [-3.0, -1.0, 1.0, 3.0]
        .into_iter()
        .map(|omega| {
            let mut q = vec![0.0; DIMENSION];
            q[0] = omega;
            q
        })
        .collect()
}

/// Non-evidence check (seed 1, 200 + 200 draws): which explicit arm the
/// library's `Metric::dense()` + `Adaptation::default()` is bit-identical to.
/// Before the WP51 flip it must equal `dense-legacy`; after it, `dense-candidate`.
fn selfcheck() -> Result<(), Box<dyn Error>> {
    let draws = |arm: &str| -> Result<Vec<f64>, Box<dyn Error>> {
        let (metric, adaptation) = arm_config(arm)?;
        let posterior = Sampler::new()
            .warmup(200)
            .draws(200)
            .chains(4)
            .threads(4)
            .seed(1)
            .metric(metric)
            .adaptation(adaptation)
            .limits(Limits::new().admit_worst_case())
            .run(&Funnel, &starts())?;
        Ok(posterior.draws().flat_map(|d| d.iter().copied()).collect())
    };
    let default = draws("dense-default")?;
    let legacy = draws("dense-legacy")?;
    let candidate = draws("dense-candidate")?;
    if legacy == candidate {
        return Err("legacy and candidate arms are identical".into());
    }
    let equals = if default == legacy {
        "dense-legacy"
    } else if default == candidate {
        "dense-candidate"
    } else {
        return Err("Metric::dense() + Adaptation::default() matches neither explicit arm".into());
    };
    eprintln!(
        "selfcheck ok: Metric::dense() + Adaptation::default() is bit-identical to {equals} ({} values)",
        default.len()
    );
    println!("{equals}");
    Ok(())
}

fn run(arm: &str, seed: u64, out: &Path) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    let tuning = Tuning::default();
    let kernel = tuning.to_kernel()?;
    let (metric, adaptation) = arm_config(arm)?;
    let sampler = Sampler::new()
        .warmup(WARMUP)
        .draws(DRAWS)
        .chains(4)
        .threads(4)
        .seed(seed)
        .metric(metric)
        .adaptation(adaptation)
        .tuning(tuning)
        .limits(Limits::new().admit_worst_case());
    let starts = starts();
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
        let chain_tuning = chain.metadata().tuning();
        let work = chain.telemetry().total();
        let retained = chain.telemetry().retained();
        chains_json.push(json!({
            "final_max_error": chain_tuning.max_error(),
            "final_step_size": chain_tuning.step_size(),
            "mass_diagonal": chain.metadata().mass_diagonal(),
            "target_calls": work.target_calls_total(),
            "retained_target_calls": retained.target_calls_total(),
            "depth_caps": retained.maximum_depth_stops(),
            "divergences": retained.divergences(),
            "refinement_exhaustions": retained.refinement_exhaustion_stops(),
            "chain_rescues": rescues_json(chain.telemetry()),
            "final_mass_dense": chain.telemetry().metric_updates().iter().rev()
                .find(|u| u.outcome() == MetricUpdateOutcome::Installed)
                .and_then(|u| u.mass_dense().map(<[f64]>::to_vec)),
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
        "schema": "dense-metric-confirmation-v1-funnel",
        "tuning": "defaults",
        "arm": arm,
        "u_turn": format!("{:?}", kernel.options().u_turn),
        "exhaustion_retained": format!("{:?}", kernel.options().exhaustion),
        "metric_regularization": format!("{:?}", owalnuts::sampler::DEFAULT_METRIC_REGULARIZATION),
        "warmup_exhaustion_rule": format!("{:?}", owalnuts::sampler::DEFAULT_WARMUP_EXHAUSTION),
        "chain_rescue": format!("{:?}", owalnuts::sampler::DEFAULT_CHAIN_RESCUE),
        "kernel_tuning": {"step_size": kernel.step_size(), "max_depth": kernel.max_depth(),
                          "max_refinement_levels": kernel.max_refinement_levels(),
                          "max_error": kernel.max_error()},
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
        "funnel {arm} seed {seed}: P(omega < -5) {estimate:.4} +- {mcse:.4} \
         (z {z:+.2}; batch-means z {z_batch:+.2}), {calls} target calls, \
         rescued {}, wall {wall:.1}s",
        posterior
            .telemetry()
            .flat_map(|telemetry| telemetry.chain_rescues())
            .filter(|update| matches!(update.outcome(), ChainRescueOutcome::Restarted { .. }))
            .count()
    );
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [cmd] if cmd == "selfcheck" => selfcheck(),
        [arm, seed, out] => match seed.parse::<u64>() {
            Ok(s) => run(arm, s, Path::new(out)),
            Err(_) => Err("seed must be an integer".into()),
        },
        _ => Err("usage: <diag|dense-legacy|dense-candidate|dense-default> <seed> <out.json> | selfcheck".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
