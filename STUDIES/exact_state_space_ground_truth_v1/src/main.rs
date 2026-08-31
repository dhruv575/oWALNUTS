//! WP4: exact state-space ground truth versus fixed metrics.
//!
//! Centered Gaussian local-level path posterior with fixed globals; the exact
//! posterior is Gaussian with tridiagonal precision `H = Q_rw + diag(1/R_t)`.
//! Four fixed metrics (identity, posterior-variance diagonal, posterior
//! precision, prior precision) are sampled with the public facade only.

use std::fs;
use std::io::Write;
use std::num::NonZeroUsize;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Instant;

use owalnuts::walnutpie::{
    DiagonalMass, InitialStepSearchConfig, KernelTuning, MultiChainOutput, RunConfig,
    StopReason, StructuredBlockMass, StructuredCovarianceBlock, Target, TargetError,
    WarmupConfig, preflight_chains, preflight_chains_structured, sample_chains,
    sample_chains_structured,
};
use rand::rngs::SmallRng;
use rand::{Rng, SeedableRng};
use rand_distr::{Distribution, Normal};

const M0: f64 = 0.0;
const TAU0: f64 = 1.0;
const MU: f64 = 0.01;
const SIGMA_X: f64 = 0.08;
const OBS_BASE: f64 = 0.0125;
const DATA_SEED: u64 = 2026_083_101;
const CHAINS: usize = 4;
const THREADS: usize = 4;
const DISCARDED: usize = 500;
const RETAINED: usize = 2_000;
const INITIAL_STEP: f64 = 0.1;
const MAX_DEPTH: usize = 8;
const MIN_MICRO: usize = 1;
const REFINEMENT_LEVELS: usize = 3;
const MAX_ERROR: f64 = 1.0;
const TARGET_ACCEPTANCE: f64 = 0.8;
const CELLS: [(usize, u64); 4] = [(100, 83_001), (1_000, 83_002), (100, 83_003), (1_000, 83_004)];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Arm {
    Identity,
    Diagonal,
    PosteriorPrecision,
    PriorPrecision,
}

impl Arm {
    const ALL: [Arm; 4] = [
        Arm::Identity,
        Arm::Diagonal,
        Arm::PosteriorPrecision,
        Arm::PriorPrecision,
    ];
    fn code(self) -> &'static str {
        match self {
            Arm::Identity => "I",
            Arm::Diagonal => "D",
            Arm::PosteriorPrecision => "P",
            Arm::PriorPrecision => "Q",
        }
    }
    fn label(self) -> &'static str {
        match self {
            Arm::Identity => "identity",
            Arm::Diagonal => "posterior-variance diagonal",
            Arm::PosteriorPrecision => "posterior precision (tridiagonal, exact)",
            Arm::PriorPrecision => "prior precision only (non-centered unit mass)",
        }
    }
}

/// Symmetric tridiagonal matrix stored as diagonal and subdiagonal.
#[derive(Clone, Debug)]
struct Tridiagonal {
    diag: Vec<f64>,
    off: Vec<f64>,
}

