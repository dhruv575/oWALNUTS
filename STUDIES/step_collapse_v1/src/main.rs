//! Step-collapse study driver (`STUDIES/step_collapse_v1`).
//!
//! Usage: `step-collapse-v1 <model.so> <data.json> <seed> <variant> <out.json> [warmup] [draws]`
//!
//! Regenerates the posteriordb-benchmark starts for `seed`
//! (`owalnuts::sampler::uniform_starts`), runs the four chains of the cell
//! with `Sampler` defaults plus the named variant, and writes per-transition
//! warmup telemetry (`h`, the dual-averaging statistic, depth, stop, selected
//! refinement level, exhaustion, energy error) with every metric update
//! (window, step before/after, installed diagonal) per chain, plus the
//! minimum bulk ESS over the unconstrained coordinates. Variants are
//! `+`-joined parts, see [`variant`]. The retained draws go next to the JSON
//! as `<out>.draws.f64` (chain-major, draw-major, little-endian). The
//! initial step (`Tuning::step_size`) can be overridden with the `H0`
//! environment variable.
#![forbid(unsafe_code)]

use owalnuts::diagnostics::{ess_bulk, ess_tail, rhat};
use owalnuts::sampler::{
    Adaptation, DEFAULT_WARMUP_EXHAUSTION, Init, Limits, Metric, Sampler, Target, Tuning,
    WarmupConfig, uniform_starts,
};
use owalnuts::walnutpie::{
    DiagonalMetricRegularization, DualAveragingAcceptance, InitialStepSearchConfig, StopReason,
};
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::json;
use std::{env, error::Error, fs, path::Path, time::Instant};

const CHAINS: usize = 4;
const TARGET_ACCEPT: f64 = 0.8;

/// The sampler's default warmup as a `WarmupConfig` (what
/// `Adaptation::DualAveraging { 0.8 }` builds).
fn base() -> Result<WarmupConfig, Box<dyn Error>> {
    Ok(WarmupConfig::new(TARGET_ACCEPT)?.with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION))
}

