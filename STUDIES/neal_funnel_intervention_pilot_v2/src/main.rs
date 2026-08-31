#![forbid(unsafe_code)]

use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DiagonalMass, InitialStepSearchConfig, KernelTuning, RunConfig, StopReason,
    Target, TargetError, TargetEvaluationAdmissionLimit, TargetEvaluationBudget, WarmupConfig,
    preflight_chains_with_target_budget, sample_chains_with_target_budget,
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

const DIMENSION: usize = 10;
const CHAINS: usize = 4;
const RETAINED: usize = 10_000;
const CALLBACK_CAP: usize = 1_000_000_000;
const WALL_CAP_SECONDS: u64 = 300;
const EXPECTED_REVISION: &str = "walnutpie-trajectory-health-tau0.6-m1-r2-e1-d3-v6";
const PROTOCOL_SHA256: &str = "a9c7657491f445f57766d90002bd97eb7dd3d13e1dbca7e1a8e44ec53a8f49c3";
const KERNEL_SHA256: &str = "7e7305c0b6c38cb1b3691fd8802f2a352aec5af0ed009f821be18e6ee97785b9";
const FACADE_SHA256: &str = "b60cae3648c754d235080b303d98af9685606061fa07bd1f2242543a4831a4d3";
const ROOT_LOCK_SHA256: &str = "7edebbe0c27a612741d9e98c0b7086f7186d1fd4e6bde58bf3f2d6cc84704345";
const SEEDS: [u64; 3] = [2_026_091_101, 2_026_091_102, 2_026_091_103];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Initialization {
    Dispersed,
    CommonZero,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Adaptation {
    Baseline,
    Robust,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct Cell {
    seed: u64,
    initialization: Initialization,
    adaptation: Adaptation,
}

fn cells() -> Vec<Cell> {
    let mut cells = Vec::with_capacity(12);
    for seed in SEEDS {
        for initialization in [Initialization::Dispersed, Initialization::CommonZero] {
            for adaptation in [Adaptation::Baseline, Adaptation::Robust] {
                cells.push(Cell {
                    seed,
                    initialization,
                    adaptation,
                });
            }
        }
    }
    cells
}

struct Funnel(AtomicUsize);

impl Target for Funnel {
    fn dimension(&self) -> usize {
        DIMENSION
    }

    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        self.0.fetch_add(1, Ordering::Relaxed);
        let v = q[0];
        let inverse_variance = (-v).exp();
        if !inverse_variance.is_finite() {
            return Err(TargetError::recoverable("non-finite exp(-v)"));
        }
        let sum_squares = q[1..].iter().map(|x| x * x).sum::<f64>();
        gradient[0] = -v / 9.0 - 4.5 + 0.5 * inverse_variance * sum_squares;
        for index in 1..DIMENSION {
            gradient[index] = -inverse_variance * q[index];
        }
        Ok(-v * v / 18.0 - 4.5 * v - 0.5 * inverse_variance * sum_squares)
    }
}

fn starts(initialization: Initialization) -> [Vec<f64>; CHAINS] {
    let values = match initialization {
        Initialization::Dispersed => [-3.0, -1.0, 1.0, 3.0],
        Initialization::CommonZero => [0.0; CHAINS],
    };
    values.map(|v| {
        let mut q = vec![0.0; DIMENSION];
        q[0] = v;
        q
    })
}

fn config(cell: Cell) -> Result<RunConfig, Box<dyn Error>> {
    if !SEEDS.contains(&cell.seed) {
        return Err("seed is outside the frozen set".into());
    }
    let tuning = KernelTuning::new(
        0.3,
        NonZeroUsize::new(10).unwrap(),
        NonZeroUsize::new(1).unwrap(),
        NonZeroUsize::new(12).unwrap(),
        0.5,
    )?
    .with_divergence_threshold(1000.0)?;
    let warmup = match cell.adaptation {
        Adaptation::Baseline => WarmupConfig::new(0.9)?.with_mass_adaptation(true),
        Adaptation::Robust => WarmupConfig::new(0.9)?
            .with_mass_adaptation(true)
            .with_initial_step_search(InitialStepSearchConfig::new(
                NonZeroUsize::new(4).unwrap(),
                NonZeroUsize::new(16).unwrap(),
                NonZeroUsize::new(1_024).unwrap(),
            )?),
    };
    Ok(RunConfig::new(
        match cell.adaptation {
            Adaptation::Baseline => 2_000,
            Adaptation::Robust => 8_000,
        },
        NonZeroUsize::new(RETAINED).unwrap(),
        cell.seed,
    )
    .with_tuning(tuning)
    .with_warmup(warmup))
}

fn sha256(path: &Path) -> Result<String, Box<dyn Error>> {
    Ok(format!("{:x}", Sha256::digest(fs::read(path)?)))
}

fn study_root() -> Result<PathBuf, Box<dyn Error>> {
    Ok(PathBuf::from(env!("CARGO_MANIFEST_DIR")))
}

fn validate_tree() -> Result<(), Box<dyn Error>> {
    let root = study_root()?;
    if ALGORITHM_REVISION != EXPECTED_REVISION
        || sha256(&root.join("protocol.json"))? != PROTOCOL_SHA256
        || sha256(&root.join("../../src/kernel.rs"))? != KERNEL_SHA256
        || sha256(&root.join("../../src/walnutpie.rs"))? != FACADE_SHA256
        || sha256(&root.join("../../Cargo.lock"))? != ROOT_LOCK_SHA256
    {
        return Err("stale protocol, telemetry revision, shared source, or lockfile".into());
    }
    Ok(())
}

fn validate_authorization(path: &Path) -> Result<(), Box<dyn Error>> {
    validate_tree()?;
    let authorization: Value = serde_json::from_slice(&fs::read(path)?)?;
    let exact = |name: &str, expected: &str| {
        authorization.get(name).and_then(Value::as_str) == Some(expected)
    };
    if authorization.get("authorized").and_then(Value::as_bool) != Some(true)
        || !exact("protocol_sha256", PROTOCOL_SHA256)
        || !exact("kernel_sha256", KERNEL_SHA256)
        || !exact("facade_sha256", FACADE_SHA256)
        || !exact("root_lock_sha256", ROOT_LOCK_SHA256)
        || authorization.get("cells").and_then(Value::as_u64) != Some(12)
        || authorization.get("callback_cap").and_then(Value::as_u64) != Some(CALLBACK_CAP as u64)
        || authorization
            .get("wall_cap_seconds")
            .and_then(Value::as_u64)
            != Some(WALL_CAP_SECONDS)
    {
        return Err("authorization does not exactly match the frozen pilot".into());
    }
    Ok(())
}

fn create_atomic(path: &Path, bytes: &[u8]) -> Result<(), Box<dyn Error>> {
    if path.exists() {
        return Err("refusing to overwrite preexisting artifact".into());
    }
    let temporary = path.with_extension("json.pending");
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&temporary)?;
    file.write_all(bytes)?;
    file.sync_all()?;
    fs::hard_link(&temporary, path)?;
    fs::remove_file(temporary)?;
    Ok(())
}

