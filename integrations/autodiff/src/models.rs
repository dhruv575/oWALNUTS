//! Reference models with hand-written gradients, used by the tests and the
//! benchmark: Eight Schools (noncentered), Neal's funnel, and the Gaussian
//! local-level state space (centered, and noncentered through `cumsum`).
//!
//! Each model implements [`Model`] once, generically; the accompanying
//! `hand_gradient` functions are the hand-written densities from the
//! repository's studies (verbatim where noted) and serve only as oracles.

use crate::{
    Const, Data, Linear, Model, Scalar, Shifted, cauchy_lpdf, dot, normal_lpdf, normal_lupdf,
};
use std::f64::consts::PI;

const LOG_2PI: f64 = 1.837_877_066_409_345_3;

fn normal_log_density(x: f64, mean: f64, sd: f64) -> f64 {
    -0.5 * LOG_2PI - sd.ln() - 0.5 * ((x - mean) / sd).powi(2)
}

// ---- Eight Schools ---------------------------------------------------------

/// Eight Schools, noncentered: `q = [mu, log tau, z_1..z_8]`, `mu ~ N(0, 5)`,
/// `tau ~ half-Cauchy(0, 5)`, `z_j ~ N(0, 1)`, `y_j ~ N(mu + tau z_j, se_j)`.
#[derive(Clone, Debug)]
pub struct EightSchools {
    /// Observed effects.
    pub y: [f64; 8],
    /// Observation standard errors.
    pub se: [f64; 8],
}

/// The classic data.
pub const EIGHT_SCHOOLS_Y: [f64; 8] = [28., 8., -3., 7., -1., 1., 18., 12.];
/// The classic standard errors.
pub const EIGHT_SCHOOLS_SE: [f64; 8] = [15., 10., 16., 11., 9., 11., 10., 18.];

impl Default for EightSchools {
    fn default() -> Self {
        Self {
            y: EIGHT_SCHOOLS_Y,
            se: EIGHT_SCHOOLS_SE,
        }
    }
}

impl Model for EightSchools {
    fn dimension(&self) -> usize {
        10
    }

    /// Written term by term in the same order as the study density so the
    /// values are bit-identical to [`EightSchools::hand_gradient`].
    fn log_density<S: Scalar>(&self, q: &[S]) -> S {
        let mu = q[0];
        let log_tau = q[1];
        let tau = log_tau.exp();
        let z = &q[2..];
        let mut value = normal_lpdf(mu, Const(0.), Const(5.))
            + (((tau / 5.).powi(2) + 1.) * (PI * 5.)).rdiv(2.).ln()
            + log_tau;
        for ((&zj, &yj), &sej) in z.iter().zip(&self.y).zip(&self.se) {
            let theta = mu + tau * zj;
            value +=
                normal_lpdf(Const(yj), theta, Const(sej)) + normal_lpdf(zj, Const(0.), Const(1.));
        }
        value
    }

    fn parameter_names(&self) -> Option<Vec<String>> {
        let mut names = vec!["mu".to_string(), "log_tau".to_string()];
        names.extend((1..=8).map(|j| format!("z[{j}]")));
        Some(names)
    }
}

impl EightSchools {
    /// Hand-written density and gradient (the confirmation-v38 density with
    /// the data read from `self`).
    #[allow(clippy::needless_range_loop)]
    pub fn hand_gradient(&self, q: &[f64], gradient: &mut [f64]) -> f64 {
        let mu = q[0];
        let log_tau = q[1];
        let tau = log_tau.exp();
        let z = &q[2..];
        let mut value = normal_log_density(mu, 0., 5.)
            + (2. / (PI * 5. * (1. + (tau / 5.).powi(2)))).ln()
            + log_tau;
        gradient.fill(0.);
        gradient[0] = -mu / 25.;
        gradient[1] = 1. - 2. * tau * tau / (25. + tau * tau);
        for j in 0..8 {
            let theta = mu + tau * z[j];
            let residual = self.y[j] - theta;
            let likelihood_gradient = residual / self.se[j].powi(2);
            value +=
                normal_log_density(self.y[j], theta, self.se[j]) + normal_log_density(z[j], 0., 1.);
            gradient[0] += likelihood_gradient;
            gradient[1] += likelihood_gradient * tau * z[j];
            gradient[j + 2] = -z[j] + likelihood_gradient * tau;
        }
        value
    }
}

