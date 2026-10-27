import sys,tempfile,unittest
from pathlib import Path
from bootstrap_monitor import execute
@unittest.skipUnless(sys.platform=='linux','Linux /proc fixtures')
class Tests(unittest.TestCase):
 def run_case(self,code,cap=3,byte_limit=1000000):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder);r=execute([sys.executable,'-c',code],p,cap,p,1024**3,byte_limit,p/'log');return r
 def test_exit(self):
  r=self.run_case('print("literal")');self.assertEqual(r['exit_code'],0);self.assertTrue(r['group_drained'])
 def test_deadline(self):
  r=self.run_case('import time;time.sleep(10)',.3);self.assertEqual(r['reason'],'deadline');self.assertTrue(r['group_drained'])
 def test_orphan(self):
  r=self.run_case('import subprocess,sys;subprocess.Popen([sys.executable,"-c","import time;time.sleep(10)"],start_new_session=True)');self.assertTrue(r['orphaned_children_after_leader_exit']);self.assertTrue(r['group_drained'])
 def test_output(self):
  r=self.run_case('import time;open("large","wb").write(b"x"*10000);time.sleep(10)',byte_limit=1000);self.assertEqual(r['reason'],'output_limit');self.assertTrue(r['group_drained'])
if __name__=='__main__':unittest.main()
