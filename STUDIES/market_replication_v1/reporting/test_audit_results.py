import unittest
from audit_results import paired_check
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
if __name__=='__main__':unittest.main()
