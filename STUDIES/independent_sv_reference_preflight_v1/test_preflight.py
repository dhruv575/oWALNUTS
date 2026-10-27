import unittest
import numpy as np
from common import fixture,extract,require_finite
class Array:
 def __init__(self,a):self.a=a
 def transpose(self,*args):return self.a
class Posterior(dict):pass
class Trace:pass
def trace():
 t=Trace();t.posterior=Posterior({k:Array(np.zeros((4,50),dtype=np.float64)) for k in ('mu','log_sigma','beta','h_last')});t.posterior.coords={'chain':np.arange(4)}
 t.sample_stats=type('Stats',(),{'diverging':Array(np.zeros((4,50),dtype=bool))})();return t
class Tests(unittest.TestCase):
 def test_nonfinite_comparison(self):
  for value in (np.nan,np.inf,-np.inf,[0,np.nan]):
   with self.assertRaises(ValueError):require_finite(value)
  require_finite(0.,[1.,2.])
 def test_literals(self):
  for n in (12,250):
   for v in (0,1,-1):
    y,q=fixture(n,v);self.assertEqual(y.shape,(n,));self.assertEqual(q.shape,(n+3,));self.assertTrue(np.isfinite(q).all())
 def test_extract(self):
  a,d=extract(trace());self.assertEqual(a.shape,(4,50,4));self.assertEqual(d['chain_ids'],[0,1,2,3])
 def test_reject_lossy(self):
  t=trace();t.posterior['beta']=Array(np.zeros((4,50),dtype=np.float32))
  with self.assertRaises(ValueError):extract(t)
 def test_reject_identity(self):
  t=trace();t.posterior.coords['chain']=[0,0,1,2]
  with self.assertRaises(ValueError):extract(t)
 def test_reject_divergence(self):
  t=trace();t.sample_stats.diverging=Array(np.full((4,50),np.nan))
  with self.assertRaises(ValueError):extract(t)
if __name__=='__main__':unittest.main()
