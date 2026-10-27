//! Warm-refresh microbenchmark (WP91): `Sampler::run_warm` against a
//! resident `WarmSession` on a hand-written stochastic-volatility target.
//!
//! Two targets: the WP84 shape (N = 250 returns, 253 coordinates) and a
//! 50-latent fixed-lag window (53 coordinates). For each, after one
//! adapted run, every combination of `threads` in {4, 1} and `K` in
//! {5, 10, 50} transitions per chain is timed over 200 calls after 20
//! warm-up calls, once as `run_warm` (a fresh pool, result buffers and
//! `Posterior` per call) and once as `WarmSession::refresh` (resident
//! worker, pool and per-chain inputs). Both start from the same state and
//! follow the session's seed rule, so call `n` of each does the same
//! transitions; the last draws are checked bit for bit. Reported per
//! call: median and P95 wall, the kernel's gradient count, and the time
//! those gradients cost in a tight loop (measured separately), so the
//! remainder is the overhead the session is meant to remove.
//!
//! ```text
//! cargo run --release --example warm_session_bench [-- --calls 200 --warmup-calls 20 --adapt 1000]
//! ```

use std::error::Error;
use std::hint::black_box;
use std::time::{Duration, Instant};

use owalnuts::sampler::{Sampler, Target, TargetError, WarmState};

const CHAINS: usize = 4;
const SEED: u64 = 0x5eed_0091;

/// Student-t stochastic volatility with an AR(1) log-variance in
/// non-centred form: `q = [mu, log sigma, beta, z_1..z_n]`,
/// `h_1 = mu + sigma z_1 / sqrt(1 - rho^2)`, `h_i = mu + rho (h_{i-1} - mu)
/// + sigma z_i`, `y_i ~ beta + exp(h_i / 2) t_nu`. A minimal copy of the
/// WP84 harness target (`STUDIES/online_sv_quote_v1/rust/src/main.rs`).
struct Sv {
    y: Vec<f64>,
    rho: f64,
    nu: f64,
    mu_mean: f64,
    mu_sd: f64,
    ls_mean: f64,
    ls_sd: f64,
    beta_sd: f64,
    cst: f64,
}

impl Sv {
    fn new(y: Vec<f64>) -> Self {
        let nu = 7.0;
        let cst = lgamma((nu + 1.) / 2.) - lgamma(nu / 2.) - 0.5 * (nu * std::f64::consts::PI).ln();
        Sv {
            y,
            rho: 0.95,
            nu,
            mu_mean: -1.0,
            mu_sd: 2.0,
            ls_mean: -1.5,
            ls_sd: 1.0,
            beta_sd: 0.1,
            cst,
        }
    }
}

