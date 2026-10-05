"""One scheduled, receipt-as-of forecast issuance. Never scores future outcomes."""
import argparse,hashlib,importlib.util,json,time
from pathlib import Path
STUDY=Path(__file__).resolve().parent.parent
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
snap=module('issuance_snapshot',STUDY/'live_snapshot/snapshot.py');features=module('issuance_features',STUDY/'receipt_features/features.py');baseline=module('issuance_baseline',STUDY/'forecast_baseline/forecast.py')
WINDOW=900_000_000_000;HORIZON=1800_000_000_000;STRIDE=HORIZON

def schedule(first,requested):
 origin=first+WINDOW if requested=='first' else int(requested)
 if origin<first+WINDOW or (origin-first-WINDOW)%STRIDE:raise ValueError('Origin not on frozen30minute schedule')
 return origin

def asof_data(receipts,summary,origin):
 rows=[r for r in receipts if r['receipt_monotonic_ns']<=origin]
 if not rows:raise ValueError('No receipts at origin')
 if summary['end_monotonic_ns']<origin:raise ValueError('Snapshot has not reached origin')
 context=features.collector_context(summary);context['observation_end_ns']=origin
 origins=list(range(receipts[0]['receipt_monotonic_ns']+WINDOW,origin+1,STRIDE))
 return features.build(rows,origins_ns=origins,horizon_ns=HORIZON,window_ns=WINDOW,staleness_ns=5_000_000_000,**context)

def issue(capture,out,requested='first',*,maximum_lag_seconds=10.,snapshot_delay_seconds=2.,clock=time.monotonic_ns,utc=time.time_ns,snapshot_fn=None,max_prefix_bytes=536870912):
 if type(max_prefix_bytes)is not int or not 1<=max_prefix_bytes<=536870912:raise ValueError('Invalid bounded prefix bytes')
 if not 0<=snapshot_delay_seconds<maximum_lag_seconds<=10:raise ValueError('Require0<=snapshot delay<maximum lag<=10seconds')
 capture=Path(capture);out=Path(out);out.mkdir(parents=True,exist_ok=False);sources=[Path(__file__),Path(snap.__file__),Path(features.__file__),Path(baseline.__file__)]
 hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources};result=dict(status='not_issued',qualified=False,scope='Actual issue-time record, not historical replay; no future scoring; exact baseline only',source_sha256=hashes,minimum_history=20,maximum_lag_seconds=maximum_lag_seconds,snapshot_delay_seconds=snapshot_delay_seconds)
 try:
  with (capture/'receipts.jsonl').open() as f:first=json.loads(f.readline())['receipt_monotonic_ns']
  origin=schedule(first,requested);now=clock();result.update(origin_receipt_ns=origin,horizon_end_receipt_ns=origin+HORIZON,attempt_utc_ns=utc(),attempt_monotonic_ns=now)
  if now<origin+int(snapshot_delay_seconds*1e9):result['reason']='not_due_after_snapshot_delay'
  elif now>=origin+HORIZON:result['reason']='target_already_matured'
  elif now-origin>int(maximum_lag_seconds*1e9):result['reason']='late_issuance'
  else:
   summary=snapshot_fn(capture,out/'snapshot') if snapshot_fn else snap.snapshot(capture,out/'snapshot',max_bytes=max_prefix_bytes)
   if summary.get('receipt_prefix',{}).get('cap_clipped') is True:raise ValueError('Snapshot prefix byte cap clipped; withhold issuance')
   raw=(out/'snapshot/receipts.jsonl').read_bytes();rows=[json.loads(line) for line in raw.splitlines()]
   if hashlib.sha256(raw).hexdigest()!=summary['files_sha256']['receipts.jsonl']:raise ValueError('Snapshot receipt identity differs')
   dataset=asof_data(rows,summary,origin)
   forecasts=[baseline.forecast(dataset,origin,flow=flow,minimum_history=20) for flow in (False,True)]
   assert dataset['rows'][-1]['label']['observed'] is False
   with (out/'asof-features.json').open('x') as f:json.dump(dataset,f,indent=2,allow_nan=False)
   result.update(forecasts=forecasts,asof_features_sha256=hashlib.sha256((out/'asof-features.json').read_bytes()).hexdigest(),snapshot_summary_sha256=hashlib.sha256((out/'snapshot/prefix-summary.json').read_bytes()).hexdigest(),status='ready_for_publication')
  for p,h in hashes.items():
   if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h:raise ValueError('Issuance source drift')
  if result['status']=='ready_for_publication':
   # Heavy snapshot, fitting, feature serialization and source verification all precede this publication decision.
   issued=clock();result.update(issued_utc_ns=utc(),issued_monotonic_ns=issued,cutoff_lag_seconds=(issued-origin)/1e9)
   if issued-origin>int(maximum_lag_seconds*1e9):result.update(status='not_issued',reason='late_after_computation',forecast_withheld=True);result.pop('forecasts',None)
   else:result['status']='issued_no_forecast' if all(f['status']=='no_forecast' for f in result['forecasts']) else 'issued'
 except Exception as exc:result.update(status='not_issued',reason='source_drift' if str(exc)=='Issuance source drift' else 'error',error=repr(exc));result.pop('forecasts',None)
 result['recorded_utc_ns']=utc()
 with (out/'issuance.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
 return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--capture',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--origin',default='first');a=p.parse_args();r=issue(a.capture,a.output,a.origin);print(json.dumps(r));return 0 if r['status'] in ('issued','issued_no_forecast') else 1
if __name__=='__main__':raise SystemExit(main())
