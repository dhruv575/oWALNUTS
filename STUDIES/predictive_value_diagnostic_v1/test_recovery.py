import json
from pathlib import Path
import tempfile
import unittest
from recover import exclusive

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

if __name__=='__main__':unittest.main()
