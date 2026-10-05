import unittest,numpy as np
from scipy.stats import multivariate_normal
from blocked import filter_state,ffbs,seed_rng
class ExactChecks(unittest.TestCase):
 def test_kalman_matches_dense_normal_with_gaps(self):
  for t in (1,8,17):
   rho=.98;q=.02;r=.09;x=np.linspace(-1,1,t);y=np.sin(np.arange(t));mask=np.arange(t)%3!=1;lam=np.linspace(.3,2,t);beta=.25
   covariance=q/(1-rho*rho)*rho**np.abs(np.arange(t)[:,None]-np.arange(t));ix=np.where(mask)[0]
   observed=covariance[np.ix_(ix,ix)]+np.diag(r/lam[ix])
   expected=multivariate_normal.logpdf(y[ix],mean=beta*x[ix],cov=observed)
   self.assertAlmostEqual(filter_state(y,x,mask,beta,q,r,lam,rho)[2],expected,places=11)
 def test_missing_values_have_zero_effect_regular_grid(self):
  t=8;y=np.arange(t,dtype=float);x=y*.1;mask=np.arange(t)%2==0;lam=np.ones(t)
  before=filter_state(y,x,mask,.2,.01,.1,lam,.9)
  y[~mask]=np.nan;x[~mask]=np.nan
  after=filter_state(y,x,mask,.2,.01,.1,lam,.9)
  for a,b in zip(before,after):np.testing.assert_array_equal(a,b)
  self.assertGreater(before[1][1],before[1][0])
 def test_ffbs_mean_covariance_dense_oracle(self):
  t=5;rho=.9;q=.03;r=.1;y=np.array([.2,.5,-.1,.4,.1]);x=np.linspace(-1,1,t);mask=np.array([1,0,1,1,0],dtype=bool);lam=np.ones(t);beta=.2
  k=q/(1-rho*rho)*rho**np.abs(np.arange(t)[:,None]-np.arange(t));ix=np.where(mask)[0];s=k[np.ix_(ix,ix)]+r*np.eye(len(ix));mean=k[:,ix]@np.linalg.solve(s,(y-beta*x)[ix]);cov=k-k[:,ix]@np.linalg.solve(s,k[ix,:])
  seed_rng(731);samples=np.asarray([ffbs(y,x,mask,beta,q,r,lam,rho) for _ in range(20000)])
  self.assertTrue(np.all(np.abs(samples.mean(0)-mean)<6*np.sqrt(np.diag(cov)/len(samples))))
  np.testing.assert_allclose(np.cov(samples,rowvar=False),cov,atol=.0025,rtol=.04)
if __name__=='__main__':unittest.main()
