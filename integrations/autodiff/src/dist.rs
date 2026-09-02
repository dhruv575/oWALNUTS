//! Fused log-density primitives.
//!
//! Each primitive is an elementwise *kernel* returning the value and the
//! partial derivatives with respect to its operands, plus two drivers:
//! `fusedN_value` (plain `f64`, partials are dead code and eliminated) and
//! `fusedN_var` (records one tape node for the whole broadcast sum). The same
//! kernel serves both, so value-only and gradient evaluation are bit-identical.

use crate::Var;
use crate::operand::{Operand, broadcast_len};
use crate::tape::{Slot, Tape, with_tape};

pub(crate) const LOG_2PI: f64 = 1.837_877_066_409_345_3;
const HALF_LOG_2PI: f64 = 0.5 * LOG_2PI;
const LOG_PI: f64 = 1.144_729_885_849_400_2;
/// `0.5 * ln(2 / pi)`.
const HALF_LOG_2_OVER_PI: f64 = -0.225_791_352_644_727_4;

/// Numerically stable `ln(1 + exp(x))`.
#[inline]
pub fn softplus_f64(x: f64) -> f64 {
    if x > 0.0 {
        x + (-x).exp().ln_1p()
    } else {
        x.exp().ln_1p()
    }
}

/// Numerically stable logistic function.
#[inline]
pub fn sigmoid_f64(x: f64) -> f64 {
    if x >= 0.0 {
        1.0 / (1.0 + (-x).exp())
    } else {
        let e = x.exp();
        e / (1.0 + e)
    }
}

/// `ln Gamma(x)`.
#[inline]
pub fn lgamma_f64(x: f64) -> f64 {
    libm::lgamma(x)
}

/// Digamma function `d/dx ln Gamma(x)` (recurrence to `x >= 6` then the
/// asymptotic series; absolute error below 1e-12 for `x > 0`).
pub fn digamma_f64(mut x: f64) -> f64 {
    if x <= 0.0 && x == x.floor() {
        return f64::NAN;
    }
    let mut result = 0.0;
    if x < 0.0 {
        // Reflection: psi(1 - x) - psi(x) = pi cot(pi x).
        let pi_x = std::f64::consts::PI * x;
        result -= std::f64::consts::PI / pi_x.tan();
        x = 1.0 - x;
    }
    while x < 6.0 {
        result -= 1.0 / x;
        x += 1.0;
    }
    let inv = 1.0 / x;
    let inv2 = inv * inv;
    result += x.ln()
        - 0.5 * inv
        - inv2
            * (1.0 / 12.0
                - inv2
                    * (1.0 / 120.0
                        - inv2 * (1.0 / 252.0 - inv2 * (1.0 / 240.0 - inv2 * (1.0 / 132.0)))));
    result
}

// ---- kernels ---------------------------------------------------------------
//
// A 3-operand kernel returns (value, d/da, d/db, d/dc); a 2-operand kernel
// (value, d/da, d/db); a 1-operand kernel (value, d/da).

/// Normal: `-0.5 ln 2pi - ln sigma - 0.5 ((x - mu)/sigma)^2`.
#[inline]
pub(crate) fn normal_kernel(x: f64, mu: f64, sigma: f64) -> (f64, f64, f64, f64) {
    let z = (x - mu) / sigma;
    let inv = 1.0 / sigma;
    let value = -HALF_LOG_2PI - sigma.ln() - 0.5 * z * z;
    let dx = -z * inv;
    (value, dx, -dx, (z * z - 1.0) * inv)
}

/// Normal without parameter-independent terms; `SIGMA_DATA` also drops
/// `-ln sigma`.
#[inline]
pub(crate) fn normal_lupdf_kernel<const SIGMA_DATA: bool>(
    x: f64,
    mu: f64,
    sigma: f64,
) -> (f64, f64, f64, f64) {
    let inv = 1.0 / sigma;
    let z = (x - mu) * inv;
    let value = if SIGMA_DATA {
        -0.5 * z * z
    } else {
        -sigma.ln() - 0.5 * z * z
    };
    let dx = -z * inv;
    (value, dx, -dx, (z * z - 1.0) * inv)
}

