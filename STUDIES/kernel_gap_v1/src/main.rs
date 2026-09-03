//! Kernel-gap study driver (`STUDIES/kernel_gap_v1`).
//!
//! Usage: `kernel-gap-v1 <model.so> <data.json> <cmdstan.json> <seed> <arm> <out.json> [draws]`
//!
//! Reads CmdStan's adapted step, inverse metric and first retained draw per
//! chain (`cmdstan_reference.py`), and runs four chains of `draws`
//! transitions from those starts with a fixed kernel at exactly those
//! values: either the oWALNUTS kernel through the sampler API (no warmup,
//! fixed diagonal metric, opt-in kernel options selected by `arm`) or the
//! reference NUTS of `examples/support/reference_nuts.rs`. Writes
//! per-transition orbit statistics (gradients, leaves, depth, stop cause,
//! orbit size, selected and initial state index, refinement level) per
//! chain, per-chain work totals, and per-coordinate bulk ESS over the four
//! chains.
#![forbid(unsafe_code)]

#[path = "../../../examples/support/reference_nuts.rs"]
mod reference_nuts;

use owalnuts::diagnostics::{ess_bulk, ess_tail, rhat};
use owalnuts::sampler::{Adaptation, Limits, Metric, Sampler, Target, Tuning};
use owalnuts::walnutpie::{ExhaustionRule, KernelOptions, StopReason, UTurnRule};
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::{Value, json};
use std::{env, error::Error, fs, path::Path, time::Instant};

const CHAINS: usize = 4;
const MAX_DEPTH: usize = 10;

#[derive(Clone, Copy)]
struct WalnutsArm {
    levels: usize,
    max_error: f64,
    options: KernelOptions,
}

enum Arm {
    Reference,
    Walnuts(WalnutsArm),
}

/// `nuts-ref`, or `walnuts` followed by `+`-joined parts: `cross`, `rhosum`
/// (U-turn rule), `levels1` (one refinement level with Stan's exhaustion
/// rule: NUTS inside the oWALNUTS machinery), `delta1000` (refinement never
/// engages), `accept` (`AcceptUnlessDivergent` at four levels).
fn arm(name: &str) -> Result<Arm, Box<dyn Error>> {
    if name == "nuts-ref" {
        return Ok(Arm::Reference);
    }
    let mut parts = name.split('+');
    if parts.next() != Some("walnuts") {
        return Err(format!("unknown arm {name:?}").into());
    }
    let mut arm = WalnutsArm {
        levels: 4,
        max_error: 1.0,
        options: KernelOptions::default(),
    };
    for part in parts {
        match part {
            "cross" => arm.options.u_turn = UTurnRule::EndpointsWithCross,
            "rhosum" => arm.options.u_turn = UTurnRule::MomentumSum,
            "levels1" => {
                arm.levels = 1;
                arm.options.exhaustion = ExhaustionRule::AcceptUnlessDivergent;
            }
            "accept" => arm.options.exhaustion = ExhaustionRule::AcceptUnlessDivergent,
            "delta1000" => arm.max_error = 1000.0,
            other => return Err(format!("unknown arm part {other:?}").into()),
        }
    }
    Ok(Arm::Walnuts(arm))
}

fn stop_name(stop: StopReason) -> &'static str {
    match stop {
        StopReason::MaximumDepth => "max_depth",
        StopReason::OuterUTurn => "outer_uturn",
        StopReason::RecursiveUTurn => "recursive_uturn",
        StopReason::RefinementExhausted => "exhausted",
        StopReason::ReverseCoarserAccepted => "reverse_coarser",
        StopReason::InvalidEvaluation => "invalid",
        _ => "other",
    }
}

struct ChainRun {
    samples: Vec<f64>,
    trace: Value,
    totals: Value,
}

