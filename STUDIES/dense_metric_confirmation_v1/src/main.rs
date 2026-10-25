//! WP51 oWALNUTS cell: one (model, arm, seed) of the dense-default confirmation
//! (`STUDIES/dense_metric_confirmation_v1`), the WP48 harness with WP51's arms.
//!
//! Usage: `dense-cell <model.so> <data.json> <arm> <seed> <out.json> [threads]`
//!
//! Arms (everything else is `owalnuts::sampler` defaults: `Tuning::default()`,
//! `Init::uniform()`, `Limits::admit_worst_case()`, 4 chains, 1,000 + 1,000):
//! - `diag`: `Metric::diagonal()` + `Adaptation::default()` (the shipped default).
//! - `dense-legacy`: `Metric::dense()` with the pre-WP51 dense warmup defaults
//!   (`DenseWarmupSeeding::Legacy`, `DenseMetricRegularization::MeanVarianceShrinkage`,
//!   unsymmetrised precision), stated explicitly.
//! - `dense-candidate`: `Metric::dense()` with `PerTransition`, `Stan` and
//!   `with_dense_symmetrized_precision(true)`, stated explicitly.
//!
//! Writes unconstrained retained draws, per-chain work and health counters,
//! the final installed metric and every metric update to JSON.
#![forbid(unsafe_code)]

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_U_TURN_RULE, DEFAULT_WARMUP_EXHAUSTION,
    Init, Limits, Metric, Sampler, Target, Tuning, WarmupConfig, uniform_starts,
};
use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DenseMetricRegularization, DenseWarmupSeeding, MetricUpdateOutcome,
};
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::json;
use std::{env, error::Error, fs, path::Path, time::Instant};

const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;
const TARGET_ACCEPT: f64 = 0.8;

/// The configuration `Adaptation::default()` builds for an adapting metric
/// (`WarmupConfig::new(0.8)` + `DEFAULT_WARMUP_EXHAUSTION` +
/// `DEFAULT_METRIC_REGULARIZATION`) with the three dense warmup settings
/// stated explicitly, so the arm does not depend on the library's defaults.
fn dense_custom(
    seeding: DenseWarmupSeeding,
    regularization: DenseMetricRegularization,
    symmetrize: bool,
) -> Result<Adaptation, Box<dyn Error>> {
    Ok(Adaptation::Custom(
        WarmupConfig::new(TARGET_ACCEPT)?
            .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
            .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
            .with_dense_metric_regularization(regularization)
            .with_dense_warmup_seeding(seeding)
            .with_dense_symmetrized_precision(symmetrize),
    ))
}

fn arm_config(arm: &str) -> Result<(Metric, Adaptation, &'static str), Box<dyn Error>> {
    match arm {
        "diag" => Ok((Metric::diagonal(), Adaptation::default(), "diagonal")),
        // The dense defaults before WP51 (bit-identical to Metric::dense() +
        // Adaptation::default() on the pre-flip library; `funnel selfcheck`).
        "dense-legacy" => Ok((
            Metric::dense(),
            dense_custom(
                DenseWarmupSeeding::Legacy,
                DenseMetricRegularization::MeanVarianceShrinkage,
                false,
            )?,
            "Legacy seeding, MeanVarianceShrinkage, unsymmetrised precision",
        )),
        // The candidate defaults under test.
        "dense-candidate" => Ok((
            Metric::dense(),
            dense_custom(
                DenseWarmupSeeding::PerTransition,
                DenseMetricRegularization::Stan,
                true,
            )?,
            "PerTransition seeding, Stan, symmetrised precision",
        )),
        other => Err(format!(
            "unknown arm {other:?} (expected diag, dense-legacy, dense-candidate)"
        )
        .into()),
    }
}

fn outcome_name(outcome: MetricUpdateOutcome) -> String {
    format!("{outcome:?}")
}

