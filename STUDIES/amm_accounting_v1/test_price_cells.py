import unittest
import numpy as np
from scipy.integrate import quad
from scipy.stats import t
from price_cells import kernel


class CellContract(unittest.TestCase):
    def test_normalized_density_and_gradient(self):
        lower=np.array([-.1,-.1,.03]);upper=np.array([.1,.1,.3])
        u=np.array([-.7,.2,1.1]);h=np.array([-1.,.3,-.5]);beta=.02;initial=.04
        value,grad=kernel(u,lower,upper,initial,beta,h)
        s=1/(1+np.exp(-u));x=lower+(upper-lower)*s
        expected=np.sum(t.logpdf(np.diff(np.r_[initial,x]),5,loc=beta,scale=np.exp(h/2)))
        expected+=np.sum(np.log((upper-lower)*s*(1-s)))
        self.assertAlmostEqual(value,expected,places=12)
        finite=[]
        for i in range(3):
            d=np.zeros(3);d[i]=1e-5
            finite.append((kernel(u+d,lower,upper,initial,beta,h)[0]-kernel(u-d,lower,upper,initial,beta,h)[0])/2e-5)
        np.testing.assert_allclose(grad,finite,atol=2e-9,rtol=2e-9)

    def test_one_cell_probability(self):
        for lo,hi,beta,h in [(-.2,.2,0.,-1.),(.3,.9,-.1,.5),(-.001,.002,0.,-8.)]:
            actual,error=quad(lambda u:np.exp(kernel([u],[lo],[hi],0.,beta,[h])[0]),-50,50,epsabs=1e-11)
            expected=t.cdf(hi,5,loc=beta,scale=np.exp(h/2))-t.cdf(lo,5,loc=beta,scale=np.exp(h/2))
            self.assertLess(error,1e-8)
            self.assertAlmostEqual(actual,expected,places=10)

    def test_two_tied_cells_joint_probability(self):
        lo,hi=-.2,.2;scale=.3
        # Integrate the second transition analytically, then the first in price.
        expected=quad(lambda x:t.pdf(x,5,scale=scale)*(t.cdf(hi-x,5,scale=scale)-t.cdf(lo-x,5,scale=scale)),lo,hi,epsabs=1e-11)[0]
        h=[2*np.log(scale)]*2
        actual=quad(lambda u:quad(lambda v:np.exp(kernel([u,v],[lo,lo],[hi,hi],0.,0.,h)[0]),-30,30,epsabs=1e-10)[0],-30,30,epsabs=1e-10)[0]
        self.assertAlmostEqual(actual,expected,places=9)
        independent=(t.cdf(hi,5,scale=scale)-t.cdf(lo,5,scale=scale))**2
        self.assertGreater(abs(expected-independent),.001)

    def test_extreme_coordinates(self):
        for u in [-1000.,-40.,40.,1000.]:
            value,grad=kernel([u],[-.1],[.1],0.,0.,[-2.])
            self.assertTrue(np.isfinite(value));self.assertTrue(np.isfinite(grad).all())
            self.assertAlmostEqual(grad[0],1 if u<0 else -1,places=12)

    def test_invalid_cells(self):
        for lo,hi in [(0.,0.),(1.,0.),(0.,np.inf)]:
            with self.assertRaises(ValueError):kernel([0.],[lo],[hi],0.,0.,[0.])


if __name__=='__main__':unittest.main()
