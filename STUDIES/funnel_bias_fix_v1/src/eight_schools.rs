//! outer-selection-bps-vs-multinomial-v1 runner.
//!
//! Samples the exact v38 noncentered Eight Schools density under two arms that
//! differ only in the research-only outer-orbit selection policy, and writes
//! per-cell retained draws, per-transition retained diagnostics, and work
//! telemetry to `artifacts/`. No statistics are computed here; see
//! `analyze.py`.
#![forbid(unsafe_code)]

use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DiagonalMass, KernelTuning, OuterOrbitSelection, RunConfig, StopReason,
    Target, TargetError, TargetEvaluationAdmissionLimit, TargetEvaluationBudget, WarmupConfig,
    preflight_chains_with_target_budget, sample_chains_with_target_budget,
};
use serde_json::{Value, json};
use std::{
    fs,
    num::NonZeroUsize,
    path::PathBuf,
    sync::atomic::{AtomicUsize, Ordering},
    time::{Duration, Instant},
};

const SEEDS: [u64; 1] = [82001];
const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;
const CAP: usize = 10_000_000;
const WALL_SECONDS: u64 = 120;
const LOG_2PI: f64 = 1.837_877_066_409_345_3;
const Y: [f64; 8] = [28., 8., -3., 7., -1., 1., 18., 12.];
const SE: [f64; 8] = [15., 10., 16., 11., 9., 11., 10., 18.];

fn normal_log_density(x: f64, mean: f64, sd: f64) -> f64 {
    -0.5 * LOG_2PI - sd.ln() - 0.5 * ((x - mean) / sd).powi(2)
}

/// Verbatim copy of the confirmation-v38 unconstrained density.
fn noncentered_log_density_gradient(q: &[f64], gradient: &mut [f64]) -> f64 {
    assert_eq!(q.len(), 10);
    let mu = q[0];
    let log_tau = q[1];
    let tau = log_tau.exp();
    let z = &q[2..];
    let mut value = normal_log_density(mu, 0., 5.)
        + (2. / (std::f64::consts::PI * 5. * (1. + (tau / 5.).powi(2)))).ln()
        + log_tau;
    gradient.fill(0.);
    gradient[0] = -mu / 25.;
    gradient[1] = 1. - 2. * tau * tau / (25. + tau * tau);
    for j in 0..8 {
        let theta = mu + tau * z[j];
        let residual = Y[j] - theta;
        let likelihood_gradient = residual / SE[j].powi(2);
        value += normal_log_density(Y[j], theta, SE[j]) + normal_log_density(z[j], 0., 1.);
        gradient[0] += likelihood_gradient;
        gradient[1] += likelihood_gradient * tau * z[j];
        gradient[j + 2] = -z[j] + likelihood_gradient * tau;
    }
    value
}

struct EightSchools {
    calls: AtomicUsize,
    deadline: Instant,
}

impl Target for EightSchools {
    fn dimension(&self) -> usize {
        10
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        let n = self.calls.fetch_add(1, Ordering::Relaxed) + 1;
        if n > CAP {
            return Err(TargetError::new("runtime target-evaluation budget exhausted"));
        }
        if Instant::now() >= self.deadline {
            return Err(TargetError::new("active process deadline exceeded"));
        }
        let value = noncentered_log_density_gradient(q, g);
        if value.is_finite() && g.iter().all(|x| x.is_finite()) {
            Ok(value)
        } else {
            Err(TargetError::new("nonfinite target evaluation"))
        }
    }
}

fn starts() -> Vec<Vec<f64>> {
    [-2., -1., 0., 1.]
        .map(|x| {
            let mut q = vec![0.; 10];
            q[1] = x;
            q
        })
        .to_vec()
}

