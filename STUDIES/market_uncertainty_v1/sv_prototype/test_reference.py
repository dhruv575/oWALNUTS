import unittest
import numpy as np
import jax
from scipy.stats import norm,t as student
from target import Target,Priors
from reference import make_reference,make_kernel
PR= Priors(-10.,2.,-1.6,.5,.02,.15)
def centered(m,q):
 mu,ls,b,g,z=m.unpack(q);sd=np.exp(ls);h=m.path(q)
 value=norm.logpdf(mu,PR.mu_mean,PR.mu_sd)+norm.logpdf(ls,PR.log_sigma_mean,PR.log_sigma_sd)+norm.logpdf(b,0,PR.beta_sd).sum()+norm.logpdf(g,0,PR.gamma_sd).sum()
 value+=norm.logpdf(h[0],mu+m.w[0]@g,sd/np.sqrt(1-m.rho*m.rho))
 for i in range(1,m.t):value+=norm.logpdf(h[i],mu+m.rho*(h[i-1]-mu)+m.w[i]@g,sd)
 value+=m.t*ls-.5*np.log(1-m.rho*m.rho)
 ix=m.observed;value+=student.logpdf(m.y[ix],m.nu,loc=m.x[ix]@b,scale=np.exp(h[ix]/2)).sum()
 return value
class ReferenceTests(unittest.TestCase):
 def test_ablations_missing_short_paths_and_centered_oracle(self):
  rng=np.random.default_rng(731)
  for n,p,k,rho in [(1,0,0,0.),(2,1,0,-.8),(8,0,2,.95),(33,2,2,.99)]:
   with self.subTest(n=n,p=p,k=k):
    mask=np.arange(n)%3!=1;y=rng.normal(0,.01,n);x=rng.normal(size=(n,p));w=rng.normal(size=(n,k));y[~mask]=np.nan;x[~mask]=np.nan
    m=Target(y,x,w,mask,rho=rho,nu=5.,priors=PR);q=np.r_[-9.,-1.3,rng.normal(0,.01,p),rng.normal(0,.1,k),rng.normal(0,.3,n)]
    density,path=make_reference(m);v,g=jax.value_and_grad(density)(q);a,ag=m.value_gradient(q)
    np.testing.assert_allclose(path(q),m.path(q),rtol=1e-12,atol=1e-12);self.assertAlmostEqual(float(v),centered(m,q),places=9);self.assertAlmostEqual(float(v),a,places=9);np.testing.assert_allclose(g,ag,rtol=1e-10,atol=1e-9)
    for j in range(m.dimension):
     d=np.zeros(m.dimension);d[j]=1e-6
     self.assertAlmostEqual(float(g[j]),(centered(m,q+d)-centered(m,q-d))/2e-6,delta=3e-5)
 def test_zero_residual_and_all_missing(self):
  for mask in [np.ones(2,dtype=bool),np.zeros(2,dtype=bool)]:
   m=Target([0.,0.],np.ones((2,1)),np.ones((2,1)),mask,rho=-.5,nu=5.,priors=PR);q=np.array([-9.,-1.,0.,.1,.2,-.3]);f,_=make_reference(m);v,g=jax.value_and_grad(f)(q);a,ag=m.value_gradient(q)
   np.testing.assert_allclose(v,a,atol=1e-10);np.testing.assert_allclose(g,ag,atol=1e-10)
 def test_dimension_and_kernel(self):
  m=Target([0.],np.empty((1,0)),np.empty((1,0)),[True],rho=.5,nu=5.,priors=PR);f,_=make_reference(m)
  with self.assertRaises(ValueError):f(np.zeros((1,3)))
  with self.assertRaises(ValueError):make_kernel(m,target_accept=True)
  self.assertIsNotNone(make_kernel(m))
if __name__=='__main__':unittest.main()
