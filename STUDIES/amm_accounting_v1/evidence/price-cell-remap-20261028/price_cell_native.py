"""Owned native callback for the candidate cell target; requires parity admission."""
import ctypes,hashlib,json,math
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class NativeCell:
    target: object
    callback: object
    dimension: int
    snapshot_sha256: str

    def value_gradient(self,q):
        q=np.ascontiguousarray(q,dtype=np.float64)
        if q.shape!=(self.dimension,):raise ValueError('Exact dimension')
        g=np.empty_like(q);p=ctypes.POINTER(ctypes.c_double)
        v=self.callback.ctypes(self.dimension,q.ctypes.data_as(p),g.ctypes.data_as(p),None)
        return float(v),g


def compile_target(lower,upper,initial=0.,rho=.95):
    import numba,owalnuts
    lo=np.array(lower,dtype=float,copy=True);hi=np.array(upper,dtype=float,copy=True)
    if lo.ndim!=1 or not len(lo) or hi.shape!=lo.shape or not np.isfinite(lo).all() or not np.isfinite(hi).all() or not np.all(hi>lo):raise ValueError('Finite positive cells')
    if not np.isfinite(initial) or not -1<rho<1:raise ValueError('Initial/rho')
    lo.setflags(write=False);hi.setflags(write=False);n=len(lo);dim=3+2*n
    digest=hashlib.sha256(json.dumps(dict(lower=lo.tolist(),upper=hi.tolist(),initial=initial,rho=rho),sort_keys=True).encode()).hexdigest()
    tc=math.lgamma(3.)-math.lgamma(2.5)-.5*np.log(5*np.pi);nc=.5*np.log(2*np.pi)
    @numba.njit(error_model='numpy')
    def evaluate(q,g):
        for j in range(dim):
            if not np.isfinite(q[j]):return np.nan
            g[j]=0.
        lp=0.
        for j in range(3+n):
            mean=2*np.log(.005) if j==0 else np.log(.2) if j==1 else 0.
            sd=.5 if j==1 else .002 if j==2 else 1.
            v=(q[j]-mean)/sd;lp+=-.5*v*v-np.log(sd)-nc;g[j]=-v/sd
        sigma=np.exp(q[1]);a=np.empty(n);h=np.empty(n);x=np.empty(n);s=np.empty(n);ds=np.empty(n)
        for i in range(n):
            a[i]=q[3+i]/np.sqrt(1-rho*rho) if i==0 else rho*a[i-1]+q[3+i]
            h[i]=q[0]+sigma*a[i];u=q[3+n+i]
            s[i]=np.exp(-np.logaddexp(0.,-u));ds[i]=np.exp(-np.logaddexp(0.,-u)-np.logaddexp(0.,u))
            x[i]=lo[i]+(hi[i]-lo[i])*s[i]
            lp+=np.log(hi[i]-lo[i])-np.logaddexp(0.,-u)-np.logaddexp(0.,u)
        dy=np.empty(n);dh=np.empty(n)
        for i in range(n):
            r=x[i]-(initial if i==0 else x[i-1])-q[2];lr=np.log(abs(r));den=np.logaddexp(np.log(5.)+h[i],2*lr)
            lp+=tc-.5*h[i]-3*np.logaddexp(0.,2*lr-np.log(5.)-h[i])
            dy[i]=-6*np.sign(r)*np.exp(lr-den);dh[i]=-.5+3*np.exp(2*lr-den)
            g[0]+=dh[i];g[1]+=dh[i]*sigma*a[i];g[2]-=dy[i]
        for i in range(n):g[3+n+i]=(dy[i]-(dy[i+1] if i+1<n else 0.))*(hi[i]-lo[i])*ds[i]+1-2*s[i]
        for i in range(n-1,-1,-1):
            g[3+i]+=sigma*dh[i]/(np.sqrt(1-rho*rho) if i==0 else 1.)
            if i:dh[i-1]+=rho*dh[i]
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
    names=['mu','log_sigma','beta']+[f'z[{i}]' for i in range(n)]+[f'u[{i}]' for i in range(n)]
    return NativeCell(owalnuts.from_cfunc(callback,dim,parameter_names=names),callback,dim,digest)