fn config(seed: u64, selection: OuterOrbitSelection) -> RunConfig {
    RunConfig::new(WARMUP, NonZeroUsize::new(RETAINED).unwrap(), seed)
        .with_tuning(
            KernelTuning::new(
                0.3,
                NonZeroUsize::new(8).unwrap(),
                NonZeroUsize::new(1).unwrap(),
                NonZeroUsize::new(8).unwrap(),
                1.,
            )
            .expect("tuning")
            .with_divergence_threshold(1000.)
            .expect("divergence threshold"),
        )
        .with_warmup(
            WarmupConfig::new(0.95)
                .expect("warmup")
                .with_mass_adaptation(true),
        )
        .with_research_outer_orbit_selection(selection)
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

fn run_cell(seed: u64, arm: &str, selection: OuterOrbitSelection) -> Value {
    let config = config(seed, selection);
    let target = EightSchools {
        calls: AtomicUsize::new(0),
        deadline: Instant::now() + Duration::from_secs(WALL_SECONDS),
    };
    let exact = config
        .worst_case_target_evaluations(NonZeroUsize::new(CHAINS).unwrap())
        .expect("worst-case bound");
    let admission = TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap());
    let budget = TargetEvaluationBudget::new(NonZeroUsize::new(CAP).unwrap());
    let mass = DiagonalMass::identity(NonZeroUsize::new(10).unwrap());
    preflight_chains_with_target_budget(&target, &starts(), &mass, &config, admission, &budget)
        .expect("preflight");
    assert_eq!(target.calls.load(Ordering::Relaxed), 0, "preflight entered target");
    assert_eq!(budget.started(), 0, "preflight consumed budget");

    let begin = Instant::now();
    let output = sample_chains_with_target_budget(
        &target,
        &starts(),
        &mass,
        &config,
        NonZeroUsize::new(1).unwrap(),
        admission,
        &budget,
    )
    .unwrap_or_else(|e| panic!("{arm} seed {seed} failed closed: {e:?}"));
    let wall = begin.elapsed().as_secs_f64();
    let callbacks = target.calls.load(Ordering::Relaxed);

    let chains: Vec<Value> = output
        .chains()
        .iter()
        .enumerate()
        .map(|(index, chain)| {
            let dim = chain.dimension();
            let retained = chain.retained();
            let samples: Vec<Vec<f64>> = (0..retained)
                .map(|d| chain.sample(d).unwrap().to_vec())
                .collect();
            let self_retained = samples
                .windows(2)
                .filter(|w| w[0] == w[1])
                .count();
            let diagnostics = chain.diagnostics();
            assert_eq!(diagnostics.len(), WARMUP + RETAINED);
            let retained_diag = &diagnostics[WARMUP..];
            let telemetry = chain.telemetry();
            let ret = telemetry.retained();
            let disc = telemetry.discarded();
            json!({
                "chain": index,
                "dimension": dim,
                "retained": retained,
                "samples": samples,
                "self_retained_transitions": self_retained,
                "self_retention_comparisons": retained.saturating_sub(1),
                "retained_transitions": {
                    "depth": retained_diag.iter().map(|d| d.depth()).collect::<Vec<_>>(),
                    "leaves_built": retained_diag.iter().map(|d| d.leaves_built()).collect::<Vec<_>>(),
                    "target_evaluations": retained_diag.iter().map(|d| d.target_evaluations()).collect::<Vec<_>>(),
                    "initial_hamiltonian": retained_diag.iter().map(|d| d.initial_hamiltonian()).collect::<Vec<_>>(),
                    "maximum_absolute_energy_error": retained_diag.iter().map(|d| d.maximum_absolute_energy_error()).collect::<Vec<_>>(),
                    "stop": retained_diag.iter().map(|d| stop_name(d.stop())).collect::<Vec<_>>(),
                    "divergent": retained_diag.iter().map(|d| d.divergent()).collect::<Vec<_>>(),
                    "uniform_draws": retained_diag.iter().map(|d| d.uniform_draws()).collect::<Vec<_>>(),
                },
                "retained_work": {
                    "target_calls_total": ret.target_calls_total(),
                    "leaves_built": ret.leaves_built(),
                    "leaves_attempted": ret.leaves_attempted(),
                    "maximum_depth_stops": ret.maximum_depth_stops(),
                    "divergences": ret.divergences(),
                    "invalid_evaluation_stops": ret.invalid_evaluation_stops(),
                    "refinement_exhaustion_stops": ret.refinement_exhaustion_stops(),
                    "reverse_coarser_stops": ret.reverse_coarser_stops(),
                    "uniform_draws": ret.uniform_draws(),
                    "direction_draws": ret.direction_draws(),
                },
                "warmup_work": {
                    "target_calls_total": disc.target_calls_total(),
                    "divergences": disc.divergences(),
                    "maximum_depth_stops": disc.maximum_depth_stops(),
                },
                "final_step_size": chain.metadata().qualified_step_size(),
                "final_mass_diagonal": chain.metadata().mass_diagonal(),
            })
        })
        .collect();

    json!({
        "arm": arm,
        "seed": seed,
        "algorithm_revision": ALGORITHM_REVISION,
        "output_algorithm_revision": output.algorithm_revision(),
        "worst_case_target_evaluations": exact,
        "target_callbacks_total": callbacks,
        "sampler_wall_seconds": wall,
        "chains": chains,
    })
}

fn main() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let artifacts = root.join("artifacts");
    fs::create_dir_all(&artifacts).expect("artifacts dir");
    let arms = [
        ("bps", OuterOrbitSelection::BiasedProgressive),
        ("multinomial", OuterOrbitSelection::ExactNormalizedMultinomial),
    ];
    let mut index = Vec::new();
    for seed in SEEDS {
        for (arm, selection) in arms {
            let path = artifacts.join(format!("cell-{arm}-{seed}.json"));
            if path.exists() {
                panic!("refusing to overwrite existing artifact {}", path.display());
            }
            let cell = run_cell(seed, arm, selection);
            let text = serde_json::to_string(&cell).expect("serialize");
            fs::write(&path, text).expect("write cell");
            eprintln!(
                "{arm} seed {seed}: wall {:.3}s callbacks {} retained depth stops {}",
                cell["sampler_wall_seconds"].as_f64().unwrap(),
                cell["target_callbacks_total"],
                cell["chains"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(|c| c["retained_work"]["maximum_depth_stops"].as_u64().unwrap())
                    .sum::<u64>()
            );
            index.push(json!({"arm": arm, "seed": seed, "path": format!("artifacts/cell-{arm}-{seed}.json")}));
        }
    }
    fs::write(
        artifacts.join("index.json"),
        serde_json::to_string_pretty(&json!({
            "schema": "owalnuts-outer-selection-ablation-index/v1",
            "algorithm_revision": ALGORITHM_REVISION,
            "cells": index,
        }))
        .unwrap(),
    )
    .expect("write index");
}