impl Tridiagonal {
    fn n(&self) -> usize {
        self.diag.len()
    }
    fn apply(&self, v: &[f64], out: &mut [f64]) {
        let n = self.n();
        for i in 0..n {
            let mut acc = self.diag[i] * v[i];
            if i > 0 {
                acc += self.off[i - 1] * v[i - 1];
            }
            if i + 1 < n {
                acc += self.off[i] * v[i + 1];
            }
            out[i] = acc;
        }
    }
    /// Lower-bidiagonal Cholesky factor `L` with `L L' = self`.
    fn cholesky(&self) -> Bidiagonal {
        let n = self.n();
        let mut d = vec![0.0; n];
        let mut l = vec![0.0; n.saturating_sub(1)];
        d[0] = self.diag[0].sqrt();
        for i in 1..n {
            l[i - 1] = self.off[i - 1] / d[i - 1];
            let value = self.diag[i] - l[i - 1] * l[i - 1];
            assert!(value > 0.0, "tridiagonal matrix is not positive definite");
            d[i] = value.sqrt();
        }
        Bidiagonal { diag: d, sub: l }
    }
    /// Solve `self x = b` (Thomas algorithm).
    fn solve(&self, b: &[f64]) -> Vec<f64> {
        let n = self.n();
        let mut c = vec![0.0; n];
        let mut d = vec![0.0; n];
        c[0] = if n > 1 { self.off[0] / self.diag[0] } else { 0.0 };
        d[0] = b[0] / self.diag[0];
        for i in 1..n {
            let m = self.diag[i] - self.off[i - 1] * c[i - 1];
            if i + 1 < n {
                c[i] = self.off[i] / m;
            }
            d[i] = (b[i] - self.off[i - 1] * d[i - 1]) / m;
        }
        let mut x = vec![0.0; n];
        x[n - 1] = d[n - 1];
        for i in (0..n - 1).rev() {
            x[i] = d[i] - c[i] * x[i + 1];
        }
        x
    }
    /// Diagonal of the inverse by one solve per column (O(n^2)).
    fn inverse_diagonal(&self) -> Vec<f64> {
        let n = self.n();
        let mut e = vec![0.0; n];
        (0..n)
            .map(|i| {
                e.iter_mut().for_each(|x| *x = 0.0);
                e[i] = 1.0;
                self.solve(&e)[i]
            })
            .collect()
    }
}

#[derive(Clone, Debug)]
struct Bidiagonal {
    diag: Vec<f64>,
    sub: Vec<f64>,
}

impl Bidiagonal {
    fn multiply(&self, v: &[f64]) -> Vec<f64> {
        let n = self.diag.len();
        (0..n)
            .map(|i| self.diag[i] * v[i] + if i > 0 { self.sub[i - 1] * v[i - 1] } else { 0.0 })
            .collect()
    }
    fn multiply_transpose(&self, v: &[f64]) -> Vec<f64> {
        let n = self.diag.len();
        (0..n)
            .map(|i| self.diag[i] * v[i] + if i + 1 < n { self.sub[i] * v[i + 1] } else { 0.0 })
            .collect()
    }
    fn solve_lower(&self, b: &[f64]) -> Vec<f64> {
        let n = self.diag.len();
        let mut x = vec![0.0; n];
        for i in 0..n {
            let prev = if i > 0 { self.sub[i - 1] * x[i - 1] } else { 0.0 };
            x[i] = (b[i] - prev) / self.diag[i];
        }
        x
    }
    fn solve_upper(&self, b: &[f64]) -> Vec<f64> {
        let n = self.diag.len();
        let mut x = vec![0.0; n];
        for i in (0..n).rev() {
            let next = if i + 1 < n { self.sub[i] * x[i + 1] } else { 0.0 };
            x[i] = (b[i] - next) / self.diag[i];
        }
        x
    }
}

struct Data {
    y: Vec<f64>,
    spread: Vec<f64>,
    volume: Vec<f64>,
    r: Vec<f64>,
    x_true: Vec<f64>,
}

fn simulate(t: usize) -> Data {
    let mut rng = SmallRng::seed_from_u64(DATA_SEED ^ (t as u64));
    let normal = Normal::new(0.0, 1.0).unwrap();
    let mut spread = Vec::with_capacity(t);
    let mut volume = Vec::with_capacity(t);
    for i in 0..t {
        let base = 0.02 + 0.03 * ((2.0 * std::f64::consts::PI * i as f64 / 37.0).sin()).abs();
        let spike = if rng.random::<f64>() < 0.05 { 0.15 } else { 0.0 };
        spread.push(base + spike);
        let z: f64 = normal.sample(&mut rng);
        volume.push((0.9 * z).exp());
    }
    let r: Vec<f64> = (0..t)
        .map(|i| OBS_BASE * (1.0 + spread[i] * spread[i] + 1.0 / (volume[i] + 1.0)))
        .collect();
    let mut x = Vec::with_capacity(t);
    let z0: f64 = normal.sample(&mut rng);
    x.push(M0 + TAU0 * z0);
    for i in 1..t {
        let next = x[i - 1] + MU + SIGMA_X * normal.sample(&mut rng);
        x.push(next);
    }
    let y = (0..t)
        .map(|i| x[i] + r[i].sqrt() * normal.sample(&mut rng))
        .collect();
    Data {
        y,
        spread,
        volume,
        r,
        x_true: x,
    }
}

