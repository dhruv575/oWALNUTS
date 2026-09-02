//! The [`Scalar`] trait, its `f64` implementation, and the tape-recording
//! [`Var`].

use crate::operand::Operand;
use crate::tape::{CONST_INDEX, with_tape};
use crate::{dist, transform};
use std::fmt;
use std::iter::Sum;
use std::ops::{Add, AddAssign, Div, DivAssign, Mul, MulAssign, Neg, Sub, SubAssign};

/// A real number that a model can be written over: plain `f64` for value-only
/// evaluation, [`Var`] for value plus gradient.
///
/// All fused primitives are trait methods so that generic model code
/// dispatches statically; the free functions in the crate root
/// (`normal_lpdf`, `dot`, ...) are thin wrappers around them.
#[allow(missing_docs)]
pub trait Scalar:
    Copy
    + fmt::Debug
    + PartialOrd
    + PartialEq
    + Add<Output = Self>
    + Sub<Output = Self>
    + Mul<Output = Self>
    + Div<Output = Self>
    + Neg<Output = Self>
    + Add<f64, Output = Self>
    + Sub<f64, Output = Self>
    + Mul<f64, Output = Self>
    + Div<f64, Output = Self>
    + AddAssign
    + SubAssign
    + MulAssign
    + DivAssign
    + AddAssign<f64>
    + SubAssign<f64>
    + MulAssign<f64>
    + DivAssign<f64>
    + Sum<Self>
    + 'static
{
    /// Lift a constant.
    fn from_f64(x: f64) -> Self;
    /// The numeric value.
    fn value(self) -> f64;
    /// Index on the tape (0 for constants and for `f64`). Internal.
    #[doc(hidden)]
    fn tape_index(self) -> u32;
    /// Tape index of `x[0]` when `x` is a sub-slice of the current input
    /// buffer. Internal.
    #[doc(hidden)]
    fn input_slice_start(_x: &[Self], _tape: &crate::Tape) -> Option<u32> {
        None
    }

    /// `numerator / self`.
    fn rdiv(self, numerator: f64) -> Self;
    /// `minuend - self`.
    fn rsub(self, minuend: f64) -> Self;

    fn exp(self) -> Self;
    fn ln(self) -> Self;
    fn sqrt(self) -> Self;
    fn powi(self, n: i32) -> Self;
    fn powf(self, p: f64) -> Self;
    fn tanh(self) -> Self;
    fn log1p(self) -> Self;
    fn expm1(self) -> Self;
    fn abs(self) -> Self;
    /// `self * self` as one node.
    fn square(self) -> Self;
    /// `1 / self`.
    fn recip(self) -> Self;
    /// `ln(1 + exp(self))`, numerically stable.
    fn softplus(self) -> Self;
    /// `1 / (1 + exp(-self))`.
    fn sigmoid(self) -> Self;
    /// True when the value is finite.
    fn is_finite(self) -> bool {
        self.value().is_finite()
    }

    // ---- fused primitives -------------------------------------------------

    fn normal_lpdf<X: Operand<Self>, M: Operand<Self>, G: Operand<Self>>(
        x: X,
        mu: M,
        sigma: G,
    ) -> Self;
    /// Normal log density without the terms that do not depend on parameters
    /// (Stan's `normal_lupdf`): `-0.5 z^2`, plus `-ln sigma` unless `sigma`
    /// is data.
    fn normal_lupdf<X: Operand<Self>, M: Operand<Self>, G: Operand<Self>>(
        x: X,
        mu: M,
        sigma: G,
    ) -> Self;
    fn student_t_lpdf<X: Operand<Self>, M: Operand<Self>, G: Operand<Self>>(
        x: X,
        nu: f64,
        mu: M,
        sigma: G,
    ) -> Self;
    fn cauchy_lpdf<X: Operand<Self>, M: Operand<Self>, G: Operand<Self>>(
        x: X,
        mu: M,
        sigma: G,
    ) -> Self;
    fn lognormal_lpdf<X: Operand<Self>, M: Operand<Self>, G: Operand<Self>>(
        x: X,
        mu: M,
        sigma: G,
    ) -> Self;
    fn exponential_lpdf<X: Operand<Self>, B: Operand<Self>>(x: X, rate: B) -> Self;
    fn gamma_lpdf<X: Operand<Self>, A: Operand<Self>, B: Operand<Self>>(
        x: X,
        shape: A,
        rate: B,
    ) -> Self;
    fn half_normal_lpdf<X: Operand<Self>, G: Operand<Self>>(x: X, sigma: G) -> Self;
    fn bernoulli_logit_lpmf<Y: Operand<Self>, E: Operand<Self>>(y: Y, eta: E) -> Self;
    fn poisson_log_lpmf<Y: Operand<Self>, E: Operand<Self>>(y: Y, log_rate: E) -> Self;
    fn dot<A: Operand<Self>, B: Operand<Self>>(a: A, b: B) -> Self;
    fn sum_all<A: Operand<Self>>(a: A) -> Self;
    fn log_sum_exp<A: Operand<Self>>(a: A) -> Self;
    /// Inclusive cumulative sum of `scale * x[j] + shift`:
    /// `out[i] = sum_{j <= i} (scale * x[j] + shift)`.
    fn cumsum_affine(x: &[Self], scale: f64, shift: f64, out: &mut [Self]);
    /// Inclusive cumulative sum, `out[i] = x[0] + ... + x[i]`.
    fn cumsum(x: &[Self], out: &mut [Self]) {
        Self::cumsum_affine(x, 1.0, 0.0, out)
    }

    // ---- constraining transforms -----------------------------------------

    /// `(exp(y), log |dx/dy|)`: maps the real line to `(0, inf)`.
    fn exp_constrain(self) -> (Self, Self);
    /// `(sigmoid(y), log |dx/dy|)`: maps the real line to `(0, 1)`.
    fn logistic_constrain(self) -> (Self, Self);
    /// Ordered vector: `x[0] = y[0]`, `x[k] = x[k-1] + exp(y[k])`; returns the
    /// log-Jacobian `sum(y[1..])`.
    fn ordered_constrain(y: &[Self], out: &mut [Self]) -> Self;
}

