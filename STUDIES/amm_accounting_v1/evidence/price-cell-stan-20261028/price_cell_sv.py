"""Full candidate SV target, q=[mu,log_sigma,beta,z,u]; synthetic validation only."""
import numpy as np
from scipy.special import expit
from price_cells import kernel


def target(q, lower, upper, initial, rho=.95):
    lower=np.asarray(lower,dtype=float);upper=np.asarray(upper,dtype=float)
    q=np.asarray(q,dtype=float)
    if lower.ndim!=1 or not lower.size or upper.shape!=lower.shape:
        raise ValueError('Matching nonempty cell vectors required')
    n=len(lower)
    if q.shape!=(3+2*n,) or not np.isfinite(q).all() or not -1<rho<1:
        raise ValueError('Finite full target coordinates and stationary rho required')
    mu,l,beta=q[:3];z=q[3:3+n];u=q[3+n:]
    sigma=np.exp(l);a=np.empty(n);a[0]=z[0]/np.sqrt(1-rho*rho)
    for i in range(1,n):a[i]=rho*a[i-1]+z[i]
    h=mu+sigma*a
    value,gu=kernel(u,lower,upper,initial,beta,h)
    mean=np.r_[2*np.log(.005),np.log(.2),0.,np.zeros(n)]
    sd=np.r_[1.,.5,.002,np.ones(n)]
    core=q[:3+n];v=(core-mean)/sd
    value+=np.sum(-.5*v*v-np.log(sd)-.5*np.log(2*np.pi))
    grad=np.r_[-v/sd,gu]
    x=lower+(upper-lower)*expit(u)
    r=np.diff(np.r_[initial,x])-beta
    with np.errstate(divide='ignore'):logr=np.log(np.abs(r))
    denom=np.logaddexp(np.log(5.)+h,2*logr)
    dh=-.5+3*np.exp(2*logr-denom)
    grad[0]+=dh.sum();grad[1]+=np.dot(dh,sigma*a)
    grad[2]+=np.sum(6*np.sign(r)*np.exp(logr-denom))
    adj=dh.copy()
    for i in range(n-1,0,-1):adj[i-1]+=rho*adj[i]
    grad[3:3+n]+=sigma*adj
    grad[3]+=sigma*adj[0]*(1/np.sqrt(1-rho*rho)-1)
    return float(value),grad
