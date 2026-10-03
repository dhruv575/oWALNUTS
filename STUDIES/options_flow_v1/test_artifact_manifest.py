import json
from pathlib import Path
import tempfile
import unittest
from artifact_manifest import manifest


class ManifestTests(unittest.TestCase):
    def test_running_cells_excluded_and_terminal_failures_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'arm-raw.json').write_text('{"partial":true}')
            report=root/'arm-report.json'
            report.write_text(json.dumps({'status':'running'}))
            self.assertEqual(manifest(root)['entries'],[])
            report.write_text(json.dumps({'status':'failed'}))
            result=manifest(root)
            self.assertEqual(result['entries'][0]['cell_status'],'failed')
            self.assertEqual(len(result['entries'][0]['sha256']),64)


if __name__=='__main__':unittest.main()
