//! WP96 oWALNUTS arms for `STUDIES/warm_drift_v1`.
//!
//! Target: the WP84/WP88 price-only SV model (density code copied verbatim from
//! `STUDIES/online_sv_quote_v2/rust/src/main.rs`), q = [mu, log_sigma, beta, z[n]], rho = 0.95 and
//! nu = 5 fixed, on a FIXED-LAG WINDOW of the return series: the target at tick t conditions on
//! the n returns y[t .. t + n).
//!
//! Modes:
//! * `wp96 reftick <data.json> <start> <n> <seed> <outstem>`   one 4 x 2,000/20,000 fit on the window
//!   y[start .. start + n) -> `<outstem>.f32` + `<outstem>.json` (the gate is applied by the Python
//!   driver, which may call this again with the next preregistered seed)
//! * `wp96 warm <data.json> <N> <K> <seed> <ticks> <policy> <draw_every> <outdir>`
//!   tick-0 fit on y[0 .. N), chain gate, then per tick t = 1..ticks: window y[t .. t + N),
//!   `shift_window` (the oldest latent dropped, a new one appended; h path preserved), the policy's
//!   re-adaptation if due, `Sampler::run_warm` with `draws(K)`; the result's `warm_state()` is the
//!   next state. Policies: `frozen` (never re-adapt), `every:M` (re-adapt at every tick t with
//!   t % M == 0), `trigger` (re-adapt when the cost trigger fires; see `Trigger`).
//!   Draws are written only at ticks with t % draw_every == 0 (and tick 0).
//! * `wp96 remapcheck <data.json> <n> <out.json>`   checks that `shift_window` preserves the
//!   log-volatility path h_1..h_{n-1} of the old window as h_0..h_{n-2} of the new one
//!
//! Every written tick is `tick-XXXX.f32` (little-endian f32, [chain][draw][3] = mu, log_sigma, h_n)
//! and one JSON line in `ticks.jsonl` (`chains` and `draws` give the shape).
//!
//! Re-adaptation (`every:M`, `trigger`): a `Sampler::run` with `warmup(READAPT_WARMUP)` and
//! `draws(1)` from the chains' current positions, `Metric::Diagonal { adapt: true, initial }` with
//! `initial` the element-wise geometric mean of the carried per-chain mass diagonals (the API
//! takes one initial diagonal for all chains), seed `tick_seed + 8`; its `warm_state()` replaces
//! the carried state, except that a chain named by a `WarmupStep` / `SampledLogDensity` warning
//! keeps its pre-re-adaptation state (per-chain fallback, counted). The re-adaptation and the
//! K-draw refresh at that tick are both inside the tick's timed region.
#![forbid(unsafe_code)]

use owalnuts::diagnostics::ChainWarning;
use owalnuts::sampler::{
    Limits, Metric, Posterior, Sampler, Target, TargetError, WarmChain, WarmState,
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
/// Result-size ceiling for the reference (as WP88; not binding at dimension 253).
const REF_RESULT_BYTES: usize = 2 << 30;
/// Re-adaptation warmup length (transitions per chain) and its single retained draw.
const READAPT_WARMUP: usize = 200;
/// Trigger: trailing window, post-adaptation baseline window (ticks), cost ratio and the stuck
/// fraction (see `Trigger`).
const TRAIL: usize = 20;
const BASE: usize = 20;
const COST_RATIO: f64 = 1.5;
const UNCHANGED_FRAC: f64 = 0.05;

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

/// The SV target on the window y[start .. start + n).
struct Sv<'a> {
    d: &'a Data,
    start: usize,
    n: usize,
    cst: f64,
    calls: AtomicUsize,
}

