import json,tempfile,unittest
from pathlib import Path
import archive_batch as a

class ArchiveTests(unittest.TestCase):
    def fixture(self,root):
        root=Path(root);folder=root/'batch-254';folder.mkdir()
        for name,value in [('FREEZE.json',{})]: (root/name).write_text(json.dumps(value))
        for name,value in [('PLAN.json',dict(indices=[3048,3049])),('SUPERVISION.json',dict(group_drained=True,sources_unchanged=True)),('FINAL.json',[dict(index=j,group_drained=True,exit_code=-9) for j in [3048,3049]])]:
            (folder/name).write_text(json.dumps(value))
        raw=folder/'job-3048'/'draws.npz';raw.parent.mkdir();raw.write_bytes(b'archive fixture bytes')
        packed=a.pack(root,254)
        # Simulated transport receipts exercise binding, not a real S3 assertion.
        common=dict(sha256=packed['sha256'],bytes=packed['bytes'],bucket='fixture',key='fixture',version_id='fixture-v1')
        upload=root/'upload.json';restore=root/'restore.json'
        upload.write_text(json.dumps(dict(**common,encryption='AES256')))
        restore.write_text(json.dumps(dict(**common,exact_version_restore_verified=True)))
        return folder,raw,upload,restore

    def test_verified_cleanup_preserves_control_and_failure_records(self):
        with tempfile.TemporaryDirectory() as temp:
            folder,raw,upload,restore=self.fixture(temp)
            a.admit(temp,254,upload,restore);audit=a.reclaim(temp,254)
            self.assertTrue(audit['completed']);self.assertFalse(raw.exists())
            self.assertTrue((folder/'FINAL.json').exists());self.assertTrue((folder/'PLAN.json').exists())

    def test_version_mismatch_blocks_admission(self):
        with tempfile.TemporaryDirectory() as temp:
            folder,raw,upload,restore=self.fixture(temp)
            r=json.loads(restore.read_text());r['version_id']='other';restore.write_text(json.dumps(r))
            with self.assertRaises(ValueError):a.admit(temp,254,upload,restore)
            self.assertTrue(raw.exists());self.assertFalse((folder/'ARCHIVE-VERIFIED.json').exists())

    def test_changed_raw_blocks_all_deletion(self):
        with tempfile.TemporaryDirectory() as temp:
            folder,raw,upload,restore=self.fixture(temp);a.admit(temp,254,upload,restore)
            raw.write_bytes(b'changed')
            with self.assertRaises(ValueError):a.reclaim(temp,254)
            self.assertTrue(raw.exists());self.assertTrue((Path(temp)/'batch-254.tar.gz').exists())

    def test_undrained_batch_not_archived(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'batch-000';folder.mkdir()
            (folder/'SUPERVISION.json').write_text(json.dumps(dict(group_drained=False,sources_unchanged=True)))
            (folder/'FINAL.json').write_text('[]')
            with self.assertRaises(ValueError):a.pack(temp,0)

if __name__=='__main__':unittest.main()
