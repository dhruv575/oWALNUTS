import json
from pathlib import Path
import tempfile
import unittest
from recover import exclusive
from recovery_view import materialize

class RecoveryFixtures(unittest.TestCase):
    def test_exclusive_preserves_existing_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'checkpoint.json'
            exclusive(path,dict(status='first'))
            before=path.read_bytes()
            with self.assertRaises(FileExistsError):exclusive(path,dict(status='replacement'))
            self.assertEqual(path.read_bytes(),before)

    def test_unique_checkpoints_allow_reader(self):
        with tempfile.TemporaryDirectory() as folder:
            first=Path(folder)/'000001.json';second=Path(folder)/'000002.json'
            exclusive(first,dict(completed=1))
            with first.open('rb') as reader:
                exclusive(second,dict(completed=2))
                self.assertEqual(json.loads(reader.read())['completed'],1)
            self.assertEqual(json.loads(second.read_bytes())['completed'],2)

    def test_reporting_view_keeps_partial_arm_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);recovery=root/'recovery';recovery.mkdir();journal=recovery/'checkpoints';journal.mkdir()
            first=dict(dataset='real',tick=61,arms=[],active_arm=dict(arm='reference',seed=None))
            later=dict(dataset='real',tick=61,arms=[dict(arm='reference',seed=None,status='ok',logpdf=1.,pit=.5)],active_arm=dict(arm='warm_K200',seed=971301))
            exclusive(journal/'000001-real-tick-061.json',first)
            exclusive(journal/'000002-real-tick-061.json',later)
            (journal/'000003-real-tick-061.json').write_text('{')
            (recovery/'real-tick-061.json').write_text('{')
            view=root/'view';manifest=materialize(recovery,view)
            self.assertEqual(json.loads((view/'real-tick-061.json').read_bytes()),later)
            self.assertEqual(manifest['origins'][0]['kind'],'partial_checkpoint')
            self.assertEqual(len(manifest['invalid_files_retained_in_original_location']),2)
            self.assertEqual((recovery/'real-tick-061.json').read_text(),'{')

if __name__=='__main__':unittest.main()
