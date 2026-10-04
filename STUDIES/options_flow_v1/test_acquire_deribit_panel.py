import unittest
from acquire_deribit_panel import discovery,instrument_panel,Incomplete,merge

class Client:
    def __init__(self,responses):self.responses=iter(responses);self.calls=[]
    def request(self,method,params):self.calls.append((method,params));return next(self.responses)
def trade(seq,time=10):return dict(timestamp=time,trade_id=str(seq),trade_seq=seq,instrument_name='BTC-X',amount=1.,price=.1,direction='buy')
class AcquisitionTests(unittest.TestCase):
    def test_discovery_saturated_single_ms_fails(self):
        c=Client([dict(has_more=True,trades=[trade(1)])])
        with self.assertRaises(Incomplete):discovery(c,{'count':1000},10,10)
    def test_discovery_overlap_deduplicates(self):
        c=Client([dict(has_more=True,trades=[]),dict(has_more=False,trades=[trade(1,9),trade(2,10)]),dict(has_more=False,trades=[trade(2,10),trade(3,11)])])
        rows=discovery(c,{'count':1000},9,11)
        self.assertEqual(len(rows),3)
    def test_sequence_overlap_and_progress(self):
        c=Client([dict(trades=[trade(1)]),dict(trades=[trade(3)]),dict(has_more=True,trades=[trade(1),trade(2)]),dict(has_more=False,trades=[trade(2),trade(3)])])
        self.assertEqual(len(instrument_panel(c,{'count':1000},'BTC-X',0,20)),3)
        self.assertEqual(c.calls[3][1]['start_seq'],2)
        for _,params in c.calls[2:]:
            self.assertNotIn('start_timestamp',params);self.assertNotIn('end_timestamp',params);self.assertEqual(params['end_seq'],3)
    def test_gap_fails(self):
        c=Client([dict(trades=[trade(1)]),dict(trades=[trade(3)]),dict(has_more=False,trades=[trade(1),trade(3)])])
        with self.assertRaises(Incomplete):instrument_panel(c,{'count':1000},'BTC-X',0,20)
    def test_conflicting_duplicate_fails(self):
        a=trade(1);b=dict(a,amount=2.)
        with self.assertRaises(Incomplete):merge([a,b])



class ProtocolTests(unittest.TestCase):
    def test_protocol_mutation_detected_without_network(self):
        import tempfile,json
        from pathlib import Path
        from acquire_deribit_panel import Client as ActualClient
        with tempfile.TemporaryDirectory() as directory:
            protocol={'x':1};client=ActualClient(protocol,directory);protocol['x']=2
            with self.assertRaises(Incomplete):client.verify()
    def test_invalid_base_or_naive_dates(self):
        import json,copy
        from pathlib import Path
        from acquire_deribit_panel import validate_protocol
        protocol=json.loads(Path(__file__).with_name('DERIBIT_ACCESS_PROTOCOL.json').read_text())
        for key,value in [('production_base','https://example.com/'),('start_utc','2026-09-25T00:00:00')]:
            changed=copy.deepcopy(protocol);changed[key]=value
            with self.assertRaises(ValueError):validate_protocol(changed)
    def test_instrument_name_never_used_as_output_path(self):
        from pathlib import Path
        source=Path(__file__).with_name('acquire_deribit_panel.py').read_text()
        self.assertIn("filename=f'trades-{ordinal:02d}.json'",source)
        self.assertNotIn("out/(name+",source)

if __name__=='__main__':unittest.main()
