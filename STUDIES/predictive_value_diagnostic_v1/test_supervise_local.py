"""Synthetic process fixtures only; never loads project predictions."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parents[1] / 'target' / 'predictive-supervisor-fixtures'
WORKER = '''import argparse,json,os,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('mode');p.add_argument('--out');a=p.parse_args()
out=Path(a.out);out.mkdir();kind=Path('kind.txt').read_text()
if kind=='deadline':subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
r=dict(pid=os.getpid(),hard_seconds=120,started_unix=time.time()-(122 if kind=='deadline' else 0),status='running')
def save():
 t=out/'phase.tmp';t.write_text(json.dumps(r));t.replace(out/'preflight.json')
save()
if kind=='output':(out/'big.bin').write_bytes(b'x'*(51*1024*1024))
time.sleep(1 if kind=='complete' else 10)
r['status']='complete';save()
'''


class SupervisorChecks(unittest.TestCase):
    def exercise(self, kind):
        FIXTURES.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix=kind+'-', dir=FIXTURES)).resolve()
        self.assertTrue(root.is_relative_to(FIXTURES.resolve()))
        study = root / 'source'; study.mkdir()
        (study / 'evaluate.py').write_bytes(WORKER.encode())
        (study / 'kind.txt').write_text(kind)
        out = root / 'outputs'
        result = subprocess.run([sys.executable, str(HERE/'supervise_local.py'),
                                 'preflight', '--study', str(study),
                                 '--python', sys.executable, '--out', str(out)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((root/'outputs.preflight.supervisor.json').read_text())
        self.assertEqual(report['remaining_owned_pids'], [])
        if (out/'big.bin').exists():
            (out/'big.bin').unlink()  # Only this newly created fixture payload.
        return report

    def test_normal_completion(self):
        result = self.exercise('complete')
        self.assertEqual(result['status'], 'exited')
        self.assertEqual(result['evaluator_status'], 'complete')

    def test_deadline_drains_child(self):
        result = self.exercise('deadline')
        self.assertEqual(result['reason'], 'phase_deadline')
        self.assertGreaterEqual(len(result['processes']), 2)

    def test_output_limit(self):
        result = self.exercise('output')
        self.assertEqual(result['reason'], 'output_limit')


if __name__ == '__main__':
    unittest.main()
