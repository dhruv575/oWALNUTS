"""Independent Gaussian-prior elliptical slice core, physical-price likelihood."""
import numpy as np
from scipy.special import gammaln
from price_cell_conditionals import sweep


def physical(core):
    core=np.asarray(core,dtype=float)
    if core.ndim!=1 or len(core)<4 or not np.isfinite(core).all():raise ValueError('Core coordinates')
    return core*np.r_[1.,.5,.002,np.ones(len(core)-3)]+np.r_[2*np.log(.005),np.log(.2),0.,np.zeros(len(core)-3)]


def likelihood(core,x,initial=0.,rho=.95):
    q=physical(core);mu,l,beta=q[:3];z=q[3:];x=np.asarray(x,dtype=float)
    if x.shape!=z.shape or not np.isfinite(x).all() or not -1<rho<1:raise ValueError('Data/shape')
    sigma=np.exp(l);h=np.empty(len(z));h[0]=mu+sigma*z[0]/np.sqrt(1-rho*rho)
    for i in range(1,len(z)):h[i]=mu+rho*(h[i-1]-mu)+sigma*z[i]
    if not np.isfinite(h).all():raise FloatingPointError('Nonfinite latent path')
    r=np.diff(np.r_[initial,x])-beta
    with np.errstate(divide='ignore'):a=2*np.log(np.abs(r))-np.log(5.)-h
    value=float(np.sum(gammaln(3.)-gammaln(2.5)-.5*np.log(5*np.pi)-h/2-3*np.logaddexp(0.,a)))
    if not np.isfinite(value):raise FloatingPointError('Nonfinite likelihood')
    return value,h,beta


def ellipse(core,x,rng,initial=0.,max_attempts=1000):
    core=np.asarray(core,dtype=float);current=likelihood(core,x,initial)[0]
    direction=rng.normal(size=len(core));uniform=float(rng.uniform())
    if uniform<=0:raise FloatingPointError('Zero slice uniform')
    threshold=current+np.log(uniform)
    angle=float(rng.uniform(0,2*np.pi));lo=angle-2*np.pi;hi=angle
    for attempt in range(max_attempts):
        proposal=core*np.cos(angle)+direction*np.sin(angle)
        if likelihood(proposal,x,initial)[0]>threshold:return proposal,attempt+1
        if angle<0:lo=angle
        else:hi=angle
        angle=float(rng.uniform(lo,hi))
    raise RuntimeError('Elliptical slice attempt cap')


def transition(core,x,lower,upper,rng,initial=0.):
    new_core,evaluations=ellipse(core,x,rng,initial)
    _,h,beta=likelihood(new_core,x,initial)
    new_x,proposals=sweep(x,h,beta,initial,lower,upper,rng)
    return new_core,new_x,dict(slice_evaluations=evaluations,price_proposals=proposals)
