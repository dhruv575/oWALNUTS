#![forbid(unsafe_code)]

//! Paper funnel adaptive-warmup runner (WP7). Reads `protocol.json`, runs one
//! named arm (fixed tuning or JMLR Appendix C paper adaptation), and writes
//! samples, final tuning, per-window adaptation telemetry, and health counters.
//! Usage: `runner --preflight out.json` or `runner --sample ARM out.json`.

use owalnuts::walnutpie::{
    DiagonalMass, KernelTuning, PaperAdaptationConfig, PaperAdaptationOutcome, RunConfig,
    StopReason, Target, TargetError, TargetEvaluationAdmissionLimit, TargetEvaluationBudget,
    WarmupConfig, preflight_chains_with_target_budget, sample_chains_with_target_budget,
};
use serde_json::{Value, json};
use std::{
    env,
    error::Error,
    fs,
    num::NonZeroUsize,
    path::{Path, PathBuf},
    sync::atomic::{AtomicUsize, Ordering},
    time::{Duration, Instant},
};

const DIMENSION: usize = 10;

struct Funnel {
    calls: AtomicUsize,
    deadline: Option<Instant>,
}

impl Target for Funnel {
    fn dimension(&self) -> usize {
        DIMENSION
    }

    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        if self
            .deadline
            .is_some_and(|deadline| Instant::now() >= deadline)
        {
            return Err(TargetError::new("arm wall cap exceeded"));
        }
        let v = q[0];
        let inverse_variance = (-v).exp();
        if !inverse_variance.is_finite() {
            return Err(TargetError::recoverable("non-finite exp(-v)"));
        }
        let sum_squares = q[1..].iter().map(|x| x * x).sum::<f64>();
        gradient[0] =
            -v / 9.0 - 0.5 * (DIMENSION - 1) as f64 + 0.5 * inverse_variance * sum_squares;
        for index in 1..DIMENSION {
            gradient[index] = -inverse_variance * q[index];
        }
        Ok(-v * v / 18.0 - 0.5 * (DIMENSION - 1) as f64 * v - 0.5 * inverse_variance * sum_squares)
    }
}

struct Paper {
    global_energy_bound: f64,
    quantile_probability: f64,
    unrefined_fraction_target: f64,
    adapt_local_error: bool,
    adapt_step_size: bool,
}

struct Arm {
    name: String,
    step_size: f64,
    max_error: f64,
    levels: usize,
    depth: usize,
    min_micro: usize,
    divergence_threshold: f64,
    discarded: usize,
    retained: usize,
    base_seed: u64,
    paper: Option<Paper>,
}

fn load_protocol(dir: &Path) -> Result<Value, Box<dyn Error>> {
    Ok(serde_json::from_slice(&fs::read(dir.join("protocol.json"))?)?)
}

fn arm(protocol: &Value, name: &str) -> Result<Arm, Box<dyn Error>> {
    let a = protocol["arms"]
        .get(name)
        .ok_or_else(|| format!("unknown arm {name}"))?;
    if a["sampler"] != "owalnuts" {
        return Err(format!("arm {name} is not an oWALNUTS arm").into());
    }
    let u = |k: &str| -> Result<usize, Box<dyn Error>> {
        Ok(usize::try_from(a[k].as_u64().ok_or_else(|| format!("{k} missing"))?)?)
    };
    let f = |k: &str| -> Result<f64, Box<dyn Error>> {
        a[k].as_f64().ok_or_else(|| format!("{k} missing").into())
    };
    let paper = match a["mode"].as_str() {
        Some("fixed") => None,
        Some("paper") => {
            let p = &a["paper"];
            let pf = |k: &str| -> Result<f64, Box<dyn Error>> {
                p[k].as_f64().ok_or_else(|| format!("paper.{k} missing").into())
            };
            Some(Paper {
                global_energy_bound: pf("global_energy_bound")?,
                quantile_probability: pf("quantile_probability")?,
                unrefined_fraction_target: pf("unrefined_fraction_target")?,
                // Post-hoc measurement switches; preregistered arms leave both true.
                adapt_local_error: p["adapt_local_error"].as_bool().unwrap_or(true),
                adapt_step_size: p["adapt_step_size"].as_bool().unwrap_or(true),
            })
        }
        _ => return Err(format!("arm {name} mode must be fixed or paper").into()),
    };
    Ok(Arm {
        name: name.to_string(),
        step_size: f("step_size")?,
        max_error: f("max_error")?,
        levels: u("max_refinement_levels")?,
        depth: u("max_depth")?,
        min_micro: u("min_micro_steps")?,
        divergence_threshold: f("divergence_threshold")?,
        discarded: u("discarded")?,
        retained: u("retained")?,
        base_seed: a["base_seed"].as_u64().ok_or("base_seed missing")?,
        paper,
    })
}

