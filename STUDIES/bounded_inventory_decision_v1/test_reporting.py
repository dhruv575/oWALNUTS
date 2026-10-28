import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import report
from bounded_loss import score

class Reporting(unittest.TestCase):
    def arm(self,m):return dict(status='ok',mean_downside=m,score=score(m,-.001),postprocess_seconds=.1,numerical={})
    def test_fixed_comparisons_and_primary(self):
        row=dict(month='2026-04',tick=1,arms={a:self.arm(m) for a,m in [('candidate',.001),('ewma_t5',.0001),('rolling_t5',.002)]})
        self.assertEqual(len(report.COMPARISONS),6)
        self.assertGreater(report.pair(row,'decision','ewma_t5'),0)
        self.assertEqual(report.pair(row,'decision','always_convert'),0)
        self.assertAlmostEqual(report.pair(row,'forecast','rolling_t5'),row['arms']['rolling_t5']['score']['squared_error']-row['arms']['candidate']['score']['squared_error'])
    def test_empty_denominators_and_invalid_success(self):
        with tempfile.TemporaryDirectory() as folder:
            r=report.terminal_accounting(dict(input=dict(root=folder)),folder,[])
            self.assertEqual(r['planned_arm_origins'],13104);self.assertEqual(r['valid_arm_origins'],0)
            a=report.batch_summary({},folder);self.assertEqual(a['status'],'incomplete')
        self.assertFalse(report.valid(dict(status='ok',mean_downside=float('nan'))))
    def test_paired_wrap_and_truncation(self):
        class Fixed:
            def integers(self,lo,hi,size):return np.full(size,hi-1)
        matrix=np.stack([np.arange(100),2*np.arange(100)],axis=1)
        with patch('report.np.random.default_rng',return_value=Fixed()):ci=report.bootstrap(matrix,17,repetitions=1)
        for length in (24,48,96):
            indices=np.tile((99+np.arange(length))%100,int(np.ceil(100/length)))[:100]
            self.assertTrue(np.allclose(np.array(ci[str(length)])[:,0],matrix[indices].mean(axis=0)))
    def test_full_aggregate(self):
        with tempfile.TemporaryDirectory() as folder:
            for m,n in report.MONTHS:
                p=Path(folder)/'reports'/m/'summary.json';p.parent.mkdir(parents=True);p.write_text(json.dumps(dict(full_scientific_panel=True,comparisons={'decision_ewma_t5':dict(mean_advantage=.01)})))
            a=report.batch_summary({},folder);self.assertEqual(a['status'],'complete');self.assertAlmostEqual(a['origin_weighted_comparisons']['decision_ewma_t5'],.01)
if __name__=='__main__':unittest.main()
