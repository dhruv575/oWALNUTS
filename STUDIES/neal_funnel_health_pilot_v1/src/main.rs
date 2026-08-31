#![forbid(unsafe_code)]

use owalnuts::walnutpie::{
    DiagonalMass, KernelTuning, RunConfig, Target, TargetError, TargetEvaluationAdmissionLimit,
    TargetEvaluationBudget, WarmupConfig, preflight_chains_with_target_budget,
    sample_chains_with_target_budget,
};
use serde_json::json;
use std::{
    env,
    error::Error,
    fs,
    num::NonZeroUsize,
    path::PathBuf,
    sync::atomic::{AtomicUsize, Ordering},
    time::{Duration, Instant},
};

const DIMENSION: usize = 10;
const CHAINS: usize = 4;
const WARMUP: usize = 2_000;
const RETAINED: usize = 10_000;
const RUNTIME_CAP: usize = 1_000_000_000;
const WALL_CAP_SECONDS: u64 = 300;
const SEEDS: [u64; 3] = [2_026_090_101, 2_026_090_102, 2_026_090_103];
const TARGET_ACCEPTS: [f64; 2] = [0.90, 0.95];
const REFINEMENT_LEVELS: [usize; 2] = [8, 12];

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
            return Err(TargetError::new("pilot cell wall cap exceeded"));
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

fn main() -> Result<(), Box<dyn Error>> {
    let mut arguments = env::args().skip(1);
    let mode = arguments.next().ok_or("mode required")?;
    let output = PathBuf::from(arguments.next().ok_or("preflight output path required")?);
    if output.exists() {
        return Err("refusing to overwrite preflight output".into());
    }

    let target = Funnel {
        calls: AtomicUsize::new(0),
        deadline: None,
    };
    let starts = [-3.0, -1.0, 1.0, 3.0].map(|v| {
        let mut q = vec![0.0; DIMENSION];
        q[0] = v;
        q
    });
    let mass = DiagonalMass::identity(NonZeroUsize::new(DIMENSION).unwrap());
    if mode == "--sample" {
        return sample_grid(output, starts, mass);
    }
    if mode != "--preflight" {
        return Err("mode must be --preflight or --sample".into());
    }
    let mut cells = Vec::new();
    for seed in SEEDS {
        for target_accept in TARGET_ACCEPTS {
            for levels in REFINEMENT_LEVELS {
                let tuning = KernelTuning::new(
                    0.3,
                    NonZeroUsize::new(10).unwrap(),
                    NonZeroUsize::new(1).unwrap(),
                    NonZeroUsize::new(levels).unwrap(),
                    0.5,
                )?
                .with_divergence_threshold(1000.0)?;
                let config = RunConfig::new(WARMUP, NonZeroUsize::new(RETAINED).unwrap(), seed)
                    .with_tuning(tuning)
                    .with_warmup(WarmupConfig::new(target_accept)?.with_mass_adaptation(true));
                let exact =
                    config.worst_case_target_evaluations(NonZeroUsize::new(CHAINS).unwrap())?;
                let budget = TargetEvaluationBudget::new(NonZeroUsize::new(RUNTIME_CAP).unwrap());
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
                    "seed": seed,
                    "target_accept": target_accept,
                    "maximum_refinement_levels": levels,
                    "worst_case_target_evaluations": report.worst_case_target_evaluations(),
                    "admission_ceiling": report.admission_ceiling(),
                    "runtime_callback_cap": budget.maximum(),
                    "budget_callbacks_started": budget.started()
                }));
            }
        }
    }
    let result = json!({
        "schema": "owalnuts-neal-funnel-health-pilot-preflight-v1",
        "mode": "dispatch-only; sampling unavailable",
        "sampling_authorized": false,
        "target_callbacks_started": target.calls.load(Ordering::Relaxed),
        "cells": cells
    });
    fs::create_dir_all(output.parent().ok_or("output must have a parent")?)?;
    fs::write(output, serde_json::to_vec_pretty(&result)?)?;
    Ok(())
}

