import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from model import simulate
from run import execute


class RunContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.out=self.root/'out';self.out.mkdir()
        self.fixture=self.root/'fixture.json';self.fixture.write_text(json.dumps(simulate(1,4,2,1)))

    def call(self):
        return execute(self.fixture,self.out,'numpyro',None,1,10,10,4,30)

    def test_failed_attempt_not_overwritten(self):
        report=self.out/'numpyro-report.json';report.write_text('{"status":"failed"}')
        original=report.read_bytes()
        with patch('run.subprocess.run') as launch:
            with self.assertRaises(FileExistsError):self.call()
            launch.assert_not_called()
        self.assertEqual(report.read_bytes(),original)
        self.assertFalse((self.out/'data.json').exists())

    def test_mismatched_data_refused_before_launch(self):
        path=self.out/'data.json';path.write_text('{"different":true}')
        with patch('run.subprocess.run') as launch:
            with self.assertRaisesRegex(ValueError,'different data'):self.call()
            launch.assert_not_called()
        self.assertEqual(json.loads(path.read_text()),{'different':True})

    def test_unknown_arm_cannot_create_artifact(self):
        with self.assertRaisesRegex(ValueError,'Unknown arm'):
            execute(self.fixture,self.out,'typo',None,1,10,10,4,30)
        self.assertEqual(list(self.out.iterdir()),[])


if __name__=='__main__':unittest.main()
