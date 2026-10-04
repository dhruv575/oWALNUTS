import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import reference_bank_allocation as r

class AllocationTests(unittest.TestCase):
    def plan(self):
        with patch.object(r,'versions',return_value={'numpy':'test','scipy':'test'}):return r.draft([])
    def test_complete_equal_information_design(self):
        p=self.plan();self.assertFalse(p['frozen']);self.assertEqual(len(p['cells']),148)
        for c in p['cells']:self.assertEqual(c['fits_per_backend']*c['lengths'][-1],32768)
        self.assertEqual(len({s for c in p['cells'] for s in c['fit_seeds']+c['init_seeds']+[c['bootstrap_seed']]}),sum(4*c['fits_per_backend']+1 for c in p['cells']))
    def test_reject_collisions_and_missing_cells(self):
        p=self.plan();p['reserved_seeds']=[p['cells'][0]['bootstrap_seed']]
        with self.assertRaises(ValueError):r.validate(p)
        p=self.plan();p['cells'][1]['init_seeds'][0]=p['cells'][0]['fit_seeds'][0]
        with self.assertRaises(ValueError):r.validate(p)
        p=self.plan();p['cells'].pop()
        with self.assertRaises(ValueError):r.validate(p)
    def test_projection_includes_worst_full_invocation(self):
        rows=[dict(status='completed',outer_seconds=v) for v in [1,2,3,4]]
        self.assertEqual(r.projection(rows),4*144*4)
        rows[0]['status']='failed';self.assertIsNone(r.projection(rows))
    def test_draft_cannot_execute(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'plan.json';r.save(path,self.plan())
            with self.assertRaisesRegex(ValueError,'Draft'):r.run(path,Path(d)/'output')
            self.assertFalse((Path(d)/'output').exists())
    def test_sentinel_failure_preserves_all_intended_statuses(self):
        p=self.plan();p['frozen']=True
        with tempfile.TemporaryDirectory() as d,patch.object(r,'verify_seed_audit'),patch.object(r,'versions',return_value=p['software']),patch.object(r.subprocess,'run',side_effect=RuntimeError('test worker failure')):
            path=Path(d)/'plan.json';r.save(path,p);out=Path(d)/'out';r.run(path,out)
            import json
            summary=json.loads((out/'summary.json').read_text())
            self.assertEqual(summary['expected'],148);self.assertEqual(summary['failed'],4);self.assertEqual(summary['not_started'],144)
    def test_wrong_sentinel_rejected(self):
        p=self.plan();p['cells'][1]['rho']=p['cells'][0]['rho'];p['cells'][1]['backend_b_shift']=p['cells'][0]['backend_b_shift']
        with self.assertRaisesRegex(ValueError,'sentinel'):r.validate(p)
    def test_historical_audit_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            inventory=Path(d)/'inventory.json';r.save(inventory,{'seeds':[12]})
            evidence=Path(d)/'audit.json';r.save(evidence,dict(status='complete',reserved_seeds=[12],inventory_files={str(inventory):r.sha(inventory)},search_scope='test-only inventory',auditor='unit test'))
            p=self.plan();p.update(reserved_seeds=[12],seed_audit=dict(path=str(evidence),sha256=r.sha(evidence)));r.verify_seed_audit(p)
            inventory.write_text('{}')
            with self.assertRaises(ValueError):r.verify_seed_audit(p)
    def test_child_memory_cap_and_reaped_exit(self):
        import subprocess,sys
        code="from reference_bank_allocation import memory_limit; handle=memory_limit(128*1024**2)\ntry:\n b=bytearray(256*1024**2)\nexcept MemoryError:\n print('limited')\nelse:\n raise AssertionError('cap ineffective')"
        child=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:out,err=child.communicate(timeout=20)
        except BaseException:child.kill();child.wait();raise
        self.assertEqual(child.returncode,0,err);self.assertIn('limited',out);self.assertIsNotNone(child.poll())
    def test_timeout_preserves_full_denominator_and_unknown_peak(self):
        import json,subprocess
        p=self.plan();p['frozen']=True
        with tempfile.TemporaryDirectory() as d,patch.object(r,'verify_seed_audit'),patch.object(r,'versions',return_value=p['software']),patch.object(r.subprocess,'run',side_effect=subprocess.TimeoutExpired('worker',1)):
            path=Path(d)/'plan.json';r.save(path,p);out=Path(d)/'out';r.run(path,out)
            summary=json.loads((out/'summary.json').read_text())
            self.assertEqual(summary['failed'],4);self.assertEqual(summary['not_started'],144)
            row=summary['rows'][0];self.assertIsNone(row['resources']['peak_committed_bytes'])
            cell=out/p['cells'][0]['id'];self.assertTrue((cell/'started.json').exists());self.assertTrue((cell/'exit.json').exists())
    def test_actual_analytic_worker_boundary(self):
        import json,subprocess,sys
        # Test-only small policy: two fits/backend, lengths32/64,240 bootstrap
        # resamples -> one expected tail draw. Never a production resolution claim.
        p=self.plan();p.update(bootstrap_replicates=240,minimum_tail_count=1)
        c=dict(p['cells'][0],fits_per_backend=2,lengths=[32,64],fit_seeds=[501,502,503,504],init_seeds=[601,602,603,604],bootstrap_seed=701)
        code="""
import json,sys
from pathlib import Path
sys.modules['psutil']=None
import reference_bank
original=reference_bank.analyze
def checked(spec,fits):
 for fit in fits:
  short=fit['levels']['32']['endpoints'];long=fit['levels']['64']['endpoints']
  assert short['lo'] is short['hi'] and long['lo'] is long['hi']
  assert short['lo']['draws']==long['lo']['draws'][:32]
 return original(spec,fits)
reference_bank.analyze=checked
from reference_bank_allocation import run_worker
p,c=json.loads(Path(sys.argv[1]).read_text());run_worker(p,c,Path(sys.argv[2]))
"""
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'input.json';r.save(path,[p,c]);out=Path(d)/'worker';out.mkdir()
            result=subprocess.run([sys.executable,'-c',code,str(path),str(out)],capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stderr)
            row=json.loads((out/'result.json').read_text());bank=json.loads((out/'bank.json').read_text());usage=json.loads((out/'resources.json').read_text())
            self.assertEqual(row['status'],'completed');self.assertAlmostEqual(row['truth'][0],-1.6448536269514722,places=12)
            self.assertAlmostEqual(row['truth'][1],1.6448536269514722,places=12)
            self.assertEqual(len(bank['joint_bootstrap_endpoints']),240)
            width=row['truth'][1]-row['truth'][0]
            self.assertAlmostEqual(row['max_endpoint_error_over_width'],max(abs(b['estimate']-t)/width for b,t in zip(row['bounds'],row['truth'])))
            self.assertGreater(usage['peak_resident_bytes'],0)
            if r.os.name=='nt':self.assertGreater(usage['peak_committed_bytes'],0);self.assertLessEqual(usage['peak_committed_bytes'],p['memory_bytes'])
if __name__=='__main__':unittest.main()