fn run(
    model: &Path,
    data: &Path,
    arm: &str,
    seed: u64,
    out: &Path,
    threads: usize,
) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    let (metric, adaptation, dense_regularization) = arm_config(arm)?;
    let data_json = fs::read_to_string(data)?;
    let target =
        ReplicatedStanTarget::load(model, &default_preload(), Some(&data_json), 1, threads)?;
    let dimension = target.dimension();
    let tuning = Tuning::default();
    let kernel = tuning.to_kernel()?;
    let max_depth = kernel.max_depth();
    let sampler = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .seed(seed)
        .threads(threads)
        .metric(metric)
        .adaptation(adaptation)
        .tuning(tuning)
        .limits(Limits::new().admit_worst_case());

    let (radius, max_attempts) = match Init::uniform() {
        Init::Uniform {
            radius,
            max_attempts,
        } => (radius, max_attempts),
        _ => unreachable!(),
    };
    let fail = |stage: &str, error: String, wall: f64, calls: usize| {
        json!({
            "schema": "dense-metric-confirmation-v1-cell",
            "sampler": format!("owalnuts-{arm}"),
            "seed": seed, "status": "error", "stage": stage, "error": error,
            "wall_seconds": wall, "target_calls": calls,
            "algorithm_revision": ALGORITHM_REVISION,
        })
    };
    let starts = match uniform_starts(&target, CHAINS, seed, radius, max_attempts) {
        Ok(s) => s,
        Err(e) => {
            fs::write(
                out,
                serde_json::to_vec_pretty(&fail("init", e.to_string(), 0.0, target.calls()))?,
            )?;
            return Err(e.into());
        }
    };
    let start_search_calls = target.calls();

    let begin = Instant::now();
    let result = sampler.run(&target, &starts);
    let wall = begin.elapsed().as_secs_f64();
    let posterior = match result {
        Ok(p) => p,
        Err(e) => {
            fs::write(
                out,
                serde_json::to_vec_pretty(&fail("sample", e.to_string(), wall, target.calls()))?,
            )?;
            return Err(e.into());
        }
    };

    let chains = posterior
        .chains()
        .iter()
        .map(|chain| {
            let t = chain.telemetry();
            let retained = t.retained();
            let discarded = t.discarded();
            let diags = &chain.diagnostics()[WARMUP..];
            let mut depth_hist = vec![0usize; max_depth + 1];
            for d in diags {
                depth_hist[d.depth().min(max_depth)] += 1;
            }
            let updates: Vec<_> = t
                .metric_updates()
                .iter()
                .map(|u| {
                    json!({
                        "window_index": u.window_index(),
                        "transition": u.transition(),
                        "sample_count": u.sample_count(),
                        "outcome": outcome_name(u.outcome()),
                        "shrinkage": u.shrinkage(),
                        "ridge": u.ridge(),
                        "condition_estimate": u.condition_estimate(),
                        "cholesky_failures": u.cholesky_failures(),
                        "step_before": u.step_before(),
                    })
                })
                .collect();
            let final_dense = t
                .metric_updates()
                .iter()
                .rev()
                .find(|u| u.outcome() == MetricUpdateOutcome::Installed)
                .and_then(|u| u.mass_dense().map(<[f64]>::to_vec));
            json!({
                "samples": (0..RETAINED).map(|i| chain.sample(i).unwrap()).collect::<Vec<_>>(),
                "divergences": retained.divergences(),
                "maximum_depth_stops": retained.maximum_depth_stops(),
                "invalid_stops": retained.invalid_evaluation_stops(),
                "refinement_exhaustions": retained.refinement_exhaustion_stops(),
                "retained_target_calls": retained.target_calls_total(),
                "warmup_target_calls": discarded.target_calls_total(),
                "total_target_calls": t.total().target_calls_total(),
                "warmup_divergences": discarded.divergences(),
                "final_step_size": chain.metadata().tuning().step_size(),
                "mass_diagonal": chain.metadata().mass_diagonal(),
                "final_mass_dense": final_dense,
                "metric_updates": updates,
                "retained_depth_histogram": depth_hist,
            })
        })
        .collect::<Vec<_>>();
    let payload = json!({
        "schema": "dense-metric-confirmation-v1-cell",
        "sampler": format!("owalnuts-{arm}"),
        "arm": arm,
        "status": "ok",
        "seed": seed,
        "model_library": model.display().to_string(),
        "threading": format!("{:?}", target.threading()), "replicas": target.replicas(),
        "dimension": dimension,
        "chains": CHAINS, "warmup": WARMUP, "retained": RETAINED, "threads": threads,
        "init": {"rule": "sampler::Init::uniform()", "radius": radius, "max_attempts": max_attempts,
                 "start_search_calls": start_search_calls},
        "starts": starts,
        "tuning": {"step_size": kernel.step_size(), "max_depth": max_depth,
                   "max_refinement_levels": kernel.max_refinement_levels(),
                   "max_error": kernel.max_error(),
                   "u_turn": format!("{:?}", kernel.options().u_turn),
                   "default_u_turn_rule": format!("{DEFAULT_U_TURN_RULE:?}")},
        "warmup_config": {"target_accept": TARGET_ACCEPT,
                          "warmup_exhaustion_rule": format!("{DEFAULT_WARMUP_EXHAUSTION:?}"),
                          "diagonal_metric_regularization": format!("{DEFAULT_METRIC_REGULARIZATION:?}"),
                          "dense_metric_regularization": dense_regularization},
        "timing_estimand": "wall around sampler::Sampler::run (warmup + retained, four parallel chains; start search excluded); contended shared machine",
        "wall_seconds": wall,
        "target_calls_total": target.calls(),
        "recoverable_failures_total": target.recoverable_failures(),
        "chains_data": chains,
        "algorithm_revision": posterior.algorithm_revision(),
    });
    fs::write(out, serde_json::to_vec(&payload)?)?;
    eprintln!(
        "{arm} seed {seed}: wall {wall:.3}s, calls {}, div {}",
        target.calls(),
        posterior
            .chains()
            .iter()
            .map(|c| c.telemetry().retained().divergences())
            .sum::<usize>(),
    );
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [model, data, arm, seed, out, rest @ ..] => {
            let threads = rest.first().map_or(Ok(CHAINS), |t| t.parse::<usize>());
            match (seed.parse::<u64>(), threads) {
                (Ok(s), Ok(t)) => run(Path::new(model), Path::new(data), arm, s, Path::new(out), t),
                _ => Err("seed and threads must be integers".into()),
            }
        }
        _ => Err("usage: <model.so> <data.json> <diag|dense-legacy|dense-candidate> <seed> <out.json> [threads]".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