/// Verbatim copy of the confirmation-v38 unconstrained density with the data
/// as compile-time constants (the form used by the repository's studies; the
/// compiler folds `ln(se_j)` away, which a data-carrying model cannot).
#[allow(clippy::needless_range_loop)]
pub fn eight_schools_hand_gradient_const(q: &[f64], gradient: &mut [f64]) -> f64 {
    let mu = q[0];
    let log_tau = q[1];
    let tau = log_tau.exp();
    let z = &q[2..];
    let mut value = normal_log_density(mu, 0., 5.)
        + (2. / (PI * 5. * (1. + (tau / 5.).powi(2)))).ln()
        + log_tau;
    gradient.fill(0.);
    gradient[0] = -mu / 25.;
    gradient[1] = 1. - 2. * tau * tau / (25. + tau * tau);
    for j in 0..8 {
        let theta = mu + tau * z[j];
        let residual = EIGHT_SCHOOLS_Y[j] - theta;
        let likelihood_gradient = residual / EIGHT_SCHOOLS_SE[j].powi(2);
        value += normal_log_density(EIGHT_SCHOOLS_Y[j], theta, EIGHT_SCHOOLS_SE[j])
            + normal_log_density(z[j], 0., 1.);
        gradient[0] += likelihood_gradient;
        gradient[1] += likelihood_gradient * tau * z[j];
        gradient[j + 2] = -z[j] + likelihood_gradient * tau;
    }
    value
}

/// Eight Schools written the way a Stan `~` statement would be: the
/// likelihood is one fused `normal_lupdf` over the linear predictor
/// `mu + tau * z` (data `se`, so its `ln se` terms are dropped), the `z` prior
/// one `normal_lpdf`, and the half-Cauchy a fused `cauchy_lpdf`. Same
/// posterior; the value differs from the study density by the constant
/// `sum_j (0.5 ln 2 pi + ln se_j)`.
#[derive(Clone, Debug, Default)]
pub struct EightSchoolsVectorised(pub EightSchools);

impl Model for EightSchoolsVectorised {
    fn dimension(&self) -> usize {
        10
    }

    fn log_density<S: Scalar>(&self, q: &[S]) -> S {
        let mu = q[0];
        let log_tau = q[1];
        let tau = log_tau.exp();
        let z = &q[2..];
        normal_lpdf(mu, Const(0.), Const(5.))
            + cauchy_lpdf(tau, Const(0.), Const(5.))
            + std::f64::consts::LN_2
            + log_tau
            + normal_lupdf(Data(&self.0.y), Linear::new(mu, tau, z), Data(&self.0.se))
            + normal_lpdf(z, Const(0.), Const(1.))
    }
}

// ---- Neal's funnel ---------------------------------------------------------

/// Neal's funnel: `omega ~ N(0, 3)`, `x_i | omega ~ N(0, exp(omega))` for
/// `dimension - 1` coordinates. Written exactly as the repository example
/// (`examples/funnel_paper_adaptation.rs`), constants omitted.
#[derive(Clone, Debug)]
pub struct Funnel {
    /// Total dimension including `omega`.
    pub dimension: usize,
}

impl Model for Funnel {
    fn dimension(&self) -> usize {
        self.dimension
    }

    fn log_density<S: Scalar>(&self, q: &[S]) -> S {
        let omega = q[0];
        let inverse_variance = (-omega).exp();
        let tail = (self.dimension - 1) as f64;
        let sum_squares = dot(&q[1..], &q[1..]);
        -omega * omega / 18.0 - omega * (0.5 * tail) - inverse_variance * 0.5 * sum_squares
    }
}

impl Funnel {
    /// Verbatim hand-written density and gradient.
    pub fn hand_gradient(&self, position: &[f64], gradient: &mut [f64]) -> f64 {
        let omega = position[0];
        let inverse_variance = (-omega).exp();
        let sum_squares: f64 = position[1..].iter().map(|x| x * x).sum();
        let tail = (self.dimension - 1) as f64;
        gradient[0] = -omega / 9.0 - 0.5 * tail + 0.5 * inverse_variance * sum_squares;
        for (g, x) in gradient[1..].iter_mut().zip(&position[1..]) {
            *g = -inverse_variance * x;
        }
        -omega * omega / 18.0 - 0.5 * tail * omega - 0.5 * inverse_variance * sum_squares
    }
}

// ---- Gaussian local level ----------------------------------------------------

/// Fixed-global local-level data (the WP4 pattern): `x_0 ~ N(m0, tau0)`,
/// `x_t = x_{t-1} + mu + sigma_x eps_t`, `y_t ~ N(x_t, sqrt(r_t))`.
#[derive(Clone, Debug)]
pub struct LocalLevelData {
    /// Observations.
    pub y: Vec<f64>,
    /// Observation variances.
    pub r: Vec<f64>,
    /// Observation standard deviations `sqrt(r)`.
    pub sd_obs: Vec<f64>,
    /// `ln sqrt(r)`, precomputed for the hand-written gradient.
    pub log_sd_obs: Vec<f64>,
    /// Prior mean of `x_0`.
    pub m0: f64,
    /// Prior standard deviation of `x_0`.
    pub tau0: f64,
    /// Drift.
    pub mu: f64,
    /// Innovation standard deviation.
    pub sigma_x: f64,
}