macro_rules! f64_unary {
    ($($name:ident),*) => {
        $( #[inline] fn $name(self) -> Self { f64::$name(self) } )*
    };
}

impl Scalar for f64 {
    #[inline]
    fn from_f64(x: f64) -> Self {
        x
    }
    #[inline]
    fn value(self) -> f64 {
        self
    }
    #[inline]
    fn tape_index(self) -> u32 {
        CONST_INDEX
    }
    #[inline]
    fn rdiv(self, numerator: f64) -> Self {
        numerator / self
    }
    #[inline]
    fn rsub(self, minuend: f64) -> Self {
        minuend - self
    }
    f64_unary!(exp, ln, sqrt, tanh, abs, recip);
    #[inline]
    fn log1p(self) -> Self {
        f64::ln_1p(self)
    }
    #[inline]
    fn expm1(self) -> Self {
        f64::exp_m1(self)
    }
    #[inline]
    fn powi(self, n: i32) -> Self {
        f64::powi(self, n)
    }
    #[inline]
    fn powf(self, p: f64) -> Self {
        f64::powf(self, p)
    }
    #[inline]
    fn square(self) -> Self {
        self * self
    }
    #[inline]
    fn softplus(self) -> Self {
        dist::softplus_f64(self)
    }
    #[inline]
    fn sigmoid(self) -> Self {
        dist::sigmoid_f64(self)
    }

    #[inline]
    fn normal_lpdf<X: Operand<Self>, M: Operand<Self>, G: Operand<Self>>(
        x: X,
        mu: M,
        sigma: G,
    ) -> Self {
        dist::fused3_value(x, mu, sigma, dist::normal_kernel)
    }
    #[inline]
    fn normal_lupdf<X: Operand<Self>, M: Operand<Self>, G: Operand<Self>>(
        x: X,
        mu: M,
        sigma: G,
    ) -> Self {
        if G::IS_DATA {
            dist::fused3_value(x, mu, sigma, dist::normal_lupdf_kernel::<true>)
        } else {
            dist::fused3_value(x, mu, sigma, dist::normal_lupdf_kernel::<false>)
        }
    }
    #[inline]
    fn student_t_lpdf<X: Operand<Self>, M: Operand<Self>, G: Operand<Self>>(
        x: X,
        nu: f64,
        mu: M,
        sigma: G,
    ) -> Self {
        dist::fused3_value(x, mu, sigma, dist::student_t_kernel(nu))
    }
    #[inline]
    fn cauchy_lpdf<X: Operand<Self>, M: Operand<Self>, G: Operand<Self>>(
        x: X,
        mu: M,
        sigma: G,
    ) -> Self {
        dist::fused3_value(x, mu, sigma, dist::cauchy_kernel)
    }
    #[inline]
    fn lognormal_lpdf<X: Operand<Self>, M: Operand<Self>, G: Operand<Self>>(
        x: X,
        mu: M,
        sigma: G,
    ) -> Self {
        dist::fused3_value(x, mu, sigma, dist::lognormal_kernel)
    }
    #[inline]
    fn exponential_lpdf<X: Operand<Self>, B: Operand<Self>>(x: X, rate: B) -> Self {
        dist::fused2_value(x, rate, dist::exponential_kernel)
    }
    #[inline]
    fn gamma_lpdf<X: Operand<Self>, A: Operand<Self>, B: Operand<Self>>(
        x: X,
        shape: A,
        rate: B,
    ) -> Self {
        dist::fused3_value(x, shape, rate, dist::gamma_kernel)
    }
    #[inline]
    fn half_normal_lpdf<X: Operand<Self>, G: Operand<Self>>(x: X, sigma: G) -> Self {
        dist::fused2_value(x, sigma, dist::half_normal_kernel)
    }
    #[inline]
    fn bernoulli_logit_lpmf<Y: Operand<Self>, E: Operand<Self>>(y: Y, eta: E) -> Self {
        dist::fused2_value(y, eta, dist::bernoulli_logit_kernel)
    }
    #[inline]
    fn poisson_log_lpmf<Y: Operand<Self>, E: Operand<Self>>(y: Y, log_rate: E) -> Self {
        dist::fused2_value(y, log_rate, dist::poisson_log_kernel)
    }
    #[inline]
    fn dot<A: Operand<Self>, B: Operand<Self>>(a: A, b: B) -> Self {
        dist::fused2_value(a, b, dist::dot_kernel)
    }
    #[inline]
    fn sum_all<A: Operand<Self>>(a: A) -> Self {
        dist::fused1_value(a, dist::sum_kernel)
    }
    #[inline]
    fn log_sum_exp<A: Operand<Self>>(a: A) -> Self {
        dist::log_sum_exp_value(a)
    }
    #[inline]
    fn cumsum_affine(x: &[Self], scale: f64, shift: f64, out: &mut [Self]) {
        assert_eq!(x.len(), out.len(), "cumsum: output length must match input");
        let mut acc = 0.0;
        for (o, v) in out.iter_mut().zip(x) {
            acc += *v * scale + shift;
            *o = acc;
        }
    }
    #[inline]
    fn exp_constrain(self) -> (Self, Self) {
        (self.exp(), self)
    }
    #[inline]
    fn logistic_constrain(self) -> (Self, Self) {
        transform::logistic_constrain_value(self)
    }
    #[inline]
    fn ordered_constrain(y: &[Self], out: &mut [Self]) -> Self {
        transform::ordered_constrain_value(y, out)
    }
}

/// A scalar recorded on the thread-local tape.
///
/// `Var` is a 16-byte `Copy` handle: the value travels with the handle so
/// arithmetic never reads the tape; only the node is written. Comparisons use
/// the value only.
#[derive(Clone, Copy)]
pub struct Var {
    pub(crate) value: f64,
    pub(crate) index: u32,
}

impl fmt::Debug for Var {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Var({}, #{})", self.value, self.index)
    }
}

impl PartialEq for Var {
    #[inline]
    fn eq(&self, other: &Self) -> bool {
        self.value == other.value
    }
}

impl PartialOrd for Var {
    #[inline]
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        self.value.partial_cmp(&other.value)
    }
}

