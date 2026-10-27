//! WP93 oWALNUTS arms for `STUDIES/tick_pooling_v1`.
//!
//! Target: the market_uncertainty_v1 price-only SV model (intercept beta, no flow columns),
//! q = [mu, log_sigma, beta, z[n]], rho = 0.95 and nu = 5 fixed, exact normalized density. The
//! density code is the WP84 / WP88 harness code unchanged
//! (`STUDIES/online_sv_quote_v2/rust/src/main.rs`).
//!
//! Modes:
//! * `wp93 eval <data.json> <n> <points.json> <out.json>`         density/gradient check
//! * `wp93 reftick <data.json> <n_obs> <seed> <outstem>`           one 4 x 2,000/20,000 fit on the
//!   first `n_obs` returns -> `<outstem>.f32` + `<outstem>.json` (the gate is applied by the
//!   Python driver, which may call this again with the next preregistered seed)
//! * `wp93 warm <data.json> <N> <K> <seed> <ticks> <outdir>`       gated tick-0 fit, then
//!   `Sampler::run_warm` with `draws(K)` on a `WarmState` extended by one coordinate per tick
//!
//! Every tick writes `tick-XXX.f32` (little-endian f32, [chain][draw][4] = mu, log_sigma, beta,
//! h_n) and one JSON line in `ticks.jsonl` (`chains` and `draws` give the shape). The pooling of
//! the last H ticks' draws is analysis-side (`analyze.py`); this binary only produces the per-tick
//! draws and the latency of the library call.
//!
//! Tick-0 gate (WP93): the default fit (4 x 1,000/1,000, best-of-16 starts) at the cell seed; if
//! any chain is named by a `WarmupStep` / `SampledLogDensity` warning the fit is repeated once at
//! the next preregistered seed (`seed + 10`); if that fit is flagged too, the flagged chains are
//! dropped from the carried state (WP88 rule; fewer than 2 left = the cell fails, a result).
//! Per tick: `WarmState::extend_to(3 + n, 0.0, 1.0)` then `Sampler::run_warm` with `draws(K)`,
//! seed `seed * 1_000_003 + 16 * tick` (chain `c` on `seed + c`); the result's `warm_state()` is
//! the next state; no re-adaptation. Latency is the wall from `Sv::new` to `warm_state()` taken.
#![forbid(unsafe_code)]

use owalnuts::diagnostics::ChainWarning;
use owalnuts::sampler::{Limits, Posterior, Sampler, Target, TargetError, WarmChain, WarmState};
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
/// Result-size ceiling for the reference (`Limits::max_result_bytes_unchecked`), as WP88.
const REF_RESULT_BYTES: usize = 2 << 30;
/// Seed offset of the second tick-0 attempt.
const TICK0_RETRY_SEED_STEP: u64 = 10;

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

/// `[chain][draw][4]` = mu, log_sigma, beta, h_n as little-endian f32.
fn write_draws(path: &Path, sv: &Sv, chains: &[&[f64]]) -> Result<(), Box<dyn Error>> {
    let dim = sv.dimension();
    let mut buf = Vec::with_capacity(chains.iter().map(|c| c.len() / dim * 16).sum());
    for c in chains {
        for q in c.chunks(dim) {
            for x in [q[0], q[1], q[2], sv.h_last(q)] {
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

fn main() -> Result<(), Box<dyn Error>> {
    let a: Vec<String> = env::args().collect();
    let mode = a.get(1).map(String::as_str).unwrap_or("");
    let usage = "usage: wp93 eval|reftick|warm ...";
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
        "warm" => {
            let big_n: usize = a[3].parse()?;
            let k: usize = a[4].parse()?;
            let seed: u64 = a[5].parse()?;
            let ticks: usize = a[6].parse()?;
            let out = PathBuf::from(&a[7]);
            let mut log = open_log(&out)?;
            // Tick-0 gate: attempt 0 at the cell seed; a flagged chain triggers one more attempt
            // at the next preregistered seed; the last attempt's flagged chains are dropped.
            let mut attempts = Vec::new();
            let mut chosen: Option<(Value, Posterior, u64)> = None;
            for attempt in 0..2u64 {
                let s = seed.wrapping_add(TICK0_RETRY_SEED_STEP * attempt);
                let (mut rec, p) = full_fit(&d, big_n, 1000, 1000, s, None)?;
                rec["attempt"] = json!(attempt);
                attempts.push(rec.clone());
                match p {
                    Some(p) if attempt == 1 || flagged(&p).is_empty() => {
                        chosen = Some((rec, p, s));
                        break;
                    }
                    Some(_) => continue,
                    None => continue,
                }
            }
            let Some((mut rec, p, seed0)) = chosen else {
                let rec = json!({"tick": 0, "n": big_n, "status": "error", "attempts": attempts,
                    "error": "tick-0 fit failed on every attempt"});
                emit(&mut log, &rec)?;
                return Ok(());
            };
            rec["tick"] = json!(0);
            rec["attempts"] = json!(attempts);
            rec["tick0_seed"] = json!(seed0);
            write_posterior(&out.join("tick-000.f32"), &Sv::new(&d, big_n), &p)?;
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
