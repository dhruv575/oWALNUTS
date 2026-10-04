"""Static-authored mocked acquisition integration; no network or production policy."""
import copy
import json
import zipfile
from pathlib import Path
import pytest
import acquire_deribit_panel as collector
from test_active_contract_selection import inputs


def protocol_and_rows():
    protocol=json.loads(Path(collector.__file__).with_name('DERIBIT_ACCESS_PROTOCOL.json').read_text())
    activity,trade=inputs();forecast=dict(protocol['forecast'],**activity['forecast']);protocol.update(activity);protocol['forecast']=forecast
    protocol['end_utc_exclusive']='2026-09-25T00:00:00+00:00'
    rows=[]
    for name,minutes in [('expired',[29,59,89,119,149,179]),('created',[29,59,89,119,149]),('a',[29,59,89,119]),('b',[29,59,89]),('c',[29,59]),('d',[29]),('thin',[15])]:
        rows += [trade(name,m,i) for i,m in enumerate(minutes)]
    return protocol,rows


def metadata(name,protocol):
    start=collector.millis(protocol['start_utc']);end=collector.millis(protocol['end_utc_exclusive'])
    return dict(instrument_name=name,kind='option',base_currency='BTC',quote_currency='BTC',settlement_currency='BTC',
        expiration_timestamp=end if name=='expired' else end+1,creation_timestamp=start+1 if name=='created' else start,
        option_type='call',strike=100.,contract_size=1.)


def mocks(monkeypatch,protocol,rows):
    calls=[]
    def request(self,method,params):
        self.verify();calls.append((method,params));return metadata(params['instrument_name'],protocol)
    monkeypatch.setattr(collector.Client,'request',request)
    monkeypatch.setattr(collector,'discovery',lambda *args:copy.deepcopy(rows))
    monkeypatch.setattr(collector,'instrument_panel',lambda client,p,name,lo,hi:[r for r in rows if r['instrument_name']==name])
    monkeypatch.setattr(collector.time,'time',lambda:collector.millis(protocol['end_utc_exclusive'])/1000+72*3600)
    return calls


def test_opt_in_activity_metadata_fill_and_source_archive(tmp_path,monkeypatch):
    p,rows=protocol_and_rows();calls=mocks(monkeypatch,p,rows);out=tmp_path/'collection'
    summary=collector.collect(p,out)
    assert summary['status']=='complete_access_panel',summary.get('error')
    selection=json.loads((out/'selection.json').read_text())
    assert selection['selected']==['a','b','c','d']
    assert selection['metadata_rejections']=={'expired':['expiry_not_after_panel_end'],'created':['created_after_panel_start']}
    assert selection['metrics']['thin']['rejection_reasons'] and 'thin' not in selection['metadata']
    assert selection['selection_available_ms']==collector.millis(p['start_utc'])+86400000+60000
    assert summary['source_dependencies_sha256']['active_contract_selection.py']==collector.digest_bytes(Path(collector.__file__).with_name('active_contract_selection.py').read_bytes())
    with zipfile.ZipFile(out/'source-snapshots.zip') as archive:
        assert set(archive.namelist())=={'acquire_deribit_panel.py','active_contract_selection.py'}
        for name,digest in summary['source_dependencies_sha256'].items():assert collector.digest_bytes(archive.read(name))==digest
    assert len(calls)==6 # Metadata for ranked candidates only, no test network.


def test_insufficient_activity_never_relaxes_or_writes_final_selection(tmp_path,monkeypatch):
    p,rows=protocol_and_rows();p['activity_selection']['minimum_trades']=2
    mocks(monkeypatch,p,rows);out=tmp_path/'collection';summary=collector.collect(p,out)
    assert summary['status']=='incomplete' and 'Fewer than four' in summary['error']
    assert not (out/'selection.json').exists()
    evidence=json.loads((out/'activity-metadata-review.json').read_text())
    assert evidence['selected']==['a','b','c']
    assert 'minimum_trades' in evidence['metrics']['d']['rejection_reasons']


def test_legacy_volume_selection_unchanged(tmp_path,monkeypatch):
    p,rows=protocol_and_rows();p.pop('activity_selection')
    for r in rows:
        if r['instrument_name']=='d':r['amount']=1000000.
    mocks(monkeypatch,p,rows);out=tmp_path/'legacy';summary=collector.collect(p,out)
    assert summary['status']=='complete_access_panel'
    selection=json.loads((out/'selection.json').read_text())
    assert selection['selected']==['d','a','b','c']
    assert 'metrics' not in selection and not (out/'activity-ranking.json').exists()
    assert set(summary['source_dependencies_sha256'])=={'acquire_deribit_panel.py'}


def test_helper_source_mutation_detected_without_network(tmp_path,monkeypatch):
    p,_=protocol_and_rows();helper=tmp_path/'helper.py';helper.write_text('original')
    monkeypatch.setattr(collector,'source_files',lambda protocol:{'acquire_deribit_panel.py':Path(collector.__file__),'active_contract_selection.py':helper})
    client=collector.Client(p,tmp_path);client.verify();helper.write_text('mutated')
    with pytest.raises(collector.Incomplete,match='source mutation'):client.verify()


def test_bad_thresholds_fail_before_discovery_or_output(tmp_path,monkeypatch):
    p,_=protocol_and_rows();p['activity_selection']['minimum_trades']=0
    monkeypatch.setattr(collector,'discovery',lambda *a:pytest.fail('No network/discovery'))
    with pytest.raises(ValueError):collector.collect(p,tmp_path/'bad')
    assert not (tmp_path/'bad').exists()


def test_discovery_incomplete_cannot_select(tmp_path,monkeypatch):
    p,_=protocol_and_rows()
    def fail(*args):
        assert (tmp_path/'bad'/'source-snapshots.zip').exists()
        raise collector.Incomplete('Unresolved discovery tie')
    monkeypatch.setattr(collector,'discovery',fail);monkeypatch.setattr(collector.time,'time',lambda:collector.millis(p['end_utc_exclusive'])/1000+72*3600)
    summary=collector.collect(p,tmp_path/'bad')
    assert summary['status']=='incomplete' and not (tmp_path/'bad'/'selection.json').exists()

    with zipfile.ZipFile(tmp_path/'bad'/'source-snapshots.zip') as archive:
        assert set(archive.namelist())=={'acquire_deribit_panel.py','active_contract_selection.py'}
        for name,digest in summary['source_dependencies_sha256'].items():assert collector.digest_bytes(archive.read(name))==digest
