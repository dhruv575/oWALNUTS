//! WP88 oWALNUTS arms for `STUDIES/online_sv_quote_v2`.
//!
//! Target: the market_uncertainty_v1 price-only SV model (intercept beta, no flow columns),
//! q = [mu, log_sigma, beta, z[n]], rho = 0.95 and nu = 5 fixed, exact normalized density
//! (identical to the WP84 harness, `STUDIES/online_sv_quote_v1/rust/src/main.rs`).
//!
//! Modes:
//! * `wp88 eval <data.json> <n> <points.json> <out.json>`         density/gradient check
//! * `wp88 reftick <data.json> <n_obs> <seed> <outstem>`           one 4 x 2,000/20,000 fit on the
//!   first `n_obs` returns -> `<outstem>.f32` + `<outstem>.json` (the gate is applied by the
//!   Python driver, which may call this again with the next preregistered seed)
//! * `wp88 refit <data.json> <N> <seed> <ticks> <outdir>`          4 x 1,000/1,000 per tick
//! * `wp88 warm <data.json> <N> <K> <seed> <ticks> <outdir>`       tick-0 fit, chain gate, then
//!   `Sampler::run_warm` on a `WarmState` extended by one coordinate per tick
//! * `wp88 bitcheck <data.json> <N> <K> <seed> <out.json>`         `run_warm` vs the WP84 harness
//!   construction (one single-chain `Sampler` per chain) for tick 1, bit-for-bit
//!
//! Every tick writes `tick-XXX.f32` (little-endian f32, [chain][draw][3] = mu, log_sigma, h_n)
//! and one JSON line in `ticks.jsonl` (`chains` and `draws` give the shape).
//!
//! The warm arm is the LIBRARY path (WP87): `Posterior::warm_state()` after the tick-0 fit,
//! chains named by a `WarmupStep` / `SampledLogDensity` warning dropped (the chain gate),
//! then per tick `WarmState::extend_to(n + 1, 0.0, 1.0)` (new innovation at its prior median
//! with prior variance 1) and `Sampler::run_warm` with `draws(K)`; the result's `warm_state()`
//! is the next state. No re-adaptation: step and metric stay those of the tick-0 fit. The
//! per-tick seed is `seed * 1_000_003 + 16 * tick`, so chain `c` runs on `seed + c` exactly
//! as the WP84 harness seeded it.
#![forbid(unsafe_code)]

use owalnuts::diagnostics::ChainWarning;
use owalnuts::sampler::{
    Adaptation, Limits, Metric, Posterior, Sampler, Target, TargetError, Tuning, WarmChain,
    WarmState,
};
use serde_json::{Value, json};
use std::{
    env,
    error::Error,
    fs,
    io::Write,
    num::NonZeroUsize,
    path::{Path, PathBuf},
    sync::atomic::{AtomicUsize, Ordering},
    time::Instant,
};

const CHAINS: usize = 4;
/// Result-size ceiling for the reference (`Limits::max_result_bytes_unchecked`): the N = 1,000
/// reference (4 x 22,000 x 1,004-D draws, about 707 MB) exceeds the 512 MiB default.
const REF_RESULT_BYTES: usize = 2 << 30;

struct Data {
    y: Vec<f64>,
    rho: f64,
    nu: f64,
    mu_mean: f64,
    mu_sd: f64,
    ls_mean: f64,
    ls_sd: f64,
    beta_sd: f64,
}

fn load(path: &Path) -> Result<Data, Box<dyn Error>> {
    let v: Value = serde_json::from_slice(&fs::read(path)?)?;
    let p = &v["priors"];
    let f = |x: &Value| x.as_f64().ok_or("bad number");
    Ok(Data {
        y: v["y"]
            .as_array()
            .ok_or("y")?
            .iter()
            .map(|x| x.as_f64().unwrap())
            .collect(),
        rho: f(&v["rho"])?,
        nu: f(&v["nu"])?,
        mu_mean: f(&p["mu_mean"])?,
        mu_sd: f(&p["mu_sd"])?,
        ls_mean: f(&p["log_sigma_mean"])?,
        ls_sd: f(&p["log_sigma_sd"])?,
        beta_sd: f(&p["beta_sd"])?,
    })
}

