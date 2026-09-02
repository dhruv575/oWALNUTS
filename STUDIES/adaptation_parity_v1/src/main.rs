//! Warmup-parity ablation: one (model, configuration, seed) cell.
//!
//! Usage: `adaptation-parity-v1 <model.so> <data.json> <config> <seed> <out.json> [threads]`
//!
//! `config` is `base` or a `+`-joined set of the opt-in changes under test
//! (`traj`, `init`, `reg`, `mu10`, `depth10`; `warmup4` = the four warmup
//! changes; `all` = `warmup4+depth10`; `h1` = start the search at `h_0 = 1`).
//! Everything else is the posteriordb benchmark v1 `owalnuts-da` arm: four
//! uniform(-2, 2) unconstrained starts from a seed-derived RNG, 1,000 warmup +
//! 1,000 retained transitions on four parallel chains, Python-package default
//! kernel tuning. Writes unconstrained draws, work/health counters, warmup
//! telemetry (step searches, metric updates), refinement-level histograms for
//! warmup and retained transitions, and `owalnuts::diagnostics` summaries on
//! the unconstrained coordinates.
#![forbid(unsafe_code)]

use owalnuts::diagnostics::{ess_bulk, ess_tail, rhat};
use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DiagonalMass, DiagonalMetricRegularization, DualAveragingAcceptance,
    InitialStepSearchConfig, KernelTuning, RunConfig, Target, TargetEvaluationAdmissionLimit,
    TargetEvaluationBudget, WarmupConfig, preflight_chains_with_target_budget,
    sample_chains_with_target_budget,
};
use owalnuts_bridgestan::{StanTarget, default_preload};
use rand::{Rng, SeedableRng, rngs::SmallRng};
use serde_json::json;
use std::{env, error::Error, fs, num::NonZeroUsize, path::Path, time::Instant};

const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;
const STEP_SIZE: f64 = 0.1;
const MIN_MICRO_STEPS: usize = 1;
const MAX_REFINEMENT_LEVELS: usize = 4;
const MAX_ERROR: f64 = 1.0;
const TARGET_ACCEPT: f64 = 0.8;

#[derive(Clone, Copy, Debug, Default)]
struct Flags {
    traj: bool,
    init: bool,
    reg: bool,
    mu10: bool,
    depth10: bool,
    h1: bool,
}

impl Flags {
    fn parse(config: &str) -> Result<Self, Box<dyn Error>> {
        let mut flags = Self::default();
        for token in config.split('+') {
            match token {
                "base" => {}
                "traj" => flags.traj = true,
                "init" => flags.init = true,
                "reg" => flags.reg = true,
                "mu10" => flags.mu10 = true,
                "depth10" => flags.depth10 = true,
                "h1" => flags.h1 = true,
                "warmup4" => {
                    flags.traj = true;
                    flags.init = true;
                    flags.reg = true;
                    flags.mu10 = true;
                }
                "all" => {
                    flags.traj = true;
                    flags.init = true;
                    flags.reg = true;
                    flags.mu10 = true;
                    flags.depth10 = true;
                }
                other => return Err(format!("unknown configuration token {other:?}").into()),
            }
        }
        Ok(flags)
    }
    fn max_depth(self) -> usize {
        if self.depth10 { 10 } else { 8 }
    }
    fn step_size(self) -> f64 {
        if self.h1 { 1.0 } else { STEP_SIZE }
    }
}

fn nz(n: usize) -> NonZeroUsize {
    NonZeroUsize::new(n).expect("nonzero")
}

fn starts(dimension: usize, seed: u64) -> Vec<Vec<f64>> {
    let mut rng = SmallRng::seed_from_u64(seed ^ 0x5eed_0000_0000);
    (0..CHAINS)
        .map(|_| (0..dimension).map(|_| rng.random_range(-2.0..2.0)).collect())
        .collect()
}

