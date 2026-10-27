import unittest,json,tempfile
from pathlib import Path
from audit_results import paired_check,audit
class AuditFixtures(unittest.TestCase):
 def rows(self):return [dict(tick=i,arms={a:dict(status='ok',logpdf=float(j),pit=.5) for j,a in enumerate(['candidate','rolling_t5','ewma_t5'])}) for i in range(1,4)]
 def test_missing_pair_preserves_denominator(self):
  rows=self.rows();rows[-1]['arms']['candidate']={'status':'unavailable'};r=paired_check(rows,None,3)
  self.assertIsNone(r['paired_means']['candidate_minus_rolling_t5']['full_mean']);self.assertEqual(r['paired_means']['candidate_minus_rolling_t5']['available_pairs'],2)
 def test_nonfinite_and_duplicate_rows_rejected(self):
  rows=self.rows();rows[0]['arms']['candidate']['logpdf']=float('nan')
  with self.assertRaises(ValueError):paired_check(rows,None,3)
  rows=self.rows();rows[-1]['tick']=1
  with self.assertRaises(ValueError):paired_check(rows,None,3)
 def test_wrong_frozen_mean_rejected(self):
  rows=self.rows();r=paired_check(rows,None,3);s=dict(status_counts=r['status_counts'],arms={a:dict(logscore=dict(full_mean=99.)) for a in r['arm_means']},paired={})
  with self.assertRaises(ValueError):paired_check(rows,s,3)
 def test_nan_frozen_mean_rejected(self):
  rows=self.rows();r=paired_check(rows,None,3);s=dict(status_counts=r['status_counts'],arms={a:dict(logscore=dict(full_mean=float('nan'))) for a in r['arm_means']},paired={})
  with self.assertRaises(ValueError):paired_check(rows,s,3)
 def test_native_failure_null_score_and_health_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);batch=root/'batch';batch.mkdir();(root/'BATCH-SUPERVISION.json').write_text(json.dumps(dict(group_drained=True,remaining_owned_pids=[])));(batch/'BATCH-FINAL.json').write_text(json.dumps(dict(jobs=[])))
   folder=batch/'2026-04/candidate/records';folder.mkdir(parents=True);(folder/'000001.json').write_text(json.dumps(dict(tick=1,native_health=None,score=None,native_status='failed',score_status='unavailable')))
   value=audit(root);self.assertEqual(value['months'][0]['native_health']['recorded_ticks'],1);self.assertEqual(value['months'][0]['numerical']['recorded_scores'],0);self.assertTrue(value['months'][0]['ledger_missing'])
if __name__=='__main__':unittest.main()
