import json,tempfile,unittest
from pathlib import Path
import numpy as np
from unittest.mock import patch
from linear_runner_snapshot import run_lane,exclusive
from ledger import build,validate_artifacts,references
from data_contract import inputs
from worker import admit
from run_reference import precision

class FakeEngine:
    def __init__(self,y,seeds):self.y=y.copy();self.seeds=seeds;self.index=0;self.initial=dict(seconds=0.)
    def advance(self,value,k):
        self.y=np.append(self.y[1:],value);call=self.index;self.index+=1
        return np.zeros((4,400,4)),dict(call_index=call,seed=self.seeds['warm']+4*call,work=[],diagnostics=[dict(divergent=np.zeros(400,dtype=bool)) for _ in range(4)])
    def close(self):pass

class WiringFixtures(unittest.TestCase):
    def test_scoring_failure_continues_and_fixed_ledger_retains_future(self):
        y=np.arange(1739,dtype=float)/100000
        def score(draws,window,label,tick):
            np.testing.assert_array_equal(window,y[tick:250+tick])
            self.assertEqual(label,y[250+tick])
            if tick==2:raise ArithmeticError('literal downstream failure')
            return dict(status='ok',logpdf=1.,pit=.5,numerical={})
        def context(tick,*_):return {k:inputs(y,tick)[k] for k in ['origin_ms','label_available_ms']}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            done=run_lane(y,updates=3,seeds=dict(initial=11,warm=19),score_ticks=[1,2,3],retain_ticks=[1,2,3],engine_factory=FakeEngine,score_hook=score,output=root/'candidate',metadata_hook=context)
            rows=build(root)
            self.assertEqual(done['native_completed'],3);self.assertEqual(len(rows),1488)
            self.assertEqual([r['arms']['candidate']['status'] for r in rows[:4]],['ok','unavailable','ok','not_started'])
            self.assertTrue(validate_artifacts(root)['integrity_ok'])

    def test_native_only_pre_score_artifact_is_verified(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);native=root/'candidate/native';native.mkdir(parents=True)
            raw=root/'candidate/draw.npy';raw.write_bytes(b'literal')
            exclusive(native/'000001.json',dict(compact=dict(file='draw.npy',sha256=hashlib.sha256(raw.read_bytes()).hexdigest())))
            self.assertTrue(validate_artifacts(root)['integrity_ok'])
            raw.write_bytes(b'changed')
            self.assertFalse(validate_artifacts(root)['integrity_ok'])

    def test_reference_checkpoint_retained_as_interrupted(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);ref=root/'references/00';ref.mkdir(parents=True);(root/'jobs').mkdir()
            exclusive(root/'jobs/reference-00.start.json',{})
            exclusive(ref/'draws-checkpoint.json',dict(index=0,tick=1,phase='draws_saved'))
            rows=references(root);self.assertEqual(len(rows),8);self.assertEqual(rows[0]['status'],'interrupted')
            self.assertIn('draws-checkpoint.json',rows[0]['checkpoints'])

    def test_precision_invalid_values_unavailable_and_draft_guard(self):
        with patch('run_reference.mean_mcse',return_value=float('nan')):
            with self.assertRaises(ValueError):precision(np.zeros((4,400)),np.full((4,400),.5))
        with self.assertRaises(ValueError):admit(Path(__file__).with_name('COMPUTE-DRAFT.json'))

if __name__=='__main__':unittest.main()