fn config(arm: &Arm) -> Result<RunConfig, Box<dyn Error>> {
    let tuning = KernelTuning::new(
        arm.step_size,
        NonZeroUsize::new(arm.depth).ok_or("depth")?,
        NonZeroUsize::new(arm.min_micro).ok_or("min micro")?,
        NonZeroUsize::new(arm.levels).ok_or("levels")?,
        arm.max_error,
    )?
    .with_divergence_threshold(arm.divergence_threshold)?;
    let mut config = RunConfig::new(
        arm.discarded,
        NonZeroUsize::new(arm.retained).ok_or("retained")?,
        arm.base_seed,
    )
    .with_tuning(tuning);
    if let Some(paper) = &arm.paper {
        let adapt_step_size = paper.adapt_step_size;
        let paper = PaperAdaptationConfig::new(
            paper.global_energy_bound,
            paper.quantile_probability,
            paper.unrefined_fraction_target,
        )?
        .with_local_error_adaptation(paper.adapt_local_error);
        config = config.with_warmup(
            WarmupConfig::default()
                .with_mass_adaptation(false)
                .with_step_size_adaptation(adapt_step_size)
                .with_paper_adaptation(paper),
        );
    }
    Ok(config)
}

fn starts(protocol: &Value) -> Result<Vec<Vec<f64>>, Box<dyn Error>> {
    let mut out = Vec::new();
    for row in protocol["starts"].as_array().ok_or("starts")? {
        let q: Vec<f64> = row
            .as_array()
            .ok_or("start row")?
            .iter()
            .map(|v| v.as_f64().ok_or("start value"))
            .collect::<Result<_, _>>()?;
        if q.len() != DIMENSION {
            return Err("start dimension".into());
        }
        out.push(q);
    }
    Ok(out)
}

fn stop_name(stop: StopReason) -> &'static str {
    match stop {
        StopReason::MaximumDepth => "maximum_depth",
        StopReason::OuterUTurn => "outer_uturn",
        StopReason::RecursiveUTurn => "recursive_uturn",
        StopReason::RefinementExhausted => "refinement_exhausted",
        StopReason::ReverseCoarserAccepted => "reverse_coarser_accepted",
        StopReason::InvalidEvaluation => "invalid_evaluation",
        _ => "other",
    }
}

fn outcome_name(outcome: PaperAdaptationOutcome) -> &'static str {
    match outcome {
        PaperAdaptationOutcome::Installed => "installed",
        PaperAdaptationOutcome::InsufficientOrbits => "insufficient_orbits",
        PaperAdaptationOutcome::NonFinite => "non_finite",
        PaperAdaptationOutcome::Disabled => "disabled",
        _ => "other",
    }
}

fn quantile(sorted: &[f64], p: f64) -> f64 {
    if sorted.is_empty() {
        return f64::NAN;
    }
    let position = p * (sorted.len() - 1) as f64;
    let lower = position.floor() as usize;
    let upper = position.ceil() as usize;
    let fraction = position - lower as f64;
    sorted[lower] + fraction * (sorted[upper] - sorted[lower])
}

fn range_quantiles(mut ranges: Vec<f64>) -> Value {
    ranges.retain(|r| r.is_finite());
    ranges.sort_by(f64::total_cmp);
    json!({
        "count": ranges.len(),
        "q50": quantile(&ranges, 0.5),
        "q80": quantile(&ranges, 0.8),
        "q90": quantile(&ranges, 0.9),
        "q95": quantile(&ranges, 0.95),
        "q99": quantile(&ranges, 0.99),
        "max": ranges.last().copied().unwrap_or(f64::NAN)
    })
}

