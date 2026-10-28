import unittest
from Crypto.Hash import keccak
from liquidity_states import CALLS,PAIR


class StateCalls(unittest.TestCase):
    def test_selectors_and_balance_address(self):
        signatures=['getReserves()','totalSupply()','kLast()','feeTo()','balanceOf(address)','balanceOf(address)','balanceOf(address)']
        self.assertEqual(len(CALLS),7)
        for (_,_,data,_),signature in zip(CALLS,signatures):
            self.assertEqual(data[:10],'0x'+keccak.new(digest_bits=256,data=signature.encode()).hexdigest()[:8])
            if signature.startswith('balanceOf'):
                self.assertEqual(len(data),74);self.assertEqual(data[10:],'0'*24+PAIR[2:])

if __name__=='__main__':unittest.main()
