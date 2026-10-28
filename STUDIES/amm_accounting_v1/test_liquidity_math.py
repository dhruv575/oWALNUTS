import unittest
from liquidity_math import protocol_fee,mint,burn,U256


class LiquidityTests(unittest.TestCase):
    def test_initial_lock_is_supply_not_a_burn(self):
        r=mint([0,0],[4000,9000],0,0,True)
        self.assertEqual((r['liquidity'],r['locked_liquidity'],r['supply']),(5000,1000,6000))
        self.assertEqual(r['k_last'],36000000)

    def test_protocol_growth_fee_and_switch_off(self):
        # sqrt(k) grows 100 -> 110: 6500*10/(550+100)=100.
        self.assertEqual(protocol_fee([110,110],6500,10000,True)['minted'],100)
        self.assertEqual(protocol_fee([110,110],6500,10000,False),dict(minted=0,supply=6500,k_last=0))
        self.assertEqual(protocol_fee([99,99],6500,10000,True)['minted'],0)

    def test_fee_dilution_precedes_mint_and_burn(self):
        r=mint([110,110],[121,121],6500,10000,True)
        self.assertEqual((r['protocol_liquidity'],r['liquidity'],r['supply']),(100,660,7260))
        b=burn([110,110],[121,132],6500,10000,True,600)
        self.assertEqual(b['amounts'],[11,12])
        self.assertEqual(b['supply'],6000)
        self.assertEqual(b['reserves'],[110,120])

    def test_donations_are_balances_not_old_reserves(self):
        b=burn([1000,1000],[1200,1500],1000,0,False,100)
        self.assertEqual(b['amounts'],[120,150])
        m=mint([1000,1000],[1200,1500],1000,0,False)
        self.assertEqual(m['liquidity'],200)

    def test_rounding_and_overflow_are_not_float_arithmetic(self):
        self.assertEqual(protocol_fee([101,101],1,10000,True)['minted'],0)
        with self.assertRaises(ValueError):protocol_fee([2,2],U256,1,True)
        with self.assertRaises(ValueError):mint([0,0],[1000,1000],0,0,False)
        with self.assertRaises(ValueError):burn([100,100],[100,100],1000,0,False,1)
        with self.assertRaises(ValueError):mint([100,100],[99,100],100,0,False)


if __name__=='__main__':unittest.main()
