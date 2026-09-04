//! oWALNUTS arm of the posteriordb benchmark v6: one (model, arm, seed) cell.
//!
//! The v5 harness built against the current `src/`, whose `sampler`
//! defaults additionally include `DEFAULT_CHAIN_RESCUE =
//! ChainRescueConfig::restart_from_best()` since WP33. The only oWALNUTS arm
//! run in v6 is `da` = the shipped defaults. The JSON records every
//! chain-rescue boundary update so that the intervention is visible.
//!
//! Usage: `posteriordb-bench-v6 <model.so> <data.json> da <seed> <out.json> [threads]`
//!
//! Loads the BridgeStan-compiled model (built without `STAN_THREADS`) through
//! `owalnuts_bridgestan::ReplicatedStanTarget` (one library copy per chain
//! thread), draws four Stan-style starts with `owalnuts::sampler::Init::uniform()`
//! (uniform(-2, 2) unconstrained, redrawn until the log density and gradient
//! are finite), and runs 1,000 warmup + 1,000 retained transitions on four
//! parallel chains with `owalnuts::sampler` defaults (`Tuning::default()`:
//! `h0 = 0.5`, depth 10, eight refinement levels, `delta = 1`, momentum-sum
//! U-turn rule; adaptive diagonal metric from the identity with Stan's
//! regularisation). The arm selects the warmup rules only:
//! `da` = `Adaptation::DualAveraging { target_accept: 0.8 }` (the default),
//! `paper` = `Adaptation::Paper(PaperAdaptationConfig::default())` (the v4
//! robust rule), `stan` = `Adaptation::Custom(WarmupConfig::stan_style(0.8))`.
//! Writes unconstrained draws, per-chain work/health counters and the wall
//! around `Sampler::run` to JSON. Nothing is tuned per model.
#![forbid(unsafe_code)]

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_U_TURN_RULE, DEFAULT_WARMUP_EXHAUSTION,
    Init, Limits, Metric, Sampler, Target, Tuning, uniform_starts,
};
use owalnuts::walnutpie::{
    ALGORITHM_REVISION, ChainRescueConfig, ChainRescueOutcome, PAPER_ADAPTATION_REVISION,
    RunTelemetry,
};
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::json;
use std::{env, error::Error, fs, path::Path, time::Instant};

const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;
const TARGET_ACCEPT: f64 = 0.8;

fn adaptation(arm: &str) -> Result<Adaptation, Box<dyn Error>> {
    match arm {
        "da" => Ok(Adaptation::default()),
        other => Err(format!("unknown arm {other:?} (expected da)").into()),
    }
}

