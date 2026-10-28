"""Native composition of the exact location rescaling and admitted base target."""
import numpy as np
from bounded_scale_native import compile_target as compile_base,NativeBounded


def compile_target(y,cap,rho=.95):
    import numba,owalnuts
    base=compile_base(y,cap,rho);dim=base.dimension;n=dim-3;original=base.evaluator
    weights=np.ones(n)/n
    for i in range(n-1,0,-1):weights[i-1]+=rho*weights[i]
    weights[0]/=np.sqrt(1-rho*rho);weights.setflags(write=False)
    @numba.njit(error_model='numpy')
    def evaluate(q,g):
        for j in range(dim):
            if not np.isfinite(q[j]):return np.nan
        sigma=np.exp(np.log(cap)-np.logaddexp(0.,q[1]));mean_a=0.
        for i in range(n):mean_a+=weights[i]*q[3+i]
        log_scale=.5*(q[0]+sigma*mean_a);scale=np.exp(log_scale)
        if not np.isfinite(scale) or scale==0:return np.nan
        p=q.copy();p[2]=scale*q[2];value=original(p,g)
        gb=g[2];factor=gb*p[2]+1.
        g[0]+=.5*factor
        g[1]-=.5*factor*sigma*mean_a*np.exp(-np.logaddexp(0.,-q[1]))
        for i in range(n):g[3+i]+=.5*factor*sigma*weights[i]
        g[2]=gb*scale
        value+=log_scale
        if not np.isfinite(value):return np.nan
        for j in range(dim):
            if not np.isfinite(g[j]):return np.nan
        return value
    @numba.cfunc(owalnuts.numba_raw_signature(),nopython=True)
    def callback(d,qptr,gptr,user):
        if d!=dim:return np.nan
        q=numba.carray(qptr,dim);g=numba.carray(gptr,dim)
        for j in range(dim):g[j]=np.nan
        value=evaluate(q,g)
        if not np.isfinite(value):
            for j in range(dim):g[j]=np.nan
        return value
    names=['mu','eta','b']+[f'z[{i}]' for i in range(n)]
    return NativeBounded(owalnuts.from_cfunc(callback,dim,parameter_names=names),callback,dim,base.snapshot_sha256,evaluate)
