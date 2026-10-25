//! WP55 harness: one (model, seed) cell of the silent-funnel diagnostic
//! study at the complete `owalnuts::sampler` defaults.
//!
//! Usage: `silent-funnel-cell <model.so | funnel> <data.json | -> <seed> <out.json> [threads]`
//!
//! A posteriordb cell is the WP44 cell exactly (four `Init::uniform()`
//! starts, 1,000 warmup + 1,000 retained, `Metric::diagonal()`,
//! `Tuning::default()`, `Limits::admit_worst_case()`, four threads, no chain
//! rescue). The `funnel` cell is the house 10-D Neal funnel of
//! `posteriordb_bench_v6/src/bin/funnel.rs` (starts omega in {-3, -1, 1, 3})
//! at 1,000 warmup + 1,000 retained. Nothing is configured for the study:
//! every statistic is read from telemetry the default run already records
//! (per-partition `WorkTotals`, per-transition diagnostics,
//! `RunTelemetry::warmup_end` / `sampling_end`, `Posterior::chain_warnings`).
#![forbid(unsafe_code)]

use owalnuts::diagnostics::{ChainWarning, Summary};
use owalnuts::sampler::{
    DEFAULT_CHAIN_RESCUE, Init, Limits, Metric, Posterior, Sampler, Target, TargetError, Tuning,
    uniform_starts,
};
use owalnuts::walnutpie::{ALGORITHM_REVISION, ChainWindowSummary, WorkTotals};
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::{Value, json};
use std::{env, error::Error, fs, path::Path, time::Instant};

const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;
const FUNNEL_DIMENSION: usize = 10;

struct Funnel;

impl Target for Funnel {
    fn dimension(&self) -> usize {
        FUNNEL_DIMENSION
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let omega = position[0];
        let inverse_variance = (-omega).exp();
        if !inverse_variance.is_finite() {
            return Err(TargetError::recoverable("exp(-omega) overflowed"));
        }
        let sum_squares: f64 = position[1..].iter().map(|x| x * x).sum();
        let tail = (FUNNEL_DIMENSION - 1) as f64;
        gradient[0] = -omega / 9.0 - 0.5 * tail + 0.5 * inverse_variance * sum_squares;
        for (g, x) in gradient[1..].iter_mut().zip(&position[1..]) {
            *g = -inverse_variance * x;
        }
        let value =
            -omega * omega / 18.0 - 0.5 * tail * omega - 0.5 * inverse_variance * sum_squares;
        if value.is_finite() && gradient.iter().all(|g| g.is_finite()) {
            Ok(value)
        } else {
            Err(TargetError::recoverable("nonfinite funnel evaluation"))
        }
    }
}

fn window_json(window: Option<&ChainWindowSummary>) -> Value {
    match window {
        None => Value::Null,
        Some(w) => json!({
            "start": w.start(), "end": w.end(), "transitions": w.transitions(),
            "step_size": w.step_size(), "median_log_density": w.median_log_density(),
            "log_density_iqr": w.log_density_iqr(),
        }),
    }
}

fn work_json(w: &WorkTotals) -> Value {
    json!({
        "transitions": w.transitions(),
        "target_calls_total": w.target_calls_total(),
        "forward_refinement_attempts": w.forward_refinement_attempts(),
        "reverse_coarsening_attempts": w.reverse_coarsening_attempts(),
        "leaves_attempted": w.leaves_attempted(),
        "leaves_built": w.leaves_built(),
        "refinement_level_built": w.refinement_level_built(),
        "maximum_depth_stops": w.maximum_depth_stops(),
        "divergences": w.divergences(),
        "invalid_evaluation_stops": w.invalid_evaluation_stops(),
        "refinement_exhaustion_stops": w.refinement_exhaustion_stops(),
        "reverse_coarser_stops": w.reverse_coarser_stops(),
        "recoverable_target_failures": w.recoverable_target_failures(),
        "zero_density_evaluations": w.zero_density_evaluations(),
    })
}

fn warning_json(warning: &ChainWarning) -> Value {
    let check = match warning {
        ChainWarning::WarmupStep { .. } => "warmup_step",
        ChainWarning::WarmupLogDensity { .. } => "warmup_log_density",
        ChainWarning::SampledLogDensity { .. } => "sampled_log_density",
        ChainWarning::RHat { .. } => "rhat",
        #[allow(unreachable_patterns)]
        _ => "other",
    };
    json!({"check": check, "chain": warning.chain(), "text": warning.to_string()})
}

fn sample<T: Target>(
    target: &T,
    starts: &[Vec<f64>],
    seed: u64,
    threads: usize,
) -> Result<Posterior, String> {
    Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .seed(seed)
        .threads(threads)
        .metric(Metric::diagonal())
        .tuning(Tuning::default())
        .limits(Limits::new().admit_worst_case())
        .run(target, starts)
        .map_err(|e| e.to_string())
}

