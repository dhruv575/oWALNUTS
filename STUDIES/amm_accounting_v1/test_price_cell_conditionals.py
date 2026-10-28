import unittest
import numpy as np
from scipy.stats import t
from price_cell_conditionals import log_acceptance,sweep


class ConditionalTests(unittest.TestCase):
    def test_joint_ratios_all_neighbors(self):
        x=np.array([.02,-.03,.04]);h=np.array([-2.,-3.,-1.]);beta=.01;initial=-.01
        def joint(v):return t.logpdf(np.diff(np.r_[initial,v]),5,loc=beta,scale=np.exp(h/2)).sum()
        for i in range(3):
            for value in [-.1,0.,.12]:
                changed=x.copy();changed[i]=value
                difference=log_acceptance(value,i,x,h,beta,initial)-log_acceptance(x[i],i,x,h,beta,initial)
                self.assertAlmostEqual(difference,joint(changed)-joint(x),places=12)
                self.assertLessEqual(log_acceptance(value,i,x,h,beta,initial),0)

    def test_terminal_has_one_factor(self):
        value=.1;h=-2.;beta=.03
        expected=t.logpdf(value,5,loc=beta,scale=np.exp(h/2))-t.logpdf(beta,5,loc=beta,scale=np.exp(h/2))
        self.assertAlmostEqual(log_acceptance(value,0,[0.],[h],beta,0.),expected,places=12)

    def test_cap_does_not_mutate_input(self):
        x=np.array([0.,0.]);original=x.copy()
        with self.assertRaises(RuntimeError):sweep(x,[-2.,-2.],0.,0.,[-.1,-.1],[.1,.1],None,max_attempts=0)
        np.testing.assert_array_equal(x,original)


if __name__=='__main__':unittest.main()