fn run_walnuts<T: Target>(
    target: &T,
    arm: WalnutsArm,
    step: f64,
    inv_metric: &[f64],
    start: &[f64],
    draws: usize,
    seed: u64,
) -> Result<ChainRun, Box<dyn Error>> {
    let mass: Vec<f64> = inv_metric.iter().map(|v| v.recip()).collect();
    let sampler = Sampler::new()
        .warmup(0)
        .draws(draws)
        .chains(1)
        .seed(seed)
        .threads(1)
        .metric(Metric::fixed_diagonal(mass))
        .adaptation(Adaptation::None)
        .tuning(
            Tuning::new()
                .step_size(step)
                .max_depth(MAX_DEPTH)
                .max_refinement_levels(arm.levels)
                .max_error(arm.max_error)
                .kernel_options(arm.options),
        )
        .cache_initial_evaluation(true)
        .limits(Limits::new().admit_worst_case());
    let posterior = sampler.run(target, std::slice::from_ref(&start.to_vec()))?;
    let chain = &posterior.chains()[0];
    let d = chain.diagnostics();
    let r = chain.telemetry().retained();
    let trace = json!({
        "gradients": d.iter().map(|x| x.target_evaluations()).collect::<Vec<_>>(),
        "leaves": d.iter().map(|x| x.leaves_built()).collect::<Vec<_>>(),
        "depth": d.iter().map(|x| x.depth()).collect::<Vec<_>>(),
        "stop": d.iter().map(|x| stop_name(x.stop())).collect::<Vec<_>>(),
        "orbit_states": d.iter().map(|x| x.orbit_states()).collect::<Vec<_>>(),
        "selected_index": d.iter().map(|x| x.selected_index()).collect::<Vec<_>>(),
        "initial_index": d.iter().map(|x| x.initial_index()).collect::<Vec<_>>(),
        "selected_level": d.iter().map(|x| x.selected_refinement_level()).collect::<Vec<_>>(),
        "refinement_attempts": d.iter().map(|x| x.refinement_attempts()).collect::<Vec<_>>(),
        "reverse_coarser_rejections": d.iter().map(|x| x.reverse_coarser_rejections()).collect::<Vec<_>>(),
        "max_abs_energy_error": d.iter().map(|x| x.maximum_absolute_energy_error()).collect::<Vec<_>>(),
        "divergent": d.iter().map(|x| x.divergent()).collect::<Vec<_>>(),
    });
    let totals = json!({
        "transitions": r.transitions(),
        "target_calls_initial": r.target_calls_initial(),
        "target_calls_forward": r.target_calls_forward(),
        "target_calls_reverse": r.target_calls_reverse(),
        "target_calls_total": r.target_calls_total(),
        "accepted_forward_micro_steps": r.accepted_forward_micro_steps(),
        "refinement_level_built": r.refinement_level_built(),
        "leaves_attempted": r.leaves_attempted(),
        "leaves_built": r.leaves_built(),
        "forward_refinement_attempts": r.forward_refinement_attempts(),
        "forward_micro_steps_executed": r.forward_micro_steps_executed(),
        "reverse_coarsening_attempts": r.reverse_coarsening_attempts(),
        "reverse_micro_steps_executed": r.reverse_micro_steps_executed(),
        "reverse_coarser_rejections": r.reverse_coarser_rejections(),
        "divergences": r.divergences(),
        "maximum_depth_stops": r.maximum_depth_stops(),
    });
    Ok(ChainRun {
        samples: posterior.chain_draws(0).ok_or("chain draws")?.to_vec(),
        trace,
        totals,
    })
}