impl Var {
    /// A constant (never receives a gradient).
    #[inline]
    pub const fn constant(value: f64) -> Self {
        Self {
            value,
            index: CONST_INDEX,
        }
    }

    /// True when this handle is a constant rather than a tape node.
    #[inline]
    pub fn is_constant(self) -> bool {
        self.index == CONST_INDEX
    }

    #[inline]
    pub(crate) fn new(value: f64, index: u32) -> Self {
        Self { value, index }
    }

    #[inline]
    fn unary(self, value: f64, da: f64) -> Self {
        let index = with_tape(|t| t.push_unary(self.index, da));
        Self { value, index }
    }

    #[inline]
    fn binary(self, other: Var, value: f64, da: f64, db: f64) -> Self {
        let index = with_tape(|t| t.push_binary(self.index, other.index, da, db));
        Self { value, index }
    }
}

impl Add for Var {
    type Output = Var;
    #[inline]
    fn add(self, rhs: Var) -> Var {
        self.binary(rhs, self.value + rhs.value, 1.0, 1.0)
    }
}

impl Sub for Var {
    type Output = Var;
    #[inline]
    fn sub(self, rhs: Var) -> Var {
        self.binary(rhs, self.value - rhs.value, 1.0, -1.0)
    }
}

impl Mul for Var {
    type Output = Var;
    #[inline]
    fn mul(self, rhs: Var) -> Var {
        self.binary(rhs, self.value * rhs.value, rhs.value, self.value)
    }
}

