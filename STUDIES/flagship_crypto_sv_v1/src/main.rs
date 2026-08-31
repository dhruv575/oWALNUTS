//! Flagship crypto SV study: native oWALNUTS cell.
//!
//! Standard stochastic volatility model on daily log returns:
//!   r_t = exp(h_t/2) eps_t,      eps_t ~ N(0,1)
//!   h_t = mu + phi (h_{t-1} - mu) + sigma eta_t, stationary init
//! Unconstrained coordinates q = [mu, a, s, h_1..h_T] with
//!   phi = 2 sigmoid(a) - 1  (prior (phi+1)/2 ~ Beta(20, 1.5) + Jacobian)
//!   sigma = exp(s)          (prior HalfNormal(0.5) + Jacobian)
//!   mu ~ N(-10, 5^2)
//!
//! Modes:
//!   flagship-crypto-sv-v1 run   <data.json> <out_dir> <seed> [pilot]
//!   flagship-crypto-sv-v1 parity <data.json> <points.json> <out.json>
//!
//! The metric is the WP4/WP16-style one-shot posterior-precision block:
//! globals diagonal precision [25, 4, 25]; latent path tridiagonal
//! AR(1) prior precision at calibrated (phi_hat=0.95, sigma_hat=0.2) plus the
//! observation curvature 0.5 r_t^2 exp(-h_hat_t) at the EWMA(0.94) volatility
//! proxy h_hat. Momentum covariance M = precision, supplied as its
//! bidiagonal Cholesky factor.

use std::fs;
use std::io::Write as _;
use std::num::NonZeroUsize;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Instant;

use owalnuts::walnutpie::{
    InitialStepSearchConfig, KernelTuning, MultiChainOutput, PaperAdaptationConfig,
    ResearchTargetEvaluationLimit, RunConfig, StopReason, StructuredBlockMass,
    StructuredCovarianceBlock, Target, TargetError, WarmupConfig,
    preflight_chains_structured, sample_chains_structured,
};
use rand::SeedableRng;
use rand::rngs::SmallRng;
use rand_distr::{Distribution, Normal};

const CHAINS: usize = 4;
const DISCARDED: usize = 1000;
const RETAINED: usize = 3000;
const MAX_DEPTH: usize = 9;
const MIN_MICRO: usize = 1;
const REFINEMENT_LEVELS: usize = 6;
const INITIAL_STEP: f64 = 0.1;
const INITIAL_MAX_ERROR: f64 = 1.0;
const TARGET_ACCEPTANCE: f64 = 0.8;
const THREADS: usize = 4;
const RESEARCH_EVALUATION_LIMIT: usize = 1_000_000_000;

// Calibrated one-shot metric constants (documented in PREREGISTRATION.md).
const PHI_HAT: f64 = 0.95;
const SIGMA_HAT: f64 = 0.2;
const EWMA_LAMBDA: f64 = 0.94;
const GLOBAL_PRECISION: [f64; 3] = [25.0, 4.0, 25.0];

// Priors.
const MU_PRIOR_MEAN: f64 = -10.0;
const MU_PRIOR_VAR: f64 = 25.0;
const BETA_A: f64 = 20.0;
const BETA_B: f64 = 1.5;
const SIGMA_HALF_NORMAL_SCALE: f64 = 0.5;

fn sigmoid(x: f64) -> f64 {
    if x >= 0.0 {
        1.0 / (1.0 + (-x).exp())
    } else {
        let e = x.exp();
        e / (1.0 + e)
    }
}

struct SvData {
    r: Vec<f64>,
}

impl SvData {
    fn load(path: &Path) -> (Self, String, String, usize) {
        let doc: serde_json::Value =
            serde_json::from_str(&fs::read_to_string(path).unwrap()).unwrap();
        let closes = doc["closes"].as_array().unwrap();
        let mut prices = Vec::with_capacity(closes.len());
        for row in closes {
            let c = row[1].as_f64().unwrap();
            assert!(c.is_finite() && c > 0.0, "bad close");
            prices.push(c);
        }
        let r: Vec<f64> = prices.windows(2).map(|w| (w[1] / w[0]).ln()).collect();
        assert!(r.iter().all(|x| x.is_finite()));
        let symbol = doc["symbol"].as_str().unwrap().to_string();
        let last = doc["last"].as_str().unwrap().to_string();
        let n = r.len();
        (Self { r }, symbol, last, n)
    }