fn main() -> Result<(), Box<dyn Error>> {
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let mut arguments = env::args().skip(1);
    let mode = arguments.next().ok_or("mode required")?;
    let protocol = load_protocol(&dir)?;
    let arm_names: Vec<String> = protocol["arms"]
        .as_object()
        .ok_or("arms")?
        .keys()
        .cloned()
        .collect();
    let starts = starts(&protocol)?;
    let mass = DiagonalMass::identity(NonZeroUsize::new(DIMENSION).unwrap());
    let cap = usize::try_from(protocol["runtime_callback_cap"].as_u64().ok_or("cap")?)?;
    let wall_cap = protocol["wall_cap_seconds_per_arm"].as_u64().ok_or("wall cap")?;
    let threads =
        NonZeroUsize::new(usize::try_from(protocol["threads"].as_u64().unwrap_or(1))?).unwrap();

    if mode == "--preflight" {
        let output = PathBuf::from(arguments.next().ok_or("output path required")?);
        if output.exists() {
            return Err("refusing to overwrite preflight output".into());
        }
        let target = Funnel {
            calls: AtomicUsize::new(0),
            deadline: None,
        };
        let mut cells = Vec::new();
        for name in &arm_names {
            let arm = arm(&protocol, name)?;
            let config = config(&arm)?;
            let exact =
                config.worst_case_target_evaluations(NonZeroUsize::new(starts.len()).unwrap())?;
            let budget = TargetEvaluationBudget::new(NonZeroUsize::new(cap.min(exact)).unwrap());
            let report = preflight_chains_with_target_budget(
                &target,
                &starts,
                &mass,
                &config,
                TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap()),
                &budget,
            )?;
            if budget.started() != 0 || target.calls.load(Ordering::Relaxed) != 0 {
                return Err("preflight invoked the target".into());
            }
            cells.push(json!({
                "arm": name,
                "mode": if arm.paper.is_some() { "paper" } else { "fixed" },
                "worst_case_target_evaluations": report.worst_case_target_evaluations(),
                "admission_ceiling": report.admission_ceiling(),
                "runtime_callback_cap": budget.maximum(),
                "total_transitions": report.total_transitions(),
            }));
        }
        let result = json!({
            "schema": "owalnuts-paper-funnel-adaptive-preflight/v1",
            "target_callbacks_started": target.calls.load(Ordering::Relaxed),
            "cells": cells
        });
        fs::create_dir_all(output.parent().ok_or("output parent")?)?;
        fs::write(output, serde_json::to_vec_pretty(&result)?)?;
        return Ok(());
    }
    if mode != "--sample" {
        return Err("mode must be --preflight or --sample".into());
    }
    let name = arguments.next().ok_or("arm name required")?;
    let output = PathBuf::from(arguments.next().ok_or("output path required")?);
    if output.exists() {
        return Err("refusing to overwrite an arm artifact".into());
    }
    let arm = arm(&protocol, &name)?;
    let config = config(&arm)?;
    let exact = config.worst_case_target_evaluations(NonZeroUsize::new(starts.len()).unwrap())?;
    let budget = TargetEvaluationBudget::new(NonZeroUsize::new(cap.min(exact)).unwrap());
    let target = Funnel {
        calls: AtomicUsize::new(0),
        deadline: Some(
            Instant::now()
                .checked_add(Duration::from_secs(wall_cap))
                .ok_or("deadline overflow")?,
        ),
    };
    let started = Instant::now();
    let chains = sample_chains_with_target_budget(
        &target,
        &starts,
        &mass,
        &config,
        threads,
        TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap()),
        &budget,
    )
    .map_err(|e| format!("arm {} failed closed ({:?}): {e}", arm.name, e.kind()))?;
    let wall = started.elapsed().as_secs_f64();

    let mut samples = Vec::new();
    let mut chain_reports = Vec::new();
    let mut pooled_ranges = Vec::new();
    for chain in chains.chains() {
        samples.push(
            (0..chain.retained())
                .map(|draw| chain.sample(draw).unwrap().to_vec())
                .collect::<Vec<_>>(),
        );
        let retained = chain.telemetry().retained();
        let discarded = chain.telemetry().discarded();
        let split = chain.metadata().discarded();
        let diagnostics = &chain.diagnostics()[split..];
        let mut depth_hist = vec![0usize; arm.depth + 1];
        let mut level_hist = vec![0usize; arm.levels + 1];
        let mut stops = std::collections::BTreeMap::<&str, usize>::new();
        let mut max_energy_error = 0.0f64;
        let mut divergent = 0usize;
        let mut calls_per_transition = Vec::with_capacity(diagnostics.len());
        let mut ranges = Vec::with_capacity(diagnostics.len());
        for d in diagnostics {
            depth_hist[d.depth().min(arm.depth)] += 1;
            if let Some(level) = d.selected_refinement_level() {
                level_hist[level.min(arm.levels)] += 1;
            }
            *stops.entry(stop_name(d.stop())).or_default() += 1;
            let err = d.maximum_absolute_energy_error();
            if err.is_finite() {
                max_energy_error = max_energy_error.max(err);
            }
            divergent += usize::from(d.divergent());
            calls_per_transition.push(d.target_evaluations());
            let range = d.maximum_hamiltonian() - d.minimum_hamiltonian();
            ranges.push(range);
            pooled_ranges.push(range);
        }
        let updates: Vec<Value> = chain
            .telemetry()
            .paper_adaptation_updates()
            .iter()
            .map(|u| {
                json!({
                    "transition": u.transition(),
                    "window_index": u.window_index(),
                    "orbits": u.orbits(),
                    "inflation_quantile": u.inflation_quantile(),
                    "energy_range_quantile": u.energy_range_quantile(),
                    "max_error_before": u.max_error_before(),
                    "max_error_after": u.max_error_after(),
                    "unrefined_fraction_mean": u.unrefined_fraction_mean(),
                    "step_before": u.step_before(),
                    "step_after": u.step_after(),
                    "outcome": outcome_name(u.outcome())
                })
            })
            .collect();
        let tuning = chain.metadata().tuning();
        chain_reports.push(json!({
            "final_tuning": {
                "step_size": tuning.step_size(),
                "max_error": tuning.max_error(),
                "max_refinement_levels": tuning.max_refinement_levels(),
                "max_depth": tuning.max_depth()
            },
            "qualified_step_size": chain.metadata().qualified_step_size(),
            "paper_adaptation_updates": updates,
            "retained_orbit_energy_range_quantiles": range_quantiles(ranges),
            "retained": {
                "target_calls": retained.target_calls_total(),
                "divergences": retained.divergences(),
                "divergent_transitions_from_diagnostics": divergent,
                "invalid_evaluation_stops": retained.invalid_evaluation_stops(),
                "refinement_exhaustion_stops": retained.refinement_exhaustion_stops(),
                "reverse_coarser_stops": retained.reverse_coarser_stops(),
                "reverse_coarser_rejections": retained.reverse_coarser_rejections(),
                "maximum_depth_stops": retained.maximum_depth_stops(),
                "recoverable_target_failures": retained.recoverable_target_failures(),
                "forward_refinement_attempts": retained.forward_refinement_attempts(),
                "forward_micro_steps": retained.forward_micro_steps_executed(),
                "reverse_coarsening_attempts": retained.reverse_coarsening_attempts(),
                "reverse_micro_steps": retained.reverse_micro_steps_executed(),
                "leaves_attempted": retained.leaves_attempted(),
                "leaves_built": retained.leaves_built(),
                "depth_histogram": depth_hist,
                "selected_refinement_level_histogram": level_hist,
                "stop_reasons": stops,
                "max_absolute_energy_error": max_energy_error,
                "mean_target_calls_per_transition": calls_per_transition.iter().sum::<usize>() as f64 / calls_per_transition.len().max(1) as f64
            },
            "discarded": {
                "target_calls": discarded.target_calls_total(),
                "divergences": discarded.divergences(),
                "invalid_evaluation_stops": discarded.invalid_evaluation_stops(),
                "refinement_exhaustion_stops": discarded.refinement_exhaustion_stops(),
                "maximum_depth_stops": discarded.maximum_depth_stops()
            }
        }));
    }
    let report = json!({
        "schema": "owalnuts-paper-funnel-adaptive-arm/v1",
        "arm": arm.name,
        "algorithm_revision": chains.algorithm_revision(),
        "paper_adaptation_revision": owalnuts::walnutpie::PAPER_ADAPTATION_REVISION,
        "base_seed": chains.base_seed(),
        "settings": {
            "mode": if arm.paper.is_some() { "paper" } else { "fixed" },
            "initial_step_size": arm.step_size, "initial_max_error": arm.max_error,
            "max_refinement_levels": arm.levels, "max_depth": arm.depth, "min_micro_steps": arm.min_micro,
            "divergence_threshold": arm.divergence_threshold,
            "discarded": arm.discarded, "retained": arm.retained,
            "paper": arm.paper.as_ref().map(|p| json!({
                "global_energy_bound": p.global_energy_bound,
                "quantile_probability": p.quantile_probability,
                "unrefined_fraction_target": p.unrefined_fraction_target,
                "adapt_local_error": p.adapt_local_error,
                "adapt_step_size": p.adapt_step_size
            }))
        },
        "wall_seconds_including_discarded": wall,
        "wall_cap_seconds": wall_cap,
        "runtime_callback_cap": cap,
        "target_callbacks_started": budget.started(),
        "target_calls_observed": target.calls.load(Ordering::Relaxed),
        "admission_ceiling": exact,
        "pooled_retained_orbit_energy_range_quantiles": range_quantiles(pooled_ranges),
        "chains": chain_reports,
        "samples": samples
    });
    fs::create_dir_all(output.parent().ok_or("output parent")?)?;
    fs::write(output, serde_json::to_vec(&report)?)?;
    eprintln!(
        "arm {} done in {:.1}s, {} callbacks",
        arm.name,
        wall,
        budget.started()
    );
    Ok(())
}
