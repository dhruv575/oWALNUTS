//! WP78 pure-Rust reference arm (`STUDIES/python_callpath_linux_v1`).
//!
//! The native densities are WP58's (`STUDIES/nutpie_per_gradient_gap_v1/rust`),
//! which reproduce the WP47 numba kernels operation for operation in the
//! shared PyMC unconstrained layout. The sampler is `owalnuts::sampler::Sampler`
//! at its defaults, configured exactly as the Python package configures it
//! (`warmup`, `draws`, `chains`, `seed`, `threads`, `Limits::admit_worst_case`),
//! with starts from `Init::default()` (best-of-16) drawn by `candidate_starts`
//! so the start-selection calls are counted separately.
//!
//! Usage:
//! * `wp78-rust cell <kind> <hier_data|-> <seed> <threads> <out.json> <draws.bin>`
//! * `wp78-rust micro <kind> <hier_data|-> <points.json> <calls> <out.json>`
//! * `wp78-rust eval <kind> <hier_data|-> <points.json> <out.json>` (setup check)
//!
//! `kind` = `gauss100` | `eight` | `hier`. Draws are little-endian f64,
//! (chains, draws, dim) row-major.
#![forbid(unsafe_code)]

use owalnuts::sampler::{
    Adaptation, Init, Limits, Metric, Sampler, StartSelection, Target, TargetError, Tuning,
    candidate_starts,
};
use owalnuts::walnutpie::{ALGORITHM_REVISION, WorkTotals};
use serde_json::{Value, json};
use std::{
    env,
    error::Error,
    fs,
    hint::black_box,
    io::Write,
    path::Path,
    sync::atomic::{AtomicUsize, Ordering},
    time::Instant,
};

const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;

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

/// Counts every call; one relaxed atomic increment per gradient (a few ns),
/// the same order as the Python transports' own call counters.
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

fn work_json(w: &WorkTotals) -> Value {
    json!({
        "transitions": w.transitions(),
        "target_calls_total": w.target_calls_total(),
        "target_calls_initial": w.target_calls_initial(),
        "target_calls_forward": w.target_calls_forward(),
        "target_calls_reverse": w.target_calls_reverse(),
        "leaves_built": w.leaves_built(),
        "divergences": w.divergences(),
        "maximum_depth_stops": w.maximum_depth_stops(),
        "refinement_exhaustion_stops": w.refinement_exhaustion_stops(),
        "recoverable_target_failures": w.recoverable_target_failures(),
        "nonfinite_position_rejections": w.nonfinite_position_rejections(),
    })
}

fn mean(xs: impl Iterator<Item = f64>) -> f64 {
    let (s, n) = xs.fold((0.0, 0usize), |(s, n), x| (s + x, n + 1));
    if n == 0 { f64::NAN } else { s / n as f64 }
}