fn preflight(output: &Path) -> Result<(), Box<dyn Error>> {
    validate_tree()?;
    let target = Funnel(AtomicUsize::new(0));
    let mass = DiagonalMass::identity(NonZeroUsize::new(DIMENSION).unwrap());
    let mut reports = Vec::new();
    for cell in cells() {
        let config = config(cell)?;
        let exact = config.worst_case_target_evaluations(NonZeroUsize::new(CHAINS).unwrap())?;
        let budget = TargetEvaluationBudget::new(NonZeroUsize::new(CALLBACK_CAP).unwrap());
        let report = preflight_chains_with_target_budget(
            &target,
            &starts(cell.initialization),
            &mass,
            &config,
            TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap()),
            &budget,
        )?;
        if target.0.load(Ordering::Relaxed) != 0 || budget.started() != 0 {
            return Err("preflight invoked a target callback".into());
        }
        reports.push(json!({
            "cell": format!("{cell:?}"),
            "seed": cell.seed,
            "initialization": format!("{:?}", cell.initialization),
            "adaptation": format!("{:?}", cell.adaptation),
            "warmup": config.discarded(),
            "initial_step_search": config.warmup().unwrap().initial_step_search().is_some(),
            "admission": report.admission_ceiling(),
            "callback_cap": budget.maximum(),
            "callbacks_started": budget.started()
        }));
    }
    create_atomic(
        output,
        &serde_json::to_vec_pretty(&json!({
            "schema": "neal-funnel-intervention-pilot-v2-preflight",
            "revision": ALGORITHM_REVISION,
            "sampling_authorized": false,
            "target_callbacks_started": target.0.load(Ordering::Relaxed),
            "cells": reports
        }))?,
    )
}

