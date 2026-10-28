"""Development centered/noncentered interweaving for the no-flow SV target.

Reuses the augmented Gibbs/elliptical/slice sweep, then updates mu and log_sigma
conditional on the physical latent path. Not yet a benchmarked comparator.
"""
import math
import numpy as np
from hybrid import EvaluationBudget, scalar_slice, sweep


def admit(model):
    if model.k != 0 or model.p != 1 or not np.all(model.x == 1):
        raise ValueError('Interweaving currently supports intercept-only, no-flow SV')


def centered_mu_conditional(model, h, log_sigma):
    admit(model)
    h = np.asarray(h, dtype=float)
    if h.shape != (model.t,) or not np.isfinite(h).all():
        raise ValueError('Finite complete latent path required')
    inverse_variance = math.exp(-2*log_sigma)
    rho, prior = model.rho, model.priors
    precision = 1/prior.mu_sd**2 + inverse_variance*((1-rho*rho)+(model.t-1)*(1-rho)**2)
    numerator = prior.mu_mean/prior.mu_sd**2 + inverse_variance*((1-rho*rho)*h[0]+(1-rho)*np.sum(h[1:]-rho*h[:-1]))
    return float(numerator/precision), float(1/math.sqrt(precision))


def centered_scale_log_density(model, h, mu, log_sigma):
    rho, prior = model.rho, model.priors
    residual = h[1:]-mu-rho*(h[:-1]-mu)
    ss = (1-rho*rho)*(h[0]-mu)**2+float(residual@residual)
    value = -model.t*log_sigma-.5*math.exp(-2*log_sigma)*ss-.5*((log_sigma-prior.log_sigma_mean)/prior.log_sigma_sd)**2
    if not math.isfinite(value):
        raise FloatingPointError('Nonfinite centered scale conditional')
    return value


def centered_update(model, q, rng, budget):
    admit(model)
    q = np.asarray(q, dtype=float).copy()
    h = model.path(q)
    mean, sd = centered_mu_conditional(model, h, q[1])
    q[0] = rng.normal(mean, sd)
    q[1] = scalar_slice(q[1], lambda ls: budget.evaluate('centered_scale', lambda value: centered_scale_log_density(model, h, q[0], value), ls), rng, width=model.priors.log_sigma_sd)
    sigma = math.exp(q[1])
    q[model.offset] = math.sqrt(1-model.rho**2)*(h[0]-q[0])/sigma
    q[model.offset+1:] = (h[1:]-q[0]-model.rho*(h[:-1]-q[0]))/sigma
    if not np.isfinite(q).all():
        raise FloatingPointError('Nonfinite remapped centered update')
    return q


def sweep_interwoven(model, q, rng, *, budget=None):
    admit(model)
    budget = EvaluationBudget() if budget is None else budget
    q, lam = sweep(model, q, rng, budget=budget)
    return centered_update(model, q, rng, budget), lam
