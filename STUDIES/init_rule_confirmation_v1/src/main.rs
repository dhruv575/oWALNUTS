//! WP52 `init_rule_confirmation_v1`: one (model, arm, seed) posteriordb cell.
//! Copied from the WP43 harness (`STUDIES/init_rule_v1/src/main.rs`). The
//! only changes: arm names `uniform` / `best_of_16`, the `median16` arm
//! dropped, and `Summary::chain_warnings` (WP44) recorded.
//!
//! Usage: `init-rule-confirmation-v1 <model.so> <data.json> <arm> <seed> <out.json> [threads]`
//!
//! Arms (the only thing that differs between them is how the four starts
//! are chosen; everything after the starts is `Sampler::run` at the shipped
//! defaults: `Tuning::default()`, `Metric::diagonal()`, `Adaptation::default()`
//! with no chain rescue, `Limits::admit_worst_case()`, 4 x 1,000 / 1,000):
//!
//! - `uniform`    = `Init::uniform()` via `uniform_starts` (uniform(-2, 2),
//!   up to 100 draws per chain until finite),
//! - `best_of_16` = `Init::best_of(16)` via `candidate_starts(.., 16, 100,
//!   StartSelection::HighestDensity)`.
//!
//! The starts are drawn here (identical to `Sampler::run_with_init`, which is
//! tested bit-for-bit in `tests/sampler_api.rs`) so that the start log
//! densities, the candidate pools and the init cost are recorded. For the
//! `uniform` arm the start log densities are measured afterwards with one
//! extra evaluation per chain; those measurement calls are subtracted from
//! `gradients_total`. Every init evaluation (rejected draws included) counts
//! in `gradients_total`.
#![forbid(unsafe_code)]

use owalnuts::diagnostics::Summary;
use owalnuts::sampler::{
    DEFAULT_CHAIN_RESCUE, DEFAULT_METRIC_REGULARIZATION, DEFAULT_U_TURN_RULE,
    DEFAULT_WARMUP_EXHAUSTION, Init, Limits, Metric, Sampler, StartSelection, Target, Tuning,
    candidate_starts, uniform_starts,
};
use owalnuts::walnutpie::ALGORITHM_REVISION;
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::json;
use std::{env, error::Error, fs, path::Path, time::Instant};

const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;
const CANDIDATES: usize = 16;

struct Chosen {
    starts: Vec<Vec<f64>>,
    start_log_densities: Vec<f64>,
    candidate_log_densities: Vec<Vec<f64>>,
    chosen: Vec<usize>,
    init_evaluations: usize,
    measurement_calls: usize,
    rule: serde_json::Value,
}

