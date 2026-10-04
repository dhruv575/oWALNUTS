import unittest
from reference_bank_controls import make_plan,summarize


class BankControlTests(unittest.TestCase):
    def test_independent_streams_and_prospective_plan(self):
        p=make_plan(trials=2);streams=[s for c in p['cells'] for s in c['fit_seeds']+c['init_seeds']+[c['bootstrap_seed']]]
        self.assertEqual(len(streams),len(set(streams)));self.assertFalse(p['frozen']);self.assertEqual(len(p['cells']),8)

    def test_false_resolution_and_failure_denominator(self):
        rows=[dict(status='completed',bank_status='numerically_resolved_under_declared_checks',backend_b_shift=.5,both_endpoints_cover_truth=False,max_endpoint_error_over_width=.2),dict(status='failed')]
        r=summarize(rows,3)
        self.assertEqual(r['completed'],1);self.assertEqual(r['shifted_backend_false_resolution_rate'],1/3)
        self.assertEqual(r['resolved_but_truth_outside_bounds_rate'],1/3)
        self.assertEqual(r['resolved_but_endpoint_error_over_budget_rate'],1/3)


if __name__=='__main__':unittest.main()
