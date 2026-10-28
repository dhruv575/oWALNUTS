import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from rolling_record_audit import audit_lane, verify_packed


class Integrity(unittest.TestCase):
    def test_packed_shape_dtype_bytes_and_extra_members(self):
        import numpy as np
        a=np.arange(8,dtype=np.float64).reshape(2,4)
        leaf=dict(array_key='x',shape=[2,4],dtype=a.dtype.str,sha256=hashlib.sha256(a.tobytes()).hexdigest())
        verify_packed(dict(nested=[leaf]),dict(x=a))
        with self.assertRaisesRegex(ValueError,'identity'):
            verify_packed(leaf,dict(x=a.reshape(4,2)))
        with self.assertRaisesRegex(ValueError,'identity'):
            verify_packed(leaf,dict(x=a.astype(np.float32)))
        with self.assertRaisesRegex(ValueError,'Unreferenced'):
            verify_packed(leaf,dict(x=a,y=a))

    def fixture(self, root, journal=True):
        (root/'records').mkdir()
        row=dict(tick=1,current_index=250,label_index=251,window_start=1,window_stop=251,
                 native_status='ok',score_status='not_planned')
        raw=json.dumps(row).encode();(root/'records/000001.json').write_bytes(raw)
        event=dict(event='tick_completed',tick=1,native_status='ok',score_status='not_planned',
                   record_sha256=hashlib.sha256(raw).hexdigest())
        (root/'progress.jsonl').write_text(json.dumps(event)+'\n' if journal else '')
        return row

    def test_hash_tampering_and_live_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            self.assertEqual(audit_lane(root,2,dict(group_drained=True))['journal_completed'],1)
            with self.assertRaisesRegex(ValueError,'Drained'):
                audit_lane(root,2,dict(group_drained=False))
            with (root/'records/000001.json').open('a') as f:f.write(' ')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):
                audit_lane(root,2,dict(group_drained=True))

    def test_killed_append_retains_orphan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root,False)
            (root/'progress.jsonl').write_bytes(b'{"event":')
            result=audit_lane(root,2,dict(group_drained=True))
            self.assertEqual(result['unjournaled_records'],[1])
            self.assertTrue(result['truncated_journal_tail'])

    def test_causal_and_path_escape_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);row=self.fixture(root,False)
            row['label_index']=250
            (root/'records/000001.json').write_text(json.dumps(row))
            with self.assertRaisesRegex(ValueError,'Causal'):
                audit_lane(root,2,dict(group_drained=True))
            row['label_index']=251;row['arrays']=dict(file='../outside',sha256='x')
            (root/'records/000001.json').write_text(json.dumps(row))
            with self.assertRaisesRegex(ValueError,'escapes'):
                audit_lane(root,2,dict(group_drained=True))

if __name__=='__main__':unittest.main()
