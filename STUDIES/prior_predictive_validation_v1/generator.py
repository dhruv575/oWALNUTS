"""Draft generation functions. Importing never generates data."""
import math
import numpy as np
DATA_BASE=2026102701000000
INIT_BASE=2026102702000000
WARM_BASE=2026102703000000
RHO=.95

def seeds(stream):
    if type(stream) is not int or not 0<=stream<32:raise ValueError('stream must be0..31')
    return dict(data=DATA_BASE+stream,initial=INIT_BASE+1000*stream,warm=WARM_BASE+1000*stream)

def generate(stream,rng_factory=np.random.default_rng):
    """One draw, without rejection/truncation/replacement; caller archives failures."""
    rng=rng_factory(seeds(stream)['data'])
    mu=float(rng.normal(2*math.log(.005),1.));ls=float(rng.normal(math.log(.2),.5));beta=float(rng.normal(0.,.002))
    z=np.asarray(rng.normal(size=283),dtype=float);innovation=np.asarray(rng.standard_t(5,size=283),dtype=float)
    with np.errstate(over='raise',invalid='raise',under='ignore'):
        sigma=np.exp(ls);h=np.empty(283);h[0]=mu+sigma*z[0]/math.sqrt(1-RHO*RHO)
        for i in range(1,283):h[i]=mu+RHO*(h[i-1]-mu)+sigma*z[i]
        y=beta+np.exp(h/2)*innovation
    if not np.isfinite([mu,ls,beta]).all() or not np.isfinite(h).all() or not np.isfinite(y).all():raise ValueError('nonfinite generated stream; preserve failure, never regenerate')
    return dict(stream=stream,seeds=seeds(stream),parameters=dict(mu=mu,log_sigma=ls,beta=beta),h=h,y=y)

def tick_inputs(data,tick):
    if type(tick) is not int or not 1<=tick<=32:raise ValueError('tick must be1..32')
    y=np.asarray(data['y']);h=np.asarray(data['h'])
    if y.shape!=(283,) or h.shape!=(283,):raise ValueError('exact283 observations/latents required')
    current=249+tick;future=current+1
    return dict(window=y[tick:250+tick].copy(),observation=float(y[current]),label=float(y[future]),current_latent=float(h[current]),current_index=current,label_index=future)
