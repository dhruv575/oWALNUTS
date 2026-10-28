import unittest
import numpy as np
from scipy.stats import norm,t
from scipy.special import log_ndtr
from bounded_scale_sv import target


class Envelope(unittest.TestCase):
    def test_joint_density_ratio(self):
        for cap in (.5,1.,2.):
            for eta in (-20.,0.,2.,20.):
                for y in (0.,.003):
                    q=np.array([-10.,eta,.0003,-.8]);mu,eta,beta,z=q
                    l=np.log(cap)-np.logaddexp(0.,eta);h=mu+np.exp(l)*z/np.sqrt(1-.95**2)
                    proposal=norm.logpdf(mu,2*np.log(.005),1)+norm.logpdf(l,np.log(.2),.5)-log_ndtr((np.log(cap)-np.log(.2))/.5)-np.logaddexp(0.,-eta)+norm.logpdf(z)+t.logpdf(beta,5,loc=y,scale=np.exp(h/2))
                    ratio=target(q,np.array([y]),cap)[0]-proposal
                    self.assertAlmostEqual(ratio,norm.logpdf(beta,0,.002),places=10)
                    self.assertLessEqual(ratio,norm.logpdf(0,0,.002))


if __name__=='__main__':unittest.main()
