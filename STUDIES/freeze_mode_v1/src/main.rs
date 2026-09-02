//! Freeze-mode study driver (`STUDIES/freeze_mode_v1`).
//!
//! Usage: `freeze-mode-v1 <model.so> <data.json> <seed> <variant> <out.json> [warmup] [draws]`
//!
//! Regenerates the `posteriordb_bench_v2` starts for `seed`
//! (`owalnuts::sampler::uniform_starts` is deterministic in the seed), runs the
//! four chains of the cell with `Sampler` defaults plus the named variant, and
//! writes per-transition telemetry (`h`, depth, stop, leaves built, recoverable
//! failures, energy error, whether the position moved) together with a
//! per-chain summary and the minimum bulk ESS over the unconstrained
//! coordinates. Variants are `+`-joined parts, see [`variant`].
#![forbid(unsafe_code)]

use owalnuts::diagnostics::{ess_bulk, ess_tail, rhat};
use owalnuts::sampler::{
    Adaptation, Init, Limits, Metric, Sampler, Target, Tuning, WarmupConfig, uniform_starts,
};
use owalnuts::walnutpie::{
    DualAveragingAcceptance, ExhaustionRule, KernelOptions, StopReason, UTurnRule,
};
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::json;
use std::{env, error::Error, fs, path::Path, time::Instant};

const CHAINS: usize = 4;
const TARGET_ACCEPT: f64 = 0.8;

struct Variant {
    options: KernelOptions,
    adaptation: Adaptation,
    init: Init,
}

