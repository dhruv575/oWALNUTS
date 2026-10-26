//! WP89 SV cell (`STUDIES/sv_stuck_chains_v1`): one (arm, seed) oWALNUTS run of the WP84
//! price-only stochastic-volatility target (`STUDIES/online_sv_quote_v1/rust/src/main.rs`,
//! copied verbatim: q = [mu, log_sigma, beta, z[n]], rho = 0.95, nu = 5) with per-transition
//! warmup and sampling telemetry streamed through the observe-only comparison observer
//! (the WP57 / WP67 `trap_cell.rs` pattern).
//!
//! Usage: `sv-cell <data.json> <N> <arm> <seed> <out.json> <telemetry.json> [threads]`
//!
//! Every arm runs 4 chains x 1,000 warmup / 1,000 retained on `threads` threads with
//! `Metric::diagonal()`, `Tuning::default()` and `Limits::admit_worst_case()`. The starts are
//! drawn here exactly as `Sampler::run_with_init` draws them (`candidate_starts`), except for
//! the `normal` arm (nutpie's default Stan init: one standard-normal draw per unconstrained
//! coordinate, no candidate selection).
//!
//! Arms (`adaptation` is `Adaptation::default()` unless stated; `custom` means
//! `Adaptation::Custom` of the configuration `Adaptation::default()` builds, i.e.
//! `WarmupConfig::new(0.8)` + `DEFAULT_WARMUP_EXHAUSTION` + `DEFAULT_METRIC_REGULARIZATION`):
//! - `defaults`: `Init::best_of(16)`.
//! - `custom_noop` (smoke only): `custom`, nothing else; must equal `defaults` bit for bit.
//! - `uniform`: `Init::uniform()` (CmdStan's rule, one candidate).
//! - `median16`: `Init::median_of(16)`.
//! - `normal`: standard-normal starts (nutpie's rule), seed `splitmix64(seed ^ NORMAL_TAG)`.
//! - `stan_reg`: `custom` with `DiagonalMetricRegularization::Stan`.
//! - `grad_metric`: `custom` with `DiagonalMetricEstimator::GradientInformed` (research, WP71).
//! - `early_windows`: `custom` with `WarmupWindowConfig::new(10, 10, 50)`.
//! - `stan_search`: `custom` with `InitialStepSearchConfig::stan()`.
//! - `small_step`: `defaults` with `Tuning::step_size(0.05)` (initial macro step).
//! - `restart`: `custom` with `TrappedChainRestartConfig::step_rule()` (WP67, research).
//! - `guard-<ratio>-<window>`: `custom` with `step_rule().with_step_ratio(ratio)
//!   .with_check_window(window)` (the WP89 candidate; `window` is the index of the slow
//!   window whose end is scored, 0 = WP67's).
//!
//! Output `out.json`: starts, candidate log densities, per chain the retained
//! `[mu, log_sigma, h_last]` draws, draw hash, warnings, trapped-chain checks, final step and
//! mass diagonal, work totals. Output `telemetry.json`: per chain and transition
//! `[t, discarded, stage, window, step, depth, stop, target_evaluations, divergent,
//! log_density, acceptance_statistic, max_abs_energy_error, zero_density,
//! recoverable_failures, position_changed, log_sigma, mu, max_abs_gradient, epoch]`, plus
//! every installed metric diagonal (chain, transition, window, diagonal).
#![forbid(unsafe_code)]

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_WARMUP_EXHAUSTION, Init, Limits, Metric,
    Sampler, StartSelection, Target, TargetError, Tuning, WarmupConfig, candidate_starts,
};
use owalnuts::walnutpie::{
    ALGORITHM_REVISION, ComparisonObserver, ComparisonTransitionObservation,
    DiagonalMetricEstimator, DiagonalMetricRegularization, InitialStepSearchConfig,
    MetricUpdateOutcome, ProposalObservation, ProposalObservationControl, ProposalObserver,
    TrappedChainCheck, TrappedChainRestartConfig, WarmupPhase, WarmupWindowConfig,
};
use serde_json::{Value, json};
use std::num::NonZeroUsize;
use std::sync::Mutex;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Instant;
use std::{env, error::Error, fs, path::Path};

