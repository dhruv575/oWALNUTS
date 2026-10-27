import json,sys,tempfile,unittest
from pathlib import Path
from supervise_acquisition import supervise

class SupervisorFixtures(unittest.TestCase):
    def test_complete_looking_files_cannot_override_failed_monitor(self):
        for tail,seconds in [('raise SystemExit(1)',5),('import time;time.sleep(30)',.8)]:
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder);out=root/'out'
                code="import pathlib,json,sys; p=pathlib.Path(sys.argv[1]);p.mkdir();(p/'terminal.json').write_text(json.dumps({'complete':True,'completed_requests':[]}));"+tail
                result=supervise([sys.executable,'-c',code,str(out)],root,out,seconds=seconds,finish_check=lambda:dict(sealed_acquisition_admitted=True))
                self.assertFalse(result['sealed_acquisition_admitted'])
                final=json.loads((root/'out.supervisor.final.json').read_bytes())
                self.assertFalse(final['sealed_acquisition_admitted'])

    def test_normal_process(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);out=root/'out'
            code="import pathlib,json; p=pathlib.Path(__import__('sys').argv[1]);p.mkdir();(p/'terminal.json').write_text(json.dumps({'complete':True,'completed_requests':[]}))"
            result=supervise([sys.executable,'-c',code,str(out)],root,out,seconds=10)
            self.assertEqual(result['status'],'exited');self.assertEqual(result['exit_code'],0)
            self.assertEqual(result['remaining_owned_pids'],[]);self.assertTrue(result['collector_complete'])
            self.assertTrue((root/'out.supervisor.start.json').exists());self.assertTrue((root/'out.supervisor.final.json').exists())

    def test_descendant_survives_launcher_then_is_drained_at_deadline(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);out=root/'out'
            code="import subprocess,sys,time,pathlib; p=pathlib.Path(sys.argv[1]);p.mkdir();(p/'request-000.json').write_text('{}');subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);time.sleep(.6)"
            result=supervise([sys.executable,'-c',code,str(out)],root,out,seconds=1.5)
            self.assertEqual(result['reason'],'whole_process_deadline');self.assertEqual(result['remaining_owned_pids'],[])
            self.assertGreaterEqual(len(result['processes']),2);self.assertEqual(result['request_statuses'][0]['status'],'interrupted')
            self.assertFalse(result['collector_complete']);self.assertLess(result['elapsed_seconds'],8)

if __name__=='__main__':unittest.main()