    fn t(&self) -> usize {
        self.r.len()
    }

    /// EWMA volatility proxy on the h scale.
    fn h_hat(&self) -> Vec<f64> {
        let tiny = 1e-10;
        let mut v = self.r.iter().map(|r| r * r).sum::<f64>() / self.r.len() as f64;
        let mut out = Vec::with_capacity(self.r.len());
        for r in &self.r {
            v = EWMA_LAMBDA * v + (1.0 - EWMA_LAMBDA) * r * r;
            out.push((v + tiny).ln());
        }
        out
    }
}

/// Joint log density and gradient. Returns every constant explicitly so the
/// JAX/numpy parity transcriptions can match bit-for-bit up to roundoff.
fn logp_grad(data: &SvData, q: &[f64], grad: &mut [f64]) -> f64 {
    let t = data.t();
    assert_eq!(q.len(), t + 3);
    let (mu, a, s) = (q[0], q[1], q[2]);
    let h = &q[3..];
    let p = sigmoid(a);
    let phi = 2.0 * p - 1.0;
    let sigma = s.exp();
    let sigma2 = sigma * sigma;
    let one_m_phi2 = 1.0 - phi * phi;
    let ln2pi = (2.0 * std::f64::consts::PI).ln();

    let mut lp = 0.0;
    for g in grad.iter_mut() {
        *g = 0.0;
    }

    // mu ~ N(-10, 25)
    lp += -0.5 * (mu - MU_PRIOR_MEAN) * (mu - MU_PRIOR_MEAN) / MU_PRIOR_VAR
        - 0.5 * (MU_PRIOR_VAR).ln()
        - 0.5 * ln2pi;
    grad[0] += -(mu - MU_PRIOR_MEAN) / MU_PRIOR_VAR;

    // (phi+1)/2 = p ~ Beta(20, 1.5), with logistic Jacobian dp/da = p(1-p):
    // lp = (A-1) ln p + (B-1) ln(1-p) + ln p + ln(1-p) - ln B(A,B)
    let ln_beta_norm = lgamma(BETA_A) + lgamma(BETA_B) - lgamma(BETA_A + BETA_B);
    lp += BETA_A * p.ln() + BETA_B * (1.0 - p).ln() - ln_beta_norm;
    grad[1] += BETA_A - (BETA_A + BETA_B) * p;

    // sigma = exp(s) ~ HalfNormal(0.5): lp = ln(2) - 0.5 ln(2 pi c^2) - sigma^2/(2 c^2) + s
    let c2 = SIGMA_HALF_NORMAL_SCALE * SIGMA_HALF_NORMAL_SCALE;
    lp += (2.0f64).ln() - 0.5 * (2.0 * std::f64::consts::PI * c2).ln() - sigma2 / (2.0 * c2) + s;
    grad[2] += -sigma2 / c2 + 1.0;

    // h_1 ~ N(mu, sigma^2/(1-phi^2))
    let d1 = h[0] - mu;
    lp += -0.5 * (sigma2 / one_m_phi2).ln() - 0.5 * ln2pi - d1 * d1 * one_m_phi2 / (2.0 * sigma2);
    grad[3] += -d1 * one_m_phi2 / sigma2;
    grad[0] += d1 * one_m_phi2 / sigma2;
    // d/dphi of [0.5 ln(1-phi^2) - d1^2 (1-phi^2)/(2 sigma^2)]
    let mut dlp_dphi = -phi / one_m_phi2 + d1 * d1 * phi / sigma2;
    // d/ds of [-0.5 ln(sigma^2 / (1-phi^2)) - d1^2 (1-phi^2)/(2 sigma^2)]
    let mut dlp_ds_latent = -1.0 + d1 * d1 * one_m_phi2 / sigma2;

    // h_t | h_{t-1}
    for i in 1..t {
        let e = h[i] - mu - phi * (h[i - 1] - mu);
        lp += -0.5 * sigma2.ln() - 0.5 * ln2pi - e * e / (2.0 * sigma2);
        grad[3 + i] += -e / sigma2;
        grad[3 + i - 1] += phi * e / sigma2;
        grad[0] += e * (1.0 - phi) / sigma2;
        dlp_dphi += e * (h[i - 1] - mu) / sigma2;
        dlp_ds_latent += -1.0 + e * e / sigma2;
    }
    // Observations: r_t ~ N(0, exp(h_t))
    for i in 0..t {
        let w = data.r[i] * data.r[i] * (-h[i]).exp();
        lp += -0.5 * h[i] - 0.5 * w - 0.5 * ln2pi;
        grad[3 + i] += -0.5 + 0.5 * w;
    }

    grad[1] += dlp_dphi * 2.0 * p * (1.0 - p); // dphi/da = 2 p (1-p)
    grad[2] += dlp_ds_latent; // d sigma^2 terms already via d/ds
    lp
}

