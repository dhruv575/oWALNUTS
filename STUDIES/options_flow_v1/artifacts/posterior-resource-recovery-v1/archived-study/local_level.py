"""Independent normalized optionsWALNUTS local-level application target.

Canonical layout is [h_0,...,h_(T-1),log_sigma_obs,log_sigma_rw].
The application uses anchor=y[0] and unit time steps: an empirical-Bayes
conditional target, not the exogenous-anchor generative model used for SBC.
No provider data or application code is imported by this module.
"""
from __future__ import annotations

import numpy as np
from scipy.special import gammaln


def validate(data):
    y = np.asarray(data['y'], dtype=float)
    if y.ndim != 1 or y.size < 1 or not np.isfinite(y).all():
        raise ValueError('y must be a nonempty finite vector of log prices')
    dt = np.asarray(data.get('dt', np.ones(len(y)-1)), dtype=float)
    if dt.shape != (len(y)-1,) or not np.isfinite(dt).all() or (dt <= 0).any():
        raise ValueError('dt must contain T-1 finite positive trading-time increments')
    if not np.isfinite(data['anchor']) or data.get('nu', 5.) != 5.:
        raise ValueError('Require a finite explicit anchor and Student-t nu=5')
    mode = data.get('anchor_mode')
    if mode not in ('exogenous', 'empirical_bayes_first_observation'):
        raise ValueError('Explicit anchor_mode is required')
    if mode == 'empirical_bayes_first_observation' and data['anchor'] != y[0]:
        raise ValueError('Application empirical-Bayes anchor must equal first log price')
    return y, dt


def application_data(log_prices):
    """Exact application target convention, unsuitable for ordinary SBC."""
    y = np.asarray(log_prices, dtype=float)
    if y.ndim != 1 or not len(y):
        raise ValueError('Need nonempty log prices')
    data = dict(y=y.tolist(), anchor=float(y[0]),
                anchor_mode='empirical_bayes_first_observation',
                dt=np.ones(len(y)-1).tolist(), nu=5.)
    validate(data)
    return data


def canonicalize(q, data, parameterization='centered', xp=np):
    if parameterization == 'centered':
        return xp.asarray(q)
    if parameterization != 'noncentered':
        raise ValueError('Unknown parameterization')
    q = xp.asarray(q)
    t = len(data['y'])
    dt = xp.asarray(data.get('dt', np.ones(t-1)))
    first = data['anchor'] + 1.5*q[..., :1]
    increments = xp.exp(q[..., -1:])*xp.sqrt(dt)*q[..., 1:t]
    h = xp.concatenate((first, first+xp.cumsum(increments, axis=-1)), axis=-1)
    return xp.concatenate((h, q[..., -2:]), axis=-1)


def noncenter(q, data):
    q = np.asarray(q, dtype=float)
    t = len(data['y'])
    dt = np.asarray(data.get('dt', np.ones(t-1)))
    z0 = (q[..., :1]-data['anchor'])/1.5
    z = np.diff(q[..., :t], axis=-1)/(np.exp(q[..., -1:])*np.sqrt(dt))
    return np.concatenate((z0, z, q[..., -2:]), axis=-1)


def log_density(q, data, xp=np, gamma=gammaln, parameterization='centered'):
    """Fully normalized density in the selected coordinates; JAX-compatible."""
    q = xp.asarray(q)
    t = len(data['y'])
    if q.ndim != 1 or q.shape[0] != t+2:
        raise ValueError('Position dimension must equal T+2')
    c = canonicalize(q, data, parameterization, xp)
    h, lo, lr = c[:t], c[-2], c[-1]
    y = xp.asarray(data['y'])
    dt = xp.asarray(data.get('dt', np.ones(t-1)))
    def normal(v, mean, sd):
        return xp.sum(-.5*((v-mean)/sd)**2-xp.log(sd)-.5*xp.log(2*xp.pi))
    lp = normal(lo, np.log(.08), 1.) + normal(lr, np.log(.12), 1.)
    if parameterization == 'centered':
        lp += normal(h[0], data['anchor'], 1.5)
        lp += normal(h[1:], h[:-1], xp.exp(lr)*xp.sqrt(dt))
    else:
        # Transition normalizers cancel exactly against the change-of-variable
        # determinant; priors are directly on log scales, not on positive scales.
        lp += normal(q[:t], 0., 1.)
    nu = 5.
    residual = (y-h)/xp.exp(lo)
    lp += xp.sum(gamma((nu+1)/2)-gamma(nu/2)-.5*xp.log(nu*xp.pi)
                 -lo-(nu+1)/2*xp.log1p(residual**2/nu))
    return lp


def simulate(seed, periods=80, holdout=20, prior=True, anchor=0.):
    """Proper prior generative fixture with an externally fixed initial anchor."""
    if periods < 1 or holdout < 0 or not np.isfinite(anchor):
        raise ValueError('Invalid simulation size or anchor')
    rng = np.random.default_rng(seed)
    logs = rng.normal(np.log([.08, .12]), 1.) if prior else np.log([.08, .12])
    h = np.empty(periods+holdout)
    h[0] = rng.normal(anchor, 1.5)
    h[1:] = h[0]+np.cumsum(rng.normal(0., np.exp(logs[1]), len(h)-1))
    y = h + np.exp(logs[0])*rng.standard_t(5., len(h))
    data = dict(y=y[:periods].tolist(), anchor=float(anchor), anchor_mode='exogenous',
                dt=np.ones(periods-1).tolist(), nu=5.)
    return dict(data=data, truth=np.r_[h[:periods], logs].tolist(), seed=seed,
                prior_predictive=bool(prior), source='synthetic_local_level',
                holdout=dict(y=y[periods:].tolist(), latent=h[periods:].tolist()),
                forecast_contract='Fixed-origin future trading-time increments; no holdout conditioning')


def predict(draws, data, horizons, seed):
    """Joint future latent and observed log/price draws at elapsed trading times.

Input is canonical posterior draws (..., T+2). A shared Brownian path gives
correct cross-horizon dependence. Observation noise is independent Student-t(5).
Price means need not exist under exponentiated Student-t noise; use quantiles.
"""
    validate(data)
    q = np.asarray(draws, float)
    times = np.asarray(horizons, float)
    if q.ndim < 2 or q.shape[-1] != len(data['y'])+2 or not np.isfinite(q).all():
        raise ValueError('Require finite canonical posterior draws')
    if times.ndim != 1 or not len(times) or not np.isfinite(times).all() or (np.diff(np.r_[0.,times]) <= 0).any():
        raise ValueError('Horizons must be strictly increasing positive elapsed trading times')
    rng = np.random.default_rng(seed)
    shape = q.shape[:-1]+(len(times),)
    increments = rng.normal(size=shape)*np.sqrt(np.diff(np.r_[0.,times]))
    latent = q[..., -3, None]+np.exp(q[..., -1, None])*np.cumsum(increments, axis=-1)
    observed = latent+np.exp(q[..., -2, None])*rng.standard_t(5., size=shape)
    with np.errstate(over='ignore'):
        return dict(latent_log=latent, observed_log=observed,
                    latent_price=np.exp(latent), observed_price=np.exp(observed))


def functionals(draws):
    """Canonical posterior functionals; retain full coordinates for health gates."""
    q = np.asarray(draws, dtype=float)
    return dict(h_terminal=q[..., -3], h_initial=q[..., 0],
                h_mean=q[..., :-2].mean(axis=-1),
                sigma_obs=np.exp(q[..., -2]), sigma_rw=np.exp(q[..., -1]))