fn prior_precision(t: usize) -> Tridiagonal {
    let s2 = 1.0 / (SIGMA_X * SIGMA_X);
    let mut diag = vec![2.0 * s2; t];
    diag[0] = 1.0 / (TAU0 * TAU0) + s2;
    diag[t - 1] = s2;
    if t == 1 {
        diag[0] = 1.0 / (TAU0 * TAU0);
    }
    Tridiagonal {
        diag,
        off: vec![-s2; t - 1],
    }
}

fn posterior_precision(data: &Data) -> Tridiagonal {
    let mut h = prior_precision(data.y.len());
    for (d, r) in h.diag.iter_mut().zip(&data.r) {
        *d += 1.0 / r;
    }
    h
}

fn posterior_linear_term(data: &Data) -> Vec<f64> {
    let t = data.y.len();
    let s2 = 1.0 / (SIGMA_X * SIGMA_X);
    let mut b: Vec<f64> = (0..t).map(|i| data.y[i] / data.r[i]).collect();
    b[0] += M0 / (TAU0 * TAU0) - MU * s2;
    b[t - 1] += MU * s2;
    b
}

struct LocalLevel {
    data: Data,
    calls: AtomicUsize,
}

impl Target for LocalLevel {
    fn dimension(&self) -> usize {
        self.data.y.len()
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        let t = q.len();
        let s2 = 1.0 / (SIGMA_X * SIGMA_X);
        let mut lp = 0.0;
        g.iter_mut().for_each(|x| *x = 0.0);
        let d0 = q[0] - M0;
        lp -= 0.5 * d0 * d0 / (TAU0 * TAU0);
        g[0] -= d0 / (TAU0 * TAU0);
        for i in 1..t {
            let inn = q[i] - q[i - 1] - MU;
            lp -= 0.5 * inn * inn * s2;
            g[i] -= inn * s2;
            g[i - 1] += inn * s2;
        }
        for i in 0..t {
            let res = self.data.y[i] - q[i];
            let ri = 1.0 / self.data.r[i];
            lp -= 0.5 * res * res * ri;
            g[i] += res * ri;
        }
        Ok(lp)
    }
}

/// Extreme eigenvalues of `W = L^-1 H L^-T` by power and inverse iteration.
fn whitened_extremes(
    h: &Tridiagonal,
    whiten: &dyn Fn(&[f64]) -> Vec<f64>,   // L^-1 v
    unwhiten_t: &dyn Fn(&[f64]) -> Vec<f64>, // L^-T v
    l_mul: &dyn Fn(&[f64]) -> Vec<f64>,     // L v
    lt_mul: &dyn Fn(&[f64]) -> Vec<f64>,    // L' v
    iterations: usize,
) -> (f64, f64) {
    let n = h.n();
    let mut rng = SmallRng::seed_from_u64(7);
    let normal = Normal::new(0.0, 1.0).unwrap();
    let mut v: Vec<f64> = (0..n).map(|_| normal.sample(&mut rng)).collect();
    let mut hv = vec![0.0; n];
    let normalize = |v: &mut Vec<f64>| {
        let norm = v.iter().map(|x| x * x).sum::<f64>().sqrt();
        v.iter_mut().for_each(|x| *x /= norm);
        norm
    };
    normalize(&mut v);
    let mut lambda_max = 0.0;
    for _ in 0..iterations {
        let inner = unwhiten_t(&v);
        h.apply(&inner, &mut hv);
        v = whiten(&hv);
        lambda_max = normalize(&mut v);
    }
    let mut v: Vec<f64> = (0..n).map(|_| normal.sample(&mut rng)).collect();
    normalize(&mut v);
    let mut lambda_min_inv = 0.0;
    for _ in 0..iterations {
        let inner = l_mul(&v);
        let solved = h.solve(&inner);
        v = lt_mul(&solved);
        lambda_min_inv = normalize(&mut v);
    }
    (lambda_max, 1.0 / lambda_min_inv)
}

