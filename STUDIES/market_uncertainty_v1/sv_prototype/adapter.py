"""Owned immutable Numba CFunc snapshot of the normalized SV research target."""
from dataclasses import dataclass
import ctypes,hashlib,json
import numpy as np
from scipy.special import gammaln
from target import Target

@dataclass(frozen=True)
class CompiledTarget:
    target: object
    callback: object
    dimension: int
    snapshot_sha256: str

    def value_gradient(self,q):
        q=np.ascontiguousarray(q,dtype=np.float64)
        if q.shape!=(self.dimension,):raise ValueError('Exact parameter dimension required')
        g=np.empty_like(q);ptr=ctypes.POINTER(ctypes.c_double)
        value=self.callback.ctypes(self.dimension,q.ctypes.data_as(ptr),g.ctypes.data_as(ptr),None)
        return float(value),g


def compile_target(model):
    """Snapshot data/prior values; finite numerical overflow returns NaN (fatal), not zero density.

    Callback owns only read-only constants and per-invocation arrays: no Python
    callbacks, mutable shared scratch or exception crosses the native ABI.
    """
    import numba
    import owalnuts
    if not isinstance(model,Target):raise TypeError('Expected validated SV Target')
    # Revalidate public model attributes and copy again; later caller mutation is irrelevant.
    frozen=Target(model.y,model.x,model.w,model.observed,rho=model.rho,nu=model.nu,priors=model.priors)
    y,x,w,observed=[np.array(a,copy=True) for a in (frozen.y,frozen.x,frozen.w,frozen.observed)]
    for a in (y,x,w,observed):a.setflags(write=False)
    T,P,K,D,O=frozen.t,frozen.p,frozen.k,frozen.dimension,frozen.offset
    rho,nu=frozen.rho,frozen.nu;pr=frozen.priors
    means=np.zeros(D);means[:2]=pr.mu_mean,pr.log_sigma_mean
    scales=np.ones(D);scales[:2]=pr.mu_sd,pr.log_sigma_sd;scales[2:2+P]=pr.beta_sd;scales[2+P:O]=pr.gamma_sd
    normal_constant=.5*np.log(2*np.pi);constant=float(gammaln((nu+1)/2)-gammaln(nu/2)-.5*np.log(nu*np.pi));lognu=np.log(nu);initial_factor=1/np.sqrt(1-rho*rho)
    description=dict(y=y.tolist(),x=x.tolist(),w=w.tolist(),observed=observed.tolist(),rho=rho,nu=nu,priors=vars(pr),coordinates='mu,log_sigma,beta,gamma,z')
    digest=hashlib.sha256(json.dumps(description,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    @numba.njit(error_model='numpy')
    def evaluate(q,g):
        lp=0.
        for j in range(D):
            if not np.isfinite(q[j]):return np.nan
            a=(q[j]-means[j])/scales[j]
            lp+=-.5*a*a-np.log(scales[j])-normal_constant
            g[j]=-a/scales[j]
        # Finite negative log_sigma can underflow to zero. This is the representable
        # zero-innovation limit; retain the finite log_sigma prior and check all outputs.
        sigma=np.exp(q[1])
        if not np.isfinite(lp) or not np.isfinite(sigma):return np.nan
        h=np.empty(T);dh=np.zeros(T)
        for i in range(T):
            forced=0.
            for k in range(K):forced+=w[i,k]*q[2+P+k]
            h[i]=q[0]+forced+sigma*initial_factor*q[O] if i==0 else q[0]+rho*(h[i-1]-q[0])+forced+sigma*q[O+i]
            if not np.isfinite(h[i]):return np.nan
            if observed[i]:
                residual=y[i]
                for p in range(P):residual-=x[i,p]*q[2+p]
                if not np.isfinite(residual):return np.nan
                logabs=np.log(abs(residual));denom=np.logaddexp(lognu+h[i],2*logabs)
                lp+=constant-.5*h[i]-.5*(nu+1)*np.logaddexp(0.,2*logabs-lognu-h[i])
                dh[i]=-.5+.5*(nu+1)*np.exp(2*logabs-denom)
                location=(nu+1)*np.sign(residual)*np.exp(logabs-denom)
                for p in range(P):g[2+p]+=x[i,p]*location
        for i in range(T-1,-1,-1):
            for k in range(K):g[2+P+k]+=dh[i]*w[i,k]
            multiplier=sigma*initial_factor if i==0 else sigma
            g[O+i]+=dh[i]*multiplier;g[1]+=dh[i]*multiplier*q[O+i]
            g[0]+=dh[i]*(1. if i==0 else 1-rho)
            if i:dh[i-1]+=rho*dh[i]
        if not np.isfinite(lp):return np.nan
        for j in range(D):
            if not np.isfinite(g[j]):return np.nan
        return lp
    @numba.cfunc(owalnuts.numba_raw_signature(),nopython=True)
    def callback(dim,qptr,gptr,user):
        if dim!=D:return np.nan
        q=numba.carray(qptr,D);g=numba.carray(gptr,D)
        for j in range(D):g[j]=np.nan
        value=evaluate(q,g)
        if not np.isfinite(value):
            for j in range(D):g[j]=np.nan
        return value
    names=['mu','log_sigma']+[f'beta_{j}' for j in range(P)]+[f'gamma_{j}' for j in range(K)]+[f'z_{j}' for j in range(T)]
    wrapped=owalnuts.from_cfunc(callback,D,parameter_names=names)
    return CompiledTarget(wrapped,callback,D,digest)