fn warmup_json(arm: &str) -> serde_json::Value {
    assert_eq!(arm, "da");
    let rescue = ChainRescueConfig::restart_from_best();
    json!({"mode": "dual_averaging", "target_accept": TARGET_ACCEPT,
    "warmup_exhaustion_rule": format!("{DEFAULT_WARMUP_EXHAUSTION:?}"),
    "metric_regularization": format!("{DEFAULT_METRIC_REGULARIZATION:?}"),
    "mass_adaptation": true,
    "chain_rescue": {
        "mode": format!("{:?}", rescue.mode()),
        "step_ratio": rescue.step_ratio(),
        "log_density_iqr_factor": rescue.log_density_iqr_factor(),
        "minimum_window_transitions": rescue.minimum_window_transitions(),
        "source": "sampler::DEFAULT_CHAIN_RESCUE"
    }})
}

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
    let data_json = fs::read_to_string(data)?;
    // One library copy per chain thread: the non-STAN_THREADS BridgeStan build
    // has a single global autodiff stack per loaded module (v1 wall-gap report).
    let target =
        ReplicatedStanTarget::load(model, &default_preload(), Some(&data_json), 1, threads)?;
    let dimension = target.dimension();
    let tuning = Tuning::default();
    let kernel = tuning.to_kernel()?;
    let max_depth = kernel.max_depth();
    let max_levels = kernel.max_refinement_levels();
    let sampler = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .seed(seed)
        .threads(threads)
        .metric(Metric::diagonal())
        .adaptation(adaptation(arm)?)
        .tuning(tuning)
        .limits(Limits::new().admit_worst_case());
    let worst_case = sampler.worst_case_target_evaluations(CHAINS)?;

    // Identical to `sampler.run_with_init(&target, &Init::uniform())`: the
    // starts are drawn here so that they and the search cost can be recorded.
    let (radius, max_attempts) = match Init::uniform() {
        Init::Uniform {
            radius,
            max_attempts,
        } => (radius, max_attempts),
        _ => unreachable!(),
    };
    let starts = match uniform_starts(&target, CHAINS, seed, radius, max_attempts) {
        Ok(s) => s,
        Err(e) => {
            let payload = json!({
                "schema": "posteriordb-bench-v6-cell",
                "sampler": format!("owalnuts-{arm}"),
                "seed": seed, "status": "error", "stage": "init", "error": e.to_string(),
                "wall_seconds": 0.0, "target_calls": target.calls(),
                "recoverable_failures": target.recoverable_failures(),
                "algorithm_revision": ALGORITHM_REVISION,
            });
            fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
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
            let payload = json!({
                "schema": "posteriordb-bench-v6-cell",
                "sampler": format!("owalnuts-{arm}"),
                "seed": seed, "status": "error", "stage": "sample", "error": e.to_string(),
                "wall_seconds": wall, "target_calls": target.calls(),
                "start_search_calls": start_search_calls,
                "recoverable_failures": target.recoverable_failures(),
                "algorithm_revision": ALGORITHM_REVISION,
            });
            fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
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
            let mut level_hist = vec![0usize; max_levels + 1];
            for d in diags {
                depth_hist[d.depth().min(max_depth)] += 1;
                if let Some(l) = d.selected_refinement_level() {
                    level_hist[l.min(max_levels)] += 1;
                }
            }
            let paper: Vec<_> = t
                .paper_adaptation_updates()
                .iter()
                .map(|u| {
                    json!({
                        "transition": u.transition(),
                        "window_index": u.window_index(),
                        "orbits": u.orbits(),
                        "inflation_quantile": u.inflation_quantile(),
                        "max_error_before": u.max_error_before(),
                        "max_error_after": u.max_error_after(),
                        "unrefined_fraction_mean": u.unrefined_fraction_mean(),
                        "step_before": u.step_before(),
                    })
                })
                .collect();
            json!({
                "samples": (0..RETAINED).map(|i| chain.sample(i).unwrap()).collect::<Vec<_>>(),
                "divergences": retained.divergences(),
                "maximum_depth_stops": retained.maximum_depth_stops(),
                "invalid_stops": retained.invalid_evaluation_stops(),
                "recoverable_failures": retained.recoverable_target_failures(),
                "refinement_exhaustions": retained.refinement_exhaustion_stops(),
                "retained_target_calls": retained.target_calls_total(),
                "warmup_target_calls": discarded.target_calls_total(),
                "warmup_divergences": discarded.divergences(),
                "final_step_size": chain.metadata().tuning().step_size(),
                "final_max_error": chain.metadata().tuning().max_error(),
                "mass_diagonal": chain.metadata().mass_diagonal(),
                "retained_depth_histogram": depth_hist,
                "retained_refinement_level_histogram": level_hist,
                "paper_adaptation_updates": paper,
                "chain_rescues": rescues_json(t),
            })
        })
        .collect::<Vec<_>>();
    let payload = json!({
        "schema": "posteriordb-bench-v6-cell",
        "sampler": format!("owalnuts-{arm}"),
        "status": "ok",
        "seed": seed,
        "model_library": model.display().to_string(),
        "model_info": target.info(),
        "threading": format!("{:?}", target.threading()), "replicas": target.replicas(),
        "dimension": dimension,
        "chains": CHAINS, "warmup": WARMUP, "retained": RETAINED, "threads": threads,
        "init": {"rule": "sampler::Init::uniform()", "radius": radius, "max_attempts": max_attempts,
                 "start_search_calls": start_search_calls},
        "starts": starts,
        "tuning": {"step_size": kernel.step_size(), "max_depth": max_depth,
                   "min_micro_steps": kernel.min_micro_steps(),
                   "max_refinement_levels": max_levels, "max_error": kernel.max_error(),
                   "divergence_threshold": kernel.divergence_threshold(),
                   "u_turn": format!("{:?}", kernel.options().u_turn),
                   "exhaustion": format!("{:?}", kernel.options().exhaustion),
                   "default_u_turn_rule": format!("{DEFAULT_U_TURN_RULE:?}"),
                   "source": "owalnuts::sampler::Tuning::default()"},
        "warmup_config": warmup_json(arm),
        "constructor_admission_bound": worst_case,
        "timing_estimand": "wall around sampler::Sampler::run (warmup + retained, four parallel chains; start search excluded)",
        "wall_seconds": wall,
        "target_calls_total": target.calls(),
        "recoverable_failures_total": target.recoverable_failures(),
        "chains_data": chains,
        "algorithm_revision": posterior.algorithm_revision(),
        "paper_adaptation_revision": PAPER_ADAPTATION_REVISION,
    });
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    eprintln!(
        "{arm} seed {seed}: wall {wall:.3}s, calls {}, div {}, rescued {}",
        target.calls(),
        posterior
            .chains()
            .iter()
            .map(|c| c.telemetry().retained().divergences())
            .sum::<usize>(),
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
        [model, data, arm, seed, out, rest @ ..] => {
            let threads = rest.first().map_or(Ok(CHAINS), |t| t.parse::<usize>());
            match (seed.parse::<u64>(), threads) {
                (Ok(s), Ok(t)) => run(Path::new(model), Path::new(data), arm, s, Path::new(out), t),
                _ => Err("seed and threads must be integers".into()),
            }
        }
        _ => Err("usage: <model.so> <data.json> <da> <seed> <out.json> [threads]".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
