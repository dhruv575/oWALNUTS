import unittest
from audit_swap_panel import transition,topic


class SwapTests(unittest.TestCase):
    def test_exact_large_integer_swap(self):
        x,y,a=2**80+7,2**85+13,2**70+3
        out=a*997*y//(x*1000+a*997)
        self.assertGreaterEqual(transition([x,y],[x+a,y-out],[a,0,0,out]),0)

    def test_excess_output_and_inconsistent_reserves_rejected(self):
        with self.assertRaisesRegex(ValueError,'invariant'):
            transition([1000,1000],[1100,900],[100,0,0,100])
        with self.assertRaisesRegex(ValueError,'conservation'):
            transition([1000,1000],[1101,910],[100,0,0,90])

    def test_ethereum_keccak_not_standard_sha3(self):
        self.assertEqual(topic('Transfer(address,address,uint256)'), '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef')


if __name__=='__main__':unittest.main()
