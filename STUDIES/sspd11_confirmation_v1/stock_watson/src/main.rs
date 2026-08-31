#![forbid(unsafe_code)]

//! Paper Stock–Watson stochastic-volatility reproduction runner (WP2b).
//!
//! Reads `protocol.json`, runs one named oWALNUTS arm, and writes functionals,
//! latent-path quantiles, per-transition traces and telemetry.
//! Usage: `runner --preflight out.json`, `runner --sample ARM out.json`,
//! `runner --data out.json` (writes the simulated series and truth).

use owalnuts::walnutpie::{
    DiagonalMass, KernelTuning, PaperAdaptationConfig, PaperAdaptationOutcome, RunConfig,
    StopReason, Target, TargetError, TargetEvaluationAdmissionLimit, TargetEvaluationBudget,
    WarmupConfig, preflight_chains_with_target_budget, sample_chains_with_target_budget,
};
use rand::rngs::SmallRng;
use rand::{Rng, SeedableRng};
use rand_distr::StandardNormal;
use serde_json::{Value, json};
use std::{
    env,
    error::Error,
    fs,
    num::NonZeroUsize,
    path::{Path, PathBuf},
    sync::atomic::{AtomicUsize, Ordering},
    time::{Duration, Instant},
};

/// Stock–Watson model, JMLR §4.4 eqs. (35)–(38), in the paper's innovation
/// parameterization with a single random-walk scale `sigma` shared by `z` and
/// `x` and prior `sigma^-2 ~ Gamma(5, rate 0.5)`.
///
/// Unconstrained layout, dimension `3T`:
/// `[0] = phi = log sigma^2`;
/// `[1] = z_1`, `[1+k] = eta_z_{k+1} = (z_{k+1}-z_k)/sigma` for `k = 1..T-2`;
/// `[T] = x_1`, `[T+k] = eta_x_{k+1}` for `k = 1..T-1`;
/// `[2T] = mu_1`, `[2T+k] = eta_mu_{k+1} = (mu_{k+1}-mu_k) exp(-z_k/2)` for `k = 1..T-1`.
///
/// Initial-state priors `z_1, x_1, mu_1 ~ N(0, s0^2)` are not stated in the
/// paper; `s0` is a protocol constant.
/// Amendment 7: gradient components are clipped to this magnitude in the
/// finite-penalty policy so leapfrog positions stay finite in the penalty
/// region. Any state with a larger gradient has an energy error many orders
/// above `delta` and can never be part of an accepted macro step.
const GRADIENT_BOUND: f64 = 1e8;

struct StockWatson {
    y: Vec<f64>,
    s0: f64,
    calls: AtomicUsize,
    deadline: Option<Instant>,
    /// Amendment 2: `true` returns a finite penalty (`-1e10`, zero gradient)
    /// for non-finite evaluations so the kernel's energy-error refinement can
    /// act; `false` returns a recoverable target error (kernel stops the
    /// transition with `InvalidEvaluation`).
    finite_penalty: bool,
}

impl StockWatson {
    fn t(&self) -> usize {
        self.y.len()
    }

    /// Latent paths `(z, x, mu)` for a parameter vector.
    fn paths(&self, q: &[f64]) -> (Vec<f64>, Vec<f64>, Vec<f64>) {
        let t = self.t();
        let sigma = (0.5 * q[0]).exp();
        let mut z = Vec::with_capacity(t - 1);
        z.push(q[1]);
        for k in 1..t - 1 {
            z.push(z[k - 1] + sigma * q[1 + k]);
        }
        let mut x = Vec::with_capacity(t);
        x.push(q[t]);
        for k in 1..t {
            x.push(x[k - 1] + sigma * q[t + k]);
        }
        let mut mu = Vec::with_capacity(t);
        mu.push(q[2 * t]);
        for k in 1..t {
            mu.push(mu[k - 1] + (0.5 * z[k - 1]).exp() * q[2 * t + k]);
        }
        (z, x, mu)
    }

