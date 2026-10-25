//! WP58 Rust-harness arm: one (target, arm, seed) cell of the nutpie
//! per-gradient gap decomposition (`STUDIES/nutpie_per_gradient_gap_v1`).
//!
//! Usage:
//! `gap-harness <kind> <path1|-> <path2|-> <arm> <seed> <out.json> <draws.bin> <threads> <mass.json|->`
//!
//! * `kind` = `gauss100` | `eight` | `hier` (native Rust densities, the WP47
//!   numpy/numba layout; `hier` reads its data from `path1`) or `stan`
//!   (`path1` = BridgeStan `*_model.so`, `path2` = data JSON).
//! * `arm` = `default` | `delta2` | `levels1` | `meanaccept` | `nutslike` |
//!   `nutpiemetric` (see `protocol.json`; `nutpiemetric` needs `mass.json`, a
//!   JSON list holding the momentum-covariance diagonal).
//!
//! Starts are `owalnuts::sampler::Init::default()` (best-of-16 since WP52),
//! drawn here with `candidate_starts` so that the start-selection calls can be
//! recorded separately; `Sampler::run` from those starts is identical to
//! `run_with_init(&target, &Init::default())`. Every target call goes through a
//! counting wrapper so the harness's own count can be compared with the
//! kernel telemetry. Draws are written as little-endian f64,
//! (chains, draws, dim) row-major.
#![forbid(unsafe_code)]

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_WARMUP_EXHAUSTION, Init, Limits, Metric,
    Sampler, StartSelection, Target, TargetError, Tuning, WarmupConfig, candidate_starts,
};
use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DualAveragingAcceptance, ExhaustionRule, KernelOptions, WorkTotals,
};
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::{Value, json};
use std::{
    env,
    error::Error,
    fs,
    io::Write,
    path::Path,
    sync::atomic::{AtomicUsize, Ordering},
    time::Instant,
};

const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;
const TARGET_ACCEPT: f64 = 0.8;

// ── native targets (WP47 layout) ────────────────────────────────────────

const Y8: [f64; 8] = [28.0, 8.0, -3.0, 7.0, -1.0, 1.0, 18.0, 12.0];
const SE8: [f64; 8] = [15.0, 10.0, 16.0, 11.0, 9.0, 11.0, 10.0, 18.0];

enum Native {
    Gauss100,
    Eight,
    Hier { x: Vec<f64>, y: Vec<f64> }, // x: (50, 20, 3), y: (50, 20)
}

impl Native {
    fn dim(&self) -> usize {
        match self {
            Native::Gauss100 => 100,
            Native::Eight => 10,
            Native::Hier { .. } => 157,
        }
    }
    fn eval(&self, q: &[f64], g: &mut [f64]) -> f64 {
        match self {
            Native::Gauss100 => {
                let mut s = 0.0;
                for i in 0..q.len() {
                    g[i] = -q[i];
                    s += q[i] * q[i];
                }
                -0.5 * s
            }
            Native::Eight => {
                let mu = q[0];
                let log_tau = q[1];
                let tau = log_tau.exp();
                let mut value = -0.02 * mu * mu - (tau * tau / 25.0).ln_1p() + log_tau;
                let mut g0 = -mu / 25.0;
                let mut g1 = 1.0 - 2.0 * tau * tau / (25.0 + tau * tau);
                for i in 0..8 {
                    let z = q[2 + i];
                    let resid = Y8[i] - (mu + tau * z);
                    let lg = resid / (SE8[i] * SE8[i]);
                    value += -0.5 * resid * lg - 0.5 * z * z;
                    g0 += lg;
                    g1 += tau * lg * z;
                    g[2 + i] = tau * lg - z;
                }
                g[0] = g0;
                g[1] = g1;
                value
            }
            Native::Hier { x, y } => {
                let (nj, ni, k) = (50usize, 20usize, 3usize);
                let n = (nj * ni) as f64;
                let mut tau = [0.0; 3];
                let mut value = 0.0;
                for kk in 0..k {
                    tau[kk] = q[3 + kk].exp();
                    value += -0.02 * q[kk] * q[kk] + q[3 + kk] - 0.5 * tau[kk] * tau[kk];
                    g[kk] = -q[kk] / 25.0;
                    g[3 + kk] = 1.0 - tau[kk] * tau[kk];
                }
                let log_sigma = q[156];
                let sigma = log_sigma.exp();
                let inv_s2 = 1.0 / (sigma * sigma);
                let mut ss = 0.0;
                for j in 0..nj {
                    let mut beta = [0.0; 3];
                    for kk in 0..k {
                        let z = q[6 + 3 * j + kk];
                        value += -0.5 * z * z;
                        beta[kk] = q[kk] + tau[kk] * z;
                    }
                    let mut gb = [0.0; 3];
                    for i in 0..ni {
                        let base = (j * ni + i) * k;
                        let r = y[j * ni + i]
                            - (x[base] * beta[0] + x[base + 1] * beta[1] + x[base + 2] * beta[2]);
                        ss += r * r;
                        for kk in 0..k {
                            gb[kk] += r * x[base + kk];
                        }
                    }
                    for kk in 0..k {
                        let gbk = gb[kk] * inv_s2;
                        let z = q[6 + 3 * j + kk];
                        g[kk] += gbk;
                        g[3 + kk] += tau[kk] * gbk * z;
                        g[6 + 3 * j + kk] = gbk * tau[kk] - z;
                    }
                }
                value += log_sigma - 0.5 * sigma * sigma - n * log_sigma - 0.5 * ss * inv_s2;
                g[156] = 1.0 - sigma * sigma - n + ss * inv_s2;
                value
            }
        }
    }
}