impl Target for Sv {
    fn dimension(&self) -> usize {
        3 + self.y.len()
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        let n = self.y.len();
        let (rho, nu) = (self.rho, self.nu);
        let ln2pi = (2. * std::f64::consts::PI).ln();
        let (mu, ls, beta) = (q[0], q[1], q[2]);
        let sigma = ls.exp();
        let norm = |x: f64, m: f64, s: f64, g: &mut f64| -> f64 {
            let u = (x - m) / s;
            *g = -u / s;
            -0.5 * u * u - s.ln() - 0.5 * ln2pi
        };
        let mut lp = norm(mu, self.mu_mean, self.mu_sd, &mut g[0]);
        lp += norm(ls, self.ls_mean, self.ls_sd, &mut g[1]);
        lp += norm(beta, 0., self.beta_sd, &mut g[2]);
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
            let r = self.y[i] - beta;
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
        if !lp.is_finite() || g.iter().any(|x| !x.is_finite()) {
            return Err(TargetError::recoverable(
                "non-finite log density or gradient",
            ));
        }
        Ok(lp)
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

/// Deterministic xorshift64* normals and Student-t draws for the data.
struct Rng(u64);

impl Rng {
    fn uniform(&mut self) -> f64 {
        self.0 ^= self.0 >> 12;
        self.0 ^= self.0 << 25;
        self.0 ^= self.0 >> 27;
        let bits = self.0.wrapping_mul(0x2545_F491_4F6C_DD1D) >> 11;
        (bits as f64 + 0.5) / (1u64 << 53) as f64
    }
    fn normal(&mut self) -> f64 {
        let (u, v) = (self.uniform(), self.uniform());
        (-2.0 * u.ln()).sqrt() * (2.0 * std::f64::consts::PI * v).cos()
    }
    fn student_t(&mut self, nu: usize) -> f64 {
        let chi2: f64 = (0..nu).map(|_| self.normal().powi(2)).sum();
        self.normal() / (chi2 / nu as f64).sqrt()
    }
}

/// Simulate `n` returns from the model with mu = -1, sigma = 0.3, rho = 0.95,
/// beta = 0, nu = 7.
fn simulate(n: usize) -> Vec<f64> {
    let mut rng = Rng(0x9E37_79B9_7F4A_7C15);
    let (mu, sigma, rho): (f64, f64, f64) = (-1.0, 0.3, 0.95);
    let mut h = mu + sigma / (1.0 - rho * rho).sqrt() * rng.normal();
    let mut y = Vec::with_capacity(n);
    for i in 0..n {
        if i > 0 {
            h = mu + rho * (h - mu) + sigma * rng.normal();
        }
        y.push((h / 2.0).exp() * rng.student_t(7));
    }
    y
}

struct Measure {
    walls: Vec<Duration>,
    gradients: Vec<usize>,
}

impl Measure {
    fn median(&self) -> Duration {
        quantile(&self.walls, 0.5)
    }
    fn p95(&self) -> Duration {
        quantile(&self.walls, 0.95)
    }
    fn mean_gradients(&self) -> f64 {
        self.gradients.iter().sum::<usize>() as f64 / self.gradients.len().max(1) as f64
    }
}

fn quantile(walls: &[Duration], probability: f64) -> Duration {
    let mut sorted = walls.to_vec();
    sorted.sort();
    let rank = ((sorted.len() - 1) as f64 * probability).round() as usize;
    sorted[rank]
}

fn micros(duration: Duration) -> f64 {
    duration.as_secs_f64() * 1e6
}

struct Options {
    calls: usize,
    warmup_calls: usize,
    adapt: usize,
}

fn parse_options() -> Result<Options, Box<dyn Error>> {
    let mut options = Options {
        calls: 200,
        warmup_calls: 20,
        adapt: 1000,
    };
    let mut args = std::env::args().skip(1);
    while let Some(flag) = args.next() {
        let value = args.next().ok_or("flag needs a value")?.parse()?;
        match flag.as_str() {
            "--calls" => options.calls = value,
            "--warmup-calls" => options.warmup_calls = value,
            "--adapt" => options.adapt = value,
            other => return Err(format!("unknown flag {other}").into()),
        }
    }
    Ok(options)
}

/// Seconds per gradient of `target` at `position`, in a tight loop.
fn gradient_seconds(target: &Sv, position: &[f64]) -> f64 {
    let mut gradient = vec![0.0; position.len()];
    let repeats = 2000;
    for _ in 0..200 {
        black_box(target.log_density_gradient(black_box(position), &mut gradient)).ok();
    }
    let started = Instant::now();
    for _ in 0..repeats {
        black_box(target.log_density_gradient(black_box(position), &mut gradient)).ok();
    }
    started.elapsed().as_secs_f64() / repeats as f64
}

fn main() -> Result<(), Box<dyn Error>> {
    let options = parse_options()?;
    let y = simulate(250);
    println!(
        "warm_session_bench: {CHAINS} chains, {} timed calls after {} warm-up calls, {} warmup transitions per target",
        options.calls, options.warmup_calls, options.adapt
    );
    println!(
        "{:<22} | {:>7} | {:>3} | {:>14} | {:>14} | {:>14} | {:>14} | {:>10} | {:>12}",
        "target",
        "threads",
        "K",
        "run_warm med",
        "run_warm P95",
        "session med",
        "session P95",
        "grads/call",
        "grad-only/call"
    );
    println!("{}", "-".repeat(140));
    let variants = [
        ("sv N=250 (dim 253)", y.clone()),
        ("sv window 50 (dim 53)", y[200..].to_vec()),
    ];
    for (name, data) in variants {
        let target = Sv::new(data.clone());
        let state0 = Sampler::new()
            .warmup(options.adapt)
            .draws(100)
            .chains(CHAINS)
            .seed(SEED)
            .threads(4)
            .run_from_random_starts(&target)?
            .warm_state()?;
        let per_gradient = gradient_seconds(&target, &state0.chains()[0].position);
        for threads in [4usize, 1] {
            for draws in [5usize, 10, 50] {
                let (warm, warm_last) = time_run_warm(&target, &state0, threads, draws, &options)?;
                let (session, session_last) =
                    time_session(Sv::new(data.clone()), &state0, threads, draws, &options)?;
                assert_eq!(
                    warm_last, session_last,
                    "run_warm and the session diverged on {name} threads {threads} K {draws}"
                );
                let gradients = session.mean_gradients();
                println!(
                    "{:<22} | {:>7} | {:>3} | {:>11.0} us | {:>11.0} us | {:>11.0} us | {:>11.0} us | {:>10.1} | {:>9.0} us",
                    name,
                    threads,
                    draws,
                    micros(warm.median()),
                    micros(warm.p95()),
                    micros(session.median()),
                    micros(session.p95()),
                    gradients,
                    gradients * per_gradient * 1e6 / threads.min(CHAINS) as f64,
                );
            }
        }
        println!(
            "{name}: one gradient costs {:.2} us in a tight loop; grad-only/call is the gradient count at that cost divided over the workers (ideal scaling)",
            per_gradient * 1e6
        );
    }
    println!(
        "Wall is per call, timed around the library call on this machine (indicative; a contended laptop)."
    );
    Ok(())
}

/// `run_warm` per call with the session's seed rule (call `n` seeded
/// `SEED + n * CHAINS`), chaining the state; returns the timings and the
/// last call's draws.
fn time_run_warm(
    target: &Sv,
    state0: &WarmState,
    threads: usize,
    draws: usize,
    options: &Options,
) -> Result<(Measure, Vec<Vec<f64>>), Box<dyn Error>> {
    let mut state = state0.clone();
    let mut measure = Measure {
        walls: Vec::with_capacity(options.calls),
        gradients: Vec::with_capacity(options.calls),
    };
    let mut last = Vec::new();
    for call in 0..options.warmup_calls + options.calls {
        let sampler = Sampler::new()
            .draws(draws)
            .seed(SEED.wrapping_add((call * CHAINS) as u64))
            .threads(threads);
        let started = Instant::now();
        let posterior = sampler.run_warm(target, &state)?;
        let wall = started.elapsed();
        state = posterior.warm_state()?;
        if call >= options.warmup_calls {
            measure.walls.push(wall);
            measure.gradients.push(posterior.total_target_calls());
        }
        last = posterior
            .chains()
            .iter()
            .map(|chain| chain.samples().to_vec())
            .collect();
    }
    Ok((measure, last))
}

fn time_session(
    target: Sv,
    state0: &WarmState,
    threads: usize,
    draws: usize,
    options: &Options,
) -> Result<(Measure, Vec<Vec<f64>>), Box<dyn Error>> {
    let mut session = Sampler::new()
        .seed(SEED)
        .threads(threads)
        .start_warm_session(target, state0.clone())?;
    let mut measure = Measure {
        walls: Vec::with_capacity(options.calls),
        gradients: Vec::with_capacity(options.calls),
    };
    let mut last = Vec::new();
    for call in 0..options.warmup_calls + options.calls {
        let started = Instant::now();
        let chunk = session.refresh(draws)?;
        let wall = started.elapsed();
        if call >= options.warmup_calls {
            measure.walls.push(wall);
            measure.gradients.push(chunk.target_calls);
        }
        last = chunk
            .chains
            .into_iter()
            .map(|chain| chain.samples)
            .collect();
    }
    session.close()?;
    Ok((measure, last))
}
