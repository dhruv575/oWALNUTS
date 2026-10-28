import copy
import unittest
from liquidity_receipts import verify_receipt


class ReceiptIdentity(unittest.TestCase):
    def test_wrong_receipt_and_altered_log_rejected(self):
        e=dict(address='pair',topics=['topic'],data='0x01',blockNumber='0x1',blockHash='block',transactionHash='tx',transactionIndex='0x0',logIndex='0x2',removed=False)
        r=dict(transactionHash='tx',blockHash='block',status='0x1',logs=[copy.deepcopy(e)])
        verify_receipt(r,[e]);r['logs'][0]['data']='0x02'
        with self.assertRaisesRegex(ValueError,'log mismatch'):verify_receipt(r,[e])
        r['transactionHash']='other'
        with self.assertRaisesRegex(ValueError,'Receipt transaction'):verify_receipt(r,[e])

if __name__=='__main__':unittest.main()
