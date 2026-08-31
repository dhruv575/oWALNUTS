#![forbid(unsafe_code)]

use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DiagonalMass, KernelTuning, ResearchRestartReferenceMultiplier, RunConfig,
    StopReason, Target, TargetError, TargetEvaluationAdmissionLimit, TargetEvaluationBudget,
    WarmupConfig, preflight_chains_with_target_budget, sample_chains_with_target_budget,
};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    env,
    error::Error,
    fs::{self, OpenOptions},
    io::Write,
    num::NonZeroUsize,
    path::{Path, PathBuf},
    sync::atomic::{AtomicUsize, Ordering},
    time::Instant,
};

const SEEDS: [u64; 3] = [2_026_092_101, 2_026_092_102, 2_026_092_103];
const CALLBACK_CAP: usize = 1_000_000_000;
const WALL_CAP_SECONDS: u64 = 300;
const PROTOCOL_SHA256: &str = "a0f1cf68caabba7dc1157c8e739210396e7ba56c33386bdea878a683ecf579fa";
const KERNEL_SHA256: &str = "c115972afc46cea75d551b3cd49f4db8d981be3add1393fa1bbe1b4549774faf";
const FACADE_SHA256: &str = "532d403d70d63d8da76f832dbf4138cf78b9ee0dcecc043c0253aee144827510";
const CHECKPOINTS: [usize; 27] = [
    0, 1, 2, 4, 8, 16, 32, 64, 74, 75, 99, 100, 149, 150, 249, 250, 449, 450, 849, 850, 1649, 1650,
    1949, 1950, 1960, 1980, 1999,
];

struct Funnel(AtomicUsize);

impl Target for Funnel {
    fn dimension(&self) -> usize {
        10
    }
    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        self.0.fetch_add(1, Ordering::Relaxed);
        let inverse_variance = (-q[0]).exp();
        let sum_squares = q[1..].iter().map(|x| x * x).sum::<f64>();
        gradient[0] = -q[0] / 9.0 - 4.5 + 0.5 * inverse_variance * sum_squares;
        for index in 1..10 {
            gradient[index] = -inverse_variance * q[index];
        }
        Ok(-q[0] * q[0] / 18.0 - 4.5 * q[0] - 0.5 * inverse_variance * sum_squares)
    }
}

fn cells() -> Vec<(u64, usize, bool)> {
    SEEDS
        .into_iter()
        .flat_map(|seed| {
            [1usize, 10]
                .into_iter()
                .flat_map(move |center| [true, false].map(|adaptive| (seed, center, adaptive)))
        })
        .collect()
}

fn starts() -> [Vec<f64>; 4] {
    [-3.0, -1.0, 1.0, 3.0].map(|v| {
        let mut q = vec![0.0; 10];
        q[0] = v;
        q
    })
}

fn config(seed: u64, center: usize, adaptive: bool) -> Result<RunConfig, Box<dyn Error>> {
    if !SEEDS.contains(&seed) || ![1, 10].contains(&center) {
        return Err("cell outside frozen grid".into());
    }
    let tuning = KernelTuning::new(
        0.3,
        NonZeroUsize::new(10).unwrap(),
        NonZeroUsize::new(1).unwrap(),
        NonZeroUsize::new(12).unwrap(),
        0.5,
    )?
    .with_divergence_threshold(1000.0)?;
    Ok(
        RunConfig::new(2_000, NonZeroUsize::new(10_000).unwrap(), seed)
            .with_tuning(tuning)
            .with_warmup(
                WarmupConfig::new(0.9)?
                    .with_mass_adaptation(adaptive)
                    .with_step_size_adaptation(true)
                    .with_telemetry_checkpoints(CHECKPOINTS.to_vec())?
                    .with_research_restart_reference_multiplier(if center == 1 {
                        ResearchRestartReferenceMultiplier::One
                    } else {
                        ResearchRestartReferenceMultiplier::Ten
                    }),
            ),
    )
}

fn sha256(path: &Path) -> Result<String, Box<dyn Error>> {
    Ok(format!("{:x}", Sha256::digest(fs::read(path)?)))
}

fn validate_tree() -> Result<(), Box<dyn Error>> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    if ALGORITHM_REVISION != "walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v7"
        || sha256(&root.join("protocol.json"))? != PROTOCOL_SHA256
        || sha256(&root.join("../../src/kernel.rs"))? != KERNEL_SHA256
        || sha256(&root.join("../../src/walnutpie.rs"))? != FACADE_SHA256
    {
        return Err("stale protocol, revision, or shared source".into());
    }
    Ok(())
}

