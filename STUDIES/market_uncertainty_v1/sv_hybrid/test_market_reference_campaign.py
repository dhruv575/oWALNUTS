import contextlib,io,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import market_reference_campaign as runner

class QueueTests(unittest.TestCase):
    def run_case(self,failed=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);plan=dict(manifests=[dict(path=f'manifest-{i}') for i in range(24)])
            def execute(command,cwd,cap,output,rss,size,log,**kwargs):
                self.assertEqual(cap,1800);self.assertEqual(rss,4*1024**3);self.assertEqual(size,1024**3)
                self.assertIn(command[2],['0-3','4-7','8-11','12-15'])
                self.assertEqual(kwargs['phase_reserved_cores'],{'startup':4})
                return dict(status='exited',exit_code=0,group_drained=not failed)
            with patch.object(runner,'validate_panel',return_value=plan),patch.object(runner.shutil,'disk_usage',return_value=SimpleNamespace(free=12*1024**3)),patch.object(runner,'execute',side_effect=execute),contextlib.redirect_stdout(io.StringIO()):
                code=runner.campaign(root)
            return code,json.loads((root/'campaign01/FINAL.json').read_bytes())
    def test_all_windows(self):
        code,r=self.run_case();self.assertEqual(code,0);self.assertEqual(len(r['jobs']),24)
        self.assertTrue(all(x['group_drained'] for x in r['jobs']))
    def test_failed_drain_stops_admission_preserves_slots(self):
        code,r=self.run_case(True);self.assertEqual(code,1);self.assertEqual(len(r['jobs']),24)
        self.assertTrue(r['resource_stop']);self.assertTrue(any(x['status']=='not_started' for x in r['jobs']))
