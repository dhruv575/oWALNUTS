import unittest
import numpy as np
from scipy.stats import norm
from price_cell_slice import physical,likelihood,ellipse
from price_cell_sv import target


class SliceContract(unittest.TestCase):
    def test_likelihood_prior_jacobian_identity(self):
        for n in [1,4,12]:
            c=np.linspace(-.4,.5,n+3);q=physical(c);u=np.linspace(-1,1,n)
            lo=np.full(n,-.001);hi=np.full(n,.001);s=1/(1+np.exp(-u));x=lo+(hi-lo)*s
            lp=likelihood(c,x)[0]
            prior=norm.logpdf(q[:3],[2*np.log(.005),np.log(.2),0.],[1.,.5,.002]).sum()+norm.logpdf(q[3:]).sum()
            jac=np.log((hi-lo)*s*(1-s)).sum()
            actual=target(np.r_[q,u],lo,hi,0.)[0]
            self.assertAlmostEqual(actual,lp+prior+jac,places=10)

    def test_attempt_cap_preserves_input(self):
        c=np.zeros(4);before=c.copy()
        with self.assertRaises(RuntimeError):ellipse(c,[0.],np.random.default_rng(17),max_attempts=0)
        np.testing.assert_array_equal(c,before)


if __name__=='__main__':unittest.main()
