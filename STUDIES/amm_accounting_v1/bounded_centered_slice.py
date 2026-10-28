"""Exact shifted Gaussian reference for the all-zero rescaled target."""
import numpy as np
from bounded_rescaled_slice import physical,likelihood as original_residual


def center(n,cap,rho=.95):
    if type(n)is not int or n<1 or not np.isfinite(cap) or cap<=0 or not np.isfinite(rho) or not -1<rho<1:raise ValueError('Center inputs')
    weights=np.ones(n)/n
    for i in range(n-1,0,-1):weights[i-1]+=rho*weights[i]
    weights[0]/=np.sqrt(1-rho*rho)
    k=(n-1)/2
    return np.r_[-k,0.,0.,-k*cap*weights]


def residual(core,y,cap):
    c=center(len(y),cap)
    return original_residual(core,y,cap)-np.dot(c,core)+.5*np.dot(c,c)


def ellipse(core,y,cap,rng,indices,max_attempts=1000):
    core=np.asarray(core,dtype=float);indices=np.asarray(indices);c=center(len(y),cap)
    if indices.ndim!=1 or not len(indices) or indices.dtype.kind not in 'iu' or len(set(indices.tolist()))!=len(indices) or np.any(indices<0) or np.any(indices>=len(core)):raise ValueError('Unique valid block indices')
    if type(max_attempts)is not int or max_attempts<1:raise ValueError('Positive attempt cap')
    current=residual(core,y,cap);direction=rng.normal(size=len(indices));u=float(rng.random())
    if u<=0:raise FloatingPointError('Zero slice uniform')
    level=current+np.log(u);angle=float(rng.uniform(0,2*np.pi));lo=angle-2*np.pi;hi=angle
    for attempt in range(max_attempts):
        proposal=core.copy();proposal[indices]=c[indices]+(core[indices]-c[indices])*np.cos(angle)+direction*np.sin(angle)
        if residual(proposal,y,cap)>level:return proposal,attempt+1
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