/// Lanczos lgamma (matches libm to ~1e-13; constants from Numerical Recipes).
fn lgamma(x: f64) -> f64 {
    const COF: [f64; 6] = [
        76.180_091_729_471_46,
        -86.505_320_329_416_77,
        24.014_098_240_830_91,
        -1.231_739_572_450_155,
        0.120_865_097_386_617_5e-2,
        -0.539_523_938_495_3e-5,
    ];
    let mut y = x;
    let tmp = x + 5.5;
    let tmp = tmp - (x + 0.5) * tmp.ln();
    let mut ser = 1.000_000_000_190_015;
    for c in COF {
        y += 1.0;
        ser += c / y;
    }
    -tmp + (2.506_628_274_631_000_5 * ser / x).ln()
}

struct SvTarget {
    data: SvData,
    calls: AtomicUsize,
}

impl Target for SvTarget {
    fn dimension(&self) -> usize {
        self.data.t() + 3
    }

    fn log_density_gradient(&self, position: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        // Deterministic zero-density region: where the transformed density is
        // not representable in f64 (phi saturating at +-1, sigma over/underflow,
        // exp(-h) overflow), the log density/gradient degenerate to NaN/inf.
        // Per the facade contract this is a recoverable failure and the kernel
        // refines through it (kernel v10 semantics).
        let lp = logp_grad(&self.data, position, gradient);
        if !lp.is_finite() || gradient.iter().any(|g| !g.is_finite()) {
            return Err(TargetError::recoverable(
                "sv target outside the representable region",
            ));
        }
        Ok(lp)
    }
}

/// Symmetric tridiagonal matrix and its bidiagonal Cholesky factor.
struct Tridiagonal {
    diag: Vec<f64>,
    off: Vec<f64>,
}

impl Tridiagonal {
    fn spd(&self) -> bool {
        let n = self.diag.len();
        let mut prev = self.diag[0];
        if prev <= 0.0 {
            return false;
        }
        for i in 1..n {
            let v = self.diag[i] - self.off[i - 1] * self.off[i - 1] / prev;
            if v <= 0.0 {
                return false;
            }
            prev = v;
        }
        true
    }

    fn cholesky(&self) -> (Vec<f64>, Vec<f64>) {
        let n = self.diag.len();
        let mut l = vec![0.0; n];
        let mut sub = vec![0.0; n.saturating_sub(1)];
        l[0] = self.diag[0].sqrt();
        for i in 1..n {
            sub[i - 1] = self.off[i - 1] / l[i - 1];
            let v = self.diag[i] - sub[i - 1] * sub[i - 1];
            assert!(v > 0.0, "path precision not SPD at {i}");
            l[i] = v.sqrt();
        }
        (l, sub)
    }
}

/// Stage-A calibration output consumed by the main run and the Python cells.
struct Calibration {
    mu_hat: f64,
    a_hat: f64,
    s_hat: f64,
    phi_hat: f64,
    sigma_hat: f64,
    global_cov: [f64; 9],
    h_mean: Vec<f64>,
}

/// Covariance-safety inflation applied to the calibration global covariance
/// before inversion (the calibration run under-disperses when mixing is slow).
const GLOBAL_COV_INFLATION: f64 = 2.0;

