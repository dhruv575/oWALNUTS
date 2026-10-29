import unittest
import numpy as np
from targets import Target
from native_check import Native,sample,CONFIGS


class NativeTests(unittest.TestCase):
    def test_abi_densities_gradients_and_counters(self):
        t=Target('banana');owner=Native(t)
        for q in t.initial():
            status,lp,g,other,h=owner.values(q);expected,gradient=t(q)
            self.assertEqual(status,0);self.assertAlmostEqual(lp,expected);self.assertAlmostEqual(other,expected)
            np.testing.assert_array_equal(g,gradient);np.testing.assert_array_equal(h,gradient)
        self.assertEqual(owner.counter[0],8);self.assertEqual(owner.counter[1],0)

    def test_all_native_adapters_on_known_normal(self):
        for i,config in enumerate(CONFIGS):
            t=Target('isotropic');owner=Native(t);q,info=sample(t,owner,config,685000000+i,1000)
            self.assertEqual(q.shape,(4,1000,12));self.assertEqual(info['nonfinite_calls'],0)
            self.assertLess(np.max(abs(q.mean(axis=(0,1)))),.12)
            self.assertLess(np.max(abs(q.var(axis=(0,1))-1)),.18)


if __name__=='__main__':unittest.main()
