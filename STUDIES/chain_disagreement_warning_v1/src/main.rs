//! WP44 harness: one (model, seed) cell of the chain-disagreement warning
//! study at the complete `owalnuts::sampler` defaults.
//!
//! Usage: `chain-check-cell <model.so> <data.json> <seed> <out.json> [threads]`
//!
//! The run is the posteriordb v5/v6 oWALNUTS cell exactly (four
//! `Init::uniform()` starts, 1,000 warmup + 1,000 retained, `Metric::diagonal()`,
//! `Adaptation::default()`, `Tuning::default()`, `Limits::admit_worst_case()`,
//! four threads) with the post-WP36 defaults (no chain rescue). Nothing is
//! configured for the checks: they read telemetry the default run records.
//! Writes the unconstrained retained draws, per-chain end-of-warmup and
//! retained-draw window summaries (`RunTelemetry::warmup_end` /
//! `sampling_end`), `Posterior::chain_warnings()` (structured and as the
//! `Summary` warning lines), the `ChainDisagreement` of the unconstrained
//! draws and per-chain health counters.
#![forbid(unsafe_code)]

use owalnuts::diagnostics::{ChainWarning, Summary};
use owalnuts::sampler::{
    DEFAULT_CHAIN_RESCUE, Init, Limits, Metric, Sampler, Target, Tuning, uniform_starts,
};
use owalnuts::walnutpie::{ALGORITHM_REVISION, ChainWindowSummary};
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::{Value, json};
use std::{env, error::Error, fs, path::Path, time::Instant};

const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;

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

fn warning_json(warning: &ChainWarning) -> Value {
    let text = warning.to_string();
    match warning {
        ChainWarning::WarmupStep {
            chain,
            step,
            median_step,
        } => json!({"check": "warmup_step", "chain": chain, "step": step,
                    "median_step": median_step, "text": text}),
        ChainWarning::WarmupLogDensity {
            chain,
            median_log_density,
            reference,
            threshold,
        } => json!({"check": "warmup_log_density", "chain": chain,
                    "median_log_density": median_log_density, "reference": reference,
                    "threshold": threshold, "text": text}),
        ChainWarning::SampledLogDensity {
            chain,
            median_log_density,
            reference,
            threshold,
        } => json!({"check": "sampled_log_density", "chain": chain,
                    "median_log_density": median_log_density, "reference": reference,
                    "threshold": threshold, "text": text}),
        ChainWarning::RHat {
            chain,
            max_rhat,
            max_rhat_without,
        } => json!({"check": "rhat", "chain": chain, "max_rhat": max_rhat,
                    "max_rhat_without": max_rhat_without, "text": text}),
        other => json!({"check": "other", "chain": other.chain(), "text": text}),
    }
}

fn run(
    model: &Path,
    data: &Path,
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
    let data_json = fs::read_to_string(data)?;
    let target =
        ReplicatedStanTarget::load(model, &default_preload(), Some(&data_json), 1, threads)?;
    let dimension = target.dimension();
    let sampler = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .seed(seed)
        .threads(threads)
        .metric(Metric::diagonal())
        .tuning(Tuning::default())
        .limits(Limits::new().admit_worst_case());
    // Identical to `sampler.run_with_init(&target, &Init::uniform())`; the
    // starts are drawn here so that the start-search cost can be recorded.
    let (radius, max_attempts) = match Init::uniform() {
        Init::Uniform {
            radius,
            max_attempts,
        } => (radius, max_attempts),
        _ => unreachable!(),
    };
    let fail = |stage: &str, error: String, wall: f64| -> Result<(), Box<dyn Error>> {
        let payload = json!({
            "schema": "chain-disagreement-warning-v1-cell", "seed": seed, "status": "error",
            "stage": stage, "error": error, "wall_seconds": wall,
            "target_calls": target.calls(), "algorithm_revision": ALGORITHM_REVISION,
        });
        fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
        Err(error.into())
    };
    let starts = match uniform_starts(&target, CHAINS, seed, radius, max_attempts) {
        Ok(s) => s,
        Err(e) => return fail("init", e.to_string(), 0.0),
    };
    let start_search_calls = target.calls();
    let begin = Instant::now();
    let result = sampler.run(&target, &starts);
    let wall = begin.elapsed().as_secs_f64();
    let posterior = match result {
        Ok(p) => p,
        Err(e) => return fail("sample", e.to_string(), wall),
    };
    let warnings = posterior.chain_warnings();
    let summary = Summary::from_output(posterior.inner(), None)?;
    assert_eq!(summary.chain_warnings, warnings);
    let disagreement = summary.chain_disagreement.as_ref().map(|d| {
        json!({"max_rhat": d.max_rhat, "max_rhat_without": d.max_rhat_without,
               "chains": d.chains})
    });
    let chains: Vec<Value> = posterior
        .chains()
        .iter()
        .map(|chain| {
            let t = chain.telemetry();
            let retained = t.retained();
            json!({
                "samples": (0..RETAINED).map(|i| chain.sample(i).unwrap()).collect::<Vec<_>>(),
                "warmup_end": window_json(t.warmup_end()),
                "sampling_end": window_json(t.sampling_end()),
                "final_step_size": chain.metadata().tuning().step_size(),
                "divergences": retained.divergences(),
                "maximum_depth_stops": retained.maximum_depth_stops(),
                "refinement_exhaustions": retained.refinement_exhaustion_stops(),
                "retained_target_calls": retained.target_calls_total(),
                "warmup_target_calls": t.discarded().target_calls_total(),
                "chain_rescues": t.chain_rescues().len(),
            })
        })
        .collect();
    let payload = json!({
        "schema": "chain-disagreement-warning-v1-cell",
        "status": "ok",
        "seed": seed,
        "model_library": model.display().to_string(),
        "dimension": dimension,
        "chains": CHAINS, "warmup": WARMUP, "retained": RETAINED, "threads": threads,
        "start_search_calls": start_search_calls,
        "wall_seconds": wall,
        "target_calls_total": target.calls(),
        "chains_data": chains,
        "chain_warnings": warnings.iter().map(warning_json).collect::<Vec<_>>(),
        "warning_lines": ChainWarning::lines(&warnings),
        "chain_disagreement": disagreement,
        "unconstrained_max_rhat": summary.parameters.iter().map(|p| p.rhat).fold(f64::NAN, f64::max),
        "algorithm_revision": posterior.algorithm_revision(),
    });
    fs::write(out, serde_json::to_vec(&payload)?)?;
    eprintln!(
        "seed {seed}: wall {wall:.2}s, calls {}, warnings {}",
        target.calls(),
        warnings.len()
    );
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [model, data, seed, out, rest @ ..] => {
            let threads = rest.first().map_or(Ok(CHAINS), |t| t.parse::<usize>());
            match (seed.parse::<u64>(), threads) {
                (Ok(s), Ok(t)) => run(Path::new(model), Path::new(data), s, Path::new(out), t),
                _ => Err("seed and threads must be integers".into()),
            }
        }
        _ => Err("usage: <model.so> <data.json> <seed> <out.json> [threads]".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
