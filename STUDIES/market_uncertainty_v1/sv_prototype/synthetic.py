"""Synthetic native-log-return controls, not priors calibrated to a market.

Covariates are a deterministic, bounded, pre-outcome forcing schedule. They are
not a model for endogenous option flow. Every prior draw is retained, including
numerical failures; diagnostics never rescale, clip or discard extreme returns.
"""
from dataclasses import asdict
import math
import numpy as np
try:
    from .target import Priors, Target
except ImportError:
    from target import Priors, Target

ABLATIONS = ('neither', 'mean', 'scale', 'both')
# Prospective illustrative units: log-return, one scheduled 30-minute step.
# Median observation scale is .005, not observation SD (Student-t nu=5).
# These choices are assumptions for diagnosis, NOT empirical market estimates.
ILLUSTRATIVE_PRIORS = Priors(2*math.log(.005), 1., math.log(.2), .5, .002, .03)


def covariates(periods, ablation):
    if type(periods) is not int or periods < 1 or ablation not in ABLATIONS:
        raise ValueError('Positive periods and named ablation required')
    i = np.arange(periods, dtype=float)
    flow = np.sin(2*np.pi*i/17)
    activity = np.cos(2*np.pi*i/29)
    x = np.column_stack([np.ones(periods), flow]) if ablation in ('mean', 'both') else np.ones((periods, 1))
    w = np.column_stack([activity, flow]) if ablation in ('scale', 'both') else np.empty((periods, 0))
    return x, w


def simulate(periods, seed, ablation, *, priors, rho=.9, nu=5., observed=None):
    """Generate one exact prior draw; fixed mask does not change latent draws.

    Truth lives separately from data. Shared seed across ablations shares global,
    path and observation randomness through independent role-specific streams.
    Scale flow is known even when the corresponding return is unobserved.
    """
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError('uint32 seed required')
    x, w = covariates(periods, ablation)
    mask = np.ones(periods, dtype=bool) if observed is None else np.asarray(observed)
    template = Target(np.zeros(periods), x, w, mask, rho=rho, nu=nu, priors=priors)
    streams = [np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(5)]
    mu = streams[0].normal(priors.mu_mean, priors.mu_sd)
    logsigma = streams[0].normal(priors.log_sigma_mean, priors.log_sigma_sd)
    beta_full = streams[1].normal(0, priors.beta_sd, 2)
    gamma_full = streams[2].normal(0, priors.gamma_sd, 2)
    beta, gamma = beta_full[:template.p], gamma_full[:template.k]
    z = streams[3].normal(size=periods)
    q = np.r_[mu, logsigma, beta, gamma, z]
    # Deliberately independent of Target.path, including its initial mean.
    sigma = np.exp(logsigma)
    h = np.empty(periods)
    h[0] = mu+w[0]@gamma+sigma*z[0]/np.sqrt(1-rho*rho)
    for t in range(1, periods):
        h[t] = mu+rho*(h[t-1]-mu)+w[t]@gamma+sigma*z[t]
    with np.errstate(over='ignore', invalid='ignore'):
        y = x@beta+np.exp(h/2)*streams[4].standard_t(nu, size=periods)
    return dict(schema='synthetic-native-return-sv-v1', ablation=ablation, seed=seed,
                units='30-minute log return; no outcome standardization', priors=asdict(priors),
                data=dict(y=np.where(mask, y, np.nan), x=x, w=w, observed=mask.copy(), rho=rho, nu=nu),
                truth=dict(q=q, h=h, y_complete=y))


def prior_predictive(periods, seeds, ablation, *, priors, rho=.9, nu=5.):
    """Finite-value quantiles are explicitly conditional; failures stay counted.

    Absolute log-return thresholds .01/.05/.20 are diagnostics, not acceptance
    gates. Large values should motivate prior review before fitting real data.
    """
    seeds = list(seeds)
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError('Nonempty distinct seeds required')
    values, hvalues, failures = [], [], []
    for seed in seeds:
        try:
            f = simulate(periods, seed, ablation, priors=priors, rho=rho, nu=nu)
            values.extend(f['truth']['y_complete'].tolist())
            hvalues.extend(f['truth']['h'].tolist())
        except (OverflowError, FloatingPointError) as exc:
            failures.append(dict(seed=seed, error=str(exc)))
            values.extend([float('nan')]*periods)
            hvalues.extend([float('nan')]*periods)
    y, h = np.asarray(values), np.asarray(hvalues)
    finite = np.isfinite(y)
    return dict(ablation=ablation, priors=asdict(priors), rho=rho, nu=nu,
                intended_draws=len(seeds), intended_returns=len(y), failed_draws=failures,
                nonfinite_returns=int((~finite).sum()),
                finite_only_abs_return_quantiles=(np.quantile(np.abs(y[finite]), [.5,.9,.99,1]).tolist() if finite.any() else None),
                exceedance_counts={str(b):int((np.abs(y)>b).sum()) for b in (.01,.05,.20)},
                nonfinite_log_scale=int((~np.isfinite(h)).sum()),
                finite_log_scale_range=([float(h[np.isfinite(h)].min()/2),float(h[np.isfinite(h)].max()/2)] if np.isfinite(h).any() else None),
                qualified=False, scope='Prior sensitivity diagnostic only; no market calibration or coverage claim')