fn validate_authorization(path: &Path) -> Result<(), Box<dyn Error>> {
    validate_tree()?;
    let value: Value = serde_json::from_slice(&fs::read(path)?)?;
    if value.get("authorized").and_then(Value::as_bool) != Some(true)
        || value.get("protocol_sha256").and_then(Value::as_str) != Some(PROTOCOL_SHA256)
        || value.get("kernel_sha256").and_then(Value::as_str) != Some(KERNEL_SHA256)
        || value.get("facade_sha256").and_then(Value::as_str) != Some(FACADE_SHA256)
        || value.get("cells").and_then(Value::as_u64) != Some(12)
        || value.get("callback_cap").and_then(Value::as_u64) != Some(CALLBACK_CAP as u64)
        || value.get("wall_cap_seconds").and_then(Value::as_u64) != Some(WALL_CAP_SECONDS)
    {
        return Err("authorization does not match frozen diagnostic".into());
    }
    Ok(())
}

fn create_atomic(path: &Path, bytes: &[u8]) -> Result<(), Box<dyn Error>> {
    if path.exists() {
        return Err("refusing to overwrite artifact".into());
    }
    let pending = path.with_extension("json.pending");
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&pending)?;
    file.write_all(bytes)?;
    file.sync_all()?;
    fs::hard_link(&pending, path)?;
    fs::remove_file(pending)?;
    Ok(())
}

fn preflight(output: &Path) -> Result<(), Box<dyn Error>> {
    validate_tree()?;
    let target = Funnel(AtomicUsize::new(0));
    let positions = starts();
    let mass = DiagonalMass::identity(NonZeroUsize::new(10).unwrap());
    let mut reports = Vec::new();
    for (seed, center, adaptive) in cells() {
        let config = config(seed, center, adaptive)?;
        let exact = config.worst_case_target_evaluations(NonZeroUsize::new(4).unwrap())?;
        let budget = TargetEvaluationBudget::new(NonZeroUsize::new(CALLBACK_CAP).unwrap());
        let report = preflight_chains_with_target_budget(
            &target,
            &positions,
            &mass,
            &config,
            TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap()),
            &budget,
        )?;
        if target.0.load(Ordering::Relaxed) != 0 || budget.started() != 0 {
            return Err("preflight invoked target".into());
        }
        reports.push(json!({
            "seed":seed,
            "restart_center_multiplier":center,
            "metric_policy":if adaptive{"adaptive_diagonal"}else{"fixed_identity"},
            "admission":report.admission_ceiling(),
            "callback_cap":budget.maximum(),
            "callbacks_started":budget.started(),
            "dispatch_ready":true
        }));
    }
    create_atomic(
        output,
        &serde_json::to_vec_pretty(&json!({
            "schema":"neal-funnel-dual-averaging-diagnostic-v3-preflight-plan",
            "algorithm_revision":ALGORITHM_REVISION,
            "sampling_authorized":false,
            "instrumentation_ready":true,
            "target_callbacks_started":target.0.load(Ordering::Relaxed),
            "cells":reports
        }))?,
    )
}

