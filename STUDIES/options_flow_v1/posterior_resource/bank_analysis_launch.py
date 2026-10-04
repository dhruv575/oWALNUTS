"""Single contained bank-analysis phase; all costs additional to fitting."""
import argparse,json,os,subprocess,sys,time,math
from pathlib import Path
from .bank_analysis import sha,validate_policy

def write(path,value):
 with Path(path).open('x') as f:json.dump(value,f,indent=2,allow_nan=False)

def launch(path):
 path=Path(path).resolve();p=json.loads(path.read_text());validate_policy(p);digest=sha(path);out=Path(p['out'])
 if path.with_suffix('.sha256').read_text().strip()!=digest:raise ValueError('Frozen analysis required')
 for suffix in ['', '-started.json','-hardware.json','-exit.json','-status.json','-launch.json','.log']:
  if Path(str(out)+suffix).exists():raise ValueError('Never retry/overwrite analysis')
 timing_path=path.parent/'materialization-timing.json';timing_digest=sha(timing_path)
 if timing_path.with_suffix('.sha256').read_text().strip()!=timing_digest:raise ValueError('Materialization timing sidecar differs')
 materialization=json.loads(timing_path.read_text())
 if materialization['analysis_plan_sha256']!=digest:raise ValueError('Materialization timing binds another plan')
 prior=materialization['seconds_including_plan_writes']
 if type(prior) not in (int,float) or not math.isfinite(prior) or type(p['materialization_seconds']) not in (int,float) or not math.isfinite(p['materialization_seconds']) or p['materialization_seconds']<0 or prior<p['materialization_seconds']:raise ValueError('Invalid prior analysis cost')
 tick=time.perf_counter();record=dict(status='unresolved',qualified=False,reference_bank_resolved=False,plan_sha256=digest,materialization_timing_sha256=timing_digest);hp=Path(str(out)+'-hardware.json')
 # The declared7200second phase reserves15seconds for controller cleanup.
 timeout=7200-15;script=Path(__file__).parent/'bank_analysis.py'
 args=[p['python'],str(Path(p['study'])/'hardware_control.py'),'--cpus','0','--record',str(hp),'--timeout',str(timeout),'--',p['python'],'-m','posterior_resource.bank_analysis','--plan',str(path)]
 write(str(out)+'-started.json',dict(command=args,plan_sha256=digest))
 try:
  if any(sha(q)!=h for q,h in p['bindings'].items()):raise ValueError('Bound inputs changed')
  timeout=7200-prior-(time.perf_counter()-tick)-15
  if timeout<=0:raise ValueError('Analysis budget exhausted during admission')
  args[args.index('--timeout')+1]=str(timeout)
  write(str(out)+'-launch.json',dict(command=args,remaining_worker_seconds=timeout,plan_sha256=digest))
  with Path(str(out)+'.log').open('x') as log:r=subprocess.run(args,cwd=p['study'],env=dict(os.environ,PYTHONPATH=p['study']),stdout=log,stderr=subprocess.STDOUT)
  record['returncode']=r.returncode;write(str(out)+'-exit.json',dict(returncode=r.returncode,plan_sha256=digest))
  h=json.loads(hp.read_text());sys.path.insert(0,p['study']);from asof_rolling_execute import validate_hardware
  validate_hardware(h,args,r.returncode,timeout)
  if h['status'] not in ['completed','worker-failed','worker-timeout']:raise ValueError('Unknown terminal status')
  if h['status']=='worker-timeout':record['status']='budgeted_timeout'
  else:
   result_path=out/'analysis-result.json';result=json.loads(result_path.read_text())
   if result['qualified'] is not False or type(result['reference_bank_resolved'])is not bool:raise ValueError('Invalid bank interpretation')
   if result['reference_bank_resolved'] and (r.returncode!=0 or result['status']!='numerically_resolved_under_declared_checks'):raise ValueError('Inconsistent bank completion')
   record.update(status=result['status'],reference_bank_resolved=result['reference_bank_resolved'],result_sha256=sha(result_path))
  if sha(timing_path)!=timing_digest or timing_path.with_suffix('.sha256').read_text().strip()!=timing_digest:raise ValueError('Materialization timing changed')
  if sha(path)!=digest or any(sha(q)!=h for q,h in p['bindings'].items()):raise ValueError('Postanalysis source/plan drift')
 except Exception as exc:record.update(status='unresolved',reference_bank_resolved=False,error=f'{type(exc).__name__}: {exc}')
 record['additional_outer_seconds']=time.perf_counter()-tick
 record['materialization_seconds']=prior;record['total_analysis_seconds']=prior+record['additional_outer_seconds']
 if record['total_analysis_seconds']>7200:record.update(status='analysis_total_budget_exceeded',reference_bank_resolved=False)
 write(str(out)+'-status.json',record);return record

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True);a=p.parse_args();launch(a.plan)