struct Sv<'a> {
    d: &'a Data,
    n: usize,
    cst: f64,
    calls: AtomicUsize,
}

impl<'a> Sv<'a> {
    fn new(d: &'a Data, n: usize) -> Self {
        assert!(n <= d.y.len(), "n = {n} exceeds the series length {}", d.y.len());
        let nu = d.nu;
        let cst = lgamma((nu + 1.) / 2.) - lgamma(nu / 2.) - 0.5 * (nu * std::f64::consts::PI).ln();
        Sv { d, n, cst, calls: AtomicUsize::new(0) }
    }
    fn h_last(&self, q: &[f64]) -> f64 {
        let (mu, s, rho) = (q[0], q[1].exp(), self.d.rho);
        let mut h = mu + s * q[3] / (1. - rho * rho).sqrt();
        for i in 1..self.n {
            h = mu + rho * (h - mu) + s * q[3 + i];
        }
        h
    }
}

fn lgamma(x: f64) -> f64 {
    // Lanczos (g = 7, n = 9); only called with x = nu/2, (nu+1)/2 > 0.
    const C: [f64; 9] = [
        0.999_999_999_999_809_9,
        676.520_368_121_885_1,
        -1_259.139_216_722_402_8,
        771.323_428_777_653_1,
        -176.615_029_162_140_6,
        12.507_343_278_686_905,
        -0.138_571_095_265_720_12,
        9.984_369_578_019_572e-6,
        1.505_632_735_149_311_6e-7,
    ];
    let x = x - 1.;
    let mut a = C[0];
    let t = x + 7.5;
    for (i, c) in C.iter().enumerate().skip(1) {
        a += c / (x + i as f64);
    }
    0.5 * (2. * std::f64::consts::PI).ln() + (x + 0.5) * t.ln() - t + a.ln()
}

impl Target for Sv<'_> {
    fn dimension(&self) -> usize {
        3 + self.n
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        let d = self.d;
        let (n, rho, nu) = (self.n, d.rho, d.nu);
        let ln2pi = (2. * std::f64::consts::PI).ln();
        let (mu, ls, beta) = (q[0], q[1], q[2]);
        let sigma = ls.exp();
        let norm = |x: f64, m: f64, s: f64, g: &mut f64| -> f64 {
            let u = (x - m) / s;
            *g = -u / s;
            -0.5 * u * u - s.ln() - 0.5 * ln2pi
        };
        let mut lp = norm(mu, d.mu_mean, d.mu_sd, &mut g[0]);
        lp += norm(ls, d.ls_mean, d.ls_sd, &mut g[1]);
        lp += norm(beta, 0., d.beta_sd, &mut g[2]);
        for i in 0..n {
            let z = q[3 + i];
            lp += -0.5 * z * z - 0.5 * ln2pi;
            g[3 + i] = -z;
        }
        let s0 = sigma / (1. - rho * rho).sqrt();
        let mut h = vec![0.; n];
        h[0] = mu + s0 * q[3];
        for i in 1..n {
            h[i] = mu + rho * (h[i - 1] - mu) + sigma * q[3 + i];
        }
        let mut dh = vec![0.; n];
        for i in 0..n {
            let r = d.y[i] - beta;
            let e = (-h[i]).exp();
            let a = r * r * e / nu;
            lp += self.cst - 0.5 * h[i] - 0.5 * (nu + 1.) * a.ln_1p();
            dh[i] = -0.5 + 0.5 * (nu + 1.) * a / (1. + a);
            g[2] += (nu + 1.) * r * e / nu / (1. + a);
        }
        for i in (0..n).rev() {
            let m = if i == 0 { s0 } else { sigma };
            g[3 + i] += dh[i] * m;
            g[1] += dh[i] * m * q[3 + i];
            g[0] += dh[i] * if i == 0 { 1. } else { 1. - rho };
            if i > 0 {
                dh[i - 1] += rho * dh[i];
            }
        }
        // Recoverable zero-density result: the proposal is rejected, as Stan rejects it.
        if !lp.is_finite() || g.iter().any(|x| !x.is_finite()) {
            return Err(TargetError::recoverable("non-finite log density or gradient"));
        }
        Ok(lp)
    }
}