fn sample_cell(index: usize, output: &Path, authorization: &Path) -> Result<(), Box<dyn Error>> {
    validate_authorization(authorization)?;
    let (seed, center, adaptive) = *cells().get(index).ok_or("cell index outside grid")?;
    let config = config(seed, center, adaptive)?;
    let target = Funnel(AtomicUsize::new(0));
    let mass = DiagonalMass::identity(NonZeroUsize::new(10).unwrap());
    let exact = config.worst_case_target_evaluations(NonZeroUsize::new(4).unwrap())?;
    let budget = TargetEvaluationBudget::new(NonZeroUsize::new(CALLBACK_CAP).unwrap());
    let started = Instant::now();
    let output_value = sample_chains_with_target_budget(
        &target,
        &starts(),
        &mass,
        &config,
        NonZeroUsize::new(1).unwrap(),
        TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap()),
        &budget,
    )?;
    let seconds = started.elapsed().as_secs_f64();
    if seconds > WALL_CAP_SECONDS as f64 {
        return Err("cell exceeded wall cap".into());
    }
    let mut samples = Vec::new();
    let mut chains = Vec::new();
    for chain in output_value.chains() {
        samples.push(
            (0..10_000)
                .map(|draw| chain.sample(draw).unwrap().to_vec())
                .collect::<Vec<_>>(),
        );
        let retained = chain.telemetry().retained();
        let retained_diagnostics = &chain.diagnostics()[2_000..];
        let checkpoints = chain
            .telemetry()
            .warmup_checkpoints()
            .iter()
            .map(|point| {
                let summary = |value: owalnuts::walnutpie::AcceptanceStatisticSummary| {
                    json!({"count":value.count(),"mean":value.mean(),"variance":value.variance(),
                        "minimum":value.minimum(),"maximum":value.maximum()})
                };
                let dual = point.dual_averaging().map(|value| json!({
                    "iteration":value.iteration(),"target":value.target(),"mu":value.mu(),
                    "h_bar":value.h_bar(),"log_step":value.log_step(),
                    "log_step_bar":value.log_step_bar()
                }));
                json!({"transition":point.transition(),"phase":format!("{:?}",point.phase()),
                    "window_index":point.window_index(),"step_before":point.step_before(),
                    "step_after":point.step_after(),"current":summary(point.current_coarse_endpoint()),
                    "trajectory":summary(point.accepted_trajectory()),"dual":dual,
                    "target_calls":point.target_calls(),"divergent":point.divergent(),
                    "refinement_attempts":point.refinement_attempts(),
                    "reverse_coarser_rejections":point.reverse_coarser_rejections()})
            })
            .collect::<Vec<_>>();
        let metric_updates = chain.telemetry().metric_updates().iter().map(|update| json!({
            "window_index":update.window_index(),"transition":update.transition(),
            "sample_count":update.sample_count(),"outcome":format!("{:?}",update.outcome()),
            "mass_before":update.mass_diagonal_before(),"mass_after":update.mass_diagonal(),
            "step_before":update.step_before(),"step_after_search":update.step_after_search(),
            "step_after_restart":update.step_after_restart(),
            "restart_multiplier":update.restart_reference_multiplier().map(|x|x.value()),
            "dual_after_restart":update.dual_averaging_after_restart().map(|d|json!({
                "iteration":d.iteration(),"mu":d.mu(),"h_bar":d.h_bar(),
                "log_step":d.log_step(),"log_step_bar":d.log_step_bar()
            }))
        })).collect::<Vec<_>>();
        chains.push(json!({
            "qualified_step_size":chain.metadata().qualified_step_size(),
            "mass_diagonal":chain.metadata().mass_diagonal(),
            "target_calls":retained.target_calls_total(),"warmup_target_calls":chain.telemetry().discarded().target_calls_total(),
            "divergences":retained.divergences(),"invalid_stops":retained.invalid_evaluation_stops(),
            "refinement_exhaustions":retained.refinement_exhaustion_stops(),
            "reverse_coarser_stops":retained.reverse_coarser_stops(),
            "reverse_coarser_rejections":retained.reverse_coarser_rejections(),
            "maximum_depth_stops":retained.maximum_depth_stops(),
            "recoverable_target_failures":retained.recoverable_target_failures(),
            "max_energy_error":retained_diagnostics.iter().map(|d|d.maximum_absolute_energy_error()).fold(0.0_f64,f64::max),
            "stop_count_crosscheck":retained_diagnostics.iter().filter(|d|d.stop()==StopReason::RefinementExhausted).count(),
            "checkpoints":checkpoints,"metric_updates":metric_updates
        }));
    }
    create_atomic(
        output,
        &serde_json::to_vec(&json!({
            "schema":"neal-funnel-dual-averaging-diagnostic-v3-cell","revision":ALGORITHM_REVISION,
            "cell_index":index,"seed":seed,"restart_center_multiplier":center,
            "metric_policy":if adaptive{"adaptive_diagonal"}else{"fixed_identity"},
            "warmup":2000,"retained":10000,"kernel_seconds":seconds,
            "wall_cap_seconds":WALL_CAP_SECONDS,"callback_cap":CALLBACK_CAP,
            "callbacks_started":budget.started(),"admission":exact,"chains":chains,"samples":samples
        }))?,
    )
}

fn main() -> Result<(), Box<dyn Error>> {
    let mut arguments = env::args().skip(1);
    match arguments.next().as_deref() {
        Some("--preflight") => {
            preflight(&PathBuf::from(arguments.next().ok_or("output required")?))
        }
        Some("--validate-authorization") => validate_authorization(&PathBuf::from(
            arguments.next().ok_or("authorization required")?,
        )),
        Some("--cell") => sample_cell(
            arguments.next().ok_or("index required")?.parse()?,
            &PathBuf::from(arguments.next().ok_or("output required")?),
            &PathBuf::from(arguments.next().ok_or("authorization required")?),
        ),
        _ => Err("invalid mode".into()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn frozen_factorial_is_exact_and_unique() {
        let cells = cells();
        assert_eq!(cells.len(), 12);
        let mut unique = cells.clone();
        unique.sort();
        unique.dedup();
        assert_eq!(unique.len(), 12);
        assert!(cells.iter().all(|(_, center, _)| [1, 10].contains(center)));
    }
}
