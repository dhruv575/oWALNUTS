"""Bounded chronological scheduler; missed origins are outcomes, never replayed."""
import argparse,hashlib,json,platform,time,shutil
from pathlib import Path
import numpy,scipy
import issue as issuer

def run(capture,out,*,capture_end_ns,max_origins=96,deadline_seconds=172800,minimum_free_bytes=12*1024**3,clock=time.monotonic_ns,utc=time.time_ns,sleep=time.sleep,issue_fn=None):
 capture=Path(capture).resolve();out=Path(out).resolve()
 if out==capture or capture in out.parents:raise ValueError('Scheduler output must be outside capture')
 if type(minimum_free_bytes)is not int or minimum_free_bytes<1:raise ValueError('Positive disk floor required')
 if type(max_origins)is not int or not 1<=max_origins<=96 or not 0<deadline_seconds<=172800 or type(capture_end_ns)is not int:raise ValueError('Invalid scheduler bounds')
 with (capture/'receipts.jsonl').open() as f:first=json.loads(f.readline())['receipt_monotonic_ns']
 if capture_end_ns<=first or capture_end_ns>first+172800_000_000_000:raise ValueError('Capture end exceeds48hour bound')
 origins=list(range(first+issuer.WINDOW,capture_end_ns-issuer.HORIZON+1,issuer.STRIDE))[:max_origins]
 out.mkdir(parents=True,exist_ok=False);started=clock();deadline=min(started+int(deadline_seconds*1e9),capture_end_ns)
 sources=[Path(__file__),Path(issuer.__file__),Path(issuer.snap.__file__),Path(issuer.features.__file__),Path(issuer.baseline.__file__)]
 bindings={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
 plan=dict(schema='receipt-online-schedule-v1',capture=str(capture),origins_ns=origins,capture_end_ns=capture_end_ns,deadline_ns=deadline,max_origins=max_origins,minimum_free_bytes=minimum_free_bytes,budget_scope='Admission deadline and disk floor, not hard resource reservation/preemption',started_monotonic_ns=started,started_utc_ns=utc(),source_sha256=bindings,runtime=dict(python=platform.python_version(),numpy=numpy.__version__,scipy=scipy.__version__),retry_policy='No restart or replacement; missed origins recorded, never backdated')
 (out/'plan.json').write_text(json.dumps(plan,indent=2));outcomes=[];abort=None
 def record(origin,reason):
  folder=out/str(origin);folder.mkdir();r=dict(status='not_issued',reason=reason,origin_receipt_ns=origin,horizon_end_receipt_ns=origin+issuer.HORIZON,recorded_utc_ns=utc(),recorded_monotonic_ns=clock(),qualified=False,source_sha256=bindings)
  (folder/'issuance.json').write_text(json.dumps(r,indent=2));return r
 for origin in origins:
  try:
   if abort:r=record(origin,abort)
   else:
    if any(hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h for p,h in bindings.items()):abort='source_drift';r=record(origin,abort)
    elif (capture/'summary.json').exists():abort='capture_terminated';r=record(origin,abort)
    elif clock()>=deadline:abort='scheduler_budget';r=record(origin,abort)
    elif clock()>origin+10_000_000_000:r=record(origin,'missed_origin')
    else:
     due=origin+3_000_000_000
     while clock()<due and clock()<deadline:sleep(max(0.,min(30.,(min(due,deadline)-clock())/1e9)))
     if (capture/'summary.json').exists():abort='capture_terminated';r=record(origin,abort)
     elif clock()>=deadline:abort='scheduler_budget';r=record(origin,abort)
     elif clock()>origin+10_000_000_000:r=record(origin,'missed_origin')
     elif any(hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h for p,h in bindings.items()):abort='source_drift';r=record(origin,abort)
     else:
      free=shutil.disk_usage(out).free
      if free<minimum_free_bytes:abort='scheduler_storage_floor';r=record(origin,abort)
      else:r=(issue_fn or issuer.issue)(capture,out/str(origin),str(origin))
      r['storage_admission']=dict(observed_free_bytes=free,minimum_free_bytes=minimum_free_bytes,passed=free>=minimum_free_bytes)
      if r.get('reason')=='source_drift':abort='source_drift'
   outcomes.append(dict(origin_receipt_ns=origin,status=r['status'],reason=r.get('reason'),storage_admission=r.get('storage_admission'),path=str(out/str(origin)/'issuance.json')))
  except Exception as exc:
   abort='scheduler_error';folder=out/str(origin);folder.mkdir(exist_ok=True);error=dict(status='not_issued',reason=abort,error=repr(exc),origin_receipt_ns=origin,horizon_end_receipt_ns=origin+issuer.HORIZON,recorded_utc_ns=utc(),qualified=False)
   error_path=folder/('scheduler-error.json' if (folder/'issuance.json').exists() else 'issuance.json')
   with error_path.open('x') as f:json.dump(error,f,indent=2)
   outcomes.append(dict(error,path=str(error_path)))
  with (out/'events.jsonl').open('a') as f:f.write(json.dumps(outcomes[-1])+'\n');f.flush()
 final=dict(status='completed' if abort is None else 'completed_with_unattempted',expected=len(origins),outcomes=outcomes,ended_monotonic_ns=clock(),ended_utc_ns=utc(),qualified=False)
 with (out/'terminal.json').open('x') as f:json.dump(final,f,indent=2)
 return final

def main():
 p=argparse.ArgumentParser();p.add_argument('--capture',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--capture-end-ns',required=True,type=int);p.add_argument('--max-origins',type=int,default=96);p.add_argument('--deadline-seconds',type=float,default=172800);p.add_argument('--minimum-free-bytes',type=int,default=12*1024**3);a=p.parse_args();r=run(a.capture,a.output,capture_end_ns=a.capture_end_ns,max_origins=a.max_origins,deadline_seconds=a.deadline_seconds,minimum_free_bytes=a.minimum_free_bytes);print(json.dumps(r))
if __name__=='__main__':main()