fn cell(
    native: Native,
    kind: &str,
    seed: u64,
    threads: usize,
    out: &Path,
    bin: &Path,
) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    let target = Counted {
        inner: native,
        calls: AtomicUsize::new(0),
    };
    let dim = target.dimension();
    let sampler = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .seed(seed)
        .threads(threads)
        .metric(Metric::diagonal())
        .adaptation(Adaptation::default())
        .tuning(Tuning::default())
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
    let begin_total = Instant::now();
    let chosen = candidate_starts(
        &target,
        CHAINS,
        seed,
        radius,
        candidates,
        max_attempts,
        selection,
    )?;
    let start_calls = target.calls.load(Ordering::Relaxed);
    let begin = Instant::now();
    let result = sampler.run(&target, &chosen.starts);
    let wall = begin.elapsed().as_secs_f64();
    let wall_total = begin_total.elapsed().as_secs_f64();
    let posterior = match result {
        Ok(p) => p,
        Err(e) => {
            let payload = json!({"status": "error", "stage": "sample", "error": e.to_string(),
                "kind": kind, "seed": seed, "threads": threads, "wall_seconds": wall,
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
            let (_warm, kept) = diags.split_at(WARMUP);
            json!({
                "work_retained": work_json(t.retained()),
                "work_discarded": work_json(t.discarded()),
                "work_total": work_json(t.total()),
                "final_step_size": chain.metadata().tuning().step_size(),
                "retained_mean_depth": mean(kept.iter().map(|d| d.depth() as f64)),
            })
        })
        .collect();
    let payload = json!({
        "schema": "wp78-rust-cell",
        "status": "ok",
        "kind": kind, "seed": seed, "threads": threads, "dimension": dim,
        "chains": CHAINS, "warmup": WARMUP, "retained": RETAINED,
        "init": {"rule": "sampler::Init::default() via candidate_starts", "radius": radius,
                 "candidates": candidates, "max_attempts": max_attempts,
                 "evaluations_per_chain": chosen.evaluations,
                 "start_log_densities": chosen.start_log_densities},
        "wall_seconds": wall,
        "wall_seconds_with_starts": wall_total,
        "counted_calls_total": counted_total,
        "counted_calls_start_selection": start_calls,
        "counted_calls_sampler": counted_total - start_calls,
        "kernel_total_target_calls": posterior.total_target_calls(),
        "chains_data": chains,
        "algorithm_revision": posterior.algorithm_revision(),
        "algorithm_revision_const": ALGORITHM_REVISION,
    });
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    Ok(())
}

fn read_points(path: &str) -> Result<Vec<Vec<f64>>, Box<dyn Error>> {
    Ok(serde_json::from_str(&fs::read_to_string(path)?)?)
}

/// Median / p10 / p90 of `calls` individually timed evaluations (cycling over
/// the points), plus the mean of `calls` evaluations in one untimed loop
/// (median of five repeats), as WP47's `njit_loop_mean`.
fn micro(native: Native, points: &[Vec<f64>], calls: usize) -> Value {
    let dim = native.dim();
    let mut g = vec![0.0; dim];
    for _ in 0..8 {
        for q in points {
            black_box(native.eval(black_box(q), &mut g));
        }
    }
    let mut ns = Vec::with_capacity(calls);
    for i in 0..calls {
        let q = &points[i % points.len()];
        let a = Instant::now();
        black_box(native.eval(black_box(q), &mut g));
        ns.push(a.elapsed().as_nanos() as f64);
    }
    // Timer overhead: an empty timed interval.
    let mut empty = Vec::with_capacity(calls);
    for _ in 0..calls {
        let a = Instant::now();
        empty.push(black_box(a).elapsed().as_nanos() as f64);
    }
    let mut reps = Vec::new();
    for _ in 0..5 {
        let a = Instant::now();
        let mut s = 0.0;
        for i in 0..calls {
            s += native.eval(black_box(&points[i % points.len()]), &mut g);
        }
        black_box(s);
        reps.push(a.elapsed().as_nanos() as f64 / calls as f64);
    }
    let q = |v: &mut Vec<f64>, p: f64| {
        v.sort_by(|a, b| a.partial_cmp(b).unwrap());
        v[((v.len() - 1) as f64 * p).round() as usize]
    };
    json!({
        "median_us": q(&mut ns, 0.5) / 1e3,
        "p10_us": q(&mut ns, 0.1) / 1e3,
        "p90_us": q(&mut ns, 0.9) / 1e3,
        "timer_overhead_median_us": q(&mut empty, 0.5) / 1e3,
        "loop_mean_us": q(&mut reps, 0.5) / 1e3,
        "calls": calls,
    })
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

fn native(kind: &str, hier: &str) -> Result<Native, Box<dyn Error>> {
    Ok(match kind {
        "gauss100" => Native::Gauss100,
        "eight" => Native::Eight,
        "hier" => read_hier(Path::new(hier))?,
        other => return Err(format!("unknown kind {other:?}").into()),
    })
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = (|| match args.first().map(String::as_str) {
        Some("cell") => {
            let [_, kind, hier, seed, threads, out, bin] = args.as_slice() else {
                return Err("usage: cell <kind> <hier|-> <seed> <threads> <out.json> <draws.bin>".into());
            };
            cell(
                native(kind, hier)?,
                kind,
                seed.parse()?,
                threads.parse()?,
                Path::new(out),
                Path::new(bin),
            )
        }
        Some("micro") => {
            let [_, kind, hier, points, calls, out] = args.as_slice() else {
                return Err("usage: micro <kind> <hier|-> <points.json> <calls> <out.json>".into());
            };
            let rec = micro(native(kind, hier)?, &read_points(points)?, calls.parse()?);
            fs::write(out, serde_json::to_vec_pretty(&rec)?)?;
            Ok(())
        }
        Some("eval") => {
            let [_, kind, hier, points, out] = args.as_slice() else {
                return Err("usage: eval <kind> <hier|-> <points.json> <out.json>".into());
            };
            let n = native(kind, hier)?;
            let evals: Vec<Value> = read_points(points)?
                .iter()
                .map(|q| {
                    let mut g = vec![0.0; n.dim()];
                    let v = n.eval(q, &mut g);
                    json!({"logp": v, "grad": g})
                })
                .collect();
            fs::write(out, serde_json::to_vec(&evals)?)?;
            Ok(())
        }
        _ => Err("usage: wp78-rust cell|micro|eval ...".into()),
    })();
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
