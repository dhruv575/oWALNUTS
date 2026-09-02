//! oWALNUTS arms of the posteriordb benchmark: one (model, arm, seed) cell.
//!
//! Usage: `posteriordb-bench-v1 <model.so> <data.json> <da|paper> <seed> <out.json> [threads]`
//!
//! Loads the BridgeStan-compiled model through `owalnuts_bridgestan::StanTarget`,
//! draws four uniform(-2, 2) unconstrained starts from a seed-derived RNG (the
//! CmdStan default initialisation rule), runs 1,000 warmup + 1,000 retained
//! transitions on four parallel chains with the Python-package default kernel
//! tuning, and writes unconstrained draws, per-chain work/health counters and
//! the sampler-call wall time to JSON. Nothing is tuned per model.
#![forbid(unsafe_code)]

use owalnuts::walnutpie::{
    Target,
    ALGORITHM_REVISION, DiagonalMass, KernelTuning, PaperAdaptationConfig, RunConfig,
    TargetEvaluationAdmissionLimit, TargetEvaluationBudget, WarmupConfig,
    preflight_chains_with_target_budget, sample_chains_with_target_budget,
};
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use rand::{Rng, SeedableRng, rngs::SmallRng};
use serde_json::json;
use std::{env, error::Error, fs, num::NonZeroUsize, path::Path, time::Instant};

const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;
// Python-package `Tuning()` defaults (integrations/python/python/owalnuts).
const STEP_SIZE: f64 = 0.1;
const MAX_DEPTH: usize = 8;
const MIN_MICRO_STEPS: usize = 1;
const MAX_REFINEMENT_LEVELS: usize = 4;
const MAX_ERROR: f64 = 1.0;
const TARGET_ACCEPT: f64 = 0.8;

fn nz(n: usize) -> NonZeroUsize {
    NonZeroUsize::new(n).expect("nonzero")
}

fn starts(dimension: usize, seed: u64) -> Vec<Vec<f64>> {
    let mut rng = SmallRng::seed_from_u64(seed ^ 0x5eed_0000_0000);
    (0..CHAINS)
        .map(|_| (0..dimension).map(|_| rng.random_range(-2.0..2.0)).collect())
        .collect()
}

fn config(arm: &str, seed: u64) -> Result<RunConfig, Box<dyn Error>> {
    let tuning = KernelTuning::new(
        STEP_SIZE,
        nz(MAX_DEPTH),
        nz(MIN_MICRO_STEPS),
        nz(MAX_REFINEMENT_LEVELS),
        MAX_ERROR,
    )?;
    let warmup = WarmupConfig::new(TARGET_ACCEPT)?.with_mass_adaptation(true);
    let warmup = match arm {
        "da" => warmup,
        "paper" => warmup.with_paper_adaptation(PaperAdaptationConfig::default()),
        other => return Err(format!("unknown arm {other:?} (expected da|paper)").into()),
    };
    Ok(RunConfig::new(WARMUP, nz(RETAINED), seed)
        .with_tuning(tuning)
        .with_warmup(warmup))
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
    // One library copy per chain thread: the recommended (non-STAN_THREADS)
    // BridgeStan build has a single global autodiff stack per loaded module.
    // See artifacts/wall-gap/README.md (deviation from the v1 build).
    let target = ReplicatedStanTarget::load(model, &default_preload(), Some(&data_json), 1, threads)?;
    let dimension = target.dimension();
    let starts = starts(dimension, seed);
    let config = config(arm, seed)?;
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
                "schema": "posteriordb-bench-v1-cell",
                "sampler": format!("owalnuts-{arm}"),
                "seed": seed, "status": "error", "error": e.to_string(),
                "wall_seconds": wall, "target_calls": target.calls(),
                "recoverable_failures": target.recoverable_failures(),
                "algorithm_revision": ALGORITHM_REVISION,
            });
            fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
            return Err(e.into());
        }
    };

    let chains = sampled
        .chains()
        .iter()
        .map(|chain| {
            let t = chain.telemetry();
            let retained = t.retained();
            let discarded = t.discarded();
            let diags = &chain.diagnostics()[WARMUP..];
            let mut depth_hist = vec![0usize; MAX_DEPTH + 1];
            let mut level_hist = vec![0usize; MAX_REFINEMENT_LEVELS + 1];
            for d in diags {
                depth_hist[d.depth().min(MAX_DEPTH)] += 1;
                if let Some(l) = d.selected_refinement_level() {
                    level_hist[l.min(MAX_REFINEMENT_LEVELS)] += 1;
                }
            }
            let paper: Vec<_> = t
                .paper_adaptation_updates()
                .iter()
                .map(|u| {
                    json!({
                        "transition": u.transition(),
                        "window_index": u.window_index(),
                        "orbits": u.orbits(),
                        "inflation_quantile": u.inflation_quantile(),
                        "max_error_before": u.max_error_before(),
                        "max_error_after": u.max_error_after(),
                        "unrefined_fraction_mean": u.unrefined_fraction_mean(),
                        "step_before": u.step_before(),
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
                "final_step_size": chain.metadata().tuning().step_size(),
                "final_max_error": chain.metadata().tuning().max_error(),
                "mass_diagonal": chain.metadata().mass_diagonal(),
                "retained_depth_histogram": depth_hist,
                "retained_refinement_level_histogram": level_hist,
                "paper_adaptation_updates": paper,
            })
        })
        .collect::<Vec<_>>();
    let payload = json!({
        "schema": "posteriordb-bench-v1-cell",
        "sampler": format!("owalnuts-{arm}"),
        "status": "ok",
        "seed": seed,
        "model_library": model.display().to_string(),
        "model_info": target.info(),
        "threading": format!("{:?}", target.threading()), "replicas": target.replicas(),
        "dimension": dimension,
        "chains": CHAINS, "warmup": WARMUP, "retained": RETAINED, "threads": threads,
        "starts": starts,
        "tuning": {"step_size": STEP_SIZE, "max_depth": MAX_DEPTH, "min_micro_steps": MIN_MICRO_STEPS,
                   "max_refinement_levels": MAX_REFINEMENT_LEVELS, "max_error": MAX_ERROR,
                   "divergence_threshold": 1000.0},
        "warmup_config": if arm == "paper" {
            json!({"mode": "appendix_c", "target_accept_unused": TARGET_ACCEPT, "global_energy_bound": 2.0,
                   "quantile_probability": 0.95, "unrefined_fraction_target": 0.8, "mass_adaptation": true})
        } else {
            json!({"mode": "dual_averaging", "target_accept": TARGET_ACCEPT, "mass_adaptation": true})
        },
        "constructor_admission_bound": exact,
        "timing_estimand": "wall around sample_chains_with_target_budget (warmup + retained, four parallel chains)",
        "wall_seconds": wall,
        "target_calls_total": target.calls(),
        "recoverable_failures_total": target.recoverable_failures(),
        "chains_data": chains,
        "algorithm_revision": ALGORITHM_REVISION,
    });
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    eprintln!(
        "{arm} seed {seed}: wall {wall:.3}s, calls {}, div {}",
        target.calls(),
        sampled.chains().iter().map(|c| c.telemetry().retained().divergences()).sum::<usize>()
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
        _ => Err("usage: <model.so> <data.json> <da|paper> <seed> <out.json> [threads]".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
