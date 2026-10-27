import hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
class Tests(unittest.TestCase):
 def launch(self,payload):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);monitor=root/'monitor.py'
   monitor.write_text('import json\nfrom pathlib import Path\ndef execute(command,cwd,cap,output_root,rss_limit,byte_limit,log_path,ownership_env):\n assert cap==600 and rss_limit==4*1024**3 and byte_limit==3*1024**3\n p=Path(output_root)/"work";p.mkdir()\n (p/"preparation.json").write_text(json.dumps({"status":"complete"}))\n return '+repr(payload)+'\n')
   result=subprocess.run([sys.executable,str(Path(__file__).with_name('supervise_prepare.py')),'--root',str(root/'out'),'--monitor',str(monitor),'--monitor-sha256',hashlib.sha256(monitor.read_bytes()).hexdigest(),'--requirements','literal-not-opened','--requirements-sha256','literal'],capture_output=True,text=True)
   return result.returncode,json.loads((root/'out/supervisor.json').read_text())
 def test_success(self):
  code,r=self.launch(dict(status='exited',exit_code=0,group_drained=True));self.assertEqual(code,0);self.assertTrue(r['preparation_complete'])
 def test_nonzero(self):
  code,r=self.launch(dict(status='exited',exit_code=1,group_drained=True));self.assertNotEqual(code,0);self.assertFalse(r['preparation_complete'])
 def test_orphan(self):
  code,r=self.launch(dict(status='exited',exit_code=0,group_drained=True,orphaned_children_after_leader_exit=True));self.assertNotEqual(code,0);self.assertFalse(r['preparation_complete'])
if __name__=='__main__':unittest.main()