impl LocalLevelData {
    /// Build from observations and variances.
    pub fn new(y: Vec<f64>, r: Vec<f64>, m0: f64, tau0: f64, mu: f64, sigma_x: f64) -> Self {
        let sd_obs: Vec<f64> = r.iter().map(|v| v.sqrt()).collect();
        let log_sd_obs = sd_obs.iter().map(|s| s.ln()).collect();
        Self {
            y,
            r,
            sd_obs,
            log_sd_obs,
            m0,
            tau0,
            mu,
            sigma_x,
        }
    }

    /// Number of time points.
    pub fn len(&self) -> usize {
        self.y.len()
    }

    /// True when there are no observations.
    pub fn is_empty(&self) -> bool {
        self.y.is_empty()
    }

    /// Deterministic synthetic data in the WP4 pattern (a small xorshift
    /// generator so the crate has no `rand` dependency).
    pub fn simulate(t: usize, seed: u64) -> Self {
        const M0: f64 = 0.0;
        const TAU0: f64 = 1.0;
        const MU: f64 = 0.01;
        const SIGMA_X: f64 = 0.08;
        const OBS_BASE: f64 = 0.0125;
        let mut state = seed ^ (t as u64) ^ 0x9E37_79B9_7F4A_7C15;
        let mut uniform = move || {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            (state >> 11) as f64 / (1u64 << 53) as f64
        };
        let mut normal = move || {
            let u1 = uniform().max(1e-300);
            let u2 = uniform();
            (-2.0 * u1.ln()).sqrt() * (2.0 * PI * u2).cos()
        };
        let mut r = Vec::with_capacity(t);
        for i in 0..t {
            let base = 0.02 + 0.03 * ((2.0 * PI * i as f64 / 37.0).sin()).abs();
            let spike = if normal().abs() > 1.96 { 0.15 } else { 0.0 };
            let spread = base + spike;
            let volume = (0.9 * normal()).exp();
            r.push(OBS_BASE * (1.0 + spread * spread + 1.0 / (volume + 1.0)));
        }
        let mut x = Vec::with_capacity(t);
        x.push(M0 + TAU0 * normal());
        for i in 1..t {
            let next = x[i - 1] + MU + SIGMA_X * normal();
            x.push(next);
        }
        let y = (0..t).map(|i| x[i] + r[i].sqrt() * normal()).collect();
        Self::new(y, r, M0, TAU0, MU, SIGMA_X)
    }
}

/// Centered local level: the state path `x_0..x_{T-1}` is the parameter.
#[derive(Clone, Debug)]
pub struct LocalLevel {
    /// Data.
    pub data: LocalLevelData,
    /// Include the normalising constants (`-0.5 ln 2 pi - ln sigma`). With
    /// `false` the density uses [`normal_lupdf`] and matches the WP4 form up
    /// to rounding; with `true` it is bit-identical to
    /// [`LocalLevel::hand_gradient`].
    pub normalised: bool,
}

impl Model for LocalLevel {
    fn dimension(&self) -> usize {
        self.data.len()
    }

    /// Three fused nodes: the prior, the transition density over the shifted
    /// path, and the observation density.
    fn log_density<S: Scalar>(&self, q: &[S]) -> S {
        let d = &self.data;
        let t = q.len();
        if self.normalised {
            normal_lpdf(q[0], Const(d.m0), Const(d.tau0))
                + normal_lpdf(&q[1..], Shifted(&q[..t - 1], d.mu), Const(d.sigma_x))
                + normal_lpdf(Data(&d.y), q, Data(&d.sd_obs))
        } else {
            normal_lupdf(q[0], Const(d.m0), Const(d.tau0))
                + normal_lupdf(&q[1..], Shifted(&q[..t - 1], d.mu), Const(d.sigma_x))
                + normal_lupdf(Data(&d.y), q, Data(&d.sd_obs))
        }
    }
}

impl LocalLevel {
    /// Hand-written density and gradient with the same terms and summation
    /// order as [`Model::log_density`], using the precomputed `ln sqrt(r)`.
    pub fn hand_gradient(&self, q: &[f64], g: &mut [f64]) -> f64 {
        let d = &self.data;
        let t = q.len();
        g.iter_mut().for_each(|x| *x = 0.0);
        let z0 = (q[0] - d.m0) / d.tau0;
        let prior = -0.5 * LOG_2PI - d.tau0.ln() - 0.5 * z0 * z0;
        g[0] -= z0 / d.tau0;
        let inv_sx = 1.0 / d.sigma_x;
        let log_sx = d.sigma_x.ln();
        let mut transition = 0.0;
        for i in 1..t {
            let z = (q[i] - (q[i - 1] + d.mu)) / d.sigma_x;
            transition += -0.5 * LOG_2PI - log_sx - 0.5 * z * z;
            g[i] -= z * inv_sx;
            g[i - 1] += z * inv_sx;
        }
        let mut observation = 0.0;
        for i in 0..t {
            let z = (d.y[i] - q[i]) / d.sd_obs[i];
            observation += -0.5 * LOG_2PI - d.log_sd_obs[i] - 0.5 * z * z;
            g[i] += z / d.sd_obs[i];
        }
        prior + transition + observation
    }

