//! oWALNUTS arms of the refinement-role study: one (model, arm, seed) cell.
//!
//! The posteriordb v5 harness (`STUDIES/posteriordb_bench_v5/src/main.rs`)
//! with the arm selecting the step-adaptation rule and `delta` (see
//! `arms.rs`), plus two instruments that the question of this study needs:
//!
//! 1. **Per-chain refinement accounting** from the retained telemetry: built
//!   leaves by refinement level, reverse-coarser stops and rejections,
//!   forward refinement attempts, the stop-cause histogram, the per-transition
//!   acceptance statistic and a histogram of the per-transition maximum
//!   absolute energy error.
//! 2. **A level-0 leaf-error trace** taken after the run, outside the wall
//!   and outside `gradients_total`: for every second retained draw of every
//!   chain a fresh momentum `p ~ N(0, M)` is drawn from the chain's installed
//!   diagonal mass and one macro step of size `m * h` (the chain's adapted
//!   `h`, multipliers 0.5, 1, 1.5, 2, 3) and of the reference step `h_ref`
//!   (CmdStan's adapted step for the model, passed on the command line) is
//!   integrated at refinement levels 0, 1 and 2 (1, 2, 4 micro-steps). The
//!   endpoint energy error `H_end - H_start` is the statistic the kernel
//!   tests against `delta` at each level, so its distribution says what
//!   fraction of leaves would be refined, and to which level, at any step
//!   in that range — including the step Stan runs at.
//!
//! Usage: `posteriordb-cell <model.so> <data.json> <arm> <seed> <out.json> [threads] [h_ref]`
//!
//! Loads the BridgeStan-compiled model (built without `STAN_THREADS`) through
//! `owalnuts_bridgestan::ReplicatedStanTarget` (one library copy per chain
//! thread), draws four Stan-style starts with `owalnuts::sampler::Init::uniform()`
//! and runs 1,000 warmup + 1,000 retained transitions on four parallel chains
//! (`Metric::diagonal()`, `Limits::admit_worst_case()`). Writes unconstrained
//! draws, per-chain work/health counters, the trace and the wall around
//! `Sampler::run` to JSON. Nothing is tuned per model.
#![forbid(unsafe_code)]

mod arms;

use arms::Arm;
use owalnuts::sampler::{Init, Limits, Metric, Sampler, Target, uniform_starts};
use owalnuts::walnutpie::{ALGORITHM_REVISION, PAPER_ADAPTATION_REVISION, StopReason};
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use rand::rngs::SmallRng;
use rand::{Rng, SeedableRng};
use rand_distr::StandardNormal;
use serde_json::json;
use std::{env, error::Error, fs, path::Path, time::Instant};

const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;
const TRACE_STRIDE: usize = 2;
const TRACE_MULTIPLIERS: [f64; 5] = [0.5, 1.0, 1.5, 2.0, 3.0];
const TRACE_LEVELS: usize = 3;
const ERROR_BINS: [f64; 8] = [0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 100.0, 1000.0];

/// One macro step of size `step` at refinement level `level` (`2^level`
/// leapfrog micro-steps) from `(q, p)`; returns the endpoint energy, or
/// `None` on a nonfinite evaluation. `grad` holds the gradient at `q` on entry.
fn macro_step(
    target: &dyn Target,
    mass: &[f64],
    q: &mut [f64],
    p: &mut [f64],
    grad: &mut [f64],
    step: f64,
    level: usize,
) -> Option<f64> {
    let micro = step / (1u32 << level) as f64;
    let half = 0.5 * micro;
    let mut log_prob = f64::NAN;
    for _ in 0..(1usize << level) {
        for (pj, gj) in p.iter_mut().zip(grad.iter()) {
            *pj += half * gj;
        }
        for ((qj, pj), mj) in q.iter_mut().zip(p.iter()).zip(mass) {
            *qj += micro * pj / mj;
        }
        log_prob = target.log_density_gradient(q, grad).ok()?;
        if !log_prob.is_finite() || grad.iter().any(|g| !g.is_finite()) {
            return None;
        }
        for (pj, gj) in p.iter_mut().zip(grad.iter()) {
            *pj += half * gj;
        }
    }
    let kinetic: f64 = p.iter().zip(mass).map(|(pj, mj)| pj * pj / (2.0 * mj)).sum();
    Some(-log_prob + kinetic)
}

