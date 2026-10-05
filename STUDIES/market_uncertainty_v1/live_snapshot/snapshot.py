"""Immutable receipt-prefix snapshots. Never writes the active capture."""
import argparse,hashlib,json,time,os
from pathlib import Path

def sha_prefix(path,length):
 h=hashlib.sha256();remaining=length
 with Path(path).open('rb') as f:
  while remaining:
   block=f.read(min(1048576,remaining))
   if not block:raise ValueError('Source prefix truncated')
   h.update(block);remaining-=len(block)
 return h.hexdigest()

def copy_complete(source,dest,cutoff=None,max_bytes=50_000_000):
 """Capture one fixed file-size boundary; ignore later appends/partial last line."""
 if type(max_bytes)is not int or max_bytes<1:raise ValueError('Positive byte cap required')
 last=None;count=0;written=0;h=hashlib.sha256()
 with Path(source).open('rb') as f,Path(dest).open('xb') as out:
  observed=os.fstat(f.fileno()).st_size;boundary=min(observed,max_bytes)
  while f.tell()<boundary:
   line=f.readline(boundary-f.tell())
   if not line.endswith(b'\n'):break
   row=json.loads(line);stamp=row.get('receipt_monotonic_ns')
   if type(stamp)is not int or (last is not None and stamp<last):raise ValueError('Nonmonotone/missing receipt clock')
   if cutoff is not None and stamp>cutoff:break
   last=stamp;count+=1;written+=len(line);out.write(line);h.update(line)
  out.flush();os.fsync(out.fileno())
 digest=h.hexdigest()
 if sha_prefix(source,written)!=digest:raise ValueError('Source prefix changed during copying')
 return dict(source=str(Path(source).resolve()),observed_file_size=observed,read_boundary_bytes=boundary,byte_cap=max_bytes,cap_clipped=observed>max_bytes,bytes=written,sha256=digest,records=count,last_complete_receipt_ns=last)

def context(receipts,lifecycle,channels,end):
 acknowledgments={};last={};gaps=[];previous=None
 for row in receipts:
  t=row['receipt_monotonic_ns'];connection=row['connection'];message=json.loads(row['raw'])
  if previous is not None and connection!=previous:
   gaps.append(dict(start=last[previous],end=t,reason='connection_change'))
  previous=connection;last[connection]=t
  if message.get('id')==1:
   if set(message.get('result',[]))!=set(channels):raise ValueError('Subscription ACK differs')
   acknowledgments[connection]=t
  elif message.get('params',{}).get('channel') and connection not in acknowledgments:raise ValueError('Data before ACK')
 for event in lifecycle:
  if event.get('kind')=='connection_gap':
   start=event['start_monotonic_ns'];detected=event['detected_monotonic_ns']
   resumed=[t for t in acknowledgments.values() if t>=detected]
   gaps.append(dict(start=start,end=min(resumed) if resumed else end,reason='recorded_gap',unclosed=not bool(resumed)))
 intervals=[]
 for connection,start in acknowledgments.items():
  finish=last[connection]
  for gap in gaps:
   if start<=gap['start']<=finish:finish=min(finish,gap['start'])
  intervals.append(dict(connection=connection,start_monotonic_ns=start,end_monotonic_ns=finish))
 clipped=[dict(start_monotonic_ns=g['start'],**({} if g.get('unclosed') else {'resubscribed_monotonic_ns':min(g['end'],end)}),reason=g['reason']) for g in gaps if g['start']<=end]
 return intervals,clipped

