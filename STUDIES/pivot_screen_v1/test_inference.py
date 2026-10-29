import unittest
import numpy as np
from scipy.integrate import quad
from scipy.special import expit
from models import Target
from inference import sample


class IndependentPosteriorTest(unittest.TestCase):
    def test_logistic_posterior_against_quadrature(self):
        import owalnuts
        t=Target('logistic',dict(X=np.ones((1,1)),y=np.array([8]),n=np.array([20]),prior_mean=np.zeros(1),prior_sd=np.ones(1)))
        norm=quad(lambda x:np.exp(t(np.array([x]))[0]),-12,12,epsabs=1e-12)[0]
        expected=quad(lambda x:expit(x)*np.exp(t(np.array([x]))[0]),-12,12,epsabs=1e-12)[0]/norm
        for i,m in enumerate(['nuts','walnuts']):
            draws,info=sample(t,m,549200000+i,500,750)
            values=np.ascontiguousarray(expit(draws));row=owalnuts.summary(values,['p'])[0]
            self.assertTrue(info['qualified'])
            self.assertLess(abs(values.mean()-expected),5*row['mcse_mean']+.002)


if __name__=='__main__':unittest.main()
