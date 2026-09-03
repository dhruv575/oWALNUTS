//! oWALNUTS cell of `STUDIES/chain_rescue_v1` (WP33): the v5 posteriordb
//! protocol with the chain-rescue arms.
//!
//! Usage: `chain-rescue-v1 <model.so> <data.json> <da|restart|pool> <seed> <out.json> [threads]`
//!
//! Identical to `STUDIES/posteriordb_bench_v5/src/main.rs` except for the arm
//! switch (`src/arms.rs`) and the per-chain `chain_rescues` records in the
//! JSON: four `Init::uniform()` starts, 1,000 warmup + 1,000 retained
//! transitions, four parallel chains, `Tuning::default()`,
//! `Metric::diagonal()`, `Limits::admit_worst_case()`.
#![forbid(unsafe_code)]

mod arms;

use owalnuts::sampler::{DEFAULT_U_TURN_RULE, Init, Limits, Metric, Sampler, Target, Tuning, uniform_starts};
use owalnuts::walnutpie::ALGORITHM_REVISION;
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::json;
use std::{env, error::Error, fs, path::Path, time::Instant};

const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;

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
    let sampler = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .seed(seed)
        .threads(threads)
        .metric(Metric::diagonal())
        .adaptation(arms::adaptation(arm)?)
        .tuning(tuning)
        .limits(Limits::new().admit_worst_case());
    let worst_case = sampler.worst_case_target_evaluations(CHAINS)?;
    let (radius, max_attempts) = match Init::uniform() {
        Init::Uniform { radius, max_attempts } => (radius, max_attempts),
        _ => unreachable!(),
    };
    let starts = match uniform_starts(&target, CHAINS, seed, radius, max_attempts) {
        Ok(s) => s,
        Err(e) => {
            let payload = json!({
                "schema": "chain-rescue-v1-cell", "arm": arm, "seed": seed, "status": "error",
                "stage": "init", "error": e.to_string(), "wall_seconds": 0.0,
                "target_calls": target.calls(), "algorithm_revision": ALGORITHM_REVISION,
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
                "schema": "chain-rescue-v1-cell", "arm": arm, "seed": seed, "status": "error",
                "stage": "sample", "error": e.to_string(), "wall_seconds": wall,
                "target_calls": target.calls(), "start_search_calls": start_search_calls,
                "algorithm_revision": ALGORITHM_REVISION,
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
            let diags = &chain.diagnostics()[WARMUP..];
            let mut depth_hist = vec![0usize; max_depth + 1];
            for d in diags {
                depth_hist[d.depth().min(max_depth)] += 1;
            }
            json!({
                "samples": (0..RETAINED).map(|i| chain.sample(i).unwrap()).collect::<Vec<_>>(),
                "divergences": retained.divergences(),
                "maximum_depth_stops": retained.maximum_depth_stops(),
                "refinement_exhaustions": retained.refinement_exhaustion_stops(),
                "retained_target_calls": retained.target_calls_total(),
                "warmup_target_calls": discarded.target_calls_total(),
                "warmup_divergences": discarded.divergences(),
                "final_step_size": chain.metadata().tuning().step_size(),
                "mass_diagonal": chain.metadata().mass_diagonal(),
                "retained_depth_histogram": depth_hist,
                "chain_rescues": arms::rescues_json(t),
            })
        })
        .collect::<Vec<_>>();
    let payload = json!({
        "schema": "chain-rescue-v1-cell",
        "arm": arm, "status": "ok", "seed": seed,
        "model_library": model.display().to_string(),
        "dimension": dimension,
        "chains": CHAINS, "warmup": WARMUP, "retained": RETAINED, "threads": threads,
        "init": {"rule": "sampler::Init::uniform()", "radius": radius, "max_attempts": max_attempts,
                 "start_search_calls": start_search_calls},
        "starts": starts,
        "tuning": {"step_size": kernel.step_size(), "max_depth": max_depth,
                   "max_refinement_levels": kernel.max_refinement_levels(), "max_error": kernel.max_error(),
                   "u_turn": format!("{:?}", kernel.options().u_turn),
                   "default_u_turn_rule": format!("{DEFAULT_U_TURN_RULE:?}"),
                   "source": "owalnuts::sampler::Tuning::default()"},
        "warmup_config": arms::warmup_json(arm),
        "constructor_admission_bound": worst_case,
        "wall_seconds": wall,
        "target_calls_total": target.calls(),
        "chains_data": chains,
        "algorithm_revision": posterior.algorithm_revision(),
    });
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    eprintln!(
        "{arm} seed {seed}: wall {wall:.3}s, calls {}, rescued {}",
        target.calls(),
        posterior
            .telemetry()
            .flat_map(|t| t.chain_rescues().iter())
            .filter(|u| matches!(u.outcome(), owalnuts::walnutpie::ChainRescueOutcome::Restarted { .. }))
            .count()
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
        _ => Err("usage: <model.so> <data.json> <da|restart|pool> <seed> <out.json> [threads]".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