impl Div for Var {
    type Output = Var;
    #[inline]
    fn div(self, rhs: Var) -> Var {
        let value = self.value / rhs.value;
        let inv = 1.0 / rhs.value;
        self.binary(rhs, value, inv, -value * inv)
    }
}

impl Neg for Var {
    type Output = Var;
    #[inline]
    fn neg(self) -> Var {
        self.unary(-self.value, -1.0)
    }
}

impl Add<f64> for Var {
    type Output = Var;
    /// Adding a constant reuses the operand's node: `d(x + c)/dx = 1`.
    #[inline]
    fn add(self, rhs: f64) -> Var {
        Var {
            value: self.value + rhs,
            index: self.index,
        }
    }
}

impl Sub<f64> for Var {
    type Output = Var;
    #[inline]
    fn sub(self, rhs: f64) -> Var {
        Var {
            value: self.value - rhs,
            index: self.index,
        }
    }
}

impl Mul<f64> for Var {
    type Output = Var;
    #[inline]
    fn mul(self, rhs: f64) -> Var {
        self.unary(self.value * rhs, rhs)
    }
}

impl Div<f64> for Var {
    type Output = Var;
    #[inline]
    fn div(self, rhs: f64) -> Var {
        self.unary(self.value / rhs, 1.0 / rhs)
    }
}

macro_rules! assign_ops {
    ($($trait:ident $method:ident $op:tt),*) => {
        $(
            impl $trait for Var {
                #[inline]
                fn $method(&mut self, rhs: Var) { *self = *self $op rhs; }
            }
            impl $trait<f64> for Var {
                #[inline]
                fn $method(&mut self, rhs: f64) { *self = *self $op rhs; }
            }
        )*
    };
}
assign_ops!(AddAssign add_assign +, SubAssign sub_assign -, MulAssign mul_assign *, DivAssign div_assign /);

