import json,tempfile,threading,unittest
from pathlib import Path
from batch import run
class BatchTests(unittest.TestCase):
    def spec(self):return json.loads(Path(__file__).with_name('OPS-DRAFT.json').read_bytes())
    def finalize(self,spec,month,root,jobs):return dict(accounting_complete=True,planned_origins=next(m['origins'] for m in spec['months'] if m['month']==month),planned_references=8,artifact_integrity={'integrity_ok':True},jobs=len(jobs))
    def test_concurrent_candidate_barrier_and_independent_failed_lane(self):
        barrier=threading.Barrier(3);finished=set();lock=threading.Lock();calls=[]
        def launch(month,phase,index,root,cap,affinity):
            if phase=='candidate':
                barrier.wait(timeout=3)
                with lock:finished.add(month)
            else:self.assertEqual(len(finished),3)
            with lock:calls.append((month,phase,index))
            return dict(status='exited',exit_code=1 if phase=='candidate' and month=='2026-04' else 0,group_drained=True)
        with tempfile.TemporaryDirectory() as t:
            state=run(self.spec(),Path(t)/'run',launch,clock=lambda:0.,finalize=self.finalize)
        self.assertEqual(len(calls),33);self.assertFalse(state['execution_complete']);self.assertTrue(state['job_accounting_complete']);self.assertTrue(all(x['jobs']==11 for x in state['month_accounting'].values()))
    def test_reference_orphan_blocks_later_work(self):
        def launch(month,phase,index,*args):return dict(status='exited',exit_code=0,group_drained=True,orphaned_children_after_leader_exit=phase=='reference' and month=='2026-04' and index==0)
        with tempfile.TemporaryDirectory() as t:state=run(self.spec(),Path(t)/'run',launch,clock=lambda:0.,finalize=self.finalize)
        self.assertFalse(state['all_launched_groups_drained']);self.assertEqual(sum(j['status']=='not_started' for j in state['jobs']),26);self.assertTrue(all(not v['accounting_complete'] for v in state['month_accounting'].values()))
    def test_resource_failure_preserves_all_slots(self):
        def launch(month,phase,index,*args):return dict(status='terminated' if phase=='baselines' else 'exited',exit_code=-15 if phase=='baselines' else 0,group_drained=True,reason='output_limit' if phase=='baselines' else None)
        with tempfile.TemporaryDirectory() as t:state=run(self.spec(),Path(t)/'run',launch,clock=lambda:0.,finalize=self.finalize)
        self.assertEqual(len(state['jobs']),33);self.assertTrue(state['all_launched_groups_drained']);self.assertFalse(state['execution_complete']);self.assertTrue(all(v['accounting_complete'] for v in state['month_accounting'].values()))
    def test_fixed_counts_reject_scope_change(self):
        s=self.spec();s['months'][0]['origins']=1
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):run(s,Path(t)/'run',lambda *a:None)
if __name__=='__main__':unittest.main()
