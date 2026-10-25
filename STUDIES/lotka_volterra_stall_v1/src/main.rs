//! WP57 cell: one (arm, seed) run of `hudson_lynx_hare-lotka_volterra` with
//! per-transition telemetry streamed during the run
//! (`STUDIES/lotka_volterra_stall_v1`).
//!
//! Usage: `stall-cell <model.so> <data.json> <arm> <seed> <out.json>
//!         <timeout_seconds> [threads] [--plain]`
//!
//! Arms (everything else is the shipped `owalnuts::sampler` default at
//! `f097391c`: `Metric::diagonal()`, `Adaptation::default()`,
//! `Tuning::default()`, `Limits::admit_worst_case()`, 4 chains, 1,000 + 1,000):
//! - `defaults`: `Init::default()` = `Init::best_of(16)` (via
//!   `candidate_starts`, exactly as `Sampler::run_with_init`).
//! - `best_of_64`: `Init::best_of(64)`.
//! - `depth6_initial`: defaults plus `WarmupConfig::with_initial_phase_max_depth(6)`,
//!   given as `Adaptation::Custom` of the configuration `Adaptation::default()`
//!   builds (`WarmupConfig::new(0.8)`, `DEFAULT_WARMUP_EXHAUSTION`,
//!   `DEFAULT_METRIC_REGULARIZATION`, no rescue).
//! - `depth10_initial`: the same with a cap of 10 = the kernel maximum (a
//!   no-op; smoke check that the `Custom` route is bit-identical).
//! - `uniform`: `Init::uniform()` (candidate_starts with one candidate, which
//!   equals `uniform_starts`), the pre-WP52 rule.
//!
//! The run goes through `Sampler::run_with_comparison_observers`; the
//! comparison observer is observe-only and records, per chain and transition,
//! the warmup stage and window, step, depth, stop reason, target calls,
//! refinement attempts, selected level, divergence, selected log density, the
//! transition's wall time and the wall time spent inside the target. The
//! target is wrapped to time each call (per thread). The run has a cooperative
//! `Limits::timeout`; on timeout the telemetry recorded so far, plus the calls
//! of each chain's unfinished transition, are written. `--plain` runs
//! `Sampler::run` with no observer and no wrapper (identity smoke check).
#![forbid(unsafe_code)]

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_WARMUP_EXHAUSTION, Limits, Metric,
    Sampler, StartSelection, Target, TargetError, Tuning, WarmupConfig, candidate_starts,
};
use owalnuts::walnutpie::{
    ALGORITHM_REVISION, ComparisonObserver, ComparisonTransitionObservation, ProposalObservation,
    ProposalObservationControl, ProposalObserver, WarmupPhase,
};
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::json;
use std::cell::Cell;
use std::num::NonZeroUsize;
use std::sync::Mutex;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::time::{Duration, Instant};
use std::{env, error::Error, fs, path::Path};

const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;
const SLOTS: usize = 128;

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

// ---------------------------------------------------------------- per-thread call timing

static NEXT_SLOT: AtomicUsize = AtomicUsize::new(0);
static SLOT_CALLS: [AtomicU64; SLOTS] = [const { AtomicU64::new(0) }; SLOTS];
static SLOT_NS: [AtomicU64; SLOTS] = [const { AtomicU64::new(0) }; SLOTS];
/// chain + 1 of the last transition observed on this slot's thread (0 = none).
static SLOT_CHAIN: [AtomicUsize; SLOTS] = [const { AtomicUsize::new(0) }; SLOTS];
thread_local! {
    static SLOT: Cell<usize> = const { Cell::new(usize::MAX) };
}
fn slot() -> usize {
    SLOT.with(|s| {
        if s.get() == usize::MAX {
            s.set(NEXT_SLOT.fetch_add(1, Ordering::Relaxed) % SLOTS);
        }
        s.get()
    })
}

