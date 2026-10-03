"""Experimental observation-residual coordinates for the unchanged local target.

u = [z, log_sigma_obs, log_sigma_rw], h = y + sigma_obs*z.
The T*log_sigma_obs Jacobian cancels the observation scale normalizers.
This is distinct from process-innovation noncentering. No sampling defaults or
qualification gates are changed; all public output must be canonicalized.
"""
import numpy as np
from scipy.special import gammaln
from local_level import validate


def _position(q, data):
    validate(data)
    q = np.asarray(q, dtype=float)
    if q.ndim < 1 or q.shape[-1] != len(data['y'])+2 or not np.isfinite(q).all():
        raise ValueError('Require finite positions with final dimension T+2')
    return q


def to_canonical(u, data):
    u = _position(u, data)
    with np.errstate(over='ignore', invalid='ignore'):
        scale = np.exp(u[..., -2:-1])
        h = np.asarray(data['y']) + scale*u[..., :-2]
    if not np.isfinite(h).all() or not np.isfinite(scale).all() or (scale == 0).any():
        raise ValueError('Canonical conversion produced nonfinite positions')
    return np.concatenate((h, u[..., -2:]), axis=-1)


def to_residual(q, data):
    q = _position(q, data)
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        scale = np.exp(q[..., -2:-1])
        z = (q[..., :-2]-np.asarray(data['y']))/scale
    if not np.isfinite(z).all() or not np.isfinite(scale).all() or (scale == 0).any():
        raise ValueError('Residual conversion produced invalid scale or positions')
    return np.concatenate((z, q[..., -2:]), axis=-1)


def canonical_starts(data, chains):
    y, _ = validate(data)
    if not isinstance(chains, int) or isinstance(chains, bool) or chains < 1:
        raise ValueError('chains must be a positive integer')
    if 'initial_positions' in data:
        starts=_position(data['initial_positions'],data)
        if starts.shape != (chains,len(y)+2):raise ValueError('Invalid canonical initial_positions')
        return starts.copy()
    offset = (np.arange(chains)-(chains-1)/2)*.02
    return np.column_stack((y[None, :]+offset[:, None],
                            np.log(.08)+offset, np.log(.12)-offset))


def log_density(u, data, xp=np):
    """Independent normalized density, usable directly with JAX autodiff."""
    u = xp.asarray(u)
    if u.ndim != 1 or u.shape[0] != len(data['y'])+2:
        raise ValueError('Position dimension must equal T+2')
    z, lo, lr = u[:-2], u[-2], u[-1]
    h = xp.asarray(data['y'])+xp.exp(lo)*z
    dt = xp.asarray(data.get('dt', np.ones(len(data['y'])-1)))
    def normal(v, mean, sd):
        return xp.sum(-.5*((v-mean)/sd)**2-xp.log(sd)-.5*np.log(2*np.pi))
    lp = normal(lo, np.log(.08), 1.)+normal(lr, np.log(.12), 1.)
    lp += normal(h[0], data['anchor'], 1.5)
    lp += normal(h[1:]-h[:-1], 0., xp.exp(lr)*xp.sqrt(dt))
    return lp+xp.sum(gammaln(3.)-gammaln(2.5)-.5*np.log(5*np.pi)
                     -3*xp.log1p(z*z/5))


def build_model(data, initial=None):
    """PyMC density-only model; one vector makes coordinate order explicit."""
    import pymc as pm
    import pytensor.tensor as pt
    y, dt = validate(data)
    y, dt = y.copy(), dt.copy()
    if initial is None:
        initial = np.r_[np.zeros(len(y)),np.log(.08),np.log(.12)]
    initial = _position(initial, data)
    if initial.ndim != 1:
        raise ValueError('initial must be one residual-coordinate vector')
    with pm.Model() as model:
        u = pm.Flat('position', shape=len(y)+2, initval=initial.copy())
        z, lo, lr = u[:-2], u[-2], u[-1]
        h = pt.constant(y)+pt.exp(lo)*z
        lp = pm.logp(pm.Normal.dist(mu=np.float64(np.log(.08)), sigma=np.float64(1.)), lo)
        lp += pm.logp(pm.Normal.dist(mu=np.float64(np.log(.12)), sigma=np.float64(1.)), lr)
        lp += pm.logp(pm.Normal.dist(mu=np.float64(data['anchor']), sigma=np.float64(1.5)), h[0])
        lp += pm.logp(pm.Normal.dist(mu=h[:-1], sigma=pt.exp(lr)*pt.sqrt(dt)), h[1:]).sum()
        lp += pm.logp(pm.StudentT.dist(nu=np.float64(5.), mu=np.float64(0.), sigma=np.float64(1.)), z).sum()
        pm.Potential('normalized_target', lp)
    return model


def compile_target(data, initial=None, gil_free=True):
    import owalnuts
    return owalnuts.from_pymc(build_model(data, initial), gil_free=gil_free)