const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;
/// Seed tag of the `normal` arm's start stream.
const NORMAL_TAG: u64 = 0x6e6f_726d_616c_3839;

// ---------------------------------------------------------------- target (WP84, verbatim)

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

// ---------------------------------------------------------------- hashing

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

// ---------------------------------------------------------------- observers

struct NoProposals;
impl ProposalObserver for NoProposals {
    fn observe(&self, _: &ProposalObservation) {}
}

const FIELDS: [&str; 19] = [
    "t",
    "discarded",
    "stage",
    "window",
    "step",
    "depth",
    "stop",
    "target_evaluations",
    "divergent",
    "log_density",
    "acceptance_statistic",
    "max_abs_energy_error",
    "zero_density",
    "recoverable_failures",
    "position_changed",
    "log_sigma",
    "mu",
    "max_abs_gradient",
    "epoch",
];
const STOPS: [&str; 6] = [
    "MaximumDepth",
    "OuterUTurn",
    "RecursiveUTurn",
    "RefinementExhausted",
    "ReverseCoarserAccepted",
    "InvalidEvaluation",
];

struct Recorder {
    rows: Mutex<Vec<Vec<[f64; 19]>>>,
    /// (chain, transition, window, installed diagonal) at every installed metric update.
    metrics: Mutex<Vec<Value>>,
    /// Per chain: (epoch, last transition seen); a transition index at or below the last one
    /// seen starts a new epoch (a restarted run).
    epochs: Mutex<Vec<(usize, Option<usize>)>>,
}
impl ComparisonObserver for Recorder {
    fn observe(&self, o: &ComparisonTransitionObservation) {
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
        let stop = STOPS
            .iter()
            .position(|x| *x == stop)
            .map_or(-1.0, |i| i as f64);
        let epoch = {
            let mut epochs = self.epochs.lock().unwrap();
            let (epoch, last) = &mut epochs[o.chain];
            if last.is_some_and(|l| o.transition <= l) {
                *epoch += 1;
            }
            *last = Some(o.transition);
            *epoch
        };
        let max_grad = o
            .selected_gradient
            .iter()
            .fold(0.0_f64, |m, g| m.max(g.abs()));
        let row = [
            o.transition as f64,
            f64::from(u8::from(o.discarded)),
            stage,
            window,
            d.step_size(),
            d.depth() as f64,
            stop,
            d.target_evaluations() as f64,
            f64::from(u8::from(d.divergent())),
            o.selected_log_density,
            d.acceptance_statistic().unwrap_or(f64::NAN),
            d.maximum_absolute_energy_error(),
            d.zero_density_evaluations() as f64,
            d.recoverable_target_failures() as f64,
            f64::from(u8::from(d.position_changed())),
            o.selected_theta.get(1).copied().unwrap_or(f64::NAN),
            o.selected_theta.first().copied().unwrap_or(f64::NAN),
            max_grad,
            epoch as f64,
        ];
        self.rows.lock().unwrap()[o.chain].push(row);
        if let Some(a) = &o.adaptation
            && matches!(a.metric_update, Some(MetricUpdateOutcome::Installed))
            && let Some(diag) = &a.installed_metric
        {
            self.metrics.lock().unwrap().push(json!({
                "chain": o.chain, "transition": o.transition, "epoch": epoch,
                "window": a.window_index, "step_after": a.active_step_after,
                "diagonal": diag,
            }));
        }
    }
}

// ---------------------------------------------------------------- arms

enum Starts {
    Candidates(usize, StartSelection),
    Normal,
}

struct Arm {
    starts: Starts,
    adaptation: Adaptation,
    tuning: Tuning,
}

fn custom() -> Result<WarmupConfig, Box<dyn Error>> {
    Ok(WarmupConfig::new(0.8)?
        .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
        .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION))
}