impl Target for Native {
    fn dimension(&self) -> usize {
        self.dim()
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        let v = self.eval(q, g);
        if v.is_finite() && g.iter().all(|x| x.is_finite()) {
            Ok(v)
        } else {
            Err(TargetError::recoverable("nonfinite native evaluation"))
        }
    }
}

/// Counts every log-density-and-gradient call made through it.
struct Counted<T> {
    inner: T,
    calls: AtomicUsize,
}

impl<T: Target> Target for Counted<T> {
    fn dimension(&self) -> usize {
        self.inner.dimension()
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        self.inner.log_density_gradient(q, g)
    }
}

// ── arms ────────────────────────────────────────────────────────────────

fn mean_accept_warmup() -> Result<WarmupConfig, Box<dyn Error>> {
    // The sampler's own `DualAveraging` warmup (`Adaptation::warmup_config`'s
    // defaults) with only the dual-averaging statistic changed to Stan's
    // `accept_stat__`.
    Ok(WarmupConfig::new(TARGET_ACCEPT)?
        .with_dual_averaging_acceptance(DualAveragingAcceptance::MeanTrajectoryAcceptance)
        .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
        .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION))
}

fn configure(
    arm: &str,
    dim: usize,
    mass: Option<Vec<f64>>,
) -> Result<(Tuning, Adaptation, Metric), Box<dyn Error>> {
    let base = Tuning::default();
    Ok(match arm {
        "default" => (base, Adaptation::default(), Metric::diagonal()),
        "delta2" => (base.max_error(2.0), Adaptation::default(), Metric::diagonal()),
        "levels1" => (
            base.max_refinement_levels(1),
            Adaptation::default(),
            Metric::diagonal(),
        ),
        "meanaccept" => (
            base,
            Adaptation::Custom(mean_accept_warmup()?),
            Metric::diagonal(),
        ),
        "nutslike" => {
            let options = KernelOptions {
                exhaustion: ExhaustionRule::AcceptUnlessDivergent,
                ..Tuning::default().to_kernel()?.options()
            };
            (
                base.max_refinement_levels(1).kernel_options(options),
                Adaptation::Custom(mean_accept_warmup()?),
                Metric::diagonal(),
            )
        }
        "nutpiemetric" => {
            let m = mass.ok_or("nutpiemetric needs a mass.json")?;
            if m.len() != dim {
                return Err(format!("mass length {} != dim {dim}", m.len()).into());
            }
            (base, Adaptation::default(), Metric::fixed_diagonal(m))
        }
        other => Err(format!("unknown arm {other:?}"))?,
    })
}

fn work_json(w: &WorkTotals) -> Value {
    json!({
        "transitions": w.transitions(),
        "target_calls_total": w.target_calls_total(),
        "target_calls_initial": w.target_calls_initial(),
        "target_calls_forward": w.target_calls_forward(),
        "target_calls_reverse": w.target_calls_reverse(),
        "leaves_attempted": w.leaves_attempted(),
        "leaves_built": w.leaves_built(),
        "refinement_level_built": w.refinement_level_built(),
        "divergences": w.divergences(),
        "maximum_depth_stops": w.maximum_depth_stops(),
        "refinement_exhaustion_stops": w.refinement_exhaustion_stops(),
        "invalid_evaluation_stops": w.invalid_evaluation_stops(),
        "reverse_coarser_stops": w.reverse_coarser_stops(),
        "recoverable_target_failures": w.recoverable_target_failures(),
        "nonfinite_position_rejections": w.nonfinite_position_rejections(),
    })
}