/// Student-t with fixed degrees of freedom `nu`.
#[inline]
pub(crate) fn student_t_kernel(nu: f64) -> impl Fn(f64, f64, f64) -> (f64, f64, f64, f64) {
    let c = lgamma_f64(0.5 * (nu + 1.0))
        - lgamma_f64(0.5 * nu)
        - 0.5 * (nu * std::f64::consts::PI).ln();
    let half_nu_p1 = 0.5 * (nu + 1.0);
    move |x, mu, sigma| {
        let inv = 1.0 / sigma;
        let z = (x - mu) * inv;
        let z2 = z * z;
        let value = c - sigma.ln() - half_nu_p1 * (z2 / nu).ln_1p();
        let dz = -(nu + 1.0) * z / (nu + z2);
        (value, dz * inv, -dz * inv, -inv - dz * z * inv)
    }
}

/// Cauchy: `-ln pi - ln sigma - ln(1 + z^2)`.
#[inline]
pub(crate) fn cauchy_kernel(x: f64, mu: f64, sigma: f64) -> (f64, f64, f64, f64) {
    let inv = 1.0 / sigma;
    let z = (x - mu) * inv;
    let z2 = z * z;
    let value = -LOG_PI - sigma.ln() - z2.ln_1p();
    let dz = -2.0 * z / (1.0 + z2);
    (value, dz * inv, -dz * inv, -inv - dz * z * inv)
}

/// Log-normal on `x > 0`.
#[inline]
pub(crate) fn lognormal_kernel(x: f64, mu: f64, sigma: f64) -> (f64, f64, f64, f64) {
    let lx = x.ln();
    let inv = 1.0 / sigma;
    let z = (lx - mu) * inv;
    let value = -HALF_LOG_2PI - sigma.ln() - lx - 0.5 * z * z;
    let dlx = -z * inv;
    (value, (dlx - 1.0) / x, -dlx, (z * z - 1.0) * inv)
}

/// Exponential with rate `beta`: `ln beta - beta x`.
#[inline]
pub(crate) fn exponential_kernel(x: f64, beta: f64) -> (f64, f64, f64) {
    (beta.ln() - beta * x, -beta, 1.0 / beta - x)
}

/// Gamma with shape `alpha` and rate `beta`.
#[inline]
pub(crate) fn gamma_kernel(x: f64, alpha: f64, beta: f64) -> (f64, f64, f64, f64) {
    let lx = x.ln();
    let lb = beta.ln();
    let value = alpha * lb - lgamma_f64(alpha) + (alpha - 1.0) * lx - beta * x;
    (
        value,
        (alpha - 1.0) / x - beta,
        lb - digamma_f64(alpha) + lx,
        alpha / beta - x,
    )
}

/// Half-normal on `x >= 0`: `0.5 ln(2/pi) - ln sigma - 0.5 (x/sigma)^2`.
#[inline]
pub(crate) fn half_normal_kernel(x: f64, sigma: f64) -> (f64, f64, f64) {
    let inv = 1.0 / sigma;
    let z = x * inv;
    (
        HALF_LOG_2_OVER_PI - sigma.ln() - 0.5 * z * z,
        -z * inv,
        (z * z - 1.0) * inv,
    )
}

/// Bernoulli with logit `eta`: `y eta - softplus(eta)`.
#[inline]
pub(crate) fn bernoulli_logit_kernel(y: f64, eta: f64) -> (f64, f64, f64) {
    (y * eta - softplus_f64(eta), eta, y - sigmoid_f64(eta))
}

/// Poisson with log rate: `y l - exp(l) - ln Gamma(y + 1)`.
#[inline]
pub(crate) fn poisson_log_kernel(y: f64, log_rate: f64) -> (f64, f64, f64) {
    let rate = log_rate.exp();
    (
        y * log_rate - rate - lgamma_f64(y + 1.0),
        log_rate - digamma_f64(y + 1.0),
        y - rate,
    )
}

