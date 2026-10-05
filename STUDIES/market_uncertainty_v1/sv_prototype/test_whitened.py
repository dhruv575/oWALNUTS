import gc
import weakref
import numpy as np
from target import Target,Priors
from whitened import compile_whitened

def test_whitened_exact_density_gradient_and_batched_starts():
 m=Target([.01,0.,-.02],np.ones((3,1)),np.ones((3,1)),[True,False,True],rho=.8,nu=5.,priors=Priors(-10.,2.,-2.,.5,.002,.03))
 w=compile_whitened(m);u=np.linspace(-.3,.4,m.dimension);q=w.canonical(u)
 value,g=m.value_gradient(q);actual,gu=w.value_gradient(u)
 np.testing.assert_allclose(actual,value+np.log(w.sd).sum(),atol=1e-10)
 np.testing.assert_allclose(gu,w.sd*g,atol=1e-10)
 starts=np.stack([q,q+.001])
 np.testing.assert_allclose(w.canonical(w.sampling(starts)),starts,atol=1e-14)
 for j in range(m.dimension):
  a=u.copy();b=u.copy();a[j]+=1e-6;b[j]-=1e-6
  np.testing.assert_allclose(gu[j],(w.value_gradient(a)[0]-w.value_gradient(b)[0])/2e-6,rtol=1e-5,atol=1e-6)
 raw=weakref.ref(w.physical.callback);target=w.target;del w;gc.collect()
 assert raw() is not None
 del target;gc.collect();assert raw() is None

def test_all_missing_whitened_prior_is_standard_normal():
 m=Target([np.nan],np.empty((1,0)),np.empty((1,0)),[False],rho=-.4,nu=5.,priors=Priors(-10.,2.,-2.,.5,.002,.03))
 w=compile_whitened(m);u=np.array([.2,-.7,.9]);v,g=w.value_gradient(u)
 np.testing.assert_allclose(v,-.5*np.sum(u*u)-len(u)/2*np.log(2*np.pi),atol=1e-12)
 np.testing.assert_allclose(g,-u,atol=1e-12)
 bad=u.copy();bad[0]=np.nan;v,g=w.value_gradient(bad)
 assert np.isnan(v) and np.isnan(g).all()
