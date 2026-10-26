//! WP73 (`STUDIES/warmup_spend_v1`): one (model, arm, seed) cell.
//!
//! A copy of the WP70 harness (`STUDIES/accel_gp_gap_v1/src/main.rs`). WP73 changes:
//! the arm is one of `src/lib.rs`'s four (`default`, `init25`, `half`,
//! `stablestop`), built by `warmup_spend_v1::arm(name, 1000)`; each chain's
//! transitions are split at its own warmup length (`RunMetadata::discarded`,
//! which `stablestop` may shorten); and each chain records the warmup spend:
//! target evaluations and step per warmup transition, the warmup schedule,
//! work by warmup phase, metric updates and stable-metric checks. The WP70
//! per-retained-transition arrays are reduced to target evaluations, stop,
//! depth and step. WP70 header follows.
//!
//! WP70 (`STUDIES/accel_gp_gap_v1`): one (model, arm, seed) cell.
//!
//! A copy of the WP65 harness (itself the v7 harness plus a dispatch argument).
//! WP70 changes: the arm (`mode`) may be one of the three preregistered research
//! settings (`target095`, `depth12`, `warmup2000`) besides `defaults`; the warmup
//! length and the kernel tuning used for the histograms follow the arm; and each
//! chain additionally records per-retained-transition diagnostics (orbit states,
//! target evaluations, depth, stop reason, acceptance statistic, selected level,
//! maximum absolute energy error) and its warmup-end step and inverse metric.
//! WP65 header follows.
//!
//! A copy of `STUDIES/posteriordb_bench_v7/src/main.rs` (WP56) with one added
//! argument, `dispatch`, which selects the BridgeStan target type:
//!
//! - `replicated`: `ReplicatedStanTarget::load(.., threads)`, exactly what v7
//!   loads. Off Windows this is `Execution::ReplicatedConcurrent` (one model
//!   module per replica, free-replica dispatch).
//! - `direct`: one `StanTarget` shared by every sampler thread. With a
//!   library built without `STAN_THREADS` this is `Execution::DirectSerialised`
//!   (every native call under one module mutex, the Linux analogue of the
//!   Windows owned-worker serialisation); with a `STAN_THREADS=true` library
//!   it is `Execution::DirectConcurrent`.
//!
//! Everything else (sampler construction, starts, timing, recorded fields) is
//! v7's. Changes are listed in `PREREGISTRATION.md`.
//!
//! Usage: `harness <model.so> <data.json> <defaults|dense> <replicated|direct> <seed> <out.json> [threads]`
//!
//! - `defaults` (the decision arm): `owalnuts::sampler::Sampler::new()` with
//!   only the run shape set (1,000 warmup, 1,000 draws, four chains, seed,
//!   threads) and `Limits::new().admit_worst_case()`. The metric, adaptation,
//!   tuning and start rule are whatever `Metric::default()`,
//!   `Adaptation::default()`, `Tuning::default()` and `Init::default()` are at
//!   the commit under test; nothing is overridden. Their `Debug` forms are
//!   written into the cell so that the defaults actually measured are on
//!   record.
//! - `dense` (descriptive, non-decision): the same, plus `Metric::dense()`,
//!   i.e. the adaptive dense metric at whatever dense defaults that commit has.
//!
//! The model is loaded through `owalnuts_bridgestan::ReplicatedStanTarget`
//! (BridgeStan 2.9.0 / Stan 2.39.0, built without `STAN_THREADS`). The starts
//! are drawn here exactly as `Sampler::run_with_init(&target, &Init::default())`
//! would draw them, so that the start rule and its evaluation count can be
//! recorded. The wall is measured around `Sampler::run` (start search
//! excluded); `target_calls_total` includes the start search.
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
use owalnuts::walnutpie::TargetError;
use owalnuts_bridgestan::{ReplicatedStanTarget, StanTarget, default_preload};
use serde_json::json;
use std::{env, error::Error, fs, path::Path, time::Instant};

const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;

/// The two BridgeStan target types this study compares (WP65 addition).
enum Loaded {
    Replicated(ReplicatedStanTarget),
    Direct(StanTarget),
}