impl Calibration {
    fn load(path: &Path) -> Self {
        let doc: serde_json::Value =
            serde_json::from_str(&fs::read_to_string(path).unwrap()).unwrap();
        let arr = |k: &str| -> Vec<f64> {
            doc[k].as_array().unwrap().iter().map(|v| v.as_f64().unwrap()).collect()
        };
        let gc = arr("global_cov");
        Self {
            mu_hat: doc["mu_hat"].as_f64().unwrap(),
            a_hat: doc["a_hat"].as_f64().unwrap(),
            s_hat: doc["s_hat"].as_f64().unwrap(),
            phi_hat: doc["phi_hat"].as_f64().unwrap(),
            sigma_hat: doc["sigma_hat"].as_f64().unwrap(),
            global_cov: gc.try_into().unwrap(),
            h_mean: arr("h_mean"),
        }
    }

    /// Tridiagonalized global precision: invert the inflated 3x3 covariance,
    /// drop the (mu, s) corner, and keep the [mu,a] and [a,s] couplings.
    fn global_precision_tridiagonal(&self) -> Tridiagonal {
        let c: Vec<f64> = self.global_cov.iter().map(|v| v * GLOBAL_COV_INFLATION).collect();
        let det = c[0] * (c[4] * c[8] - c[5] * c[7]) - c[1] * (c[3] * c[8] - c[5] * c[6])
            + c[2] * (c[3] * c[7] - c[4] * c[6]);
        assert!(det > 0.0, "calibration global covariance not SPD");
        let p00 = (c[4] * c[8] - c[5] * c[7]) / det;
        let p01 = -(c[1] * c[8] - c[2] * c[7]) / det;
        let p11 = (c[0] * c[8] - c[2] * c[6]) / det;
        let p12 = -(c[0] * c[5] - c[2] * c[3]) / det;
        let p22 = (c[0] * c[4] - c[1] * c[3]) / det;
        let tri = Tridiagonal { diag: vec![p00, p11, p22], off: vec![p01, p12] };
        if tri.spd() {
            tri
        } else {
            // Fall back to the diagonal precision.
            Tridiagonal {
                diag: vec![1.0 / c[0], 1.0 / c[4], 1.0 / c[8]],
                off: vec![0.0, 0.0],
            }
        }
    }
}

fn path_precision(data: &SvData, cal: &Calibration) -> Tridiagonal {
    let t = data.t();
    let s2 = cal.sigma_hat * cal.sigma_hat;
    let phi = cal.phi_hat;
    let mut diag = vec![0.0; t];
    let mut off = vec![0.0; t - 1];
    for i in 0..t {
        let prior = if i == 0 || i == t - 1 {
            if t == 1 { (1.0 - phi * phi) / s2 } else { 1.0 / s2 }
        } else {
            (1.0 + phi * phi) / s2
        };
        let obs = 0.5 * data.r[i] * data.r[i] * (-cal.h_mean[i]).exp();
        diag[i] = prior + obs;
    }
    for o in off.iter_mut() {
        *o = -phi / s2;
    }
    Tridiagonal { diag, off }
}

fn build_mass(data: &SvData, cal: &Calibration) -> StructuredBlockMass {
    let (gl, gsub) = cal.global_precision_tridiagonal().cholesky();
    let (l, sub) = path_precision(data, cal).cholesky();
    StructuredBlockMass::new(vec![
        StructuredCovarianceBlock::BidiagonalCholesky { diagonal: gl, subdiagonal: gsub },
        StructuredCovarianceBlock::BidiagonalCholesky { diagonal: l, subdiagonal: sub },
    ])
    .unwrap()
}

fn starts(data: &SvData, cal: &Calibration, seed: u64) -> Vec<Vec<f64>> {
    let h_hat = &cal.h_mean;
    let mu0 = cal.mu_hat;
    let a0 = cal.a_hat;
    let s0 = cal.s_hat;
    (0..CHAINS)
        .map(|chain| {
            let mut rng = SmallRng::seed_from_u64(
                seed.wrapping_mul(6_364_136_223_846_793_005).wrapping_add(chain as u64),
            );
            let n = Normal::new(0.0, 1.0).unwrap();
            let mut q = Vec::with_capacity(data.t() + 3);
            q.push(mu0 + 0.5 * n.sample(&mut rng));
            q.push(a0 + 0.5 * n.sample(&mut rng));
            q.push(s0 + 0.3 * n.sample(&mut rng));
            for h in h_hat {
                q.push(h + 0.5 * n.sample(&mut rng));
            }
            q
        })
        .collect()
}