fn arm(name: &str) -> Result<Arm, Box<dyn Error>> {
    let best16 = || Starts::Candidates(16, StartSelection::HighestDensity);
    let plain = |starts: Starts, adaptation: Adaptation| Arm {
        starts,
        adaptation,
        tuning: Tuning::default(),
    };
    let c = Adaptation::Custom;
    Ok(match name {
        "defaults" => plain(best16(), Adaptation::default()),
        "custom_noop" => plain(best16(), c(custom()?)),
        "uniform" => plain(
            Starts::Candidates(1, StartSelection::HighestDensity),
            Adaptation::default(),
        ),
        "median16" => plain(
            Starts::Candidates(16, StartSelection::MedianDensity),
            Adaptation::default(),
        ),
        "normal" => plain(Starts::Normal, Adaptation::default()),
        "stan_reg" => plain(
            best16(),
            c(custom()?.with_metric_regularization(DiagonalMetricRegularization::Stan)),
        ),
        "grad_metric" => plain(
            best16(),
            c(custom()?
                .with_diagonal_metric_estimator(DiagonalMetricEstimator::GradientInformed)),
        ),
        "early_windows" => plain(
            best16(),
            c(custom()?.with_windows(WarmupWindowConfig::new(
                10,
                NonZeroUsize::new(10).unwrap(),
                50,
            )?)),
        ),
        "stan_search" => plain(
            best16(),
            c(custom()?.with_initial_step_search(InitialStepSearchConfig::stan())),
        ),
        "small_step" => Arm {
            starts: best16(),
            adaptation: Adaptation::default(),
            tuning: Tuning::default().step_size(0.05),
        },
        "restart" => plain(
            best16(),
            c(custom()?.with_trapped_chain_restart(TrappedChainRestartConfig::step_rule())),
        ),
        other => {
            let rest = other
                .strip_prefix("guard-")
                .ok_or_else(|| format!("unknown arm {other:?}"))?;
            let (ratio, window) = rest
                .split_once('-')
                .ok_or_else(|| format!("guard arm {other:?} needs guard-<ratio>-<window>"))?;
            let restart = TrappedChainRestartConfig::step_rule()
                .with_step_ratio(ratio.parse::<f64>()?)?
                .with_check_window(window.parse::<usize>()?);
            plain(best16(), c(custom()?.with_trapped_chain_restart(restart)))
        }
    })
}

fn check_json(c: &TrappedChainCheck) -> Value {
    json!({
        "chain": c.chain(), "transition": c.transition(), "step": c.step(),
        "median_step": c.median_step(), "threshold": c.threshold(),
        "restarted": c.restarted(), "abandoned_target_calls": c.abandoned_target_calls(),
        "abandoned_log_density": c.abandoned_log_density(),
        "replacement_start_log_density": c.replacement_start_log_density(),
        "replacement_start_log_sigma": c.replacement_start().and_then(|s| s.get(1).copied()),
        "replacement_candidate_evaluations": c.replacement_candidate_evaluations(),
        "replacement_seed": c.replacement_seed().map(|s| format!("{s:016x}")),
    })
}