struct Timed<'a>(&'a ReplicatedStanTarget);
impl Target for Timed<'_> {
    fn dimension(&self) -> usize {
        self.0.dimension()
    }
    fn parameter_names(&self) -> Option<Vec<String>> {
        self.0.parameter_names()
    }
    fn log_density_gradient(&self, position: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        let begin = Instant::now();
        let out = self.0.log_density_gradient(position, gradient);
        let ns = begin.elapsed().as_nanos() as u64;
        let s = slot();
        SLOT_CALLS[s].fetch_add(1, Ordering::Relaxed);
        SLOT_NS[s].fetch_add(ns, Ordering::Relaxed);
        out
    }
}

// ---------------------------------------------------------------- observers

struct NoProposals;
impl ProposalObserver for NoProposals {
    fn observe(&self, _: &ProposalObservation) {}
}

/// Field order of one telemetry row.
const FIELDS: [&str; 19] = [
    "t", "discarded", "stage", "window", "step", "depth", "stop", "target_evaluations",
    "leaves_built", "refinement_attempts", "selected_level", "divergent", "log_density",
    "wall_us", "eval_us", "eval_calls", "max_abs_energy_error", "zero_density", "t_end_ms",
];
const STOPS: [&str; 6] = [
    "MaximumDepth", "OuterUTurn", "RecursiveUTurn", "RefinementExhausted",
    "ReverseCoarserAccepted", "InvalidEvaluation",
];

struct Recorder {
    begin: Instant,
    last: Mutex<Vec<Instant>>,
    rows: Mutex<Vec<Vec<[f64; 19]>>>,
}
impl ComparisonObserver for Recorder {
    fn observe(&self, o: &ComparisonTransitionObservation) {
        let now = Instant::now();
        let s = slot();
        let calls = SLOT_CALLS[s].swap(0, Ordering::Relaxed);
        let ns = SLOT_NS[s].swap(0, Ordering::Relaxed);
        SLOT_CHAIN[s].store(o.chain + 1, Ordering::Relaxed);
        let wall = {
            let mut last = self.last.lock().unwrap();
            let w = now.duration_since(last[o.chain]);
            last[o.chain] = now;
            w
        };
        let d = &o.diagnostics;
        let (stage, window) = match &o.adaptation {
            Some(a) => (
                match a.stage {
                    WarmupPhase::InitialFast => 0.0,
                    WarmupPhase::SlowWindow => 1.0,
                    WarmupPhase::TerminalFast => 2.0,
                    _ => -1.0,
                },
                a.window_index.map_or(-1.0, |w| w as f64),
            ),
            None => (3.0, -1.0),
        };
        let stop = format!("{:?}", d.stop());
        let stop = STOPS.iter().position(|x| *x == stop).map_or(-1.0, |i| i as f64);
        let row = [
            o.transition as f64,
            f64::from(u8::from(o.discarded)),
            stage,
            window,
            d.step_size(),
            d.depth() as f64,
            stop,
            d.target_evaluations() as f64,
            d.leaves_built() as f64,
            d.refinement_attempts() as f64,
            d.selected_refinement_level().map_or(-1.0, |l| l as f64),
            f64::from(u8::from(d.divergent())),
            o.selected_log_density,
            wall.as_secs_f64() * 1e6,
            ns as f64 / 1e3,
            calls as f64,
            d.maximum_absolute_energy_error(),
            d.zero_density_evaluations() as f64,
            now.duration_since(self.begin).as_secs_f64() * 1e3,
        ];
        self.rows.lock().unwrap()[o.chain].push(row);
    }
}

// ---------------------------------------------------------------- arms

fn init_candidates(arm: &str) -> usize {
    match arm {
        "best_of_64" => 64,
        "uniform" => 1,
        _ => 16,
    }
}

fn adaptation_for(arm: &str) -> Result<Adaptation, Box<dyn Error>> {
    let custom = |depth: usize| -> Result<Adaptation, Box<dyn Error>> {
        Ok(Adaptation::Custom(
            WarmupConfig::new(0.8)?
                .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
                .with_initial_phase_max_depth(depth)?,
        ))
    };
    match arm {
        "defaults" | "best_of_64" | "uniform" => Ok(Adaptation::default()),
        "depth6_initial" => custom(6),
        "depth10_initial" => custom(10),
        other => Err(format!("unknown arm {other:?}").into()),
    }
}

