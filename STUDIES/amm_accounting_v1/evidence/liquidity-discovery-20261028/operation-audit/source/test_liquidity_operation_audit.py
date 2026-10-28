import copy
import json
import unittest
from pathlib import Path
from liquidity_operation_audit import audit,MINT,BURN


class ObservedArithmetic(unittest.TestCase):
    def test_recorded_operations_and_changed_mint_amount(self):
        root=Path(__file__).parent/'evidence/liquidity-discovery-20261028/states-aws/states01'
        states=json.loads((root/'STATES.json').read_bytes());logs=json.loads((root/'BLOCK-LOGS.json').read_bytes())
        counts=[]
        for n,entries in logs.items():counts.append(len(audit(states[str(int(n)-1)],states[n],entries)['operations']))
        self.assertEqual(counts,[2,2,1])
        n=next(iter(logs));changed=copy.deepcopy(logs[n])
        event=next(e for e in changed if e['topics'][0]==MINT)
        event['data']='0x'+format(int(event['data'][2:66],16)+1,'064x')+event['data'][66:]
        with self.assertRaisesRegex(ValueError,'amounts'):audit(states[str(int(n)-1)],states[n],changed)
        changed=copy.deepcopy(logs[n]);event=next(e for e in changed if e['topics'][0]==BURN)
        event['topics'][2]='0x'+'0'*24+'1'*40
        with self.assertRaisesRegex(ValueError,'recipient'):audit(states[str(int(n)-1)],states[n],changed)

if __name__=='__main__':unittest.main()
