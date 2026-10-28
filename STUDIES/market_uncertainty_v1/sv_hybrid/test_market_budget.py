import unittest
from market_budget import budget

class BudgetTests(unittest.TestCase):
    def test_existing_budget_unchanged(self):
        r=budget(dict(warmup=1000,retained=2000))
        self.assertEqual((r['cap'],r['evaluations'],r['chain_seconds'],r['chain_bytes']),(295,2000000,300,64*1024**2))

    def test_precision_is_bounded_and_blocked_only(self):
        r=budget(dict(warmup=4000,retained=8000,methods=[2]))
        self.assertEqual((r['cap'],r['evaluations'],r['chain_seconds']),(1195,8000000,1200))
        for methods in ([0,1],[],None):
            with self.assertRaises(ValueError):budget(dict(warmup=4000,retained=8000,methods=methods))
        with self.assertRaises(ValueError):budget(dict(warmup=4000,retained=16000,methods=[2]))
