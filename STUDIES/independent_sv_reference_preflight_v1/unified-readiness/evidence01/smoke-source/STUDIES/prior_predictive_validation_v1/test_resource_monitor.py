import json,os,sys,tempfile,unittest
from pathlib import Path
from resource_monitor import execute

@unittest.skipUnless(os.name=='posix','Linux process fixtures')
class ProcessFixtures(unittest.TestCase):
 def run_fixture(self,source,cap=3,limit=1024**2,scope='OWALNUTS_JOB_TOKEN'):
  with tempfile.TemporaryDirectory(prefix='amm-supervision-fixture-') as directory:
   root=Path(directory);script=root/'fixture.py';script.write_text(source)
   result=execute([sys.executable,str(script)],root,cap,root,256*1024**2,limit,root/'log',ownership_env=scope)
   self.assertTrue(result['group_drained'],result);self.assertEqual(result['remaining_owned_pids'],[])
   return result
 def test_normal(self):
  r=self.run_fixture('print("fixture")');self.assertEqual(r['exit_code'],0);self.assertEqual(r['status'],'exited');self.assertFalse(r.get('orphaned_children_after_leader_exit',False))
 def test_child_survives_leader_exit(self):
  r=self.run_fixture('import subprocess,sys\nsubprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"],start_new_session=True)')
  self.assertTrue(r['orphaned_children_after_leader_exit']);self.assertLess(r['elapsed_seconds'],3)
 def test_deadline_and_descendant(self):
  r=self.run_fixture('import subprocess,sys,time\nsubprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"],start_new_session=True)\ntime.sleep(30)',cap=.3)
  self.assertEqual(r['reason'],'deadline')
 def test_output_limit(self):
  r=self.run_fixture('from pathlib import Path\nimport time\nPath("big").write_bytes(b"x"*20000)\ntime.sleep(30)',limit=10000)
  self.assertEqual(r['reason'],'output_limit')
 def test_outer_token_survives_nested_job_token(self):
  r=self.run_fixture('import os,subprocess,sys,time\nenv=os.environ.copy();env["OWALNUTS_JOB_TOKEN"]="inner"\nsubprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"],env=env,start_new_session=True)',scope='OWALNUTS_CAMPAIGN_TOKEN')
  self.assertTrue(r['orphaned_children_after_leader_exit'])
if __name__=='__main__':unittest.main()
