import json
import sys
import tempfile
import unittest
from pathlib import Path
from rolling_analysis_campaign import validate
from rolling_record_audit import sha


class AnalysisAdmission(unittest.TestCase):
    def test_live_sampling_and_source_drift_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.py';source.write_text('x=1\n')
            plan=root/'ANALYSIS-PLAN.json'
            plan.write_text(json.dumps(dict(bindings={str(source):sha(source)},runtime=dict(prefix=sys.prefix,packages={}),root=str(root))))
            receipt=root/'SUPERVISION.json';receipt.write_text(json.dumps(dict(group_drained=False)))
            with self.assertRaisesRegex(ValueError,'terminal and drained'):validate(plan)
            receipt.write_text(json.dumps(dict(group_drained=True)));validate(plan)
            source.write_text('x=2\n')
            with self.assertRaisesRegex(ValueError,'binding drift'):validate(plan)

if __name__=='__main__':unittest.main()