fn sample_grid(
    output: PathBuf,
    starts: [Vec<f64>; CHAINS],
    mass: DiagonalMass,
) -> Result<(), Box<dyn Error>> {
    let authorization = output
        .parent()
        .ok_or("output must have a parent")?
        .parent()
        .ok_or("output directory must be under the study")?
        .join("AUTHORIZE_SAMPLING.json");
    if !authorization.is_file() {
        return Err("checksum-bound AUTHORIZE_SAMPLING.json is required".into());
    }
    fs::create_dir_all(&output)?;
    for seed in SEEDS {
        for target_accept in TARGET_ACCEPTS {
            for levels in REFINEMENT_LEVELS {
                let name = format!("seed-{seed}-a{:.2}-r{levels}.json", target_accept);
                let path = output.join(name);
                if path.exists() {
                    return Err("refusing to overwrite a pilot cell".into());
                }
                let tuning = KernelTuning::new(
                    0.3,
                    NonZeroUsize::new(10).unwrap(),
                    NonZeroUsize::new(1).unwrap(),
                    NonZeroUsize::new(levels).unwrap(),
                    0.5,
                )?
                .with_divergence_threshold(1000.0)?;
                let config = RunConfig::new(WARMUP, NonZeroUsize::new(RETAINED).unwrap(), seed)
                    .with_tuning(tuning)
                    .with_warmup(WarmupConfig::new(target_accept)?.with_mass_adaptation(true));
                let exact =
                    config.worst_case_target_evaluations(NonZeroUsize::new(CHAINS).unwrap())?;
                let budget = TargetEvaluationBudget::new(NonZeroUsize::new(RUNTIME_CAP).unwrap());
                let target = Funnel {
                    calls: AtomicUsize::new(0),
                    deadline: Some(
                        Instant::now()
                            .checked_add(Duration::from_secs(WALL_CAP_SECONDS))
                            .ok_or("wall deadline overflow")?,
                    ),
                };
                let started = Instant::now();
                let chains = sample_chains_with_target_budget(
                    &target,
                    &starts,
                    &mass,
                    &config,
                    NonZeroUsize::new(1).unwrap(),
                    TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap()),
                    &budget,
                )?;
                let kernel_seconds = started.elapsed().as_secs_f64();
                if kernel_seconds > WALL_CAP_SECONDS as f64 {
                    return Err("pilot cell wall cap exceeded".into());
                }
                let mut samples = Vec::new();
                let mut reports = Vec::new();
                for chain in chains.chains() {
                    samples.push(
                        (0..RETAINED)
                            .map(|draw| chain.sample(draw).unwrap().to_vec())
                            .collect::<Vec<_>>(),
                    );
                    let retained = chain.telemetry().retained();
                    reports.push(json!({
                        "qualified_step_size": chain.metadata().qualified_step_size(),
                        "target_calls": retained.target_calls_total(),
                        "divergences": retained.divergences(),
                        "invalid_evaluation_stops": retained.invalid_evaluation_stops(),
                        "refinement_exhaustion_stops": retained.refinement_exhaustion_stops(),
                        "reverse_coarser_stops": retained.reverse_coarser_stops(),
                        "reverse_coarser_rejections": retained.reverse_coarser_rejections(),
                        "maximum_depth_stops": retained.maximum_depth_stops(),
                        "recoverable_target_failures": retained.recoverable_target_failures(),
                        "forward_refinement_attempts": retained.forward_refinement_attempts(),
                        "forward_micro_steps": retained.forward_micro_steps_executed(),
                        "reverse_coarsening_attempts": retained.reverse_coarsening_attempts(),
                        "reverse_micro_steps": retained.reverse_micro_steps_executed()
                    }));
                }
                let report = json!({
                    "schema": "owalnuts-neal-funnel-health-pilot-cell-v1",
                    "seed": seed,
                    "target_accept": target_accept,
                    "maximum_refinement_levels": levels,
                    "kernel_seconds_including_warmup": kernel_seconds,
                    "wall_cap_seconds": WALL_CAP_SECONDS,
                    "runtime_callback_cap": RUNTIME_CAP,
                    "target_callbacks_started": budget.started(),
                    "admission_ceiling": exact,
                    "chains": reports,
                    "samples": samples
                });
                fs::write(path, serde_json::to_vec(&report)?)?;
            }
        }
    }
    Ok(())
}
