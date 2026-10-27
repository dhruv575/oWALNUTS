import hashlib,json,tempfile,unittest
from pathlib import Path
from integrity import audit
class IntegrityTests(unittest.TestCase):
    def test_missing_and_changed_referenced_draws_fail_closed(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);lane=p/'lanes'/'control-r0';(lane/'native').mkdir(parents=True);(lane/'draws').mkdir();raw=b'literal';target=lane/'draws'/'000001.npy';target.write_bytes(raw);record=lane/'native'/'000001.json';record.write_text(json.dumps({'compact':{'file':'draws/000001.npy','sha256':hashlib.sha256(raw).hexdigest()}}));self.assertTrue(audit(p)['integrity_ok']);target.write_bytes(b'changed');self.assertFalse(audit(p)['integrity_ok']);target.unlink();self.assertFalse(audit(p)['integrity_ok'])
    def test_completion_journal_binds_scalar_row(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);lane=p/'lanes'/'control-r0';(lane/'records').mkdir(parents=True);raw=b'{"tick":1}';row=lane/'records'/'000001.json';row.write_bytes(raw);(lane/'progress.jsonl').write_text(json.dumps({'event':'tick_completed','tick':1,'record_sha256':hashlib.sha256(raw).hexdigest()})+'\n');self.assertTrue(audit(p)['integrity_ok']);row.write_text('{"tick":2}');self.assertFalse(audit(p)['integrity_ok'])
if __name__=='__main__':unittest.main()
