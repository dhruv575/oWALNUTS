import unittest
import numpy as np
from scipy.integrate import quad
from scipy.special import stdtr
from price_cell_predictive import conditional_cdf,last_volatility


class Predictive(unittest.TestCase):
    def test_independent_quadrature_and_limits(self):
        for sigma in (0.,.2,2.):
            for threshold in (-.005,0.,.005):
                mu=-10.;beta=.0002;last=-9.
                def integrand(z):
                    h=mu+.95*(last-mu)+sigma*z
                    return stdtr(5,(threshold-beta)*np.exp(-h/2))*np.exp(-z*z/2)/np.sqrt(2*np.pi)
                expected,error=quad(integrand,-12,12,epsabs=1e-12,epsrel=1e-12)
                self.assertLess(error,1e-10)
                self.assertAlmostEqual(float(conditional_cdf(threshold,mu,sigma,beta,last,order=128)),expected,places=9)
        np.testing.assert_allclose(conditional_cdf(.0002,-10.,np.array([0.,1.,5.]),.0002,-9.),.5,atol=1e-15)

    def test_terminal_volatility(self):
        q=np.r_[-10.,np.log(.2),0.,[1.,2.,3.],[0.,0.,0.]]
        expected=-10.+.2*(.95**2/np.sqrt(1-.95**2)+.95*2+3)
        self.assertAlmostEqual(float(last_volatility(q)),expected,places=13)


if __name__=='__main__':unittest.main()
