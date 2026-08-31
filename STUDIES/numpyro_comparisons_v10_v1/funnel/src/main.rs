//! WP14 part 3: oWALNUTS funnel cells (fixed paper tuning and Appendix C
//! paper adaptation, v3 defaults) on kernel v10, one run per evidence seed.
//! Derived from `STUDIES/funnel_bias_fix_v1` and `STUDIES/paper_funnel_adaptive_v2`.
//! Usage: `runner --preflight out.json` or `runner --sample ARM SEED out.json`.
//! Only `omega` and `x_1` draws are written (binary f64, chain-major).

use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DiagonalMass, KernelTuning, PaperAdaptationConfig, PaperAdaptationOutcome,
    PaperRestartPolicy, PaperStepStatistic, RunConfig, StopReason, Target, TargetError,
    TargetEvaluationAdmissionLimit, TargetEvaluationBudget, WarmupConfig,
    preflight_chains_with_target_budget, sample_chains_with_target_budget,
};
use serde_json::{Value, json};
use std::{
    env,
    error::Error,
    fs,
    io::Write,
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
        if self.deadline.is_some_and(|deadline| Instant::now() >= deadline) {
            return Err(TargetError::new("arm wall cap exceeded"));
        }
        let v = q[0];
        let inverse_variance = (-v).exp();
        if !inverse_variance.is_finite() {
            return Err(TargetError::recoverable("non-finite exp(-v)"));
        }
        let sum_squares = q[1..].iter().map(|x| x * x).sum::<f64>();
        gradient[0] = -v / 9.0 - 0.5 * (DIMENSION - 1) as f64 + 0.5 * inverse_variance * sum_squares;
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
    step_statistic: String,
    restart_policy: String,
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
    paper: Option<Paper>,
}

fn load_protocol(dir: &Path) -> Result<Value, Box<dyn Error>> {
    Ok(serde_json::from_slice(&fs::read(dir.join("protocol.json"))?)?)
}

