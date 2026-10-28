import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rolling_diagnostics import run


class DiagnosticDenominators(unittest.TestCase):
    def test_missing_scores_do_not_remove_successful_native_fits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);lane=root/'campaign01/job-00/fit/lane';(lane/'records').mkdir(parents=True)
            metadata=dict(divergences=[0,0,0,0],chain_coordinates=[0,1,2,3])
            (lane/'records/000001.json').write_text(json.dumps(dict(native_status='ok',score_status='unavailable',
                compact=dict(file='draws/000001.npy'),native=dict(artifacts={},metadata=metadata))))
            audit=dict(jobs=[dict(job=j,month=str(j//2),replicate=j%2) for j in range(6)],
                       spots=[dict(job=j,tick=t,available=False) for j in range(6) for t in range(1,9)])
            report=dict(metadata=metadata,diagnostic_passed=False,flagged_coordinates=['log_sigma'])
            with patch('rolling_diagnostics.inventory',return_value=audit),patch('rolling_diagnostics.report_trace',return_value=report) as reader:
                result=run(root,'unused','unused',root/'analysis')
            self.assertEqual(len(result['rows']),54)
            self.assertEqual(sum(r['status']=='available' for r in result['rows']),1)
            self.assertEqual(reader.call_count,1)
            row=next(r for r in result['rows'] if r['job']==0 and r['tick']==1)
            self.assertFalse(row['diagnostic_passed'])
            self.assertEqual(row['flagged_coordinates'],['log_sigma'])

if __name__=='__main__':unittest.main()
