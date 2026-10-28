import json
from pathlib import Path
import tempfile
import unittest
from market_report import collect_chains
from literal_reference import sha


class ReportTests(unittest.TestCase):
    def test_missing_chains_keep_four_slots(self):
        with tempfile.TemporaryDirectory() as directory:
            records,full,compact=collect_chains(Path(directory),{},3,1)
            self.assertEqual([r['index'] for r in records],[28,29,30,31])
            self.assertEqual(full,[]);self.assertEqual(compact,[])

    def test_completed_receipt_with_wrong_seed_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);fit=root/'campaign01/chain-000/fit';fit.mkdir(parents=True)
            (root/'MANIFEST.json').write_text('{}')
            (fit.parent/'MONITOR.json').write_text(json.dumps(dict(exit_code=0,group_drained=True)))
            (fit/'FINAL.json').write_text(json.dumps(dict(status='complete',index=0,spot=0,method=0,chain=0)))
            (fit/'STARTED.json').write_text(json.dumps(dict(seed=99,manifest_sha256=sha(root/'MANIFEST.json'),window_sha256='fixture')))
            with self.assertRaisesRegex(ValueError,'seed binding'):
                collect_chains(root,dict(seeds=[1],windows=[dict(sha256='fixture')]),0,0)


if __name__=='__main__':unittest.main()
