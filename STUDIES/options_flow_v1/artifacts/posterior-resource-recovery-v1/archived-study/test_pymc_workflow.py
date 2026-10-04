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
        result=SimpleNamespace(samples=encode(expected),health=lambda:{'divergences':0},target_calls=5,config={'warmup':2},chains=[dict(metadata={},selected_refinement_level=np.zeros(5,dtype=int),work_discarded={},work_retained={},work_total={}) for _ in range(2)])
        events=[]
        with patch.object(workflow.owalnuts,'sample',return_value=result) as sample,patch('run_local_level.evaluate',return_value={'computational_screen_pass':True}) as evaluate:
            report,raw=workflow.sample_fit(None,fixture,starts,1,2,3,'observation_residual',phase_callback=lambda *event:events.append(event))
        np.testing.assert_array_equal(sample.call_args.kwargs['init'],encode(starts))
        np.testing.assert_allclose(raw['canonical_draws'],expected,atol=1e-14)
        np.testing.assert_array_equal(raw['initial_positions'],starts)
        np.testing.assert_allclose(evaluate.call_args.args[0],expected,atol=1e-14)
        self.assertEqual(raw['coordinates'],'observation_residual')
        self.assertEqual(events,[(stage,event,3) for stage in ['sampling','canonical_conversion','evaluation'] for event in ['start','end']])
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



class ScanParityRoutingTests(unittest.TestCase):
    def test_whitening_parity_uses_scan_density(self):
        import numpy as np
        import jax.numpy as jnp
        from unittest.mock import patch
        import local_conditional_whitening as guide
        import pymc_workflow as workflow
        point=np.array([.2,-2.,-1.])
        calls=[]
        def scan(q,data):
            calls.append(True)
            return -.5*jnp.sum(q*q)
        with patch.object(guide,'jax_log_density',side_effect=scan), patch.object(guide,'log_density',side_effect=AssertionError('Unrolled route must not run')), patch.object(workflow,'evaluate_cfunc',return_value=(-.5*np.sum(point*point),-point)):
            result=workflow.parity(None,{},[point],'conditional_whitening')
        self.assertTrue(result['passed']);self.assertTrue(calls)



class CompactChainWorkTests(unittest.TestCase):
    def test_warmup_retained_histograms_and_metadata(self):
        from types import SimpleNamespace
        import numpy as np
        import json
        from pymc_workflow import compact_chain_work
        chain=dict(selected_refinement_level=np.array([0,2,1,1,2]),
          work_discarded={'transitions':2,'refinement_exhaustion_stops':1},
          work_retained={'transitions':3,'refinement_exhaustion_stops':0},
          work_total={'transitions':5,'target_calls_total':np.int64(42)},
          metadata={'final_step_size':np.float64(.2),'final_mass':np.array([1.,2.])})
        out=compact_chain_work(SimpleNamespace(config={'warmup':2},chains=[chain]))
        row=out['chains'][0]
        self.assertEqual(row['selected_refinement_level_histogram'],{'warmup':{'0':1,'2':1},'retained':{'1':2,'2':1}})
        self.assertEqual(row['stop_counts']['warmup']['refinement_exhaustion_stops'],1)
        self.assertEqual(row['metadata']['final_mass'],[1.,2.]);json.dumps(out,allow_nan=False)

if __name__=='__main__':unittest.main()
