import unittest
import numpy as np
from scipy.stats import t
from price_cell_conditionals import log_acceptance,sweep,cell_log_envelope


class ConditionalTests(unittest.TestCase):
    def test_cell_bound_and_unchanged_ratios(self):
        x=np.array([-.2,.03,.4]);h=np.array([-15.,-12.,-18.]);beta=.01
        for i in range(3):
            lo=x[i]-.0005;hi=x[i]+.0005
            bound=cell_log_envelope(i,x,h,beta,0.,lo,hi)
            self.assertLessEqual(bound,0.)
            vals=[log_acceptance(v,i,x,h,beta,0.) for v in np.linspace(lo,hi,101)]
            self.assertTrue(all(v<=bound+1e-10 for v in vals))
            self.assertAlmostEqual((vals[17]-bound)-(vals[81]-bound),vals[17]-vals[81],places=12)
            self.assertGreater(bound,-1000.)
        # A far-from-mode narrow cell makes the old peak envelope wasteful.
        bound=cell_log_envelope(1,x,h,beta,0.,.0295,.0305)
        self.assertLess(bound,-30.)
        self.assertGreater(log_acceptance(.03,1,x,h,beta,0.)-bound,-1.)

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
