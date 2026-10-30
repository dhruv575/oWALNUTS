"""Qualification rejects failed references and precision errors, and preserves pairs."""
import unittest
import numpy as np
from analyze import accuracy,tuning_key,paired

class Tests(unittest.TestCase):
    def test_reference_gate_and_precision(self):
        s=dict(mean=[0.]*5,sd=[1.]*5,mcse=[.001]*5,diagnostic_pass=True)
        r=dict(status='ok',summary=s);ref=dict(qualified=False,summary=s)
        self.assertFalse(accuracy(r,ref,1,2)['pass_all']);ref['qualified']=True
        self.assertTrue(accuracy(r,ref,1,2)['pass_all'])
        bad=dict(r,summary=dict(s,mcse=[.02]*5))
        self.assertFalse(accuracy(bad,ref,1,2)['pass_all'])
        biased=dict(r,summary=dict(s,mean=[0.,0.,0.,0.,.1]))
        self.assertFalse(accuracy(biased,ref,1,2)['pass_all'])
    def test_selection_prefers_qualified(self):
        good=dict(status='ok',summary=dict(diagnostic_pass=True),seconds=100,config='a')
        bad=dict(status='ok',summary=dict(diagnostic_pass=False,mcse=[.0001],sd=[1]),seconds=1,config='b')
        self.assertLess(tuning_key(good),tuning_key(bad))
    def test_pairs_never_impute_failures(self):
        w={0:dict(seconds=2),1:dict(seconds=1)};n={0:dict(seconds=4),2:dict(seconds=10)}
        result=paired(w,n,'seconds');self.assertEqual(result['pairs'],1);self.assertEqual(result['geomean'],2.)
        self.assertEqual(paired({},n,'seconds')['pairs'],0)

if __name__=='__main__':unittest.main()
