//! A Gaussian local-level state-space path sampled with the posterior-precision
//! tridiagonal metric.
//!
//! With the global parameters fixed, the posterior over the latent path
//! `x_1..x_T` of `x_t = x_{t-1} + mu + Normal(0, sigma_x^2)`,
//! `y_t = x_t + Normal(0, r_t)` is exactly Gaussian with the tridiagonal
//! precision `H = Q_rw + diag(1 / r_t)`. Supplying `H` as the momentum
//! covariance (its Cholesky factor is lower bidiagonal, so the metric costs
//! `O(T)` per operation) whitens the whole path: trajectories U-turn after a
//! handful of leapfrogs at any `T`, whereas a prior-based path metric collapses
//! the step and saturates the tree depth at `T = 1000` (see
//! `STUDIES/exact_state_space_ground_truth_v1`, ledger entry `WP4-ESSGT-V1`,
//! and the real-target follow-up `WP4B-REAL-TARGET-PATH-METRIC-V1`).
//!
//! The example compares that metric with the identity metric against the exact
//! posterior mean. One caveat worth knowing: on an *exactly* whitened Gaussian
//! every coordinate rotates at the same rate, so a fixed macro step can alias
//! the tree-doubling schedule (the outer U-turn test lands near zero at one
//! depth and stays positive for several more). Stan jitters its step size for
//! this reason; here the target acceptance is set to 0.95, which keeps the
//! adapted step away from that resonance for this fixture.

use std::error::Error;
use std::num::NonZeroUsize;

use owalnuts::walnutpie::{
    DiagonalMass, KernelTuning, RunConfig, StructuredBlockMass, StructuredCovarianceBlock, Target,
    TargetError, WarmupConfig, sample_chains, sample_chains_structured,
};

const T: usize = 200;
const MU: f64 = 0.01;
const SIGMA_X: f64 = 0.08;
const TAU0: f64 = 1.0;

/// Symmetric tridiagonal matrix stored as diagonal and subdiagonal.
struct Tridiagonal {
    diag: Vec<f64>,
    off: Vec<f64>,
}

impl Tridiagonal {
    /// Lower-bidiagonal Cholesky factor `L` with `L L' = self`.
    fn cholesky(&self) -> (Vec<f64>, Vec<f64>) {
        let n = self.diag.len();
        let mut d = vec![0.0; n];
        let mut l = vec![0.0; n - 1];
        d[0] = self.diag[0].sqrt();
        for i in 1..n {
            l[i - 1] = self.off[i - 1] / d[i - 1];
            d[i] = (self.diag[i] - l[i - 1] * l[i - 1]).sqrt();
        }
        (d, l)
    }

    /// Solve `self x = b` by the Thomas algorithm.
    fn solve(&self, b: &[f64]) -> Vec<f64> {
        let n = self.diag.len();
        let mut c = vec![0.0; n];
        let mut d = vec![0.0; n];
        c[0] = self.off[0] / self.diag[0];
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
}

struct LocalLevel {
    y: Vec<f64>,
    r: Vec<f64>,
}

impl LocalLevel {
    /// Prior random-walk precision plus the observation precision.
    fn posterior_precision(&self) -> Tridiagonal {
        let s2 = 1.0 / (SIGMA_X * SIGMA_X);
        let mut diag = vec![2.0 * s2; T];
        diag[0] = 1.0 / (TAU0 * TAU0) + s2;
        diag[T - 1] = s2;
        for (d, r) in diag.iter_mut().zip(&self.r) {
            *d += 1.0 / r;
        }
        Tridiagonal {
            diag,
            off: vec![-s2; T - 1],
        }
    }

    fn posterior_mean(&self) -> Vec<f64> {
        let s2 = 1.0 / (SIGMA_X * SIGMA_X);
        let mut b: Vec<f64> = self.y.iter().zip(&self.r).map(|(y, r)| y / r).collect();
        b[0] -= MU * s2;
        b[T - 1] += MU * s2;
        self.posterior_precision().solve(&b)
    }
}

impl Target for LocalLevel {
    fn dimension(&self) -> usize {
        T
    }