/// `baseline` is `Adaptation::default()`; any other `+`-joined list of parts
/// is applied to the sampler's default `WarmupConfig` in order.
fn variant(name: &str) -> Result<Adaptation, Box<dyn Error>> {
    if name == "baseline" {
        return Ok(Adaptation::default());
    }
    let mut config = base()?;
    for part in name.split('+') {
        config = match part {
            "mean-accept" => config
                .with_dual_averaging_acceptance(DualAveragingAcceptance::MeanTrajectoryAcceptance),
            "research" => config.with_initial_step_search(InitialStepSearchConfig::stan()),
            "ramp" => config.with_initial_phase_max_error(1000.0)?,
            "mu10" => config.with_stan_restart_reference(true),
            "reg" => config.with_metric_regularization(DiagonalMetricRegularization::Stan),
            "stan-style" => WarmupConfig::stan_style(TARGET_ACCEPT)?
                .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION),
            other => {
                if let Some(rest) = other.strip_prefix("floor-rel:") {
                    config.with_step_floor_relative_to_search(rest.parse()?)?
                } else if let Some(rest) = other.strip_prefix("shrink:") {
                    config.with_max_window_shrink(rest.parse()?)?
                } else {
                    return Err(format!("unknown variant part {other:?}").into());
                }
            }
        };
    }
    Ok(Adaptation::Custom(config))
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
    let adaptation = variant(name)?;
    let data_json = fs::read_to_string(data)?;
    let target =
        ReplicatedStanTarget::load(model, &default_preload(), Some(&data_json), 1, CHAINS)?;
    let dimension = target.dimension();
    let h0: f64 = env::var("H0").ok().map_or(Ok(0.5), |s| s.parse())?;
    let tuning = Tuning::default().step_size(h0);
    let (radius, max_attempts) = match Init::uniform() {
        Init::Uniform {
            radius,
            max_attempts,
        } => (radius, max_attempts),
        _ => unreachable!(),
    };
    let starts = uniform_starts(&target, CHAINS, seed, radius, max_attempts)?;
    let mut grad = vec![0.0; dimension];
    let start_info: Vec<_> = starts
        .iter()
        .map(|s| {
            let lp = target.log_density_gradient(s, &mut grad).ok();
            let gnorm = grad.iter().map(|g| g * g).sum::<f64>().sqrt();
            json!({"start": s, "log_density": lp, "gradient_norm": gnorm})
        })
        .collect();

    let sampler = Sampler::new()
        .warmup(warmup)
        .draws(draws)
        .chains(CHAINS)
        .seed(seed)
        .threads(CHAINS)
        .metric(Metric::diagonal())
        .adaptation(adaptation)
        .tuning(tuning)
        .limits(Limits::new().admit_worst_case());
    let begin = Instant::now();
    let posterior = sampler.run(&target, &starts)?;
    let wall = begin.elapsed().as_secs_f64();

    let schedule = posterior.chains()[0]
        .metadata()
        .warmup_schedule()
        .map(|s| {
            json!({"initial_fast_end": s.initial_fast_end(),
                   "terminal_fast_start": s.terminal_fast_start(),
                   "windows": s.windows().iter().map(|w| [w.start(), w.end()]).collect::<Vec<_>>()})
        });

    let chains: Vec<_> = posterior
        .chains()
        .iter()
        .map(|chain| {
            let d = chain.diagnostics();
            let t = chain.telemetry();
            let r = t.retained();
            let moved: Vec<bool> = d.iter().map(|x| x.position_changed()).collect();
            let retained_caps = r.maximum_depth_stops();
            let retained_depths: Vec<usize> = d[warmup..].iter().map(|x| x.depth()).collect();
            let mean_depth =
                retained_depths.iter().sum::<usize>() as f64 / retained_depths.len().max(1) as f64;
            let refined = d[warmup..]
                .iter()
                .filter(|x| x.selected_refinement_level().is_some_and(|l| l > 0))
                .count();
            json!({
                "final_step_size": chain.metadata().tuning().step_size(),
                "final_mass_diagonal": chain.metadata().mass_diagonal(),
                "retained_depth_caps": retained_caps,
                "retained_depth_cap_rate": retained_caps as f64 / draws as f64,
                "retained_mean_depth": mean_depth,
                "retained_refined_fraction": refined as f64 / draws as f64,
                "retained_exhaustions": r.refinement_exhaustion_stops(),
                "retained_divergences": r.divergences(),
                "retained_recoverable_failures": r.recoverable_target_failures(),
                "retained_target_calls": r.target_calls_total(),
                "warmup_target_calls": t.discarded().target_calls_total(),
                "warmup_divergences": t.discarded().divergences(),
                "warmup_exhaustions": t.discarded().refinement_exhaustion_stops(),
                "warmup_depth_caps": t.discarded().maximum_depth_stops(),
                "warmup_moved": moved[..warmup].iter().filter(|m| **m).count(),
                "retained_moved": moved[warmup..].iter().filter(|m| **m).count(),
                "step_searches": t.step_searches().iter().map(|e| json!({
                    "reason": format!("{:?}", e.reason()),
                    "initial_step": e.search().initial_step(),
                    "selected_step": e.search().selected_step(),
                    "target_calls": e.search().target_calls(),
                })).collect::<Vec<_>>(),
                "metric_updates": t.metric_updates().iter().map(|u| json!({
                    "window_index": u.window_index(),
                    "transition": u.transition(),
                    "sample_count": u.sample_count(),
                    "outcome": format!("{:?}", u.outcome()),
                    "step_before": u.step_before(),
                    "step_after_search": u.step_after_search(),
                    "step_after_restart": u.step_after_restart(),
                    "mass_diagonal": u.mass_diagonal(),
                })).collect::<Vec<_>>(),
                "trace": {
                    "step_size": d.iter().map(|x| x.step_size()).collect::<Vec<_>>(),
                    "acceptance_statistic": d.iter().map(|x| x.acceptance_statistic()).collect::<Vec<_>>(),
                    "depth": d.iter().map(|x| x.depth()).collect::<Vec<_>>(),
                    "stop": d.iter().map(|x| stop_name(x.stop())).collect::<Vec<_>>(),
                    "leaves_built": d.iter().map(|x| x.leaves_built()).collect::<Vec<_>>(),
                    "selected_level": d.iter().map(|x| x.selected_refinement_level()).collect::<Vec<_>>(),
                    "refinement_attempts": d.iter().map(|x| x.refinement_attempts()).collect::<Vec<_>>(),
                    "reverse_coarser_rejections": d.iter().map(|x| x.reverse_coarser_rejections()).collect::<Vec<_>>(),
                    "recoverable_failures": d.iter().map(|x| x.recoverable_target_failures()).collect::<Vec<_>>(),
                    "max_abs_energy_error": d.iter().map(|x| x.maximum_absolute_energy_error()).collect::<Vec<_>>(),
                    "initial_hamiltonian": d.iter().map(|x| x.initial_hamiltonian()).collect::<Vec<_>>(),
                    "divergent": d.iter().map(|x| x.divergent()).collect::<Vec<_>>(),
                    "target_evaluations": d.iter().map(|x| x.target_evaluations()).collect::<Vec<_>>(),
                    "moved": moved,
                },
            })
        })
        .collect();

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
    let gradients_total: usize = posterior.total_target_calls();
    let gradients_sampling: usize = posterior
        .chains()
        .iter()
        .map(|c| c.telemetry().retained().target_calls_total())
        .sum();
    let payload = json!({
        "schema": "step-collapse-v1-cell",
        "model": model.file_stem().map(|s| s.to_string_lossy().to_string()),
        "variant": name, "h0": h0,
        "seed": seed, "chains": CHAINS, "warmup": warmup, "draws": draws,
        "dimension": dimension,
        "starts": start_info,
        "schedule": schedule,
        "wall_seconds": wall,
        "gradients_total": gradients_total,
        "gradients_sampling": gradients_sampling,
        "min_bulk_ess": min_bulk, "min_tail_ess": min_tail, "max_rhat": max_rhat,
        "min_bulk_ess_per_gradient": min_bulk / gradients_total as f64,
        "per_coordinate": per_coordinate,
        "chains_data": chains,
        "algorithm_revision": posterior.algorithm_revision(),
    });
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(out, serde_json::to_vec(&payload)?)?;
    let mut bytes = Vec::with_capacity(CHAINS * draws * dimension * 8);
    for c in 0..CHAINS {
        for x in posterior.chain_draws(c).unwrap() {
            bytes.extend_from_slice(&x.to_le_bytes());
        }
    }
    fs::write(out.with_extension("draws.f64"), bytes)?;
    eprintln!(
        "{name} seed {seed}: wall {wall:.1}s min bulk ESS {min_bulk:.0} rhat {max_rhat:.3} grads {gradients_total} ESS/grad*1e3 {:.3} h {:?} caps {:?}",
        1e3 * min_bulk / gradients_total as f64,
        chains
            .iter()
            .map(|c| c["final_step_size"].as_f64().unwrap_or(f64::NAN))
            .collect::<Vec<_>>(),
        chains
            .iter()
            .map(|c| c["retained_depth_caps"].as_u64().unwrap_or(0))
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
