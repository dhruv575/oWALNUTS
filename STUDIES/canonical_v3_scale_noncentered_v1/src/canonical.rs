#![allow(dead_code)]
//! `polyscope-canonical-v2` target, ported verbatim from
//! `C:\dev\polyscope\POLYSCOPE_WEB\processor\owalnuts_local\src\canonical.rs`
//! with the triangular unit-Jacobian centeredness map generalised to a
//! runtime `a` (the production value is 0.75; `a = 1` gives the centered
//! latent-state coordinates `[globals; x_1..x_T]`).

use std::f64::consts::PI;

use owalnuts::walnutpie::{Target, TargetError};

pub const MODEL_REVISION: &str = "polyscope-canonical-v2";

#[derive(Clone, Debug)]
pub struct Data {
    pub logit_y: Vec<f64>,
    pub s: Vec<f64>,
    pub v_n: Vec<f64>,
    sigma_mu: f64,
    sigma_rw: f64,
    sigma_obs: f64,
    pub tau: f64,
    eps: f64,
    delta_t: f64,
}

impl Data {
    pub fn try_from_raw(y: &[f64], spread: &[f64], volume: &[f64]) -> Result<Self, String> {
        if y.is_empty() {
            return Err("price data must not be empty".into());
        }
        if spread.len() != y.len() || volume.len() != y.len() {
            return Err("price, spread, and volume lengths must match".into());
        }
        if let Some((i, value)) = y
            .iter()
            .enumerate()
            .find(|(_, x)| !x.is_finite() || **x <= 0.0 || **x >= 1.0)
        {
            return Err(format!("price at index {i} must be finite and strictly within (0, 1) (got {value})"));
        }
        for (name, values) in [("spread", spread), ("volume", volume)] {
            if let Some((i, value)) = values.iter().enumerate().find(|(_, x)| !x.is_finite() || **x < 0.0) {
                return Err(format!("{name} at index {i} must be finite and non-negative (got {value})"));
            }
        }
        let mut positive: Vec<_> = volume.iter().copied().filter(|v| *v > 0.0).collect();
        positive.sort_by(f64::total_cmp);
        let median = positive.get(positive.len() / 2).copied().unwrap_or(1.0);
        Ok(Self {
            logit_y: y.iter().map(|p| (p / (1.0 - p)).ln()).collect(),
            s: spread.to_vec(),
            v_n: volume.iter().map(|v| v / median).collect(),
            sigma_mu: 0.1,
            sigma_rw: 0.1,
            sigma_obs: 0.5,
            tau: 1.0,
            eps: 1.0,
            delta_t: 1.0,
        })
    }

    pub fn t(&self) -> usize {
        self.logit_y.len()
    }

    pub fn dim(&self) -> usize {
        self.t() + 6
    }

    /// Data-informed innovations-coordinate start (identical to production).
    pub fn initial_innovations(&self) -> Vec<f64> {
        let t = self.t();
        let diffs: Vec<_> = self.logit_y.windows(2).map(|w| w[1] - w[0]).collect();
        let mean = diffs.iter().sum::<f64>() / diffs.len().max(1) as f64;
        let variance = diffs.iter().map(|d| (d - mean).powi(2)).sum::<f64>()
            / (diffs.len() as f64 - 1.0).max(1.0);
        let mut params = vec![0.0; self.dim()];
        params[0] = mean.clamp(-0.05, 0.05);
        params[1] = variance.sqrt().clamp(0.001, 1.0).ln();
        let mut latent = vec![self.logit_y[0]; t];
        for i in 1..t {
            latent[i] = latent[i - 1] + mean;
        }
        let residuals: Vec<_> = latent.iter().zip(&self.logit_y).map(|(x, y)| x - y).collect();
        let residual_mean = residuals.iter().sum::<f64>() / t as f64;
        let residual_sd = (residuals.iter().map(|r| (r - residual_mean).powi(2)).sum::<f64>()
            / t as f64)
            .sqrt()
            .max(0.01);
        params[2] = residual_sd.clamp(0.001, 1.0).ln();
        params[3] = -2.0;
        params[4] = residual_sd.clamp(0.001, 1.0).ln();
        params[6] = self.logit_y[0];
        params[7..].copy_from_slice(&diffs);
        params
    }

