//! Reverse-mode autodiff for `owalnuts` targets: write the log density once,
//! generically over [`Scalar`], and get an [`owalnuts::walnutpie::Target`]
//! with a gradient from a fused-primitive arena tape.
//!
//! # Design
//!
//! * [`Var`] is a 16-byte `Copy` handle `{ value, index }` into a
//!   thread-local, reusable arena tape ([`Tape`]). Because the value travels
//!   with the handle, arithmetic never reads the tape; it appends one node.
//! * Nodes are an enum with inline operand indices and partials
//!   (`Unary`/`Binary`/`Ternary`) or, for the fused vector primitives, an
//!   `Nary` node whose `(index, partial)` pairs live in two side arrays. There
//!   are no boxed closures and no per-node allocation.
//! * Fused primitives ([`normal_lpdf`], [`dot`], [`cumsum`], ...) record one
//!   node per call however long the vectors are, so a `T = 1000` state-space
//!   likelihood is a handful of nodes with `O(T)` side entries.
//! * [`cumsum`] over a contiguous input is one *block* node spanning its
//!   outputs; its reverse sweep is a single reverse scan.
//! * A fused node is made of one *segment* per operand. An operand whose
//!   elements sit at consecutive tape indices (a slice of the inputs, a
//!   [`cumsum`] output) stores partials only and its reverse sweep is a
//!   contiguous `axpy`; scattered operands store index/partial pairs.
//! * `Var + f64` and `Var - f64` reuse the operand's node (the derivative is
//!   one), and the wrappers [`Const`], [`Data`], [`Shifted`] and [`Linear`]
//!   let data, shifted vectors and linear predictors `a + b * x` enter a
//!   primitive without extra nodes.
//! * [`AutodiffTarget`] resets and reuses the tape each call; every worker
//!   thread has its own, so parallel chains need no locking.
//!
//! # Example
//!
//! ```
//! use owalnuts_autodiff::{AutodiffTarget, Const, Model, Scalar, normal_lpdf};
//! use owalnuts::walnutpie::Target;
//!
//! struct EightSchools { y: [f64; 8], sigma: [f64; 8] }
//!
//! impl Model for EightSchools {
//!     fn dimension(&self) -> usize { 10 }
//!     fn log_density<S: Scalar>(&self, q: &[S]) -> S {
//!         let (mu, log_tau, z) = (q[0], q[1], &q[2..]);
//!         let tau = log_tau.exp();
//!         let mut lp = normal_lpdf(mu, Const(0.0), Const(5.0))
//!             + ((tau / 5.0).square() + 1.0).rdiv(2.0 / (std::f64::consts::PI * 5.0)).ln()
//!             + log_tau; // half-Cauchy(0, 5) on tau plus the log-Jacobian of exp
//!         for j in 0..8 {
//!             let theta = mu + tau * z[j];
//!             lp += normal_lpdf(Const(self.y[j]), theta, Const(self.sigma[j]))
//!                 + normal_lpdf(z[j], Const(0.0), Const(1.0));
//!         }
//!         lp
//!     }
//! }
//!
//! let target = AutodiffTarget::new(EightSchools {
//!     y: [28., 8., -3., 7., -1., 1., 18., 12.],
//!     sigma: [15., 10., 16., 11., 9., 11., 10., 18.],
//! });
//! let q = [0.5, -0.2, 0.1, -0.3, 0.2, 0.0, 0.4, -0.1, 0.3, 0.2];
//! let mut grad = [0.0; 10];
//! let value = target.log_density_gradient(&q, &mut grad).unwrap();
//! assert!(value.is_finite() && grad.iter().all(|g| g.is_finite()));
//! ```
#![forbid(unsafe_code)]
#![warn(missing_docs)]

mod dist;
pub mod models;
mod operand;
mod scalar;
mod tape;
mod target;
mod transform;

pub use dist::{digamma_f64, lgamma_f64, sigmoid_f64, softplus_f64};
pub use operand::{Const, Data, Linear, Operand, Shifted, VectorPart};
pub use scalar::{Scalar, Var};
pub use tape::Tape;
pub use target::{
    AutodiffTarget, Model, NonfinitePolicy, TapeStats, gradient_with, last_tape_stats,
};

/// Sum of `normal_lpdf(x_i | mu_i, sigma_i)` over the broadcast length.
#[inline]
pub fn normal_lpdf<S: Scalar, X: Operand<S>, M: Operand<S>, G: Operand<S>>(
    x: X,
    mu: M,
    sigma: G,
) -> S {
    S::normal_lpdf(x, mu, sigma)
}

/// Normal log density dropping the terms that do not depend on parameters
/// (Stan's `normal_lupdf`): `-0.5 z^2`, plus `-ln sigma` unless `sigma` is
/// data. Cheaper than [`normal_lpdf`] when `sigma` is a data vector.
#[inline]
pub fn normal_lupdf<S: Scalar, X: Operand<S>, M: Operand<S>, G: Operand<S>>(
    x: X,
    mu: M,
    sigma: G,
) -> S {
    S::normal_lupdf(x, mu, sigma)
}

/// Student-t log density with fixed degrees of freedom `nu`.
#[inline]
pub fn student_t_lpdf<S: Scalar, X: Operand<S>, M: Operand<S>, G: Operand<S>>(
    x: X,
    nu: f64,
    mu: M,
    sigma: G,
) -> S {
    S::student_t_lpdf(x, nu, mu, sigma)
}

