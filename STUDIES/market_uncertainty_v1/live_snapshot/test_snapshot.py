import hashlib,json
from pathlib import Path
import snapshot as module

def line(t,raw=None,**extra):return dict(receipt_monotonic_ns=t,receipt_utc_ns=t+1000,connection=1,raw=json.dumps(raw or {}),**extra)
def write(path,rows):path.write_bytes(b''.join(json.dumps(r).encode()+b'\n' for r in rows))
def fixture(tmp_path):
 c=tmp_path/'capture';c.mkdir();(c/'selection.json').write_text(json.dumps(dict(channels=['x'])))
 write(c/'receipts.jsonl',[line(1,dict(id=1,result=['x'])),line(10,dict(params=dict(channel='x')))])
 write(c/'lifecycle.jsonl',[dict(kind='subscribed',receipt_monotonic_ns=2,receipt_utc_ns=1002,connection=1)])
 return c

def test_partial_line_and_append(tmp_path,monkeypatch):
 c=fixture(tmp_path);p=c/'receipts.jsonl';original=p.read_bytes();p.write_bytes(original+b'{"partial":')
 result=module.snapshot(c,tmp_path/'snapshot')
 assert (tmp_path/'snapshot/receipts.jsonl').read_bytes()==original
 assert result['receipt_prefix']['records']==2
 # Appends after fixed read boundary must not invalidate already captured bytes.
 p.write_bytes(original);real=module.sha_prefix;done=[]
 def append_then_hash(path,n):
  if Path(path)==p and not done:
   with p.open('ab') as f:f.write(json.dumps(line(20)).encode()+b'\n')
   done.append(True)
  return real(path,n)
 monkeypatch.setattr(module,'sha_prefix',append_then_hash)
 r=module.snapshot(c,tmp_path/'appended');assert r['receipt_prefix']['records']==2

def test_historical_cutoff_no_future_leak(tmp_path):
 c=fixture(tmp_path);a=module.snapshot(c,tmp_path/'a',10)
 with (c/'receipts.jsonl').open('ab') as f:f.write(json.dumps(line(30)).encode()+b'\n')
 with (c/'lifecycle.jsonl').open('ab') as f:f.write(json.dumps(dict(kind='connection_gap',receipt_monotonic_ns=31,receipt_utc_ns=1031,start_monotonic_ns=9,detected_monotonic_ns=31)).encode()+b'\n')
 b=module.snapshot(c,tmp_path/'b',10)
 assert a['coverage_intervals']==b['coverage_intervals'] and a['gaps']==b['gaps']
 assert a['files_sha256']==b['files_sha256']

def test_live_late_gap_is_conservative_and_source_bound(tmp_path):
 c=fixture(tmp_path)
 with (c/'lifecycle.jsonl').open('ab') as f:f.write(json.dumps(dict(kind='connection_gap',receipt_monotonic_ns=31,receipt_utc_ns=1031,start_monotonic_ns=9,detected_monotonic_ns=31)).encode()+b'\n')
 r=module.snapshot(c,tmp_path/'out')
 assert r['coverage_intervals'][0]['end_monotonic_ns']==9
 assert r['gaps'][0]['start_monotonic_ns']==9 and 'resubscribed_monotonic_ns' not in r['gaps'][0]
 assert r['source_sha256']==hashlib.sha256((tmp_path/'out/snapshot-source.py').read_bytes()).hexdigest()
 assert r['end_utc_ns']==1010 and r['status']=='prefix_snapshot_not_terminal'

def test_reconciliation_requires_rebuild_for_late_gap(tmp_path):
 c=fixture(tmp_path);module.snapshot(c,tmp_path/'prefix')
 final=dict(schema='public-receipt-collector-v2',status='duration_complete_with_gaps',end_monotonic_ns=40,gaps=[dict(start_monotonic_ns=9,detected_monotonic_ns=30)])
 (c/'summary.json').write_text(json.dumps(final))
 r=module.reconcile(tmp_path/'prefix/prefix-summary.json',c/'summary.json')
 assert r['prefix_bytes_match'] and r['requires_rebuild']

def test_bounded_copy(tmp_path):
 c=fixture(tmp_path);first=(c/'receipts.jsonl').read_bytes().splitlines(keepends=True)[0]
 r=module.copy_complete(c/'receipts.jsonl',tmp_path/'small.jsonl',max_bytes=len(first)+3)
 assert r['cap_clipped'] and r['records']==1 and r['bytes']==len(first)