fn run_config(seed: u64, pilot: bool) -> RunConfig {
    let tuning = KernelTuning::new(
        INITIAL_STEP,
        NonZeroUsize::new(MAX_DEPTH).unwrap(),
        NonZeroUsize::new(MIN_MICRO).unwrap(),
        NonZeroUsize::new(REFINEMENT_LEVELS).unwrap(),
        INITIAL_MAX_ERROR,
    )
    .unwrap();
    let paper = PaperAdaptationConfig::new(2.0, 0.95, 0.8).unwrap();
    let warmup = WarmupConfig::new(TARGET_ACCEPTANCE)
        .unwrap()
        .with_mass_adaptation(false)
        .with_step_size_adaptation(true)
        .with_initial_step_search(InitialStepSearchConfig::default())
        .with_paper_adaptation(paper);
    let retained = if pilot { 500 } else { RETAINED };
    let discarded = if pilot { 300 } else { DISCARDED };
    RunConfig::new(discarded, NonZeroUsize::new(retained).unwrap(), seed)
        .with_tuning(tuning)
        .with_warmup(warmup)
        .with_research_target_evaluation_limit(
            ResearchTargetEvaluationLimit::new(NonZeroUsize::new(RESEARCH_EVALUATION_LIMIT).unwrap())
                .unwrap(),
        )
        .with_maximum_depth_stop_limit(usize::MAX)
}

fn fmt(x: f64) -> String {
    assert!(x.is_finite(), "non-finite value in JSON output");
    format!("{x:?}")
}

fn json_array(values: &[f64]) -> String {
    let inner: Vec<String> = values.iter().map(|v| fmt(*v)).collect();
    format!("[{}]", inner.join(","))
}

fn json_usize_array(values: &[usize]) -> String {
    let inner: Vec<String> = values.iter().map(|v| v.to_string()).collect();
    format!("[{}]", inner.join(","))
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

fn summarize(
    symbol: &str,
    t: usize,
    seed: u64,
    pilot: bool,
    preflight_worst: usize,
    preflight_ceiling: usize,
    calls: usize,
    wall: f64,
    output: &MultiChainOutput,
) -> String {
    let mut depth_hist = vec![0usize; MAX_DEPTH + 1];
    let mut max_depth_stops = 0usize;
    let mut divergences = 0usize;
    let mut invalid = 0usize;
    let mut exhaustions = 0usize;
    let mut retained_transitions = 0usize;
    let mut retained_calls = 0usize;
    let mut steps = Vec::new();
    let mut max_errors = Vec::new();
    for chain in output.chains() {
        let discarded = chain.diagnostics().len() - chain.retained();
        for d in chain.diagnostics().iter().skip(discarded) {
            retained_transitions += 1;
            retained_calls += d.target_evaluations();
            let depth = d.depth().min(MAX_DEPTH);
            depth_hist[depth] += 1;
            if d.divergent() {
                divergences += 1;
            }
            match d.stop() {
                StopReason::MaximumDepth => max_depth_stops += 1,
                StopReason::InvalidEvaluation => invalid += 1,
                StopReason::RefinementExhausted => exhaustions += 1,
                _ => {}
            }
        }
        steps.push(chain.metadata().tuning().step_size());
        max_errors.push(chain.metadata().tuning().max_error());
    }
    format!(
        "{{\"schema\":\"flagship-crypto-sv-v1/run\",\"symbol\":\"{symbol}\",\"cell\":\"native\",\"t\":{t},\"dim\":{},\
\"seed\":{seed},\"pilot\":{pilot},\"chains\":{CHAINS},\"discarded\":{},\"retained_per_chain\":{},\
\"algorithm_revision\":\"{}\",\"preflight_worst_case\":{preflight_worst},\"preflight_ceiling\":{preflight_ceiling},\
\"target_calls_total\":{calls},\"retained_target_calls\":{retained_calls},\"wall_seconds\":{},\
\"depth_hist\":{},\"max_depth_stops\":{max_depth_stops},\"max_depth_rate\":{},\
\"divergences\":{divergences},\"invalid\":{invalid},\"exhaustions\":{exhaustions},\
\"final_step_sizes\":{},\"final_max_errors\":{}}}",
        t + 3,
        if pilot { 300 } else { DISCARDED },
        if pilot { 500 } else { RETAINED },
        owalnuts::walnutpie::ALGORITHM_REVISION,
        fmt(wall),
        json_usize_array(&depth_hist),
        fmt(max_depth_stops as f64 / retained_transitions.max(1) as f64),
        json_array(&steps),
        json_array(&max_errors),
    )
}

fn cmd_parity(data_path: &Path, points_path: &Path, out_path: &Path) {
    let (data, _, _, _) = SvData::load(data_path);
    let doc: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(points_path).unwrap()).unwrap();
    let mut rows = Vec::new();
    for point in doc["points"].as_array().unwrap() {
        let q: Vec<f64> = point.as_array().unwrap().iter().map(|v| v.as_f64().unwrap()).collect();
        let mut grad = vec![0.0; q.len()];
        let lp = logp_grad(&data, &q, &mut grad);
        rows.push(format!("{{\"logp\":{},\"grad\":{}}}", fmt(lp), json_array(&grad)));
    }
    fs::write(out_path, format!("{{\"rows\":[{}]}}", rows.join(","))).unwrap();
}