impl Sum for Var {
    /// Sequential accumulation (same rounding order as an `f64` loop).
    fn sum<I: Iterator<Item = Var>>(iter: I) -> Var {
        let mut acc: Option<Var> = None;
        for v in iter {
            acc = Some(match acc {
                None => v,
                Some(a) => a + v,
            });
        }
        acc.unwrap_or(Var::constant(0.0))
    }
}

impl Scalar for Var {
    #[inline]
    fn from_f64(x: f64) -> Self {
        Var::constant(x)
    }
    #[inline]
    fn value(self) -> f64 {
        self.value
    }
    #[inline]
    fn tape_index(self) -> u32 {
        self.index
    }
    #[inline]
    fn input_slice_start(x: &[Self], tape: &crate::Tape) -> Option<u32> {
        tape.input_slice_start(x)
    }
    #[inline]
    fn rdiv(self, numerator: f64) -> Self {
        let value = numerator / self.value;
        self.unary(value, -value / self.value)
    }
    #[inline]
    fn rsub(self, minuend: f64) -> Self {
        self.unary(minuend - self.value, -1.0)
    }
    #[inline]
    fn exp(self) -> Self {
        let e = self.value.exp();
        self.unary(e, e)
    }
    #[inline]
    fn ln(self) -> Self {
        self.unary(self.value.ln(), 1.0 / self.value)
    }
    #[inline]
    fn sqrt(self) -> Self {
        let s = self.value.sqrt();
        self.unary(s, 0.5 / s)
    }
    #[inline]
    fn powi(self, n: i32) -> Self {
        let value = self.value.powi(n);
        self.unary(value, f64::from(n) * self.value.powi(n - 1))
    }
    #[inline]
    fn powf(self, p: f64) -> Self {
        let value = self.value.powf(p);
        self.unary(value, p * self.value.powf(p - 1.0))
    }
    #[inline]
    fn tanh(self) -> Self {
        let t = self.value.tanh();
        self.unary(t, 1.0 - t * t)
    }
    #[inline]
    fn log1p(self) -> Self {
        self.unary(self.value.ln_1p(), 1.0 / (1.0 + self.value))
    }
    #[inline]
    fn expm1(self) -> Self {
        let v = self.value.exp_m1();
        self.unary(v, v + 1.0)
    }
    #[inline]
    fn abs(self) -> Self {
        let sign = if self.value < 0.0 { -1.0 } else { 1.0 };
        self.unary(self.value.abs(), sign)
    }
    #[inline]
    fn square(self) -> Self {
        self.unary(self.value * self.value, 2.0 * self.value)
    }
    #[inline]
    fn recip(self) -> Self {
        let r = 1.0 / self.value;
        self.unary(r, -r * r)
    }
    #[inline]
    fn softplus(self) -> Self {
        self.unary(
            dist::softplus_f64(self.value),
            dist::sigmoid_f64(self.value),
        )
    }
    #[inline]
    fn sigmoid(self) -> Self {
        let s = dist::sigmoid_f64(self.value);
        self.unary(s, s * (1.0 - s))
    }