/// One splitmix64 output (the stream of the `normal` arm; the library's own is crate-private).
fn splitmix64(state: &mut u64) -> u64 {
    *state = state.wrapping_add(0x9e37_79b9_7f4a_7c15);
    let mut z = *state;
    z = (z ^ (z >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    z ^ (z >> 31)
}

/// Standard-normal starts: Box-Muller on a splitmix64 stream (nutpie's rule, not its RNG).
fn normal_starts(seed: u64, dimension: usize) -> Vec<Vec<f64>> {
    let mut state = seed ^ NORMAL_TAG;
    let mut next = move || {
        // uniform in (0, 1]
        ((splitmix64(&mut state) >> 11) as f64 + 1.0) / (1u64 << 53) as f64
    };
    (0..CHAINS)
        .map(|_| {
            (0..dimension)
                .map(|_| {
                    let (u1, u2) = (next(), next());
                    (-2.0 * u1.ln()).sqrt() * (2.0 * std::f64::consts::PI * u2).cos()
                })
                .collect()
        })
        .collect()
}

#[allow(clippy::too_many_lines)]
fn run(
    data: &Path,
    n: usize,
    arm_name: &str,
    seed: u64,
    out: &Path,
    telemetry_out: &Path,
    threads: usize,
) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    let d = load(data)?;
    let target = Sv::new(&d, n);
    let dimension = target.dimension();
    let arm = arm(arm_name)?;
    let kernel = arm.tuning.to_kernel()?;
    let (starts, init_json) = match arm.starts {
        Starts::Candidates(candidates, selection) => {
            let c = candidate_starts(&target, CHAINS, seed, 2.0, candidates, 100, selection)?;
            (
                c.starts.clone(),
                json!({"rule": format!("candidate_starts(radius 2, candidates {candidates}, attempts 100, {selection:?})"),
                       "candidates": candidates,
                       "start_log_densities": c.start_log_densities,
                       "candidate_log_densities": c.candidate_log_densities,
                       "chosen": c.chosen, "evaluations": c.evaluations}),
            )
        }
        Starts::Normal => {
            let starts = normal_starts(seed, dimension);
            let mut g = vec![0.0; dimension];
            let lps: Vec<f64> = starts
                .iter()
                .map(|s| {
                    target
                        .log_density_gradient(s, &mut g)
                        .unwrap_or(f64::NAN)
                })
                .collect();
            (
                starts,
                json!({"rule": "standard normal per coordinate (nutpie's Stan init), no selection",
                       "candidates": 1, "start_log_densities": lps}),
            )
        }
    };
    let start_search_calls = target.calls.load(Ordering::Relaxed);
    let start_log_sigma: Vec<f64> = starts.iter().map(|s| s[1]).collect();
    let start_mu: Vec<f64> = starts.iter().map(|s| s[0]).collect();
    let mut starts_hash = Fnv::new();
    for s in &starts {
        for &x in s {
            starts_hash.f64(x);
        }
    }
    let sampler = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .seed(seed)
        .threads(threads)
        .metric(Metric::diagonal())
        .adaptation(arm.adaptation.clone())
        .tuning(arm.tuning.clone())
        .limits(Limits::new().admit_worst_case());
    let mut v = json!({
        "schema": "sv-stuck-chains-v1-sv-cell",
        "arm": arm_name, "seed": seed, "n": n, "dimension": dimension, "threads": threads,
        "chains": CHAINS, "warmup": WARMUP, "retained": RETAINED,
        "init": init_json, "init_default": format!("{:?}", Init::default()),
        "starts_hash": starts_hash.hex(),
        "start_log_sigma": start_log_sigma, "start_mu": start_mu,
        "start_search_calls": start_search_calls,
        "adaptation": format!("{:?}", arm.adaptation),
        "tuning": format!("{:?}", arm.tuning),
        "kernel_max_depth": kernel.max_depth(),
        "algorithm_revision_const": ALGORITHM_REVISION,
        "telemetry_fields": FIELDS, "stop_reasons": STOPS,
    });
    let o = v.as_object_mut().unwrap();
    let recorder = Recorder {
        rows: Mutex::new(vec![Vec::new(); CHAINS]),
        metrics: Mutex::new(Vec::new()),
        epochs: Mutex::new(vec![(0, None); CHAINS]),
    };
    let proposals = NoProposals;
    let control = ProposalObservationControl::new(&proposals, NonZeroUsize::new(1).unwrap(), 0);
    let begin = Instant::now();
    let result = sampler.run_with_comparison_observers(&target, &starts, &control, &recorder);
    let wall = begin.elapsed().as_secs_f64();
    o.insert("wall_seconds_pinned_cotenanted".into(), json!(wall));
    o.insert(
        "target_calls_total".into(),
        json!(target.calls.load(Ordering::Relaxed)),
    );
    fs::write(
        telemetry_out,
        serde_json::to_vec(&json!({
            "arm": arm_name, "seed": seed, "fields": FIELDS, "stop_reasons": STOPS,
            "rows": *recorder.rows.lock().unwrap(),
            "installed_metrics": *recorder.metrics.lock().unwrap(),
        }))?,
    )?;
    let posterior = match result {
        Ok(p) => p,
        Err(e) => {
            o.insert("status".into(), json!("error"));
            o.insert("error_kind".into(), json!(format!("{:?}", e.kind())));
            o.insert("error".into(), json!(e.to_string()));
            fs::write(out, serde_json::to_vec(&v)?)?;
            eprintln!(
                "{arm_name} seed {seed}: error {:?} after {wall:.1}s: {e}",
                e.kind()
            );
            return Ok(());
        }
    };
    let mut all = Fnv::new();
    let chains = posterior
        .chains()
        .iter()
        .map(|chain| {
            let t = chain.telemetry();
            let (retained, discarded, total) = (t.retained(), t.discarded(), t.total());
            let mut h = Fnv::new();
            let mut draws: Vec<[f64; 3]> = Vec::with_capacity(RETAINED);
            for i in 0..RETAINED {
                let s = chain.sample(i).unwrap();
                for &x in s {
                    h.f64(x);
                    all.f64(x);
                }
                draws.push([s[0], s[1], target.h_last(s)]);
            }
            let diags = chain.diagnostics();
            let step_at = |t: usize| diags.get(t).map(|d| d.step_size());
            json!({
                "draws_mu_logsigma_hlast": draws, "draw_hash": h.hex(),
                "divergences": retained.divergences(),
                "warmup_divergences": discarded.divergences(),
                "recoverable_target_failures": total.recoverable_target_failures(),
                "maximum_depth_stops": retained.maximum_depth_stops(),
                "warmup_maximum_depth_stops": discarded.maximum_depth_stops(),
                "refinement_exhaustions": retained.refinement_exhaustion_stops(),
                "retained_target_calls": retained.target_calls_total(),
                "warmup_target_calls": discarded.target_calls_total(),
                "total_target_calls": total.target_calls_total(),
                "final_step_size": chain.metadata().tuning().step_size(),
                "mass_diagonal": chain.metadata().mass_diagonal(),
                "step_at_transition": {"74": step_at(74), "99": step_at(99), "149": step_at(149),
                                       "249": step_at(249), "449": step_at(449), "949": step_at(949),
                                       "999": step_at(999)},
                "effective_seed": format!("{:016x}", chain.metadata().effective_seed()),
                "trapped_chain_checks": t.trapped_chain_checks().iter().map(check_json).collect::<Vec<_>>(),
                "initial_step_search": t.initial_step_search().map(|s| json!({
                    "initial_step": s.initial_step(), "selected_step": s.selected_step(),
                    "target_calls": s.target_calls()})),
            })
        })
        .collect::<Vec<_>>();
    let warnings = posterior.chain_warnings();
    o.insert("status".into(), json!("ok"));
    o.insert("draw_hash".into(), json!(all.hex()));
    o.insert("chains_data".into(), json!(chains));
    o.insert(
        "chain_warnings".into(),
        json!(
            warnings
                .iter()
                .map(|w| format!("{w:?}"))
                .collect::<Vec<_>>()
        ),
    );
    o.insert(
        "chain_warning_chains".into(),
        json!(warnings.iter().map(|w| w.chain()).collect::<Vec<_>>()),
    );
    o.insert(
        "algorithm_revision".into(),
        json!(posterior.algorithm_revision()),
    );
    o.insert("timing_estimand".into(), json!("wall around Sampler::run_with_comparison_observers; core-pinned on a shared box (pinned, co-tenanted)"));
    fs::write(out, serde_json::to_vec(&v)?)?;
    eprintln!(
        "{arm_name} seed {seed}: ok wall {wall:.2}s hash {} warnings {}",
        all.hex(),
        warnings.len()
    );
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [data, n, arm, seed, out, telemetry, rest @ ..] => {
            let threads = rest.first().map_or(Ok(CHAINS), |t| t.parse::<usize>());
            match (n.parse::<usize>(), seed.parse::<u64>(), threads) {
                (Ok(n), Ok(s), Ok(t)) => run(
                    Path::new(data),
                    n,
                    arm,
                    s,
                    Path::new(out),
                    Path::new(telemetry),
                    t,
                ),
                _ => Err("N, seed and threads must be integers".into()),
            }
        }
        _ => Err(
            "usage: <data.json> <N> <arm> <seed> <out.json> <telemetry.json> [threads]".into(),
        ),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
