import hashlib,json,tempfile,unittest
from pathlib import Path
from integrity_corrected import audit
class CorrectionTests(unittest.TestCase):
    def test_ancestor_lanes_and_exact_relocation(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'lanes'/'campaign'/'work';ref=root/'references'/'00';ref.mkdir(parents=True);raw=b'literal';artifact=ref/'captured.so';artifact.write_bytes(raw);remote='/home/ubuntu/lanes/frozen/campaign/work';metadata={'compiler_captures':[{'copy_path':remote+'/references/00/captured.so','sha256':hashlib.sha256(raw).hexdigest()}]};(ref/'COMPILED.json').write_text(json.dumps(metadata));self.assertTrue(audit(root,remote)['integrity_ok']);artifact.write_bytes(b'tampered');self.assertFalse(audit(root,remote)['integrity_ok']);artifact.write_bytes(raw);self.assertFalse(audit(root,'/home/ubuntu/lanes/OTHER/work')['integrity_ok'])
if __name__=='__main__':unittest.main()