impl Loaded {
    fn load(model: &Path, data: &str, threads: usize, dispatch: &str) -> Result<Self, Box<dyn Error>> {
        match dispatch {
            "replicated" => Ok(Self::Replicated(ReplicatedStanTarget::load(
                model,
                &default_preload(),
                Some(data),
                1,
                threads,
            )?)),
            "direct" => Ok(Self::Direct(StanTarget::load(model, &default_preload(), Some(data), 1)?)),
            other => Err(format!("unknown dispatch {other:?} (expected replicated or direct)").into()),
        }
    }
    fn calls(&self) -> usize {
        match self {
            Self::Replicated(t) => t.calls(),
            Self::Direct(t) => t.calls(),
        }
    }
    fn recoverable_failures(&self) -> usize {
        match self {
            Self::Replicated(t) => t.recoverable_failures(),
            Self::Direct(t) => t.recoverable_failures(),
        }
    }
    fn info(&self) -> &str {
        match self {
            Self::Replicated(t) => t.info(),
            Self::Direct(t) => t.info(),
        }
    }
    fn threading(&self) -> String {
        match self {
            Self::Replicated(t) => format!("{:?}", t.threading()),
            Self::Direct(t) => format!("{:?}", t.threading()),
        }
    }
    fn compiled_threading(&self) -> String {
        match self {
            Self::Replicated(t) => format!("{:?}", t.compiled_threading()),
            Self::Direct(t) => format!("{:?}", t.compiled_threading()),
        }
    }
    fn execution(&self) -> String {
        match self {
            Self::Replicated(t) => format!("{:?}", t.execution()),
            Self::Direct(t) => format!("{:?}", t.execution()),
        }
    }
    fn replicas(&self) -> usize {
        match self {
            Self::Replicated(t) => t.effective_replicas(),
            Self::Direct(_) => 1,
        }
    }
    fn requested_replicas(&self) -> usize {
        match self {
            Self::Replicated(t) => t.requested_replicas(),
            Self::Direct(_) => 1,
        }
    }
}

impl Target for Loaded {
    fn dimension(&self) -> usize {
        match self {
            Self::Replicated(t) => t.dimension(),
            Self::Direct(t) => t.dimension(),
        }
    }
    fn log_density_gradient(&self, position: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        match self {
            Self::Replicated(t) => t.log_density_gradient(position, gradient),
            Self::Direct(t) => t.log_density_gradient(position, gradient),
        }
    }
    fn parameter_names(&self) -> Option<Vec<String>> {
        match self {
            Self::Replicated(t) => t.parameter_names(),
            Self::Direct(t) => t.parameter_names(),
        }
    }
}

/// `Cpus_allowed_list` of this process (Linux), to record the lane pinning.
fn cpus_allowed() -> Option<String> {
    fs::read_to_string("/proc/self/status").ok()?.lines().find_map(|l| {
        l.strip_prefix("Cpus_allowed_list:").map(|v| v.trim().to_string())
    })
}

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

/// The sampler for an arm (WP73): the run shape, the admission rule and the
/// arm's tuning, adaptation and warmup length from `warmup_spend_v1::arm`.
/// The `default` arm sets `Tuning::default()` and `Adaptation::default()`
/// explicitly, which is what an unset sampler uses.
fn sampler(arm: &str, seed: u64, threads: usize) -> Result<(Sampler, Tuning, usize), Box<dyn Error>> {
    let selected = warmup_spend_v1::arm(arm, WARMUP)?;
    let sampler = Sampler::new()
        .warmup(selected.warmup)
        .draws(RETAINED)
        .chains(CHAINS)
        .seed(seed)
        .threads(threads)
        .limits(Limits::new().admit_worst_case())
        .tuning(selected.tuning.clone())
        .adaptation(selected.adaptation);
    Ok((sampler, selected.tuning, selected.warmup))
}

/// Starts as `Sampler::run_with_init(target, &Init::default())` draws them.
fn starts(
    target: &Loaded,
    seed: u64,
) -> Result<(Vec<Vec<f64>>, serde_json::Value), Box<dyn Error>> {
    let init = Init::default();
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
        other => Err(format!("Init::default() is {other:?}; this harness draws only Uniform and Candidates starts").into()),
    }
}