    fn log_density_gradient_impl(&self, q: &[f64], gradient: &mut [f64]) -> Option<f64> {
        let t = self.t();
        let phi = q[0];
        let sigma = (0.5 * phi).exp();
        let (z, x, mu) = self.paths(q);
        if z.iter().chain(&x).chain(&mu).any(|v| !v.is_finite()) {
            return None;
        }
        let inv_s0_sq = 1.0 / (self.s0 * self.s0);
        // Prior on phi = log sigma^2 with sigma^-2 ~ Gamma(5, rate 0.5):
        // log p(phi) = -5 phi - 0.5 exp(-phi) + const.
        let mut lp = -5.0 * phi - 0.5 * (-phi).exp();
        lp -= 0.5 * (z[0] * z[0] + x[0] * x[0] + mu[0] * mu[0]) * inv_s0_sq;
        for k in 1..t - 1 {
            lp -= 0.5 * q[1 + k] * q[1 + k];
        }
        for k in 1..t {
            lp -= 0.5 * q[t + k] * q[t + k];
            lp -= 0.5 * q[2 * t + k] * q[2 * t + k];
        }
        // Observation likelihood and direct adjoints.
        let mut d_mu = vec![0.0; t];
        let mut d_x = vec![0.0; t];
        for i in 0..t {
            let resid = self.y[i] - mu[i];
            // Amendment 7: bounded exponent keeps the penalty region finite so
            // the kernel's energy-error refinement (not its non-finite stop)
            // handles overflowing coarse attempts, as the reference does.
            let e = if self.finite_penalty { (-x[i]).min(700.0).exp() } else { (-x[i]).exp() };
            if !e.is_finite() {
                return None;
            }
            lp += -0.5 * x[i] - 0.5 * resid * resid * e;
            d_mu[i] = resid * e;
            d_x[i] = -0.5 + 0.5 * resid * resid * e;
        }
        if !lp.is_finite() {
            return None;
        }
        // Suffix sums: total derivatives with respect to each latent state.
        for i in (0..t - 1).rev() {
            d_mu[i] += d_mu[i + 1];
            d_x[i] += d_x[i + 1];
        }
        // z_k (k = 0..T-2) enters mu_{k+1} through exp(z_k/2) and z_{k+1}.
        let mut d_z = vec![0.0; t - 1];
        for k in (0..t - 1).rev() {
            let local = 0.5 * (0.5 * z[k]).exp() * q[2 * t + k + 1] * d_mu[k + 1];
            d_z[k] = local + if k + 1 < t - 1 { d_z[k + 1] } else { 0.0 };
        }
        let mut g_phi = -5.0 + 0.5 * (-phi).exp();
        gradient[1] = d_z[0] - z[0] * inv_s0_sq;
        for k in 1..t - 1 {
            gradient[1 + k] = sigma * d_z[k] - q[1 + k];
            g_phi += 0.5 * sigma * q[1 + k] * d_z[k];
        }
        gradient[t] = d_x[0] - x[0] * inv_s0_sq;
        for k in 1..t {
            gradient[t + k] = sigma * d_x[k] - q[t + k];
            g_phi += 0.5 * sigma * q[t + k] * d_x[k];
        }
        gradient[2 * t] = d_mu[0] - mu[0] * inv_s0_sq;
        for k in 1..t {
            gradient[2 * t + k] = (0.5 * z[k - 1]).exp() * d_mu[k] - q[2 * t + k];
        }
        gradient[0] = g_phi;
        if gradient.iter().any(|g| !g.is_finite()) {
            return None;
        }
        if self.finite_penalty {
            for g in gradient.iter_mut() {
                *g = g.clamp(-GRADIENT_BOUND, GRADIENT_BOUND);
            }
        }
        Some(lp)
    }
}

impl Target for StockWatson {
    fn dimension(&self) -> usize {
        3 * self.t()
    }

    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        if self
            .deadline
            .is_some_and(|deadline| Instant::now() >= deadline)
        {
            return Err(TargetError::new("arm wall cap exceeded"));
        }
        match self.log_density_gradient_impl(q, gradient) {
            Some(lp) => Ok(lp),
            None if self.finite_penalty => {
                gradient.iter_mut().for_each(|g| *g = 0.0);
                Ok(-1e10)
            }
            None => Err(TargetError::recoverable("non-finite Stock-Watson evaluation")),
        }
    }
}

