import unittest
import numpy as np
from analyze import precision, summarize


class AnalysisTests(unittest.TestCase):
    def test_constant_density_with_extreme_offset(self):
        for k in (400, 1600):
            result = precision(np.full((4, k), -10000.), np.full((4, k), .25), k)
            self.assertEqual(result, dict(logpdf=-10000., pit=.25, logpdf_mcse=0., pit_mcse=0.))

    def test_log_mean_density_not_mean_log_density(self):
        logs = np.tile(np.log([1., 3.]), (4, 200))
        result = precision(logs, np.full((4, 400), .5), 400)
        self.assertAlmostEqual(result['logpdf'], np.log(2.))
        self.assertNotAlmostEqual(result['logpdf'], logs.mean())

    def test_missing_pairs_and_failed_references_preserved(self):
        rows = []
        for job in range(12):
            for tick in range(1, 9):
                rows.append(dict(job=job, tick=tick, month=str(job//4), reference_pass=tick != 8,
                                 metrics_status='unavailable' if job == 1 else 'available',
                                 difference=dict(logpdf=(-2. if job%2 else 1.), pit=.01),
                                 candidate=dict(logpdf_mcse=.1, pit_mcse=.01)))
        summaries, pairs = summarize(rows)
        self.assertEqual(len(pairs), 48)
        self.assertEqual(sum(p['available'] for p in pairs), 40)
        self.assertEqual(sum(not p['reference_pass'] for p in pairs), 6)
        self.assertEqual(summaries[2]['planned'], 8)
        self.assertEqual(summaries[2]['available'], 0)
        self.assertFalse(summaries[2]['full_panel_available'])
        pair = next(p for p in pairs if p['low_job'] == 2)
        self.assertEqual(pair['high_minus_low_absolute_discrepancy']['logpdf'], 1.)


if __name__ == '__main__':
    unittest.main()
