import json,os,sys,tempfile,unittest
from pathlib import Path
from resource_monitor import execute

@unittest.skipUnless(os.name=='posix','Linux process containment')
class MonitorTests(unittest.TestCase):
    def test_reserved_core_mapping_and_clean_exit(self):
        with tempfile.TemporaryDirectory() as root:
            r=execute([sys.executable,'-c','print("fixture")'],root,10,root,256*1024**2,1024**2,str(Path(root)/'log'),utilization_path=str(Path(root)/'util.jsonl'),phase_reserved_cores={'startup':16})
            self.assertEqual(r['exit_code'],0);self.assertTrue(r['group_drained'])
            rows=[json.loads(x) for x in (Path(root)/'util.jsonl').read_text().splitlines()]
            self.assertTrue(rows);self.assertEqual(rows[0]['reserved_cores'],16)

if __name__=='__main__':unittest.main()