#[inline]
pub(crate) fn dot_kernel(a: f64, b: f64) -> (f64, f64, f64) {
    (a * b, b, a)
}

#[inline]
pub(crate) fn sum_kernel(a: f64) -> (f64, f64) {
    (a, 1.0)
}

// ---- value drivers ---------------------------------------------------------

#[inline]
pub(crate) fn fused1_value<A: Operand<f64>>(a: A, f: impl Fn(f64) -> (f64, f64)) -> f64 {
    let n = broadcast_len(&[a.len()]);
    let mut total = 0.0;
    for i in 0..n {
        total += f(a.value(i)).0;
    }
    total
}

#[inline]
pub(crate) fn fused2_value<A: Operand<f64>, B: Operand<f64>>(
    a: A,
    b: B,
    f: impl Fn(f64, f64) -> (f64, f64, f64),
) -> f64 {
    let n = broadcast_len(&[a.len(), b.len()]);
    let mut total = 0.0;
    for i in 0..n {
        total += f(a.value(i), b.value(i)).0;
    }
    total
}

#[inline]
pub(crate) fn fused3_value<A: Operand<f64>, B: Operand<f64>, C: Operand<f64>>(
    a: A,
    b: B,
    c: C,
    f: impl Fn(f64, f64, f64) -> (f64, f64, f64, f64),
) -> f64 {
    let n = broadcast_len(&[a.len(), b.len(), c.len()]);
    if n == 1 {
        return f(a.value(0), b.value(0), c.value(0)).0;
    }
    let mut total = 0.0;
    for i in 0..n {
        total += f(a.value(i), b.value(i), c.value(i)).0;
    }
    total
}

pub(crate) fn log_sum_exp_value<A: Operand<f64>>(a: A) -> f64 {
    let n = broadcast_len(&[a.len()]);
    let mut m = f64::NEG_INFINITY;
    for i in 0..n {
        m = m.max(a.value(i));
    }
    if !m.is_finite() {
        return m;
    }
    let mut s = 0.0;
    for i in 0..n {
        s += (a.value(i) - m).exp();
    }
    m + s.ln()
}

// ---- tape drivers ----------------------------------------------------------
//
// Each operand gets one segment (see `Tape`): vector operands write one
// partial per element into their slot; scalar parents (a broadcast `Var`, or
// the slope and intercept of a `Linear`) accumulate across the loop and are
// recorded once at the end.

/// Store element `i`'s partial `d` for operand `o`.
#[inline(always)]
fn record<O: Operand<Var>>(o: &O, slot: &mut Slot<'_>, i: usize, d: f64, acc: &mut [f64; 2]) {
    match slot {
        Slot::Skip => {}
        Slot::Contiguous(p) => p[i] = d * o.chain(i),
        Slot::Indexed(p, idx) => {
            p[i] = d * o.chain(i);
            idx[i] = o.index(i);
        }
    }
    if O::SCALAR_PARENTS >= 1 {
        acc[0] += d * o.scalar_weight(0, i);
    }
    if O::SCALAR_PARENTS >= 2 {
        acc[1] += d * o.scalar_weight(1, i);
    }
}

/// Record the accumulated scalar-parent partials of operand `o`.
#[inline(always)]
fn finish<O: Operand<Var>>(o: &O, t: &mut Tape, acc: [f64; 2]) {
    for (k, partial) in acc.iter().enumerate().take(O::SCALAR_PARENTS) {
        t.single_parent(o.scalar_parent(k), *partial);
    }
}

#[inline]
pub(crate) fn fused1_var<A: Operand<Var>>(a: A, f: impl Fn(f64) -> (f64, f64)) -> Var {
    let n = broadcast_len(&[a.len()]);
    if n == 1 && A::SIMPLE {
        let (v, da) = f(a.value(0));
        let index = with_tape(|t| t.push_unary(a.index(0), da));
        return Var::new(v, index);
    }
    with_tape(|t| {
        let parts = [a.vector_part(t)];
        let begin = t.nary_begin();
        let mut total = 0.0;
        let mut acc_a = [0.0; 2];
        {
            let [mut sa] = t.open_segments(parts, n);
            for i in 0..n {
                let (v, da) = f(a.value(i));
                total += v;
                record(&a, &mut sa, i, da, &mut acc_a);
            }
        }
        finish(&a, t, acc_a);
        Var::new(total, t.push_nary(begin))
    })
}

