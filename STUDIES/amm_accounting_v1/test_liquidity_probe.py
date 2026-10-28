import unittest
from liquidity_probe import START,BLOCK,TOPICS,partitions


class TransportPartition(unittest.TestCase):
    def test_topics_match_ethereum_keccak(self):
        from Crypto.Hash import keccak
        signatures=['Mint(address,uint256,uint256)','Burn(address,uint256,uint256,address)']
        self.assertEqual(TOPICS,['0x'+keccak.new(digest_bits=256,data=s.encode()).hexdigest() for s in signatures])

    def test_same_fixed_range_no_gaps_or_overlap(self):
        for width,count in ((128,32),(256,16)):
            ranges=partitions(width)
            self.assertEqual(len(ranges),count)
            expanded=[n for lo,hi in ranges for n in range(lo,hi+1)]
            self.assertEqual(expanded,list(range(START,BLOCK+1)))
            self.assertTrue(all(hi-lo+1<=width for lo,hi in ranges))
        with self.assertRaises(ValueError):partitions(4096)

if __name__=='__main__':unittest.main()