/// Simulate `y` from the model with true scale `sigma` and initial states.
fn simulate(t: usize, sigma: f64, z1: f64, x1: f64, mu1: f64, seed: u64) -> Value {
    let mut rng = SmallRng::seed_from_u64(seed);
    let mut normal = || -> f64 { rng.sample(StandardNormal) };
    let mut z = vec![z1];
    for k in 1..t - 1 {
        let next = z[k - 1] + sigma * normal();
        z.push(next);
    }
    let mut x = vec![x1];
    for k in 1..t {
        let next = x[k - 1] + sigma * normal();
        x.push(next);
    }
    let mut mu = vec![mu1];
    for k in 1..t {
        let next = mu[k - 1] + (0.5 * z[k - 1]).exp() * normal();
        mu.push(next);
    }
    let y: Vec<f64> = (0..t)
        .map(|i| mu[i] + (0.5 * x[i]).exp() * normal())
        .collect();
    json!({
        "schema": "owalnuts-paper-stock-watson-data/v1",
        "t": t, "sigma": sigma, "log_sigma2": (sigma * sigma).ln(), "data_seed": seed,
        "z": z, "x": x, "mu": mu, "y": y
    })
}

struct Arm {
    name: String,
    step_size: f64,
    max_error: f64,
    levels: usize,
    depth: usize,
    min_micro: usize,
    divergence_threshold: f64,
    discarded: usize,
    retained: usize,
    base_seed: u64,
    paper: Option<(f64, f64, f64)>,
}

fn load_json(dir: &Path, file: &str) -> Result<Value, Box<dyn Error>> {
    Ok(serde_json::from_slice(&fs::read(dir.join(file))?)?)
}

fn arm(protocol: &Value, name: &str) -> Result<Arm, Box<dyn Error>> {
    let a = protocol["arms"]
        .get(name)
        .ok_or_else(|| format!("unknown arm {name}"))?;
    let u = |k: &str| -> Result<usize, Box<dyn Error>> {
        Ok(usize::try_from(a[k].as_u64().ok_or_else(|| format!("{k} missing"))?)?)
    };
    let f = |k: &str| -> Result<f64, Box<dyn Error>> {
        a[k].as_f64().ok_or_else(|| format!("{k} missing").into())
    };
    let paper = a.get("paper_adaptation").filter(|p| !p.is_null()).map(|p| {
        (
            p["global_energy_bound"].as_f64().unwrap_or(2.0),
            p["quantile_probability"].as_f64().unwrap_or(0.95),
            p["unrefined_fraction_target"].as_f64().unwrap_or(0.8),
        )
    });
    Ok(Arm {
        name: name.to_string(),
        step_size: f("step_size")?,
        max_error: f("max_error")?,
        levels: u("max_refinement_levels")?,
        depth: u("max_depth")?,
        min_micro: u("min_micro_steps")?,
        divergence_threshold: f("divergence_threshold")?,
        discarded: u("discarded")?,
        retained: u("retained")?,
        base_seed: a["base_seed"].as_u64().ok_or("base_seed missing")?,
        paper,
    })
}

fn config(arm: &Arm) -> Result<RunConfig, Box<dyn Error>> {
    let tuning = KernelTuning::new(
        arm.step_size,
        NonZeroUsize::new(arm.depth).ok_or("depth")?,
        NonZeroUsize::new(arm.min_micro).ok_or("min micro")?,
        NonZeroUsize::new(arm.levels).ok_or("levels")?,
        arm.max_error,
    )?
    .with_divergence_threshold(arm.divergence_threshold)?;
    let mut config = RunConfig::new(
        arm.discarded,
        NonZeroUsize::new(arm.retained).ok_or("retained")?,
        arm.base_seed,
    )
    .with_tuning(tuning);
    if let Some((delta, p, gamma)) = arm.paper {
        config = config.with_warmup(
            WarmupConfig::default()
                .with_mass_adaptation(false)
                .with_paper_adaptation(PaperAdaptationConfig::new(delta, p, gamma)?),
        );
    }
    Ok(config)
}

