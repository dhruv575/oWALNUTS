"""Static authored planner contracts; no generation, freezing or numerical imports."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import optimized_mixed_comparison_plan as p

class OptimizedMixedPlanTests(unittest.TestCase):
    def test_six_fresh_paired_cells_and_associative_routing(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);python=root/'python.exe';python.write_text('mock')
            package=root/'package';(package/'owalnuts').mkdir(parents=True)
            for n in ['__init__.py','_owalnuts.pyd']:(package/'owalnuts'/n).write_text('mock')
            att=root/'att.json';p.save(att,{})
            fixture=root/'fixture.json';p.save(fixture,{'existing':'no generation'})
            inventory=root/'old.json';p.save(inventory,{'seed':13})
            audit=root/'audit.json';p.save(audit,dict(status='passed',seeds=p.SEEDS+[s+130000 for s in p.SEEDS],hits=[],scope='test inventory',auditor='unit test',inventory_files={str(inventory):p.sha(inventory)}))
            shape=dict(periods=1000,dimension=1012,forecast_rows=4,starts=[[i]*1012 for i in range(4)])
            with patch.object(p,'fixture_contract',return_value=shape),patch.object(p,'attested_dependencies',return_value={}),patch.object(p,'runtime',return_value={'mock':'runtime'}),patch.object(p,'sources',return_value={}):
                out=root/'draft';plan=p.create(out,python,package,att,fixture,audit)
            self.assertFalse(plan['frozen']);self.assertEqual(len(plan['cells']),6)
            for cell in plan['cells']:
                self.assertEqual(cell['starts'],shape['starts']);self.assertEqual(cell['fixture_sha256'],p.sha(fixture))
                if cell['arm']=='numpyro_mixed':self.assertEqual(cell['command'][-2:],['--implementation','associative'])
                if cell['arm']=='numpyro_nc':self.assertIn('continuation_precision.py',' '.join(cell['command']))
            altered=copy.deepcopy(plan);altered['cells'][3]['seed']=plan['cells'][0]['seed']
            with self.assertRaises(ValueError):p.validate_plan(altered,out)
            altered=copy.deepcopy(plan);altered['cells'][1]['starts']=copy.deepcopy(altered['cells'][1]['starts']);altered['cells'][1]['starts'][0][0]+=1
            with self.assertRaises(ValueError):p.validate_plan(altered,out)
    def test_asserted_seed_audit_without_inventory_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'audit.json';p.save(path,dict(status='passed',seeds=p.SEEDS+[s+130000 for s in p.SEEDS],hits=[],scope='claimed'))
            with self.assertRaises(ValueError):p.audit_seeds(path)
    def test_sequential_mixed_report_cannot_be_accepted(self):
        report=dict(status='completed',implementation='sequential',settings={},parity={})
        with self.assertRaises(ValueError):p.validate_report({},dict(arm='numpyro_mixed'),report,Path('unused'))
    def test_executor_preserves_launch_failures_and_refuses_retry(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);draft=root/'plan-draft.json';p.save(draft,{'reviewed':True})
            cells=[dict(id=f'cell{i}',fixture_sha256='fixture',seed=10+i,predictive_seed=130010+i,command=['mock']) for i in range(6)]
            plan=dict(frozen=True,cells=cells,pythonpath='mock',reviewed_draft_sha256=p.sha(draft));path=root/'plan.json';p.save(path,plan);path.with_suffix('.sha256').write_text(p.sha(path))
            with patch.object(p,'validate_plan'),patch.object(p,'verify_bindings'),patch.object(p,'command',return_value=['mock']),patch('subprocess.run',side_effect=OSError('launch failed')):
                p.execute(path)
                summary=p.load(root/'execution-summary.json');self.assertEqual(summary['recorded'],6);self.assertEqual(summary['successful'],0)
                self.assertTrue(all(c['status']=='executor_or_validation_failed' for c in summary['cells']))
                with self.assertRaisesRegex(ValueError,'Existing'):p.execute(path)
    def test_executor_source_abort_keeps_six_denominator(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);draft=root/'plan-draft.json';p.save(draft,{'reviewed':True})
            plan=dict(frozen=True,cells=[dict(id=f'cell{i}',fixture_sha256='fixture',seed=i,predictive_seed=130000+i) for i in range(6)],reviewed_draft_sha256=p.sha(draft));path=root/'plan.json';p.save(path,plan);path.with_suffix('.sha256').write_text(p.sha(path))
            with patch.object(p,'validate_plan'),patch.object(p,'verify_bindings',side_effect=ValueError('source drift')),patch('subprocess.run') as launch:
                p.execute(path);launch.assert_not_called()
            summary=p.load(root/'execution-summary.json');self.assertEqual(summary['recorded'],6)
            self.assertEqual(sum(r['status']=='unattempted_provenance_abort' for r in summary['cells']),5)
if __name__=='__main__':unittest.main()


