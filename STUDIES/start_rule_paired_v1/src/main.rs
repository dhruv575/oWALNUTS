//! WP60 (start_rule_paired_v1): one (model, arm, seed) cell of the paired
//! start-rule study at `f097391c`.
//!
//! Usage: `start-rule-paired-v1 <model.so> <data.json> <uniform|best_of_16> <seed> <out.json> [threads]`
//!
//! Both arms are `Sampler::new()` with only the run shape (1,000 warmup,
//! 1,000 draws, four chains, seed, threads) and `Limits::admit_worst_case()`
//! set; metric, adaptation and tuning are the commit's defaults. The arms
//! differ only in the start rule: `uniform` = `Init::uniform()`,
//! `best_of_16` = `Init::best_of(16)` (= `Init::default()` at `f097391c`).
//! The starts are drawn here exactly as `Sampler::run_with_init` draws them.
//! After the run (and after `target_calls_total` is read) each chain's start
//! is re-evaluated once to record its log density.
#![forbid(unsafe_code)]

use owalnuts::sampler::{
    Adaptation, DEFAULT_CHAIN_RESCUE, DEFAULT_METRIC_REGULARIZATION, DEFAULT_U_TURN_RULE,
    DEFAULT_WARMUP_EXHAUSTION, Init, Limits, Metric, Sampler, Target, Tuning, candidate_starts,
    uniform_starts,
};
use owalnuts::walnutpie::{
    ALGORITHM_REVISION, ChainRescueOutcome, PAPER_ADAPTATION_REVISION, RunTelemetry, StopReason,
    TransitionDiagnostics, WorkTotals,
};
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::json;
use std::{env, error::Error, fs, path::Path, time::Instant};

const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;

fn work_json(w: &WorkTotals) -> serde_json::Value {
    json!({
        "transitions": w.transitions(),
        "target_calls_total": w.target_calls_total(),
        "leaves_attempted": w.leaves_attempted(),
        "leaves_built": w.leaves_built(),
        "refinement_level_built": w.refinement_level_built(),
        "maximum_depth_stops": w.maximum_depth_stops(),
        "recoverable_target_failures": w.recoverable_target_failures(),
        "nonfinite_position_rejections": w.nonfinite_position_rejections(),
        "zero_density_evaluations": w.zero_density_evaluations(),
        "divergences": w.divergences(),
        "invalid_evaluation_stops": w.invalid_evaluation_stops(),
        "refinement_exhaustion_stops": w.refinement_exhaustion_stops(),
        "reverse_coarser_stops": w.reverse_coarser_stops(),
        "reverse_coarser_rejections": w.reverse_coarser_rejections(),
    })
}

fn stop_name(s: StopReason) -> String {
    match s {
        StopReason::MaximumDepth => "maximum_depth".into(),
        StopReason::OuterUTurn => "outer_u_turn".into(),
        StopReason::RecursiveUTurn => "recursive_u_turn".into(),
        StopReason::RefinementExhausted => "refinement_exhausted".into(),
        StopReason::ReverseCoarserAccepted => "reverse_coarser_accepted".into(),
        StopReason::InvalidEvaluation => "invalid_evaluation".into(),
        #[allow(unreachable_patterns)]
        other => format!("{other:?}"),
    }
}

fn stop_histogram(diags: &[TransitionDiagnostics]) -> serde_json::Value {
    let mut map = serde_json::Map::new();
    for d in diags {
        let entry = map.entry(stop_name(d.stop())).or_insert(json!(0));
        *entry = json!(entry.as_u64().unwrap_or(0) + 1);
    }
    serde_json::Value::Object(map)
}

