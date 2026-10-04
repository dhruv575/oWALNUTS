"""Offline raw-record consistency audit, independent of collector pagination."""
import hashlib
import json
from pathlib import Path
import zipfile

P = Path(__file__).resolve().parent
def load(p): return json.loads(p.read_text())
def sha(b): return hashlib.sha256(b).hexdigest()
def canonical(x): return sha(json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())
summary=load(P/'summary.json'); protocol=load(P/'protocol.json'); selection=load(P/'selection.json')
assert summary['status']=='complete_access_panel'
assert canonical(protocol)==summary['protocol_sha256']
assert summary['selected']==selection['selected'] and len(set(selection['selected']))==4
requests=sorted(P.glob('*.request.json')); manifest=[]; leaves=[]; discovered={}; sequence_rows={}
for i,path in enumerate(requests,1):
    request=load(path); raw=path.with_name(path.name.replace('.request.json','.response'))
    content=raw.read_bytes(); assert sha(content)==request['response_sha256']
    assert len(content)==request['response_bytes'] and request['http_status']==200
    response=json.loads(content)['result']; params=request['params']
    assert params.get('include_old')=='true' or request['method']=='public/get_instrument'
    for f in [path,raw]:
        data=f.read_bytes(); manifest.append(dict(path=f.name,bytes=len(data),sha256=sha(data)))
    if request['method']=='public/get_last_trades_by_currency_and_time' and not response['has_more']:
        leaves.append((params['start_timestamp'],params['end_timestamp']))
        for trade in response['trades']:
            key=trade['trade_id']
            assert key not in discovered or discovered[key]==trade
            discovered[key]=trade
    if 'start_seq' in params:
        assert request['started_utc']>=selection['selection_completed_utc']
        rows=sequence_rows.setdefault(params['instrument_name'],{})
        for trade in response['trades']:
            key=trade['trade_seq']; assert params['start_seq']<=key<=params['end_seq']
            assert key not in rows or rows[key]==trade
            rows[key]=trade
assert len(requests)==summary['requests']
assert sum(r['bytes'] for r in manifest if r['path'].endswith('.response'))==summary['raw_response_bytes']
leaves.sort(); left=leaves[0][0]; right=left-1
for a,b in leaves:
    assert a<=right+1; right=max(right,b)
assert right-left+1==86400000
volume={}
for t in discovered.values():
    if not any(t.get(k) is not None for k in protocol['exclude_flags']):
        volume[t['instrument_name']]=volume.get(t['instrument_name'],0.)+t['amount']
assert set(volume)==set(selection['first_day_volume'])
assert all(abs(v-selection['first_day_volume'][k])<=1e-9*max(1,v) for k,v in volume.items())
for name in summary['selected']:
    rows=load(P/summary['field_quality'][name]['file'])
    assert len(rows)==summary['trade_counts'][name]
    assert {t['trade_seq']:t for t in rows}==sequence_rows[name]
    seq=sorted(t['trade_seq'] for t in rows)
    assert seq==list(range(seq[0],seq[-1]+1))
    assert {t['trade_id'] for t in rows if t['timestamp']<=right}=={t['trade_id'] for t in discovered.values() if t['instrument_name']==name}
with zipfile.ZipFile(P/'raw-http.zip','x',zipfile.ZIP_DEFLATED) as z:
    for row in manifest:z.writestr(row['path'],(P/row['path']).read_bytes())
with zipfile.ZipFile(P/'raw-http.zip') as z:
    assert all(sha(z.read(row['path']))==row['sha256'] for row in manifest)
result=dict(passed=True,requests=len(requests),trades=sum(summary['trade_counts'].values()),
            checks=['raw hashes/byte counts','discovery interval coverage','first-day volume agreement',
                    'selection before sequence retrieval','trade files equal sequence responses',
                    'contiguous instrument sequences','first-day cross-endpoint agreement','lossless archive roundtrip'],
            limitations=['Does not prove exchange feed completeness or historical receipt availability.',
                         'Does not establish model adequacy or market utility.'],
            raw_archive_sha256=sha((P/'raw-http.zip').read_bytes()),entries=manifest)
with (P/'independent-audit.json').open('x') as f:json.dump(result,f,indent=2)
(P/'.gitignore').write_text('*.request.json\n*.response\n')
print(json.dumps({k:v for k,v in result.items() if k!='entries'}))
