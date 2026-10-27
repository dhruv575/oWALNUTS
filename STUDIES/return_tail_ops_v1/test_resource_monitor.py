"""Linux process fixtures for throttled byte scans; no scientific data or RNG."""
import os, sys, tempfile, unittest
from pathlib import Path
from resource_monitor import execute

@unittest.skipUnless(os.name == 'posix' and Path('/proc').exists(), 'Linux deployment fixtures')
class OutputScanFixtures(unittest.TestCase):
    def run_child(self, code, limit):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            return execute([sys.executable, '-c', code], root, 10, root,
                           256*1024**2, limit, root/'child.log', output_scan_interval=60)

    def test_final_scan_rejects_successful_oversized_writer(self):
        result = self.run_child("import pathlib,time;time.sleep(.2);pathlib.Path('payload').write_bytes(b'x'*4096)", 1024)
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(result['status'], 'terminated')
        self.assertEqual(result['reason'], 'output_limit_final_scan')
        self.assertGreaterEqual(result['final_output_bytes'], 4096)
        self.assertTrue(result['group_drained'])
        self.assertEqual(result['output_size_scans'], 2)

    def test_under_limit_completes_with_final_accounting(self):
        result = self.run_child("import pathlib,time;time.sleep(.2);pathlib.Path('payload').write_bytes(b'x'*128)", 1024)
        self.assertEqual(result['status'], 'exited')
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(result['final_output_bytes'], 128)
        self.assertTrue(result['group_drained'])
        self.assertEqual(result['output_size_scans'], 2)

if __name__ == '__main__':
    unittest.main()
