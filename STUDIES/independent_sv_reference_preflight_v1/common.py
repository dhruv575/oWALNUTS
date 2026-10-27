import json, math
import numpy as np

def fixture(n, variant=0):
    y=np.resize(np.array([.001,-.004,.003,.002,-.0005,.0007,-.0022,.0015]),n)
    q=np.r_[2*math.log(.005)+.2*variant,math.log(.2)-.1*variant,.0003*variant,np.resize(np.array([.2,-.4,.1,.3,.5,-.2,0.,.7]),n)*variant]
    return y,q

def data(y):
    return dict(n=len(y),y=np.asarray(y).tolist(),rho=.95,nu=5.,mu_mean=2*math.log(.005),mu_sd=1.,log_sigma_mean=math.log(.2),log_sigma_sd=.5,beta_sd=.002)

def extract(trace, draws=50):
    values=[]
    for name in ('mu','log_sigma','beta','h_last'):
        a=np.asarray(trace.posterior[name].transpose('chain','draw'))
        if a.dtype != np.dtype('float64') or a.shape!=(4,draws) or not np.isfinite(a).all():
            raise ValueError('invalid full precision component '+name)
        values.append(a)
    chains=np.asarray(trace.posterior.coords['chain'])
    if chains.shape!=(4,) or len(set(chains.tolist()))!=4:raise ValueError('chain identities')
    d=np.asarray(trace.sample_stats.diverging.transpose('chain','draw'))
    if d.shape!=(4,draws) or not np.isfinite(d).all() or not np.isin(d,[0,1]).all():raise ValueError('divergences')
    return np.stack(values,-1),dict(chain_ids=chains.tolist(),divergences=d.sum(1).astype(int).tolist())
