import unittest
import numpy as np
from scipy.integrate import quad
from scipy.special import expit,log_ndtr
from scipy.stats import norm,t
from bounded_scale_sv import target


class BoundedTarget(unittest.TestCase):
    def test_normalized_transformed_prior(self):
        for cap in (.5,1.,2.):
            def density(eta):
                l=np.log(cap)-np.logaddexp(0.,eta)
                return np.exp(norm.logpdf(l,np.log(.2),.5)-log_ndtr((np.log(cap)-np.log(.2))/.5))*expit(eta)
            integral,error=quad(density,-40,40,epsabs=1e-11,epsrel=1e-11)
            self.assertAlmostEqual(integral,1.,places=10);self.assertLess(error,1e-10)

    def test_density_and_gradient_with_ties(self):
        for cap in (.5,1.,2.):
            for n in (1,4,12):
                y=np.zeros(n);q=np.r_[-10.,.7,.0001,np.linspace(-.3,.4,n)]
                value,g=target(q,y,cap)
                mu,eta,beta=q[:3];l=np.log(cap)-np.logaddexp(0.,eta);sigma=np.exp(l)
                h=np.empty(n);h[0]=mu+sigma*q[3]/np.sqrt(1-.95**2)
                for i in range(1,n):h[i]=mu+.95*(h[i-1]-mu)+sigma*q[3+i]
                expected=norm.logpdf(mu,2*np.log(.005),1)+norm.logpdf(l,np.log(.2),.5)-log_ndtr((np.log(cap)-np.log(.2))/.5)+np.log(expit(eta))+norm.logpdf(beta,0,.002)+norm.logpdf(q[3:]).sum()+t.logpdf(y,5,loc=beta,scale=np.exp(h/2)).sum()
                self.assertAlmostEqual(value,expected,places=10)
                for k in range(len(q)):
                    step=1e-8 if k==2 else 1e-5;delta=np.zeros(len(q));delta[k]=step
                    numerical=(target(q+delta,y,cap)[0]-target(q-delta,y,cap)[0])/(2*step)
                    np.testing.assert_allclose(g[k],numerical,rtol=2e-6,atol=2e-6)
                for eta in (-1000.,1000.):
                    q[1]=eta;v,g=target(q,y,cap);self.assertTrue(np.isfinite(v));self.assertTrue(np.isfinite(g).all())


if __name__=='__main__':unittest.main()
