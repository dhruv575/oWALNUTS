import unittest
from analyze import ladder,ratio_summary


class AnalysisTests(unittest.TestCase):
    def test_charges_failed_attempt_before_success(self):
        r=ladder([dict(draws=250,status='ok',metrics=dict(passed=False),total_seconds=3,seconds=1,target_calls=100),dict(draws=1000,status='ok',metrics=dict(passed=True),total_seconds=5,seconds=2,target_calls=200)])
        self.assertTrue(r['reached']);self.assertEqual(r['total_seconds'],8);self.assertEqual(r['target_calls'],300)

    def test_failed_and_missing_attempts_censored(self):
        self.assertTrue(ladder([])['censored'])
        r=ladder([dict(draws=d,status='failed',total_seconds=4) for d in [250,1000,3000]])
        self.assertFalse(r['reached']);self.assertEqual(r['total_seconds_spent'],12)

    def test_failed_attempt_does_not_invent_sampler_time(self):
        r=ladder([dict(draws=250,status='failed',resource_seconds=120),dict(draws=1000,status='ok',total_seconds=5,seconds=2,target_calls=200,metrics=dict(passed=True))])
        self.assertEqual(r['total_seconds'],125);self.assertIsNone(r['sampler_seconds'])

    def test_ratio_bootstrap(self):
        self.assertEqual(ratio_summary([2.]*8,1)['interval_95'],[2.,2.])
        self.assertIsNone(ratio_summary([],1)['median'])

    def test_native_ladder_charges_initial_failed_budget(self):
        from analyze_native import ladder as native_ladder
        r=native_ladder([dict(draws=3000,status='ok',total_seconds=3,seconds=1,target_calls=100,metrics=dict(passed=False)),
            dict(draws=6000,status='ok',total_seconds=5,seconds=2,target_calls=200,metrics=dict(passed=True))])
        self.assertEqual(r['budget'],6000);self.assertEqual(r['total_seconds'],8);self.assertEqual(r['target_calls'],300)

    def test_native_ladder_preserves_censoring(self):
        from analyze_native import ladder as native_ladder
        r=native_ladder([dict(draws=d,status='resource_failed',resource_seconds=120) for d in [3000,6000,12000]])
        self.assertFalse(r['reached']);self.assertEqual(r['total_seconds_spent'],360)


if __name__=='__main__':unittest.main()
