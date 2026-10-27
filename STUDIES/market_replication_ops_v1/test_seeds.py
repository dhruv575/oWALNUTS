import unittest
from seed_derivation_snapshot import native_roles,flatten
class SeedTests(unittest.TestCase):
    def test_full_last_call_is_reserved(self):
        roles=native_roles(2026102801000000,2026102802000000,1440);self.assertEqual(len(roles['warm_call_inputs']),5760);self.assertEqual(roles['warm_call_inputs'][-1],2026102802005759)
    def test_distinct_month_ranges(self):
        a=flatten(native_roles(2026102801000000,2026102802000000,1440));b=flatten(native_roles(2026102801100000,2026102802100000,1488));self.assertFalse(a&b)
if __name__=='__main__':unittest.main()