#[allow(clippy::too_many_lines)]
fn run(
    model: &Path,
    data: &Path,
    arm: &str,
    seed: u64,
    out: &Path,
    timeout: f64,
    threads: usize,
    plain: bool,
) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    let adaptation = adaptation_for(arm)?;
    let tuning = Tuning::default();
    let kernel = tuning.to_kernel()?;
    let data_json = fs::read_to_string(data)?;
    let preload = default_preload();
    let target = ReplicatedStanTarget::load(model, &preload, Some(&data_json), 1, threads)?;
    let dimension = target.dimension();
    let candidates = init_candidates(arm);
    let chosen = candidate_starts(
        &target, CHAINS, seed, 2.0, candidates, 100, StartSelection::HighestDensity,
    )?;
    let start_search_calls = target.calls();
    let sampler = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .seed(seed)
        .threads(threads)
        .metric(Metric::diagonal())
        .adaptation(adaptation.clone())
        .tuning(tuning)
        .limits(Limits::new().admit_worst_case().timeout(Duration::from_secs_f64(timeout)));
    let mut starts_hash = Fnv::new();
    for s in &chosen.starts {
        for &x in s {
            starts_hash.f64(x);
        }
    }
    let mut v = json!({
        "schema": "lotka-volterra-stall-v1-cell",
        "arm": arm, "seed": seed, "dimension": dimension, "plain": plain,
        "model_library": model.display().to_string(),
        "construct_seed": 1, "threads": threads,
        "chains": CHAINS, "warmup": WARMUP, "retained": RETAINED,
        "timeout_seconds": timeout,
        "init": {"rule": format!("candidate_starts(radius 2, candidates {candidates}, attempts 100, HighestDensity)"),
                 "candidates": candidates},
        "adaptation": format!("{adaptation:?}"),
        "kernel_max_depth": kernel.max_depth(),
        "kernel_nonfinite_position": format!("{:?}", kernel.nonfinite_position()),
        "algorithm_revision_const": ALGORITHM_REVISION,
        "starts": chosen.starts, "starts_hash": starts_hash.hex(),
        "start_log_densities": chosen.start_log_densities,
        "candidate_log_densities": chosen.candidate_log_densities,
        "chosen_candidate": chosen.chosen,
        "start_search_calls": start_search_calls,
        "telemetry_fields": FIELDS, "stop_reasons": STOPS,
    });
    let o = v.as_object_mut().unwrap();
    let recorder = Recorder {
        begin: Instant::now(),
        last: Mutex::new(vec![Instant::now(); CHAINS]),
        rows: Mutex::new(vec![Vec::new(); CHAINS]),
    };
    for i in 0..SLOTS {
        SLOT_CALLS[i].store(0, Ordering::Relaxed);
        SLOT_NS[i].store(0, Ordering::Relaxed);
        SLOT_CHAIN[i].store(0, Ordering::Relaxed);
    }
    let timed = Timed(&target);
    let proposals = NoProposals;
    let control = ProposalObservationControl::new(&proposals, NonZeroUsize::new(1).unwrap(), 0);
    let begin = Instant::now();
    {
        let now = Instant::now();
        *recorder.last.lock().unwrap() = vec![now; CHAINS];
    }
    let result = if plain {
        sampler.run(&target, &chosen.starts)
    } else {
        sampler.run_with_comparison_observers(&timed, &chosen.starts, &control, &recorder)
    };
    let wall = begin.elapsed().as_secs_f64();
    o.insert("wall_seconds".into(), json!(wall));
    o.insert("target_calls_total".into(), json!(target.calls()));
    o.insert("sampling_calls".into(), json!(target.calls() - start_search_calls));
    o.insert("recoverable_failures_total".into(), json!(target.recoverable_failures()));
    // Unfinished-transition work, by the chain last seen on each thread.
    let pending: Vec<_> = (0..SLOTS)
        .filter_map(|i| {
            let calls = SLOT_CALLS[i].load(Ordering::Relaxed);
            (calls > 0).then(|| {
                let chain = SLOT_CHAIN[i].load(Ordering::Relaxed);
                json!({"slot": i, "chain": if chain == 0 { serde_json::Value::Null } else { json!(chain - 1) },
                       "calls": calls, "eval_seconds": SLOT_NS[i].load(Ordering::Relaxed) as f64 / 1e9})
            })
        })
        .collect();
    o.insert("pending_unfinished_transition_work".into(), json!(pending));
    o.insert("telemetry".into(), json!(*recorder.rows.lock().unwrap()));
    let posterior = match result {
        Ok(p) => p,
        Err(e) => {
            o.insert("status".into(), json!("error"));
            o.insert("error_kind".into(), json!(format!("{:?}", e.kind())));
            o.insert("error".into(), json!(e.to_string()));
            fs::write(out, serde_json::to_vec(&v)?)?;
            eprintln!("{arm} seed {seed}: error {:?} after {wall:.1}s: {e}", e.kind());
            return Ok(());
        }
    };
    let max_depth = kernel.max_depth();
    let mut all = Fnv::new();
    let chains = posterior
        .chains()
        .iter()
        .map(|chain| {
            let t = chain.telemetry();
            let (retained, discarded, total) = (t.retained(), t.discarded(), t.total());
            let mut depth_hist = vec![0usize; max_depth + 1];
            for d in &chain.diagnostics()[WARMUP..] {
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
                "samples": samples, "draw_hash": h.hex(),
                "divergences": retained.divergences(),
                "warmup_divergences": discarded.divergences(),
                "nonfinite_position_rejections_total": total.nonfinite_position_rejections(),
                "recoverable_target_failures": total.recoverable_target_failures(),
                "maximum_depth_stops": retained.maximum_depth_stops(),
                "warmup_maximum_depth_stops": discarded.maximum_depth_stops(),
                "refinement_exhaustions": retained.refinement_exhaustion_stops(),
                "retained_target_calls": retained.target_calls_total(),
                "warmup_target_calls": discarded.target_calls_total(),
                "total_target_calls": total.target_calls_total(),
                "final_step_size": chain.metadata().tuning().step_size(),
                "final_max_depth": chain.metadata().tuning().max_depth(),
                "mass_diagonal": chain.metadata().mass_diagonal(),
                "retained_depth_histogram": depth_hist,
            })
        })
        .collect::<Vec<_>>();
    let warnings = posterior.chain_warnings();
    o.insert("status".into(), json!("ok"));
    o.insert("draw_hash".into(), json!(all.hex()));
    o.insert("chains_data".into(), json!(chains));
    o.insert("chain_warnings".into(), json!(warnings.iter().map(|w| format!("{w:?}")).collect::<Vec<_>>()));
    o.insert("chain_warning_chains".into(), json!(warnings.iter().map(|w| w.chain()).collect::<Vec<_>>()));
    o.insert("algorithm_revision".into(), json!(posterior.algorithm_revision()));
    o.insert("timing_estimand".into(), json!("wall around Sampler::run*; contended shared machine"));
    fs::write(out, serde_json::to_vec(&v)?)?;
    eprintln!("{arm} seed {seed}: ok wall {wall:.2}s hash {}", all.hex());
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let plain = args.iter().any(|a| a == "--plain");
    let args: Vec<_> = args.into_iter().filter(|a| a != "--plain").collect();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [model, data, arm, seed, out, timeout, rest @ ..] => {
            let threads = rest.first().map_or(Ok(CHAINS), |t| t.parse::<usize>());
            match (seed.parse::<u64>(), timeout.parse::<f64>(), threads) {
                (Ok(s), Ok(to), Ok(t)) => run(
                    Path::new(model), Path::new(data), arm, s, Path::new(out), to, t, plain,
                ),
                _ => Err("seed, timeout and threads must be numbers".into()),
            }
        }
        _ => Err("usage: <model.so> <data.json> <arm> <seed> <out.json> <timeout_s> [threads] [--plain]".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
