import unittest,tempfile,types
from pathlib import Path
from compiler_capture import capture_compiler
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
 def test_compiler_capture(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);source=root/'original.so';source.write_bytes(b'literal binary fixture');calls=[]
   def original(*args,**kwargs):calls.append((args,kwargs));return source
   module=types.SimpleNamespace(compile_model=original);records=[]
   with capture_compiler(module,root/'capture',records):
    self.assertEqual(module.compile_model('literal',make_args=['unchanged']),source)
   self.assertIs(module.compile_model,original);self.assertEqual(calls,[(('literal',),{'make_args':['unchanged']})]);self.assertEqual(Path(records[0]['copy_path']).read_bytes(),source.read_bytes())
 def test_compiler_restore_failure(self):
  with tempfile.TemporaryDirectory() as folder:
   def original():raise RuntimeError('literal failure')
   module=types.SimpleNamespace(compile_model=original)
   with self.assertRaises(RuntimeError):
    with capture_compiler(module,Path(folder)/'capture',[]):module.compile_model()
   self.assertIs(module.compile_model,original)
 def test_capture_invalid_output(self):
  with tempfile.TemporaryDirectory() as folder:
   def original():return Path(folder)/'missing.so'
   module=types.SimpleNamespace(compile_model=original)
   with self.assertRaises(ValueError):
    with capture_compiler(module,Path(folder)/'capture',[]):module.compile_model()
   self.assertIs(module.compile_model,original)
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
