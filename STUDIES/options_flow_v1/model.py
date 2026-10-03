"""Matched options-flow research target, simulation, and chronological data contract."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from scipy.special import gammaln


def validate(data):
    y, x = np.asarray(data['y'], float), np.asarray(data['x'], float)
    if y.ndim != 2 or y.shape != x.shape or min(y.shape) < 1:
        raise ValueError('y and x must be equal nonempty T by G arrays')
    if not np.isfinite(y).all() or not np.isfinite(x).all():
        raise ValueError('Missing/nonfinite observations are not supported; no silent imputation')
    if not np.isfinite(float(data['nu'])) or not float(data['nu']) > 2 or not abs(float(data['rho'])) < 1:
        raise ValueError('Require finite nu > 2 and abs(rho) < 1')
    return y, x


def log_density(q, data, xp=np, gamma=gammaln):
    y, x = xp.asarray(data['y']), xp.asarray(data['x'])
    t, g = y.shape
    b, lt, mu, ls = q[:4]
    za, zb, h = q[4:4+g], q[4+g:4+2*g], q[4+2*g:]
    def normal(v, m, s):
        return xp.sum(-.5*((v-m)/s)**2-xp.log(s)-.5*xp.log(2*xp.pi))
    lp = normal(q[:4],xp.asarray([0.,-1.,-1.,-1.5]),xp.asarray([.5,.5,1.,.5]))
    lp += normal(za,0.,1.)+normal(zb,0.,1.)
    rho, nu = data['rho'], data['nu']
    sig = xp.exp(ls)
    lp += normal(h[0],mu,sig/xp.sqrt(1-rho*rho))
    lp += normal(h[1:],mu+rho*(h[:-1]-mu),sig)
    scale = xp.exp(h[:,None]/2)
    residual = (y-(.3*za+(b+xp.exp(lt)*zb)*x))/scale
    lp += xp.sum(gamma((nu+1)/2)-gamma(nu/2)-.5*xp.log(nu*xp.pi)-xp.log(scale)-(nu+1)/2*xp.log1p(residual**2/nu))
    return lp


def simulate(seed, periods=80, groups=4, holdout=20, prior=False):
    rng=np.random.default_rng(seed)
    globals_=rng.normal([0,-1,-1,-1.5],[.5,.5,1,.5]) if prior else np.array([.25,-1.,-1.,-1.5])
    b,lt,mu,ls=globals_; rho=.95; nu=5.
    za=rng.normal(size=groups); zb=rng.normal(size=groups)
    h=np.empty(periods+holdout); h[0]=rng.normal(mu,np.exp(ls)/np.sqrt(1-rho*rho))
    for k in range(1,len(h)): h[k]=rng.normal(mu+rho*(h[k-1]-mu),np.exp(ls))
    # Exogenous covariates: these are available lagged signals, not future contemporaneous flow.
    x=rng.normal(size=(len(h),groups))
    y=.3*za+(b+np.exp(lt)*zb)*x+np.exp(h[:,None]/2)*rng.standard_t(nu,size=x.shape)
    q=np.r_[globals_,za,zb,h[:periods]]
    return {'data':{'y':y[:periods].tolist(),'x':x[:periods].tolist(),'rho':rho,'nu':nu},
            'holdout':{'y':y[periods:].tolist(),'x':x[periods:].tolist()},'truth':q.tolist(),
            'seed':seed,'prior_predictive':prior,'source':'synthetic',
            'forecast_contract':'Fixed-origin multi-horizon scenario conditional on supplied x; no held-out y updates.'}


def functionals(q, groups):
    q=np.asarray(q); h=q[...,4+2*groups:]
    vals={'beta_bar':q[...,0],'tau':np.exp(q[...,1]),'mu_h':q[...,2],
          'sigma_h':np.exp(q[...,3]),'h_terminal':h[...,-1],'h_mean':h.mean(axis=-1)}
    for g in range(groups):
        vals[f'alpha_{g}']=.3*q[...,4+g]
        vals[f'beta_{g}']=q[...,0]+np.exp(q[...,1])*q[...,4+groups+g]
    return vals


def load_fixture(path):
    fixture=json.loads(Path(path).read_text()); validate(fixture['data'])
    if 'holdout' in fixture:
        future=dict(fixture['holdout'],nu=fixture['data']['nu'],rho=fixture['data']['rho'])
        validate(future)
        if len(future['x'][0])!=len(fixture['data']['x'][0]): raise ValueError('Holdout group count differs')
    return fixture