fn arm(part: &Value, name: &str) -> Result<Arm, Box<dyn Error>> {
    let a = part["arms"].get(name).ok_or_else(|| format!("unknown arm {name}"))?;
    if a["backend"] != "owalnuts" {
        return Err(format!("arm {name} is not an oWALNUTS arm").into());
    }
    let u = |k: &str| -> Result<usize, Box<dyn Error>> {
        Ok(usize::try_from(a[k].as_u64().ok_or_else(|| format!("{k} missing"))?)?)
    };
    let f = |k: &str| -> Result<f64, Box<dyn Error>> { a[k].as_f64().ok_or_else(|| format!("{k} missing").into()) };
    let paper = match a["mode"].as_str() {
        Some("fixed") => None,
        Some("paper") => {
            let p = &a["paper"];
            let pf = |k: &str| -> Result<f64, Box<dyn Error>> { p[k].as_f64().ok_or_else(|| format!("paper.{k} missing").into()) };
            Some(Paper {
                global_energy_bound: pf("global_energy_bound")?,
                quantile_probability: pf("quantile_probability")?,
                unrefined_fraction_target: pf("unrefined_fraction_target")?,
                step_statistic: p["step_statistic"].as_str().ok_or("paper.step_statistic")?.to_string(),
                restart_policy: p["restart_policy"].as_str().ok_or("paper.restart_policy")?.to_string(),
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
        paper,
    })
}

fn config(arm: &Arm, seed: u64) -> Result<RunConfig, Box<dyn Error>> {
    let tuning = KernelTuning::new(
        arm.step_size,
        NonZeroUsize::new(arm.depth).ok_or("depth")?,
        NonZeroUsize::new(arm.min_micro).ok_or("min micro")?,
        NonZeroUsize::new(arm.levels).ok_or("levels")?,
        arm.max_error,
    )?
    .with_divergence_threshold(arm.divergence_threshold)?;
    let mut config = RunConfig::new(arm.discarded, NonZeroUsize::new(arm.retained).ok_or("retained")?, seed)
        .with_tuning(tuning);
    if let Some(paper) = &arm.paper {
        let paper = PaperAdaptationConfig::new(
            paper.global_energy_bound,
            paper.quantile_probability,
            paper.unrefined_fraction_target,
        )?
        .with_step_statistic(match paper.step_statistic.as_str() {
            "per_transition" => PaperStepStatistic::PerTransition,
            "cumulative" => PaperStepStatistic::Cumulative,
            other => return Err(format!("unknown step_statistic {other}").into()),
        })
        .with_restart_policy(match paper.restart_policy.as_str() {
            "restart" => PaperRestartPolicy::RestartOnLocalErrorInstall,
            "continue" => PaperRestartPolicy::ContinueThroughLocalErrorInstall,
            other => return Err(format!("unknown restart_policy {other}").into()),
        });
        config = config.with_warmup(
            WarmupConfig::default()
                .with_mass_adaptation(false)
                .with_step_size_adaptation(true)
                .with_paper_adaptation(paper),
        );
    }
    Ok(config)
}

fn starts(part: &Value) -> Result<Vec<Vec<f64>>, Box<dyn Error>> {
    let mut out = Vec::new();
    for row in part["starts"].as_array().ok_or("starts")? {
        let q: Vec<f64> = row.as_array().ok_or("start row")?.iter().map(|v| v.as_f64().ok_or("start value")).collect::<Result<_, _>>()?;
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

fn main() -> Result<(), Box<dyn Error>> {
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let study = dir.parent().ok_or("study dir")?.to_path_buf();
    let protocol = load_protocol(&study)?;
    if protocol["kernel"]["expected_algorithm_revision"] != ALGORITHM_REVISION {
        return Err(format!("kernel revision mismatch: {ALGORITHM_REVISION}").into());
    }
    let part = &protocol["parts"]["3_funnel"];
    let mut arguments = env::args().skip(1);
    let mode = arguments.next().ok_or("mode required")?;
    let starts = starts(part)?;
    let mass = DiagonalMass::identity(NonZeroUsize::new(DIMENSION).unwrap());
    let cap = usize::try_from(part["runtime_callback_cap"].as_u64().ok_or("cap")?)?;
    let wall_cap = protocol["wall_cap_seconds_per_cell"].as_u64().ok_or("wall cap")?;
    let threads = NonZeroUsize::new(usize::try_from(part["threads"].as_u64().unwrap_or(1))?).unwrap();
    let owalnuts_arms: Vec<String> = part["arms"]
        .as_object()
        .ok_or("arms")?
        .iter()
        .filter(|(_, v)| v["backend"] == "owalnuts")
        .map(|(k, _)| k.clone())
        .collect();
    let seeds: Vec<u64> = protocol["seeds"]["evidence"].as_array().ok_or("seeds")?.iter().map(|v| v.as_u64().unwrap()).collect();

    if mode == "--preflight" {
        let output = PathBuf::from(arguments.next().ok_or("output path required")?);
        if output.exists() {
            return Err("refusing to overwrite preflight output".into());
        }
        let target = Funnel { calls: AtomicUsize::new(0), deadline: None };
        let mut cells = Vec::new();
        for name in &owalnuts_arms {
            let arm = arm(part, name)?;
            for &seed in &seeds {
                let config = config(&arm, seed)?;
                let exact = config.worst_case_target_evaluations(NonZeroUsize::new(starts.len()).unwrap())?;
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
                    "arm": name, "seed": seed,
                    "worst_case_target_evaluations": report.worst_case_target_evaluations(),
                    "admission_ceiling": report.admission_ceiling(),
                    "runtime_callback_cap": budget.maximum(),
                    "total_transitions": report.total_transitions(),
                }));
            }
        }
        let result = json!({
            "schema": "numpyro-comparisons-v10/funnel-preflight",
            "algorithm_revision": ALGORITHM_REVISION,
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
    let seed: u64 = arguments.next().ok_or("seed required")?.parse()?;
    if !seeds.contains(&seed) {
        return Err(format!("seed {seed} is not an evidence seed").into());
    }
    let output = PathBuf::from(arguments.next().ok_or("output path required")?);
    if output.exists() {
        return Err("refusing to overwrite an arm artifact".into());
    }
    let arm = arm(part, &name)?;
    let config = config(&arm, seed)?;
    let exact = config.worst_case_target_evaluations(NonZeroUsize::new(starts.len()).unwrap())?;
    let budget = TargetEvaluationBudget::new(NonZeroUsize::new(cap.min(exact)).unwrap());
    let target = Funnel {
        calls: AtomicUsize::new(0),
        deadline: Some(Instant::now().checked_add(Duration::from_secs(wall_cap)).ok_or("deadline overflow")?),
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
    .map_err(|e| format!("arm {} seed {seed} failed closed ({:?}): {e}", arm.name, e.kind()))?;
    let wall = started.elapsed().as_secs_f64();

    let draws_path = output.with_extension("f64");
    let mut draws = fs::File::create(&draws_path)?;
    let mut chain_reports = Vec::new();
    for chain in chains.chains() {
        let mut bytes = Vec::with_capacity(chain.retained() * 16);
        for draw in 0..chain.retained() {
            let s = chain.sample(draw).unwrap();
            bytes.extend_from_slice(&s[0].to_le_bytes());
            bytes.extend_from_slice(&s[1].to_le_bytes());
        }
        draws.write_all(&bytes)?;
        let retained = chain.telemetry().retained();
        let discarded = chain.telemetry().discarded();
        let diagnostics = &chain.diagnostics()[chain.metadata().discarded()..];
        let mut depth_hist = vec![0usize; arm.depth + 1];
        let mut level_hist = vec![0usize; arm.levels + 1];
        let mut stops = std::collections::BTreeMap::<&str, usize>::new();
        let mut divergent = 0usize;
        let mut max_energy_error = 0.0f64;
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
        }
        let updates: Vec<Value> = chain
            .telemetry()
            .paper_adaptation_updates()
            .iter()
            .map(|u| {
                json!({
                    "transition": u.transition(), "window_index": u.window_index(), "orbits": u.orbits(),
                    "max_error_before": u.max_error_before(), "max_error_after": u.max_error_after(),
                    "unrefined_fraction_mean": u.unrefined_fraction_mean(),
                    "step_before": u.step_before(), "step_after": u.step_after(), "outcome": outcome_name(u.outcome())
                })
            })
            .collect();
        chain_reports.push(json!({
            "qualified_step_size": chain.metadata().qualified_step_size(),
            "final_max_error": chain.metadata().tuning().max_error(),
            "retained": {
                "target_calls": retained.target_calls_total(),
                "divergences": retained.divergences(),
                "divergent_transitions_from_diagnostics": divergent,
                "invalid_evaluation_stops": retained.invalid_evaluation_stops(),
                "refinement_exhaustion_stops": retained.refinement_exhaustion_stops(),
                "reverse_coarser_stops": retained.reverse_coarser_stops(),
                "maximum_depth_stops": retained.maximum_depth_stops(),
                "recoverable_target_failures": retained.recoverable_target_failures(),
                "leaves_built": retained.leaves_built(),
                "depth_histogram": depth_hist,
                "selected_refinement_level_histogram": level_hist,
                "stop_reasons": stops,
                "max_absolute_energy_error": max_energy_error,
            },
            "discarded": {
                "target_calls": discarded.target_calls_total(),
                "divergences": discarded.divergences(),
                "refinement_exhaustion_stops": discarded.refinement_exhaustion_stops(),
                "maximum_depth_stops": discarded.maximum_depth_stops(),
            },
            "paper_adaptation_updates": updates,
        }));
    }
    let report = json!({
        "schema": "numpyro-comparisons-v10/funnel-arm",
        "arm": arm.name,
        "backend": "owalnuts",
        "mode": if arm.paper.is_some() { "paper" } else { "fixed" },
        "algorithm_revision": chains.algorithm_revision(),
        "seed": seed,
        "chains": starts.len(),
        "retained_per_chain": arm.retained,
        "settings": {
            "step_size": arm.step_size, "max_error": arm.max_error, "max_refinement_levels": arm.levels,
            "max_depth": arm.depth, "min_micro_steps": arm.min_micro, "divergence_threshold": arm.divergence_threshold,
            "discarded": arm.discarded, "retained": arm.retained, "threads": threads.get()
        },
        "wall_seconds_total_sampler_call": wall,
        "timing_note": "one sampler call covering warmup and retained phases; compilation excluded",
        "wall_cap_seconds": wall_cap,
        "runtime_callback_cap": cap,
        "target_callbacks_started": budget.started(),
        "target_calls_observed": target.calls.load(Ordering::Relaxed),
        "admission_ceiling": exact,
        "draws_file": draws_path.file_name().unwrap().to_str().unwrap(),
        "draws_layout": "chain-major, per draw [omega, x_1] little-endian f64",
        "chains_detail": chain_reports
    });
    fs::create_dir_all(output.parent().ok_or("output parent")?)?;
    fs::write(&output, serde_json::to_vec_pretty(&report)?)?;
    eprintln!("arm {} seed {seed} done in {wall:.1}s, {} callbacks", arm.name, budget.started());
    Ok(())
}