struct Prediction {
    lambda_max: f64,
    lambda_min: f64,
    kappa: f64,
    leapfrogs: f64,
    depth: usize,
    cap: bool,
}

fn predict(h: &Tridiagonal, arm: Arm, posterior_var: &[f64], q: &Tridiagonal) -> Prediction {
    let n = h.n();
    let (lambda_max, lambda_min) = match arm {
        Arm::Identity => {
            let id = |v: &[f64]| v.to_vec();
            whitened_extremes(h, &id, &id, &id, &id, 3_000)
        }
        Arm::Diagonal => {
            // M = diag(1/var) => L = diag(1/sqrt(var)).
            let root: Vec<f64> = posterior_var.iter().map(|v| v.sqrt()).collect();
            let root2 = root.clone();
            let root3 = root.clone();
            let root4 = root.clone();
            let whiten = move |v: &[f64]| v.iter().zip(&root).map(|(x, r)| x * r).collect();
            let unwhiten_t = move |v: &[f64]| v.iter().zip(&root2).map(|(x, r)| x * r).collect();
            let l_mul = move |v: &[f64]| v.iter().zip(&root3).map(|(x, r)| x / r).collect();
            let lt_mul = move |v: &[f64]| v.iter().zip(&root4).map(|(x, r)| x / r).collect();
            whitened_extremes(h, &whiten, &unwhiten_t, &l_mul, &lt_mul, 3_000)
        }
        Arm::PosteriorPrecision | Arm::PriorPrecision => {
            let factor = if arm == Arm::PosteriorPrecision {
                h.cholesky()
            } else {
                q.cholesky()
            };
            let f1 = factor.clone();
            let f2 = factor.clone();
            let f3 = factor.clone();
            let f4 = factor;
            let whiten = move |v: &[f64]| f1.solve_lower(v);
            let unwhiten_t = move |v: &[f64]| f2.solve_upper(v);
            let l_mul = move |v: &[f64]| f3.multiply(v);
            let lt_mul = move |v: &[f64]| f4.multiply_transpose(v);
            whitened_extremes(h, &whiten, &unwhiten_t, &l_mul, &lt_mul, 3_000)
        }
    };
    let kappa = lambda_max / lambda_min;
    let leapfrogs = 1.75 * kappa.sqrt();
    let depth = ((leapfrogs + 1.0).log2().ceil() as usize).max(1);
    let _ = n;
    Prediction {
        lambda_max,
        lambda_min,
        kappa,
        leapfrogs,
        depth,
        cap: depth >= MAX_DEPTH,
    }
}

fn prior_starts(t: usize, seed: u64) -> Vec<Vec<f64>> {
    (0..CHAINS)
        .map(|chain| {
            let mut rng = SmallRng::seed_from_u64(seed.wrapping_mul(1_000_003).wrapping_add(chain as u64));
            let normal = Normal::new(0.0, 1.0).unwrap();
            let mut x = Vec::with_capacity(t);
            let z0: f64 = normal.sample(&mut rng);
    x.push(M0 + TAU0 * z0);
            for i in 1..t {
                let next = x[i - 1] + MU + SIGMA_X * normal.sample(&mut rng);
                x.push(next);
            }
            x
        })
        .collect()
}