fn config(flags: Flags, seed: u64) -> Result<RunConfig, Box<dyn Error>> {
    let tuning = KernelTuning::new(
        flags.step_size(),
        nz(flags.max_depth()),
        nz(MIN_MICRO_STEPS),
        nz(MAX_REFINEMENT_LEVELS),
        MAX_ERROR,
    )?;
    let mut warmup = WarmupConfig::new(TARGET_ACCEPT)?.with_mass_adaptation(true);
    if flags.traj {
        warmup = warmup
            .with_dual_averaging_acceptance(DualAveragingAcceptance::MeanTrajectoryAcceptance);
    }
    if flags.init {
        warmup = warmup.with_initial_step_search(InitialStepSearchConfig::stan());
    }
    if flags.reg {
        warmup = warmup.with_metric_regularization(DiagonalMetricRegularization::Stan);
    }
    if flags.mu10 {
        warmup = warmup.with_stan_restart_reference(true);
    }
    Ok(RunConfig::new(WARMUP, nz(RETAINED), seed)
        .with_tuning(tuning)
        .with_warmup(warmup))
}

fn run(
    model: &Path,
    data: &Path,
    config_name: &str,
    seed: u64,
    out: &Path,
    threads: usize,
) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    let flags = Flags::parse(config_name)?;
    let data_json = fs::read_to_string(data)?;
    let target = StanTarget::load(model, &default_preload(), Some(&data_json), 1)?;
    let dimension = target.dimension();
    let starts = starts(dimension, seed);
    let config = config(flags, seed)?;
    let mass = DiagonalMass::identity(nz(dimension));
    let exact = config.worst_case_target_evaluations(nz(CHAINS))?;
    let admission = TargetEvaluationAdmissionLimit::new(nz(exact));
    let budget = TargetEvaluationBudget::new(nz(exact));
    preflight_chains_with_target_budget(&target, &starts, &mass, &config, admission, &budget)?;
    if target.calls() != 0 {
        return Err("preflight entered the target".into());
    }

    let begin = Instant::now();
    let result = sample_chains_with_target_budget(
        &target,
        &starts,
        &mass,
        &config,
        nz(threads),
        admission,
        &budget,
    );
    let wall = begin.elapsed().as_secs_f64();
    let sampled = match result {
        Ok(s) => s,
        Err(e) => {
            let payload = json!({
                "schema": "adaptation-parity-v1-cell",
                "config": config_name,
                "seed": seed, "status": "error", "error": e.to_string(),
                "wall_seconds": wall, "target_calls": target.calls(),
                "recoverable_failures": target.recoverable_failures(),
                "algorithm_revision": ALGORITHM_REVISION,
            });
            fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
            return Err(e.into());
        }
    };

    let max_depth = flags.max_depth();
    let chains = sampled
        .chains()
        .iter()
        .map(|chain| {
            let t = chain.telemetry();
            let retained = t.retained();
            let discarded = t.discarded();
            let diags = chain.diagnostics();
            let histogram = |range: std::ops::Range<usize>| {
                let mut depth_hist = vec![0usize; max_depth + 1];
                let mut level_hist = vec![0usize; MAX_REFINEMENT_LEVELS + 1];
                for d in &diags[range] {
                    depth_hist[d.depth().min(max_depth)] += 1;
                    if let Some(l) = d.selected_refinement_level() {
                        level_hist[l.min(MAX_REFINEMENT_LEVELS)] += 1;
                    }
                }
                (depth_hist, level_hist)
            };
            let (retained_depth, retained_level) = histogram(WARMUP..WARMUP + RETAINED);
            let (warmup_depth, warmup_level) = histogram(0..WARMUP);
            let searches: Vec<_> = t
                .step_searches()
                .iter()
                .map(|s| {
                    json!({
                        "reason": format!("{:?}", s.reason()),
                        "initial_step": s.search().initial_step(),
                        "selected_step": s.search().selected_step(),
                        "steps": s.search().steps(),
                        "target_calls": s.search().target_calls(),
                    })
                })
                .collect();
            let updates: Vec<_> = t
                .metric_updates()
                .iter()
                .map(|u| {
                    json!({
                        "window_index": u.window_index(),
                        "transition": u.transition(),
                        "outcome": format!("{:?}", u.outcome()),
                        "step_before": u.step_before(),
                        "step_after_search": u.step_after_search(),
                        "step_after_restart": u.step_after_restart(),
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
                "warmup_maximum_depth_stops": discarded.maximum_depth_stops(),
                "final_step_size": chain.metadata().tuning().step_size(),
                "final_max_error": chain.metadata().tuning().max_error(),
                "mass_diagonal": chain.metadata().mass_diagonal(),
                "retained_depth_histogram": retained_depth,
                "retained_refinement_level_histogram": retained_level,
                "warmup_depth_histogram": warmup_depth,
                "warmup_refinement_level_histogram": warmup_level,
                "step_searches": searches,
                "metric_updates": updates,
            })
        })
        .collect::<Vec<_>>();

    // owalnuts::diagnostics on the unconstrained coordinates.
    let columns: Vec<Vec<Vec<f64>>> = (0..dimension)
        .map(|p| {
            sampled
                .chains()
                .iter()
                .map(|chain| (0..RETAINED).map(|i| chain.sample(i).unwrap()[p]).collect())
                .collect()
        })
        .collect();
    let rust_diagnostics: Vec<_> = columns
        .iter()
        .map(|per_chain| {
            let refs: Vec<&[f64]> = per_chain.iter().map(Vec::as_slice).collect();
            json!({"ess_bulk": ess_bulk(&refs), "ess_tail": ess_tail(&refs), "rhat": rhat(&refs)})
        })
        .collect();
    let min_bulk = rust_diagnostics
        .iter()
        .map(|d| d["ess_bulk"].as_f64().unwrap_or(f64::NAN))
        .fold(f64::INFINITY, f64::min);
    let max_rhat = rust_diagnostics
        .iter()
        .map(|d| d["rhat"].as_f64().unwrap_or(f64::NAN))
        .fold(f64::NEG_INFINITY, f64::max);

    let payload = json!({
        "schema": "adaptation-parity-v1-cell",
        "config": config_name,
        "flags": format!("{flags:?}"),
        "status": "ok",
        "seed": seed,
        "model_library": model.display().to_string(),
        "model_info": target.info(),
        "dimension": dimension,
        "chains": CHAINS, "warmup": WARMUP, "retained": RETAINED, "threads": threads,
        "starts": starts,
        "tuning": {"step_size": flags.step_size(), "max_depth": max_depth, "min_micro_steps": MIN_MICRO_STEPS,
                   "max_refinement_levels": MAX_REFINEMENT_LEVELS, "max_error": MAX_ERROR,
                   "divergence_threshold": 1000.0},
        "warmup_config": {"mode": "dual_averaging", "target_accept": TARGET_ACCEPT, "mass_adaptation": true,
                          "acceptance_statistic": if flags.traj { "mean_trajectory" } else { "current_coarse_endpoint" },
                          "initial_step_search": if flags.init { "stan" } else { "none" },
                          "metric_regularization": if flags.reg { "stan" } else { "toward_unit" },
                          "restart_reference": if flags.mu10 { "ln(10h)" } else { "ln(h)" }},
        "constructor_admission_bound": exact,
        "wall_seconds": wall,
        "target_calls_total": target.calls(),
        "recoverable_failures_total": target.recoverable_failures(),
        "rust_diagnostics_unconstrained": rust_diagnostics,
        "rust_min_bulk_ess": min_bulk,
        "rust_max_rhat": max_rhat,
        "rust_min_bulk_ess_per_gradient": min_bulk / target.calls() as f64,
        "chains_data": chains,
        "algorithm_revision": ALGORITHM_REVISION,
    });
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    eprintln!(
        "{config_name} seed {seed}: wall {wall:.3}s, calls {}, rust min bulk ESS {min_bulk:.0}, div {}",
        target.calls(),
        sampled.chains().iter().map(|c| c.telemetry().retained().divergences()).sum::<usize>()
    );
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [model, data, config, seed, out, rest @ ..] => {
            let threads = rest.first().map_or(Ok(CHAINS), |t| t.parse::<usize>());
            match (seed.parse::<u64>(), threads) {
                (Ok(s), Ok(t)) => run(Path::new(model), Path::new(data), config, s, Path::new(out), t),
                _ => Err("seed and threads must be integers".into()),
            }
        }
        _ => Err("usage: <model.so> <data.json> <config> <seed> <out.json> [threads]".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
