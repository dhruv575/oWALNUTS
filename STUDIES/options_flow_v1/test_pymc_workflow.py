import importlib.util
import unittest
import numpy as np
from local_level import simulate,log_density

@unittest.skipUnless(importlib.util.find_spec('pymc') and importlib.util.find_spec('owalnuts'), 'Optional isolated PyMC workflow environment required')
class PyMCWorkflowTests(unittest.TestCase):
    def test_float64_normalization_and_generated_gradient(self):
        from pymc_workflow import compile_target,evaluate_cfunc
        fixture=simulate(71,4,1,prior=False);data=fixture['data'];q=np.asarray(fixture['truth'])
        target,_=compile_target(data);value,gradient=evaluate_cfunc(target,q)
        self.assertAlmostEqual(value,float(log_density(q,data)),places=10)
        step=1e-6;finite=[]
        for j in range(len(q)):
            direction=np.zeros_like(q);direction[j]=step
            finite.append((log_density(q+direction,data)-log_density(q-direction,data))/(2*step))
        np.testing.assert_allclose(gradient,finite,rtol=2e-6,atol=2e-6)
    def test_supplied_canonical_starts(self):
        from pymc_workflow import canonical_starts
        data=simulate(81,4,1)['data'];starts=np.arange(18,dtype=float).reshape(3,6)/10
        data['initial_positions']=starts.tolist()
        np.testing.assert_array_equal(canonical_starts(data,3),starts)
        with self.assertRaises(ValueError):canonical_starts(data,2)
if __name__=='__main__':unittest.main()
