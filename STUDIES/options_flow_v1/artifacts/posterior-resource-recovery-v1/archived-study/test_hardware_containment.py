import ctypes,json,subprocess,sys,tempfile,unittest
from pathlib import Path
import hardware_control as hw

@unittest.skipUnless(hw.os.name=='nt','Windows jobs')
class RealTreeTests(unittest.TestCase):
    def assert_dead(self,pid):
        api=ctypes.WinDLL('kernel32',use_last_error=True)
        api.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];api.OpenProcess.restype=ctypes.c_void_p
        api.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];api.WaitForSingleObject.restype=ctypes.c_ulong
        api.CloseHandle.argtypes=[ctypes.c_void_p]
        h=api.OpenProcess(0x100000,False,pid)
        if h:
            try:self.assertEqual(api.WaitForSingleObject(h,2000),0,'descendant survived')
            finally:api.CloseHandle(h)
    def run_tree(self,exit_parent):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);script=root/'tree.py';pids=root/'pids';pids.mkdir()
            script.write_text("import os,sys,subprocess,time\nfrom pathlib import Path\nd=Path(sys.argv[1]);depth=int(sys.argv[2]);early=int(sys.argv[3])\n(d/str(os.getpid())).write_text(str(depth))\nif depth: subprocess.Popen([sys.executable,__file__,str(d),str(depth-1),'0'])\nif early:\n while len(list(d.iterdir()))<3:time.sleep(.01)\nelse:time.sleep(60)\n")
            record=root/'record.json'
            done=subprocess.run(hw.wrapper_command([sys.executable,str(script),str(pids),'2',str(int(exit_parent))],[hw.get_affinity()[0]],record,timeout=2),timeout=15,capture_output=True,text=True)
            self.assertEqual(done.returncode,0 if exit_parent else 124,done.stderr)
            ids=[int(f.name) for f in pids.iterdir()];self.assertEqual(len(ids),3)
            for pid in ids:self.assert_dead(pid)
            evidence=json.loads(record.read_text());self.assertTrue(evidence['containment']['assigned_before_worker_execution']);self.assertTrue(evidence['descendant_cleanup_requested'])
    def test_abrupt_wrapper_exit_kills_job(self):
        import time
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);pidfile=root/'pid';record=root/'record.json'
            code="import os,time;from pathlib import Path;Path("+repr(str(pidfile))+").write_text(str(os.getpid()));time.sleep(60)"
            launcher=subprocess.Popen(hw.wrapper_command([sys.executable,'-c',code],[hw.get_affinity()[0]],record),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                deadline=time.monotonic()+5
                while not pidfile.exists() and time.monotonic()<deadline:time.sleep(.01)
                self.assertTrue(pidfile.exists(),'worker did not start')
                pid=int(pidfile.read_text())
                evidence=json.loads(record.read_text())
                actual_wrapper_pid=evidence['launcher_pid']
                api=ctypes.WinDLL('kernel32',use_last_error=True)
                api.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];api.OpenProcess.restype=ctypes.c_void_p
                api.TerminateProcess.argtypes=[ctypes.c_void_p,ctypes.c_uint];api.TerminateProcess.restype=ctypes.c_int
                api.CloseHandle.argtypes=[ctypes.c_void_p]
                handle=api.OpenProcess(1,False,actual_wrapper_pid)
                self.assertTrue(handle,'actual wrapper is unavailable')
                try:self.assertTrue(api.TerminateProcess(handle,137))
                finally:api.CloseHandle(handle)
                launcher.wait(timeout=5)
                self.assert_dead(actual_wrapper_pid)
                self.assert_dead(pid)
            finally:
                if launcher.poll() is None:launcher.kill();launcher.wait(timeout=5)
    def test_timeout_tree(self):self.run_tree(False)
    def test_parent_exit_tree(self):self.run_tree(True)

if __name__=='__main__':unittest.main()