impl<'a> Sv<'a> {
    fn new(d: &'a Data, start: usize, n: usize) -> Self {
        assert!(
            start + n <= d.y.len(),
            "window [{start}, {}) exceeds the series length {}",
            start + n,
            d.y.len()
        );
        let nu = d.nu;
        let cst = lgamma((nu + 1.) / 2.) - lgamma(nu / 2.) - 0.5 * (nu * std::f64::consts::PI).ln();
        Sv {
            d,
            start,
            n,
            cst,
            calls: AtomicUsize::new(0),
        }
    }
    fn y(&self, i: usize) -> f64 {
        self.d.y[self.start + i]
    }
    fn h_path(&self, q: &[f64]) -> Vec<f64> {
        let (mu, s, rho) = (q[0], q[1].exp(), self.d.rho);
        let mut h = Vec::with_capacity(self.n);
        h.push(mu + s * q[3] / (1. - rho * rho).sqrt());
        for i in 1..self.n {
            let prev = h[i - 1];
            h.push(mu + rho * (prev - mu) + s * q[3 + i]);
        }
        h
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
            let r = self.y(i) - beta;
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
            return Err(TargetError::recoverable(
                "non-finite log density or gradient",
            ));
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
        .map(|c| {
            c.diagnostics()[skip..]
                .iter()
                .filter(|x| x.divergent())
                .count()
        })
        .collect()
}

/// One full fit at sampler defaults (best-of-16 random starts, diagonal metric).
fn full_fit(
    sv: &Sv,
    warmup: usize,
    draws: usize,
    seed: u64,
    result_bytes: Option<usize>,
) -> Result<(Value, Option<Posterior>), Box<dyn Error>> {
    let t0 = Instant::now();
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
        .run_from_random_starts(sv);
    let wall = t0.elapsed().as_secs_f64();
    let p = match res {
        Ok(p) => p,
        Err(e) => {
            return Ok((
                json!({"n": sv.n, "start": sv.start, "status": "error", "error": e.to_string(),
                    "seed": seed, "wall_seconds": wall, "calls": sv.calls.load(Ordering::Relaxed)}),
                None,
            ));
        }
    };
    let steps: Vec<f64> = p
        .chains()
        .iter()
        .map(|c| c.metadata().tuning().step_size())
        .collect();
    let warnings: Vec<String> = p
        .chain_warnings()
        .iter()
        .map(|w| format!("{w:?}"))
        .collect();
    let rec = json!({"n": sv.n, "start": sv.start, "status": "ok", "wall_seconds": wall, "seed": seed,
        "warmup": warmup, "draws": draws, "chains": CHAINS, "divergences": divergences(&p, warmup),
        "steps": steps, "calls": sv.calls.load(Ordering::Relaxed), "chain_warnings": warnings,
        "flagged": flagged(&p)});
    Ok((rec, Some(p)))
}

fn tick_seed(seed: u64, tick: usize) -> u64 {
    seed.wrapping_mul(1_000_003)
        .wrapping_add((tick * 16) as u64)
}

/// The fixed-lag window remap: drop the oldest latent z_0, append a new one at 0 (prior median,
/// mass 1), and preserve the log-volatility path. The new first latent is z'_0 = rho z_0 +
/// sqrt(1 - rho^2) z_1, so that h'_0 = mu + sigma z'_0 / sqrt(1 - rho^2) equals the old h_1; every
/// other latent shifts by one (z'_i = z_{i+1}), so h'_i = h_{i+1} for i = 0..n-2 exactly. Masses:
/// the first latent keeps the mass of the old first latent (same role, the stationary start),
/// the others shift with their coordinates, the new one gets 1. Steps unchanged. [mu, log_sigma,
/// beta] unchanged. (The WP91 `shift_window` helper is not on main; this is the harness version.)
fn shift_window(state: &WarmState, rho: f64) -> Result<WarmState, Box<dyn Error>> {
    let dim = state.dimension();
    if dim < 5 {
        return Err("shift_window needs at least two latents".into());
    }
    let sq = (1. - rho * rho).sqrt();
    let chains: Vec<WarmChain> = state
        .chains()
        .iter()
        .map(|c| {
            let (p, m) = (&c.position, &c.mass_diagonal);
            let mut position = Vec::with_capacity(dim);
            let mut mass = Vec::with_capacity(dim);
            position.extend_from_slice(&p[..3]);
            mass.extend_from_slice(&m[..3]);
            position.push(rho * p[3] + sq * p[4]);
            mass.push(m[3]);
            position.extend_from_slice(&p[5..]);
            mass.extend_from_slice(&m[5..]);
            position.push(0.0);
            mass.push(1.0);
            WarmChain {
                position,
                step_size: c.step_size,
                mass_diagonal: mass,
            }
        })
        .collect();
    Ok(WarmState::new(chains)?)
}

/// Element-wise geometric mean of the carried per-chain mass diagonals.
fn pooled_mass(state: &WarmState) -> Vec<f64> {
    let dim = state.dimension();
    let k = state.chain_count() as f64;
    (0..dim)
        .map(|i| {
            (state
                .chains()
                .iter()
                .map(|c| c.mass_diagonal[i].ln())
                .sum::<f64>()
                / k)
                .exp()
        })
        .collect()
}

struct Readapt {
    state: WarmState,
    info: Value,
}

/// A short re-adaptation from the chains' current positions (see the module docs).
fn readapt(sv: &Sv, state: &WarmState, seed: u64, tick: usize) -> Readapt {
    let t0 = Instant::now();
    let starts: Vec<Vec<f64>> = state.chains().iter().map(|c| c.position.clone()).collect();
    let res = Sampler::new()
        .warmup(READAPT_WARMUP)
        .draws(1)
        .chains(state.chain_count())
        .seed(tick_seed(seed, tick).wrapping_add(8))
        .threads(CHAINS)
        .metric(Metric::Diagonal {
            adapt: true,
            initial: Some(pooled_mass(state)),
        })
        .limits(Limits::new().admit_worst_case())
        .run(sv, &starts);
    let wall = t0.elapsed().as_secs_f64();
    match res.and_then(|p| p.warm_state().map(|s| (p, s))) {
        Ok((p, fresh)) => {
            let dropped = flagged(&p);
            let mut chains = fresh.into_chains();
            for &c in &dropped {
                chains[c] = state.chains()[c].clone();
            }
            let steps: Vec<f64> = chains.iter().map(|c| c.step_size).collect();
            let warnings: Vec<String> = p
                .chain_warnings()
                .iter()
                .map(|w| format!("{w:?}"))
                .collect();
            match WarmState::new(chains) {
                Ok(new_state) => Readapt {
                    state: new_state,
                    info: json!({"wall": wall, "status": "ok", "flagged": dropped, "steps": steps,
                        "warmup": READAPT_WARMUP, "chain_warnings": warnings,
                        "divergences": divergences(&p, READAPT_WARMUP)}),
                },
                Err(e) => Readapt {
                    state: state.clone(),
                    info: json!({"wall": wall, "status": "error", "error": e.to_string()}),
                },
            }
        }
        Err(e) => Readapt {
            state: state.clone(),
            info: json!({"wall": wall, "status": "error", "error": e.to_string()}),
        },
    }
}

/// Per-tick diagnostics of the warm refresh, pooled over chains and transitions.
struct TickStats {
    evals: f64,
    depth: f64,
    step_ratio: f64,
    energy: f64,
    unchanged: f64,
}

fn tick_stats(p: &Posterior) -> TickStats {
    let (mut n, mut evals, mut depth, mut ratio, mut energy, mut unchanged) =
        (0usize, 0., 0., 0., 0., 0.);
    for c in p.chains() {
        for d in c.diagnostics() {
            n += 1;
            evals += d.target_evaluations() as f64;
            depth += d.depth() as f64;
            ratio += d
                .selected_refinement_level()
                .map_or(1.0, |l| 0.5f64.powi(l as i32));
            energy += d.maximum_absolute_energy_error();
            unchanged += if d.position_changed() { 0. } else { 1. };
        }
    }
    let n = n.max(1) as f64;
    TickStats {
        evals: evals / n,
        depth: depth / n,
        step_ratio: ratio / n,
        energy: energy / n,
        unchanged: unchanged / n,
    }
}

#[derive(Clone, Copy)]
enum Policy {
    Frozen,
    Every(usize),
    Trigger,
}

fn parse_policy(s: &str) -> Result<Policy, Box<dyn Error>> {
    Ok(match s {
        "frozen" => Policy::Frozen,
        "trigger" => Policy::Trigger,
        _ => match s.strip_prefix("every:") {
            Some(m) => Policy::Every(m.parse::<usize>()?.max(1)),
            None => return Err(format!("unknown policy {s}").into()),
        },
    })
}

/// The cost trigger. C_t = mean target evaluations per transition of tick t (over all chains and
/// their K transitions); U_t = fraction of tick t's transitions whose position did not change.
/// With `a` the tick of the latest adaptation (0 = the tick-0 fit), the baseline is the mean of
/// C over ticks a+1 ..= a+BASE and the trailing value the mean over ticks t-TRAIL ..= t-1; the
/// trigger is armed at tick t once t - 1 >= a + BASE + TRAIL and fires when
/// trailing > COST_RATIO x baseline or the trailing mean of U exceeds UNCHANGED_FRAC. Evaluated at
/// the start of tick t, before its refresh; a firing re-adapts at tick t.
struct Trigger {
    cost: Vec<f64>,
    unchanged: Vec<f64>,
    last_adapt: usize,
}

impl Trigger {
    fn evaluate(&self, tick: usize) -> (bool, Value) {
        let a = self.last_adapt;
        let armed = tick > a + BASE + TRAIL;
        if !armed {
            return (false, json!({"armed": false}));
        }
        let mean = |v: &[f64]| v.iter().sum::<f64>() / v.len() as f64;
        // cost[i] holds tick i + 1.
        let baseline = mean(&self.cost[a..a + BASE]);
        let trailing = mean(&self.cost[tick - 1 - TRAIL..tick - 1]);
        let stuck = mean(&self.unchanged[tick - 1 - TRAIL..tick - 1]);
        let fired = trailing > COST_RATIO * baseline || stuck > UNCHANGED_FRAC;
        (
            fired,
            json!({"armed": true, "baseline": baseline, "trailing": trailing, "ratio": trailing / baseline,
                "stuck": stuck, "fired": fired}),
        )
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

#[allow(clippy::too_many_arguments)]
fn warm_cell(
    d: &Data,
    big_n: usize,
    k: usize,
    seed: u64,
    ticks: usize,
    policy: Policy,
    draw_every: usize,
    out: &Path,
) -> Result<(), Box<dyn Error>> {
    let mut log = open_log(out)?;
    let sv0 = Sv::new(d, 0, big_n);
    let (mut rec, p) = full_fit(&sv0, 1000, 1000, seed, None)?;
    rec["tick"] = json!(0);
    let Some(p) = p else {
        emit(&mut log, &rec)?;
        return Ok(());
    };
    write_posterior(&out.join("tick-0000.f32"), &sv0, &p)?;
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
    let mut trigger = Trigger {
        cost: Vec::with_capacity(ticks),
        unchanged: Vec::with_capacity(ticks),
        last_adapt: 0,
    };
    for tick in 1..=ticks {
        let t0 = Instant::now();
        let sv = Sv::new(d, tick, big_n);
        state = shift_window(&state, d.rho)?;
        let (due, trig) = match policy {
            Policy::Frozen => (false, Value::Null),
            Policy::Every(m) => (tick % m == 0, Value::Null),
            Policy::Trigger => trigger.evaluate(tick),
        };
        let mut readapt_info = Value::Null;
        if due {
            let r = readapt(&sv, &state, seed, tick);
            state = r.state;
            readapt_info = r.info;
            trigger.last_adapt = tick;
        }
        let res = Sampler::new()
            .draws(k)
            .seed(tick_seed(seed, tick))
            .threads(CHAINS)
            .limits(Limits::new().admit_worst_case())
            .run_warm(&sv, &state);
        let p = match res {
            Ok(p) => p,
            Err(e) => {
                let rec = json!({"tick": tick, "n": big_n, "start": tick, "status": "error",
                    "error": e.to_string(), "wall_seconds": t0.elapsed().as_secs_f64(),
                    "readapt": due, "readapt_info": readapt_info, "trigger": trig});
                emit(&mut log, &rec)?;
                break;
            }
        };
        state = p.warm_state()?;
        let wall = t0.elapsed().as_secs_f64();
        let st = tick_stats(&p);
        trigger.cost.push(st.evals);
        trigger.unchanged.push(st.unchanged);
        let written = tick % draw_every == 0;
        if written {
            write_posterior(&out.join(format!("tick-{tick:04}.f32")), &sv, &p)?;
        }
        let steps: Vec<f64> = state.chains().iter().map(|c| c.step_size).collect();
        let rec = json!({"tick": tick, "n": big_n, "start": tick, "status": "ok", "wall_seconds": wall,
            "k": k, "chains": p.chain_count(), "draws": p.draws_per_chain(), "kept": kept, "written": written,
            "readapt": due, "readapt_info": readapt_info, "trigger": trig,
            "divergences": divergences(&p, 0), "steps": steps,
            "evals_per_transition": st.evals, "depth_mean": st.depth, "step_ratio": st.step_ratio,
            "energy_err_mean": st.energy, "unchanged_frac": st.unchanged,
            "calls": sv.calls.load(Ordering::Relaxed)});
        emit(&mut log, &rec)?;
    }
    Ok(())
}

fn main() -> Result<(), Box<dyn Error>> {
    let a: Vec<String> = env::args().collect();
    let mode = a.get(1).map(String::as_str).unwrap_or("");
    let usage = "usage: wp96 reftick|warm|remapcheck ...";
    let d = load(Path::new(a.get(2).ok_or(usage)?))?;
    match mode {
        "reftick" => {
            let start: usize = a[3].parse()?;
            let n: usize = a[4].parse()?;
            let seed: u64 = a[5].parse()?;
            let stem = PathBuf::from(&a[6]);
            let sv = Sv::new(&d, start, n);
            let (rec, p) = full_fit(&sv, 2000, 20000, seed, Some(REF_RESULT_BYTES))?;
            if let Some(p) = &p {
                write_posterior(&stem.with_extension("f32"), &sv, p)?;
            }
            fs::write(stem.with_extension("json"), serde_json::to_vec(&rec)?)?;
            Ok(())
        }
        "warm" => {
            let big_n: usize = a[3].parse()?;
            let k: usize = a[4].parse()?;
            let seed: u64 = a[5].parse()?;
            let ticks: usize = a[6].parse()?;
            let policy = parse_policy(&a[7])?;
            let draw_every: usize = a[8].parse::<usize>()?.max(1);
            let out = PathBuf::from(&a[9]);
            warm_cell(&d, big_n, k, seed, ticks, policy, draw_every, &out)
        }
        "remapcheck" => {
            let n: usize = a[3].parse()?;
            let old = Sv::new(&d, 0, n);
            let new = Sv::new(&d, 1, n);
            // A deterministic, non-trivial state: two chains with distinct positions and masses.
            let chains: Vec<WarmChain> = (0..2)
                .map(|c| {
                    let dim = 3 + n;
                    let position: Vec<f64> = (0..dim)
                        .map(|i| match i {
                            0 => d.mu_mean + 0.3 * c as f64,
                            1 => d.ls_mean - 0.2 * c as f64,
                            2 => 0.001,
                            _ => ((i * 7 + c * 13) % 11) as f64 / 5.0 - 1.0,
                        })
                        .collect();
                    let mass_diagonal: Vec<f64> =
                        (0..dim).map(|i| 0.5 + ((i + c) % 5) as f64 / 4.0).collect();
                    WarmChain {
                        position,
                        step_size: 0.1 + 0.05 * c as f64,
                        mass_diagonal,
                    }
                })
                .collect();
            let state = WarmState::new(chains)?;
            let shifted = shift_window(&state, d.rho)?;
            let mut max_err: f64 = 0.0;
            let mut mass_ok = true;
            for (c, s) in state.chains().iter().zip(shifted.chains()) {
                let h_old = old.h_path(&c.position);
                let h_new = new.h_path(&s.position);
                for (hn, ho) in h_new.iter().zip(h_old.iter().skip(1)) {
                    max_err = max_err.max((hn - ho).abs() / (1.0 + ho.abs()));
                }
                mass_ok &= s.mass_diagonal[..4]
                    == [
                        c.mass_diagonal[0],
                        c.mass_diagonal[1],
                        c.mass_diagonal[2],
                        c.mass_diagonal[3],
                    ]
                    && s.mass_diagonal[4..n + 2] == c.mass_diagonal[5..n + 3]
                    && s.mass_diagonal[n + 2] == 1.0
                    && s.position[n + 2] == 0.0
                    && s.step_size == c.step_size;
            }
            let ok = max_err < 1e-12 && mass_ok;
            let out = json!({"ok": ok, "max_rel_h_error": max_err, "mass_and_step_ok": mass_ok, "n": n,
                "dimension": 3 + n});
            fs::write(&a[4], serde_json::to_vec_pretty(&out)?)?;
            println!("{out}");
            if ok {
                Ok(())
            } else {
                Err("shift_window does not preserve the h path".into())
            }
        }
        _ => Err(usage.into()),
    }
}
