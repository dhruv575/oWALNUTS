import copy
import unittest
import tempfile
import json
import hashlib
import zipfile
from pathlib import Path
from market_flow_features import build_panel,training_fixture,load_verified_panel,digest_json


class MarketFeaturesTests(unittest.TestCase):
    def test_verified_loader_rejects_tampering_and_wrong_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);protocol,_,_=self.setup();protocol['contracts']=1
            source=b'# fixed collector\n';trade=self.trade(30,trade_id='one')
            summary=dict(status='complete_access_panel',selected=['option'],trade_counts={'option':1},field_quality={'option':{'file':'trades-01.json','total':1}},protocol_sha256=digest_json(protocol),source_sha256=hashlib.sha256(source).hexdigest())
            objects={'protocol.json':protocol,'summary.json':summary,'selection.json':{'selected':['option']},'trades-01.json':[trade],'independent-audit.json':{'passed':True,'trades':1}}
            for name,value in objects.items():(root/name).write_text(json.dumps(value))
            with zipfile.ZipFile(root/'source-snapshots.zip','w') as archive:archive.writestr('acquire_deribit_panel.py',source)
            def bind():
                hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.name!='artifact-hashes.json'}
                (root/'artifact-hashes.json').write_text(json.dumps(hashes))
                return hashlib.sha256((root/'artifact-hashes.json').read_bytes()).hexdigest()
            digest=bind();panel=load_verified_panel(root,expected_manifest_sha256=digest,expected_protocol_sha256=digest_json(protocol))
            self.assertEqual(panel['stabilizer']['value'],1e-8)
            (root/'trades-01.json').write_text('[]')
            with self.assertRaises(ValueError):load_verified_panel(root,expected_manifest_sha256=digest,expected_protocol_sha256=digest_json(protocol))
            (root/'trades-01.json').write_text(json.dumps([trade]));(root/'selection.json').write_text(json.dumps({'selected':['wrong']}));digest=bind()
            with self.assertRaises(ValueError):load_verified_panel(root,expected_manifest_sha256=digest,expected_protocol_sha256=digest_json(protocol))

    def test_invalid_sequence_asof_and_phase(self):
        row=self.trade(30);row['trade_seq']=True
        with self.assertRaises(ValueError):self.panel([row])
        panel=self.panel([])
        for asof,phase in [(True,'development'),(1.5,'development'),(1,'unknown')]:
            with self.assertRaises(ValueError):training_fixture(panel,as_of_ms=asof,phase=phase)

    def setup(self):
        protocol=dict(start_utc='1970-01-01T00:00:00+00:00',end_utc_exclusive='1970-01-08T00:00:00+00:00',development_hours=48,validation_hours=24,selection_hours=24,
            exclude_flags=['block_trade_id','combo_id','combo_trade_id'],forecast=dict(feature_bin_minutes=15,availability_lag_seconds=60,maximum_reference_staleness_minutes=30,horizon_minutes=30,origin_stride_minutes=30,estimand='conditional logreturn',availability='event time+60seconds'))
        return protocol,dict(instrument_names=['option'],selection_end_ms=86400000),dict(value=1.,estimated_through_ms=0,provenance='fixed development setting')

    def trade(self,minute,price=10.,amount=1.,direction='buy',sequence=None,**extra):
        return dict(instrument_name='option',timestamp=int(minute*60000),price=price,amount=amount,direction=direction,trade_seq=minute if sequence is None else sequence,**extra)

    def panel(self,trades):
        protocol,selection,stabilizer=self.setup()
        return build_panel(trades,selection,protocol,acquisition_complete=True,stabilizer=stabilizer)

    def test_exact_feature_target_boundaries_and_future_feature_invariance(self):
        # Cutoff30: excludes15, includes30; decision31 target excludes31, includes61.
        trades=[self.trade(15,amount=100),self.trade(20,amount=3),self.trade(30,amount=1,direction='sell'),self.trade(31,price=99),self.trade(45,price=12),self.trade(61,price=20)]
        panel=self.panel(trades);row=panel['records'][1];group=row['groups'][0]
        self.assertAlmostEqual(group['x'],2/5);self.assertAlmostEqual(group['y'],__import__('math').log(2))
        self.assertEqual(group['target_timestamp'],61*60000);self.assertEqual(group['target_available_ms'],62*60000)
        changed=copy.deepcopy(trades);changed[-1]['price']=200.;changed[-1]['amount']=999
        self.assertEqual(self.panel(changed)['records'][1]['groups'][0]['x'],group['x'])

    def test_no_zero_targets_and_no_compressed_missing_grid(self):
        panel=self.panel([self.trade(30),self.trade(60)])
        self.assertIsNone(panel['records'][2]['groups'][0]['y'])
        self.assertFalse(panel['records'][0]['groups'][0]['x_available'])
        self.assertEqual(panel['records'][3]['cutoff_ms'],90*60000)
        fixture=training_fixture(panel,as_of_ms=95*60000,phase='development')
        self.assertEqual(len(fixture['data']['y']),4)
        self.assertFalse(fixture['data']['observation_mask'][2][0])

    def test_training_asof_cannot_see_unfinalized_last_trade(self):
        panel=self.panel([self.trade(30),self.trade(45,price=12)])
        early=training_fixture(panel,as_of_ms=61*60000,phase='development')
        self.assertFalse(early['data']['observation_mask'][1][0]);self.assertEqual(early['data']['y'][1][0],0.)
        later=training_fixture(panel,as_of_ms=62*60000,phase='development')
        self.assertTrue(later['data']['observation_mask'][1][0])

    def test_stale_reference_flags_and_phase_purge(self):
        panel=self.panel([self.trade(1),self.trade(40),self.trade(45,block_trade_id='block'),self.trade(2880),self.trade(2890)])
        self.assertEqual(panel['excluded_trades'],1)
        # Cutoff2850 lies in development, but label window finalizes2882>2880.
        row=panel['records'][95]
        self.assertTrue(row['groups'][0]['phase_boundary_purged'])
        self.assertFalse(row['groups'][0]['observation_mask'])
        protocol,selection,stabilizer=self.setup()
        with self.assertRaises(ValueError):build_panel([],selection,protocol,acquisition_complete=False,stabilizer=stabilizer)
        stabilizer['estimated_through_ms']=49*3600000
        with self.assertRaises(ValueError):build_panel([],selection,protocol,acquisition_complete=True,stabilizer=stabilizer)


if __name__=='__main__':unittest.main()