fn write_draws(path: &Path, sv: &Sv, chains: &[&[f64]]) -> Result<(), Box<dyn Error>> {
    let dim = sv.dimension();
    let mut buf = Vec::new();
    for c in chains {
        for q in c.chunks(dim) {
            for x in [q[0], q[1], sv.h_last(q)] {
                buf.extend_from_slice(&(x as f32).to_le_bytes());
            }
        }
    }
    fs::File::create(path)?.write_all(&buf)?;
    Ok(())
}

fn write_posterior(path: &Path, sv: &Sv, p: &Posterior) -> Result<(), Box<dyn Error>> {
    let chains: Vec<&[f64]> = p.chains().iter().map(|c| c.samples()).collect();
    write_draws(path, sv, &chains)
}

/// Chains named by the gate warnings (`WarmupStep`, `SampledLogDensity`), sorted, unique.
fn flagged(p: &Posterior) -> Vec<usize> {
    let mut out: Vec<usize> = p
        .chain_warnings()
        .iter()
        .filter(|w| {
            matches!(
                w,
                ChainWarning::WarmupStep { .. } | ChainWarning::SampledLogDensity { .. }
            )
        })
        .map(ChainWarning::chain)
        .collect();
    out.sort_unstable();
    out.dedup();
    out
}

fn divergences(p: &Posterior, skip: usize) -> Vec<usize> {
    p.chains()
        .iter()
        .map(|c| c.diagnostics()[skip..].iter().filter(|x| x.divergent()).count())
        .collect()
}

/// One full fit at sampler defaults (best-of-16 random starts, diagonal metric).
fn full_fit(
    d: &Data,
    n: usize,
    warmup: usize,
    draws: usize,
    seed: u64,
    result_bytes: Option<usize>,
) -> Result<(Value, Option<Posterior>), Box<dyn Error>> {
    let t0 = Instant::now();
    let sv = Sv::new(d, n);
    let mut limits = Limits::new().admit_worst_case();
    if let Some(bytes) = result_bytes {
        limits = limits.max_result_bytes_unchecked(NonZeroUsize::new(bytes).ok_or("bytes")?);
    }
    let res = Sampler::new()
        .warmup(warmup)
        .draws(draws)
        .chains(CHAINS)
        .seed(seed)
        .threads(CHAINS)
        .limits(limits)
        .run_from_random_starts(&sv);
    let wall = t0.elapsed().as_secs_f64();
    let p = match res {
        Ok(p) => p,
        Err(e) => {
            return Ok((
                json!({"n": n, "status": "error", "error": e.to_string(), "seed": seed,
                    "wall_seconds": wall, "calls": sv.calls.load(Ordering::Relaxed)}),
                None,
            ));
        }
    };
    let steps: Vec<f64> = p.chains().iter().map(|c| c.metadata().tuning().step_size()).collect();
    let warnings: Vec<String> = p.chain_warnings().iter().map(|w| format!("{w:?}")).collect();
    let rec = json!({"n": n, "status": "ok", "wall_seconds": wall, "seed": seed,
        "warmup": warmup, "draws": draws, "chains": CHAINS, "divergences": divergences(&p, warmup),
        "steps": steps, "calls": sv.calls.load(Ordering::Relaxed), "chain_warnings": warnings,
        "flagged": flagged(&p)});
    Ok((rec, Some(p)))
}

fn tick_seed(seed: u64, tick: usize) -> u64 {
    seed.wrapping_mul(1_000_003).wrapping_add((tick * 16) as u64)
}

