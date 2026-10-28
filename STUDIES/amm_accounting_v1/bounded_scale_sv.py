"""Separate point-return SV candidate with a normalized bounded-scale prior.

q=[mu,eta,beta,z]; log_sigma=log(cap)-softplus(eta). Includes Jacobian.
No observation jitter, dropped ties, or inherited market qualification.
"""
import math
import numpy as np
from scipy.special import expit,log_ndtr


def target(q,y,cap,rho=.95):
    q=np.asarray(q,dtype=float);y=np.asarray(y,dtype=float)
    if y.ndim!=1 or not len(y) or q.shape!=(3+len(y),) or not np.isfinite(q).all() or not np.isfinite(y).all():raise ValueError('Finite target inputs')
    if not np.isfinite(cap) or cap<=0 or not np.isfinite(rho) or not -1<rho<1:raise ValueError('Positive cap and stationary rho')
    mu,eta,beta=q[:3];z=q[3:];n=len(y)
    l=np.log(cap)-np.logaddexp(0.,eta);sigma=np.exp(l);a=np.empty(n)
    a[0]=z[0]/np.sqrt(1-rho*rho)
    for i in range(1,n):a[i]=rho*a[i-1]+z[i]
    h=mu+sigma*a;r=y-beta
    with np.errstate(divide='ignore'):lr=np.log(abs(r))
    den=np.logaddexp(np.log(5.)+h,2*lr)
    tc=math.lgamma(3.)-math.lgamma(2.5)-.5*np.log(5*np.pi)
    value=np.sum(tc-.5*h-3*np.logaddexp(0.,2*lr-np.log(5.)-h))
    core=np.r_[mu,l,beta,z];mean=np.r_[2*np.log(.005),np.log(.2),0.,np.zeros(n)];sd=np.r_[1.,.5,.002,np.ones(n)]
    standardized=(core-mean)/sd
    value+=np.sum(-.5*standardized**2-np.log(sd)-.5*np.log(2*np.pi))
    value-=log_ndtr((np.log(cap)-np.log(.2))/.5)
    value-=np.logaddexp(0.,-eta)
    grad=-standardized/sd
    dh=-.5+3*np.exp(2*lr-den)
    grad[0]+=dh.sum();grad[1]+=np.dot(dh,sigma*a)
    grad[2]+=np.sum(6*np.sign(r)*np.exp(lr-den))
    adj=dh.copy()
    for i in range(n-1,0,-1):adj[i-1]+=rho*adj[i]
    grad[3:]+=sigma*adj;grad[3]+=sigma*adj[0]*(1/np.sqrt(1-rho*rho)-1)
    grad[1]=-expit(eta)*grad[1]+expit(-eta)
    if not np.isfinite(value) or not np.isfinite(grad).all():raise ValueError('Nonfinite target evaluation')
    return float(value),grad