    /// Student-t curvature at zero residual, `(nu+1)/(nu sigma_t^2)`, for the
    /// observation scale implied by unconstrained globals `q[2..6]`.
    pub fn observation_curvature(&self, q_globals: &[f64]) -> Vec<f64> {
        let alpha = q_globals[2].exp();
        let beta = q_globals[3].exp();
        let gamma = q_globals[4].exp();
        let nu = 2.0 + q_globals[5].exp();
        (0..self.t())
            .map(|i| {
                let variance = alpha * alpha
                    + beta * beta * self.s[i] * self.s[i]
                    + gamma * gamma / (self.v_n[i] + self.eps);
                (nu + 1.0) / (nu * variance)
            })
            .collect()
    }
}

pub fn from_innovations(q: &[f64], a: f64) -> Vec<f64> {
    let mut y = q.to_vec();
    let mut x = q[6];
    for i in 7..q.len() {
        y[i] = q[i] + a * x;
        x += q[i];
    }
    y
}

pub fn to_innovations(y: &[f64], a: f64) -> Vec<f64> {
    let mut q = y.to_vec();
    let mut x = y[6];
    for i in 7..y.len() {
        q[i] = y[i] - a * x;
        x = (1.0 - a) * x + y[i];
    }
    q
}

fn pullback_gradient(gq: &[f64], a: f64) -> Vec<f64> {
    let mut gy = gq.to_vec();
    let mut adj = 0.0;
    for i in (7..gq.len()).rev() {
        gy[i] = gq[i] + adj;
        adj = -a * gq[i] + (1.0 - a) * adj;
    }
    gy[6] = gq[6] + adj;
    gy
}

pub fn latent_path_from_innovations(q: &[f64]) -> Vec<f64> {
    let mut path = Vec::with_capacity(q.len() - 6);
    let mut x = q[6];
    path.push(x);
    for innovation in &q[7..] {
        x += innovation;
        path.push(x);
    }
    path
}

#[inline]
fn normal_lp(x: f64, mean: f64, sigma: f64) -> f64 {
    let z = (x - mean) / sigma;
    -0.5 * z * z - sigma.ln() - 0.5 * (2.0 * PI).ln()
}

fn ln_gamma(x: f64) -> f64 {
    if x < 0.5 {
        return (PI / (PI * x).sin()).ln() - ln_gamma(1.0 - x);
    }
    let x = x - 1.0;
    let c = [
        0.99999999999980993,
        676.5203681218851,
        -1259.1392167224028,
        771.32342877765313,
        -176.61502916214059,
        12.507343278686905,
        -0.13857109526572012,
        9.9843695780195716e-6,
        1.5056327351493116e-7,
    ];
    let sum = c.iter().enumerate().skip(1).fold(c[0], |s, (i, v)| s + v / (x + i as f64));
    let z = x + 7.5;
    0.5 * (2.0 * PI).ln() + (x + 0.5) * z.ln() - z + sum.ln()
}

fn digamma(mut x: f64) -> f64 {
    if x < 1e-6 {
        return -1.0 / x - 0.5772156649015329;
    }
    let mut result = 0.0;
    while x < 6.0 {
        result -= 1.0 / x;
        x += 1.0;
    }
    let x2 = 1.0 / (x * x);
    result + x.ln() - 0.5 / x - x2 / 12.0 + x2.powi(2) / 120.0 - x2.powi(3) / 252.0
        + x2.powi(4) / 240.0
        - x2.powi(5) / 132.0
        + 691.0 * x2.powi(6) / 32760.0
}

#[inline]
fn exact_exp(x: f64, name: &str) -> Result<f64, String> {
    let value = x.exp();
    if value.is_finite() && value > 0.0 {
        Ok(value)
    } else {
        Err(format!("{name}=exp({x}) is not representable as a positive finite f64"))
    }
}

fn recoverable(message: &str) -> bool {
    message.contains("is not representable as a positive finite f64")
        || message.contains("variance is not representable as a positive finite f64")
}

struct StudentT {
    nu: f64,
    log_normalizer: f64,
    digamma_term: f64,
}

impl StudentT {
    fn new(nu: f64) -> Self {
        Self {
            nu,
            log_normalizer: ln_gamma((nu + 1.0) / 2.0) - ln_gamma(nu / 2.0) - 0.5 * (nu * PI).ln(),
            digamma_term: digamma((nu + 1.0) / 2.0) - digamma(nu / 2.0) - 1.0 / nu,
        }
    }

