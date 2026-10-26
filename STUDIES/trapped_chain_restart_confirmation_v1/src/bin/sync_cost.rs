//! WP69 arm (d): wall cost of the trapped-chain synchronisation point
//! (`STUDIES/trapped_chain_restart_confirmation_v1`). New harness.
//!
//! Usage: `sync-cost <chains> <repeat> <seed> <out.json>`
//!
//! One cell = one process = one repeat at one chain count: a 100-D standard
//! Gaussian (analytic gradient), `chains` x 1,000 warmup / 1,000 draws on
//! `min(chains, 4)` threads (the lane has four cores), starts
//! `Init::best_of(16)` drawn once by `candidate_starts` and shared by both
//! arms. After one untimed warm-up run of `defaults`, seven interleaved
//! pairs run, each pair in the order `defaults, restart` on even repeats and
//! `restart, defaults` on odd repeats; the repeat's ratio is the median
//! restart wall over the median defaults wall. The wall is measured around
//! `Sampler::run` only. Both arms' draw hashes and target-call counts are
//! recorded (they must agree: the detector cannot fire on this target).
#![forbid(unsafe_code)]

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_WARMUP_EXHAUSTION, Limits, Sampler,
    StartSelection, Target, TargetError, WarmupConfig, candidate_starts,
};
use owalnuts::walnutpie::TrappedChainRestartConfig;
use serde_json::json;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::{env, error::Error, fs, path::Path, time::Instant};

const DIMENSION: usize = 100;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;
const LANE_CORES: usize = 4;
/// Interleaved (defaults, restart) pairs per repeat; the repeat's ratio is
/// median(restart walls) / median(defaults walls).
const PAIRS_PER_REPEAT: usize = 7;

struct Gaussian {
    calls: AtomicUsize,
}

impl Target for Gaussian {
    fn dimension(&self) -> usize {
        DIMENSION
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        for (gi, x) in g.iter_mut().zip(q) {
            *gi = -x;
        }
        Ok(-0.5 * q.iter().map(|x| x * x).sum::<f64>())
    }
}

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
}

fn sampler(arm: &str, chains: usize, seed: u64) -> Result<Sampler, Box<dyn Error>> {
    let base = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(chains)
        .seed(seed)
        .threads(chains.min(LANE_CORES))
        .limits(Limits::new().admit_worst_case());
    Ok(match arm {
        "defaults" => base,
        "restart" => base.adaptation(Adaptation::Custom(
            WarmupConfig::new(0.8)?
                .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
                .with_trapped_chain_restart(TrappedChainRestartConfig::step_rule()),
        )),
        other => return Err(format!("unknown arm {other:?}").into()),
    })
}

fn timed(
    arm: &str,
    chains: usize,
    seed: u64,
    target: &Gaussian,
    starts: &[Vec<f64>],
) -> Result<serde_json::Value, Box<dyn Error>> {
    let s = sampler(arm, chains, seed)?;
    let before = target.calls.load(Ordering::Relaxed);
    let begin = Instant::now();
    let posterior = s.run(target, starts)?;
    let wall = begin.elapsed().as_secs_f64();
    let calls = target.calls.load(Ordering::Relaxed) - before;
    let mut h = Fnv::new();
    let mut restarted = 0usize;
    let mut checks = 0usize;
    for chain in posterior.chains() {
        for i in 0..chain.retained() {
            for &x in chain.sample(i).expect("draw") {
                h.f64(x);
            }
        }
        checks += chain.telemetry().trapped_chain_checks().len();
        restarted += chain
            .telemetry()
            .trapped_chain_checks()
            .iter()
            .filter(|c| c.restarted())
            .count();
    }
    Ok(json!({"arm": arm, "wall_seconds": wall, "target_calls": calls,
              "draw_hash": format!("{:016x}", h.0), "checks": checks, "restarted": restarted}))
}

fn run(chains: usize, repeat: usize, seed: u64, out: &Path) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    let target = Gaussian {
        calls: AtomicUsize::new(0),
    };
    let starts = candidate_starts(
        &target, chains, seed, 2.0, 16, 100, StartSelection::HighestDensity,
    )?
    .starts;
    let warm = timed("defaults", chains, seed, &target, &starts)?;
    let order: [&str; 2] = if repeat % 2 == 0 {
        ["defaults", "restart"]
    } else {
        ["restart", "defaults"]
    };
    let mut runs = Vec::new();
    for _ in 0..PAIRS_PER_REPEAT {
        for arm in order {
            runs.push(timed(arm, chains, seed, &target, &starts)?);
        }
    }
    let walls = |arm: &str| -> Vec<f64> {
        let mut w: Vec<f64> = runs
            .iter()
            .filter(|r| r["arm"] == arm)
            .map(|r| r["wall_seconds"].as_f64().unwrap())
            .collect();
        w.sort_by(f64::total_cmp);
        w
    };
    let (wd, wr) = (walls("defaults"), walls("restart"));
    let median = |w: &[f64]| w[w.len() / 2];
    let ratio = median(&wr) / median(&wd);
    let identical = runs.iter().all(|r| {
        r["draw_hash"] == runs[0]["draw_hash"] && r["target_calls"] == runs[0]["target_calls"]
    });
    let (d, r) = (wd, wr);
    let payload = json!({
        "schema": "trapped-chain-restart-confirmation-v1-sync-cost",
        "dimension": DIMENSION, "chains": chains, "threads": chains.min(LANE_CORES),
        "warmup": WARMUP, "retained": RETAINED, "repeat": repeat, "seed": seed,
        "order": order, "pairs_per_repeat": PAIRS_PER_REPEAT, "warmup_run": warm, "runs": runs,
        "defaults_walls_sorted": d, "restart_walls_sorted": r,
        "wall_ratio_restart_over_defaults": ratio,
        "identical": identical,
        "timing_estimand": "wall around Sampler::run; pinned to lane cores 12-15 on a co-tenanted box; read as a ratio",
    });
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    eprintln!("sync chains {chains} repeat {repeat}: ratio {ratio:.4}");
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [chains, repeat, seed, out] => match (chains.parse(), repeat.parse(), seed.parse()) {
            (Ok(c), Ok(r), Ok(s)) => run(c, r, s, Path::new(out)),
            _ => Err("chains, repeat and seed must be integers".into()),
        },
        _ => Err("usage: sync-cost <chains> <repeat> <seed> <out.json>".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
