import unittest
from liquidity_probe import START,BLOCK,partitions


class TransportPartition(unittest.TestCase):
    def test_same_fixed_range_no_gaps_or_overlap(self):
        for width,count in ((128,32),(256,16)):
            ranges=partitions(width)
            self.assertEqual(len(ranges),count)
            expanded=[n for lo,hi in ranges for n in range(lo,hi+1)]
            self.assertEqual(expanded,list(range(START,BLOCK+1)))
            self.assertTrue(all(hi-lo+1<=width for lo,hi in ranges))
        with self.assertRaises(ValueError):partitions(4096)

if __name__=='__main__':unittest.main()