fn run_reference<T: Target>(
    target: &T,
    step: f64,
    inv_metric: &[f64],
    start: &[f64],
    draws: usize,
    seed: u64,
) -> ChainRun {
    let (samples, stats) = reference_nuts::run_chain(
        target,
        step,
        inv_metric.to_vec(),
        start,
        draws,
        MAX_DEPTH,
        seed,
    );
    let gradients: usize = stats.iter().map(|s| s.leapfrogs).sum();
    let trace = json!({
        "gradients": stats.iter().map(|s| s.leapfrogs).collect::<Vec<_>>(),
        "leaves": stats.iter().map(|s| s.leapfrogs).collect::<Vec<_>>(),
        "depth": stats.iter().map(|s| s.depth).collect::<Vec<_>>(),
        "stop": stats.iter().map(|s| if s.divergent { "divergent" } else if s.max_depth { "max_depth" } else { "uturn" }).collect::<Vec<_>>(),
        "orbit_states": stats.iter().map(|s| s.orbit_states).collect::<Vec<_>>(),
        "selected_index": stats.iter().map(|s| s.selected_index).collect::<Vec<_>>(),
        "initial_index": stats.iter().map(|s| s.initial_index).collect::<Vec<_>>(),
        "divergent": stats.iter().map(|s| s.divergent).collect::<Vec<_>>(),
    });
    let totals = json!({
        "transitions": stats.len(),
        "target_calls_initial": 0,
        "target_calls_forward": gradients,
        "target_calls_reverse": 0,
        "target_calls_total": gradients,
        "accepted_forward_micro_steps": stats.iter().map(|s| s.orbit_states - 1).sum::<usize>(),
        "refinement_level_built": [stats.iter().map(|s| s.orbit_states - 1).sum::<usize>()],
        "leaves_attempted": gradients,
        "leaves_built": gradients,
        "divergences": stats.iter().filter(|s| s.divergent).count(),
        "maximum_depth_stops": stats.iter().filter(|s| s.max_depth).count(),
    });
    ChainRun {
        samples,
        trace,
        totals,
    }
}