fn quantile(sorted: &[f64], p: f64) -> f64 {
    if sorted.is_empty() {
        return f64::NAN;
    }
    let idx = ((sorted.len() - 1) as f64 * p).round() as usize;
    sorted[idx.min(sorted.len() - 1)]
}

/// Summary of a set of endpoint energy errors `H_end - H_start`.
fn summarise_errors(errors: &[Option<f64>]) -> serde_json::Value {
    let n = errors.len();
    let finite: Vec<f64> = errors.iter().filter_map(|e| *e).collect();
    let nonfinite = n - finite.len();
    let mut abs: Vec<f64> = finite.iter().map(|e| e.abs()).collect();
    abs.sort_by(|a, b| a.partial_cmp(b).unwrap());
    // A nonfinite leaf counts as exceeding every threshold and contributing
    // zero acceptance, as it does in the kernel.
    let frac_gt = |t: f64| (abs.iter().filter(|e| **e > t).count() + nonfinite) as f64 / n as f64;
    let mean_exp_neg_abs = abs.iter().map(|e| (-e).exp()).sum::<f64>() / n as f64;
    let mean_stan_accept = finite.iter().map(|e| (-e).exp().min(1.0)).sum::<f64>() / n as f64;
    json!({
        "n": n, "nonfinite": nonfinite,
        "frac_abs_gt_0.25": frac_gt(0.25), "frac_abs_gt_0.5": frac_gt(0.5),
        "frac_abs_gt_1": frac_gt(1.0), "frac_abs_gt_2": frac_gt(2.0),
        "frac_abs_gt_1000": frac_gt(1000.0),
        "mean_exp_neg_abs": mean_exp_neg_abs,
        "mean_stan_accept": mean_stan_accept,
        "mean_signed": if finite.is_empty() { f64::NAN } else { finite.iter().sum::<f64>() / finite.len() as f64 },
        "abs_q50": quantile(&abs, 0.5), "abs_q80": quantile(&abs, 0.8), "abs_q90": quantile(&abs, 0.9),
        "abs_q95": quantile(&abs, 0.95), "abs_q99": quantile(&abs, 0.99),
    })
}