fn run_config(seed: u64) -> RunConfig {
    let tuning = KernelTuning::new(
        INITIAL_STEP,
        NonZeroUsize::new(MAX_DEPTH).unwrap(),
        NonZeroUsize::new(MIN_MICRO).unwrap(),
        NonZeroUsize::new(REFINEMENT_LEVELS).unwrap(),
        MAX_ERROR,
    )
    .unwrap();
    let warmup = WarmupConfig::new(TARGET_ACCEPTANCE)
        .unwrap()
        .with_mass_adaptation(false)
        .with_step_size_adaptation(true)
        .with_initial_step_search(InitialStepSearchConfig::default());
    RunConfig::new(DISCARDED, NonZeroUsize::new(RETAINED).unwrap(), seed)
        .with_tuning(tuning)
        .with_warmup(warmup)
        .with_maximum_depth_stop_limit(usize::MAX)
}

fn fmt(x: f64) -> String {
    assert!(x.is_finite(), "non-finite value in JSON output");
    format!("{x:?}")
}

fn json_array(values: &[f64]) -> String {
    let mut s = String::from("[");
    for (i, v) in values.iter().enumerate() {
        if i > 0 {
            s.push(',');
        }
        s.push_str(&fmt(*v));
    }
    s.push(']');
    s
}

fn json_usize_array(values: &[usize]) -> String {
    let inner: Vec<String> = values.iter().map(|v| v.to_string()).collect();
    format!("[{}]", inner.join(","))
}

struct RunSummary {
    json: String,
}

fn summarize(
    arm: Arm,
    t: usize,
    seed: u64,
    prediction: &Prediction,
    preflight_worst: usize,
    preflight_ceiling: usize,
    calls_before_sampling: usize,
    calls_after: usize,
    wall: f64,
    output: &MultiChainOutput,
) -> RunSummary {
    let mut depth_hist = vec![0usize; MAX_DEPTH + 1];
    let mut max_depth_stops = 0usize;
    let mut divergences = 0usize;
    let mut invalid = 0usize;
    let mut exhausted = 0usize;
    let mut reverse_coarser_stops = 0usize;
    let mut reverse_coarser_rejections = 0usize;
    let mut refinement_hist = vec![0usize; REFINEMENT_LEVELS + 1];
    let mut retained_calls = 0usize;
    let mut total_calls = 0usize;
    let mut retained_transitions = 0usize;
    let mut warmup_divergences = 0usize;
    let mut steps = Vec::new();
    let mut mean_leaves = 0.0;
    let mut mean_energy_error = 0.0;
    let mut max_energy_error: f64 = 0.0;
    for chain in output.chains() {
        steps.push(chain.metadata().qualified_step_size());
        total_calls += chain.telemetry().total().target_calls_total();
        retained_calls += chain.telemetry().retained().target_calls_total();
        warmup_divergences += chain.telemetry().discarded().divergences();
        for d in &chain.diagnostics()[DISCARDED..] {
            retained_transitions += 1;
            depth_hist[d.depth().min(MAX_DEPTH)] += 1;
            match d.stop() {
                StopReason::MaximumDepth => max_depth_stops += 1,
                StopReason::InvalidEvaluation => invalid += 1,
                StopReason::RefinementExhausted => exhausted += 1,
                StopReason::ReverseCoarserAccepted => reverse_coarser_stops += 1,
                _ => {}
            }
            reverse_coarser_rejections += d.reverse_coarser_rejections();
            refinement_hist[d.selected_refinement_level().unwrap_or(REFINEMENT_LEVELS).min(REFINEMENT_LEVELS)] += 1;
            if d.divergent() {
                divergences += 1;
            }
            mean_leaves += d.leaves_built() as f64;
            mean_energy_error += d.maximum_absolute_energy_error();
            max_energy_error = max_energy_error.max(d.maximum_absolute_energy_error());
        }
    }
    mean_leaves /= retained_transitions as f64;
    mean_energy_error /= retained_transitions as f64;
    let mut median_depth = 0usize;
    let mut cumulative = 0usize;
    for (depth, count) in depth_hist.iter().enumerate() {
        cumulative += count;
        if cumulative * 2 >= retained_transitions {
            median_depth = depth;
            break;
        }
    }
    let json = format!(
        "{{\"arm\":\"{}\",\"arm_label\":\"{}\",\"t\":{t},\"seed\":{seed},\"chains\":{CHAINS},\"discarded\":{DISCARDED},\"retained\":{RETAINED},\
\"algorithm_revision\":\"{}\",\
\"prediction\":{{\"lambda_max\":{},\"lambda_min\":{},\"kappa\":{},\"leapfrogs\":{},\"depth\":{},\"cap\":{}}},\
\"preflight\":{{\"worst_case_target_evaluations\":{preflight_worst},\"admission_ceiling\":{preflight_ceiling},\"callbacks_before_sampling\":{calls_before_sampling}}},\
\"wall_seconds\":{},\"target_calls_counter\":{},\"target_calls_telemetry_total\":{total_calls},\"target_calls_retained\":{retained_calls},\
\"retained_transitions\":{retained_transitions},\"depth_histogram\":{},\"median_depth\":{median_depth},\"max_depth_rate\":{},\
\"retained_divergences\":{divergences},\"warmup_divergences\":{warmup_divergences},\"retained_invalid_evaluations\":{invalid},\"retained_refinement_exhaustions\":{exhausted},\"retained_reverse_coarser_stops\":{reverse_coarser_stops},\"retained_reverse_coarser_rejections\":{reverse_coarser_rejections},\"selected_refinement_level_histogram\":{},\
\"mean_leaves_built\":{},\"mean_max_abs_energy_error\":{},\"max_abs_energy_error\":{},\"final_step_sizes\":{}}}",
        arm.code(),
        arm.label(),
        output.algorithm_revision(),
        fmt(prediction.lambda_max),
        fmt(prediction.lambda_min),
        fmt(prediction.kappa),
        fmt(prediction.leapfrogs),
        prediction.depth,
        prediction.cap,
        fmt(wall),
        calls_after - calls_before_sampling,
        json_usize_array(&depth_hist),
        fmt(max_depth_stops as f64 / retained_transitions as f64),
        json_usize_array(&refinement_hist),
        fmt(mean_leaves),
        fmt(mean_energy_error),
        fmt(max_energy_error),
        json_array(&steps),
    );
    RunSummary { json }
}

