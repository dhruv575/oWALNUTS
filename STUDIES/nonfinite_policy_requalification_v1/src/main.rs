//! WP54 oWALNUTS cell: one (model, policy, seed) of the nonfinite-position
//! policy default-flip confirmation (`STUDIES/nonfinite_policy_requalification_v1`).
//!
//! Usage: `policy-cell <model.so> <data.json> <abort|reject_leaf> <seed> <out.json>
//!         [threads] [construct_seed] [preload.dll]`
//!
//! Everything is the shipped `owalnuts::sampler` default (the WP48 `diag`
//! arm): `Metric::diagonal()`, `Adaptation::default()`, `Tuning::default()`,
//! `Init::uniform()` at its shipped radius (via `uniform_starts`, exactly as
//! WP48), `Limits::admit_worst_case()`, 4 chains, 1,000 + 1,000. The two arms
//! differ only in `Tuning::nonfinite_position`:
//! - `abort`: `Tuning::default()` (the shipped `NonfinitePositionPolicy::Abort`);
//! - `reject_leaf`: `Tuning::default().nonfinite_position(RejectLeaf)`.
//!
//! The target is `ReplicatedStanTarget::load(model, preload, data,
//! construct_seed, threads)` with `construct_seed = 1` and
//! `preload = default_preload()` unless given (WP48 used 1 and the default).
//!
//! Writes the unconstrained retained draws, an FNV-1a-64 hash over the IEEE
//! bits of every retained draw (chain order), per-chain work counters
//! (target calls, nonfinite-position rejections by phase, divergences by
//! phase) and, on failure, the error kind and message.
#![forbid(unsafe_code)]

use owalnuts::sampler::{
    Init, Limits, Metric, NonfinitePositionPolicy, Sampler, Target, Tuning, uniform_starts,
    Adaptation,
};
use owalnuts::walnutpie::ALGORITHM_REVISION;
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::json;
use std::{env, error::Error, fs, path::{Path, PathBuf}, time::Instant};

const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;

struct Fnv(u64);
impl Fnv {
    fn new() -> Self {
        Self(0xcbf2_9ce4_8422_2325)
    }
    fn f64(&mut self, x: f64) {
        for b in x.to_bits().to_le_bytes() {
            self.0 ^= u64::from(b);
            self.0 = self.0.wrapping_mul(0x0000_0100_0000_01b3);
        }
    }
    fn hex(&self) -> String {
        format!("{:016x}", self.0)
    }
}

fn tuning_for(policy: &str) -> Result<Tuning, Box<dyn Error>> {
    match policy {
        "abort" => Ok(Tuning::default()),
        "reject_leaf" => Ok(Tuning::default().nonfinite_position(NonfinitePositionPolicy::RejectLeaf)),
        other => Err(format!("unknown policy {other:?} (expected abort, reject_leaf)").into()),
    }
}

