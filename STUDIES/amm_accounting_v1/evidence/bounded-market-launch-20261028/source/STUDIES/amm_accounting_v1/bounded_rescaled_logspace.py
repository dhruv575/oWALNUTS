"""Direct rescaled density without constructing physical beta or observation scales."""
import math
import numpy as np
from scipy.special import expit,log_ndtr


def signed_difference(log_a,sign_a,log_b,sign_b):
    if sign_a==0:return log_b,-sign_b
    if sign_b==0:return log_a,sign_a
    if sign_a!=sign_b:return float(np.logaddexp(log_a,log_b)),sign_a
    if log_a==log_b:return -np.inf,0.
    if log_a>log_b:return log_a+np.log(-np.expm1(log_b-log_a)),sign_a
    return log_b+np.log(-np.expm1(log_a-log_b)),-sign_b


def target(q,y,cap,rho=.95):
    q=np.asarray(q,dtype=float);y=np.asarray(y,dtype=float);n=len(y)
    if y.ndim!=1 or n<1 or q.shape!=(n+3,) or not np.isfinite(q).all() or not np.isfinite(y).all():raise ValueError('Finite shape-matched inputs')
    if not np.isfinite(cap) or cap<=0 or not np.isfinite(rho) or not -1<rho<1:raise ValueError('Cap/rho')
    mu,eta,b=q[:3];z=q[3:];l=np.log(cap)-np.logaddexp(0.,eta);sigma=np.exp(l)
    a=np.empty(n);a[0]=z[0]/np.sqrt(1-rho*rho)
    for i in range(1,n):a[i]=rho*a[i-1]+z[i]
    abar=a.mean();s=.5*(mu+sigma*abar);h=mu+sigma*a
    weights=np.ones(n)/n
    for i in range(n-1,0,-1):weights[i-1]+=rho*weights[i]
    weights[0]/=np.sqrt(1-rho*rho)
    logb=np.log(abs(b)) if b else -np.inf;signb=np.sign(b)
    with np.errstate(over='raise',invalid='raise'):
        beta2=np.exp(2*s+2*logb-2*np.log(.002)) if b else 0.
        beta_db=signb*np.exp(2*s+logb-2*np.log(.002)) if b else 0.
    nc=.5*np.log(2*np.pi);m=2*np.log(.005)
    value=-.5*(mu-m)**2-nc-.5*((l-np.log(.2))/.5)**2-np.log(.5)-nc
    value+=-.5*np.dot(z,z)-n*nc-.5*beta2-np.log(.002)-nc
    value+=-log_ndtr((np.log(cap)-np.log(.2))/.5)-np.logaddexp(0.,-eta)+s
    di=np.empty(n);kb=-beta2;db=-beta_db
    tc=math.lgamma(3.)-math.lgamma(2.5)-.5*np.log(5*np.pi)
    for i in range(n):
        delta=.5*sigma*(abar-a[i])
        logy=np.log(abs(y[i]))-.5*h[i] if y[i] else -np.inf
        lr,sr=signed_difference(logy,np.sign(y[i]),logb+delta,signb)
        den=np.logaddexp(np.log(5.),2*lr)
        value+=tc-.5*h[i]-3*np.logaddexp(0.,2*lr-np.log(5.))
        di[i]=-.5+3*np.exp(2*lr-den)
        if sr:
            db+=6*sr*np.exp(lr+delta-den)
            if b:kb+=6*sr*signb*np.exp(lr+logb+delta-den)
    factor=kb+1.;g=np.empty_like(q)
    g[0]=-(mu-m)+di.sum()+.5*factor
    gl=-(l-np.log(.2))/.25+sigma*np.dot(di,a)+.5*factor*sigma*abar
    g[1]=-expit(eta)*gl+expit(-eta);g[2]=db
    adj=di.copy()
    for i in range(n-1,0,-1):adj[i-1]+=rho*adj[i]
    adj[0]/=np.sqrt(1-rho*rho)
    g[3:]=-z+sigma*adj+.5*factor*sigma*weights
    if not np.isfinite(value) or not np.isfinite(g).all():raise FloatingPointError('Unrepresentable log density or gradient')
    return float(value),g
