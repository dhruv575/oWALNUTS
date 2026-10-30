import ctypes,json
from types import SimpleNamespace
from pathlib import Path
import numpy as np
import owalnuts
from nutpie.compile_pymc import CompiledPyMCModel

ROOT=Path(__file__).resolve().parent.parent
BUILD=ROOT/'build'
DP=ctypes.POINTER(ctypes.c_double)

class Backend:
    def __init__(self,data,center=None,A=None,starts=None):
        self.data=data;self.dim=data['P'];d=self.dim
        self.center=np.zeros(d) if center is None else np.asarray(center,dtype=float)
        self.A=np.eye(d) if A is None else np.ascontiguousarray(A,dtype=float)
        self.lib=ctypes.CDLL(str(BUILD/'adapter.so'))
        self.lib.create.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int,ctypes.c_int,DP,DP];self.lib.create.restype=ctypes.c_void_p
        self.lib.destroy.argtypes=[ctypes.c_void_p]
        self.lib.last_error.argtypes=[ctypes.c_void_p];self.lib.last_error.restype=ctypes.c_char_p
        self.lib.evaluate.argtypes=[ctypes.c_uint64,DP,DP,DP,ctypes.c_void_p];self.lib.evaluate.restype=ctypes.c_int
        self.lib.nuts.argtypes=[ctypes.c_uint64,DP,DP,DP,ctypes.c_void_p];self.lib.nuts.restype=ctypes.c_int64
        self.lib.walnuts.argtypes=[ctypes.c_uint64,DP,DP,ctypes.c_void_p];self.lib.walnuts.restype=ctypes.c_double
        self.lib.expand.argtypes=[ctypes.c_uint64,ctypes.c_uint64,DP,DP,ctypes.c_void_p];self.lib.expand.restype=ctypes.c_int64
        self.lib.reset.argtypes=[ctypes.c_void_p];self.lib.counters.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint64)]
        self.lib.predict.argtypes=[ctypes.c_void_p,DP,DP];self.lib.predict.restype=ctypes.c_int
        self.ptr=self.lib.create(str(BUILD/'model_model.so').encode(),json.dumps(data).encode(),d,data['Npred'],self.center.ctypes.data_as(DP),self.A.ctypes.data_as(DP))
        if not self.ptr:raise RuntimeError('Native model creation failed')
        self.initial=np.asarray(starts,dtype=float) if starts is not None else np.zeros((4,d))
        self.initial_calls=0
        def initial(seed):
            q=self.initial[self.initial_calls].copy();self.initial_calls+=1;return q
        wrap=lambda f:SimpleNamespace(address=ctypes.cast(f,ctypes.c_void_p).value,ctypes=f)
        self.nuts=CompiledPyMCModel(dims=None,compiled_logp_func=wrap(self.lib.nuts),compiled_expand_func=wrap(self.lib.expand),initial_point_func=initial,shared_data={},user_data=np.array([self.ptr],dtype=np.uint64),n_expanded=d,shape_info=(['q'],None,[(d,)]),logp_func=None,expand_func=None,_n_dim=d,_shapes={'q':(d,)},_coords={})
        self.walnuts=owalnuts.from_cfunc(wrap(self.lib.walnuts),d,user_data=self.ptr)
    def value(self,q):
        q=np.ascontiguousarray(q);g=np.empty(self.dim);lp=np.zeros(1)
        s=self.lib.evaluate(self.dim,q.ctypes.data_as(DP),g.ctypes.data_as(DP),lp.ctypes.data_as(DP),self.ptr)
        if s:raise ValueError(self.lib.last_error(self.ptr).decode())
        return lp[0],g
    def predict(self,q):
        q=np.ascontiguousarray(q);out=np.empty(self.data['Npred'])
        if self.lib.predict(self.ptr,q.ctypes.data_as(DP),out.ctypes.data_as(DP)):raise ValueError(self.lib.last_error(self.ptr).decode())
        if not np.isfinite(out).all():raise ValueError('Nonfinite log concentration prediction')
        return out
    def counts(self):
        a=np.zeros(2,dtype=np.uint64);self.lib.counters(self.ptr,a.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)));return a.tolist()
    def reset(self):self.lib.reset(self.ptr)
    def close(self):
        if self.ptr:self.lib.destroy(self.ptr);self.ptr=None
