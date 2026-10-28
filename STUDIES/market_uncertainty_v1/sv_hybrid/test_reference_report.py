import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import reference_report as report


class ReportTests(unittest.TestCase):
    def test_missing_reference_and_specialists_keep_all_slots(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);ref=root/'ref';dev=root/'dev';ref.mkdir();dev.mkdir()
            (ref/'SUPERVISION.json').write_text(json.dumps(dict(group_drained=True,exit_code=-15)))
            (dev/'PLAN.json').write_text(json.dumps(dict(periods=250)))
            result=report.run(ref,dev)
            self.assertEqual(len(result['methods']),3)
            self.assertEqual(len(result['mean_contrasts']),8)
            self.assertTrue(all(v['status']=='unavailable' for v in result['mean_contrasts']))

    def test_path_corruption_rejected_and_flags_do_not_drop_coordinates(self):
        full=np.zeros((4,8,253));compact=np.zeros((4,8,4))
        full[:,:,0]=compact[:,:,0]=-10
        full[:,:,1]=compact[:,:,1]=-1.6
        compact[:,:,3]=-10
        m=dict(rhat=1.03,bulk_ess=100,tail_ess=50,mean_mcse=.1)
        with patch.object(report,'metrics',return_value=m):
            result=report.summarize(full,compact)
            self.assertEqual(len(result['coordinates']),254)
            self.assertEqual(len(result['flagged_coordinates']),254)
            compact[0,0,3]+=.01
            with self.assertRaisesRegex(ValueError,'reconstruction'):report.summarize(full,compact)

    def test_mean_and_quantiles_with_actual_diagnostics(self):
        a=np.random.default_rng(81).normal(size=(4,1000))
        m=report.metrics(a)
        self.assertAlmostEqual(m['mean'],float(a.mean()))
        self.assertAlmostEqual(m['quantiles']['q05'],float(np.quantile(a,.05)))
        self.assertGreater(m['mean_mcse'],0)


if __name__=='__main__':unittest.main()
