import unittest
from rolling_market_worker import settings,reserved_seeds

class SeedTests(unittest.TestCase):
    def test_all_paths_and_external_seed_pairs_are_disjoint(self):
        self.assertEqual([(settings(i)[0],settings(i)[1]) for i in range(6)],[(0,0),(0,1),(1,0),(1,1),(2,0),(2,1)])
        seeds=reserved_seeds();self.assertEqual(len(seeds),17292);self.assertEqual(len(set(seeds)),len(seeds))
        self.assertTrue(all(0<=s<2**32-1 for s in seeds))
        for i in range(0,len(seeds),2):self.assertEqual(seeds[i+1],seeds[i]+1)
        with self.assertRaises(ValueError):settings(6)