fn write_draws(path: &Path, output: &MultiChainOutput) {
    let mut file = fs::File::create(path).unwrap();
    for chain in output.chains() {
        let mut bytes = Vec::with_capacity(chain.samples().len() * 8);
        for value in chain.samples() {
            bytes.extend_from_slice(&value.to_le_bytes());
        }
        file.write_all(&bytes).unwrap();
    }
}

fn main() {
    let out = PathBuf::from(std::env::args().nth(1).unwrap_or_else(|| "artifacts".into()));
    fs::create_dir_all(out.join("draws")).unwrap();
    fs::create_dir_all(out.join("runs")).unwrap();
    let mut index = Vec::new();
    for (t, seed) in CELLS {
        let data = simulate(t);
        let h = posterior_precision(&data);
        let q = prior_precision(t);
        let b = posterior_linear_term(&data);
        let exact_mean = h.solve(&b);
        let exact_var = h.inverse_diagonal();
        let truth_path = out.join(format!("truth-T{t}.json"));
        if !truth_path.exists() {
            fs::write(
                &truth_path,
                format!(
                    "{{\"t\":{t},\"data_seed\":{DATA_SEED},\"m0\":{},\"tau0\":{},\"mu\":{},\"sigma_x\":{},\"obs_base\":{},\
\"y\":{},\"spread\":{},\"volume\":{},\"r\":{},\"x_true\":{},\"exact_mean\":{},\"exact_var\":{}}}",
                    fmt(M0), fmt(TAU0), fmt(MU), fmt(SIGMA_X), fmt(OBS_BASE),
                    json_array(&data.y), json_array(&data.spread), json_array(&data.volume),
                    json_array(&data.r), json_array(&data.x_true),
                    json_array(&exact_mean), json_array(&exact_var)
                ),
            )
            .unwrap();
        }
        let target = LocalLevel {
            data,
            calls: AtomicUsize::new(0),
        };
        let starts = prior_starts(t, seed);
        let config = run_config(seed);
        for arm in Arm::ALL {
            let prediction = predict(&h, arm, &exact_var, &q);
            eprintln!(
                "T={t} seed={seed} arm={} kappa={:.4e} predicted leapfrogs={:.1} depth={} cap={}",
                arm.code(),
                prediction.kappa,
                prediction.leapfrogs,
                prediction.depth,
                prediction.cap
            );
            let calls_before = target.calls.load(Ordering::Relaxed);
            let started = Instant::now();
            let (report, output) = match arm {
                Arm::Identity | Arm::Diagonal => {
                    let mass = if arm == Arm::Identity {
                        DiagonalMass::identity(NonZeroUsize::new(t).unwrap())
                    } else {
                        DiagonalMass::from_diagonal(exact_var.iter().map(|v| 1.0 / v).collect())
                            .unwrap()
                    };
                    let report = preflight_chains(&target, &starts, &mass, &config).unwrap();
                    let after_preflight = target.calls.load(Ordering::Relaxed);
                    assert_eq!(after_preflight, calls_before, "preflight started callbacks");
                    let output = sample_chains(
                        &target,
                        &starts,
                        &mass,
                        &config,
                        NonZeroUsize::new(THREADS).unwrap(),
                    )
                    .unwrap_or_else(|e| panic!("arm {} failed: {e:?}", arm.code()));
                    (report, output)
                }
                Arm::PosteriorPrecision | Arm::PriorPrecision => {
                    let factor = if arm == Arm::PosteriorPrecision {
                        h.cholesky()
                    } else {
                        q.cholesky()
                    };
                    let mass = StructuredBlockMass::new(vec![StructuredCovarianceBlock::BidiagonalCholesky {
                        diagonal: factor.diag.clone(),
                        subdiagonal: factor.sub.clone(),
                    }])
                    .unwrap();
                    let report =
                        preflight_chains_structured(&target, &starts, &mass, &config).unwrap();
                    let after_preflight = target.calls.load(Ordering::Relaxed);
                    assert_eq!(after_preflight, calls_before, "preflight started callbacks");
                    let output = sample_chains_structured(
                        &target,
                        &starts,
                        &mass,
                        &config,
                        NonZeroUsize::new(THREADS).unwrap(),
                    )
                    .unwrap_or_else(|e| panic!("arm {} failed: {e:?}", arm.code()));
                    (report, output)
                }
            };
            let wall = started.elapsed().as_secs_f64();
            let calls_after = target.calls.load(Ordering::Relaxed);
            let summary = summarize(
                arm,
                t,
                seed,
                &prediction,
                report.worst_case_target_evaluations(),
                report.admission_ceiling(),
                calls_before,
                calls_after,
                wall,
                &output,
            );
            let stem = format!("T{t}-{}-{seed}", arm.code());
            fs::write(out.join("runs").join(format!("{stem}.json")), &summary.json).unwrap();
            write_draws(&out.join("draws").join(format!("{stem}.f64")), &output);
            eprintln!("  done in {wall:.2}s, {} target calls", calls_after - calls_before);
            index.push(format!("\"{stem}\""));
        }
    }
    fs::write(
        out.join("index.json"),
        format!(
            "{{\"schema\":\"exact-state-space-ground-truth-v1/runs\",\"chains\":{CHAINS},\"discarded\":{DISCARDED},\"retained\":{RETAINED},\"max_depth\":{MAX_DEPTH},\"runs\":[{}]}}",
            index.join(",")
        ),
    )
    .unwrap();
}