/// Stage A: short diagonal-adapted run that produces the calibration file.
fn cmd_calibrate(data_path: &Path, out: &Path, seed: u64) {
    let (data, symbol, _, _) = SvData::load(data_path);
    let t = data.t();
    let sym = symbol.split('-').next().unwrap().to_string();
    fs::create_dir_all(out.join("calibration")).unwrap();
    // Data-informed EWMA starts for the calibration stage itself.
    let ewma = Calibration {
        mu_hat: data.h_hat().iter().sum::<f64>() / t as f64,
        a_hat: ((1.0 + PHI_HAT) / (1.0 - PHI_HAT)).ln(),
        s_hat: SIGMA_HAT.ln(),
        phi_hat: PHI_HAT,
        sigma_hat: SIGMA_HAT,
        global_cov: [
            1.0 / GLOBAL_PRECISION[0], 0.0, 0.0,
            0.0, 1.0 / GLOBAL_PRECISION[1], 0.0,
            0.0, 0.0, 1.0 / GLOBAL_PRECISION[2],
        ],
        h_mean: data.h_hat(),
    };
    let target = SvTarget { data, calls: AtomicUsize::new(0) };
    let starts = starts(&target.data, &ewma, seed ^ 0xC0FFEE);
    let tuning = KernelTuning::new(
        INITIAL_STEP,
        NonZeroUsize::new(MAX_DEPTH).unwrap(),
        NonZeroUsize::new(MIN_MICRO).unwrap(),
        NonZeroUsize::new(REFINEMENT_LEVELS).unwrap(),
        INITIAL_MAX_ERROR,
    )
    .unwrap();
    let warmup = WarmupConfig::new(TARGET_ACCEPTANCE)
        .unwrap()
        .with_initial_step_search(InitialStepSearchConfig::default());
    let config = RunConfig::new(800, NonZeroUsize::new(400).unwrap(), seed ^ 0xC0FFEE)
        .with_tuning(tuning)
        .with_warmup(warmup)
        .with_research_target_evaluation_limit(
            ResearchTargetEvaluationLimit::new(NonZeroUsize::new(RESEARCH_EVALUATION_LIMIT).unwrap())
                .unwrap(),
        )
        .with_maximum_depth_stop_limit(usize::MAX);
    let mass = owalnuts::walnutpie::DiagonalMass::identity(NonZeroUsize::new(t + 3).unwrap());
    let started = Instant::now();
    let output = owalnuts::walnutpie::sample_chains(
        &target,
        &starts,
        &mass,
        &config,
        NonZeroUsize::new(THREADS).unwrap(),
    )
    .unwrap_or_else(|e| panic!("{sym} calibration failed: {e:?}"));
    let wall = started.elapsed().as_secs_f64();
    // Pooled posterior means per coordinate and 3x3 global covariance.
    let dim = t + 3;
    let mut mean = vec![0.0; dim];
    let mut count = 0.0;
    for chain in output.chains() {
        for draw in chain.samples().chunks(dim) {
            count += 1.0;
            for (i, v) in draw.iter().enumerate() {
                mean[i] += (v - mean[i]) / count;
            }
        }
    }
    let mut cov = [0.0f64; 9];
    for chain in output.chains() {
        for draw in chain.samples().chunks(dim) {
            for i in 0..3 {
                for j in 0..3 {
                    cov[3 * i + j] += (draw[i] - mean[i]) * (draw[j] - mean[j]);
                }
            }
        }
    }
    for v in cov.iter_mut() {
        *v /= count - 1.0;
    }
    write_draws(
        &out.join("draws").join(format!("{sym}-caldiag-{seed}.f64")),
        &output,
    );
    let phi_hat = 2.0 * sigmoid(mean[1]) - 1.0;
    let sigma_hat = mean[2].exp();
    fs::write(
        out.join("calibration").join(format!("{sym}-{seed}.json")),
        format!(
            "{{\"schema\":\"flagship-crypto-sv-v1/calibration\",\"symbol\":\"{sym}\",\"seed\":{seed},\
\"discarded\":800,\"retained\":400,\"wall_seconds\":{},\"target_calls\":{},\
\"mu_hat\":{},\"a_hat\":{},\"s_hat\":{},\"phi_hat\":{},\"sigma_hat\":{},\
\"global_cov\":{},\"h_mean\":{}}}",
            fmt(wall),
            target.calls.load(Ordering::Relaxed),
            fmt(mean[0]),
            fmt(mean[1]),
            fmt(mean[2]),
            fmt(phi_hat),
            fmt(sigma_hat),
            json_array(&cov),
            json_array(&mean[3..]),
        ),
    )
    .unwrap();
    eprintln!("{sym} calibration: {wall:.1}s, phi_hat={phi_hat:.3} sigma_hat={sigma_hat:.3}");
}

