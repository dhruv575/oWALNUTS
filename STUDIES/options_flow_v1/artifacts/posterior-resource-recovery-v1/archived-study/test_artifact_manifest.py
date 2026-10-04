import json
from pathlib import Path
import tempfile
import unittest
from artifact_manifest import manifest


class ManifestTests(unittest.TestCase):
    def test_named_reference_raw_requires_terminal_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'raw.json').write_text('{"canonical_draws":[]}')
            self.assertEqual(manifest(root)['skipped'][0]['reason'],'no report')
            (root/'report.json').write_text('{"status":"running"}')
            self.assertEqual(manifest(root)['entries'],[])
            (root/'report.json').write_text('{"status":"completed"}')
            result=manifest(root)
            self.assertEqual(len(result['entries']),1)
            self.assertEqual(result['entries'][0]['path'],'raw.json')
            self.assertEqual(result['entries'][0]['report_path'],'report.json')
            self.assertEqual(result['skipped'],[])

    def test_pymc_tier_reports_bind_their_raw_draws(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'python-pymc-raw.json').write_text('{"canonical_draws":[]}')
            (root/'python-pymc-flow-raw.json').write_text('{"canonical_draws":[]}')
            report=root/'fit-report.json'
            report.write_text(json.dumps({'status':'running'}))
            self.assertEqual(manifest(root)['entries'],[])
            report.write_text(json.dumps({'status':'completed'}))
            result=manifest(root)
            self.assertEqual(len(result['entries']),2)
            self.assertEqual(result['entries'][0]['report_path'],'fit-report.json')
            self.assertEqual(result['skipped'],[])

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