fn variant(name: &str) -> Result<Variant, Box<dyn Error>> {
    let mut v = Variant {
        options: KernelOptions::default(),
        adaptation: Adaptation::default(),
        init: Init::uniform(),
    };
    let parts: Vec<&str> = if name.contains("exhaust-signed") && name.contains('+') {
        vec![name]
    } else {
        name.split('+').collect()
    };
    for part in parts {
        match part {
            "baseline" => {}
            "exhaust-accept" => {
                v.options.exhaustion = ExhaustionRule::AcceptBelowDivergenceThreshold
            }
            "exhaust-signed" => v.options.exhaustion = ExhaustionRule::AcceptUnlessDivergent,
            "rhosum" => v.options.u_turn = UTurnRule::MomentumSum,
            "warmup-signed" => {
                v.adaptation = Adaptation::Custom(
                    WarmupConfig::new(TARGET_ACCEPT)?
                        .with_warmup_exhaustion_rule(ExhaustionRule::AcceptUnlessDivergent),
                )
            }
            "step-floor" => {
                v.adaptation =
                    Adaptation::Custom(WarmupConfig::new(TARGET_ACCEPT)?.with_minimum_step(1e-3)?)
            }
            "stan-style+exhaust-signed" => {
                v.options.exhaustion = ExhaustionRule::AcceptUnlessDivergent;
                v.adaptation = Adaptation::Custom(WarmupConfig::stan_style(TARGET_ACCEPT)?)
            }
            "mean-accept+exhaust-signed" | "exhaust-signed+mean-accept" => {
                v.options.exhaustion = ExhaustionRule::AcceptUnlessDivergent;
                v.adaptation = Adaptation::Custom(
                    WarmupConfig::new(TARGET_ACCEPT)?.with_dual_averaging_acceptance(
                        DualAveragingAcceptance::MeanTrajectoryAcceptance,
                    ),
                )
            }
            "mean-accept" => {
                v.adaptation = Adaptation::Custom(
                    WarmupConfig::new(TARGET_ACCEPT)?.with_dual_averaging_acceptance(
                        DualAveragingAcceptance::MeanTrajectoryAcceptance,
                    ),
                )
            }
            "stan-style" => {
                v.adaptation = Adaptation::Custom(WarmupConfig::stan_style(TARGET_ACCEPT)?)
            }
            other => return Err(format!("unknown variant part {other:?}").into()),
        }
    }
    Ok(v)
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

fn run(
    model: &Path,
    data: &Path,
    seed: u64,
    name: &str,
    out: &Path,
    warmup: usize,
    draws: usize,
) -> Result<(), Box<dyn Error>> {
    let v = variant(name)?;
    let data_json = fs::read_to_string(data)?;
    let target =
        ReplicatedStanTarget::load(model, &default_preload(), Some(&data_json), 1, CHAINS)?;
    let dimension = target.dimension();
    let tuning = Tuning::default().kernel_options(v.options);
    let (radius, max_attempts) = match Init::uniform() {
        Init::Uniform {
            radius,
            max_attempts,
        } => (radius, max_attempts),
        _ => unreachable!(),
    };
    // The v2 starts, exactly (same seed, same rule).
    let v2_starts = uniform_starts(&target, CHAINS, seed, radius, max_attempts)?;
    let calls_before = target.calls();
    let starts = match &v.init {
        Init::Given(starts) => starts.clone(),
        _ => v2_starts.clone(),
    };
    let start_search_calls = target.calls() - calls_before;
    let mut grad = vec![0.0; dimension];
    let start_info: Vec<_> = starts
        .iter()
        .zip(&v2_starts)
        .map(|(s, v2)| {
            let lp = target.log_density_gradient(s, &mut grad).ok();
            let gnorm = grad.iter().map(|g| g * g).sum::<f64>().sqrt();
            json!({"start": s, "same_as_v2": s == v2, "log_density": lp, "gradient_norm": gnorm,
                   "gradient_max_abs": grad.iter().fold(0.0f64, |m, g| m.max(g.abs()))})
        })
        .collect();

    let sampler = Sampler::new()
        .warmup(warmup)
        .draws(draws)
        .chains(CHAINS)
        .seed(seed)
        .threads(CHAINS)
        .metric(Metric::diagonal())
        .adaptation(v.adaptation.clone())
        .tuning(tuning)
        .limits(Limits::new().admit_worst_case());
    let begin = Instant::now();
    let posterior = sampler.run(&target, &starts)?;
    let wall = begin.elapsed().as_secs_f64();

    let chains: Vec<_> = posterior
        .chains()
        .iter()
        .map(|chain| {
            let d = chain.diagnostics();
            let t = chain.telemetry();
            let moved: Vec<bool> = d.iter().map(|x| x.position_changed()).collect();
            // Escape = first transition after which at least 45 of the next 50
            // transitions move the position; None if never.
            let escape = (0..moved.len().saturating_sub(50))
                .find(|&i| moved[i..i + 50].iter().filter(|m| **m).count() >= 45);
            let retained_moved = moved[warmup..].iter().filter(|m| **m).count();
            json!({
                "first_retained": chain.sample(0),
                "final_step_size": chain.metadata().tuning().step_size(),
                "escape_transition": escape,
                "retained_moved": retained_moved,
                "warmup_moved": moved[..warmup].iter().filter(|m| **m).count(),
                "retained_exhaustions": t.retained().refinement_exhaustion_stops(),
                "retained_divergences": t.retained().divergences(),
                "retained_recoverable_failures": t.retained().recoverable_target_failures(),
                "retained_depth_caps": t.retained().maximum_depth_stops(),
                "warmup_recoverable_failures": t.discarded().recoverable_target_failures(),
                "warmup_target_calls": t.discarded().target_calls_total(),
                "retained_target_calls": t.retained().target_calls_total(),
                "mass_diagonal": chain.metadata().mass_diagonal(),
                "trace": {
                    "step_size": d.iter().map(|x| x.step_size()).collect::<Vec<_>>(),
                    "depth": d.iter().map(|x| x.depth()).collect::<Vec<_>>(),
                    "stop": d.iter().map(|x| stop_name(x.stop())).collect::<Vec<_>>(),
                    "leaves_built": d.iter().map(|x| x.leaves_built()).collect::<Vec<_>>(),
                    "recoverable_failures": d.iter().map(|x| x.recoverable_target_failures()).collect::<Vec<_>>(),
                    "max_abs_energy_error": d.iter().map(|x| x.maximum_absolute_energy_error()).collect::<Vec<_>>(),
                    "initial_hamiltonian": d.iter().map(|x| x.initial_hamiltonian()).collect::<Vec<_>>(),
                    "divergent": d.iter().map(|x| x.divergent()).collect::<Vec<_>>(),
                    "selected_level": d.iter().map(|x| x.selected_refinement_level()).collect::<Vec<_>>(),
                    "refinement_attempts": d.iter().map(|x| x.refinement_attempts()).collect::<Vec<_>>(),
                    "target_evaluations": d.iter().map(|x| x.target_evaluations()).collect::<Vec<_>>(),
                    "acceptance_statistic": d.iter().map(|x| x.acceptance_statistic()).collect::<Vec<_>>(),
                    "moved": moved,
                },
            })
        })
        .collect();

    // ESS / R-hat over unconstrained coordinates (rank-normalised bulk ESS).
    let mut per_coordinate = Vec::new();
    let mut min_bulk = f64::INFINITY;
    let mut min_tail = f64::INFINITY;
    let mut max_rhat: f64 = 0.0;
    for k in 0..dimension {
        let columns: Vec<Vec<f64>> = (0..CHAINS)
            .map(|c| {
                posterior
                    .chain_draws(c)
                    .unwrap()
                    .chunks(dimension)
                    .map(|row| row[k])
                    .collect()
            })
            .collect();
        let refs: Vec<&[f64]> = columns.iter().map(Vec::as_slice).collect();
        let (b, tl, r) = (ess_bulk(&refs), ess_tail(&refs), rhat(&refs));
        min_bulk = min_bulk.min(b);
        min_tail = min_tail.min(tl);
        max_rhat = if r.is_nan() {
            f64::NAN
        } else {
            max_rhat.max(r)
        };
        per_coordinate.push(json!({"bulk_ess": b, "tail_ess": tl, "rhat": r}));
    }
    let gradients_total: usize = posterior
        .chains()
        .iter()
        .map(|c| c.telemetry().total().target_calls_total())
        .sum();
    let gradients_sampling: usize = posterior
        .chains()
        .iter()
        .map(|c| c.telemetry().retained().target_calls_total())
        .sum();
    let frozen = chains
        .iter()
        .filter(|c| c["escape_transition"].is_null())
        .count();
    let payload = json!({
        "schema": "freeze-mode-v1-cell",
        "model": model.file_stem().map(|s| s.to_string_lossy().to_string()),
        "variant": name,
        "seed": seed, "chains": CHAINS, "warmup": warmup, "draws": draws,
        "dimension": dimension,
        "starts": start_info,
        "start_search_calls": start_search_calls,
        "wall_seconds": wall,
        "gradients_total": gradients_total,
        "gradients_sampling": gradients_sampling,
        "min_bulk_ess": min_bulk, "min_tail_ess": min_tail, "max_rhat": max_rhat,
        "min_bulk_ess_per_gradient": min_bulk / gradients_total as f64,
        "per_coordinate": per_coordinate,
        "frozen_chains": frozen,
        "chains_data": chains,
        "algorithm_revision": posterior.algorithm_revision(),
    });
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(out, serde_json::to_vec(&payload)?)?;
    eprintln!(
        "{name} seed {seed}: wall {wall:.2}s frozen {frozen} min bulk ESS {min_bulk:.1} grads {gradients_total} h {:?}",
        chains
            .iter()
            .map(|c| c["final_step_size"].as_f64().unwrap_or(f64::NAN))
            .collect::<Vec<_>>()
    );
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [model, data, seed, name, out, rest @ ..] => {
            let warmup = rest.first().map_or(Ok(1000), |t| t.parse::<usize>());
            let draws = rest.get(1).map_or(Ok(1000), |t| t.parse::<usize>());
            match (seed.parse::<u64>(), warmup, draws) {
                (Ok(s), Ok(w), Ok(d)) => run(
                    Path::new(model),
                    Path::new(data),
                    s,
                    name,
                    Path::new(out),
                    w,
                    d,
                ),
                _ => Err("seed, warmup and draws must be integers".into()),
            }
        }
        _ => {
            Err("usage: <model.so> <data.json> <seed> <variant> <out.json> [warmup] [draws]".into())
        }
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
