//! WP85 `metric_autoselect_confirmation_v1`, posteriordb arm: one (model, arm, seed) cell.
//!
//! Usage: `pdb <model.so> <data.json> <diag|dense|auto> <seed> <out.json> [threads]`
//!
//! Copied from `STUDIES/metric_autoselect_v1/src/bin/pdb.rs` (WP75, itself
//! the WP71 / WP68 / v7 / WP62 oWALNUTS cell). The sampler is `Sampler::new()`
//! with only the run shape (1,000 / 1,000, four chains, seed, threads) and
//! `Limits::new().admit_worst_case()`, plus per arm:
//! `diag` = nothing else (the default diagonal metric);
//! `dense` = `.metric(Metric::dense())` (dense defaults since WP51);
//! `auto` = the default (diagonal) metric and `Adaptation::Custom` with the
//! sampler's own warmup defaults (`WarmupConfig::new(0.8)`,
//! `DEFAULT_WARMUP_EXHAUSTION`, `DEFAULT_METRIC_REGULARIZATION`) plus the
//! research flag `with_dense_auto_select(DenseAutoSelectConfig::hessian_fit(2, 5.0, 0.5))`
//! (WP85's Hessian-fit rule). Changes from WP75: the `auto` arm and the
//! recorded decision fields. One build (`owalnuts/research`) serves every
//! arm. Each chain records its metric updates (family of the installed
//! metric, step) and the run-level auto-selection decision.
#![forbid(unsafe_code)]

use owalnuts::sampler::{
    Adaptation, DEFAULT_CHAIN_RESCUE, DEFAULT_MAX_REFINEMENT_LEVELS, DEFAULT_METRIC_REGULARIZATION,
    DEFAULT_U_TURN_RULE, DEFAULT_WARMUP_EXHAUSTION, Init, Limits, Metric, Sampler, Target, Tuning,
    WarmupConfig, candidate_starts, uniform_starts,
};
use owalnuts::walnutpie::{
    ALGORITHM_REVISION, ChainRescueOutcome, DenseAutoSelectConfig, PAPER_ADAPTATION_REVISION,
    RunTelemetry, StopReason, TransitionDiagnostics, WorkTotals,
};
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::json;
use std::{env, error::Error, fs, path::Path, time::Instant};

const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;
/// WP85's frozen Hessian-fit rule (protocol.json `selection`).
const SELECT_WINDOW: usize = 2;
const THRESHOLD: f64 = 5.0;
const MIN_LINEARITY: f64 = 0.5;

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

/// The metric and adaptation of an arm.
fn arm_setup(arm: &str) -> Result<(Metric, Adaptation), Box<dyn Error>> {
    if DEFAULT_CHAIN_RESCUE.is_some() {
        return Err("DEFAULT_CHAIN_RESCUE is set; the arms assume none".into());
    }
    Ok(match arm {
        "diag" => (Metric::default(), Adaptation::default()),
        "dense" => (Metric::dense(), Adaptation::default()),
        "auto" => (
            Metric::default(),
            Adaptation::Custom(
                WarmupConfig::new(0.8)?
                    .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                    .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
                    .with_dense_auto_select(DenseAutoSelectConfig::hessian_fit(
                        SELECT_WINDOW,
                        THRESHOLD,
                        MIN_LINEARITY,
                    )?),
            ),
        ),
        other => {
            return Err(format!("unknown arm {other:?} (expected diag, dense or auto)").into());
        }
    })
}

/// The sampler for an arm; only the run shape, the admission rule and the
/// arm's metric / adaptation are set (`diag` sets neither, `auto` only the
/// adaptation).
fn sampler(arm: &str, seed: u64, threads: usize) -> Result<Sampler, Box<dyn Error>> {
    let base = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .seed(seed)
        .threads(threads)
        .limits(Limits::new().admit_worst_case());
    let (metric, adaptation) = arm_setup(arm)?;
    Ok(match arm {
        "diag" => base,
        "dense" => base.metric(metric),
        _ => base.adaptation(adaptation),
    })
}

fn geomean(xs: &[f64]) -> f64 {
    (xs.iter().map(|x| x.ln()).sum::<f64>() / xs.len() as f64).exp()
}

