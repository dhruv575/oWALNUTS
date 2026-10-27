import unittest
import numpy as np
from scipy.special import ndtri
from scale_functional import evaluate_scale
from query_grid import query_grid
class FunctionalFixtures(unittest.TestCase):
 def test_scale_terminal_column_not_beta(self):
  a=np.zeros((4,8,4));a[:,:,0]=-10.;a[:,:,1]=np.log(.2);a[:,:,2]=123.;a[:,:,3]=-9.8
  result=evaluate_scale(a,mean_mcse=lambda v:0.)
  expected=np.exp((-10.+.95*.2+.2*ndtri([.5,.95]))/2)
  np.testing.assert_allclose(result['quantiles'],expected,rtol=1e-12)
  a[:,:,2]=-987.;other=evaluate_scale(a,mean_mcse=lambda v:0.)
  self.assertEqual(result['quantiles'],other['quantiles']);self.assertEqual(result['joint_columns'],[0,1,3])
 def test_scale_rejects_nonfinite_mcse(self):
  a=np.zeros((4,8,4));a[:,:,1]=np.log(.2)
  with self.assertRaises(ValueError):evaluate_scale(a,mean_mcse=lambda v:float('nan'))
 def test_grid_exact_population_standardization(self):
  window=np.arange(250,dtype=float);r=query_grid(window)
  np.testing.assert_array_equal(r['queries'],window.mean()+window.std(ddof=0)*np.array([-2,-1,0,1,2]))
  with self.assertRaises(ValueError):query_grid(np.ones(250))
if __name__=='__main__':unittest.main()
