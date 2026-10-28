"""Independent blocked elliptical-slice control in Gaussian prior coordinates."""
import numpy as np
from scipy.special import log_ndtr,ndtri_exp,gammaln


def physical(core,cap):
    core=np.asarray(core,dtype=float)
    if core.ndim!=1 or len(core)<4 or not np.isfinite(core).all() or not np.isfinite(cap) or cap<=0:raise ValueError('Finite core and positive cap')
    log_mass=log_ndtr((np.log(cap)-np.log(.2))/.5)
    l=np.log(.2)+.5*ndtri_exp(log_mass+log_ndtr(core[1]))
    return np.r_[2*np.log(.005)+core[0],l,.002*core[2],core[3:]]


def likelihood(core,y,cap,rho=.95):
    q=physical(core,cap);mu,l,beta=q[:3];z=q[3:];y=np.asarray(y,dtype=float)
    if y.shape!=z.shape or not np.isfinite(y).all() or not np.isfinite(rho) or not -1<rho<1:raise ValueError('Matching finite observations and stationary rho')
    sigma=np.exp(l);h=np.empty(len(z));h[0]=mu+sigma*z[0]/np.sqrt(1-rho*rho)
    for i in range(1,len(z)):h[i]=mu+rho*(h[i-1]-mu)+sigma*z[i]
    with np.errstate(divide='ignore'):log_ratio=2*np.log(abs(y-beta))-np.log(5.)-h
    value=float(np.sum(gammaln(3.)-gammaln(2.5)-.5*np.log(5*np.pi)-h/2-3*np.logaddexp(0.,log_ratio)))
    if not np.isfinite(value):raise FloatingPointError('Nonfinite likelihood')
    return value


def ellipse(core,y,cap,rng,indices,max_attempts=1000):
    core=np.asarray(core,dtype=float);indices=np.asarray(indices)
    if indices.ndim!=1 or not len(indices) or indices.dtype.kind not in 'iu' or len(set(indices.tolist()))!=len(indices) or np.any(indices<0) or np.any(indices>=len(core)):raise ValueError('Unique valid block indices')
    if type(max_attempts)is not int or max_attempts<1:raise ValueError('Positive attempt cap')
    current=likelihood(core,y,cap);direction=rng.normal(size=len(indices));u=float(rng.random())
    if u<=0:raise FloatingPointError('Zero slice uniform')
    level=current+np.log(u);angle=float(rng.uniform(0,2*np.pi));lo=angle-2*np.pi;hi=angle
    for attempt in range(max_attempts):
        proposal=core.copy();proposal[indices]=core[indices]*np.cos(angle)+direction*np.sin(angle)
        if likelihood(proposal,y,cap)>level:return proposal,attempt+1
        if angle<0:lo=angle
        else:hi=angle
        angle=float(rng.uniform(lo,hi))
    raise RuntimeError('Elliptical slice proposal cap; no silent self-loop')


def transition(core,y,cap,rng,block_size=16):
    if type(block_size)is not int or block_size<1:raise ValueError('Positive block size')
    state=np.array(core,dtype=float,copy=True);calls=0
    blocks=[np.array([i]) for i in range(3)]+[np.arange(i,min(i+block_size,len(state))) for i in range(3,len(state),block_size)]
    for block in blocks:
        state,count=ellipse(state,y,cap,rng,block);calls+=count
    return state,calls