fn mean(xs: impl Iterator<Item = f64>) -> f64 {
    let (s, n) = xs.fold((0.0, 0usize), |(s, n), x| (s + x, n + 1));
    if n == 0 { f64::NAN } else { s / n as f64 }
}

#[allow(clippy::too_many_arguments)]
fn run<T: Target>(
    target: T,
    target_label: Value,
    arm: &str,
    seed: u64,
    out: &Path,
    bin: &Path,
    threads: usize,
    mass: Option<Vec<f64>>,
) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    let target = Counted {
        inner: target,
        calls: AtomicUsize::new(0),
    };
    let dim = target.dimension();
    let (tuning, adaptation, metric) = configure(arm, dim, mass)?;
    let kernel = tuning.to_kernel()?;
    let sampler = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .seed(seed)
        .threads(threads)
        .metric(metric)
        .adaptation(adaptation.clone())
        .tuning(tuning)
        .limits(Limits::new().admit_worst_case());

    let (radius, candidates, max_attempts, selection) = match Init::default() {
        Init::Candidates {
            radius,
            candidates,
            max_attempts,
            selection,
        } => (radius, candidates, max_attempts, selection),
        _ => return Err("Init::default() is no longer Init::Candidates".into()),
    };
    assert_eq!(selection, StartSelection::HighestDensity);
    let chosen = candidate_starts(
        &target,
        CHAINS,
        seed,
        radius,
        candidates,
        max_attempts,
        selection,
    )?;
    let start_calls_counted = target.calls.load(Ordering::Relaxed);

    let begin = Instant::now();
    let result = sampler.run(&target, &chosen.starts);
    let wall = begin.elapsed().as_secs_f64();
    let posterior = match result {
        Ok(p) => p,
        Err(e) => {
            let payload = json!({"status": "error", "stage": "sample", "error": e.to_string(),
                "arm": arm, "seed": seed, "target": target_label, "wall_seconds": wall,
                "counted_calls_total": target.calls.load(Ordering::Relaxed)});
            fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
            return Err(e.into());
        }
    };
    let counted_total = target.calls.load(Ordering::Relaxed);

    let mut f = fs::File::create(bin)?;
    let mut buf = Vec::with_capacity(CHAINS * RETAINED * dim * 8);
    for chain in posterior.chains() {
        for x in chain.samples() {
            buf.extend_from_slice(&x.to_le_bytes());
        }
    }
    f.write_all(&buf)?;

    let chains: Vec<Value> = posterior
        .chains()
        .iter()
        .map(|chain| {
            let t = chain.telemetry();
            let diags = chain.diagnostics();
            let (warm, kept) = diags.split_at(WARMUP);
            let tail = &warm[WARMUP.saturating_sub(100)..];
            json!({
                "work_retained": work_json(t.retained()),
                "work_discarded": work_json(t.discarded()),
                "work_total": work_json(t.total()),
                "final_step_size": chain.metadata().tuning().step_size(),
                "final_max_error": chain.metadata().tuning().max_error(),
                "mass_diagonal": chain.metadata().mass_diagonal(),
                "retained_mean_depth": mean(kept.iter().map(|d| d.depth() as f64)),
                "retained_mean_target_evaluations": mean(kept.iter().map(|d| d.target_evaluations() as f64)),
                "retained_mean_leaves_built": mean(kept.iter().map(|d| d.leaves_built() as f64)),
                "retained_mean_orbit_states": mean(kept.iter().map(|d| d.orbit_states() as f64)),
                "retained_mean_macro_length": mean(kept.iter().map(|d| d.trajectory_macro_length())),
                "retained_fraction_selected_refined": mean(kept.iter().map(|d| match d.selected_refinement_level() { Some(l) if l > 0 => 1.0, _ => 0.0 })),
                "warmup_last100_mean_acceptance_statistic": mean(tail.iter().filter_map(|d| d.acceptance_statistic())),
                "warmup_last100_acceptance_count": tail.iter().filter(|d| d.acceptance_statistic().is_some()).count(),
                "retained_depth": kept.iter().map(|d| d.depth()).collect::<Vec<_>>(),
                "retained_target_evaluations": kept.iter().map(|d| d.target_evaluations()).collect::<Vec<_>>(),
            })
        })
        .collect();
    let kernel_calls: usize = posterior.total_target_calls();
    let payload = json!({
        "schema": "nutpie-gap-v1-rust-cell",
        "status": "ok",
        "arm": arm, "seed": seed, "target": target_label, "dimension": dim,
        "chains": CHAINS, "warmup": WARMUP, "retained": RETAINED, "threads": threads,
        "init": {"rule": "sampler::Init::default() via candidate_starts", "radius": radius,
                 "candidates": candidates, "max_attempts": max_attempts,
                 "evaluations_per_chain": chosen.evaluations,
                 "start_log_densities": chosen.start_log_densities},
        "tuning": {"step_size": kernel.step_size(), "max_depth": kernel.max_depth(),
                   "max_refinement_levels": kernel.max_refinement_levels(),
                   "max_error": kernel.max_error(),
                   "divergence_threshold": kernel.divergence_threshold(),
                   "u_turn": format!("{:?}", kernel.options().u_turn),
                   "exhaustion": format!("{:?}", kernel.options().exhaustion)},
        "adaptation": format!("{adaptation:?}"),
        "wall_seconds": wall,
        "counted_calls_total": counted_total,
        "counted_calls_start_selection": start_calls_counted,
        "counted_calls_sampler": counted_total - start_calls_counted,
        "kernel_total_target_calls": kernel_calls,
        "chains_data": chains,
        "algorithm_revision": posterior.algorithm_revision(),
        "algorithm_revision_const": ALGORITHM_REVISION,
        "draws_file": bin.display().to_string(),
    });
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    eprintln!("{arm} seed {seed}: wall {wall:.2}s counted {counted_total} kernel {kernel_calls}");
    Ok(())
}

