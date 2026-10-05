import gc,weakref
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pytest
from target import Target,Priors
from adapter import compile_target
PR= Priors(-10.,2.,np.log(.2),.5,.02,.15)
def model(k=1,t=4):
 return Target(np.linspace(-.01,.01,t),np.ones((t,1)),np.linspace(-1,1,t).reshape(t,1) if k else np.empty((t,0)),np.array([i!=1 for i in range(t)]),rho=.8,nu=5.,priors=PR)
@pytest.fixture(scope='module',params=[0,1])
def pair(request):
 m=model(request.param);return m,compile_target(m)
def test_normalized_value_gradient_parity(pair):
 m,c=pair
 for mu,ls in [(-10,np.log(.2)),(-8,-4),(-12,0)]:
  q=np.zeros(m.dimension);q[:2]=mu,ls;q[2]=.001;q[m.offset:]=np.linspace(-1,1,m.t)
  if m.k:q[3]=.04
  expected=m.value_gradient(q);actual=c.value_gradient(q)
  np.testing.assert_allclose(actual[0],expected[0],rtol=1e-12,atol=1e-10);np.testing.assert_allclose(actual[1],expected[1],rtol=1e-11,atol=1e-9)
  step=1e-6;fd=[]
  for j in range(len(q)):
   a=q.copy();b=q.copy();a[j]+=step;b[j]-=step;fd.append((c.value_gradient(a)[0]-c.value_gradient(b)[0])/(2*step))
  np.testing.assert_allclose(actual[1],fd,rtol=1e-5,atol=1e-5)
def test_extreme_failure_abi(pair):
 m,c=pair
 for index,value in [(0,1e308),(1,1000.),(2,float('nan'))]:
  q=np.zeros(m.dimension);q[:2]=[-10,-2];q[index]=value;v,g=c.value_gradient(q);assert np.isnan(v) and np.isnan(g).all()
 with pytest.raises(ValueError):c.value_gradient(np.zeros(m.dimension+1))
def test_parallel_reentrant(pair):
 m,c=pair;q=np.zeros(m.dimension);q[:2]=[-10,-2];expected=c.value_gradient(q)
 with ThreadPoolExecutor(4) as pool:results=list(pool.map(c.value_gradient,[q]*16))
 for v,g in results:assert v==expected[0];np.testing.assert_array_equal(g,expected[1])
def test_snapshot_ownership_and_t1_zero_residual():
 m=model(t=1);c=compile_target(m);q=np.zeros(m.dimension);q[:2]=[-10,-2];q[2]=m.y[0];before=c.value_gradient(q)
 m.y.setflags(write=True);m.y[:]=9;m.w.setflags(write=True);m.w[:]=4
 np.testing.assert_array_equal(before[1],c.value_gradient(q)[1]);assert before[0]==c.value_gradient(q)[0]
 callback=weakref.ref(c.callback);target=c.target;del c,m;gc.collect();assert callback() is not None;assert target.keep_alive is callback()
 del target;gc.collect();assert callback() is None
def test_independent_jax_parity(pair):
 import jax
 from reference import make_reference
 m,c=pair;density,_=make_reference(m);q=np.zeros(m.dimension);q[:2]=[-9.,-.8];q[2]=.001;q[m.offset:]=np.linspace(-.5,.5,m.t)
 if m.k:q[3]=-.07
 value,gradient=jax.value_and_grad(density)(q);actual=c.value_gradient(q)
 np.testing.assert_allclose(actual[0],value,rtol=1e-12,atol=1e-10);np.testing.assert_allclose(actual[1],gradient,rtol=1e-11,atol=1e-9)

def test_finite_underflow_limit(pair):
 m,c=pair
 from reference import make_reference
 import jax
 density,_=make_reference(m)
 for logsigma in [-1000.,-1e6]:
  q=np.zeros(m.dimension);q[:2]=[-10,logsigma];q[2]=m.y[0]
  v,g=c.value_gradient(q);pv,pg=m.value_gradient(q);jv,jg=jax.value_and_grad(density)(q)
  assert np.isfinite(v) and np.isfinite(g).all()
  np.testing.assert_allclose(v,pv,rtol=1e-12);np.testing.assert_allclose(g,pg,rtol=1e-11,atol=1e-9)
  np.testing.assert_allclose(v,jv,rtol=1e-12);np.testing.assert_allclose(g,jg,rtol=1e-11,atol=1e-9)

def test_exact_observed_first_failure_regression():
 import json,jax
 from pathlib import Path
 from reference import make_reference
 f=json.loads((Path(__file__).parent/'test_data/underflow_first_failure.json').read_text())
 m=Target(**f['data'],priors=Priors(**f['priors']));q=np.asarray(f['q']);v,g=compile_target(m).value_gradient(q);pv,pg=m.value_gradient(q);density,_=make_reference(m);jv,jg=jax.value_and_grad(density)(q)
 assert np.isfinite(v) and np.isfinite(g).all()
 np.testing.assert_allclose(v,pv,rtol=1e-12);np.testing.assert_allclose(v,jv,rtol=1e-12);np.testing.assert_allclose(g,pg,rtol=1e-11,atol=1e-9);np.testing.assert_allclose(g,jg,rtol=1e-11,atol=1e-9)
