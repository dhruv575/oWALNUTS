"""Physical-price conditional rejection kernel, independent of target gradients."""
import numpy as np


def log_acceptance(value,index,x,h,beta,initial):
    """Log conditional density divided by product of Student-t peak heights."""
    x=np.asarray(x,dtype=float);h=np.asarray(h,dtype=float)
    if x.ndim!=1 or h.shape!=x.shape or not 0<=index<len(x):raise ValueError('Shape/index')
    if not np.isfinite(x).all() or not np.isfinite(h).all() or not np.isfinite([value,beta,initial]).all():raise ValueError('Finite inputs')
    residuals=[value-(initial if index==0 else x[index-1])-beta]
    scales=[h[index]]
    if index+1<len(x):residuals.append(x[index+1]-value-beta);scales.append(h[index+1])
    with np.errstate(divide='ignore'):
        a=2*np.log(np.abs(residuals))-np.log(5.)-np.asarray(scales)
    return float(-3*np.logaddexp(0.,a).sum())


def sweep(x,h,beta,initial,lower,upper,rng,max_attempts=10000):
    """Sequential exact conditional draws; abort on cap, no partial success."""
    x=np.asarray(x,dtype=float).copy();lower=np.asarray(lower,dtype=float);upper=np.asarray(upper,dtype=float)
    if lower.shape!=x.shape or upper.shape!=x.shape or not np.all(upper>lower):raise ValueError('Cells')
    if not np.isfinite(lower).all() or not np.isfinite(upper).all() or not np.all((x>lower)&(x<upper)):raise ValueError('Interior state')
    attempts=0
    for i in range(len(x)):
        envelope=cell_log_envelope(i,x,h,beta,initial,lower[i],upper[i])
        for _ in range(max_attempts):
            value=float(rng.uniform(lower[i],upper[i]));attempts+=1
            if not lower[i]<value<upper[i]:raise FloatingPointError('Rounded endpoint proposal')
            uniform=float(rng.uniform())
            if uniform<=0:raise FloatingPointError('Zero uniform')
            log_ratio=log_acceptance(value,i,x,h,beta,initial)-envelope
            if log_ratio>1e-10:raise FloatingPointError('Conditional envelope violation')
            if np.log(uniform)<min(0.,log_ratio):x[i]=value;break
        else:raise RuntimeError('Conditional rejection attempt cap')
    return x,attempts


def cell_log_envelope(index,x,h,beta,initial,lower,upper):
    """Product of factor maxima over the cell, relative to global peaks."""
    x=np.asarray(x,dtype=float);h=np.asarray(h,dtype=float)
    if x.ndim!=1 or h.shape!=x.shape or not 0<=index<len(x):raise ValueError('Shape/index')
    if not np.isfinite([lower,upper,beta,initial]).all() or not lower<upper:raise ValueError('Cell')
    modes=[(initial if index==0 else x[index-1])+beta];scales=[h[index]]
    if index+1<len(x):modes.append(x[index+1]-beta);scales.append(h[index+1])
    modes=np.asarray(modes);distance=np.abs(np.clip(modes,lower,upper)-modes)
    with np.errstate(divide='ignore'):a=2*np.log(distance)-np.log(5.)-np.asarray(scales)
    return float(-3*np.logaddexp(0.,a).sum())