def snapshot(capture,out,cutoff_ns=None,max_bytes=50_000_000):
 capture=Path(capture).resolve();out=Path(out).resolve()
 if out==capture or capture in out.parents:raise ValueError('Snapshot must be outside active capture')
 if cutoff_ns is not None and (type(cutoff_ns)is not int or cutoff_ns<=0):raise ValueError('Positive explicit cutoff required')
 out.mkdir(parents=True,exist_ok=False);started=time.time_ns()
 try:
  selection_raw=(capture/'selection.json').read_bytes();selection=json.loads(selection_raw);channels=selection['channels']
  receipt=copy_complete(capture/'receipts.jsonl',out/'receipts.jsonl',cutoff_ns,max_bytes)
  if not receipt['records']:raise ValueError('No complete receipts at cutoff')
  lifecycle=copy_complete(capture/'lifecycle.jsonl',out/'lifecycle.jsonl',cutoff_ns,max_bytes)
  if lifecycle['cap_clipped']:raise ValueError('Lifecycle cap prevents conservative gap reconstruction')
  rows=[json.loads(line) for line in (out/'receipts.jsonl').read_text().splitlines()];events=[json.loads(line) for line in (out/'lifecycle.jsonl').read_text().splitlines()]
  end=receipt['last_complete_receipt_ns'];coverage,gaps=context(rows,events,channels,end)
  if not coverage:raise ValueError('No acknowledged connection')
  if (capture/'selection.json').read_bytes()!=selection_raw:raise ValueError('Selection changed')
  (out/'selection.json').write_bytes(selection_raw)
  for proof in (receipt,lifecycle):
   if sha_prefix(proof['source'],proof['bytes'])!=proof['sha256']:raise ValueError('Source prefix changed before snapshot seal')
  source=Path(__file__).read_bytes();(out/'snapshot-source.py').write_bytes(source)
  summary=dict(schema='public-receipt-prefix-snapshot-v1',status='prefix_snapshot_not_terminal',end_utc_ns=rows[-1]['receipt_utc_ns'],end_monotonic_ns=end,coverage_intervals=coverage,gaps=gaps,files_sha256={'receipts.jsonl':receipt['sha256'],'lifecycle.jsonl':lifecycle['sha256'],'selection.json':hashlib.sha256(selection_raw).hexdigest()},capture_directory=str(capture),receipt_prefix=receipt,lifecycle_prefix=lifecycle,requested_cutoff_ns=cutoff_ns,snapshot_started_utc_ns=started,snapshot_issued_utc_ns=time.time_ns(),source_sha256=hashlib.sha256(source).hexdigest(),qualified=False,scope='Local receipt prefix, not collector terminal or exchange completeness. Open recorded gaps conservatively clipped to last complete receipt. Default live snapshot includes all captured lifecycle events, even late gap notices; explicit historical cutoff filters both streams. Final stream-prefix reconciliation required.')
  with (out/'prefix-summary.json').open('x') as f:json.dump(summary,f,indent=2)
  return summary
 except Exception as exc:
  with (out/'failure.json').open('x') as f:json.dump(dict(status='snapshot_failed',error=repr(exc)),f)
  raise

def reconcile(prefix_summary,final_summary):
 prefix=json.loads(Path(prefix_summary).read_text());final_path=Path(final_summary);final=json.loads(final_path.read_text());root=final_path.parent
 if final.get('schema')!='public-receipt-collector-v2' or final.get('status')=='started':raise ValueError('Collector terminal summary required')
 checks={}
 for name,key in [('receipts.jsonl','receipt_prefix'),('lifecycle.jsonl','lifecycle_prefix')]:
  proof=prefix[key];checks[name]=sha_prefix(root/name,proof['bytes'])==proof['sha256']
 checks['selection.json']=hashlib.sha256((root/'selection.json').read_bytes()).hexdigest()==prefix['files_sha256']['selection.json']
 gaps=[]
 for g in final['gaps']:
  a=g['start_monotonic_ns'];b=g.get('resubscribed_monotonic_ns',final['end_monotonic_ns'])
  if any(a<v['end_monotonic_ns'] and b>v['start_monotonic_ns'] for v in prefix['coverage_intervals']):gaps.append(g)
 return dict(prefix_bytes_match=all(checks.values()),checks=checks,final_gaps_intersecting_provisional_coverage=gaps,requires_rebuild=bool(gaps) or not all(checks.values()),qualified=False,final_summary_sha256=hashlib.sha256(final_path.read_bytes()).hexdigest(),scope='Prefix-only byte reconciliation; does not rehash entire terminal stream or certify feed completeness')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--capture',required=True);p.add_argument('--out',required=True);p.add_argument('--cutoff-ns',type=int);p.add_argument('--max-bytes',type=int,default=50_000_000);a=p.parse_args();snapshot(a.capture,a.out,a.cutoff_ns,a.max_bytes)