    #[inline]
    fn normal_lpdf<X: Operand<Self>, M: Operand<Self>, G: Operand<Self>>(
        x: X,
        mu: M,
        sigma: G,
    ) -> Self {
        dist::fused3_var(x, mu, sigma, dist::normal_kernel)
    }
    #[inline]
    fn normal_lupdf<X: Operand<Self>, M: Operand<Self>, G: Operand<Self>>(
        x: X,
        mu: M,
        sigma: G,
    ) -> Self {
        if G::IS_DATA {
            dist::fused3_var(x, mu, sigma, dist::normal_lupdf_kernel::<true>)
        } else {
            dist::fused3_var(x, mu, sigma, dist::normal_lupdf_kernel::<false>)
        }
    }
    #[inline]
    fn student_t_lpdf<X: Operand<Self>, M: Operand<Self>, G: Operand<Self>>(
        x: X,
        nu: f64,
        mu: M,
        sigma: G,
    ) -> Self {
        dist::fused3_var(x, mu, sigma, dist::student_t_kernel(nu))
    }
    #[inline]
    fn cauchy_lpdf<X: Operand<Self>, M: Operand<Self>, G: Operand<Self>>(
        x: X,
        mu: M,
        sigma: G,
    ) -> Self {
        dist::fused3_var(x, mu, sigma, dist::cauchy_kernel)
    }
    #[inline]
    fn lognormal_lpdf<X: Operand<Self>, M: Operand<Self>, G: Operand<Self>>(
        x: X,
        mu: M,
        sigma: G,
    ) -> Self {
        dist::fused3_var(x, mu, sigma, dist::lognormal_kernel)
    }
    #[inline]
    fn exponential_lpdf<X: Operand<Self>, B: Operand<Self>>(x: X, rate: B) -> Self {
        dist::fused2_var(x, rate, dist::exponential_kernel)
    }
    #[inline]
    fn gamma_lpdf<X: Operand<Self>, A: Operand<Self>, B: Operand<Self>>(
        x: X,
        shape: A,
        rate: B,
    ) -> Self {
        dist::fused3_var(x, shape, rate, dist::gamma_kernel)
    }
    #[inline]
    fn half_normal_lpdf<X: Operand<Self>, G: Operand<Self>>(x: X, sigma: G) -> Self {
        dist::fused2_var(x, sigma, dist::half_normal_kernel)
    }
    #[inline]
    fn bernoulli_logit_lpmf<Y: Operand<Self>, E: Operand<Self>>(y: Y, eta: E) -> Self {
        dist::fused2_var(y, eta, dist::bernoulli_logit_kernel)
    }
    #[inline]
    fn poisson_log_lpmf<Y: Operand<Self>, E: Operand<Self>>(y: Y, log_rate: E) -> Self {
        dist::fused2_var(y, log_rate, dist::poisson_log_kernel)
    }
    #[inline]
    fn dot<A: Operand<Self>, B: Operand<Self>>(a: A, b: B) -> Self {
        dist::fused2_var(a, b, dist::dot_kernel)
    }
    #[inline]
    fn sum_all<A: Operand<Self>>(a: A) -> Self {
        dist::fused1_var(a, dist::sum_kernel)
    }
    #[inline]
    fn log_sum_exp<A: Operand<Self>>(a: A) -> Self {
        dist::log_sum_exp_var(a)
    }
    #[inline]
    fn cumsum_affine(x: &[Self], scale: f64, shift: f64, out: &mut [Self]) {
        assert_eq!(x.len(), out.len(), "cumsum: output length must match input");
        if x.is_empty() {
            return;
        }
        with_tape(|t| {
            if let crate::VectorPart::Contiguous(first) = crate::operand::slice_part(x, t) {
                // One block node: the outputs occupy consecutive tape indices
                // and the reverse sweep is a single reverse scan.
                let start = t.push_cumsum(first, x.len(), scale);
                let mut acc = 0.0;
                for (i, (o, v)) in out.iter_mut().zip(x).enumerate() {
                    acc += v.value * scale + shift;
                    *o = Var::new(acc, start + i as u32);
                }
            } else {
                // Scattered inputs: a chain of binary nodes (still O(n)); the
                // first output is an identity node so the outputs are
                // contiguous for downstream operands.
                out[0] = Var::new(x[0].value * scale + shift, t.push_unary(x[0].index, scale));
                for i in 1..x.len() {
                    let prev = out[i - 1];
                    let index = t.push_binary(prev.index, x[i].index, 1.0, scale);
                    out[i] = Var::new(prev.value + (x[i].value * scale + shift), index);
                }
            }
        });
    }
    #[inline]
    fn exp_constrain(self) -> (Self, Self) {
        (self.exp(), self)
    }
    #[inline]
    fn logistic_constrain(self) -> (Self, Self) {
        transform::logistic_constrain_var(self)
    }
    #[inline]
    fn ordered_constrain(y: &[Self], out: &mut [Self]) -> Self {
        transform::ordered_constrain_var(y, out)
    }
}
