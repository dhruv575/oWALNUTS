import unittest
import numpy as np
from scipy.special import log_ndtr
from scipy.stats import norm,t
from bounded_scale_slice import physical,likelihood,ellipse
from bounded_scale_sv import target


class PriorCoordinates(unittest.TestCase):
    def test_change_of_variables_and_likelihood(self):
        for cap in (.5,1.,2.):
            for n in (1,4,12):
                core=np.linspace(-.8,.7,3+n);y=np.zeros(n)
                p=physical(core,cap);mu,l,beta=p[:3];sigma=np.exp(l)
                h=np.empty(n);h[0]=mu+sigma*p[3]/np.sqrt(1-.95**2)
                for i in range(1,n):h[i]=mu+.95*(h[i-1]-mu)+sigma*p[3+i]
                self.assertAlmostEqual(likelihood(core,y,cap),t.logpdf(y,5,loc=beta,scale=np.exp(h/2)).sum(),places=10)
                gap=np.log(cap)-l;eta=gap+np.log(-np.expm1(-gap));q=p.copy();q[1]=eta
                standardized=(l-np.log(.2))/.5
                logjac=np.log(.002)+np.log(.5)+log_ndtr((np.log(cap)-np.log(.2))/.5)+norm.logpdf(core[1])-norm.logpdf(standardized)+np.logaddexp(0.,-eta)
                actual=target(q,y,cap)[0]+logjac
                expected=norm.logpdf(core).sum()+likelihood(core,y,cap)
                self.assertAlmostEqual(actual,expected,places=9)

    def test_block_ownership_and_validation(self):
        core=np.array([.2,-.3,.1,.4,-.2]);saved=core.copy();rng=np.random.default_rng(19)
        new,count=ellipse(core,np.zeros(2),1.,rng,np.array([1,3]))
        np.testing.assert_array_equal(core,saved);np.testing.assert_array_equal(new[[0,2,4]],core[[0,2,4]])
        self.assertGreaterEqual(count,1);self.assertTrue(np.isfinite(new).all())
        with self.assertRaises(ValueError):ellipse(core,np.zeros(2),1.,rng,np.array([1,1]))
        for w in (-40.,40.):
            core[1]=w;p=physical(core,1.);self.assertTrue(np.isfinite(p).all());self.assertLessEqual(p[1],0.)


if __name__=='__main__':unittest.main()
