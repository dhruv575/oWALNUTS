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
    def test_residual_dispatch_and_transport(self):
        from pymc_workflow import compile_target,parity,canonical_starts,coordinate_transport
        from continuation_precision import local_configuration
        data=simulate(91,4,1,prior=False)['data']
        starts=canonical_starts(data,3);data['initial_positions']=starts.tolist()
        target,metadata=compile_target(data,'observation_residual')
        encode,decode=coordinate_transport(data,'observation_residual')
        u=encode(starts)
        self.assertEqual(metadata['coordinates'],'observation_residual')
        self.assertTrue(parity(target,data,list(u),'observation_residual')['passed'])
        initial,reference_starts,potential,canonical=local_configuration(data,3,'observation_residual')
        np.testing.assert_array_equal(initial,starts)
        np.testing.assert_array_equal(reference_starts,u)
        np.testing.assert_allclose(canonical(u[:,None,:])[:,0,:],starts,atol=1e-14)
        np.testing.assert_allclose(decode(u),starts,atol=1e-14)
        for coordinates in ['bad','noncentered']:
            with self.assertRaises(ValueError):coordinate_transport(data,coordinates)
            with self.assertRaises(ValueError):local_configuration(data,3,coordinates)

    def test_sample_fit_returns_canonical_raw(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        import pymc_workflow as workflow
        fixture=simulate(92,4,1,prior=False);data=fixture['data']
        starts=workflow.canonical_starts(data,2)
        encode,_=workflow.coordinate_transport(data,'observation_residual')
        expected=np.repeat(starts[:,None,:],3,axis=1)
        result=SimpleNamespace(samples=encode(expected),health=lambda:{'divergences':0},target_calls=5)
        with patch.object(workflow.owalnuts,'sample',return_value=result) as sample,patch('run_local_level.evaluate',return_value={'computational_screen_pass':True}) as evaluate:
            report,raw=workflow.sample_fit(None,fixture,starts,1,2,3,'observation_residual')
        np.testing.assert_array_equal(sample.call_args.kwargs['init'],encode(starts))
        np.testing.assert_allclose(raw['canonical_draws'],expected,atol=1e-14)
        np.testing.assert_array_equal(raw['initial_positions'],starts)
        np.testing.assert_allclose(evaluate.call_args.args[0],expected,atol=1e-14)
        self.assertEqual(raw['coordinates'],'observation_residual')
    def test_reference_rejects_flow_residual_before_output(self):
        from unittest.mock import patch
        from contextlib import redirect_stderr
        import io
        import continuation_precision
        argv=['continuation_precision','--fixture','unused','--out','unused',
              '--model','flow','--coordinates','observation_residual','--seed','1']
        with patch('sys.argv',argv),redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as error:
            continuation_precision.main()
        self.assertEqual(error.exception.code,2)
if __name__=='__main__':unittest.main()
