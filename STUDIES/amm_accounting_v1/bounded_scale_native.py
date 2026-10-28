"""Owned WALNUTS callback for the normalized bounded-scale point-return target."""
import ctypes, hashlib, json, math
from dataclasses import dataclass
import numpy as np
from scipy.special import log_ndtr


@dataclass(frozen=True)
class NativeBounded:
    target: object
    callback: object
    dimension: int
    snapshot_sha256: str

    def value_gradient(self,q):
        q=np.ascontiguousarray(q,dtype=np.float64)
        if q.shape!=(self.dimension,): raise ValueError('Exact dimension')
        g=np.empty_like(q);p=ctypes.POINTER(ctypes.c_double)
        value=self.callback.ctypes(self.dimension,q.ctypes.data_as(p),g.ctypes.data_as(p),None)
        return float(value),g


def compile_target(y,cap,rho=.95):
    import numba,owalnuts
    obs=np.array(y,dtype=float,copy=True)
    if obs.ndim!=1 or not len(obs) or not np.isfinite(obs).all(): raise ValueError('Finite observations')
    if not np.isfinite(cap) or cap<=0 or not np.isfinite(rho) or not -1<rho<1: raise ValueError('Cap/rho')
    obs.setflags(write=False);n=len(obs);dim=3+n
    digest=hashlib.sha256(json.dumps(dict(y=obs.tolist(),cap=cap,rho=rho),sort_keys=True).encode()).hexdigest()
    tc=math.lgamma(3.)-math.lgamma(2.5)-.5*np.log(5*np.pi);nc=.5*np.log(2*np.pi)
    normalizer=float(log_ndtr((np.log(cap)-np.log(.2))/.5))
    @numba.njit(error_model='numpy')
    def evaluate(q,g):
        for j in range(dim):
            if not np.isfinite(q[j]):return np.nan
        eta=q[1];l=np.log(cap)-np.logaddexp(0.,eta);sigma=np.exp(l)
        lp=-normalizer-np.logaddexp(0.,-eta)
        for j in range(dim):
            value=l if j==1 else q[j]
            mean=2*np.log(.005) if j==0 else np.log(.2) if j==1 else 0.
            sd=.5 if j==1 else .002 if j==2 else 1.
            v=(value-mean)/sd;lp+=-.5*v*v-np.log(sd)-nc;g[j]=-v/sd
        a=np.empty(n);dh=np.empty(n)
        for i in range(n):
            a[i]=q[3+i]/np.sqrt(1-rho*rho) if i==0 else rho*a[i-1]+q[3+i]
            h=q[0]+sigma*a[i];r=obs[i]-q[2];lr=np.log(abs(r));den=np.logaddexp(np.log(5.)+h,2*lr)
            lp+=tc-.5*h-3*np.logaddexp(0.,2*lr-np.log(5.)-h)
            dh[i]=-.5+3*np.exp(2*lr-den)
            g[0]+=dh[i];g[1]+=dh[i]*sigma*a[i];g[2]+=6*np.sign(r)*np.exp(lr-den)
        for i in range(n-1,-1,-1):
            g[3+i]+=sigma*dh[i]/(np.sqrt(1-rho*rho) if i==0 else 1.)
            if i:dh[i-1]+=rho*dh[i]
        g[1]=-np.exp(-np.logaddexp(0.,-eta))*g[1]+np.exp(-np.logaddexp(0.,eta))
        if not np.isfinite(lp):return np.nan
        for j in range(dim):
            if not np.isfinite(g[j]):return np.nan
        return lp
    @numba.cfunc(owalnuts.numba_raw_signature(),nopython=True)
    def callback(d,qptr,gptr,user):
        if d!=dim:return np.nan
        q=numba.carray(qptr,dim);g=numba.carray(gptr,dim)
        for j in range(dim):g[j]=np.nan
        value=evaluate(q,g)
        if not np.isfinite(value):
            for j in range(dim):g[j]=np.nan
        return value
    names=['mu','eta','beta']+[f'z[{i}]' for i in range(n)]
    return NativeBounded(owalnuts.from_cfunc(callback,dim,parameter_names=names),callback,dim,digest)
