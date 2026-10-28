import unittest
from precision_comparison import compare

class ComparisonTests(unittest.TestCase):
    def test_missing_results_do_not_shrink_denominator(self):
        rows=[dict(index=i,status='missing') for i in range(24)]
        r=compare(rows,rows)
        self.assertEqual((r['planned'],r['available_pairs'],r['long_passed']),(24,0,0))

    def test_flagged_fit_can_improve_prediction_without_passing(self):
        def fit(i,difference,flags):
            return dict(index=i,status='complete',month='fixture',tick=i,method=2,reference={'passed':True},flagged_coordinates=flags,
                predictive=dict(status='available',difference=dict(logpdf=difference,pit=difference),logpdf_mcse=.1,pit_mcse=.1))
        r=compare([fit(i,.2,[]) for i in range(24)],[fit(i,.1,['log_sigma']) for i in range(24)])
        self.assertEqual(r['long_passed'],0)
        self.assertEqual(r['improvements']['logpdf']['absolute_discrepancy_improved'],24)
        self.assertEqual(r['improvements']['logpdf']['mcse_reduced'],0)