    /// The WP4 hand-written gradient verbatim (no normalising constants, the
    /// fastest form a user would write): the throughput baseline in the
    /// research notes.
    pub fn hand_gradient_wp4(&self, q: &[f64], g: &mut [f64]) -> f64 {
        let d = &self.data;
        let t = q.len();
        let s2 = 1.0 / (d.sigma_x * d.sigma_x);
        let mut lp = 0.0;
        g.iter_mut().for_each(|x| *x = 0.0);
        let d0 = q[0] - d.m0;
        lp -= 0.5 * d0 * d0 / (d.tau0 * d.tau0);
        g[0] -= d0 / (d.tau0 * d.tau0);
        for i in 1..t {
            let inn = q[i] - q[i - 1] - d.mu;
            lp -= 0.5 * inn * inn * s2;
            g[i] -= inn * s2;
            g[i - 1] += inn * s2;
        }
        for i in 0..t {
            let res = d.y[i] - q[i];
            let ri = 1.0 / d.r[i];
            lp -= 0.5 * res * res * ri;
            g[i] += res * ri;
        }
        lp
    }
}

/// Noncentered local level: `q = [x_0, eps_1..eps_{T-1}]` with
/// `x_t = x_0 + sum_{s<=t} (mu + sigma_x eps_s)` built with one
/// [`cumsum_affine`](crate::cumsum_affine) block node.
#[derive(Clone, Debug)]
pub struct LocalLevelNoncentered {
    /// Data.
    pub data: LocalLevelData,
}

impl Model for LocalLevelNoncentered {
    fn dimension(&self) -> usize {
        self.data.len()
    }

    fn log_density<S: Scalar>(&self, q: &[S]) -> S {
        let d = &self.data;
        let x0 = q[0];
        // c_t = sum_{s<=t} (sigma_x eps_s + mu), so x_t = x_0 + c_t for t >= 1.
        let c = crate::cumsum_affine(&q[1..], d.sigma_x, d.mu);
        normal_lpdf(x0, Const(d.m0), Const(d.tau0))
            + normal_lpdf(&q[1..], Const(0.0), Const(1.0))
            + normal_lpdf(Const(d.y[0]), x0, Const(d.sd_obs[0]))
            + normal_lpdf(
                Data(&d.y[1..]),
                Linear::new(x0, S::from_f64(1.0), &c),
                Data(&d.sd_obs[1..]),
            )
    }
}

impl LocalLevelNoncentered {
    /// Hand-written density and gradient (reverse cumulative sum of the
    /// observation residuals).
    pub fn hand_gradient(&self, q: &[f64], g: &mut [f64]) -> f64 {
        let d = &self.data;
        let t = q.len();
        let z0 = (q[0] - d.m0) / d.tau0;
        let prior = -0.5 * LOG_2PI - d.tau0.ln() - 0.5 * z0 * z0;
        let mut eps_prior = 0.0;
        for &e in &q[1..] {
            eps_prior += -0.5 * LOG_2PI - 0.5 * e * e;
        }
        // Same arithmetic as the model: c_t accumulates from zero and
        // x_t = x_0 + c_t.
        let z_obs0 = (d.y[0] - q[0]) / d.sd_obs[0];
        let obs0 = -0.5 * LOG_2PI - d.log_sd_obs[0] - 0.5 * z_obs0 * z_obs0;
        let mut c = 0.0;
        let mut observation = 0.0;
        // dlp/dx_t, accumulated in reverse below.
        let mut dx = vec![0.0; t];
        dx[0] = z_obs0 / d.sd_obs[0];
        for i in 1..t {
            c += q[i] * d.sigma_x + d.mu;
            let x = q[0] + c;
            let z = (d.y[i] - x) / d.sd_obs[i];
            observation += -0.5 * LOG_2PI - d.log_sd_obs[i] - 0.5 * z * z;
            dx[i] = z / d.sd_obs[i];
        }
        let mut tail = 0.0;
        for i in (0..t).rev() {
            tail += dx[i];
            g[i] = if i == 0 {
                tail - z0 / d.tau0
            } else {
                tail * d.sigma_x - q[i]
            };
        }
        prior + eps_prior + obs0 + observation
    }
}
