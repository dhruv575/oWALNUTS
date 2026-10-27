"""Deterministic fixtures/mocks only: no study RNG, sampler, or observed outcomes."""
import math,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
import numpy as np
import generator,baseline
from stream_driver import run_stream
from resident_adapter import DrawResident
from sentinel_adapter import log_density_mcse,stan_data,api_inventory
from watchdog import supervise

class FixtureTests(unittest.TestCase):
    def test_generator_shape_and_rng_order_without_rng(self):
        calls=[]
        class Fake:
            def normal(self,*args,**kwargs):
                calls.append(('normal',args,kwargs));return np.zeros(kwargs['size']) if 'size' in kwargs else args[0]
            def standard_t(self,*args,**kwargs):calls.append(('t',args,kwargs));return np.zeros(kwargs['size'])
        data=generator.generate(0,rng_factory=lambda seed:Fake())
        self.assertEqual(len(calls),5);self.assertEqual(data['y'].shape,(283,));self.assertEqual(data['h'].shape,(283,))
        self.assertEqual(calls[-1],('t',(5,),{'size':283}))
        np.testing.assert_array_equal(data['y'],np.zeros(283))
    def fixture(self):return dict(stream=0,seeds=dict(data=1,initial=2,warm=3),parameters=dict(mu=4.,log_sigma=5.,beta=6.),y=np.arange(283,dtype=float),h=np.arange(283,dtype=float)+1000)
    def test_causal_windows_and_extra_final_label(self):
        d=self.fixture();a=generator.tick_inputs(d,1);b=generator.tick_inputs(d,32)
        self.assertEqual((a['current_index'],a['label_index']),(250,251));self.assertEqual((b['current_index'],b['label_index']),(281,282))
        self.assertEqual(a['current_latent'],1250);self.assertEqual(b['current_latent'],1281)
        np.testing.assert_array_equal(a['window'],np.arange(1,251));np.testing.assert_array_equal(b['window'],np.arange(32,282))
    def test_driver_all_planned_and_oracle_only_current_latent(self):
        d=self.fixture();engine=Mock();engine.advance.return_value=(np.zeros((4,400,4)),{'seed':3});seen=[]
        def oracle(params,current,label):seen.append((current,label));return dict(cdf=.5,logpdf=0.)
        result=run_stream(d,lambda initial,seeds:engine,lambda draws,label:dict(cdf=.5,logpdf=0.),oracle,lambda r,a:None)
        self.assertEqual(result['status'],'complete');self.assertEqual(result['valid_ticks'],32);self.assertEqual(result['unattempted_ticks'],[])
        self.assertEqual(seen[0],(1250,251));self.assertEqual(seen[-1],(1281,282));engine.close.assert_called_once()
    def test_failure_keeps_attempted_and_unattempted_denominator(self):
        engine=Mock();engine.advance.return_value=(np.zeros((4,400,4)),{})
        result=run_stream(self.fixture(),lambda initial,seeds:engine,lambda a,y:dict(cdf=float('nan'),logpdf=0.),lambda *a:None,lambda r,a:None)
        self.assertEqual(result['status'],'failed');self.assertEqual(len(result['rows']),1);self.assertEqual(result['rows'][0]['phase'],'evaluate');self.assertEqual(result['valid_ticks'],0);self.assertEqual(len(result['unattempted_ticks']),31)
        self.assertEqual(engine.advance.call_count,1);engine.close.assert_called_once()
    def test_initialization_failure_never_replaces_stream(self):
        factory=Mock(side_effect=RuntimeError('hard case'))
        r=run_stream(self.fixture(),factory,Mock(),Mock(),lambda r,a:None)
        self.assertEqual(r['status'],'failed');self.assertEqual(r['unattempted_ticks'],list(range(1,33)));factory.assert_called_once()
    def test_resident_retarget_failure_poison_no_window_commit(self):
        r=DrawResident.__new__(DrawResident);r.closed=False;r.y=np.arange(250.);r.compiled=None;r.session=Mock();r.session.retarget.side_effect=RuntimeError('retarget')
        r.targets=Mock();r.targets.remap.return_value=None;r.targets.TargetOwner.return_value=Mock(target=None)
        with self.assertRaises(RuntimeError):r.advance(250.,400)
        self.assertTrue(r.closed);np.testing.assert_array_equal(r.y,np.arange(250.));r.session.refresh_functionals.assert_not_called()
        with self.assertRaises(RuntimeError):r.advance(251.,400)
    def test_logscore_mcse_target_is_log_mean_density(self):
        a=np.log(np.array([[1.,9.],[1.,9.]]));r=log_density_mcse(a,lambda scaled:.1)
        self.assertAlmostEqual(r['log_predictive_density'],math.log(5.));self.assertAlmostEqual(r['delta_mcse'],.1/(5/9));self.assertNotAlmostEqual(r['log_predictive_density'],float(a.mean()))
    def test_baseline_full_window_no_future_leakage(self):
        a=baseline.score(np.zeros(250),.001);b=baseline.score(np.zeros(250),-.001)
        self.assertEqual(a['training_pairs'],249);self.assertEqual(a['df'],255);self.assertAlmostEqual(a['cdf']+b['cdf'],1.);self.assertEqual(a['scale'],b['scale']);self.assertAlmostEqual(a['logpdf'],b['logpdf'])
        with self.assertRaises(ValueError):baseline.score(np.zeros(249),0.)
    def test_reference_preflight_does_not_promise_missing_api(self):
        with self.assertRaises(ValueError):api_inventory(object())
        self.assertEqual(stan_data(np.zeros(250))['n'],250)
        with self.assertRaises(ValueError):stan_data(np.zeros(251))
    def test_draft_watchdog_never_executes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'draft.json';p.write_text('{"status":"draft"}')
            with self.assertRaises(ValueError):supervise(p,Path(tmp)/'out')
            self.assertFalse((Path(tmp)/'out').exists())
if __name__=='__main__':unittest.main()
