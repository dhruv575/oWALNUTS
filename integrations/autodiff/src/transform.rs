//! Constraining transforms with their log-Jacobians.

use crate::Var;
use crate::dist::{sigmoid_f64, softplus_f64};
use crate::tape::with_tape;

/// `(sigmoid(y), ln sigmoid(y) + ln (1 - sigmoid(y)))`.
#[inline]
pub(crate) fn logistic_constrain_value(y: f64) -> (f64, f64) {
    (sigmoid_f64(y), -softplus_f64(-y) - softplus_f64(y))
}

#[inline]
pub(crate) fn logistic_constrain_var(y: Var) -> (Var, Var) {
    let (x, lj) = logistic_constrain_value(y.value);
    let (ix, ilj) = with_tape(|t| {
        let ix = t.push_unary(y.index, x * (1.0 - x));
        let ilj = t.push_unary(y.index, 1.0 - 2.0 * x);
        (ix, ilj)
    });
    (Var::new(x, ix), Var::new(lj, ilj))
}

/// `x[0] = y[0]`, `x[k] = x[k-1] + exp(y[k])`; returns `sum(y[1..])`.
pub(crate) fn ordered_constrain_value(y: &[f64], out: &mut [f64]) -> f64 {
    assert_eq!(y.len(), out.len(), "ordered_constrain: length mismatch");
    if y.is_empty() {
        return 0.0;
    }
    out[0] = y[0];
    let mut log_jac = 0.0;
    for k in 1..y.len() {
        out[k] = out[k - 1] + y[k].exp();
        log_jac += y[k];
    }
    log_jac
}

pub(crate) fn ordered_constrain_var(y: &[Var], out: &mut [Var]) -> Var {
    assert_eq!(y.len(), out.len(), "ordered_constrain: length mismatch");
    if y.is_empty() {
        return Var::constant(0.0);
    }
    out[0] = y[0];
    with_tape(|t| {
        for k in 1..y.len() {
            let e = y[k].value.exp();
            let prev = out[k - 1];
            let index = t.push_binary(prev.index, y[k].index, 1.0, e);
            out[k] = Var::new(prev.value + e, index);
        }
    });
    crate::dist::fused1_var(&y[1..], crate::dist::sum_kernel)
}
