import ctypes
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from scipy.special import expit,logit
import owalnuts
from nutpie.compile_pymc import CompiledPyMCModel
ROOT=Path(__file__).resolve().parent
DP=ctypes.POINTER(ctypes.c_double)
LOW=np.array([-5.,-2.]);WIDTH=np.array([6.,4.])
def physical(z):return LOW+WIDTH*expit(z)
def unconstrained(q):return logit((np.asarray(q)-LOW)/WIDTH)
def linear_prediction(q,t,theta):
    q=np.atleast_2d(q);c=np.exp(q[:,0,None]);k=np.exp(q[:,1,None]);t=np.asarray(t)[None,:]
    w=np.sqrt((k-c*c/4).astype(complex));wt=w*t
    # sinc is continuous at critical damping and works with complex arguments.
    return (theta*np.exp(-c*t/2)*(np.cos(wt)+c*t/2*np.sinc(wt/np.pi))).real
class Backend:
    def __init__(self,data,center=None,A=None,starts=None,step=.01):
        self.data=data;self.dim=2;self.initial_calls=0
        self.center=np.zeros(2) if center is None else np.asarray(center,dtype=float)
        self.A=np.eye(2) if A is None else np.ascontiguousarray(A,dtype=float)
        self.initial=np.zeros((4,2)) if starts is None else np.asarray(starts,dtype=float)
        self.lib=ctypes.CDLL(str(ROOT/'pendulum.so'))
        self.lib.create.argtypes=[ctypes.c_double,ctypes.c_double,ctypes.c_double,ctypes.c_int,ctypes.c_int,DP,DP,DP,DP];self.lib.create.restype=ctypes.c_void_p
        self.lib.destroy.argtypes=[ctypes.c_void_p]
        self.lib.evaluate.argtypes=[ctypes.c_uint64,DP,DP,DP,ctypes.c_void_p];self.lib.evaluate.restype=ctypes.c_int
        self.lib.nuts.argtypes=[ctypes.c_uint64,DP,DP,DP,ctypes.c_void_p];self.lib.nuts.restype=ctypes.c_int64
        self.lib.walnuts.argtypes=[ctypes.c_uint64,DP,DP,ctypes.c_void_p];self.lib.walnuts.restype=ctypes.c_double
        self.lib.expand.argtypes=[ctypes.c_uint64,ctypes.c_uint64,DP,DP,ctypes.c_void_p];self.lib.expand.restype=ctypes.c_int64
        self.lib.predict.argtypes=[ctypes.c_void_p,DP,ctypes.c_int,DP,DP];self.lib.predict.restype=ctypes.c_int
        self.lib.predict_batch.argtypes=[ctypes.c_void_p,ctypes.c_int,DP,ctypes.c_int,DP,DP];self.lib.predict_batch.restype=ctypes.c_int
        self.lib.reset.argtypes=[ctypes.c_void_p];self.lib.counters.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint64)]
        t=np.ascontiguousarray(data['times'],dtype=float);y=np.ascontiguousarray(data['observed'],dtype=float)
        self.ptr=self.lib.create(data['theta'],data['sigma'],step,int(data.get('linear',False)),len(t),t.ctypes.data_as(DP),y.ctypes.data_as(DP),self.center.ctypes.data_as(DP),self.A.ctypes.data_as(DP))
        def initial(seed):
            q=self.initial[self.initial_calls].copy();self.initial_calls+=1;return q
        wrap=lambda f:SimpleNamespace(address=ctypes.cast(f,ctypes.c_void_p).value,ctypes=f)
        self.nuts=CompiledPyMCModel(dims=None,compiled_logp_func=wrap(self.lib.nuts),compiled_expand_func=wrap(self.lib.expand),initial_point_func=initial,shared_data={},user_data=np.array([self.ptr],dtype=np.uint64),n_expanded=2,shape_info=(['q'],None,[(2,)]),logp_func=None,expand_func=None,_n_dim=2,_shapes={'q':(2,)},_coords={})
        self.walnuts=owalnuts.from_cfunc(wrap(self.lib.walnuts),2,user_data=self.ptr)
    def value(self,q):
        q=np.ascontiguousarray(q,dtype=float);g=np.empty(2);v=np.empty(1)
        if self.lib.evaluate(2,q.ctypes.data_as(DP),g.ctypes.data_as(DP),v.ctypes.data_as(DP),self.ptr):raise ValueError('Nonfinite density')
        return float(v[0]),g
    def predict(self,q,t=None):
        q=np.ascontiguousarray(q,dtype=float);t=np.ascontiguousarray(self.data['future_times'] if t is None else t,dtype=float);out=np.empty(len(t))
        if self.lib.predict(self.ptr,q.ctypes.data_as(DP),len(t),t.ctypes.data_as(DP),out.ctypes.data_as(DP)):raise ValueError('Prediction failure')
        return out
    def predict_batch(self,q,t=None):
        q=np.ascontiguousarray(q,dtype=float)
        if q.ndim!=2 or q.shape[1]!=2:raise ValueError('Expected (draws, 2) parameters')
        t=np.ascontiguousarray(self.data['future_times'] if t is None else t,dtype=float)
        if t.ndim!=1 or len(q)>2147483647 or len(t)>2147483647:raise ValueError('Invalid batch shape')
        out=np.empty((len(q),len(t)))
        if self.lib.predict_batch(self.ptr,len(q),q.ctypes.data_as(DP),len(t),t.ctypes.data_as(DP),out.ctypes.data_as(DP)):raise ValueError('Prediction failure')
        return out
    def reset(self):self.lib.reset(self.ptr)
    def counts(self):
        a=np.zeros(2,dtype=np.uint64);self.lib.counters(self.ptr,a.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)));return a.tolist()
    def close(self):
        if self.ptr:self.lib.destroy(self.ptr);self.ptr=None
