import unittest
import numpy as np
from worker import diagnostics,summary
from target import Target,Priors
class FiniteGate(unittest.TestCase):
 def test_constant_later_coordinate_cannot_hide_behind_finite_first(self):
  rng=np.random.default_rng(714);q=rng.normal(size=(4,500,3));q[:,:,1]=0.
  d=diagnostics(q);self.assertFalse(d['all_finite']);self.assertFalse(d['all_parameters'][1]['all_finite'])
  m=Target([0.],np.empty((1,0)),np.empty((1,0)),[True],rho=.5,nu=5.,priors=Priors(-10,1,-1.5,.5,.02,.03))
  q[:,:,0]=-10+q[:,:,0]*.1
  result=summary(q,m,dict(future=dict(x=[],w=[])));self.assertFalse(result['healthy']);self.assertFalse(result['precision_pass'])
 def test_finite_normal_arrays(self):
  self.assertTrue(diagnostics(np.random.default_rng(715).normal(size=(4,500,3)))['all_finite'])
if __name__=='__main__':unittest.main()
