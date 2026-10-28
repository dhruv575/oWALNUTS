import unittest
import numpy as np
from blocked_path import conditional,update_path
from development import Target,Priors,EvaluationBudget
from hybrid import augmented_log_density


class BlockTests(unittest.TestCase):
    def test_conditional_ratios_equal_complete_ar_prior(self):
        for n,lo,hi in [(1,0,1),(7,0,3),(7,2,5),(7,4,7),(7,0,7),(250,240,250)]:
            h=np.linspace(-11.,-9.,n);mu=-10.;sigma=.3;rho=.95
            mean,lower,transform=conditional(h,mu,sigma,rho,lo,hi)
            candidate=h.copy();candidate[lo:hi]+=.17
            def prior(a):return -.5*((1-rho*rho)*(a[0]-mu)**2+np.sum((a[1:]-mu-rho*(a[:-1]-mu))**2))/sigma**2
            a=lower.T@(h[lo:hi]-mean)/sigma;b=lower.T@(candidate[lo:hi]-mean)/sigma
            self.assertAlmostEqual(prior(candidate)-prior(h),-.5*(b@b-a@a),places=10)
            np.testing.assert_allclose(transform@lower.T,np.eye(hi-lo)*sigma,atol=1e-14)

    def test_update_does_not_mutate_input_or_globals(self):
        n=7;model=Target(np.linspace(-.002,.003,n),np.ones((n,1)),np.empty((n,0)),np.ones(n,dtype=bool),rho=.95,nu=5,priors=Priors(-10,1,-1.6,.5,.002,.03))
        q=np.r_[-10.,-1.6,0.,np.zeros(n)];before=q.copy()
        changed=update_path(model,q,np.ones(n),np.random.default_rng(90),EvaluationBudget(),block_size=3)
        np.testing.assert_array_equal(q,before);np.testing.assert_array_equal(changed[:3],q[:3])
        self.assertTrue(np.isfinite(changed).all());self.assertFalse(np.array_equal(changed[3:],q[3:]))

    def test_block_density_ratio_matches_full_augmented_target(self):
        n=7;rho=.95;sigma=.2;mu=-10.
        model=Target(np.linspace(-.002,.003,n),np.ones((n,1)),np.empty((n,0)),np.array([True,False,True,True,True,False,True]),rho=rho,nu=5,priors=Priors(-10,1,-1.6,.5,.002,.03))
        q=np.r_[mu,np.log(sigma),.0001,np.linspace(-.5,.5,n)];h=model.path(q);lam=np.linspace(.5,1.5,n)
        for lo,hi in [(0,3),(2,5),(4,7)]:
            mean,lower,_=conditional(h,mu,sigma,rho,lo,hi)
            candidate=h.copy();candidate[lo:hi]+=.15
            changed=q.copy();changed[3]=np.sqrt(1-rho*rho)*(candidate[0]-mu)/sigma
            changed[4:]=(candidate[1:]-mu-rho*(candidate[:-1]-mu))/sigma
            def local(a):
                white=lower.T@(a[lo:hi]-mean)/sigma;obs=model.observed[lo:hi]
                hh=a[lo:hi][obs];r=(model.y[lo:hi]-q[2])[obs]
                return -.5*(white@white)+np.sum(-.5*hh-.5*lam[lo:hi][obs]*r*r*np.exp(-hh))
            self.assertAlmostEqual(local(candidate)-local(h),augmented_log_density(model,changed,lam)-augmented_log_density(model,q,lam),places=10)


if __name__=='__main__':unittest.main()
