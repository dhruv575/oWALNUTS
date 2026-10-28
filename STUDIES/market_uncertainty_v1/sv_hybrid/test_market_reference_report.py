import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import market_reference_report as report

class ReportTests(unittest.TestCase):
    def test_undrained_complete_fit_cannot_be_reported_as_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);window=root/'window.npz';np.savez(window,window=np.zeros(250),label=.01)
            spec=dict(spot=0,scope='fixed_market_reference',window_metadata=dict(month='fixture',tick=1,label=.01),bindings={'window':dict(path=str(window),sha256=report.sha(window))})
            manifest=root/'manifest.json';manifest.write_text(json.dumps(spec))
            (root/'PANEL.json').write_text(json.dumps(dict(manifests=[dict(path=str(manifest),sha256=report.sha(manifest))])))
            comparison=root/'comparison.json';comparison.write_text(json.dumps(dict(rows=[dict(month='fixture',tick=1,extended={'passed':False})])))
            fit=root/'campaign01/job-00/fit';fit.mkdir(parents=True)
            (fit/'FINAL.json').write_text(json.dumps(dict(status='complete')))
            (fit.parent/'SUPERVISION.json').write_text(json.dumps(dict(exit_code=0,group_drained=False)))
            sha=report.sha
            def bound(path):return '51a9157e7de396022a4f28a9cfdf0aff609ce0d6a227c067fc3447ec0bc46b57' if Path(path)==comparison else sha(path)
            with patch.object(report,'sha',side_effect=bound):r=report.run(root,0,comparison,'unused',root/'out')
            self.assertEqual(r['status'],'unavailable');self.assertEqual(r['predictive']['status'],'unavailable')
            self.assertFalse(r['reference']['passed'])
