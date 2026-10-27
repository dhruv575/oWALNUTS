"""Deterministic fixtures only: no project observations, sampling, or scored artifacts."""
import math
import time
import unittest
from unittest.mock import patch
import numpy as np
from scipy.integrate import quad
from scipy.special import logsumexp,stdtr
from scipy.stats import norm,t
import predictive_density as pd

def draws(m,sigma,beta,chains=1):
    a=np.array([[mm,math.log(ss),bb,mm] for mm,ss,bb in zip(m,sigma,beta)])
    return a.reshape(chains,-1,4)

class PredictiveDensityChecks(unittest.TestCase):
    def test_exact_density_moment_and_center_cdf(self):
        m=np.array([-11.,-9.]);s=np.array([.2,.8]);a=draws(m,s,[.001,.001])
        r=pd.evaluate_observation(a,.001)
        exact=logsumexp(pd.LOG_C5-m/2+s*s/8)-math.log(2)
        self.assertAlmostEqual(r['logpdf'],exact,places=12)
        self.assertAlmostEqual(r['pit'],.5,places=14)
        np.testing.assert_allclose(r['logpdf_by_chain_draw'][0],pd.LOG_C5-m/2+s*s/8,atol=1e-12,rtol=0)
    def test_independent_density_cdf_quadrature(self):
        m=[-11.,-8.8];s=[.2,1.4];beta=[-.001,.002];y=.01
        r=pd.evaluate_observation(draws(m,s,beta),y)
        pdfs=[];cdfs=[]
        for mm,ss,bb in zip(m,s,beta):
            pdf,error=quad(lambda z:norm.pdf(z)*t.pdf(y,5,loc=bb,scale=np.exp((mm+ss*z)/2)),-12,12,epsabs=1e-11,epsrel=1e-11)
            cdf,cerror=quad(lambda z:norm.pdf(z)*stdtr(5,(y-bb)*np.exp(-(mm+ss*z)/2)),-12,12,epsabs=1e-12,epsrel=1e-12)
            tail=math.exp(pd.LOG_C5-mm/2+ss*ss/8)*(norm.cdf(-12+ss/2)+norm.cdf(-12-ss/2))
            self.assertLess(error+tail,1e-8);self.assertLess(cerror+2*norm.cdf(-12),1e-10)
            pdfs.append(pdf);cdfs.append(cdf)
        self.assertAlmostEqual(r['logpdf'],math.log(np.mean(pdfs)),places=8)
        self.assertAlmostEqual(r['pit'],np.mean(cdfs),places=9)
    def test_cdf_derivative_density_coherence(self):
        a=draws([-10.],[.4],[.001]);y=.002;r=pd.evaluate_observation(a,y)
        for eps in (1e-7,5e-8):
            lo=pd.evaluate_observation(a,y-eps)['pit'];hi=pd.evaluate_observation(a,y+eps)['pit']
            self.assertLess(abs((hi-lo)/(2*eps)/math.exp(r['logpdf'])-1),1e-7)
    def test_affine_and_permutation_and_chain_order(self):
        a=draws([-11.,-10.,-9.,-8.],[.2,.3,.4,.5],[-.002,-.001,.001,.002],chains=2)
        r=pd.evaluate_observation(a,.003,chunk=1)
        b=a.copy();factor=2.3;offset=.004;b[:,:,0]+=2*math.log(factor);b[:,:,3]+=2*math.log(factor);b[:,:,2]=factor*b[:,:,2]+offset
        transformed=pd.evaluate_observation(b,factor*.003+offset,chunk=3)
        self.assertAlmostEqual(transformed['logpdf'],r['logpdf']-math.log(factor),places=12)
        self.assertAlmostEqual(transformed['pit'],r['pit'],places=13)
        reordered=pd.evaluate_observation(a[::-1,::-1,:],.003)
        np.testing.assert_allclose(reordered['logpdf_by_chain_draw'],r['logpdf_by_chain_draw'][::-1,::-1],atol=1e-13,rtol=0)
        np.testing.assert_allclose(reordered['pit_by_chain_draw'],r['pit_by_chain_draw'][::-1,::-1],atol=1e-14,rtol=0)
        self.assertAlmostEqual(reordered['logpdf'],r['logpdf'],places=13)
    def test_small_innovation_and_extreme_log_density(self):
        a=draws([-10.],[1e-8],[.001]);y=.01;r=pd.evaluate_observation(a,y)
        self.assertAlmostEqual(r['logpdf'],t.logpdf(y,5,loc=.001,scale=math.exp(-5)),places=12)
        for y in (1e150,-1e150,1e308,-1e308):
            extreme=pd.evaluate_observation(draws([-10.],[.3],[0.]),y)
            self.assertTrue(np.isfinite(extreme['logpdf']))
            self.assertGreaterEqual(extreme['pit'],0);self.assertLessEqual(extreme['pit'],1)
        # Opposite-sign finite values whose difference overflows still have finite log distance.
        overflow=pd.evaluate_observation(draws([-10.],[.3],[-1e308]),1e308)
        self.assertTrue(np.isfinite(overflow['logpdf']))
    def test_correct_density_scaling_for_mcse(self):
        logs=np.array([[-1000.,-999.],[-998.,-997.]])
        r=pd.density_mcse_inputs(logs)
        self.assertEqual(r['scaled_density'].shape,logs.shape)
        self.assertAlmostEqual(r['log_mean_density'],logsumexp(logs)-math.log(4),places=12)
        shifted=pd.density_mcse_inputs(logs+700)
        np.testing.assert_array_equal(r['scaled_density'],shifted['scaled_density'])
        # Mean of logs is deliberately different from log of mean density.
        self.assertGreater(abs(r['log_mean_density']-logs.mean()),.1)
    def test_invalid_and_deadline_and_disagreement_fail_closed(self):
        a=draws([-10.],[.3],[0.])
        for bad in (np.nan,np.inf,-np.inf):
            with self.assertRaises(pd.NumericalFailure):pd.evaluate_observation(a,bad)
        with self.assertRaises(TimeoutError):pd.evaluate_observation(a,0.,deadline=time.monotonic()-1)
        for kw in ({'orders':(32,64)},{'chunk':0},{'chunk':True},{'nu':7},{'rho':1}):
            with self.assertRaises(pd.NumericalFailure):pd.evaluate_observation(a,0.,**kw)
        bad=a.copy();bad[0,0,1]=-1000
        with self.assertRaises(pd.NumericalFailure):pd.evaluate_observation(bad,0.)
        original=pd._evaluate_order
        def perturbed(*args,**kwargs):
            r=original(*args,**kwargs)
            if r['order']==64:r['logpdf']+=1e-3
            return r
        with patch.object(pd,'_evaluate_order',side_effect=perturbed):
            with self.assertRaises(pd.IntegrationDisagreement) as caught:pd.evaluate_observation(a,0.)
        self.assertGreater(caught.exception.diagnostics['logpdf_absolute_difference'],1e-6)
if __name__=='__main__':unittest.main()
