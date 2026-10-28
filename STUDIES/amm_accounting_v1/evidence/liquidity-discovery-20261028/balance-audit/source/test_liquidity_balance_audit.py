import unittest
from liquidity_balance_audit import reconcile,address,TRANSFER,PAIR,USDC,ZERO


class BalanceAudit(unittest.TestCase):
    def test_self_transfer_and_ambiguous_zero_recipient(self):
        pad=lambda a:'0x'+'0'*24+a[2:]
        log=lambda c,a,b,v:dict(address=c,topics=[TRANSFER,pad(a),pad(b)],data='0x'+format(v,'064x'),transactionHash='tx',logIndex='0x1')
        state=dict(balance_usdc=100,balance_weth=200,pair_lp_balance=0,supply=1000,reserves=[100,200,0])
        r=reconcile(state,state,[log(USDC,PAIR,PAIR,20),log(PAIR,'0x'+'1'*40,ZERO,5)])
        self.assertEqual(r['terminal_balances'][USDC],100)
        self.assertFalse(r['treating_all_nonmint_zero_outflows_as_burns_matches_supply'])
        with self.assertRaisesRegex(ValueError,'underflow'):
            reconcile(state,state,[log(USDC,PAIR,ZERO,101)])
        with self.assertRaisesRegex(ValueError,'padding'):
            address('0x'+'f'*64)

if __name__=='__main__':unittest.main()
