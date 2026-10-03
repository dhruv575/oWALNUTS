import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from breadth import plan,run,summarize,_coverage,flow_initial_positions


class BreadthTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.binary=self.root/'worker.exe';self.binary.write_bytes(b'test-only')
        self.spec={'seeds':{model:[{'dataset_seed':base+i,'chain_seed':base+100+i} for i in range(24)]
                    for model,base in [('flow',1000),('local_level',2000)]},
                   'executables':{'flow':str(self.binary),'local_level':str(self.binary)},'cpus':[0]}
        for i,entry in enumerate(self.spec['seeds']['flow']):entry['init_seed']=3000+i
        self.snapshot={'python':{'model.py':'frozen'},'rust':{},'requirements_sha256':'frozen'}
        p=patch('breadth.source_snapshot',return_value=self.snapshot);p.start();self.addCleanup(p.stop)

    def test_plan_freezes_48_distinct_datasets_and_no_launch(self):
        out=self.root/'plan';manifest=plan(self.spec,out)
        self.assertEqual(len(manifest['cells']),48)
        self.assertFalse((out/'cells').exists())
        first=json.loads((out/manifest['cells'][0]['fixture']).read_text())
        self.assertEqual(len(first['data']['y']),128);self.assertEqual(len(first['data']['y'][0]),4)
        self.assertTrue(first['prior_predictive'])
        self.assertNotEqual(first['breadth_seed_contract']['chain_seed'],first['seed'])
        self.assertEqual(len(first['data']['initial_positions']),4)
        self.assertEqual(first['breadth_seed_contract']['init_seed'],3000)
        summary=summarize(out)
        self.assertEqual(summary['expected_cells'],48)
        self.assertEqual(summary['groups']['flow/autodiff-noncentered']['categories']['missing_not_started'],24)
        self.assertFalse(summary['qualified'])
        with self.assertRaises(FileExistsError):plan(self.spec,out)

    def test_six_reference_checks_declared_upfront(self):
        self.spec['reference_indices']={'flow':[0,1,2,3,4,5],'local_level':[0,1,2,3,4,5]}
        manifest=plan(self.spec,self.root/'plan')
        self.assertEqual(len(manifest['cells']),60)
        self.assertEqual(sum(c['reference'] for c in manifest['cells']),12)

    def test_duplicate_and_implicit_shared_seeds_rejected(self):
        self.spec['seeds']['flow'][0]['chain_seed']=self.spec['seeds']['flow'][0]['dataset_seed']
        with self.assertRaises(ValueError):plan(self.spec,self.root/'plan')

    def test_initialization_is_deterministic_dispersed_and_not_truth_based(self):
        import numpy as np
        data={'y':np.zeros((128,4)).tolist(),'rho':.95,'truth':[999]}
        a=flow_initial_positions(data,411)
        self.assertEqual(a,flow_initial_positions(data,411))
        self.assertNotEqual(a,flow_initial_positions(data,412))
        self.assertEqual(len({tuple(row) for row in a}),4)
        data['truth']=[-1e100];data['y']=np.full((128,4),1e100).tolist()
        self.assertEqual(a,flow_initial_positions(data,411))
        values=np.asarray(a)
        self.assertEqual(values.shape,(4,140));self.assertTrue(np.isfinite(values).all())
        # Smooth AR perturbations, not independent rough latent coordinates.
        self.assertLess(float(np.std(np.diff(values[:,12:],axis=1))),.1)
        from model import simulate,log_density
        fixture=simulate(17,8,2,1,True);q=np.asarray(fixture['truth'])
        before=log_density(q,fixture['data'])
        fixture['data']['initial_positions']=flow_initial_positions(fixture['data'],411)
        self.assertEqual(log_density(q,fixture['data']),before)

    def test_initialization_seed_collisions_and_unused_local_seed_rejected(self):
        self.spec['seeds']['flow'][0]['init_seed']=self.spec['seeds']['flow'][0]['chain_seed']+130000
        with self.assertRaises(ValueError):plan(self.spec,self.root/'plan')
        self.spec['seeds']['flow'][0]['init_seed']=self.spec['seeds']['local_level'][0]['dataset_seed']
        with self.assertRaises(ValueError):plan(self.spec,self.root/'plan')
        self.spec['seeds']['flow'][0]['init_seed']=3000
        self.spec['seeds']['local_level'][0]['init_seed']=4000
        with self.assertRaises(ValueError):plan(self.spec,self.root/'plan')

    def test_failed_execution_retained_and_never_replaced(self):
        out=self.root/'plan';manifest=plan(self.spec,out);cid=manifest['cells'][0]['id']
        def broken(*args,**kwargs):raise RuntimeError('mock failure, no sampler invoked')
        result=run(out,[cid],runner=broken)
        self.assertEqual(result[0]['status'],'failed')
        self.assertGreaterEqual(result[0]['cell_driver_seconds'],0.)
        summary=summarize(out)['groups']['flow/autodiff-noncentered']
        self.assertEqual(summary['expected'],24)
        self.assertEqual(summary['categories']['executor_failed'],1)
        self.assertEqual(summary['categories']['missing_not_started'],23)
        with self.assertRaises(FileExistsError):run(out,[cid],runner=broken)

    def test_source_manifest_and_fixture_binding(self):
        out=self.root/'plan';manifest=plan(self.spec,out);cid=manifest['cells'][0]['id']
        with patch('breadth.source_snapshot',return_value={}):
            with self.assertRaises(ValueError):run(out,[cid],runner=lambda *a,**k:None)
        (out/manifest['cells'][0]['fixture']).write_text('{}')
        calls=[]
        result=run(out,[cid],runner=lambda *a,**k:calls.append(1))
        self.assertEqual(calls,[]);self.assertEqual(result[0]['status'],'failed')
        self.assertIn('changed since plan',result[0]['error'])

    def test_both_six_truth_contracts_and_missing_predictive_truth(self):
        for model,names in [('flow',['beta_bar','tau','mu_h','sigma_h','h_terminal']),
                            ('local_level',['h_initial','h_terminal','h_mean','sigma_obs','sigma_rw'])]:
            row={'horizon':1,'lower':-1.,'upper':1.,'observed':0.}
            if model=='flow':row['group']=0
            report={'evaluation':{'functionals':{n:{'truth':0.,'interval_90':[-1.,1.]} for n in names},'forecast':{'rows':[row]}}}
            coverage,gaps=_coverage(report,model)
            self.assertEqual(len(coverage),6);self.assertFalse(gaps);self.assertTrue(all(coverage.values()))
            del row['observed'];self.assertEqual(len(_coverage(report,model)[1]),1)


if __name__=='__main__':unittest.main()