fn run(
    model: &Path,
    data: &Path,
    arm: &str,
    dispatch: &str,
    seed: u64,
    out: &Path,
    threads: usize,
) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    let data_json = fs::read_to_string(data)?;
    let target = Loaded::load(model, &data_json, threads, dispatch)?;
    let dimension = target.dimension();
    let (sampler, tuning, warmup) = sampler(arm, seed, threads)?;
    let kernel = tuning.to_kernel()?;
    let max_depth = kernel.max_depth();
    let max_levels = kernel.max_refinement_levels();
    let worst_case = sampler.worst_case_target_evaluations(CHAINS)?;
    let defaults_json = json!({
        "metric_default": format!("{:?}", Metric::default()),
        "metric_used": format!("{:?}", Metric::default()),
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

    let (starts, init_json) = match starts(&target, seed) {
        Ok(s) => s,
        Err(e) => {
            let payload = json!({
                "schema": "warmup-spend-v1-cell", "sampler": format!("owalnuts-{arm}"),
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
                "schema": "warmup-spend-v1-cell", "sampler": format!("owalnuts-{arm}"),
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
            let chain_warmup = chain.metadata().discarded();
            let diags = &all_diags[chain_warmup..];
            let warm = &all_diags[..chain_warmup];
            let mut depth_hist = vec![0usize; max_depth + 1];
            let mut level_hist = vec![0usize; max_levels + 1];
            for d in diags {
                depth_hist[d.depth().min(max_depth)] += 1;
                if let Some(l) = d.selected_refinement_level() {
                    level_hist[l.min(max_levels)] += 1;
                }
            }
            let per_transition = json!({
                "target_evaluations": diags.iter().map(|d| d.target_evaluations()).collect::<Vec<_>>(),
                "depth": diags.iter().map(|d| d.depth()).collect::<Vec<_>>(),
                "stop": diags.iter().map(|d| stop_name(d.stop())).collect::<Vec<_>>(),
                "step_size": diags.iter().map(|d| d.step_size()).collect::<Vec<_>>(),
            });
            let warmup_per_transition = json!({
                "target_evaluations": warm.iter().map(|d| d.target_evaluations()).collect::<Vec<_>>(),
                "step_size": warm.iter().map(|d| d.step_size()).collect::<Vec<_>>(),
                "depth": warm.iter().map(|d| d.depth()).collect::<Vec<_>>(),
                "stop": warm.iter().map(|d| stop_name(d.stop())).collect::<Vec<_>>(),
            });
            let warmup_evaluations: usize = warm.iter().map(|d| d.target_evaluations()).sum();
            let schedule = chain.metadata().warmup_schedule().map(|s| json!({
                "initial_fast_end": s.initial_fast_end(),
                "terminal_fast_start": s.terminal_fast_start(),
                "windows": s.windows().iter().map(|w| [w.start(), w.end()]).collect::<Vec<_>>(),
                "used_short_warmup_fallback": s.used_short_warmup_fallback(),
            }));
            let metric_updates = t.metric_updates().iter().map(|u| json!({
                "window_index": u.window_index(), "transition": u.transition(),
                "sample_count": u.sample_count(), "step_before": u.step_before(),
                "step_after_restart": u.step_after_restart(),
            })).collect::<Vec<_>>();
            let stable_checks = t.stable_metric_checks().iter().map(|c| json!({
                "window_index": c.window_index(), "transition": c.transition(),
                "metric_change": c.metric_change(), "step_change": c.step_change(), "stopped": c.stopped(),
            })).collect::<Vec<_>>();
            json!({
                "retained_per_transition": per_transition,
                "warmup_per_transition": warmup_per_transition,
                "warmup_transitions": chain_warmup,
                "warmup_transition_evaluations": warmup_evaluations,
                "warmup_schedule": schedule,
                "phase_work": {"initial_fast": work_json(t.initial_fast()), "slow": work_json(t.slow()),
                               "terminal_fast": work_json(t.terminal_fast())},
                "metric_updates": metric_updates,
                "stable_metric_checks": stable_checks,
                "adaptation_target_calls": t.adaptation_target_calls(),
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
    let warnings: Vec<String> = posterior
        .chain_warnings()
        .iter()
        .map(|w| w.to_string())
        .collect();
    let payload = json!({
        "schema": "warmup-spend-v1-cell",
        "sampler": format!("owalnuts-{arm}"),
        "status": "ok",
        "seed": seed,
        "model_library": model.display().to_string(),
        "model_info": target.info(),
        "dispatch": dispatch,
        "threading": target.threading(), "replicas": target.replicas(),
        "compiled_threading": target.compiled_threading(),
        "cpus_allowed_list": cpus_allowed(),
        "requested_replicas": target.requested_replicas(),
        "execution": target.execution(),
        "dimension": dimension,
        "chains": CHAINS, "warmup": warmup, "retained": RETAINED, "threads": threads,
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
        "target_calls_total": target.calls(),
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
        [model, data, arm, dispatch, seed, out, rest @ ..] => {
            let threads = rest.first().map_or(Ok(CHAINS), |t| t.parse::<usize>());
            match (seed.parse::<u64>(), threads) {
                (Ok(s), Ok(t)) => run(Path::new(model), Path::new(data), arm, dispatch, s, Path::new(out), t),
                _ => Err("seed and threads must be integers".into()),
            }
        }
        _ => Err("usage: <model.so> <data.json> <default|init25|half|stablestop> <replicated|direct> <seed> <out.json> [threads]".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