/// Typical-set starts (amendments 3 and 5): the innovation image of the
/// simulated true latent paths at the chain's own `sigma`, with `phi` offset
/// per chain from the true `log sigma^2` and independent `N(0, jitter^2)`
/// noise on every coordinate, seeded per chain. This evaluates the fixed paper kernel in the stationary regime, as
/// the paper's Figure 16 does; it is not a warmup test.
fn starts(protocol: &Value, data: &Value) -> Result<Vec<Vec<f64>>, Box<dyn Error>> {
    let t = usize::try_from(data["t"].as_u64().ok_or("t")?)?;
    let vec = |key: &str| -> Result<Vec<f64>, Box<dyn Error>> {
        data[key]
            .as_array()
            .ok_or("truth array")?
            .iter()
            .map(|v| v.as_f64().ok_or_else(|| "truth value".into()))
            .collect()
    };
    let (z, x, mu) = (vec("z")?, vec("x")?, vec("mu")?);
    let phi_true = data["log_sigma2"].as_f64().ok_or("log_sigma2")?;
    let seed = protocol["start_seed"].as_u64().ok_or("start_seed")?;
    let jitter = protocol["start_jitter_sd"].as_f64().ok_or("start_jitter_sd")?;
    let mut out = Vec::new();
    for (chain, offset) in protocol["start_log_sigma2_offsets"]
        .as_array()
        .ok_or("start_log_sigma2_offsets")?
        .iter()
        .enumerate()
    {
        let mut rng = SmallRng::seed_from_u64(seed + chain as u64);
        let mut q: Vec<f64> = (0..3 * t)
            .map(|_| jitter * rng.sample::<f64, _>(StandardNormal))
            .collect();
        q[0] = phi_true + offset.as_f64().ok_or("offset")?;
        // Innovations at the chain's own sigma, so the reconstructed latent
        // paths equal the simulated truth for every phi offset.
        let sigma = (0.5 * q[0]).exp();
        q[1] += z[0];
        for k in 1..t - 1 {
            q[1 + k] += (z[k] - z[k - 1]) / sigma;
        }
        q[t] += x[0];
        for k in 1..t {
            q[t + k] += (x[k] - x[k - 1]) / sigma;
        }
        q[2 * t] += mu[0];
        for k in 1..t {
            q[2 * t + k] += (mu[k] - mu[k - 1]) * (-0.5 * z[k - 1]).exp();
        }
        out.push(q);
    }
    Ok(out)
}

fn stop_name(stop: StopReason) -> &'static str {
    match stop {
        StopReason::MaximumDepth => "maximum_depth",
        StopReason::OuterUTurn => "outer_uturn",
        StopReason::RecursiveUTurn => "recursive_uturn",
        StopReason::RefinementExhausted => "refinement_exhausted",
        StopReason::ReverseCoarserAccepted => "reverse_coarser_accepted",
        StopReason::InvalidEvaluation => "invalid_evaluation",
        _ => "other",
    }
}

fn quantile(sorted: &[f64], p: f64) -> f64 {
    if sorted.is_empty() {
        return f64::NAN;
    }
    let pos = p * (sorted.len() - 1) as f64;
    let lo = pos.floor() as usize;
    let hi = pos.ceil() as usize;
    sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo as f64)
}

