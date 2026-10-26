//! WP84 oWALNUTS arms for `STUDIES/online_sv_quote_v1`.
//!
//! Target: the market_uncertainty_v1 price-only SV model (intercept beta, no flow columns),
//! q = [mu, log_sigma, beta, z[n]], rho = 0.95 and nu = 5 fixed, exact normalized density.
//!
//! Usage (T ticks, default 100, override with WP84_TICKS for smoke tests):
//! * `wp84 eval <data.json> <n> <points.json> <out.json>`        density/gradient check
//! * `wp84 ref <data.json> <N> <seed> <outdir>`                    4 x 2,000/20,000 per tick
//! * `wp84 refit <data.json> <N> <seed> <outdir>`                  4 x 1,000/1,000 per tick (defaults)
//! * `wp84 warm <data.json> <N> <K> <seed> <outdir>`               tick 0 default fit, then K
//!   transitions per tick per chain from the carried positions, step and diagonal metric
//!
//! Every tick writes `tick-XXX.f32` (little-endian f32, [chain][draw][3] = mu, log_sigma, h_n)
//! and one JSON line in `ticks.jsonl`.
//!
//! Warm continuation ("research-only retarget"): the continuation session
//! (`Sampler::start_session`) owns one immutable target of fixed dimension and cannot be
//! retargeted, so the warm arm is built from the public API: each tick constructs the new
//! target (n + 1 observations, dimension + 1), extends every chain's last position with the new
//! innovation z_new = 0 (its prior median), extends the chain's adapted diagonal metric with
//! the prior variance 1 for z_new, and runs one single-chain `Sampler` per chain with
//! `Metric::fixed_diagonal`, `Tuning::step_size(carried step)`, `Adaptation::None`,
//! `warmup(0)` and `draws(K)`, the four chains in parallel threads. No re-adaptation:
//! step and metric stay those of the tick-0 fit (only the new coordinate is appended).
#![forbid(unsafe_code)]

use owalnuts::sampler::{Adaptation, Limits, Metric, Sampler, Target, TargetError, Tuning};
use serde_json::{Value, json};
use std::{
    env,
    error::Error,
    fs,
    io::Write,
    path::{Path, PathBuf},
    sync::atomic::{AtomicUsize, Ordering},
    time::Instant,
};

const CHAINS: usize = 4;

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