/// Cauchy log density.
#[inline]
pub fn cauchy_lpdf<S: Scalar, X: Operand<S>, M: Operand<S>, G: Operand<S>>(
    x: X,
    mu: M,
    sigma: G,
) -> S {
    S::cauchy_lpdf(x, mu, sigma)
}

/// Log-normal log density (`x > 0`).
#[inline]
pub fn lognormal_lpdf<S: Scalar, X: Operand<S>, M: Operand<S>, G: Operand<S>>(
    x: X,
    mu: M,
    sigma: G,
) -> S {
    S::lognormal_lpdf(x, mu, sigma)
}

/// Exponential log density with rate `rate` (`x >= 0`).
#[inline]
pub fn exponential_lpdf<S: Scalar, X: Operand<S>, B: Operand<S>>(x: X, rate: B) -> S {
    S::exponential_lpdf(x, rate)
}

/// Gamma log density with shape `shape` and rate `rate` (`x > 0`).
#[inline]
pub fn gamma_lpdf<S: Scalar, X: Operand<S>, A: Operand<S>, B: Operand<S>>(
    x: X,
    shape: A,
    rate: B,
) -> S {
    S::gamma_lpdf(x, shape, rate)
}

/// Half-normal log density (`x >= 0`).
#[inline]
pub fn half_normal_lpdf<S: Scalar, X: Operand<S>, G: Operand<S>>(x: X, sigma: G) -> S {
    S::half_normal_lpdf(x, sigma)
}

/// Bernoulli log mass with logit `eta`: `y * eta - softplus(eta)`.
#[inline]
pub fn bernoulli_logit_lpmf<S: Scalar, Y: Operand<S>, E: Operand<S>>(y: Y, eta: E) -> S {
    S::bernoulli_logit_lpmf(y, eta)
}

/// Poisson log mass with log rate: `y * l - exp(l) - ln Gamma(y + 1)`.
#[inline]
pub fn poisson_log_lpmf<S: Scalar, Y: Operand<S>, E: Operand<S>>(y: Y, log_rate: E) -> S {
    S::poisson_log_lpmf(y, log_rate)
}

/// Inner product (scalars broadcast).
#[inline]
pub fn dot<S: Scalar, A: Operand<S>, B: Operand<S>>(a: A, b: B) -> S {
    S::dot(a, b)
}

/// Sum of the elements.
#[inline]
pub fn sum<S: Scalar, A: Operand<S>>(a: A) -> S {
    S::sum_all(a)
}

/// `ln sum exp(a_i)`, computed stably.
#[inline]
pub fn log_sum_exp<S: Scalar, A: Operand<S>>(a: A) -> S {
    S::log_sum_exp(a)
}

/// Inclusive cumulative sum into a new vector (`O(n)` tape nodes).
#[inline]
pub fn cumsum<S: Scalar>(x: &[S]) -> Vec<S> {
    let mut out = vec![S::from_f64(0.0); x.len()];
    S::cumsum(x, &mut out);
    out
}

/// Inclusive cumulative sum into a caller-provided buffer.
#[inline]
pub fn cumsum_into<S: Scalar>(x: &[S], out: &mut [S]) {
    S::cumsum(x, out);
}

/// `out[i] = sum_{j <= i} (scale * x[j] + shift)` into a new vector: a random
/// walk with drift `shift` and innovation scale `scale` in one block node.
#[inline]
pub fn cumsum_affine<S: Scalar>(x: &[S], scale: f64, shift: f64) -> Vec<S> {
    let mut out = vec![S::from_f64(0.0); x.len()];
    S::cumsum_affine(x, scale, shift, &mut out);
    out
}

/// `ln(1 + exp(x))`.
#[inline]
pub fn softplus<S: Scalar>(x: S) -> S {
    x.softplus()
}

/// `(exp(y), log-Jacobian)`.
#[inline]
pub fn exp_constrain<S: Scalar>(y: S) -> (S, S) {
    y.exp_constrain()
}

/// `(lb + exp(y), log-Jacobian)`: real line to `(lb, inf)`.
#[inline]
pub fn lower_bound_constrain<S: Scalar>(y: S, lb: f64) -> (S, S) {
    (y.exp() + lb, y)
}

/// `(sigmoid(y), log-Jacobian)`: real line to `(0, 1)`.
#[inline]
pub fn logistic_constrain<S: Scalar>(y: S) -> (S, S) {
    y.logistic_constrain()
}

/// `(lb + (ub - lb) sigmoid(y), log-Jacobian)`: real line to `(lb, ub)`.
#[inline]
pub fn interval_constrain<S: Scalar>(y: S, lb: f64, ub: f64) -> (S, S) {
    let (u, lj) = y.logistic_constrain();
    (u * (ub - lb) + lb, lj + (ub - lb).ln())
}

/// Ordered vector from free coordinates, returning `(x, log-Jacobian)`.
#[inline]
pub fn ordered_constrain<S: Scalar>(y: &[S]) -> (Vec<S>, S) {
    let mut out = vec![S::from_f64(0.0); y.len()];
    let lj = S::ordered_constrain(y, &mut out);
    (out, lj)
}
