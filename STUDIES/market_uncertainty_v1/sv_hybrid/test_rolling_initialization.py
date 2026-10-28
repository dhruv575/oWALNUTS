import unittest
import numpy as np
from rolling_initialization import physical_path,remap,initialization_center

class InitializationTests(unittest.TestCase):
    def test_preserves_overlap_globals_and_input(self):
        q=np.r_[-10.,np.log(.2),.001,np.linspace(-2,3,250)];before=q.copy()
        h=physical_path(q);mapped=remap(q);new=physical_path(mapped)
        np.testing.assert_allclose(new[:-1],h[1:],atol=1e-12)
        self.assertAlmostEqual(new[-1],q[0]+.95*(h[-1]-q[0]))
        np.testing.assert_array_equal(q,before);np.testing.assert_array_equal(mapped[:3],q[:3])
    def test_center_uses_each_remapped_terminal_state(self):
        q=np.zeros((4,253));q[:,0]=[-11,-10,-9,-8];q[:,1]=np.log([.1,.2,.3,.4]);q[:,3:]=np.arange(250)/250
        center,mapped=initialization_center(q)
        np.testing.assert_allclose(center,np.stack([remap(row) for row in q]).mean(axis=0))
        self.assertEqual(mapped.shape,(4,253))
        with self.assertRaises(ValueError):initialization_center(q[:3])
