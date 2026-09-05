//! oWALNUTS arms of the reverse-coarser policy study: one (model, arm, seed) cell.
//!
//! The posteriordb v5 harness (`STUDIES/posteriordb_bench_v5/src/main.rs`)
//! with the arm selecting `Tuning::reverse_coarser_policy` (see `arms.rs`),
//! plus per-chain refinement accounting from the retained telemetry: built
//! leaves by refinement level, reverse-coarser stops, rejections and
//! continuations, zero-weight leaves, the stop-cause and depth histograms.
//!
//! Usage: `posteriordb-cell <model.so> <data.json> <arm> <seed> <out.json> [threads]`
//!
//! Loads the BridgeStan-compiled model (built without `STAN_THREADS`) through
//! `owalnuts_bridgestan::ReplicatedStanTarget` (one library copy per chain
//! thread), draws four Stan-style starts with `owalnuts::sampler::Init::uniform()`
//! and runs 1,000 warmup + 1,000 retained transitions on four parallel chains
//! (`Metric::diagonal()`, `Limits::admit_worst_case()`). Writes unconstrained
//! draws, per-chain work/health counters and the wall around `Sampler::run`
//! to JSON. Nothing is tuned per model.
#![forbid(unsafe_code)]

mod arms;

use arms::Arm;
use owalnuts::sampler::{Init, Limits, Metric, Sampler, Target, uniform_starts};
use owalnuts::walnutpie::{ALGORITHM_REVISION, StopReason};
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::json;
use std::{env, error::Error, fs, path::Path, time::Instant};

const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;
const ERROR_BINS: [f64; 8] = [0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 100.0, 1000.0];

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