    fn evaluate(&self, y: f64, mean: f64, sigma: f64) -> (f64, f64, f64, f64) {
        let residual = y - mean;
        let z2 = (residual / sigma).powi(2);
        let tail = (1.0 + z2 / self.nu).ln();
        let lp = self.log_normalizer - sigma.ln() - 0.5 * (self.nu + 1.0) * tail;
        let dmean = (self.nu + 1.0) * residual / (self.nu * sigma * sigma + residual * residual);
        let dsigma = -1.0 / sigma + (self.nu + 1.0) * z2 / (sigma * (self.nu + z2));
        let dnu = 0.5 * (self.digamma_term + ((self.nu + 1.0) / self.nu) * z2 / (self.nu + z2) - tail);
        (lp, dmean, dsigma, dnu)
    }
}

pub fn log_prob_and_grad(params: &[f64], data: &Data) -> Result<(f64, Vec<f64>), String> {
    if params.len() != data.dim() || params.iter().any(|x| !x.is_finite()) {
        return Err("invalid parameter vector".into());
    }
    let t = data.t();
    let mu = params[0];
    let sigma_x = exact_exp(params[1], "sigma_x")?;
    let alpha = exact_exp(params[2], "alpha")?;
    let beta = exact_exp(params[3], "beta")?;
    let gamma = exact_exp(params[4], "gamma")?;
    let eta = exact_exp(params[5], "eta")?;
    let nu = 2.0 + eta;
    if !nu.is_finite() {
        return Err("nu=2+eta is not finite".into());
    }
    let x1 = params[6];
    let mut lp = normal_lp(mu, 0.0, data.sigma_mu);
    let mut grad = vec![0.0; params.len()];
    grad[0] = -mu / data.sigma_mu.powi(2);
    for (i, value, sigma) in [
        (1, sigma_x, data.sigma_rw),
        (2, alpha, data.sigma_obs),
        (3, beta, data.sigma_obs),
        (4, gamma, data.sigma_obs),
    ] {
        let z2 = (value / sigma).powi(2);
        lp += -0.5 * z2 + 2.0_f64.ln() - sigma.ln() - 0.5 * (2.0 * PI).ln() + params[i];
        grad[i] = 1.0 - z2;
    }
    lp += params[5] - eta;
    grad[5] = 1.0 - eta;
    lp += normal_lp(x1, data.logit_y[0], data.tau);
    grad[6] = -(x1 - data.logit_y[0]) / data.tau.powi(2);
    let innovation_mean = mu * data.delta_t;
    let innovation_variance = (sigma_x * data.delta_t.sqrt()).powi(2);
    if !innovation_variance.is_finite() || innovation_variance <= 0.0 {
        return Err("innovation variance is not representable as a positive finite f64".into());
    }
    for (i, innovation) in params[7..].iter().enumerate() {
        let residual = innovation - innovation_mean;
        lp += normal_lp(*innovation, innovation_mean, innovation_variance.sqrt());
        grad[7 + i] -= residual / innovation_variance;
        grad[0] += residual * data.delta_t / innovation_variance;
        grad[1] += residual * residual / innovation_variance - 1.0;
    }
    let mut latent = Vec::with_capacity(t);
    latent.push(x1);
    for innovation in &params[7..] {
        let next = latent.last().unwrap() + innovation;
        if !next.is_finite() {
            return Err("latent path is not finite".into());
        }
        latent.push(next);
    }
    let student = StudentT::new(nu);
    let mut latent_grad = vec![0.0; t];
    let mut scale_grads = [0.0; 3];
    let mut nu_grad = 0.0;
    for (i, x) in latent.iter().copied().enumerate() {
        let spread2 = data.s[i] * data.s[i];
        let volume = data.v_n[i] + data.eps;
        let variance = alpha * alpha + beta * beta * spread2 + gamma * gamma / volume;
        if !variance.is_finite() || variance <= 0.0 {
            return Err(format!("observation variance at index {i} is not positive and finite"));
        }
        let sigma = variance.sqrt();
        let (ll, dx, dsigma, dnu) = student.evaluate(data.logit_y[i], x, sigma);
        lp += ll;
        latent_grad[i] += dx;
        let d = dsigma / sigma;
        scale_grads[0] += d * alpha * alpha;
        scale_grads[1] += d * beta * beta * spread2;
        scale_grads[2] += d * gamma * gamma / volume;
        nu_grad += dnu;
    }
    grad[2] += scale_grads[0];
    grad[3] += scale_grads[1];
    grad[4] += scale_grads[2];
    grad[5] += nu_grad * eta;
    let mut suffix = 0.0;
    for i in (0..t).rev() {
        suffix += latent_grad[i];
        if i > 0 {
            grad[6 + i] += suffix;
        }
    }
    grad[6] += suffix;
    if !lp.is_finite() || grad.iter().any(|value| !value.is_finite()) {
        return Err("canonical log density or gradient is not representable as finite f64".into());
    }
    Ok((lp, grad))
}

