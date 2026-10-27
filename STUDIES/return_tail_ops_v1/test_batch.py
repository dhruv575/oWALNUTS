import json,tempfile,threading,unittest
from pathlib import Path
from batch import run

class BatchTests(unittest.TestCase):
    def spec(self):return json.loads(Path(__file__).with_name('OPS-DRAFT.json').read_bytes())
    def test_parallel_barriers_and_failed_science_continues(self):
        barriers={p:threading.Barrier(12) for p in ('candidate','reference')};finished={p:set() for p in barriers};lock=threading.Lock()
        def launch(job,*args):
            p=job['phase']
            if p=='reference':self.assertEqual(len(finished['candidate']),12)
            if p=='report':self.assertEqual(len(finished['reference']),12)
            else:
                barriers[p].wait(timeout=5)
                with lock:finished[p].add(job['shard'])
            return dict(status='exited',exit_code=1 if p=='candidate' and job['shard']==0 else 0,group_drained=True)
        with tempfile.TemporaryDirectory() as t:state=run(self.spec(),Path(t)/'run',launch,clock=lambda:0.)
        self.assertEqual(len(state['jobs']),27);self.assertFalse(state['execution_complete']);self.assertTrue(state['job_accounting_complete'])
    def test_orphan_blocks_references_and_reports(self):
        def launch(job,*args):return dict(status='exited',exit_code=0,group_drained=True,orphaned_children_after_leader_exit=job.get('shard')==0)
        with tempfile.TemporaryDirectory() as t:state=run(self.spec(),Path(t)/'run',launch,clock=lambda:0.)
        self.assertFalse(state['all_launched_groups_drained']);self.assertEqual(sum(j['status']=='not_started' for j in state['jobs']),15)
    def test_resource_limit_preserves_fixed_denominator(self):
        def launch(job,*args):return dict(status='terminated',reason='rss_limit',group_drained=True)
        with tempfile.TemporaryDirectory() as t:state=run(self.spec(),Path(t)/'run',launch,clock=lambda:0.)
        self.assertEqual(len(state['jobs']),27);self.assertTrue(state['all_launched_groups_drained']);self.assertFalse(state['execution_complete'])
    def test_scope_change_rejected(self):
        spec=self.spec();spec['months'][0]['origins']=1
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):run(spec,Path(t)/'run',lambda *a:None)
    def test_final_aggregate_is_required_for_execution(self):
        def launch(*args):return dict(status='exited',exit_code=0,group_drained=True)
        def finalize(*args):return dict(accounting_complete=True,artifact_integrity={'integrity_ok':True})
        with tempfile.TemporaryDirectory() as t:
            missing=run(self.spec(),Path(t)/'missing',launch,clock=lambda:0.,finalize=finalize)
            complete=run(self.spec(),Path(t)/'complete',launch,clock=lambda:0.,finalize=finalize,aggregate=lambda *a:{'written':True})
        self.assertTrue(missing['all_jobs_successful']);self.assertFalse(missing['execution_complete']);self.assertTrue(complete['execution_complete'])
