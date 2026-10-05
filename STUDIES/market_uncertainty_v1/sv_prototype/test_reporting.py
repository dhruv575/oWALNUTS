import unittest
from unittest.mock import patch
import numpy as np
from target import Target,Priors
import reporting
PR= Priors(-10.,1.,-1.5,.5,.002,.03)
class ReportingTests(unittest.TestCase):
 def test_exact_terminal_short_missing_ablations(self):
  rng=np.random.default_rng(842)
  for n,k in [(1,0),(2,2),(33,2)]:
   mask=np.arange(n)%3!=1;m=Target(np.zeros(n),np.ones((n,1)),rng.normal(size=(n,k)),mask,rho=-.6,nu=5.,priors=PR)
   q=rng.normal(size=(4,9,m.dimension))*.1;q[:,:,0]-=10;q[:,:,1]-=1.5
   original=q.copy();expected=np.array([[m.path(v)[-1] for v in chain] for chain in q]);np.testing.assert_array_equal(reporting.terminal_path(q,m),expected);np.testing.assert_array_equal(q,original)
 def test_rng_and_complete_summary_exact_oracle(self):
  rng=np.random.default_rng(843);m=Target(np.zeros(4),np.ones((4,1)),rng.normal(size=(4,2)),[True,False,True,True],rho=.9,nu=5.,priors=PR)
  q=rng.normal(size=(4,500,m.dimension))*.1;q[:,:,0]-=10;q[:,:,1]-=1.5;future=dict(x=[1.],w=[.2,-.1])
  actual=reporting.summarize(q,m,future,predictive_seed=6501)
  with patch.object(reporting,'terminal_path',side_effect=lambda a,b:np.array([[b.path(v)[-1] for v in chain] for chain in a])):expected=reporting.summarize(q,m,future,predictive_seed=6501)
  import json
  convert=lambda x:json.dumps(x,sort_keys=True,default=lambda a:a.tolist())
  self.assertEqual(convert(actual),convert(expected))
 def test_constant_later_coordinate_fails(self):
  a=np.random.default_rng(844).normal(size=(4,500,3));a[:,:,1]=1.
  self.assertFalse(reporting.diagnostics(a)['all_finite'])
 def test_invalid_shape(self):
  m=Target([0.],np.ones((1,1)),np.empty((1,0)),[True],rho=.9,nu=5.,priors=PR)
  with self.assertRaises(ValueError):reporting.terminal_path(np.zeros((4,5,m.dimension+1)),m)
if __name__=='__main__':unittest.main()
