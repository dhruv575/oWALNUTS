//! `polyscope-canonical-v3`: canonical-v2 with **scale-non-centered innovations**.
//!
//! Coordinates `z = [globals(6), x_1, eps_2 .. eps_T]` where the canonical-v2
//! innovation `d_t = x_t - x_{t-1}` is written `d_t = mu + sigma_x * eps_t`,
//! so that a priori `eps_t ~ N(0, 1)` independent of `(mu, sigma_x)`.  The map
//! `z -> q` (v2 innovation coordinates) is block lower-triangular with
//! diagonal `sigma_x` on the `T-1` innovation rows, hence
//!
//! `log p_z(z) = log p_q(q(z)) + (T - 1) * log sigma_x`.
//!
//! Location is left centered in the innovations (the `mu` shift is part of the
//! same affine map), so `eps` carries neither the drift nor the scale.  The
//! observation model, priors, and globals are exactly canonical-v2.

use owalnuts::walnutpie::{Target, TargetError};

use crate::canonical::{Data, log_prob_and_grad};

pub const MODEL_REVISION: &str = "polyscope-canonical-v3-scale-noncentered";

/// `z -> q` (v2 innovation coordinates).
pub fn to_innovations(z: &[f64]) -> Vec<f64> {
    let mu = z[0];
    let sigma_x = z[1].exp();
    let mut q = z.to_vec();
    for i in 7..z.len() {
        q[i] = mu + sigma_x * z[i];
    }
    q
}

/// `q -> z`.
pub fn from_innovations(q: &[f64]) -> Vec<f64> {
    let mu = q[0];
    let sigma_x = q[1].exp();
    let mut z = q.to_vec();
    for i in 7..q.len() {
        z[i] = (q[i] - mu) / sigma_x;
    }
    z
}

/// Log density and gradient in `z` coordinates (includes the log-Jacobian).
pub fn log_prob_and_grad_z(z: &[f64], data: &Data) -> Result<(f64, Vec<f64>), String> {
    if z.len() != data.dim() || z.iter().any(|x| !x.is_finite()) {
        return Err("invalid parameter vector".into());
    }
    let sigma_x = z[1].exp();
    if !sigma_x.is_finite() || sigma_x <= 0.0 {
        return Err("sigma_x=exp(log sigma_x) is not representable as a positive finite f64".into());
    }
    let q = to_innovations(z);
    if q[7..].iter().any(|d| !d.is_finite()) {
        return Err("innovation is not representable as a positive finite f64".into());
    }
    let (lp_q, gq) = log_prob_and_grad(&q, data)?;
    let t_minus_one = (z.len() - 7) as f64;
    let lp = lp_q + t_minus_one * z[1];
    let mut g = gq.clone();
    let mut sum_gd = 0.0;
    let mut sum_gd_eps = 0.0;
    for i in 7..z.len() {
        let gd = gq[i];
        g[i] = gd * sigma_x;
        sum_gd += gd;
        sum_gd_eps += gd * z[i];
    }
    g[0] = gq[0] + sum_gd;
    g[1] = gq[1] + sigma_x * sum_gd_eps + t_minus_one;
    if !lp.is_finite() || g.iter().any(|v| !v.is_finite()) {
        return Err("canonical-v3 log density or gradient is not representable as finite f64".into());
    }
    Ok((lp, g))
}

fn recoverable(message: &str) -> bool {
    message.contains("is not representable as a positive finite f64")
        || message.contains("variance is not representable as a positive finite f64")
}

pub struct V3Target {
    pub data: Data,
    pub calls: std::sync::atomic::AtomicUsize,
}

impl Target for V3Target {
    fn dimension(&self) -> usize {
        self.data.dim()
    }

    fn log_density_gradient(&self, position: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        match log_prob_and_grad_z(position, &self.data) {
            Ok((lp, grad)) => {
                gradient.copy_from_slice(&grad);
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

    fn parity_data() -> Data {
        let fixture: Value =
            serde_json::from_str(include_str!("../fixtures/polyscope_parity.json")).unwrap();
        Data::try_from_raw(
            &numbers(&fixture["data"]["y"]),
            &numbers(&fixture["data"]["spread"]),
            &numbers(&fixture["data"]["volume"]),
        )
        .unwrap()
    }

    /// Deterministic LCG so the test needs no extra dependency.
    fn lcg(state: &mut u64) -> f64 {
        *state = state.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        ((*state >> 11) as f64) / ((1u64 << 53) as f64)
    }

    #[test]
    fn round_trips_and_includes_jacobian() {
        let data = parity_data();
        let q = data.initial_innovations();
        let z = from_innovations(&q);
        let back = to_innovations(&z);
        for (u, v) in q.iter().zip(&back) {
            assert!((u - v).abs() < 1e-12);
        }
        let (lp_q, _) = log_prob_and_grad(&q, &data).unwrap();
        let (lp_z, _) = log_prob_and_grad_z(&z, &data).unwrap();
        let t_minus_one = (q.len() - 7) as f64;
        assert!((lp_z - (lp_q + t_minus_one * q[1])).abs() < 1e-9 * (1.0 + lp_q.abs()));
    }

    #[test]
    fn gradient_matches_central_differences_at_20_random_points() {
        let data = parity_data();
        let base = from_innovations(&data.initial_innovations());
        let n = base.len();
        let mut state = 0x9E3779B97F4A7C15u64;
        for point in 0..20 {
            let mut z = base.clone();
            for (i, value) in z.iter_mut().enumerate() {
                let scale = if i < 6 { 0.5 } else if i == 6 { 0.3 } else { 1.0 };
                *value += scale * (2.0 * lcg(&mut state) - 1.0);
            }
            let (_, g) = log_prob_and_grad_z(&z, &data).unwrap();
            // Every coordinate at three points, a random subset otherwise.
            let coords: Vec<usize> = if point < 3 {
                (0..n).collect()
            } else {
                (0..8).map(|_| (lcg(&mut state) * n as f64) as usize).collect()
            };
            for i in coords {
                let eps = 1e-4;
                let mut zp = z.clone();
                zp[i] += eps;
                let mut zm = z.clone();
                zm[i] -= eps;
                let (lpp, _) = log_prob_and_grad_z(&zp, &data).unwrap();
                let (lpm, _) = log_prob_and_grad_z(&zm, &data).unwrap();
                let fd = (lpp - lpm) / (2.0 * eps);
                let tol = 1e-6 * g[i].abs() + 1e-5;
                assert!(
                    (fd - g[i]).abs() <= tol,
                    "point {point} coord {i}: fd {fd} vs analytic {} (tol {tol})",
                    g[i]
                );
            }
        }
    }

    #[test]
    fn target_maps_recoverable_errors() {
        let data = parity_data();
        let target = V3Target { data, calls: Default::default() };
        let mut z = from_innovations(&target.data.initial_innovations());
        z[1] = 800.0; // exp overflows -> recoverable
        let mut g = vec![0.0; z.len()];
        let err = target.log_density_gradient(&z, &mut g).unwrap_err();
        assert!(matches!(err.kind(), owalnuts::walnutpie::TargetErrorKind::Recoverable));
    }
}
