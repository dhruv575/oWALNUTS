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
if __name__=='__main__':unittest.main()