fn sample_cell(index: usize, output: &Path, authorization: &Path) -> Result<(), Box<dyn Error>> {
    validate_authorization(authorization)?;
    let cell = *cells().get(index).ok_or("cell index outside frozen grid")?;
    let config = config(cell)?;
    let positions = starts(cell.initialization);
    let mass = DiagonalMass::identity(NonZeroUsize::new(DIMENSION).unwrap());
    let target = Funnel(AtomicUsize::new(0));
    let exact = config.worst_case_target_evaluations(NonZeroUsize::new(CHAINS).unwrap())?;
    let budget = TargetEvaluationBudget::new(NonZeroUsize::new(CALLBACK_CAP).unwrap());
    let started = Instant::now();
    let result = sample_chains_with_target_budget(
        &target,
        &positions,
        &mass,
        &config,
        NonZeroUsize::new(1).unwrap(),
        TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap()),
        &budget,
    )?;
    let seconds = started.elapsed().as_secs_f64();
    if seconds > WALL_CAP_SECONDS as f64 {
        return Err("cell exceeded active process wall cap".into());
    }
    let mut samples = Vec::new();
    let mut chains = Vec::new();
    for chain in result.chains() {
        samples.push(
            (0..RETAINED)
                .map(|draw| chain.sample(draw).unwrap().to_vec())
                .collect::<Vec<_>>(),
        );
        let retained = chain.telemetry().retained();
        let diagnostics = &chain.diagnostics()[config.discarded()..];
        chains.push(json!({
            "qualified_step_size": chain.metadata().qualified_step_size(),
            "target_calls": retained.target_calls_total(),
            "divergences": retained.divergences(),
            "invalid_stops": retained.invalid_evaluation_stops(),
            "refinement_exhaustions": retained.refinement_exhaustion_stops(),
            "reverse_coarser_stops": retained.reverse_coarser_stops(),
            "reverse_coarser_rejections": retained.reverse_coarser_rejections(),
            "maximum_depth_stops": retained.maximum_depth_stops(),
            "recoverable_target_failures": retained.recoverable_target_failures(),
            "max_energy_error": diagnostics.iter()
                .map(|d| d.maximum_absolute_energy_error()).fold(0.0_f64, f64::max),
            "stop_count_crosscheck": diagnostics.iter().filter(
                |d| d.stop() == StopReason::RefinementExhausted).count()
        }));
    }
    create_atomic(
        output,
        &serde_json::to_vec(&json!({
            "schema": "neal-funnel-intervention-pilot-v2-cell",
            "revision": ALGORITHM_REVISION,
            "cell_index": index,
            "seed": cell.seed,
            "initialization": format!("{:?}", cell.initialization),
            "adaptation": format!("{:?}", cell.adaptation),
            "warmup": config.discarded(),
            "retained": RETAINED,
            "kernel_seconds": seconds,
            "wall_cap_seconds": WALL_CAP_SECONDS,
            "callback_cap": CALLBACK_CAP,
            "callbacks_started": budget.started(),
            "admission": exact,
            "chains": chains,
            "samples": samples
        }))?,
    )
}

fn parse_index(value: Option<String>) -> Result<usize, Box<dyn Error>> {
    Ok(value.ok_or("cell index required")?.parse()?)
}