#[inline]
pub(crate) fn fused2_var<A: Operand<Var>, B: Operand<Var>>(
    a: A,
    b: B,
    f: impl Fn(f64, f64) -> (f64, f64, f64),
) -> Var {
    let n = broadcast_len(&[a.len(), b.len()]);
    if n == 1 && A::SIMPLE && B::SIMPLE {
        let (v, da, db) = f(a.value(0), b.value(0));
        let index = with_tape(|t| t.push_binary(a.index(0), b.index(0), da, db));
        return Var::new(v, index);
    }
    with_tape(|t| {
        let parts = [a.vector_part(t), b.vector_part(t)];
        let begin = t.nary_begin();
        let mut total = 0.0;
        let mut acc_a = [0.0; 2];
        let mut acc_b = [0.0; 2];
        {
            let [mut sa, mut sb] = t.open_segments(parts, n);
            for i in 0..n {
                let (v, da, db) = f(a.value(i), b.value(i));
                total += v;
                record(&a, &mut sa, i, da, &mut acc_a);
                record(&b, &mut sb, i, db, &mut acc_b);
            }
        }
        finish(&a, t, acc_a);
        finish(&b, t, acc_b);
        Var::new(total, t.push_nary(begin))
    })
}

#[inline]
pub(crate) fn fused3_var<A: Operand<Var>, B: Operand<Var>, C: Operand<Var>>(
    a: A,
    b: B,
    c: C,
    f: impl Fn(f64, f64, f64) -> (f64, f64, f64, f64),
) -> Var {
    let n = broadcast_len(&[a.len(), b.len(), c.len()]);
    if n == 1 && A::SIMPLE && B::SIMPLE && C::SIMPLE {
        let (v, da, db, dc) = f(a.value(0), b.value(0), c.value(0));
        let index = with_tape(|t| t.push_ternary(a.index(0), b.index(0), c.index(0), da, db, dc));
        return Var::new(v, index);
    }
    with_tape(|t| {
        let parts = [a.vector_part(t), b.vector_part(t), c.vector_part(t)];
        let begin = t.nary_begin();
        let mut total = 0.0;
        let mut acc_a = [0.0; 2];
        let mut acc_b = [0.0; 2];
        let mut acc_c = [0.0; 2];
        {
            let [mut sa, mut sb, mut sc] = t.open_segments(parts, n);
            for i in 0..n {
                let (v, da, db, dc) = f(a.value(i), b.value(i), c.value(i));
                total += v;
                record(&a, &mut sa, i, da, &mut acc_a);
                record(&b, &mut sb, i, db, &mut acc_b);
                record(&c, &mut sc, i, dc, &mut acc_c);
            }
        }
        finish(&a, t, acc_a);
        finish(&b, t, acc_b);
        finish(&c, t, acc_c);
        Var::new(total, t.push_nary(begin))
    })
}

pub(crate) fn log_sum_exp_var<A: Operand<Var>>(a: A) -> Var {
    let n = broadcast_len(&[a.len()]);
    let mut m = f64::NEG_INFINITY;
    for i in 0..n {
        m = m.max(a.value(i));
    }
    if !m.is_finite() {
        return Var::constant(m);
    }
    let mut s = 0.0;
    for i in 0..n {
        s += (a.value(i) - m).exp();
    }
    let value = m + s.ln();
    with_tape(|t| {
        let parts = [a.vector_part(t)];
        let begin = t.nary_begin();
        let mut acc = [0.0; 2];
        {
            let [mut sa] = t.open_segments(parts, n);
            for i in 0..n {
                record(&a, &mut sa, i, (a.value(i) - value).exp(), &mut acc);
            }
        }
        finish(&a, t, acc);
        Var::new(value, t.push_nary(begin))
    })
}
