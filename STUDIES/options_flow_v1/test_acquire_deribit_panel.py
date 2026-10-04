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
        c=Client([dict(trades=[trade(1)]),dict(trades=[trade(3)]),dict(has_more=False,trades=[trade(1),trade(2),trade(3)]),dict(has_more=False,trades=[trade(1),trade(2),trade(3)]),dict(has_more=True,trades=[trade(1),trade(2)]),dict(has_more=False,trades=[trade(2),trade(3)])])
        self.assertEqual(len(instrument_panel(c,{'count':1000},'BTC-X',0,20)),3)
        self.assertEqual(c.calls[5][1]['start_seq'],2)
        for _,params in c.calls[4:]:
            self.assertNotIn('start_timestamp',params);self.assertNotIn('end_timestamp',params);self.assertEqual(params['end_seq'],3)
    def test_gap_fails(self):
        c=Client([dict(trades=[trade(1)]),dict(trades=[trade(3)]),dict(has_more=False,trades=[trade(1),trade(2),trade(3)]),dict(has_more=False,trades=[trade(1),trade(2),trade(3)]),dict(has_more=False,trades=[trade(1),trade(3)])])
        with self.assertRaises(Incomplete):instrument_panel(c,{'count':1000},'BTC-X',0,20)
    def test_conflicting_duplicate_fails(self):
        a=trade(1);b=dict(a,amount=2.)
        with self.assertRaises(Incomplete):merge([a,b])



class ProtocolTests(unittest.TestCase):
    def test_history_requires_explicit_flag_and_records_it(self):
        import json,tempfile
        from pathlib import Path
        from unittest.mock import patch,MagicMock
        from acquire_deribit_panel import validate_protocol,Client as ActualClient
        protocol=json.loads(Path(__file__).with_name('DERIBIT_ACCESS_PROTOCOL.json').read_text())
        protocol['production_base']='https://history.deribit.com/api/v2/'
        with self.assertRaises(ValueError):validate_protocol(protocol)
        protocol['include_old']=True;validate_protocol(protocol)
        response=MagicMock();response.status=200
        response.read.return_value=b'{"result":{"trades":[],"has_more":false}}'
        response.__enter__.return_value=response
        with tempfile.TemporaryDirectory() as directory,patch('urllib.request.urlopen',return_value=response) as request:
            client=ActualClient(protocol,directory)
            original={'currency':'BTC'}
            client.request('public/get_last_trades_by_currency_and_time',original)
            self.assertEqual(original,{'currency':'BTC'})
            self.assertIn('include_old=true',request.call_args.args[0].full_url)
            record=json.loads((Path(directory)/'0001.request.json').read_text())
            self.assertEqual(record['params']['include_old'],'true')

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



class StructuralValidationTests(unittest.TestCase):
    def test_boolean_fractional_nonfinite_integer_fields_rejected(self):
        from acquire_deribit_panel import valid_trade
        for key in ['timestamp','trade_seq']:
            for value in [True,False,.5,float('nan'),float('inf'),-1,'10']:
                row=trade(1);row[key]=value
                with self.assertRaises(Incomplete):valid_trade(row,0,20)
    def test_boundary_probe_cardinality(self):
        for boundary in [[],[trade(1),trade(2)],{},None]:
            client=Client([dict(trades=boundary),dict(trades=[trade(3)])])
            with self.assertRaises(Incomplete):instrument_panel(client,{'count':1000},'BTC-X',0,20)
    def test_sequence_cannot_exceed_frozen_upper(self):
        client=Client([dict(trades=[trade(1)]),dict(trades=[trade(3)]),dict(has_more=False,trades=[trade(1),trade(2),trade(3)]),dict(has_more=False,trades=[trade(1),trade(2),trade(3)]),dict(has_more=True,trades=[trade(1),trade(4)])])
        with self.assertRaises(Incomplete):instrument_panel(client,{'count':1000},'BTC-X',0,20)
    def test_metadata_units_and_type_required(self):
        from acquire_deribit_panel import validate_instrument
        base=dict(instrument_name='BTC-X',kind='option',base_currency='BTC',quote_currency='BTC',settlement_currency='BTC',option_type='call',strike=50000.,contract_size=1.,creation_timestamp=1,expiration_timestamp=20)
        validate_instrument(base,'BTC-X')
        for key,value in [('quote_currency','USD'),('settlement_currency',None),('option_type','future'),('strike',True),('contract_size',0),('expiration_timestamp',float('inf'))]:
            changed=dict(base);changed[key]=value
            with self.assertRaises(Incomplete):validate_instrument(changed,'BTC-X')
    def test_reversed_boundary_sequences(self):
        client=Client([dict(trades=[trade(3,9)]),dict(trades=[trade(1,11)]),dict(has_more=False,trades=[trade(3,9)]),dict(has_more=False,trades=[trade(1,11)])])
        with self.assertRaises(Incomplete):instrument_panel(client,{'count':1000},'BTC-X',0,20)

class OrderingAndTieTests(unittest.TestCase):
    def pages(self,body):
        ties=dict(has_more=False,trades=[trade(3),trade(1),trade(2)])
        return Client([dict(trades=[trade(2)]),dict(trades=[trade(2)]),ties,ties,body])
    def test_unsorted_valid_and_full_boundary_ties(self):
        c=self.pages(dict(has_more=False,trades=[trade(3),trade(1),trade(2)]))
        rows=instrument_panel(c,{'count':1000},'BTC-X',0,20)
        self.assertEqual([r['trade_seq'] for r in rows],[1,2,3])
        self.assertEqual(c.calls[-1][1]['start_seq'],1);self.assertEqual(c.calls[-1][1]['end_seq'],3)
    def test_duplicate_page_sequence_rejected(self):
        c=self.pages(dict(has_more=False,trades=[trade(1),trade(1),trade(3)]))
        with self.assertRaises(Incomplete):instrument_panel(c,{'count':1000},'BTC-X',0,20)
    def test_saturated_boundary_fails_closed(self):
        c=Client([dict(trades=[trade(1)]),dict(trades=[trade(3)]),dict(has_more=True,trades=[trade(1)])])
        with self.assertRaises(Incomplete):instrument_panel(c,{'count':1000},'BTC-X',0,20)

if __name__=='__main__':unittest.main()