fn cmd_run(data_path: &Path, out: &Path, seed: u64, cal_path: &Path, pilot: bool) {
    let (data, symbol, last, _) = SvData::load(data_path);
    let t = data.t();
    let sym = symbol.split('-').next().unwrap().to_string();
    fs::create_dir_all(out.join("draws")).unwrap();
    fs::create_dir_all(out.join("runs")).unwrap();
    let cal = Calibration::load(cal_path);
    assert_eq!(cal.h_mean.len(), t, "calibration/data length mismatch");
    let mass = build_mass(&data, &cal);
    let target = SvTarget { data, calls: AtomicUsize::new(0) };
    let starts = starts(&target.data, &cal, seed);
    let config = run_config(seed, pilot);
    let report = preflight_chains_structured(&target, &starts, &mass, &config).unwrap();
    assert_eq!(target.calls.load(Ordering::Relaxed), 0, "preflight started callbacks");
    let started = Instant::now();
    let output = sample_chains_structured(
        &target,
        &starts,
        &mass,
        &config,
        NonZeroUsize::new(THREADS).unwrap(),
    )
    .unwrap_or_else(|e| panic!("{sym} seed {seed} failed: {e:?}"));
    let wall = started.elapsed().as_secs_f64();
    let calls = target.calls.load(Ordering::Relaxed);
    let stem = format!("{sym}-native-{seed}{}", if pilot { "-pilot" } else { "" });
    let summary = summarize(
        &sym,
        t,
        seed,
        pilot,
        report.worst_case_target_evaluations(),
        report.admission_ceiling(),
        calls,
        wall,
        &output,
    );
    fs::write(out.join("runs").join(format!("{stem}.json")), summary).unwrap();
    write_draws(&out.join("draws").join(format!("{stem}.f64")), &output);
    eprintln!("{sym} T={t} last={last} seed={seed} pilot={pilot}: {wall:.1}s, {calls} calls");
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("calibrate") => cmd_calibrate(
            Path::new(&args[2]),
            &PathBuf::from(&args[3]),
            args[4].parse().unwrap(),
        ),
        Some("run") => {
            let pilot = args.get(6).map(String::as_str) == Some("pilot");
            cmd_run(
                Path::new(&args[2]),
                &PathBuf::from(&args[3]),
                args[4].parse().unwrap(),
                Path::new(&args[5]),
                pilot,
            );
        }
        Some("parity") => cmd_parity(Path::new(&args[2]), Path::new(&args[3]), Path::new(&args[4])),
        _ => {
            eprintln!(
                "usage: calibrate <data.json> <out_dir> <seed> | run <data.json> <out_dir> <seed> <calibration.json> [pilot] | parity <data.json> <points.json> <out.json>"
            );
            std::process::exit(2);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_data() -> SvData {
        // Deterministic synthetic returns.
        let mut rng = SmallRng::seed_from_u64(97_000_001);
        let n = Normal::new(0.0, 1.0).unwrap();
        let (mu, phi, sigma): (f64, f64, f64) = (-9.0, 0.95, 0.25);
        let mut h: f64 = mu;
        let mut r = Vec::with_capacity(40);
        for _ in 0..40 {
            h = mu + phi * (h - mu) + sigma * n.sample(&mut rng);
            r.push((h / 2.0).exp() * n.sample(&mut rng));
        }
        SvData { r }
    }

    #[test]
    fn gradient_matches_finite_differences() {
        let data = test_data();
        let t = data.t();
        let mut rng = SmallRng::seed_from_u64(12345);
        let n = Normal::new(0.0, 1.0).unwrap();
        for _ in 0..20 {
            let mut q: Vec<f64> = (0..t + 3).map(|_| 0.4 * n.sample(&mut rng)).collect();
            q[0] += -9.0;
            q[1] += 2.0;
            q[2] += -1.5;
            for v in q.iter_mut().skip(3) {
                *v += -9.0;
            }
            let mut grad = vec![0.0; t + 3];
            let lp = logp_grad(&data, &q, &mut grad);
            assert!(lp.is_finite());
            let eps = 1e-6;
            for i in 0..t + 3 {
                let mut qp = q.clone();
                let mut qm = q.clone();
                qp[i] += eps;
                qm[i] -= eps;
                let mut scratch = vec![0.0; t + 3];
                let fd = (logp_grad(&data, &qp, &mut scratch) - logp_grad(&data, &qm, &mut scratch))
                    / (2.0 * eps);
                let scale = 1.0 + grad[i].abs().max(fd.abs());
                assert!(
                    (grad[i] - fd).abs() / scale < 5e-5,
                    "coord {i}: analytic {} vs fd {fd}",
                    grad[i]
                );
            }
        }
    }

    #[test]
    fn lgamma_matches_known_values() {
        // ln Gamma(20) = ln(19!) computed exactly.
        let exact: f64 = (2..20).map(|k| (k as f64).ln()).sum();
        assert!((lgamma(20.0) - exact).abs() < 1e-10);
        // ln Gamma(1.5) = ln(sqrt(pi)/2)
        assert!((lgamma(1.5) - (std::f64::consts::PI.sqrt() / 2.0).ln()).abs() < 1e-10);
    }

    #[test]
    fn path_precision_cholesky_reconstructs() {
        let data = test_data();
        let cal = Calibration {
            mu_hat: -9.0,
            a_hat: 3.0,
            s_hat: -1.5,
            phi_hat: 0.9,
            sigma_hat: 0.25,
            global_cov: [0.04, 0.0, 0.0, 0.0, 0.25, 0.0, 0.0, 0.0, 0.04],
            h_mean: vec![-9.0; data.t()],
        };
        let tri = path_precision(&data, &cal);
        let (l, sub) = tri.cholesky();
        let n = tri.diag.len();
        for i in 0..n {
            let recon = l[i] * l[i] + if i > 0 { sub[i - 1] * sub[i - 1] } else { 0.0 };
            assert!((recon - tri.diag[i]).abs() < 1e-9 * tri.diag[i].abs().max(1.0));
            if i + 1 < n {
                let recon_off = l[i] * sub[i];
                assert!((recon_off - tri.off[i]).abs() < 1e-9 * tri.off[i].abs().max(1.0));
            }
        }
    }
}
