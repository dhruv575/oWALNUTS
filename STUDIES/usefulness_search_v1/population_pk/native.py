import ctypes
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import owalnuts
from nutpie.compile_pymc import CompiledPyMCModel
from model import Population,OLD
DP=ctypes.POINTER(ctypes.c_double)
ROOT=Path(__file__).resolve().parent
class Native:
 def __init__(self,center=None,A=None,starts=None):
  self.model=Population('linear');self.dim=d=43
  self.center=np.zeros(d) if center is None else np.asarray(center,dtype=float)
  self.A=np.eye(d) if A is None else np.ascontiguousarray(A,dtype=float)
  self.lib=ctypes.CDLL(str(ROOT/'population.so'))
  self.lib.population_create.argtypes=[ctypes.c_char_p,ctypes.POINTER(ctypes.c_void_p)]+[DP]*7;self.lib.population_create.restype=ctypes.c_void_p
  self.lib.population_destroy.argtypes=[ctypes.c_void_p]
  self.lib.population_evaluate.argtypes=[ctypes.c_uint64,DP,DP,DP,ctypes.c_void_p];self.lib.population_evaluate.restype=ctypes.c_int
  self.lib.population_value.argtypes=[DP,ctypes.c_void_p];self.lib.population_value.restype=ctypes.c_double
  self.lib.population_walnuts.argtypes=[ctypes.c_uint64,DP,DP,ctypes.c_void_p];self.lib.population_walnuts.restype=ctypes.c_double
  self.lib.population_nuts.argtypes=[ctypes.c_uint64,DP,DP,DP,ctypes.c_void_p];self.lib.population_nuts.restype=ctypes.c_int64
  self.lib.population_expand.argtypes=[ctypes.c_uint64,ctypes.c_uint64,DP,DP,ctypes.c_void_p];self.lib.population_expand.restype=ctypes.c_int64
  self.lib.population_counters.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint64)];self.lib.population_reset.argtypes=[ctypes.c_void_p]
  ptrs=(ctypes.c_void_p*12)(*[b.ptr for b in self.model.backends]);data=[b.data for b in self.model.backends]
  arrays=[self.model.weights,np.array([b['dose'] for b in data]),np.array([b['c0'] for b in data]),np.array([b['times'] for b in data]),np.log(np.array([b['concentration'] for b in data])),self.center,self.A]
  arrays=[np.ascontiguousarray(a,dtype=float) for a in arrays]
  self.ptr=self.lib.population_create(str(OLD/'build/adapter.so').encode(),ptrs,*[a.ctypes.data_as(DP) for a in arrays]);assert self.ptr
  self.initial=np.zeros((4,d)) if starts is None else np.asarray(starts,dtype=float);self.initial_calls=0
  def initial(seed):
   q=self.initial[self.initial_calls].copy();self.initial_calls+=1;return q
  wrap=lambda f:SimpleNamespace(address=ctypes.cast(f,ctypes.c_void_p).value,ctypes=f)
  self.nuts=CompiledPyMCModel(dims=None,compiled_logp_func=wrap(self.lib.population_nuts),compiled_expand_func=wrap(self.lib.population_expand),initial_point_func=initial,shared_data={},user_data=np.array([self.ptr],dtype=np.uint64),n_expanded=d,shape_info=(['q'],None,[(d,)]),logp_func=None,expand_func=None,_n_dim=d,_shapes={'q':(d,)},_coords={})
  self.walnuts=owalnuts.from_cfunc(wrap(self.lib.population_walnuts),d,user_data=self.ptr)
 def value(self,q):
  q=np.ascontiguousarray(q,dtype=float);g=np.empty(43);lp=np.zeros(1)
  if self.lib.population_evaluate(43,q.ctypes.data_as(DP),g.ctypes.data_as(DP),lp.ctypes.data_as(DP),self.ptr):raise ValueError('Native population evaluation failed')
  return float(lp[0]),g
 def density(self,q):return self.lib.population_value(np.ascontiguousarray(q,dtype=float).ctypes.data_as(DP),self.ptr)
 def counts(self):
  a=np.zeros(2,dtype=np.uint64);self.lib.population_counters(self.ptr,a.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)));return a.tolist()
 def reset(self):self.lib.population_reset(self.ptr)
 def close(self):
  if self.ptr:self.lib.population_destroy(self.ptr);self.ptr=None
  self.model.close()