fn main() -> Result<(), Box<dyn Error>> {
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let mut arguments = env::args().skip(1);
    let mode = arguments.next().ok_or("mode required")?;
    let protocol = load_json(&dir, "protocol.json")?;
    let d = &protocol["data"];
    if mode == "--data" {
        let output = PathBuf::from(arguments.next().ok_or("output path required")?);
        if output.exists() {
            return Err("refusing to overwrite data".into());
        }
        let data = simulate(
            usize::try_from(d["t"].as_u64().ok_or("t")?)?,
            d["sigma"].as_f64().ok_or("sigma")?,
            d["z1"].as_f64().ok_or("z1")?,
            d["x1"].as_f64().ok_or("x1")?,
            d["mu1"].as_f64().ok_or("mu1")?,
            match arguments.next() {
                Some(seed) => seed.parse::<u64>()?,
                None => d["data_seed"].as_u64().ok_or("data_seed")?,
            },
        );
        fs::create_dir_all(output.parent().ok_or("output parent")?)?;
        fs::write(output, serde_json::to_vec_pretty(&data)?)?;
        return Ok(());
    }
    let data = load_json(&dir, "artifacts/data.json")?;
    let y: Vec<f64> = data["y"]
        .as_array()
        .ok_or("y")?
        .iter()
        .map(|v| v.as_f64().ok_or("y value"))
        .collect::<Result<_, _>>()?;
    let t = y.len();
    let s0 = protocol["initial_state_prior_sd"].as_f64().ok_or("s0")?;
    let finite_penalty = protocol["nonfinite_policy"] == "finite_penalty";
    let starts = starts(&protocol, &data)?;
    let mass = DiagonalMass::identity(NonZeroUsize::new(3 * t).unwrap());
    let cap = usize::try_from(protocol["runtime_callback_cap"].as_u64().ok_or("cap")?)?;
    let wall_cap = protocol["wall_cap_seconds_per_arm"].as_u64().ok_or("wall cap")?;
    let threads = NonZeroUsize::new(usize::try_from(protocol["threads"].as_u64().unwrap_or(1))?)
        .ok_or("threads")?;
    let arm_names: Vec<String> = protocol["arms"]
        .as_object()
        .ok_or("arms")?
        .keys()
        .cloned()
        .collect();

    if mode == "--starts" {
        // Diagnostic: dump starts and the analytic gradient there (no sampling).
        let output = PathBuf::from(arguments.next().ok_or("output path required")?);
        let probe = StockWatson { y: y.clone(), s0, calls: AtomicUsize::new(0), deadline: None, finite_penalty };
        let mut rows = Vec::new();
        for q in &starts {
            let mut g = vec![0.0; 3 * t];
            let lp = probe.log_density_gradient_impl(q, &mut g);
            rows.push(json!({"q": q, "log_density": lp, "gradient": g}));
        }
        fs::write(output, serde_json::to_vec(&json!({"starts": rows}))?)?;
        return Ok(());
    }
    if mode == "--preflight" {
        let output = PathBuf::from(arguments.next().ok_or("output path required")?);
        if output.exists() {
            return Err("refusing to overwrite preflight output".into());
        }
        let target = StockWatson { y: y.clone(), s0, calls: AtomicUsize::new(0), deadline: None, finite_penalty: false };
        let mut cells = Vec::new();
        for name in &arm_names {
            let arm = arm(&protocol, name)?;
            let config = config(&arm)?;
            let exact = config.worst_case_target_evaluations(NonZeroUsize::new(starts.len()).unwrap())?;
            let budget = TargetEvaluationBudget::new(NonZeroUsize::new(cap.min(exact)).unwrap());
            let report = preflight_chains_with_target_budget(
                &target,
                &starts,
                &mass,
                &config,
                TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap()),
                &budget,
            )?;
            if budget.started() != 0 || target.calls.load(Ordering::Relaxed) != 0 {
                return Err("preflight invoked the target".into());
            }
            cells.push(json!({
                "arm": name,
                "worst_case_target_evaluations": report.worst_case_target_evaluations(),
                "admission_ceiling": report.admission_ceiling(),
                "runtime_callback_cap": budget.maximum(),
                "total_transitions": report.total_transitions(),
            }));
        }
        let result = json!({
            "schema": "owalnuts-paper-stock-watson-preflight/v1",
            "dimension": 3 * t,
            "target_callbacks_started": target.calls.load(Ordering::Relaxed),
            "cells": cells
        });
        fs::create_dir_all(output.parent().ok_or("output parent")?)?;
        fs::write(output, serde_json::to_vec_pretty(&result)?)?;
        return Ok(());
    }
    if mode != "--sample" {
        return Err("mode must be --data, --preflight or --sample".into());
    }
    let name = arguments.next().ok_or("arm name required")?;
    let output = PathBuf::from(arguments.next().ok_or("output path required")?);
    if output.exists() {
        return Err("refusing to overwrite an arm artifact".into());
    }
    let arm = arm(&protocol, &name)?;
    let config = config(&arm)?;
    let exact = config.worst_case_target_evaluations(NonZeroUsize::new(starts.len()).unwrap())?;
    let budget = TargetEvaluationBudget::new(NonZeroUsize::new(cap.min(exact)).unwrap());
    let target = StockWatson {
        y: y.clone(),
        s0,
        calls: AtomicUsize::new(0),
        finite_penalty,
        deadline: Some(
            Instant::now()
                .checked_add(Duration::from_secs(wall_cap))
                .ok_or("deadline overflow")?,
        ),
    };
    let started = Instant::now();
    let chains = sample_chains_with_target_budget(
        &target,
        &starts,
        &mass,
        &config,
        threads,
        TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap()),
        &budget,
    )
    .map_err(|e| format!("arm {} failed closed ({:?}): {e}", arm.name, e.kind()))?;
    let wall = started.elapsed().as_secs_f64();

    let functional_names = [
        "log_sigma2", "z_1", "z_last", "x_1", "x_last", "mu_last", "z_mean", "x_mean", "mu_mean",
    ];
    let mut functionals = Vec::new();
    let mut chain_reports = Vec::new();
    let mut z_all: Vec<Vec<f64>> = vec![Vec::new(); t - 1];
    let mut x_all: Vec<Vec<f64>> = vec![Vec::new(); t];
    let mut mu_all: Vec<Vec<f64>> = vec![Vec::new(); t];
    let probe = StockWatson { y: y.clone(), s0, calls: AtomicUsize::new(0), deadline: None, finite_penalty: false };
    for chain in chains.chains() {
        let mut rows = Vec::with_capacity(chain.retained());
        for draw in 0..chain.retained() {
            let q = chain.sample(draw).unwrap();
            let (z, x, mu) = probe.paths(q);
            for (k, v) in z.iter().enumerate() {
                z_all[k].push(*v);
            }
            for (k, v) in x.iter().enumerate() {
                x_all[k].push(*v);
            }
            for (k, v) in mu.iter().enumerate() {
                mu_all[k].push(*v);
            }
            let mean = |v: &[f64]| v.iter().sum::<f64>() / v.len() as f64;
            rows.push(vec![
                q[0], z[0], z[t - 2], x[0], x[t - 1], mu[t - 1], mean(&z), mean(&x), mean(&mu),
            ]);
        }
        functionals.push(rows);
        let retained = chain.telemetry().retained();
        let discarded = chain.telemetry().discarded();
        let diagnostics = chain.diagnostics();
        let split = chain.metadata().discarded();
        let mut depth_hist = vec![0usize; arm.depth + 1];
        let mut level_hist = vec![0usize; arm.levels + 1];
        let mut stops = std::collections::BTreeMap::<&str, usize>::new();
        let mut divergent = 0usize;
        let mut calls_per_transition = Vec::with_capacity(diagnostics.len());
        let mut trace_rows = Vec::new();
        let mut energy_ranges = Vec::new();
        let mut max_abs_errors = Vec::new();
        for (index, dg) in diagnostics.iter().enumerate() {
            let phase_retained = index >= split;
            let range = dg.maximum_hamiltonian() - dg.minimum_hamiltonian();
            trace_rows.push(json!([
                u8::from(phase_retained),
                dg.depth(),
                stop_name(dg.stop()),
                dg.selected_refinement_level().map(|l| l as i64).unwrap_or(-1),
                dg.target_evaluations(),
                dg.maximum_absolute_energy_error(),
                range,
                dg.reverse_coarser_rejections(),
                u8::from(dg.divergent()),
                dg.trajectory_macro_length()
            ]));
            if !phase_retained {
                continue;
            }
            depth_hist[dg.depth().min(arm.depth)] += 1;
            if let Some(level) = dg.selected_refinement_level() {
                level_hist[level.min(arm.levels)] += 1;
            }
            *stops.entry(stop_name(dg.stop())).or_default() += 1;
            divergent += usize::from(dg.divergent());
            calls_per_transition.push(dg.target_evaluations());
            if range.is_finite() {
                energy_ranges.push(range);
            }
            if dg.maximum_absolute_energy_error().is_finite() {
                max_abs_errors.push(dg.maximum_absolute_energy_error());
            }
        }
        energy_ranges.sort_by(f64::total_cmp);
        max_abs_errors.sort_by(f64::total_cmp);
        let summarize = |v: &[f64]| {
            json!({
                "count": v.len(),
                "q50": quantile(v, 0.5), "q90": quantile(v, 0.9), "q99": quantile(v, 0.99),
                "max": v.last().copied().unwrap_or(f64::NAN),
                "fraction_gt_2": v.iter().filter(|e| **e > 2.0).count() as f64 / v.len().max(1) as f64,
                "fraction_gt_1": v.iter().filter(|e| **e > 1.0).count() as f64 / v.len().max(1) as f64
            })
        };
        let paper_updates: Vec<Value> = chain
            .telemetry()
            .paper_adaptation_updates()
            .iter()
            .map(|u| {
                json!({
                    "transition": u.transition(),
                    "window_index": u.window_index(),
                    "orbits": u.orbits(),
                    "inflation_quantile": u.inflation_quantile(),
                    "energy_range_quantile": u.energy_range_quantile(),
                    "max_error_before": u.max_error_before(),
                    "max_error_after": u.max_error_after(),
                    "unrefined_fraction_mean": u.unrefined_fraction_mean(),
                    "step_before": u.step_before(),
                    "step_after": u.step_after(),
                    "installed": u.outcome() == PaperAdaptationOutcome::Installed
                })
            })
            .collect();
        chain_reports.push(json!({
            "trace_columns": ["retained_phase", "depth", "stop", "selected_refinement_level", "target_evaluations", "max_abs_energy_error", "hamiltonian_range", "reverse_coarser_rejections", "divergent", "trajectory_macro_length"],
            "trace": trace_rows,
            "qualified_step_size": chain.metadata().qualified_step_size(),
            "final_tuning": {
                "step_size": chain.metadata().tuning().step_size(),
                "max_error": chain.metadata().tuning().max_error(),
                "min_micro_steps": chain.metadata().tuning().min_micro_steps(),
                "max_refinement_levels": chain.metadata().tuning().max_refinement_levels()
            },
            "paper_adaptation_updates": paper_updates,
            "retained": {
                "target_calls": retained.target_calls_total(),
                "divergences": retained.divergences(),
                "divergent_transitions_from_diagnostics": divergent,
                "invalid_evaluation_stops": retained.invalid_evaluation_stops(),
                "refinement_exhaustion_stops": retained.refinement_exhaustion_stops(),
                "reverse_coarser_stops": retained.reverse_coarser_stops(),
                "reverse_coarser_rejections": retained.reverse_coarser_rejections(),
                "maximum_depth_stops": retained.maximum_depth_stops(),
                "recoverable_target_failures": retained.recoverable_target_failures(),
                "forward_refinement_attempts": retained.forward_refinement_attempts(),
                "forward_micro_steps": retained.forward_micro_steps_executed(),
                "reverse_coarsening_attempts": retained.reverse_coarsening_attempts(),
                "reverse_micro_steps": retained.reverse_micro_steps_executed(),
                "leaves_attempted": retained.leaves_attempted(),
                "leaves_built": retained.leaves_built(),
                "depth_histogram": depth_hist,
                "selected_refinement_level_histogram": level_hist,
                "stop_reasons": stops,
                "hamiltonian_range": summarize(&energy_ranges),
                "max_abs_energy_error": summarize(&max_abs_errors),
                "mean_target_calls_per_transition": calls_per_transition.iter().sum::<usize>() as f64 / calls_per_transition.len().max(1) as f64
            },
            "discarded": {
                "target_calls": discarded.target_calls_total(),
                "divergences": discarded.divergences(),
                "refinement_exhaustion_stops": discarded.refinement_exhaustion_stops(),
                "maximum_depth_stops": discarded.maximum_depth_stops()
            }
        }));
    }
    let path_quantiles = |all: &mut [Vec<f64>]| -> Value {
        let mut q05 = Vec::new();
        let mut q50 = Vec::new();
        let mut q95 = Vec::new();
        for v in all.iter_mut() {
            v.sort_by(f64::total_cmp);
            q05.push(quantile(v, 0.05));
            q50.push(quantile(v, 0.5));
            q95.push(quantile(v, 0.95));
        }
        json!({"q05": q05, "q50": q50, "q95": q95})
    };
    let report = json!({
        "schema": "owalnuts-paper-stock-watson-arm/v1",
        "arm": arm.name,
        "algorithm_revision": chains.algorithm_revision(),
        "base_seed": chains.base_seed(),
        "dimension": 3 * t,
        "nonfinite_policy": if finite_penalty { "finite_penalty" } else { "recoverable" },
        "settings": {
            "step_size": arm.step_size, "max_error": arm.max_error, "max_refinement_levels": arm.levels,
            "max_depth": arm.depth, "min_micro_steps": arm.min_micro, "divergence_threshold": arm.divergence_threshold,
            "discarded": arm.discarded, "retained": arm.retained,
            "paper_adaptation": arm.paper.map(|(d, p, g)| json!({"global_energy_bound": d, "quantile_probability": p, "unrefined_fraction_target": g}))
        },
        "threads": threads.get(),
        "wall_seconds_including_discarded": wall,
        "wall_cap_seconds": wall_cap,
        "runtime_callback_cap": cap,
        "target_callbacks_started": budget.started(),
        "target_calls_observed": target.calls.load(Ordering::Relaxed),
        "admission_ceiling": exact,
        "functional_names": functional_names,
        "functionals": functionals,
        "latent_quantiles": {
            "z": path_quantiles(&mut z_all),
            "x": path_quantiles(&mut x_all),
            "mu": path_quantiles(&mut mu_all)
        },
        "chains": chain_reports
    });
    fs::create_dir_all(output.parent().ok_or("output parent")?)?;
    fs::write(output, serde_json::to_vec(&report)?)?;
    eprintln!(
        "arm {} done in {:.1}s, {} callbacks",
        arm.name,
        wall,
        budget.started()
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn target(t: usize) -> StockWatson {
        let data = simulate(t, 0.3, 0.0, 0.0, 2.0, 7);
        let y = data["y"].as_array().unwrap().iter().map(|v| v.as_f64().unwrap()).collect();
        StockWatson { y, s0: 10.0, calls: AtomicUsize::new(0), deadline: None, finite_penalty: false }
    }

    #[test]
    fn gradient_matches_central_differences() {
        let t = 12;
        let target = target(t);
        let mut rng = SmallRng::seed_from_u64(11);
        for trial in 0..5 {
            let mut q: Vec<f64> = (0..3 * t).map(|_| rng.sample::<f64, _>(StandardNormal) * 0.7).collect();
            q[0] = -2.5 + 0.5 * trial as f64;
            let mut g = vec![0.0; 3 * t];
            let lp = target.log_density_gradient_impl(&q, &mut g).unwrap();
            assert!(lp.is_finite());
            let mut scratch = vec![0.0; 3 * t];
            for i in 0..3 * t {
                let h = 1e-5 * (1.0 + q[i].abs());
                let mut qp = q.clone();
                qp[i] += h;
                let mut qm = q.clone();
                qm[i] -= h;
                let fp = target.log_density_gradient_impl(&qp, &mut scratch).unwrap();
                let fm = target.log_density_gradient_impl(&qm, &mut scratch).unwrap();
                let fd = (fp - fm) / (2.0 * h);
                let tol = 1e-6 * (1.0 + fd.abs().max(g[i].abs()));
                assert!(
                    (fd - g[i]).abs() <= tol,
                    "coordinate {i}: analytic {} vs finite difference {}",
                    g[i],
                    fd
                );
            }
        }
    }

    #[test]
    fn innovation_reparameterization_round_trips_simulated_truth() {
        let t = 30;
        let data = simulate(t, 0.3, 0.1, -0.2, 2.0, 3);
        let y: Vec<f64> = data["y"].as_array().unwrap().iter().map(|v| v.as_f64().unwrap()).collect();
        let z: Vec<f64> = data["z"].as_array().unwrap().iter().map(|v| v.as_f64().unwrap()).collect();
        let x: Vec<f64> = data["x"].as_array().unwrap().iter().map(|v| v.as_f64().unwrap()).collect();
        let mu: Vec<f64> = data["mu"].as_array().unwrap().iter().map(|v| v.as_f64().unwrap()).collect();
        let sigma = 0.3f64;
        let mut q = vec![0.0; 3 * t];
        q[0] = (sigma * sigma).ln();
        q[1] = z[0];
        for k in 1..t - 1 {
            q[1 + k] = (z[k] - z[k - 1]) / sigma;
        }
        q[t] = x[0];
        for k in 1..t {
            q[t + k] = (x[k] - x[k - 1]) / sigma;
        }
        q[2 * t] = mu[0];
        for k in 1..t {
            q[2 * t + k] = (mu[k] - mu[k - 1]) * (-0.5 * z[k - 1]).exp();
        }
        let target = StockWatson { y, s0: 10.0, calls: AtomicUsize::new(0), deadline: None, finite_penalty: false };
        let (zz, xx, mm) = target.paths(&q);
        for k in 0..t - 1 {
            assert!((zz[k] - z[k]).abs() < 1e-9);
        }
        for k in 0..t {
            assert!((xx[k] - x[k]).abs() < 1e-9);
            assert!((mm[k] - mu[k]).abs() < 1e-9);
        }
    }
}