fn run(
    model: &Path,
    data: &Path,
    arm_name: &str,
    seed: u64,
    out: &Path,
    threads: usize,
) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    let arm = Arm::parse(arm_name)?;
    let data_json = fs::read_to_string(data)?;
    let target =
        ReplicatedStanTarget::load(model, &default_preload(), Some(&data_json), 1, threads)?;
    let dimension = target.dimension();
    let tuning = arm.tuning();
    let kernel = tuning.to_kernel()?;
    let max_depth = kernel.max_depth();
    let max_levels = kernel.max_refinement_levels();
    let sampler = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .seed(seed)
        .threads(threads)
        .metric(Metric::diagonal())
        .adaptation(arm.adaptation())
        .tuning(tuning)
        .limits(Limits::new().admit_worst_case());
    let worst_case = sampler.worst_case_target_evaluations(CHAINS)?;

    let (radius, max_attempts) = match Init::uniform() {
        Init::Uniform {
            radius,
            max_attempts,
        } => (radius, max_attempts),
        _ => unreachable!(),
    };
    let starts = match uniform_starts(&target, CHAINS, seed, radius, max_attempts) {
        Ok(s) => s,
        Err(e) => {
            let payload = json!({
                "schema": "reverse-coarser-policy-v1-cell",
                "sampler": format!("owalnuts-{}", arm.name),
                "seed": seed, "status": "error", "stage": "init", "error": e.to_string(),
                "wall_seconds": 0.0, "target_calls": target.calls(),
                "algorithm_revision": ALGORITHM_REVISION,
            });
            fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
            return Err(e.into());
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
                "schema": "reverse-coarser-policy-v1-cell",
                "sampler": format!("owalnuts-{}", arm.name),
                "seed": seed, "status": "error", "stage": "sample", "error": e.to_string(),
                "wall_seconds": wall, "target_calls": target.calls(),
                "start_search_calls": start_search_calls,
                "algorithm_revision": ALGORITHM_REVISION,
            });
            fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
            return Err(e.into());
        }
    };
    let target_calls_total = target.calls();
    let recoverable_failures_total = target.recoverable_failures();

    let chains = posterior
        .chains()
        .iter()
        .map(|chain| {
            let t = chain.telemetry();
            let retained = t.retained();
            let discarded = t.discarded();
            let diags = &chain.diagnostics()[WARMUP..];
            let mut depth_hist = vec![0usize; max_depth + 1];
            let mut level_hist = vec![0usize; max_levels + 1];
            let mut stop_hist = serde_json::Map::new();
            let mut error_hist = vec![0usize; ERROR_BINS.len() + 1];
            let mut accept_sum = 0.0;
            let mut accept_n = 0usize;
            let mut orbit_states = 0usize;
            for d in diags {
                depth_hist[d.depth().min(max_depth)] += 1;
                if let Some(l) = d.selected_refinement_level() {
                    level_hist[l.min(max_levels)] += 1;
                }
                let name = stop_name(d.stop());
                *stop_hist.entry(name).or_insert(json!(0)) = json!(
                    stop_hist.get(name).and_then(|v| v.as_u64()).unwrap_or(0) + 1
                );
                let e = d.maximum_absolute_energy_error();
                let bin = ERROR_BINS.iter().position(|b| e <= *b).unwrap_or(ERROR_BINS.len());
                error_hist[bin] += 1;
                if let Some(a) = d.acceptance_statistic() {
                    accept_sum += a;
                    accept_n += 1;
                }
                orbit_states += d.orbit_states();
            }
            let samples: Vec<Vec<f64>> = (0..RETAINED)
                .map(|i| chain.sample(i).unwrap().to_vec())
                .collect();
            let mass = chain.metadata().mass_diagonal().to_vec();
            let h = chain.metadata().tuning().step_size();
            json!({
                "samples": samples,
                "divergences": retained.divergences(),
                "maximum_depth_stops": retained.maximum_depth_stops(),
                "invalid_stops": retained.invalid_evaluation_stops(),
                "recoverable_failures": retained.recoverable_target_failures(),
                "refinement_exhaustions": retained.refinement_exhaustion_stops(),
                "retained_target_calls": retained.target_calls_total(),
                "warmup_target_calls": discarded.target_calls_total(),
                "warmup_divergences": discarded.divergences(),
                "final_step_size": h,
                "final_max_error": chain.metadata().tuning().max_error(),
                "mass_diagonal": mass,
                "retained_depth_histogram": depth_hist,
                "retained_refinement_level_histogram": level_hist,
                "retained_stop_histogram": stop_hist,
                "retained_max_energy_error_histogram": {"bins_upper": ERROR_BINS, "counts": error_hist},
                "retained_mean_acceptance_statistic": if accept_n > 0 { accept_sum / accept_n as f64 } else { f64::NAN },
                "retained_orbit_states": orbit_states,
                "retained_work": {
                    "leaves_attempted": retained.leaves_attempted(),
                    "leaves_built": retained.leaves_built(),
                    "refinement_level_built": retained.refinement_level_built(),
                    "forward_refinement_attempts": retained.forward_refinement_attempts(),
                    "reverse_coarsening_attempts": retained.reverse_coarsening_attempts(),
                    "reverse_coarser_stops": retained.reverse_coarser_stops(),
                    "reverse_coarser_rejections": retained.reverse_coarser_rejections(),
                    "reverse_coarser_continuations": retained.reverse_coarser_continuations(),
                    "zero_weight_leaves": retained.zero_weight_leaves(),
                    "target_calls_forward": retained.target_calls_forward(),
                    "target_calls_reverse": retained.target_calls_reverse(),
                    "target_calls_initial": retained.target_calls_initial(),
                },
                "warmup_work": {
                    "leaves_built": discarded.leaves_built(),
                    "reverse_coarser_stops": discarded.reverse_coarser_stops(),
                    "reverse_coarser_rejections": discarded.reverse_coarser_rejections(),
                    "reverse_coarser_continuations": discarded.reverse_coarser_continuations(),
                    "zero_weight_leaves": discarded.zero_weight_leaves(),
                },
            })
        })
        .collect::<Vec<_>>();
    let payload = json!({
        "schema": "reverse-coarser-policy-v1-cell",
        "sampler": format!("owalnuts-{}", arm.name),
        "arm": arm.name,
        "status": "ok",
        "seed": seed,
        "model_library": model.display().to_string(),
        "model_info": target.info(),
        "threading": format!("{:?}", target.threading()), "replicas": target.replicas(),
        "dimension": dimension,
        "chains": CHAINS, "warmup": WARMUP, "retained": RETAINED, "threads": threads,
        "init": {"rule": "sampler::Init::uniform()", "radius": radius, "max_attempts": max_attempts,
                 "start_search_calls": start_search_calls},
        "starts": starts,
        "tuning": {"step_size": kernel.step_size(), "max_depth": max_depth,
                   "min_micro_steps": kernel.min_micro_steps(),
                   "max_refinement_levels": max_levels, "max_error": kernel.max_error(),
                   "divergence_threshold": kernel.divergence_threshold(),
                   "reverse_coarser_policy": format!("{:?}", kernel.reverse_coarser_policy()),
                   "u_turn": format!("{:?}", kernel.options().u_turn),
                   "exhaustion": format!("{:?}", kernel.options().exhaustion)},
        "warmup_config": arm.json(),
        "constructor_admission_bound": worst_case,
        "timing_estimand": "wall around sampler::Sampler::run (warmup + retained, four parallel chains; start search excluded)",
        "wall_seconds": wall,
        "target_calls_total": target_calls_total,
        "recoverable_failures_total": recoverable_failures_total,
        "chains_data": chains,
        "algorithm_revision": posterior.algorithm_revision(),
    });
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    eprintln!(
        "{} seed {seed}: wall {wall:.3}s, calls {target_calls_total}, div {}",
        arm.name,
        posterior
            .chains()
            .iter()
            .map(|c| c.telemetry().retained().divergences())
            .sum::<usize>()
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
        _ => Err("usage: <model.so> <data.json> <arm> <seed> <out.json> [threads]".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
