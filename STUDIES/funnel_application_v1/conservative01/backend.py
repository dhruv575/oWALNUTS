import ctypes,json,sys,inspect
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from scipy.special import expit,logit
sys.path.append('/home/ubuntu/lanes/unified-readiness-20261027/installation02/work/env/lib/python3.12/site-packages')
import owalnuts
from nutpie.compile_pymc import CompiledPyMCModel
BASE=Path(__file__).resolve().parent;DP=ctypes.POINTER(ctypes.c_double)
def flags(data,space):return np.full(12,space=='centered') if space!='hybrid' else np.array(data['n'])>=1000
def to_physical(q,data,space):
    theta=np.array(q[...,2:],copy=True);nc=~flags(data,space);theta[...,nc]=q[...,:1]+np.exp(q[...,1:2])*theta[...,nc];return np.concatenate([q[...,:1],np.exp(q[...,1:2]),theta],axis=-1)
def from_physical(p,data,space):
    q=np.array(p,copy=True);q[...,1]=np.log(p[...,1]);nc=~flags(data,space);q[...,2:][...,nc]=(p[...,2:][...,nc]-p[...,:1])/p[...,1:2];return q
def features(p):return np.concatenate([p,expit(p[...,2:]),(p[...,1:2]<.1).astype(float),(p[...,1:2]<.5).astype(float)],axis=-1)
class Backend:
    def __init__(self,data,space,seed=1):
        self.data=data;self.space=space;self.dim=14;self.lib=ctypes.CDLL('/home/ubuntu/lanes/funnel-application-20261101/model.so')
        self.lib.create.argtypes=[ctypes.c_int,DP,DP,ctypes.c_int];self.lib.create.restype=ctypes.c_void_p
        self.lib.evaluate.argtypes=[ctypes.c_uint64,DP,DP,DP,ctypes.c_void_p];self.lib.evaluate.restype=ctypes.c_int
        self.lib.nuts.argtypes=[ctypes.c_uint64,DP,DP,DP,ctypes.c_void_p];self.lib.nuts.restype=ctypes.c_int64
        self.lib.walnuts.argtypes=[ctypes.c_uint64,DP,DP,ctypes.c_void_p];self.lib.walnuts.restype=ctypes.c_double
        self.lib.expand.argtypes=[ctypes.c_uint64,ctypes.c_uint64,DP,DP,ctypes.c_void_p];self.lib.expand.restype=ctypes.c_int64
        self.lib.destroy.argtypes=[ctypes.c_void_p];self.lib.counters.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint64)]
        n=np.ascontiguousarray(data['n'],dtype=float);y=np.ascontiguousarray(data['y'],dtype=float);self.ptr=self.lib.create(12,n.ctypes.data_as(DP),y.ctypes.data_as(DP),['centered','noncentered','hybrid'].index(space))
        rng=np.random.default_rng(seed);p=np.zeros((4,14));p[:,0]=logit((y.sum()+.5)/(n.sum()+1))+rng.normal(0,.2,4);p[:,1]=[.05,.2,.5,1.];p[:,2:]=p[:,:1]+p[:,1:2]*rng.normal(0,.1,(4,12));self.starts=from_physical(p,data,space);self.initial_calls=0
        def initial(seed):row=self.starts[self.initial_calls].copy();self.initial_calls+=1;return row
        wrap=lambda f:SimpleNamespace(address=ctypes.cast(f,ctypes.c_void_p).value,ctypes=f)
        extra={'shared_var_keys':[]} if 'shared_var_keys' in inspect.signature(CompiledPyMCModel).parameters else {}
        self.nuts=CompiledPyMCModel(dims=None,compiled_logp_func=wrap(self.lib.nuts),compiled_expand_func=wrap(self.lib.expand),initial_point_func=initial,shared_data={},user_data=np.array([self.ptr],dtype=np.uint64),n_expanded=14,shape_info=(['q'],None,[(14,)]),logp_func=None,expand_func=None,_n_dim=14,_shapes={'q':(14,)},_coords={},**extra)
        self.walnuts=owalnuts.from_cfunc(wrap(self.lib.walnuts),14,user_data=self.ptr)
    def value(self,q):
        q=np.ascontiguousarray(q,dtype=float);g=np.empty(14);v=np.empty(1)
        if self.lib.evaluate(14,q.ctypes.data_as(DP),g.ctypes.data_as(DP),v.ctypes.data_as(DP),self.ptr):raise ValueError('Invalid target')
        return float(v[0]),g
    def counts(self):
        a=np.zeros(2,dtype=np.uint64);self.lib.counters(self.ptr,a.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)));return a.tolist()
    def close(self):self.lib.destroy(self.ptr)
