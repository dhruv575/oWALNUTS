import contextlib,io,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import rolling_market_campaign as runner

class CampaignTests(unittest.TestCase):
    def run_case(self,failed=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            def execute(command,cwd,cap,output,rss,size,log,**kwargs):
                self.assertEqual((cap,rss,size),(3600,4*1024**3,1024**3))
                i=int(command[-2]);g=i%4;self.assertEqual(command[2],f'{g*4}-{g*4+3}')
                self.assertEqual(kwargs['phase_reserved_cores'],{'startup':4})
                return dict(status='exited',exit_code=0,group_drained=not failed)
            with patch.object(runner,'validate'),patch.object(runner.os,'sched_getaffinity',return_value=set(range(16)),create=True),patch.object(runner.shutil,'disk_usage',return_value=SimpleNamespace(free=9*1024**3)),patch.object(runner,'execute',side_effect=execute),contextlib.redirect_stdout(io.StringIO()):
                code=runner.campaign(root)
            return code,json.loads((root/'campaign01/FINAL.json').read_bytes())
    def test_all_six_fixed_paths_and_limits(self):
        code,r=self.run_case();self.assertEqual(code,0);self.assertEqual(len(r['jobs']),6)
        self.assertTrue(all(x['group_drained'] for x in r['jobs']))
    def test_containment_failure_stops_new_admission(self):
        code,r=self.run_case(True);self.assertEqual(code,1);self.assertEqual(len(r['jobs']),6)
        self.assertTrue(r['resource_stop']);self.assertTrue(any(x['status']=='not_started' for x in r['jobs']))