/// Target in y-coordinates with centeredness `a`.
pub struct CenteredTarget {
    pub data: Data,
    pub a: f64,
    pub calls: std::sync::atomic::AtomicUsize,
}

impl Target for CenteredTarget {
    fn dimension(&self) -> usize {
        self.data.dim()
    }

    fn log_density_gradient(&self, position: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        let q = to_innovations(position, self.a);
        match log_prob_and_grad(&q, &self.data) {
            Ok((lp, grad)) => {
                gradient.copy_from_slice(&pullback_gradient(&grad, self.a));
                Ok(lp)
            }
            Err(message) if recoverable(&message) => Err(TargetError::recoverable(message)),
            Err(message) => Err(TargetError::new(message)),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Value;

    fn numbers(value: &Value) -> Vec<f64> {
        value.as_array().unwrap().iter().map(|item| item.as_f64().unwrap()).collect()
    }

    #[test]
    fn matches_every_canonical_v2_oracle_case() {
        let fixture: Value =
            serde_json::from_str(include_str!("../fixtures/polyscope_parity.json")).unwrap();
        assert_eq!(fixture["schema"], MODEL_REVISION);
        let data = Data::try_from_raw(
            &numbers(&fixture["data"]["y"]),
            &numbers(&fixture["data"]["spread"]),
            &numbers(&fixture["data"]["volume"]),
        )
        .unwrap();
        for case in fixture["cases"].as_array().unwrap() {
            let params = numbers(&case["params"]);
            let expected_gradient = numbers(&case["gradient"]);
            let (actual_lp, actual_gradient) = log_prob_and_grad(&params, &data).unwrap();
            let expected_lp = case["log_prob"].as_f64().unwrap();
            assert!(
                (actual_lp - expected_lp).abs() <= 2e-12 + 5e-15 * expected_lp.abs(),
                "{} log density mismatch",
                case["name"]
            );
            assert!(
                actual_gradient.iter().zip(&expected_gradient).all(|(a, e)| (a - e).abs() <= 2e-10 + 5e-15 * e.abs()),
                "{} gradient mismatch",
                case["name"]
            );
        }
    }

    #[test]
    fn centeredness_map_round_trips_and_gradient_pulls_back() {
        let fixture: Value =
            serde_json::from_str(include_str!("../fixtures/polyscope_parity.json")).unwrap();
        let data = Data::try_from_raw(
            &numbers(&fixture["data"]["y"]),
            &numbers(&fixture["data"]["spread"]),
            &numbers(&fixture["data"]["volume"]),
        )
        .unwrap();
        let q = data.initial_innovations();
        for a in [0.0, 0.75, 1.0] {
            let y = from_innovations(&q, a);
            let back = to_innovations(&y, a);
            for (u, v) in q.iter().zip(&back) {
                assert!((u - v).abs() < 1e-12);
            }
            if a == 1.0 {
                let path = latent_path_from_innovations(&q);
                for (i, x) in path.iter().enumerate() {
                    assert!((y[6 + i] - x).abs() < 1e-12, "a=1 coordinates are the latent path");
                }
            }
            let target = CenteredTarget { data: data.clone(), a, calls: Default::default() };
            let mut g = vec![0.0; y.len()];
            let lp = target.log_density_gradient(&y, &mut g).unwrap();
            for &i in &[0usize, 1, 5, 6, 7, y.len() / 2, y.len() - 1] {
                let eps = 1e-6;
                let mut yp = y.clone();
                yp[i] += eps;
                let mut ym = y.clone();
                ym[i] -= eps;
                let mut gp = vec![0.0; y.len()];
                let lpp = target.log_density_gradient(&yp, &mut gp).unwrap();
                let lpm = target.log_density_gradient(&ym, &mut gp).unwrap();
                let fd = (lpp - lpm) / (2.0 * eps);
                assert!((fd - g[i]).abs() < 1e-5 * (1.0 + g[i].abs()), "a={a} i={i} fd {fd} vs {}", g[i]);
            }
            let _ = lp;
        }
    }
}