fn metric_updates_json(telemetry: &RunTelemetry) -> Vec<serde_json::Value> {
    telemetry
        .metric_updates()
        .iter()
        .map(|u| {
            let mass = u.mass_diagonal();
            // Largest |M_ij| / sqrt(M_ii M_jj) of an installed dense precision
            // (0 for a diagonal one); None for a diagonal-driver update.
            let dense_offdiag = u.mass_dense().map(|m| {
                let d = (m.len() as f64).sqrt().round() as usize;
                (0..d * d)
                    .filter(|k| k / d != k % d)
                    .map(|k| {
                        (m[k] / (m[(k / d) * d + k / d] * m[(k % d) * d + k % d]).sqrt()).abs()
                    })
                    .fold(0.0, f64::max)
            });
            json!({
                "dense_offdiag_max": dense_offdiag,
                "window_index": u.window_index(),
                "transition": u.transition(),
                "sample_count": u.sample_count(),
                "outcome": format!("{:?}", u.outcome()),
                "step_before": u.step_before(),
                "step_after_restart": u.step_after_restart(),
                "mass_min": mass.map(|m| m.iter().copied().fold(f64::INFINITY, f64::min)),
                "mass_max": mass.map(|m| m.iter().copied().fold(f64::NEG_INFINITY, f64::max)),
                "mass_geomean": mass.map(geomean),
            })
        })
        .collect()
}

fn fnv(hash: &mut u64, values: &[f64]) {
    for v in values {
        for b in v.to_bits().to_le_bytes() {
            *hash ^= u64::from(b);
            *hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
        }
    }
}

/// Starts as `Sampler::run_with_init(target, &Init::default())` draws them.
fn starts(
    target: &ReplicatedStanTarget,
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
        other => Err(format!(
            "Init::default() is {other:?}; this harness draws only Uniform and Candidates starts"
        )
        .into()),
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
    let sampler = sampler(arm, seed, threads)?;
    let worst_case = sampler.worst_case_target_evaluations(CHAINS)?;
    let defaults_json = json!({
        "metric_default": format!("{:?}", Metric::default()),
        "metric_used": format!("{:?}", arm_setup(arm)?.0),
        "arm_adaptation": format!("{:?}", arm_setup(arm)?.1),
        "default_max_refinement_levels": DEFAULT_MAX_REFINEMENT_LEVELS,
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
                "schema": "posteriordb-bench-v7-cell", "sampler": format!("owalnuts-{arm}"),
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
                "schema": "posteriordb-bench-v7-cell", "sampler": format!("owalnuts-{arm}"),
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
            let mut hash: u64 = 0xcbf2_9ce4_8422_2325;
            fnv(&mut hash, chain.samples());
            let level7 = all_diags.iter().filter(|d| d.selected_refinement_level() == Some(7)).count();
            let level8_plus = all_diags.iter().filter(|d| d.selected_refinement_level().is_some_and(|l| l >= 8)).count();
            let exhausted = all_diags.iter().filter(|d| d.stop() == StopReason::RefinementExhausted).count();
            json!({
                "draws_fnv": format!("{hash:016x}"),
                "all_transitions_level7_selected": level7,
                "all_transitions_level8_plus_selected": level8_plus,
                "all_transitions_exhaustion_stops": exhausted,
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
                "metric_updates": metric_updates_json(t),
                "dense_auto_select": t.dense_auto_select().map(|d| json!({
                    "window_index": d.window_index(), "transition": d.transition(),
                    "previous_count": d.previous_count(), "current_count": d.current_count(),
                    "kappa_diagonal": d.kappa_diagonal(), "kappa_dense": d.kappa_dense(),
                    "statistic": d.statistic(), "threshold": d.threshold(),
                    "chose_dense": d.chose_dense(), "max_abs_correlation": d.max_abs_correlation(),
                    "min_linearity": d.min_linearity(), "linearity": d.linearity(),
                    "hessian_gain": d.hessian_gain(), "hessian_kappa_diagonal": d.hessian_kappa_diagonal(),
                    "hessian_kappa_dense": d.hessian_kappa_dense(), "fit_count": d.fit_count(),
                })),
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
        "schema": "metric-autoselect-v2-pdb-cell",
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
        [model, data, arm, seed, out, rest @ ..] => {
            let threads = rest.first().map_or(Ok(CHAINS), |t| t.parse::<usize>());
            match (seed.parse::<u64>(), threads) {
                (Ok(s), Ok(t)) => run(Path::new(model), Path::new(data), arm, s, Path::new(out), t),
                _ => Err("seed and threads must be integers".into()),
            }
        }
        _ => Err(
            "usage: pdb <model.so> <data.json> <diag|dense|auto> <seed> <out.json> [threads]"
                .into(),
        ),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