/// The WP84 harness construction of one warm chain on the grown target: a single-chain
/// sampler with the carried start, step and fixed diagonal mass (new coordinates at 0 with
/// mass 1), no warmup, no adaptation, seed `base + chain`.
fn harness_chain(sv: &Sv, chain: &WarmChain, seed: u64, k: usize) -> Result<Posterior, Box<dyn Error>> {
    let dim = sv.dimension();
    let mut start = chain.position.clone();
    let mut mass = chain.mass_diagonal.clone();
    start.resize(dim, 0.0);
    mass.resize(dim, 1.0);
    Ok(Sampler::new()
        .warmup(0)
        .draws(k)
        .seed(seed)
        .threads(1)
        .metric(Metric::fixed_diagonal(mass))
        .adaptation(Adaptation::None)
        .tuning(Tuning::new().step_size(chain.step_size))
        .limits(Limits::new().admit_worst_case())
        .run(sv, &[start])?)
}

fn main() -> Result<(), Box<dyn Error>> {
    let a: Vec<String> = env::args().collect();
    let mode = a.get(1).map(String::as_str).unwrap_or("");
    let usage = "usage: wp88 eval|reftick|refit|warm|bitcheck ...";
    let d = load(Path::new(a.get(2).ok_or(usage)?))?;
    match mode {
        "eval" => {
            let n: usize = a[3].parse()?;
            let pts: Vec<Vec<f64>> = serde_json::from_slice(&fs::read(&a[4])?)?;
            let sv = Sv::new(&d, n);
            let mut res = Vec::new();
            for q in &pts {
                let mut g = vec![0.; sv.dimension()];
                let lp = sv.log_density_gradient(q, &mut g).map_err(|e| format!("{e:?}"))?;
                res.push(json!({"lp": lp, "grad": g, "h_last": sv.h_last(q)}));
            }
            fs::write(&a[5], serde_json::to_vec(&res)?)?;
            Ok(())
        }
        "reftick" => {
            let n: usize = a[3].parse()?;
            let seed: u64 = a[4].parse()?;
            let stem = PathBuf::from(&a[5]);
            let (rec, p) = full_fit(&d, n, 2000, 20000, seed, Some(REF_RESULT_BYTES))?;
            if let Some(p) = &p {
                write_posterior(&stem.with_extension("f32"), &Sv::new(&d, n), p)?;
            }
            fs::write(stem.with_extension("json"), serde_json::to_vec(&rec)?)?;
            Ok(())
        }
        "refit" => {
            let big_n: usize = a[3].parse()?;
            let seed: u64 = a[4].parse()?;
            let ticks: usize = a[5].parse()?;
            let out = PathBuf::from(&a[6]);
            let mut log = open_log(&out)?;
            for tick in 1..=ticks {
                let s = seed.wrapping_mul(1000).wrapping_add(tick as u64);
                let (mut rec, p) = full_fit(&d, big_n + tick, 1000, 1000, s, None)?;
                if let Some(p) = &p {
                    write_posterior(&out.join(format!("tick-{tick:03}.f32")), &Sv::new(&d, big_n + tick), p)?;
                }
                rec["tick"] = json!(tick);
                emit(&mut log, &rec)?;
            }
            Ok(())
        }
        "warm" => {
            let big_n: usize = a[3].parse()?;
            let k: usize = a[4].parse()?;
            let seed: u64 = a[5].parse()?;
            let ticks: usize = a[6].parse()?;
            let out = PathBuf::from(&a[7]);
            let mut log = open_log(&out)?;
            let (mut rec, p) = full_fit(&d, big_n, 1000, 1000, seed, None)?;
            rec["tick"] = json!(0);
            let Some(p) = p else {
                emit(&mut log, &rec)?;
                return Ok(());
            };
            write_posterior(&out.join("tick-000.f32"), &Sv::new(&d, big_n), &p)?;
            // The chain gate on the tick-0 fit: drop flagged chains from the carried state.
            let dropped = flagged(&p);
            let kept: Vec<usize> = (0..CHAINS).filter(|c| !dropped.contains(c)).collect();
            let chains: Vec<WarmChain> = p
                .warm_state()?
                .into_chains()
                .into_iter()
                .enumerate()
                .filter(|(c, _)| kept.contains(c))
                .map(|(_, chain)| chain)
                .collect();
            rec["kept"] = json!(kept);
            if chains.len() < 2 {
                rec["status"] = json!("gate_failed");
                emit(&mut log, &rec)?;
                return Ok(());
            }
            emit(&mut log, &rec)?;
            let mut state = WarmState::new(chains)?;
            for tick in 1..=ticks {
                let t0 = Instant::now();
                let sv = Sv::new(&d, big_n + tick);
                let grown = state.extend_to(sv.dimension(), 0.0, 1.0)?;
                let res = Sampler::new()
                    .draws(k)
                    .seed(tick_seed(seed, tick))
                    .threads(CHAINS)
                    .limits(Limits::new().admit_worst_case())
                    .run_warm(&sv, &grown);
                let p = match res {
                    Ok(p) => p,
                    Err(e) => {
                        let rec = json!({"tick": tick, "n": big_n + tick, "status": "error",
                            "error": e.to_string(), "wall_seconds": t0.elapsed().as_secs_f64()});
                        emit(&mut log, &rec)?;
                        break;
                    }
                };
                state = p.warm_state()?;
                let wall = t0.elapsed().as_secs_f64();
                write_posterior(&out.join(format!("tick-{tick:03}.f32")), &sv, &p)?;
                let steps: Vec<f64> = state.chains().iter().map(|c| c.step_size).collect();
                let rec = json!({"tick": tick, "n": big_n + tick, "status": "ok", "wall_seconds": wall,
                    "k": k, "chains": p.chain_count(), "draws": p.draws_per_chain(), "kept": kept,
                    "divergences": divergences(&p, 0), "steps": steps,
                    "calls": sv.calls.load(Ordering::Relaxed)});
                emit(&mut log, &rec)?;
            }
            Ok(())
        }
        "bitcheck" => {
            let big_n: usize = a[3].parse()?;
            let k: usize = a[4].parse()?;
            let seed: u64 = a[5].parse()?;
            let (rec0, p) = full_fit(&d, big_n, 1000, 1000, seed, None)?;
            let p = p.ok_or("tick-0 fit failed")?;
            let state = p.warm_state()?;
            let sv = Sv::new(&d, big_n + 1);
            let grown = state.extend_to(sv.dimension(), 0.0, 1.0)?;
            let base = tick_seed(seed, 1);
            let warm = Sampler::new()
                .draws(k)
                .seed(base)
                .threads(CHAINS)
                .limits(Limits::new().admit_worst_case())
                .run_warm(&sv, &grown)?;
            let mut per_chain = Vec::new();
            for (c, chain) in state.chains().iter().enumerate() {
                let oracle = harness_chain(&sv, chain, base.wrapping_add(c as u64), k)?;
                let (w, o) = (&warm.chains()[c], &oracle.chains()[0]);
                let same = w.samples() == o.samples()
                    && w.diagnostics() == o.diagnostics()
                    && w.metadata().effective_seed() == o.metadata().effective_seed()
                    && w.metadata().tuning().step_size() == o.metadata().tuning().step_size()
                    && w.metadata().mass_diagonal() == o.metadata().mass_diagonal();
                per_chain.push(same);
            }
            let identical = per_chain.iter().all(|&s| s);
            let out = json!({"identical": identical, "per_chain": per_chain, "N": big_n, "k": k,
                "seed": seed, "tick_seed": base, "dimension": sv.dimension(),
                "tick0_flagged": rec0["flagged"], "tick0_wall_seconds": rec0["wall_seconds"]});
            fs::write(&a[6], serde_json::to_vec_pretty(&out)?)?;
            println!("{out}");
            if identical { Ok(()) } else { Err("run_warm differs from the harness construction".into()) }
        }
        _ => Err(usage.into()),
    }
}

fn open_log(out: &Path) -> Result<fs::File, Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output exists: {}", out.display()).into());
    }
    fs::create_dir_all(out)?;
    Ok(fs::File::create(out.join("ticks.jsonl"))?)
}

fn emit(log: &mut fs::File, v: &Value) -> Result<(), Box<dyn Error>> {
    writeln!(log, "{v}")?;
    log.flush()?;
    Ok(())
}
