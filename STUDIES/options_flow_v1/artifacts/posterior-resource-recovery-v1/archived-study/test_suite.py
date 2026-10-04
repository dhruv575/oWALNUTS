import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import suite


class SuiteTests(unittest.TestCase):
    def test_expected_denominator_and_rotating_order(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            def execute(fixture, out, arm, *args, **kwargs):
                manifest = json.loads((Path(directory)/'manifest.json').read_text())
                self.assertEqual(len(manifest['intended_cells']), 4)
                calls.append((arm, kwargs))
                return {'status': 'failed'}
            argv = ['suite.py', '--out', directory, '--exe', 'unused.exe',
                    '--seeds', '99069001,99069002', '--arms', 'numpyro,autodiff',
                    '--cpus', '0', '--require-attestation',
                    '--reference-script', 'optimized_reference.py']
            with patch('sys.argv', argv), patch.object(suite, 'execute', execute), \
                    patch.object(suite, 'simulate', return_value={'data': {}}):
                suite.main()
            self.assertEqual([c[0] for c in calls], ['numpyro', 'autodiff', 'autodiff', 'numpyro'])
            self.assertTrue(all(c[1]['require_attestation'] for c in calls))
            self.assertTrue(all(c[1]['cpus'] == [0] for c in calls))
            self.assertTrue(all(c[1]['reference_script'] == Path('optimized_reference.py') for c in calls))


if __name__ == '__main__':
    unittest.main()