#[cfg(test)]
mod tests {
    use super::*;

    fn dense(tri: &Tridiagonal) -> Vec<Vec<f64>> {
        let n = tri.n();
        let mut m = vec![vec![0.0; n]; n];
        for i in 0..n {
            m[i][i] = tri.diag[i];
            if i + 1 < n {
                m[i][i + 1] = tri.off[i];
                m[i + 1][i] = tri.off[i];
            }
        }
        m
    }

    fn dense_inverse(mut a: Vec<Vec<f64>>) -> Vec<Vec<f64>> {
        let n = a.len();
        let mut inv = vec![vec![0.0; n]; n];
        for i in 0..n {
            inv[i][i] = 1.0;
        }
        for i in 0..n {
            let p = (i..n).max_by(|&x, &y| a[x][i].abs().total_cmp(&a[y][i].abs())).unwrap();
            a.swap(i, p);
            inv.swap(i, p);
            let s = a[i][i];
            for j in 0..n {
                a[i][j] /= s;
                inv[i][j] /= s;
            }
            for k in 0..n {
                if k != i {
                    let f = a[k][i];
                    for j in 0..n {
                        a[k][j] -= f * a[i][j];
                        inv[k][j] -= f * inv[i][j];
                    }
                }
            }
        }
        inv
    }

