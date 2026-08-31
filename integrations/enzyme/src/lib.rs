//! Reverse-mode autodiff for a pure-Rust log density without Enzyme.
//!
//! `std::autodiff` (Enzyme) is not shipped in the distributed nightly on this
//! platform (see `probe/` and `../AUTODIFF-RESEARCH.md`). This crate measures
//! the honest fallback: a Wengert-tape crate (`reverse` 0.2.2, MIT/Apache-2.0,
//! zero dependencies) differentiating the same Gaussian local-level log
//! density that `STUDIES/exact_state_space_ground_truth_v1` writes by hand.
//!
//! The model is written once as a generic function over a scalar trait so the
//! identical source is evaluated with `f64` (value only) and with `Var`
//! (value + gradient). That is the ergonomic target for any Rust autodiff
//! route: one function, no hand gradient.
#![forbid(unsafe_code)]

use owalnuts::walnutpie::{Target, TargetError};
use reverse::{Gradient, Tape, Var};
use std::ops::{Add, Mul, Sub};
use std::sync::atomic::{AtomicUsize, Ordering};

/// Minimal scalar abstraction shared by `f64` and `reverse::Var`.
pub trait Scalar: Copy + Add<Output = Self> + Sub<Output = Self> + Mul<Output = Self> {
    fn from_f64(x: f64) -> Self;
    fn sub_f64(self, x: f64) -> Self;
    fn mul_f64(self, x: f64) -> Self;
}

impl Scalar for f64 {
    fn from_f64(x: f64) -> Self {
        x
    }
    fn sub_f64(self, x: f64) -> Self {
        self - x
    }
    fn mul_f64(self, x: f64) -> Self {
        self * x
    }
}

impl<'a> Scalar for Var<'a> {
    fn from_f64(_x: f64) -> Self {
        unreachable!("constants are folded through *_f64 helpers")
    }
    fn sub_f64(self, x: f64) -> Self {
        self - x
    }
    fn mul_f64(self, x: f64) -> Self {
        self * x
    }
}

/// Fixed-global local-level model data (matches WP4).
#[derive(Clone, Debug)]
pub struct LocalLevelData {
    pub y: Vec<f64>,
    pub r: Vec<f64>,
    pub m0: f64,
    pub tau0: f64,
    pub mu: f64,
    pub sigma_x: f64,
}

/// The log density written once, generically. Constants are folded so the tape
/// only records operations on parameters.
#[allow(clippy::needless_range_loop)]
pub fn log_density<S: Scalar>(q: &[S], d: &LocalLevelData) -> S {
    let t = q.len();
    let s2 = 1.0 / (d.sigma_x * d.sigma_x);
    let d0 = q[0].sub_f64(d.m0);
    let mut lp = (d0 * d0).mul_f64(-0.5 / (d.tau0 * d.tau0));
    for i in 1..t {
        let inn = (q[i] - q[i - 1]).sub_f64(d.mu);
        lp = lp + (inn * inn).mul_f64(-0.5 * s2);
    }
    for i in 0..t {
        let res = q[i].sub_f64(d.y[i]);
        lp = lp + (res * res).mul_f64(-0.5 / d.r[i]);
    }
    lp
}

/// Hand-written gradient (verbatim from WP4) for verification.
pub fn hand_log_density_gradient(q: &[f64], g: &mut [f64], d: &LocalLevelData) -> f64 {
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

/// Tape-differentiated evaluation: builds a fresh tape per call (the crate's
/// tape is not reusable across evaluations), records the forward pass, and
/// reverse-sweeps once.
pub fn tape_log_density_gradient(q: &[f64], g: &mut [f64], d: &LocalLevelData) -> f64 {
    let tape = Tape::new();
    let vars = tape.add_vars(q);
    let lp = log_density(&vars, d);
    let grads = lp.grad();
    let wrt = grads.wrt(&vars);
    g.copy_from_slice(&wrt);
    lp.val
}

/// Which evaluator backs the target.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Backend {
    Hand,
    Tape,
}

