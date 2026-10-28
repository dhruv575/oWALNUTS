"""Conditional finite-cell likelihood kernel; not an admitted market model."""
import numpy as np
from scipy.special import expit, gammaln


def kernel(u, lower, upper, initial, beta, h):
    """Return log joint observation/augmentation kernel and its u gradient.

    Includes transition normalization constants; integrates to the cell event
    probability, not one. It is not a normalized conditional posterior in u.
    """
    u, lower, upper, h = [np.asarray(v, dtype=float) for v in (u, lower, upper, h)]
    if u.ndim != 1 or not len(u) or any(v.shape != u.shape for v in (lower, upper, h)):
        raise ValueError('Matching nonempty vectors required')
    if not all(np.isfinite(v).all() for v in (u, lower, upper, h)) or not np.isfinite([initial, beta]).all():
        raise ValueError('Finite inputs required')
    width = upper-lower
    if np.any(width <= 0) or not np.isfinite(width).all():
        raise ValueError('Finite positive cell widths required')
    s = expit(u)
    x = lower+width*s
    residual = np.diff(np.r_[initial, x])-beta
    # logaddexp avoids overflow in exp(h) and residual squared / exp(h).
    with np.errstate(divide='ignore'):
        log_abs = np.log(np.abs(residual))
    log_denom = np.logaddexp(np.log(5.)+h, 2*log_abs)
    log_ratio = np.logaddexp(0., 2*log_abs-np.log(5.)-h)
    log_f = gammaln(3.)-gammaln(2.5)-.5*np.log(5*np.pi)-.5*h-3*log_ratio
    log_jac = np.log(width)-np.logaddexp(0., -u)-np.logaddexp(0., u)
    g = -6*np.sign(residual)*np.exp(log_abs-log_denom)
    gx = g-np.r_[g[1:], 0.]
    # Compute logistic derivative without the cancellation in 1-expit(u).
    ds = np.exp(-np.logaddexp(0., -u)-np.logaddexp(0., u))
    grad = gx*width*ds+1-2*s
    return float(np.sum(log_f+log_jac)), grad