    #[test]
    fn cholesky_reconstructs_tridiagonal() {
        let data = simulate(100);
        let h = posterior_precision(&data);
        let l = h.cholesky();
        let n = h.n();
        for i in 0..n {
            let mut e = vec![0.0; n];
            e[i] = 1.0;
            let lt_e = l.multiply_transpose(&e);
            let column = l.multiply(&lt_e);
            let mut expected = vec![0.0; n];
            h.apply(&e, &mut expected);
            for j in 0..n {
                assert!((column[j] - expected[j]).abs() < 1e-9 * (1.0 + expected[j].abs()));
            }
        }
    }

    #[test]
    fn solve_and_inverse_diagonal_match_dense() {
        let data = simulate(100);
        let h = posterior_precision(&data);
        let inv = dense_inverse(dense(&h));
        let diag = h.inverse_diagonal();
        for i in 0..100 {
            assert!((diag[i] - inv[i][i]).abs() < 1e-9 * inv[i][i]);
        }
        let b = posterior_linear_term(&data);
        let x = h.solve(&b);
        for i in 0..100 {
            let dense_x: f64 = (0..100).map(|j| inv[i][j] * b[j]).sum();
            assert!((x[i] - dense_x).abs() < 1e-8 * (1.0 + dense_x.abs()));
        }
    }

    #[test]
    fn gradient_matches_finite_differences_and_mode_is_exact_mean() {
        let data = simulate(50);
        let h = posterior_precision(&data);
        let b = posterior_linear_term(&data);
        let mean = h.solve(&b);
        let target = LocalLevel {
            data,
            calls: AtomicUsize::new(0),
        };
        let mut g = vec![0.0; 50];
        let lp = target.log_density_gradient(&mean, &mut g).unwrap();
        assert!(g.iter().all(|x| x.abs() < 1e-7), "gradient at exact mean must vanish");
        let mut q = mean.clone();
        for i in [0usize, 7, 49] {
            let eps = 1e-6;
            q[i] += eps;
            let mut g2 = vec![0.0; 50];
            let lp2 = target.log_density_gradient(&q, &mut g2).unwrap();
            let fd = (lp2 - lp) / eps;
            let _ = g2;
            assert!((fd - g[i]).abs() < 1e-3, "fd {fd} vs {}", g[i]);
            q[i] -= eps;
        }
        let mut g3 = vec![0.0; 50];
        let mut e = mean.clone();
        e[3] += 1.0;
        target.log_density_gradient(&e, &mut g3).unwrap();
        let mut he = vec![0.0; 50];
        let mut unit = vec![0.0; 50];
        unit[3] = 1.0;
        h.apply(&unit, &mut he);
        for i in 0..50 {
            assert!((g3[i] + he[i]).abs() < 1e-8, "gradient is -H (q - mean)");
        }
    }

    #[test]
    fn whitened_posterior_precision_is_identity() {
        let data = simulate(100);
        let h = posterior_precision(&data);
        let q = prior_precision(100);
        let var = h.inverse_diagonal();
        let p = predict(&h, Arm::PosteriorPrecision, &var, &q);
        assert!((p.lambda_max - 1.0).abs() < 1e-6 && (p.lambda_min - 1.0).abs() < 1e-6);
    }
}