fn choose(target: &ReplicatedStanTarget, arm: &str, seed: u64) -> Result<Chosen, Box<dyn Error>> {
    let before = target.calls();
    match arm {
        "uniform" => {
            let Init::Uniform {
                radius,
                max_attempts,
            } = Init::uniform()
            else {
                unreachable!("Init::uniform() is Init::Uniform")
            };
            let starts = uniform_starts(target, CHAINS, seed, radius, max_attempts)?;
            let init_evaluations = target.calls() - before;
            let mut gradient = vec![0.0; target.dimension()];
            let mut densities = Vec::with_capacity(CHAINS);
            let measure_before = target.calls();
            for start in &starts {
                densities.push(
                    target
                        .log_density_gradient(start, &mut gradient)
                        .map_err(|e| format!("start re-evaluation failed: {e:?}"))?,
                );
            }
            let measurement_calls = target.calls() - measure_before;
            Ok(Chosen {
                starts,
                start_log_densities: densities.clone(),
                candidate_log_densities: densities.iter().map(|d| vec![*d]).collect(),
                chosen: vec![0; CHAINS],
                init_evaluations,
                measurement_calls,
                rule: json!({"rule": "sampler::Init::uniform()", "radius": radius,
                             "max_attempts": max_attempts, "candidates": 1}),
            })
        }
        "best_of_16" => {
            let init = Init::best_of(CANDIDATES);
            let Init::Candidates {
                radius,
                candidates,
                max_attempts,
                selection,
            } = init
            else {
                unreachable!("Init::best_of / median_of are Init::Candidates")
            };
            let report = candidate_starts(
                target,
                CHAINS,
                seed,
                radius,
                candidates,
                max_attempts,
                selection,
            )?;
            let init_evaluations = target.calls() - before;
            assert_eq!(init_evaluations, report.evaluations.iter().sum::<usize>());
            Ok(Chosen {
                starts: report.starts,
                start_log_densities: report.start_log_densities,
                candidate_log_densities: report.candidate_log_densities,
                chosen: report.chosen,
                init_evaluations,
                measurement_calls: 0,
                rule: json!({"rule": if selection == StartSelection::HighestDensity {
                                "sampler::Init::best_of(16)" } else { "sampler::Init::median_of(16)" },
                             "radius": radius, "candidates": candidates,
                             "max_attempts": max_attempts,
                             "selection": format!("{selection:?}"),
                             "evaluations_per_chain": report.evaluations}),
            })
        }
        other => Err(format!("unknown arm {other:?} (expected uniform, best_of_16)").into()),
    }
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
    let target =
        ReplicatedStanTarget::load(model, &default_preload(), Some(&data_json), 1, threads)?;
    let dimension = target.dimension();
    let tuning = Tuning::default();
    let kernel = tuning.to_kernel()?;
    let sampler = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .seed(seed)
        .threads(threads)
        .metric(Metric::diagonal())
        .tuning(tuning)
        .limits(Limits::new().admit_worst_case());

    let chosen = match choose(&target, arm, seed) {
        Ok(c) => c,
        Err(e) => {
            let payload = json!({
                "schema": "init-rule-confirmation-v1-cell", "arm": arm, "seed": seed,
                "status": "error", "stage": "init", "error": e.to_string(),
                "wall_seconds": 0.0, "target_calls": target.calls(),
                "algorithm_revision": ALGORITHM_REVISION,
            });
            fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
            return Err(e);
        }
    };
    let calls_before_run = target.calls();

    let begin = Instant::now();
    let result = sampler.run(&target, &chosen.starts);
    let wall = begin.elapsed().as_secs_f64();
    let posterior = match result {
        Ok(p) => p,
        Err(e) => {
            let payload = json!({
                "schema": "init-rule-confirmation-v1-cell", "arm": arm, "seed": seed,
                "status": "error", "stage": "sample", "error": e.to_string(),
                "wall_seconds": wall, "target_calls": target.calls(),
                "init_evaluations": chosen.init_evaluations,
                "starts": chosen.starts, "start_log_densities": chosen.start_log_densities,
                "algorithm_revision": ALGORITHM_REVISION,
            });
            fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
            return Err(e.into());
        }
    };
    let run_calls = target.calls() - calls_before_run;
    let gradients_total = target.calls() - chosen.measurement_calls;

    // Leave-one-chain-out R-hat over the unconstrained coordinates.
    let summary = Summary::from_chains(posterior.chains(), None)?;
    let disagreement = summary.chain_disagreement.as_ref().map(|d| {
        json!({"max_rhat": d.max_rhat, "max_rhat_without": d.max_rhat_without,
               "chains": d.chains})
    });
    let max_unconstrained_rhat = summary
        .parameters
        .iter()
        .map(|p| p.rhat)
        .fold(f64::NAN, f64::max);

    let chains = posterior
        .chains()
        .iter()
        .map(|chain| {
            let t = chain.telemetry();
            let retained = t.retained();
            let discarded = t.discarded();
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
                "mass_diagonal": chain.metadata().mass_diagonal(),
                "chain_rescues": t.chain_rescues().len(),
            })
        })
        .collect::<Vec<_>>();
    let payload = json!({
        "schema": "init-rule-confirmation-v1-cell",
        "arm": arm,
        "status": "ok",
        "seed": seed,
        "model_library": model.display().to_string(),
        "model_info": target.info(),
        "replicas": target.replicas(),
        "dimension": dimension,
        "chains": CHAINS, "warmup": WARMUP, "retained": RETAINED, "threads": threads,
        "init": chosen.rule,
        "init_evaluations": chosen.init_evaluations,
        "start_log_density_measurement_calls": chosen.measurement_calls,
        "starts": chosen.starts,
        "start_log_densities": chosen.start_log_densities,
        "candidate_log_densities": chosen.candidate_log_densities,
        "chosen_candidate": chosen.chosen,
        "tuning": {"step_size": kernel.step_size(), "max_depth": kernel.max_depth(),
                   "max_refinement_levels": kernel.max_refinement_levels(),
                   "max_error": kernel.max_error(),
                   "u_turn": format!("{:?}", kernel.options().u_turn),
                   "default_u_turn_rule": format!("{DEFAULT_U_TURN_RULE:?}"),
                   "warmup_exhaustion_rule": format!("{DEFAULT_WARMUP_EXHAUSTION:?}"),
                   "metric_regularization": format!("{DEFAULT_METRIC_REGULARIZATION:?}"),
                   "chain_rescue": format!("{DEFAULT_CHAIN_RESCUE:?}"),
                   "source": "Tuning::default(), Adaptation::default(), Metric::diagonal()"},
        "wall_seconds": wall,
        "timing_estimand": "wall around Sampler::run; init excluded; contended shared machine",
        "run_target_calls": run_calls,
        "gradients_total": gradients_total,
        "chain_disagreement": disagreement,
        "chain_warnings": summary.chain_warnings.iter().map(|w| format!("{w:?}")).collect::<Vec<_>>(),
        "chain_warning_chains": summary.chain_warnings.iter().map(|w| w.chain()).collect::<Vec<_>>(),
        "max_unconstrained_rhat": max_unconstrained_rhat,
        "chains_data": chains,
        "algorithm_revision": posterior.algorithm_revision(),
    });
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    eprintln!(
        "{arm} seed {seed}: wall {wall:.2}s, gradients {gradients_total}, init {}, \
         start logp {:?}, disagreeing {:?}",
        chosen.init_evaluations,
        chosen
            .start_log_densities
            .iter()
            .map(|d| format!("{d:.1}"))
            .collect::<Vec<_>>(),
        summary.chain_disagreement.as_ref().map(|d| d.chains.clone())
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
        _ => Err("usage: <model.so> <data.json> <uniform|best_of_16> <seed> <out.json> [threads]".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
