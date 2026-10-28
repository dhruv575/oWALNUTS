import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import market_campaign as runner


class CampaignTests(unittest.TestCase):
    def run_case(self,failed=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            def execute(command,cwd,cap,output,rss,size,log,**kwargs):
                self.assertEqual(cap,300);self.assertEqual(rss,1024**3);self.assertEqual(size,64*1024**2)
                self.assertEqual(kwargs['phase_reserved_cores'],{'startup':1})
                self.assertIn(int(command[2]),range(16))
                return dict(status='exited',exit_code=1 if failed else 0,group_drained=not failed)
            with patch.object(runner,'validate',return_value={}),patch.object(runner.shutil,'disk_usage',return_value=SimpleNamespace(free=20*1024**3)),patch.object(runner,'execute',side_effect=execute),contextlib.redirect_stdout(io.StringIO()):
                code=runner.campaign(root)
            return code,json.loads((root/'campaign01/FINAL.json').read_bytes())

    def test_all_192_slots_and_fixed_limits(self):
        code,result=self.run_case()
        self.assertEqual(code,0);self.assertEqual(len(result['jobs']),192)
        self.assertTrue(all(r['group_drained'] for r in result['jobs']))

    def test_containment_failure_stops_new_work_keeps_denominator(self):
        code,result=self.run_case(True)
        self.assertEqual(code,1);self.assertTrue(result['resource_stop'])
        self.assertEqual(len(result['jobs']),192)
        self.assertTrue(any(r['status']=='not_started' for r in result['jobs']))


if __name__=='__main__':unittest.main()