#[allow(clippy::too_many_arguments)]
fn run(
    model: &Path,
    data: &Path,
    policy: &str,
    seed: u64,
    out: &Path,
    threads: usize,
    construct_seed: u32,
    preload: Option<PathBuf>,
) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    let tuning = tuning_for(policy)?;
    let kernel = tuning.to_kernel()?;
    let data_json = fs::read_to_string(data)?;
    let preload = match preload {
        Some(p) => vec![p],
        None => default_preload(),
    };
    let target =
        ReplicatedStanTarget::load(model, &preload, Some(&data_json), construct_seed, threads)?;
    let dimension = target.dimension();
    let max_depth = kernel.max_depth();
    let sampler = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .seed(seed)
        .threads(threads)
        .metric(Metric::diagonal())
        .adaptation(Adaptation::default())
        .tuning(tuning)
        .limits(Limits::new().admit_worst_case());
    let (radius, max_attempts) = match Init::uniform() {
        Init::Uniform { radius, max_attempts } => (radius, max_attempts),
        _ => unreachable!(),
    };
    let common = json!({
        "schema": "nonfinite-policy-requalification-v1-cell",
        "policy": policy, "seed": seed, "dimension": dimension,
        "kernel_nonfinite_position": format!("{:?}", kernel.nonfinite_position()),
        "model_library": model.display().to_string(),
        "preload": preload.iter().map(|p| p.display().to_string()).collect::<Vec<_>>(),
        "construct_seed": construct_seed, "threads": threads,
        "chains": CHAINS, "warmup": WARMUP, "retained": RETAINED,
        "init": {"rule": "sampler::Init::uniform()", "radius": radius, "max_attempts": max_attempts},
        "algorithm_revision_const": ALGORITHM_REVISION,
    });
    let fail = |stage: &str, kind: String, error: String, wall: f64, calls: usize| {
        let mut v = common.clone();
        let o = v.as_object_mut().unwrap();
        o.insert("status".into(), json!("error"));
        o.insert("stage".into(), json!(stage));
        o.insert("error_kind".into(), json!(kind));
        o.insert("error".into(), json!(error));
        o.insert("wall_seconds".into(), json!(wall));
        o.insert("target_calls".into(), json!(calls));
        v
    };
    let starts = match uniform_starts(&target, CHAINS, seed, radius, max_attempts) {
        Ok(s) => s,
        Err(e) => {
            let v = fail("init", format!("{:?}", e.kind()), e.to_string(), 0.0, target.calls());
            fs::write(out, serde_json::to_vec_pretty(&v)?)?;
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
            let v = fail("sample", format!("{:?}", e.kind()), e.to_string(), wall, target.calls());
            fs::write(out, serde_json::to_vec_pretty(&v)?)?;
            eprintln!("{policy} seed {seed}: error {:?}: {e}", e.kind());
            // A sampler error is a recorded result, not a harness failure.
            return Ok(());
        }
    };
    let mut all = Fnv::new();
    let chains = posterior
        .chains()
        .iter()
        .map(|chain| {
            let t = chain.telemetry();
            let retained = t.retained();
            let discarded = t.discarded();
            let total = t.total();
            let diags = &chain.diagnostics()[WARMUP..];
            let mut depth_hist = vec![0usize; max_depth + 1];
            for d in diags {
                depth_hist[d.depth().min(max_depth)] += 1;
            }
            let samples: Vec<Vec<f64>> = (0..RETAINED).map(|i| chain.sample(i).unwrap().to_vec()).collect();
            let mut h = Fnv::new();
            for s in &samples {
                for &x in s {
                    h.f64(x);
                    all.f64(x);
                }
            }
            json!({
                "samples": samples,
                "draw_hash": h.hex(),
                "divergences": retained.divergences(),
                "warmup_divergences": discarded.divergences(),
                "nonfinite_position_rejections_total": total.nonfinite_position_rejections(),
                "nonfinite_position_rejections_warmup": discarded.nonfinite_position_rejections(),
                "nonfinite_position_rejections_retained": retained.nonfinite_position_rejections(),
                "recoverable_target_failures": total.recoverable_target_failures(),
                "maximum_depth_stops": retained.maximum_depth_stops(),
                "invalid_stops": retained.invalid_evaluation_stops(),
                "refinement_exhaustions": retained.refinement_exhaustion_stops(),
                "retained_target_calls": retained.target_calls_total(),
                "warmup_target_calls": discarded.target_calls_total(),
                "total_target_calls": total.target_calls_total(),
                "final_step_size": chain.metadata().tuning().step_size(),
                "mass_diagonal": chain.metadata().mass_diagonal(),
                "retained_depth_histogram": depth_hist,
            })
        })
        .collect::<Vec<_>>();
    let mut v = common.clone();
    let o = v.as_object_mut().unwrap();
    o.insert("status".into(), json!("ok"));
    o.insert("draw_hash".into(), json!(all.hex()));
    o.insert("starts".into(), json!(starts));
    o.insert("start_search_calls".into(), json!(start_search_calls));
    o.insert("wall_seconds".into(), json!(wall));
    o.insert("target_calls_total".into(), json!(target.calls()));
    o.insert("recoverable_failures_total".into(), json!(target.recoverable_failures()));
    o.insert("chains_data".into(), json!(chains));
    o.insert("algorithm_revision".into(), json!(posterior.algorithm_revision()));
    o.insert("timing_estimand".into(), json!("wall around Sampler::run; contended shared machine"));
    fs::write(out, serde_json::to_vec(&v)?)?;
    eprintln!("{policy} seed {seed}: ok wall {wall:.2}s hash {}", all.hex());
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [model, data, policy, seed, out, rest @ ..] => {
            let threads = rest.first().map_or(Ok(CHAINS), |t| t.parse::<usize>());
            let construct = rest.get(1).map_or(Ok(1u32), |t| t.parse::<u32>());
            let preload = rest.get(2).map(PathBuf::from);
            match (seed.parse::<u64>(), threads, construct) {
                (Ok(s), Ok(t), Ok(c)) => run(
                    Path::new(model), Path::new(data), policy, s, Path::new(out), t, c, preload,
                ),
                _ => Err("seed, threads and construct_seed must be integers".into()),
            }
        }
        _ => Err("usage: <model.so> <data.json> <abort|reject_leaf> <seed> <out.json> [threads] [construct_seed] [preload]".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