fn read_hier(path: &Path) -> Result<Native, Box<dyn Error>> {
    let v: Value = serde_json::from_str(&fs::read_to_string(path)?)?;
    let flat = |key: &str| -> Result<Vec<f64>, Box<dyn Error>> {
        v[key]
            .as_array()
            .ok_or("missing array")?
            .iter()
            .map(|x| x.as_f64().ok_or_else(|| "non-number".into()))
            .collect()
    };
    let x = flat("x_flat")?;
    let y = flat("y_flat")?;
    if x.len() != 50 * 20 * 3 || y.len() != 50 * 20 {
        return Err("hier data has the wrong shape".into());
    }
    Ok(Native::Hier { x, y })
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = (|| {
        let [kind, p1, p2, arm, seed, out, bin, threads, mass] = args.as_slice() else {
            return Err("usage: <kind> <path1|-> <path2|-> <arm> <seed> <out.json> <draws.bin> <threads> <mass.json|->".into());
        };
        let seed: u64 = seed.parse()?;
        let threads: usize = threads.parse()?;
        let mass: Option<Vec<f64>> = if mass == "-" || arm == "eval" {
            None
        } else {
            Some(serde_json::from_str(&fs::read_to_string(mass)?)?)
        };
        let (out, bin) = (Path::new(out), Path::new(bin));
        if arm == "eval" {
            // Setup check only: evaluate the native density at the positions in `mass.json`.
            let native = match kind.as_str() {
                "gauss100" => Native::Gauss100,
                "eight" => Native::Eight,
                "hier" => read_hier(Path::new(p1))?,
                other => return Err(format!("eval supports native kinds only, not {other:?}").into()),
            };
            let points: Vec<Vec<f64>> = serde_json::from_str(&fs::read_to_string(&args[8])?)?;
            let evals: Vec<Value> = points.iter().map(|q| {
                let mut g = vec![0.0; native.dim()];
                let v = native.eval(q, &mut g);
                json!({"logp": v, "grad": g})
            }).collect();
            fs::write(out, serde_json::to_vec(&evals)?)?;
            return Ok(());
        }
        match kind.as_str() {
            "gauss100" => run(Native::Gauss100, json!("native:gauss100"), arm, seed, out, bin, threads, mass),
            "eight" => run(Native::Eight, json!("native:eight"), arm, seed, out, bin, threads, mass),
            "hier" => run(read_hier(Path::new(p1))?, json!("native:hier"), arm, seed, out, bin, threads, mass),
            "stan" => {
                let data = fs::read_to_string(p2)?;
                let t = ReplicatedStanTarget::load(Path::new(p1), &default_preload(), Some(&data), 1, threads)?;
                let label = json!({"stan_library": p1, "data": p2, "replicas": t.replicas()});
                run(t, label, arm, seed, out, bin, threads, mass)
            }
            other => Err(format!("unknown kind {other:?}").into()),
        }
    })();
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
