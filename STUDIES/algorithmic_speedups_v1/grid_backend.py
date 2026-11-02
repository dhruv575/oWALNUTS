import ctypes
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from nutpie.compile_pymc import CompiledPyMCModel
from grid import GridGP
DP=ctypes.POINTER(ctypes.c_double)
class Native:
    def __init__(self,data,seed=954100001):
        self.model=GridGP(data);m=self.model;self.lib=ctypes.CDLL(str(Path(__file__).with_name('grid_native.so')))
        self.lib.grid_create.argtypes=[ctypes.c_int,ctypes.c_int,DP,DP,DP,DP,ctypes.c_double];self.lib.grid_create.restype=ctypes.c_void_p
        arrays=[np.ascontiguousarray(a,dtype=float) for a in [m.x,m.y,m.design,m.counts]]
        self.ptr=self.lib.grid_create(m.nx,m.ny,*[a.ctypes.data_as(DP) for a in arrays],m.exposure)
        self.lib.grid_evaluate.argtypes=[ctypes.c_uint64,DP,DP,DP,ctypes.c_void_p];self.lib.grid_evaluate.restype=ctypes.c_int
        self.lib.grid_nuts.argtypes=[ctypes.c_uint64,DP,DP,DP,ctypes.c_void_p];self.lib.grid_nuts.restype=ctypes.c_int64
        self.lib.grid_expand.argtypes=[ctypes.c_uint64,ctypes.c_uint64,DP,DP,ctypes.c_void_p];self.lib.grid_expand.restype=ctypes.c_int64
        self.lib.grid_counts.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint64)]
        self.lib.grid_destroy.argtypes=[ctypes.c_void_p]
        wrap=lambda f:SimpleNamespace(address=ctypes.cast(f,ctypes.c_void_p).value,ctypes=f)
        rng=np.random.default_rng(seed);d=m.n+5
        def initial(seed):return rng.uniform(-1,1,d)
        self.compiled=CompiledPyMCModel(dims=None,compiled_logp_func=wrap(self.lib.grid_nuts),compiled_expand_func=wrap(self.lib.grid_expand),initial_point_func=initial,shared_data={},shared_var_keys=[],user_data=np.array([self.ptr],dtype=np.uint64),n_expanded=d,shape_info=(['q'],None,[(d,)]),logp_func=None,expand_func=None,_n_dim=d,_shapes={'q':(d,)},_coords={})
    def value(self,q):
        q=np.ascontiguousarray(q);g=np.empty_like(q);v=np.empty(1)
        status=self.lib.grid_evaluate(len(q),q.ctypes.data_as(DP),g.ctypes.data_as(DP),v.ctypes.data_as(DP),self.ptr)
        if status:raise ValueError('native grid evaluation failed')
        return float(v[0]),g
    def counts(self):
        out=np.zeros(2,dtype=np.uint64);self.lib.grid_counts(self.ptr,out.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)));return out.tolist()
    def close(self):self.lib.grid_destroy(self.ptr)