fn run(
    model: &Path,
    data: &Path,
    cmdstan: &Path,
    seed: u64,
    name: &str,
    out: &Path,
    draws: usize,
) -> Result<(), Box<dyn Error>> {
    let arm = arm(name)?;
    let data_json = fs::read_to_string(data)?;
    let reference: Value = serde_json::from_str(&fs::read_to_string(cmdstan)?)?;
    let target =
        ReplicatedStanTarget::load(model, &default_preload(), Some(&data_json), 1, CHAINS)?;
    let dimension = target.dimension();
    let chains_in: Vec<(f64, Vec<f64>, Vec<f64>)> = reference["chains"]
        .as_array()
        .ok_or("cmdstan chains")?
        .iter()
        .take(CHAINS)
        .map(|c| {
            let f = |k: &str| -> Vec<f64> {
                c[k].as_array()
                    .unwrap()
                    .iter()
                    .map(|v| v.as_f64().unwrap())
                    .collect()
            };
            (
                c["step_size"].as_f64().unwrap(),
                f("inv_metric"),
                f("start_unconstrained"),
            )
        })
        .collect();
    if chains_in.len() != CHAINS || chains_in.iter().any(|c| c.1.len() != dimension) {
        return Err("cmdstan reference does not match the model".into());
    }
    let begin = Instant::now();
    let runs: Vec<ChainRun> = std::thread::scope(|scope| {
        let handles: Vec<_> = chains_in
            .iter()
            .enumerate()
            .map(|(c, (step, inv_metric, start))| {
                let target = &target;
                let chain_seed = seed.wrapping_mul(16).wrapping_add(c as u64);
                let arm = match &arm {
                    Arm::Reference => None,
                    Arm::Walnuts(w) => Some(*w),
                };
                scope.spawn(move || -> Result<ChainRun, String> {
                    match arm {
                        None => Ok(run_reference(
                            target, *step, inv_metric, start, draws, chain_seed,
                        )),
                        Some(w) => {
                            run_walnuts(target, w, *step, inv_metric, start, draws, chain_seed)
                                .map_err(|e| e.to_string())
                        }
                    }
                })
            })
            .collect();
        handles
            .into_iter()
            .map(|h| h.join().expect("chain thread"))
            .collect::<Result<Vec<_>, String>>()
    })?;
    let wall = begin.elapsed().as_secs_f64();

    let mut per_coordinate = Vec::new();
    let (mut min_bulk, mut min_tail, mut max_rhat, mut sum_bulk) =
        (f64::INFINITY, f64::INFINITY, 0.0f64, 0.0);
    for k in 0..dimension {
        let columns: Vec<Vec<f64>> = runs
            .iter()
            .map(|r| r.samples.chunks(dimension).map(|row| row[k]).collect())
            .collect();
        let refs: Vec<&[f64]> = columns.iter().map(Vec::as_slice).collect();
        let (b, t, rh) = (ess_bulk(&refs), ess_tail(&refs), rhat(&refs));
        min_bulk = min_bulk.min(b);
        min_tail = min_tail.min(t);
        max_rhat = if rh.is_nan() {
            f64::NAN
        } else {
            max_rhat.max(rh)
        };
        sum_bulk += b;
        per_coordinate.push(json!({"bulk_ess": b, "tail_ess": t, "rhat": rh}));
    }
    let gradients: u64 = runs
        .iter()
        .map(|r| r.totals["target_calls_total"].as_u64().unwrap())
        .sum();
    let leaves: u64 = runs
        .iter()
        .map(|r| r.totals["leaves_built"].as_u64().unwrap())
        .sum();
    let transitions = (CHAINS * draws) as f64;
    let payload = json!({
        "schema": "kernel-gap-v1-cell",
        "model": model.file_stem().map(|s| s.to_string_lossy().to_string()),
        "arm": name, "seed": seed, "chains": CHAINS, "draws": draws, "dimension": dimension,
        "cmdstan_reference": cmdstan.file_name().map(|s| s.to_string_lossy().to_string()),
        "step_sizes": chains_in.iter().map(|c| c.0).collect::<Vec<_>>(),
        "wall_seconds": wall,
        "gradients": gradients,
        "leaves": leaves,
        "min_bulk_ess": min_bulk, "mean_bulk_ess": sum_bulk / dimension as f64,
        "min_tail_ess": min_tail, "max_rhat": max_rhat,
        "min_bulk_ess_per_gradient": min_bulk / gradients as f64,
        "min_bulk_ess_per_orbit": min_bulk / transitions,
        "leaves_per_orbit": leaves as f64 / transitions,
        "gradients_per_leaf": gradients as f64 / leaves as f64,
        "per_coordinate": per_coordinate,
        "chains_data": runs.iter().map(|r| json!({"totals": r.totals, "trace": r.trace})).collect::<Vec<_>>(),
    });
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(out, serde_json::to_vec(&payload)?)?;
    eprintln!(
        "{name} seed {seed}: wall {wall:.1}s min bulk ESS {min_bulk:.0} (mean {:.0}) rhat {max_rhat:.3} grads {gradients} leaves {leaves} ESS/grad*1e3 {:.3} ESS/orbit {:.3} leaves/orbit {:.1} grads/leaf {:.3}",
        sum_bulk / dimension as f64,
        1e3 * min_bulk / gradients as f64,
        min_bulk / transitions,
        leaves as f64 / transitions,
        gradients as f64 / leaves as f64,
    );
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [model, data, cmdstan, seed, name, out, rest @ ..] => {
            let draws = rest.first().map_or(Ok(2000), |t| t.parse::<usize>());
            match (seed.parse::<u64>(), draws) {
                (Ok(s), Ok(d)) => run(
                    Path::new(model),
                    Path::new(data),
                    Path::new(cmdstan),
                    s,
                    name,
                    Path::new(out),
                    d,
                ),
                _ => Err("seed and draws must be integers".into()),
            }
        }
        _ => Err(
            "usage: <model.so> <data.json> <cmdstan.json> <seed> <arm> <out.json> [draws]".into(),
        ),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