fn quantiles(mut xs: Vec<f64>) -> serde_json::Value {
    xs.retain(|x| x.is_finite());
    if xs.is_empty() {
        return json!(null);
    }
    xs.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let q = |p: f64| xs[((xs.len() - 1) as f64 * p).round() as usize];
    json!({"q05": q(0.05), "q25": q(0.25), "q50": q(0.5), "q75": q(0.75), "q95": q(0.95)})
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
                other => json!({"kind": format!("{other:?}")}),
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

/// The sampler; only the run shape and the admission rule are set (both arms).
fn sampler(seed: u64, threads: usize) -> Result<Sampler, Box<dyn Error>> {
    Ok(Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .seed(seed)
        .threads(threads)
        .limits(Limits::new().admit_worst_case()))
}

fn init_for(arm: &str) -> Result<Init, Box<dyn Error>> {
    match arm {
        "uniform" => Ok(Init::uniform()),
        "best_of_16" => Ok(Init::best_of(16)),
        other => Err(format!("unknown arm {other:?} (expected uniform or best_of_16)").into()),
    }
}

/// Starts as `Sampler::run_with_init(target, &init)` draws them.
fn starts(
    target: &ReplicatedStanTarget,
    seed: u64,
    init: Init,
) -> Result<(Vec<Vec<f64>>, serde_json::Value), Box<dyn Error>> {
    match &init {
        Init::Uniform {
            radius,
            max_attempts,
        } => {
            let s = uniform_starts(target, CHAINS, seed, *radius, *max_attempts)?;
            Ok((s, json!({"rule": format!("{init:?}")})))
        }
        Init::Candidates {
            radius,
            candidates,
            max_attempts,
            selection,
        } => {
            let c = candidate_starts(
                target,
                CHAINS,
                seed,
                *radius,
                *candidates,
                *max_attempts,
                *selection,
            )?;
            Ok((
                c.starts.clone(),
                json!({"rule": format!("{init:?}"),
                       "start_log_densities": c.start_log_densities,
                       "chosen": c.chosen, "evaluations": c.evaluations}),
            ))
        }
        other => Err(format!("{other:?}: this harness draws only Uniform and Candidates starts").into()),
    }
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
    let target =
        ReplicatedStanTarget::load(model, &default_preload(), Some(&data_json), 1, threads)?;
    let dimension = target.dimension();
    let tuning = Tuning::default();
    let kernel = tuning.to_kernel()?;
    let max_depth = kernel.max_depth();
    let max_levels = kernel.max_refinement_levels();
    let sampler = sampler(seed, threads)?;
    let init = init_for(arm)?;
    let worst_case = sampler.worst_case_target_evaluations(CHAINS)?;
    let defaults_json = json!({
        "metric_default": format!("{:?}", Metric::default()),
        "init_used": format!("{init:?}"),
        "init_used_equals_default": init == Init::default(),
        "adaptation_default": format!("{:?}", Adaptation::default()),
        "init_default": format!("{:?}", Init::default()),
        "tuning_default": format!("{tuning:?}"),
        "kernel_options": format!("{:?}", kernel.options()),
        "default_u_turn_rule": format!("{DEFAULT_U_TURN_RULE:?}"),
        "default_metric_regularization": format!("{DEFAULT_METRIC_REGULARIZATION:?}"),
        "default_warmup_exhaustion": format!("{DEFAULT_WARMUP_EXHAUSTION:?}"),
        "default_chain_rescue": format!("{DEFAULT_CHAIN_RESCUE:?}"),
        "sampler_debug": format!("{sampler:?}"),
    });

    let (starts, init_json) = match starts(&target, seed, init.clone()) {
        Ok(s) => s,
        Err(e) => {
            let payload = json!({
                "schema": "start-rule-paired-v1-cell", "sampler": format!("owalnuts-{arm}"),
                "seed": seed, "status": "error", "stage": "init", "error": e.to_string(),
                "wall_seconds": 0.0, "target_calls": target.calls(),
                "defaults": defaults_json, "algorithm_revision": ALGORITHM_REVISION,
            });
            fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
            return Err(e);
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
                "schema": "start-rule-paired-v1-cell", "sampler": format!("owalnuts-{arm}"),
                "seed": seed, "status": "error", "stage": "sample", "error": e.to_string(),
                "wall_seconds": wall, "target_calls": target.calls(),
                "start_search_calls": start_search_calls,
                "defaults": defaults_json, "algorithm_revision": ALGORITHM_REVISION,
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
            let all_diags = chain.diagnostics();
            let diags = &all_diags[WARMUP..];
            let warm = &all_diags[..WARMUP];
            let mut depth_hist = vec![0usize; max_depth + 1];
            let mut level_hist = vec![0usize; max_levels + 1];
            for d in diags {
                depth_hist[d.depth().min(max_depth)] += 1;
                if let Some(l) = d.selected_refinement_level() {
                    level_hist[l.min(max_levels)] += 1;
                }
            }
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
                "chain_rescues": rescues_json(t),
                "retained_work": work_json(retained),
                "warmup_work": work_json(discarded),
                "retained_stop_histogram": stop_histogram(diags),
                "warmup_step_trace_every_50": warm.iter().step_by(50).map(|d| d.step_size()).collect::<Vec<_>>(),
                "retained_step_quantiles": quantiles(diags.iter().map(|d| d.step_size()).collect()),
                "retained_initial_hamiltonian_quantiles": quantiles(diags.iter().map(|d| d.initial_hamiltonian()).collect()),
            })
        })
        .collect::<Vec<_>>();
    let target_calls_total = target.calls();
    // Re-evaluate each start once, after the call count above was read.
    let start_log_densities: Vec<Option<f64>> = starts
        .iter()
        .map(|q| {
            let mut g = vec![0.0; dimension];
            target.log_density_gradient(q, &mut g).ok()
        })
        .collect();
    let warnings: Vec<String> = posterior
        .chain_warnings()
        .iter()
        .map(|w| w.to_string())
        .collect();
    let payload = json!({
        "schema": "start-rule-paired-v1-cell",
        "sampler": format!("owalnuts-{arm}"),
        "status": "ok",
        "seed": seed,
        "model_library": model.display().to_string(),
        "model_info": target.info(),
        "threading": format!("{:?}", target.threading()), "replicas": target.replicas(),
        "requested_replicas": target.requested_replicas(),
        "execution": format!("{:?}", target.execution()),
        "dimension": dimension,
        "chains": CHAINS, "warmup": WARMUP, "retained": RETAINED, "threads": threads,
        "init": {"start_search_calls": start_search_calls, "detail": init_json},
        "starts": starts,
        "tuning": {"step_size": kernel.step_size(), "max_depth": max_depth,
                   "min_micro_steps": kernel.min_micro_steps(),
                   "max_refinement_levels": max_levels, "max_error": kernel.max_error(),
                   "divergence_threshold": kernel.divergence_threshold(),
                   "u_turn": format!("{:?}", kernel.options().u_turn),
                   "exhaustion": format!("{:?}", kernel.options().exhaustion)},
        "defaults": defaults_json,
        "warmup_config_used": posterior.chains().first().map(|c| format!("{:?}", c.metadata().warmup())),
        "constructor_admission_bound": worst_case,
        "timing_estimand": "wall around sampler::Sampler::run (warmup + retained, four parallel chains; start search excluded)",
        "wall_seconds": wall,
        "target_calls_total": target_calls_total,
        "start_log_densities": start_log_densities,
        "recoverable_failures_total": target.recoverable_failures(),
        "chain_warnings": warnings,
        "chains_data": chains,
        "algorithm_revision": posterior.algorithm_revision(),
        "paper_adaptation_revision": PAPER_ADAPTATION_REVISION,
    });
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    eprintln!(
        "{arm} seed {seed}: wall {wall:.3}s, calls {}, div {}, warnings {}",
        target.calls(),
        posterior
            .chains()
            .iter()
            .map(|c| c.telemetry().retained().divergences())
            .sum::<usize>(),
        warnings.len()
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
        _ => Err("usage: <model.so> <data.json> <uniform|best_of_16> <seed> <out.json> [threads]".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