pub struct LocalLevel {
    pub data: LocalLevelData,
    pub backend: Backend,
    calls: AtomicUsize,
}

impl LocalLevel {
    pub fn new(data: LocalLevelData, backend: Backend) -> Self {
        Self {
            data,
            backend,
            calls: AtomicUsize::new(0),
        }
    }
    pub fn calls(&self) -> usize {
        self.calls.load(Ordering::Relaxed)
    }
}

impl Target for LocalLevel {
    fn dimension(&self) -> usize {
        self.data.y.len()
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        let lp = match self.backend {
            Backend::Hand => hand_log_density_gradient(q, g, &self.data),
            Backend::Tape => tape_log_density_gradient(q, g, &self.data),
        };
        if lp.is_finite() && g.iter().all(|x| x.is_finite()) {
            Ok(lp)
        } else {
            Err(TargetError::new("nonfinite evaluation"))
        }
    }
}

/// Deterministic synthetic data in the WP4 pattern.
pub fn simulate(t: usize, seed: u64) -> LocalLevelData {
    use rand::{Rng, SeedableRng, rngs::SmallRng};
    use rand_distr::{Distribution, Normal};
    const M0: f64 = 0.0;
    const TAU0: f64 = 1.0;
    const MU: f64 = 0.01;
    const SIGMA_X: f64 = 0.08;
    const OBS_BASE: f64 = 0.0125;
    let mut rng = SmallRng::seed_from_u64(seed ^ (t as u64));
    let normal = Normal::new(0.0, 1.0).unwrap();
    let mut r = Vec::with_capacity(t);
    for i in 0..t {
        let base = 0.02 + 0.03 * ((2.0 * std::f64::consts::PI * i as f64 / 37.0).sin()).abs();
        let spike = if rng.random::<f64>() < 0.05 {
            0.15
        } else {
            0.0
        };
        let spread = base + spike;
        let z: f64 = normal.sample(&mut rng);
        let volume = (0.9 * z).exp();
        r.push(OBS_BASE * (1.0 + spread * spread + 1.0 / (volume + 1.0)));
    }
    let mut x = Vec::with_capacity(t);
    x.push(M0 + TAU0 * normal.sample(&mut rng));
    for i in 1..t {
        let next = x[i - 1] + MU + SIGMA_X * normal.sample(&mut rng);
        x.push(next);
    }
    let y = (0..t)
        .map(|i| x[i] + r[i].sqrt() * normal.sample(&mut rng))
        .collect();
    LocalLevelData {
        y,
        r,
        m0: M0,
        tau0: TAU0,
        mu: MU,
        sigma_x: SIGMA_X,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::{Rng, SeedableRng, rngs::SmallRng};

    #[test]
    fn tape_gradient_matches_hand_gradient() {
        for &t in &[1usize, 2, 7, 100, 1000] {
            let data = simulate(t, 11);
            let mut rng = SmallRng::seed_from_u64(t as u64);
            for _ in 0..5 {
                let q: Vec<f64> = (0..t).map(|_| rng.random_range(-2.0..2.0)).collect();
                let mut gh = vec![0.0; t];
                let mut gt = vec![0.0; t];
                let lh = hand_log_density_gradient(&q, &mut gh, &data);
                let lt = tape_log_density_gradient(&q, &mut gt, &data);
                assert!((lh - lt).abs() <= 1e-10 * (1.0 + lh.abs()), "value T={t}");
                for i in 0..t {
                    assert!(
                        (gh[i] - gt[i]).abs() <= 1e-10 * (1.0 + gh[i].abs()),
                        "gradient T={t} i={i}: {} vs {}",
                        gh[i],
                        gt[i]
                    );
                }
            }
        }
    }

    #[test]
    fn value_only_path_agrees() {
        let data = simulate(50, 3);
        let q: Vec<f64> = (0..50).map(|i| 0.01 * i as f64).collect();
        let mut g = vec![0.0; 50];
        assert!(
            (log_density(&q, &data) - hand_log_density_gradient(&q, &mut g, &data)).abs() < 1e-12
        );
    }
}
