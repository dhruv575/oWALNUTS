"""Exact beta=exp(mean(h)/2)*b coordinates for the existing bounded target."""
import numpy as np
from scipy.special import expit
from bounded_scale_sv import target as original


def physical(q,cap,rho=.95):
    q=np.asarray(q,dtype=float)
    if q.ndim!=1 or len(q)<4 or not np.isfinite(q).all():raise ValueError('Finite vector')
    if not np.isfinite(cap) or cap<=0 or not np.isfinite(rho) or not -1<rho<1:raise ValueError('Cap/rho')
    z=q[3:];n=len(z);a=np.empty(n);a[0]=z[0]/np.sqrt(1-rho*rho)
    for i in range(1,n):a[i]=rho*a[i-1]+z[i]
    sigma=np.exp(np.log(cap)-np.logaddexp(0.,q[1]))
    log_scale=.5*(q[0]+sigma*a.mean());scale=np.exp(log_scale)
    if not np.isfinite(scale) or scale==0:raise ValueError('Unrepresentable scale')
    p=q.copy();p[2]=scale*q[2]
    d=np.zeros_like(q);d[0]=.5;d[1]=-.5*sigma*a.mean()*expit(q[1])
    weights=np.ones(n)/n
    for i in range(n-1,0,-1):weights[i-1]+=rho*weights[i]
    weights[0]/=np.sqrt(1-rho*rho);d[3:]=.5*sigma*weights
    return p,float(log_scale),scale,d


def target(q,y,cap,rho=.95):
    p,log_scale,scale,d=physical(q,cap,rho)
    value,g=original(p,y,cap,rho)
    grad=g+(g[2]*p[2]+1)*d
    grad[2]=g[2]*scale
    return value+log_scale,grad