fn main() -> Result<(), Box<dyn Error>> {
    let mut arguments = env::args().skip(1);
    match arguments.next().as_deref() {
        Some("--preflight") => {
            let output = PathBuf::from(arguments.next().ok_or("output required")?);
            preflight(&output)
        }
        Some("--validate-authorization") => {
            let authorization = PathBuf::from(arguments.next().ok_or("authorization required")?);
            validate_authorization(&authorization)
        }
        Some("--cell") => {
            let index = parse_index(arguments.next())?;
            let output = PathBuf::from(arguments.next().ok_or("output required")?);
            let authorization = PathBuf::from(arguments.next().ok_or("authorization required")?);
            sample_cell(index, &output, &authorization)
        }
        _ => Err("mode must be --preflight, --validate-authorization, or --cell".into()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn frozen_grid_and_configs_are_exact() {
        let grid = cells();
        assert_eq!(grid.len(), 12);
        assert_eq!(
            grid.iter().map(|c| c.seed).collect::<Vec<_>>(),
            [vec![SEEDS[0]; 4], vec![SEEDS[1]; 4], vec![SEEDS[2]; 4]].concat()
        );
        for cell in grid {
            let run = config(cell).unwrap();
            assert_eq!(run.seed(), cell.seed);
            assert_eq!(run.retained(), 10_000);
            assert_eq!(run.tuning().step_size(), 0.3);
            assert_eq!(run.tuning().max_refinement_levels(), 12);
            assert_eq!(run.tuning().min_micro_steps(), 1);
            assert_eq!(run.tuning().max_error(), 0.5);
            assert_eq!(run.tuning().divergence_threshold(), 1000.0);
            assert_eq!(run.tuning().max_depth(), 10);
            let positions = starts(cell.initialization);
            assert!(positions.iter().all(|position| position[1..] == [0.0; 9]));
            assert_eq!(
                positions.map(|position| position[0]),
                match cell.initialization {
                    Initialization::Dispersed => [-3.0, -1.0, 1.0, 3.0],
                    Initialization::CommonZero => [0.0; 4],
                }
            );
            let search = run.warmup().unwrap().initial_step_search();
            match cell.adaptation {
                Adaptation::Baseline => {
                    assert_eq!(run.discarded(), 2_000);
                    assert!(search.is_none());
                }
                Adaptation::Robust => {
                    assert_eq!(run.discarded(), 8_000);
                    let search = search.unwrap();
                    assert_eq!(
                        (
                            search.probes(),
                            search.max_steps(),
                            search.max_target_calls()
                        ),
                        (4, 16, 1_024)
                    );
                }
            }
        }
    }

    #[test]
    fn wrong_seed_and_preexisting_artifact_fail_closed() {
        let mut cell = cells()[0];
        cell.seed = 1;
        assert!(config(cell).is_err());
        let path = env::temp_dir().join(format!("owalnuts-v2-existing-{}", std::process::id()));
        fs::write(&path, b"existing").unwrap();
        assert!(create_atomic(&path, b"replacement").is_err());
        assert_eq!(fs::read(&path).unwrap(), b"existing");
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn partial_pending_output_and_reuse_fail_closed() {
        let path = env::temp_dir().join(format!("owalnuts-v2-atomic-{}", std::process::id()));
        let pending = path.with_extension("json.pending");
        fs::write(&pending, b"partial").unwrap();
        assert!(create_atomic(&path, b"complete").is_err());
        assert!(!path.exists());
        fs::remove_file(pending).unwrap();
        create_atomic(&path, b"complete").unwrap();
        assert!(create_atomic(&path, b"again").is_err());
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn stale_revision_and_caps_are_constants_not_cli_inputs() {
        assert_eq!(ALGORITHM_REVISION, EXPECTED_REVISION);
        assert_eq!(CALLBACK_CAP, 1_000_000_000);
        assert_eq!(WALL_CAP_SECONDS, 300);
        assert!(parse_index(Some("12".into())).unwrap() >= cells().len());
        assert!(parse_index(Some("wrong".into())).is_err());
    }

    #[test]
    fn malformed_or_stale_authorization_is_rejected() {
        let path = env::temp_dir().join(format!("owalnuts-v2-auth-{}", std::process::id()));
        fs::write(
            &path,
            br#"{"authorized":true,"cells":12,"callback_cap":999999999,
                "wall_cap_seconds":300}"#,
        )
        .unwrap();
        assert!(validate_authorization(&path).is_err());
        fs::remove_file(path).unwrap();
    }
}
