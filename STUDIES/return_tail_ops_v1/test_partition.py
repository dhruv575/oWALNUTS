import unittest
from partition import MONTHS, assignments

class PartitionTests(unittest.TestCase):
    def test_complete_disjoint_fixed_work(self):
        for phase,expected,count in (("candidate",[(m,t) for m,n in MONTHS for t in range(1,n+1)],364),("reference",[(m,i) for m,_ in MONTHS for i in range(8)],2)):
            shards=[assignments(phase,i) for i in range(12)]
            self.assertTrue(all(len(x)==count for x in shards))
            rebuilt=[shards[i%12][i//12] for i in range(len(expected))]
            self.assertEqual(rebuilt,expected)
            self.assertEqual(len(set(rebuilt)),len(expected))
    def test_invalid_shard(self):
        for value in (-1,12,True,1.5):
            with self.assertRaises(ValueError): assignments('candidate',value)