fn ticks() -> usize {
    env::var("WP84_TICKS").ok().and_then(|s| s.parse().ok()).unwrap_or(100)
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

struct Fit {
    last: Vec<Vec<f64>>,
    steps: Vec<f64>,
    masses: Vec<Vec<f64>>,
}

/// One full fit at sampler defaults (best-of-16 random starts, diagonal metric).
fn full_fit(
    d: &Data,
    n: usize,
    warmup: usize,
    draws: usize,
    seed: u64,
    tick: usize,
    out: &Path,
) -> Result<(Value, Option<Fit>), Box<dyn Error>> {
    let t0 = Instant::now();
    let sv = Sv::new(d, n);
    let res = Sampler::new()
        .warmup(warmup)
        .draws(draws)
        .chains(CHAINS)
        .seed(seed)
        .threads(CHAINS)
        .limits(Limits::new().admit_worst_case())
        .run_from_random_starts(&sv);
    let wall = t0.elapsed().as_secs_f64();
    let p = match res {
        Ok(p) => p,
        Err(e) => {
            return Ok((
                json!({"tick": tick, "n": n, "status": "error", "error": e.to_string(),
                "wall_seconds": wall, "calls": sv.calls.load(Ordering::Relaxed)}),
                None,
            ));
        }
    };
    let chains: Vec<&[f64]> = p.chains().iter().map(|c| c.samples()).collect();
    write_draws(&out.join(format!("tick-{tick:03}.f32")), &sv, &chains)?;
    let dim = sv.dimension();
    let div: Vec<usize> = p
        .chains()
        .iter()
        .map(|c| c.diagnostics()[warmup..].iter().filter(|x| x.divergent()).count())
        .collect();
    let steps: Vec<f64> = p.chains().iter().map(|c| c.metadata().tuning().step_size()).collect();
    let fit = Fit {
        last: p.chains().iter().map(|c| c.samples()[(draws - 1) * dim..].to_vec()).collect(),
        steps: steps.clone(),
        masses: p.chains().iter().map(|c| c.metadata().mass_diagonal().to_vec()).collect(),
    };
    let warnings: Vec<String> = p.chain_warnings().iter().map(|w| format!("{w:?}")).collect();
    let rec = json!({"tick": tick, "n": n, "status": "ok", "wall_seconds": wall, "seed": seed,
        "warmup": warmup, "draws": draws, "divergences": div, "steps": steps,
        "calls": sv.calls.load(Ordering::Relaxed), "chain_warnings": warnings});
    Ok((rec, Some(fit)))
}

fn warm_tick(
    d: &Data,
    n: usize,
    k: usize,
    seed: u64,
    tick: usize,
    fit: &mut Fit,
    out: &Path,
) -> Result<Value, Box<dyn Error>> {
    let t0 = Instant::now();
    let sv = Sv::new(d, n);
    let dim = sv.dimension();
    for c in 0..CHAINS {
        while fit.last[c].len() < dim {
            fit.last[c].push(0.0);
        }
        while fit.masses[c].len() < dim {
            fit.masses[c].push(1.0);
        }
    }
    let results: Vec<_> = std::thread::scope(|s| {
        let hs: Vec<_> = (0..CHAINS)
            .map(|c| {
                let (sv, start, mass, step) =
                    (&sv, fit.last[c].clone(), fit.masses[c].clone(), fit.steps[c]);
                let chain_seed = seed
                    .wrapping_mul(1_000_003)
                    .wrapping_add((tick * 16 + c) as u64);
                s.spawn(move || {
                    Sampler::new()
                        .warmup(0)
                        .draws(k)
                        .seed(chain_seed)
                        .threads(1)
                        .metric(Metric::fixed_diagonal(mass))
                        .adaptation(Adaptation::None)
                        .tuning(Tuning::new().step_size(step))
                        .limits(Limits::new().admit_worst_case())
                        .run(sv, &[start])
                })
            })
            .collect();
        hs.into_iter().map(|h| h.join().expect("chain thread panicked")).collect()
    });
    let wall = t0.elapsed().as_secs_f64();
    let mut posts = Vec::new();
    for r in results {
        match r {
            Ok(p) => posts.push(p),
            Err(e) => {
                return Ok(json!({"tick": tick, "n": n, "status": "error",
                    "error": e.to_string(), "wall_seconds": wall}));
            }
        }
    }
    let chains: Vec<&[f64]> = posts.iter().map(|p| p.chains()[0].samples()).collect();
    write_draws(&out.join(format!("tick-{tick:03}.f32")), &sv, &chains)?;
    for c in 0..CHAINS {
        fit.last[c] = chains[c][(k - 1) * dim..].to_vec();
    }
    let div: Vec<usize> = posts
        .iter()
        .map(|p| p.chains()[0].diagnostics().iter().filter(|x| x.divergent()).count())
        .collect();
    Ok(json!({"tick": tick, "n": n, "status": "ok", "wall_seconds": wall, "k": k,
        "divergences": div, "steps": fit.steps, "calls": sv.calls.load(Ordering::Relaxed)}))
}

fn main() -> Result<(), Box<dyn Error>> {
    let a: Vec<String> = env::args().collect();
    let mode = a.get(1).map(String::as_str).unwrap_or("");
    if mode == "eval" {
        let d = load(Path::new(&a[2]))?;
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
        return Ok(());
    }
    let d = load(Path::new(a.get(2).ok_or("data")?))?;
    let big_n: usize = a[3].parse()?;
    let (k, seed, out) = match mode {
        "warm" => (a[4].parse::<usize>()?, a[5].parse::<u64>()?, PathBuf::from(&a[6])),
        "ref" | "refit" => (0, a[4].parse::<u64>()?, PathBuf::from(&a[5])),
        _ => return Err("usage: wp84 eval|ref|refit|warm ...".into()),
    };
    if out.exists() {
        return Err(format!("output exists: {}", out.display()).into());
    }
    fs::create_dir_all(&out)?;
    let mut log = fs::File::create(out.join("ticks.jsonl"))?;
    let mut emit = |v: Value| -> Result<(), Box<dyn Error>> {
        writeln!(log, "{v}")?;
        log.flush()?;
        Ok(())
    };
    let t = ticks();
    match mode {
        "ref" => {
            for tick in 1..=t {
                let s = seed.wrapping_mul(1000).wrapping_add(tick as u64);
                let (rec, _) = full_fit(&d, big_n + tick, 2000, 20000, s, tick, &out)?;
                emit(rec)?;
            }
        }
        "refit" => {
            for tick in 1..=t {
                let s = seed.wrapping_mul(1000).wrapping_add(tick as u64);
                let (rec, _) = full_fit(&d, big_n + tick, 1000, 1000, s, tick, &out)?;
                emit(rec)?;
            }
        }
        _ => {
            let (rec, fit) = full_fit(&d, big_n, 1000, 1000, seed, 0, &out)?;
            emit(rec)?;
            let Some(mut fit) = fit else { return Ok(()) };
            for tick in 1..=t {
                let rec = warm_tick(&d, big_n + tick, k, seed, tick, &mut fit, &out)?;
                let stop = rec["status"] != "ok";
                emit(rec)?;
                if stop {
                    break;
                }
            }
        }
    }
    Ok(())
}