    fn log_density_gradient(&self, x: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        let s2 = 1.0 / (SIGMA_X * SIGMA_X);
        let mut lp = -0.5 * x[0] * x[0] / (TAU0 * TAU0);
        g.iter_mut().for_each(|value| *value = 0.0);
        g[0] = -x[0] / (TAU0 * TAU0);
        for t in 1..T {
            let innovation = x[t] - x[t - 1] - MU;
            lp -= 0.5 * s2 * innovation * innovation;
            g[t] -= s2 * innovation;
            g[t - 1] += s2 * innovation;
        }
        for t in 0..T {
            let residual = self.y[t] - x[t];
            lp -= 0.5 * residual * residual / self.r[t];
            g[t] += residual / self.r[t];
        }
        Ok(lp)
    }
}

/// Deterministic synthetic data from a tiny linear congruential generator, so
/// the example needs no external randomness.
fn simulate() -> LocalLevel {
    let mut state = 0x2545_f491_4f6c_dd1du64;
    let mut normal = || {
        // Sum of twelve uniforms, centred: adequate for a demonstration.
        let mut sum = 0.0;
        for _ in 0..12 {
            state = state
                .wrapping_mul(6_364_136_223_846_793_005)
                .wrapping_add(1_442_695_040_888_963_407);
            sum += (state >> 11) as f64 / (1u64 << 53) as f64;
        }
        sum - 6.0
    };
    let mut x = 0.0;
    let mut y = Vec::with_capacity(T);
    let mut r = Vec::with_capacity(T);
    for t in 0..T {
        x += MU + SIGMA_X * normal();
        // Heteroscedastic observation variance patterned on a spread/volume
        // microstructure model.
        let variance = 0.0125 * (1.0 + 0.5 * ((t % 7) as f64 / 7.0));
        r.push(variance);
        y.push(x + variance.sqrt() * normal());
    }
    LocalLevel { y, r }
}

fn main() -> Result<(), Box<dyn Error>> {
    let nz = |value: usize| NonZeroUsize::new(value).expect("nonzero");
    let target = simulate();
    let exact_mean = target.posterior_mean();

    let tuning = KernelTuning::new(0.5, nz(8), nz(1), nz(2), 1.0)?;
    let config = RunConfig::new(300, nz(1_000), 0x5eed_2026)
        .with_tuning(tuning)
        .with_warmup(WarmupConfig::new(0.95)?.with_mass_adaptation(false));
    let starts: Vec<Vec<f64>> = (0..4)
        .map(|chain| vec![0.5 * (chain as f64 - 1.5); T])
        .collect();

    let identity = DiagonalMass::identity(nz(T));
    let identity_output = sample_chains(&target, &starts, &identity, &config, nz(4))?;

    let (diagonal, subdiagonal) = target.posterior_precision().cholesky();
    let path_metric =
        StructuredBlockMass::new(vec![StructuredCovarianceBlock::BidiagonalCholesky {
            diagonal,
            subdiagonal,
        }])?;
    let path_output = sample_chains_structured(&target, &starts, &path_metric, &config, nz(4))?;

    for (label, output) in [
        ("identity", &identity_output),
        ("posterior precision", &path_output),
    ] {
        let mut calls = 0usize;
        let mut caps = 0usize;
        let mut depths = Vec::new();
        let mut max_abs_error: f64 = 0.0;
        for chain in output.chains() {
            calls += chain.telemetry().total().target_calls_total();
            caps += chain.telemetry().total().maximum_depth_stops();
            depths.extend(chain.diagnostics().iter().map(|d| d.depth()));
            let mut mean = vec![0.0; T];
            for draw in 0..chain.retained() {
                for (m, value) in mean.iter_mut().zip(chain.sample(draw).expect("draw")) {
                    *m += value;
                }
            }
            for (m, exact) in mean.iter_mut().zip(&exact_mean) {
                *m /= chain.retained() as f64;
                max_abs_error = max_abs_error.max((*m - exact).abs());
            }
        }
        depths.sort_unstable();
        let steps: Vec<String> = output
            .chains()
            .iter()
            .map(|c| format!("{:.3}", c.metadata().tuning().step_size()))
            .collect();
        println!(
            "{label:>19}: target calls={calls}, median depth={}, depth caps={caps}, adapted steps={steps:?}, max |mean - exact|={max_abs_error:.4}",
            depths[depths.len() / 2],
        );
    }
    Ok(())
}