/// The leaf-error trace of one chain: for every `TRACE_STRIDE`-th retained
/// draw, a fresh momentum from the installed mass and one macro step at each
/// (step, level). Returns the JSON summary and the target calls used.
fn leaf_error_trace(
    target: &dyn Target,
    mass: &[f64],
    draws: &[Vec<f64>],
    h: f64,
    h_ref: Option<f64>,
    seed: u64,
) -> (serde_json::Value, usize) {
    let dim = mass.len();
    let mut steps: Vec<(String, f64)> = TRACE_MULTIPLIERS
        .iter()
        .map(|m| (format!("h_x{m}"), m * h))
        .collect();
    if let Some(r) = h_ref {
        steps.push(("h_ref".to_string(), r));
    }
    let mut errors: Vec<Vec<Vec<Option<f64>>>> =
        vec![vec![Vec::new(); TRACE_LEVELS]; steps.len()];
    let mut rng = SmallRng::seed_from_u64(seed ^ 0x5eaf_e880_0000_0000);
    let mut calls = 0usize;
    let mut grad0 = vec![0.0; dim];
    let mut q = vec![0.0; dim];
    let mut p = vec![0.0; dim];
    let mut grad = vec![0.0; dim];
    for draw in draws.iter().step_by(TRACE_STRIDE) {
        calls += 1;
        let Ok(lp0) = target.log_density_gradient(draw, &mut grad0) else {
            continue;
        };
        let p0: Vec<f64> = mass
            .iter()
            .map(|m| m.sqrt() * rng.sample::<f64, _>(StandardNormal))
            .collect();
        let k0: f64 = p0.iter().zip(mass).map(|(pj, mj)| pj * pj / (2.0 * mj)).sum();
        let h0 = -lp0 + k0;
        for (s, (_, step)) in steps.iter().enumerate() {
            for level in 0..TRACE_LEVELS {
                q.copy_from_slice(draw);
                p.copy_from_slice(&p0);
                grad.copy_from_slice(&grad0);
                calls += 1usize << level;
                let end = macro_step(target, mass, &mut q, &mut p, &mut grad, *step, level);
                errors[s][level].push(end.map(|e| e - h0));
            }
        }
    }
    let summary: serde_json::Map<String, serde_json::Value> = steps
        .iter()
        .enumerate()
        .map(|(s, (label, step))| {
            (
                label.clone(),
                json!({
                    "step": step,
                    "levels": (0..TRACE_LEVELS).map(|l| summarise_errors(&errors[s][l])).collect::<Vec<_>>(),
                }),
            )
        })
        .collect();
    (
        json!({"draws_traced": draws.len().div_ceil(TRACE_STRIDE), "stride": TRACE_STRIDE,
               "levels": TRACE_LEVELS, "adapted_step": h, "reference_step": h_ref,
               "steps": summary}),
        calls,
    )
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

#[allow(clippy::too_many_arguments)]
fn run(
    model: &Path,
    data: &Path,
    arm_name: &str,
    seed: u64,
    out: &Path,
    threads: usize,
    h_ref: Option<f64>,
) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    let arm = Arm::parse(arm_name)?;
    let data_json = fs::read_to_string(data)?;
    // One library copy per chain thread: the non-STAN_THREADS BridgeStan build
    // has a single global autodiff stack per loaded module (v1 wall-gap report).
    let target =
        ReplicatedStanTarget::load(model, &default_preload(), Some(&data_json), 1, threads)?;
    let dimension = target.dimension();
    let tuning = arm.tuning();
    let kernel = tuning.to_kernel()?;
    let max_depth = kernel.max_depth();
    let max_levels = kernel.max_refinement_levels();
    let adaptation = arm.adaptation()?;
    let sampler = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .seed(seed)
        .threads(threads)
        .metric(Metric::diagonal())
        .adaptation(adaptation)
        .tuning(tuning)
        .limits(Limits::new().admit_worst_case());
    let worst_case = sampler.worst_case_target_evaluations(CHAINS)?;

    // Identical to `sampler.run_with_init(&target, &Init::uniform())`: the
    // starts are drawn here so that they and the search cost can be recorded.
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
                "schema": "refinement-role-v1-cell",
                "sampler": format!("owalnuts-{}", arm.name),
                "seed": seed, "status": "error", "stage": "init", "error": e.to_string(),
                "wall_seconds": 0.0, "target_calls": target.calls(),
                "recoverable_failures": target.recoverable_failures(),
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
                "schema": "refinement-role-v1-cell",
                "sampler": format!("owalnuts-{}", arm.name),
                "seed": seed, "status": "error", "stage": "sample", "error": e.to_string(),
                "wall_seconds": wall, "target_calls": target.calls(),
                "start_search_calls": start_search_calls,
                "recoverable_failures": target.recoverable_failures(),
                "algorithm_revision": ALGORITHM_REVISION,
            });
            fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
            return Err(e.into());
        }
    };
    let target_calls_total = target.calls();
    let recoverable_failures_total = target.recoverable_failures();

    let mut trace_calls_total = 0usize;
    let chains = posterior
        .chains()
        .iter()
        .enumerate()
        .map(|(c, chain)| {
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
            let mut leaves_attempted = 0usize;
            let mut orbit_states = 0usize;
            let mut refinement_attempts = 0usize;
            let mut reverse_rejections = 0usize;
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
                leaves_attempted += d.leaves_attempted();
                orbit_states += d.orbit_states();
                refinement_attempts += d.refinement_attempts();
                reverse_rejections += d.reverse_coarser_rejections();
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
            let samples: Vec<Vec<f64>> = (0..RETAINED)
                .map(|i| chain.sample(i).unwrap().to_vec())
                .collect();
            let mass = chain.metadata().mass_diagonal().to_vec();
            let h = chain.metadata().tuning().step_size();
            let (trace, trace_calls) =
                leaf_error_trace(&target, &mass, &samples, h, h_ref, seed.wrapping_mul(7919) + c as u64);
            trace_calls_total += trace_calls;
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
                "retained_leaves_attempted": leaves_attempted,
                "retained_orbit_states": orbit_states,
                "retained_transition_refinement_attempts": refinement_attempts,
                "retained_transition_reverse_coarser_rejections": reverse_rejections,
                "retained_work": {
                    "leaves_attempted": retained.leaves_attempted(),
                    "leaves_built": retained.leaves_built(),
                    "refinement_level_built": retained.refinement_level_built(),
                    "accepted_forward_micro_steps": retained.accepted_forward_micro_steps(),
                    "forward_refinement_attempts": retained.forward_refinement_attempts(),
                    "reverse_coarsening_attempts": retained.reverse_coarsening_attempts(),
                    "reverse_coarser_stops": retained.reverse_coarser_stops(),
                    "reverse_coarser_rejections": retained.reverse_coarser_rejections(),
                    "target_calls_forward": retained.target_calls_forward(),
                    "target_calls_reverse": retained.target_calls_reverse(),
                    "target_calls_initial": retained.target_calls_initial(),
                },
                "warmup_work": {
                    "leaves_built": discarded.leaves_built(),
                    "refinement_level_built": discarded.refinement_level_built(),
                    "reverse_coarser_stops": discarded.reverse_coarser_stops(),
                },
                "paper_adaptation_updates": paper,
                "leaf_error_trace": trace,
            })
        })
        .collect::<Vec<_>>();
    let payload = json!({
        "schema": "refinement-role-v1-cell",
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
                   "u_turn": format!("{:?}", kernel.options().u_turn),
                   "exhaustion": format!("{:?}", kernel.options().exhaustion),
                   "source": if arm.is_default() { "owalnuts::sampler::Tuning::default()" } else { "owalnuts::sampler::Tuning::default().max_error(arm)" }},
        "warmup_config": arm.json(),
        "constructor_admission_bound": worst_case,
        "timing_estimand": "wall around sampler::Sampler::run (warmup + retained, four parallel chains; start search and the leaf-error trace excluded)",
        "wall_seconds": wall,
        "target_calls_total": target_calls_total,
        "trace_target_calls": trace_calls_total,
        "target_calls_including_trace": target.calls(),
        "recoverable_failures_total": recoverable_failures_total,
        "chains_data": chains,
        "algorithm_revision": posterior.algorithm_revision(),
        "paper_adaptation_revision": PAPER_ADAPTATION_REVISION,
    });
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    eprintln!(
        "{} seed {seed}: wall {wall:.3}s, calls {target_calls_total} (+{trace_calls_total} trace), div {}",
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
            let h_ref = rest.get(1).map(|h| h.parse::<f64>());
            match (seed.parse::<u64>(), threads, h_ref) {
                (Ok(s), Ok(t), None) => {
                    run(Path::new(model), Path::new(data), arm, s, Path::new(out), t, None)
                }
                (Ok(s), Ok(t), Some(Ok(h))) => {
                    run(Path::new(model), Path::new(data), arm, s, Path::new(out), t, Some(h))
                }
                _ => Err("seed and threads must be integers, h_ref a number".into()),
            }
        }
        _ => Err("usage: <model.so> <data.json> <arm> <seed> <out.json> [threads] [h_ref]".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
