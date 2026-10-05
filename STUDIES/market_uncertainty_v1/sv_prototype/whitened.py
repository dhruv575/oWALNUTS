"""Exact diagonal prior whitening, preserving the physical SV posterior.

All coordinates including priors are transformed, not retuned. The constant
Jacobian is included. This is a geometry candidate, not evidence of speed or
market coverage. Unexpected nonfinite target values retain the fatal ABI policy.
"""
from dataclasses import dataclass
import hashlib
import json
import numpy as np
from adapter import compile_target, CompiledTarget
from target import Target

@dataclass(frozen=True)
class WhitenedTarget:
    compiled: CompiledTarget
    physical: CompiledTarget
    mean: np.ndarray
    sd: np.ndarray

    @property
    def target(self): return self.compiled.target
    @property
    def dimension(self): return self.compiled.dimension
    @property
    def snapshot_sha256(self): return self.compiled.snapshot_sha256
    def value_gradient(self,u): return self.compiled.value_gradient(u)
    def canonical(self,u):
        u=np.asarray(u,dtype=float)
        if u.ndim<1 or u.shape[-1]!=self.dimension or not np.isfinite(u).all():raise ValueError('Finite last coordinate dimension required')
        return self.mean+self.sd*u
    def sampling(self,q):
        q=np.asarray(q,dtype=float)
        if q.ndim<1 or q.shape[-1]!=self.dimension or not np.isfinite(q).all():raise ValueError('Finite last coordinate dimension required')
        return (q-self.mean)/self.sd


def compile_whitened(model):
    import numba
    import owalnuts
    # Snapshot/revalidate first, exactly as the physical adapter does.
    model=Target(model.y,model.x,model.w,model.observed,rho=model.rho,nu=model.nu,priors=model.priors)
    physical=compile_target(model);D=model.dimension;pr=model.priors
    mean=np.zeros(D);mean[:2]=pr.mu_mean,pr.log_sigma_mean
    sd=np.ones(D);sd[:2]=pr.mu_sd,pr.log_sigma_sd
    sd[2:2+model.p]=pr.beta_sd;sd[2+model.p:model.offset]=pr.gamma_sd
    mean.setflags(write=False);sd.setflags(write=False)
    logjac=float(np.log(sd).sum());raw=physical.callback.ctypes
    @numba.cfunc(owalnuts.numba_raw_signature(),nopython=True)
    def callback(dim,uptr,gptr,user):
        if dim!=D:return np.nan
        u=numba.carray(uptr,D);g=numba.carray(gptr,D)
        q=np.empty(D);gq=np.empty(D)
        for j in range(D):g[j]=np.nan
        for j in range(D):
            q[j]=mean[j]+sd[j]*u[j]
            if not np.isfinite(q[j]):return np.nan
        value=raw(D,q.ctypes,gq.ctypes,user)
        if not np.isfinite(value):return value
        for j in range(D):
            g[j]=sd[j]*gq[j]
        return value+logjac
    # Explicit closure lifetime: wrapper alone must retain its underlying native code.
    callback._physical_keepalive=physical
    target=owalnuts.from_cfunc(callback,D,parameter_names=[f'prior_white_{i}' for i in range(D)])
    digest=hashlib.sha256(json.dumps(dict(physical=physical.snapshot_sha256,mean=mean.tolist(),sd=sd.tolist(),logjac=logjac),sort_keys=True).encode()).hexdigest()
    return WhitenedTarget(CompiledTarget(target,callback,D,digest),physical,mean,sd)
