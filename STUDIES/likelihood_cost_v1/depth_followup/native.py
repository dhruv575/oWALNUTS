import ctypes
import numpy as np
import numba,owalnuts,nutpie
from nutpie.compile_pymc import CompiledPyMCModel
from targets import core

class Native:
    def __init__(self,target):
        d=target.dim;kind=target.kind;P=target.precision.copy();self.counter=np.zeros(2,dtype=np.float64)
        sig=numba.types.int64(numba.types.uint64,numba.types.CPointer(numba.types.double),numba.types.CPointer(numba.types.double),numba.types.CPointer(numba.types.double),numba.types.voidptr)
        @numba.cfunc(sig,nopython=True,error_model='numpy')
        def nuts_logp(dim,qp,gp,lp,user):
            if dim!=d:return -1
            counts=numba.carray(user,(2,),dtype=numba.types.float64);counts[0]+=1
            q=numba.carray(qp,(d,));g=numba.carray(gp,(d,));value,gradient=core(q,kind,P)
            for i in range(d):g[i]=gradient[i]
            lp[0]=value
            if not np.isfinite(value) or not np.isfinite(gradient).all():counts[1]+=1;return 1
            return 0
        esig=numba.types.int64(numba.types.uint64,numba.types.uint64,numba.types.CPointer(numba.types.double),numba.types.CPointer(numba.types.double),numba.types.voidptr)
        @numba.cfunc(esig,nopython=True)
        def expand(dim,expanded,qp,out,user):
            if dim!=d or expanded!=d:return -1
            for i in range(d):out[i]=qp[i]
            return 0
        @numba.cfunc(owalnuts.numba_raw_signature(),nopython=True,error_model='numpy')
        def walnuts_logp(dim,qp,gp,user):
            if dim!=d:return np.nan
            counts=numba.carray(user,(2,),dtype=numba.types.float64);counts[0]+=1
            q=numba.carray(qp,(d,));g=numba.carray(gp,(d,));value,gradient=core(q,kind,P)
            for i in range(d):g[i]=gradient[i]
            if not np.isfinite(value) or not np.isfinite(gradient).all():
                counts[1]+=1
                for i in range(d):g[i]=0.
                return -np.inf
            return value
        self.nuts_logp=nuts_logp;self.expand=expand;self.walnuts_logp=walnuts_logp
        starts=iter(target.initial());self.initial_calls=0
        def initial(seed):self.initial_calls+=1;return next(starts).copy()
        self.nuts=CompiledPyMCModel(dims=None,compiled_logp_func=nuts_logp,compiled_expand_func=expand,initial_point_func=initial,
            shared_data={},user_data=self.counter,n_expanded=d,shape_info=(['q'],None,[(d,)]),logp_func=None,expand_func=None,_n_dim=d,_shapes={'q':(d,)},_coords={})
        self.walnuts=owalnuts.from_cfunc(walnuts_logp,d,user_data=self.counter.ctypes.data)

    def values(self,q):
        q=np.ascontiguousarray(q,dtype=float);g=np.empty_like(q);h=np.empty_like(q);lp=np.zeros(1)
        ptr=ctypes.POINTER(ctypes.c_double);user=ctypes.c_void_p(self.counter.ctypes.data)
        status=self.nuts_logp.ctypes(len(q),q.ctypes.data_as(ptr),g.ctypes.data_as(ptr),lp.ctypes.data_as(ptr),user)
        other=self.walnuts_logp.ctypes(len(q),q.ctypes.data_as(ptr),h.ctypes.data_as(ptr),user)
        return status,lp[0],g,other,h