fn chain_payload(posterior: &Posterior) -> Vec<Value> {
    posterior
        .chains()
        .iter()
        .map(|chain| {
            let t = chain.telemetry();
            let diags = chain.diagnostics();
            let (warm, kept) = diags.split_at(WARMUP.min(diags.len()));
            let mut selected_level_hist = vec![0usize; 16];
            let mut depth_sum = 0usize;
            for d in kept {
                if let Some(l) = d.selected_refinement_level() {
                    selected_level_hist[l.min(15)] += 1;
                }
                depth_sum += d.depth();
            }
            json!({
                "samples": (0..chain.retained()).map(|i| chain.sample(i).unwrap()).collect::<Vec<_>>(),
                "warmup_end": window_json(t.warmup_end()),
                "sampling_end": window_json(t.sampling_end()),
                "final_step_size": chain.metadata().tuning().step_size(),
                "warmup_step_trace_every_25": warm.iter().step_by(25).map(|d| d.step_size()).collect::<Vec<_>>(),
                "retained_work": work_json(t.retained()),
                "warmup_work": work_json(t.discarded()),
                "retained_selected_level_histogram": selected_level_hist,
                "retained_mean_tree_depth": depth_sum as f64 / kept.len().max(1) as f64,
                "chain_rescues": t.chain_rescues().len(),
            })
        })
        .collect()
}

fn run(
    model: &str,
    data: &str,
    seed: u64,
    out: &Path,
    threads: usize,
) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    assert!(
        DEFAULT_CHAIN_RESCUE.is_none(),
        "post-WP36 defaults required"
    );
    let fail = |stage: &str, error: String, wall: f64| -> Result<(), Box<dyn Error>> {
        let payload = json!({
            "schema": "silent-funnel-diagnostic-v1-cell", "seed": seed, "status": "error",
            "stage": stage, "error": error, "wall_seconds": wall,
            "algorithm_revision": ALGORITHM_REVISION,
        });
        fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
        Err(error.into())
    };
    let begin = Instant::now();
    let (result, dimension, calls, start_calls) = if model == "funnel" {
        let starts: Vec<Vec<f64>> = [-3.0, -1.0, 1.0, 3.0]
            .into_iter()
            .map(|omega| {
                let mut q = vec![0.0; FUNNEL_DIMENSION];
                q[0] = omega;
                q
            })
            .collect();
        (
            sample(&Funnel, &starts, seed, threads),
            FUNNEL_DIMENSION,
            None,
            0,
        )
    } else {
        let data_json = fs::read_to_string(data)?;
        let target = ReplicatedStanTarget::load(
            Path::new(model),
            &default_preload(),
            Some(&data_json),
            1,
            threads,
        )?;
        let (radius, max_attempts) = match Init::uniform() {
            Init::Uniform {
                radius,
                max_attempts,
            } => (radius, max_attempts),
            _ => unreachable!(),
        };
        let starts = match uniform_starts(&target, CHAINS, seed, radius, max_attempts) {
            Ok(s) => s,
            Err(e) => return fail("init", e.to_string(), 0.0),
        };
        let start_calls = target.calls();
        let r = sample(&target, &starts, seed, threads);
        (r, target.dimension(), Some(target.calls()), start_calls)
    };
    let wall = begin.elapsed().as_secs_f64();
    let posterior = match result {
        Ok(p) => p,
        Err(e) => return fail("sample", e, wall),
    };
    let warnings = posterior.chain_warnings();
    let summary = Summary::from_output(posterior.inner(), None)?;
    assert_eq!(summary.chain_warnings, warnings);
    let disagreement = summary.chain_disagreement.as_ref().map(|d| {
        json!({"max_rhat": d.max_rhat, "max_rhat_without": d.max_rhat_without,
               "chains": d.chains})
    });
    let payload = json!({
        "schema": "silent-funnel-diagnostic-v1-cell",
        "status": "ok",
        "seed": seed,
        "model": model,
        "dimension": dimension,
        "chains": CHAINS, "warmup": WARMUP, "retained": RETAINED, "threads": threads,
        "start_search_calls": start_calls,
        "wall_seconds": wall,
        "target_calls_total": calls,
        "chains_data": chain_payload(&posterior),
        "chain_warnings": warnings.iter().map(warning_json).collect::<Vec<_>>(),
        "warning_lines": ChainWarning::lines(&warnings),
        "chain_disagreement": disagreement,
        "algorithm_revision": posterior.algorithm_revision(),
    });
    fs::write(out, serde_json::to_vec(&payload)?)?;
    eprintln!("seed {seed}: wall {wall:.2}s, warnings {}", warnings.len());
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [model, data, seed, out, rest @ ..] => {
            let threads = rest.first().map_or(Ok(CHAINS), |t| t.parse::<usize>());
            match (seed.parse::<u64>(), threads) {
                (Ok(s), Ok(t)) => run(model, data, s, Path::new(out), t),
                _ => Err("seed and threads must be integers".into()),
            }
        }
        _ => Err("usage: <model.so|funnel> <data.json|-> <seed> <out.json> [threads]".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
