import json,tempfile,threading,unittest
from pathlib import Path
from batch import run

class BatchTests(unittest.TestCase):
    def spec(self):return json.loads(Path(__file__).with_name('OPS-DRAFT.json').read_bytes())
    def test_fixed_queues_and_barriers(self):
        native=threading.Barrier(3);refs=threading.Barrier(4);tails={p:threading.Barrier(12) for p in ('tail_candidate','tail_reference')};lock=threading.Lock();done={p:0 for p in ('native','baselines','reference','tail_candidate','tail_reference','report')};queue_order={str(i):[] for i in range(4)};sealed=[]
        def launch(j,root,cap,affinity):
            phase=j['phase']
            if phase=='native':native.wait(5)
            elif phase=='baselines':self.assertEqual(done['native'],3)
            elif phase=='reference':
                self.assertEqual(done['baselines'],3);refs.wait(5);q=str(int(affinity.split('-')[0])//4);queue_order[q].append((j['month'],j['index']))
            elif phase.startswith('tail_'):
                self.assertEqual(done['reference'],24);self.assertTrue(sealed)
                if phase=='tail_reference':self.assertEqual(done['tail_candidate'],12)
                tails[phase].wait(5)
            else:self.assertEqual(done['tail_reference'],12)
            with lock:done[phase]+=1
            return dict(status='exited',exit_code=0,group_drained=True)
        def seal(*args):self.assertEqual(done['reference'],24);sealed.append(True);return {'sha256':'fixture'}
        with tempfile.TemporaryDirectory() as t:r=run(self.spec(),Path(t)/'run',launch,clock=lambda:0.,seal_inference=seal)
        expected=[(m['month'],i) for m in self.spec()['months'] for i in range(8)]
        for q in range(4):self.assertEqual(queue_order[str(q)],expected[q::4])
        self.assertEqual(len(r['jobs']),57);self.assertTrue(r['all_jobs_successful']);self.assertEqual(len(sealed),1)
    def test_cleanup_failure_blocks_new_phases(self):
        def launch(*a):return dict(status='exited',exit_code=0,group_drained=False)
        with tempfile.TemporaryDirectory() as t:r=run(self.spec(),Path(t)/'run',launch,clock=lambda:0.)
        self.assertFalse(r['all_launched_groups_drained']);self.assertTrue(all(j['status']=='not_started' for j in r['jobs'] if j['phase']!='native'));self.assertEqual(len(r['jobs']),57)
    def test_seal_failure_preserves_tail_slots(self):
        def launch(*a):return dict(status='exited',exit_code=0,group_drained=True)
        def seal(*a):raise ValueError('fixture integrity failure')
        with tempfile.TemporaryDirectory() as t:r=run(self.spec(),Path(t)/'run',launch,clock=lambda:0.,seal_inference=seal)
        self.assertIsNotNone(r['inference_seal_error']);self.assertEqual(sum(j['status']=='not_started' for j in r['jobs']),27);self.assertFalse(r['execution_complete'])
    def test_scope_and_bounds(self):
        s=self.spec();s['bounds']['reference_seconds']=601
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):run(s,Path(t)/'run',lambda *a:None)
