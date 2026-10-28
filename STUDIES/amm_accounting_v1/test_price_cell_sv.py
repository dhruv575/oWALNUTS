import unittest
import numpy as np
from scipy.stats import norm,t
from scipy.special import expit
from price_cell_sv import target


class FullTarget(unittest.TestCase):
    def test_all_coordinates_and_normalization(self):
        for n in [1,4,12]:
            q=np.r_[2*np.log(.005),np.log(.2),.0003,np.linspace(-.8,.7,n),np.linspace(-2,2,n)]
            lower=np.zeros(n)-.0005;upper=np.zeros(n)+.0005
            value,grad=target(q,lower,upper,0.)
            # Separate direct recurrence and SciPy normalized densities.
            mu,l,beta=q[:3];z=q[3:3+n];u=q[3+n:];h=np.empty(n)
            h[0]=mu+np.exp(l)*z[0]/np.sqrt(1-.95**2)
            for i in range(1,n):h[i]=mu+.95*(h[i-1]-mu)+np.exp(l)*z[i]
            s=expit(u);x=lower+(upper-lower)*s
            expected=norm.logpdf(mu,2*np.log(.005),1)+norm.logpdf(l,np.log(.2),.5)+norm.logpdf(beta,0,.002)+norm.logpdf(z).sum()
            expected+=t.logpdf(np.diff(np.r_[0.,x]),5,loc=beta,scale=np.exp(h/2)).sum()
            expected+=np.log((upper-lower)*s*(1-s)).sum()
            self.assertAlmostEqual(value,expected,places=10)
            numerical=[]
            for j in range(len(q)):
                step=1e-8 if j==2 else 1e-5
                d=np.zeros(len(q));d[j]=step
                numerical.append((target(q+d,lower,upper,0.)[0]-target(q-d,lower,upper,0.)[0])/(2*step))
            np.testing.assert_allclose(grad,numerical,atol=2e-6,rtol=2e-6)


if __name__=='__main__':unittest.main()
