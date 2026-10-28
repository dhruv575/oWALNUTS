import copy
import unittest
from unittest.mock import patch
from test_analysis_gate import GateTests
from primary_analysis import analyze


def constant_summary(scores, n, block, seed):
    means = scores.mean(axis=0).tolist()
    return dict(mean=means, lower_9875=means, interval_95=[[v, v] for v in means],
                block=block, seed=seed)


class PrimaryAnalysisTests(unittest.TestCase):
    def test_incomplete_denominator_never_bootstraps(self):
        calendar, reports = GateTests().fixture()
        with patch('primary_analysis.summarize') as bootstrap:
            result = analyze(calendar, reports[:-1])
            bootstrap.assert_not_called()
        self.assertEqual(result['status'], 'not_admitted')

    def test_fixed_seeds_paired_columns_and_no_month_pooling(self):
        calendar, reports = GateTests().fixture()
        with patch('primary_analysis.summarize', side_effect=constant_summary) as bootstrap:
            result = analyze(calendar, reversed(reports))
        self.assertTrue(result['predictive_confirmation'])
        self.assertTrue(result['predictive_functional_equivalence'])
        self.assertEqual([c.args[3] for c in bootstrap.call_args_list], list(range(398300000, 398300006)))
        self.assertEqual([c.args[1:3] for c in bootstrap.call_args_list],
                         [(1440, 96), (1440, 48), (1440, 336), (1488, 96), (1488, 48), (1488, 336)])
        self.assertTrue(all(c.args[0].shape[1] == 3 for c in bootstrap.call_args_list))

    def test_one_failed_month_prevents_confirmation(self):
        calendar, reports = GateTests().fixture()
        for report in reports:
            if report['fixture']['month'] == '2025-10':
                report['comparisons'][0].update(model=-.02, total=-.019)
        with patch('primary_analysis.summarize', side_effect=constant_summary):
            self.assertFalse(analyze(calendar, reports)['predictive_confirmation'])

    def test_calendar_and_baseline_consistency(self):
        calendar, reports = GateTests().fixture()
        altered = copy.deepcopy(calendar)
        altered[0]['primary'] = False
        with self.assertRaises(ValueError): analyze(altered, reports)
        reports[0]['comparisons'][1].update(inference=.002, total=.102)
        with self.assertRaises(ValueError): analyze(calendar, reports)

    def test_sensitivity_cannot_replace_failed_primary(self):
        calendar, reports = GateTests().fixture()
        def summary(scores, n, block, seed):
            result = constant_summary(scores, n, block, seed)
            if block == 96:
                result['lower_9875'] = [0., .1, .001]
                result['interval_95'][2] = [-.01, .009]
            return result
        with patch('primary_analysis.summarize', side_effect=summary):
            result = analyze(calendar, reports)
        self.assertFalse(result['predictive_confirmation'])
        self.assertFalse(result['predictive_functional_equivalence'])
        self.assertTrue(result['block_sensitivity_changes_predictive_conclusion'])
        self.assertTrue(result['block_sensitivity_changes_equivalence_conclusion'])


if __name__ == '__main__': unittest.main()
