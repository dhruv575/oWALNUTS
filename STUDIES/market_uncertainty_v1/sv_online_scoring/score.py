"""Identity-bound delayed predictive scoring; never fits or replaces intervals."""
import argparse,hashlib,importlib.util,json,math
from pathlib import Path
STUDY=Path(__file__).resolve().parents[1]
HORIZON=1_800_000_000_000
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
features=load('sv_score_features',STUDY/'receipt_features/features.py')
snapshot=load('sv_score_snapshot',STUDY/'live_snapshot/snapshot.py')
baseline_score=load('sv_score_interval',STUDY/'delayed_scoring/score.py')
def digest(raw):return hashlib.sha256(raw).hexdigest()
def finite(x):return type(x) in (int,float) and math.isfinite(x)
def prefix_reconcile(original,later,root):
 checks={}
 for name,key in [('receipts.jsonl','receipt_prefix'),('lifecycle.jsonl','lifecycle_prefix')]:
  proof=original[key];checks[name]=snapshot.sha_prefix(root/name,proof['bytes'])==proof['sha256']
 checks['selection.json']=digest((root/'selection.json').read_bytes())==original['files_sha256']['selection.json']
 gaps=[g for g in later['gaps'] if any(g['start_monotonic_ns']<v['end_monotonic_ns'] and g.get('resubscribed_monotonic_ns',later['end_monotonic_ns'])>v['start_monotonic_ns'] for v in original['coverage_intervals'])]
 return dict(prefix_bytes_match=all(checks.values()),late_gaps=gaps,requires_rebuild=bool(gaps) or not all(checks.values()),provisional=True)
def numerical_gate(report,fixture):
 data=fixture['data'];t=len(data['y']);p=len(data['x'][0]);k=len(data['w'][0]);names={'mu','sigma','h_terminal','next_observed'}|{f'beta_{i}' for i in range(p)}|{f'gamma_{i}' for i in range(k)}
 if p!=4 or k!=2 or not 20<=t<=256 or data.get('rho')!=.9 or data.get('nu')!=5.:raise ValueError('Live SV target scope differs')
 if report.get('status')!='completed' or report.get('precision_pass') is not True:raise ValueError('Worker did not complete precision gate')
 attempts=report['attempts'];draws=[a['draws'] for a in attempts]
 if not draws or draws!=[1000,2000,4000][:len(draws)]:raise ValueError('First-pass tier prefix differs')
 for i,a in enumerate(attempts):
  ev=a['evaluation'];coords=ev['canonical']['all_parameters'];func=ev['functionals']
  if len(coords)!=2+p+k+t or set(func)!=names:raise ValueError('Health/functional family differs')
  good=a['divergences']==0 and all(all(finite(d[v]) for v in ('rhat','bulk_ess','tail_ess')) and 0<d['rhat']<=1.01 and min(d['bulk_ess'],d['tail_ess'])>=400 for d in coords+list(func.values()))
  for d in func.values():
   lo,hi=d['interval'];mc=d['endpoint_mcse'];good=good and len(mc)==2 and all(finite(v) for v in [lo,hi,*mc]) and hi>lo and min(mc)>=0 and max(mc)/(hi-lo)<=.02
  if good!=(i==len(attempts)-1):raise ValueError('Numerical first-pass gate differs')
 return attempts[-1]['evaluation']['functionals']['next_observed']['interval']

def score(issued_dir,capture,*,expected_issuance_sha256,provisional=False):
 issued_dir=Path(issued_dir);capture=Path(capture);tracked={}
 result=dict(schema='delayed-live-sv-score-v1',qualified=False,provisional=provisional,final_reconciliation_required=provisional,status='invalid_issuance',scored=False,scope='Descriptive single predictive interval; no calibration guarantee or certified issue clock')
 def read(path,expected=None):
  path=Path(path).resolve();raw=path.read_bytes();h=digest(raw)
  if expected is not None and h!=expected:raise ValueError('Bound file differs: '+str(path))
  tracked[str(path)]=h;return raw
 try:
  if not isinstance(expected_issuance_sha256,str) or len(expected_issuance_sha256)!=64:raise ValueError('External immutable issuance SHA required')
  for p in (Path(__file__),Path(features.__file__),Path(snapshot.__file__),Path(baseline_score.__file__)):read(p)
  issuance=json.loads(read(issued_dir/'issuance.json',expected_issuance_sha256));result.update(issuance_sha256=expected_issuance_sha256,issuance_status=issuance.get('status'),origin_receipt_ns=issuance.get('origin_receipt_ns'))
  origin=issuance.get('origin_receipt_ns')
  if issuance.get('schema')!='research-live-sv-issuance-v1' or type(origin)is not int or issuance.get('horizon_end_receipt_ns')!=origin+HORIZON:raise ValueError('Issuance schema/origin/horizon')
  if issuance['status'] not in ('issued','issued_no_forecast','not_issued'):raise ValueError('Unknown issuance status')
  if issuance['status']=='not_issued':result.update(status='not_issued',reason=issuance.get('reason'))
  else:
   issued=issuance.get('issued_monotonic_ns');lag=issuance.get('maximum_lag_seconds')
   if type(issued)is not int or lag!=60 or not origin<=issued<=origin+60_000_000_000:raise ValueError('Late or invalid publication clock')
   pins=issuance.get('source_sha256')
   if not isinstance(pins,dict) or not pins:raise ValueError('Issuance source pins missing')
   for p,h in pins.items():read(p,h)
   prefix_path=issued_dir/'snapshot/prefix-summary.json';prefix=json.loads(read(prefix_path,issuance['snapshot_summary_sha256']))
   if prefix.get('receipt_prefix',{}).get('cap_clipped'):raise ValueError('Issuance prefix clipped')
   for name,h in prefix['files_sha256'].items():
    if name not in ('receipts.jsonl','lifecycle.jsonl','selection.json'):raise ValueError('Unexpected prefix member')
    read(issued_dir/'snapshot'/name,h)
   asof=json.loads(read(issued_dir/'asof-features.json',issuance['asof_features_sha256']))
   if not asof['rows'] or asof['rows'][-1]['features']['origin_receipt_ns']!=origin or asof['rows'][-1]['label'].get('observed') is not False or asof['rows'][-1]['label'].get('log_midpoint_return') is not None:raise ValueError('Wrong origin or future outcome present at issue')
   for row in asof['rows']:
    if row['features']['origin_receipt_ns']>origin or (row['label'].get('observed') and row['label'].get('available_at_receipt_ns',origin+1)>origin):raise ValueError('Future training label at issue')
   if issuance['status']=='issued_no_forecast':result.update(status='no_forecast',reason=issuance.get('reason'))
   else:
    report=json.loads(read(issued_dir/'worker-result.json',issuance['worker_result_sha256']));fixture=json.loads(read(issued_dir/'fixture.json',issuance['fixture_sha256']))
    production_keys=('hardware_sha256','worker_config_sha256')
    if any(k in issuance for k in production_keys):
     if not all(k in issuance for k in production_keys):raise ValueError('Incomplete production evidence')
     hardware=json.loads(read(issued_dir/'hardware.json',issuance['hardware_sha256']));config=json.loads(read(issued_dir/'worker-config.json',issuance['worker_config_sha256']))
     if hardware.get('returncode')!=0 or hardware.get('job_active_processes_after_cleanup')!=0 or hardware.get('realized_cpus')!=[0,1,2,3] or hardware.get('enforced_before_worker_launch') is not True or hardware.get('containment',{}).get('assigned_before_worker_execution') is not True:raise ValueError('Production worker containment failed')
     if config.get('sampler_seed')!=issuance['sampler_seed'] or config.get('predictive_seed')!=issuance['predictive_seed']:raise ValueError('Production configuration identity differs')
     for p,h in config['bindings'].items():read(p,h)
     for p,h in config['runtime_bindings'].items():read(p,h)
     if report.get('runtime_bindings')!=config['runtime_bindings']:raise ValueError('Actual production runtime differs')
    if issuance.get('model')!='sv_both_prior_whitened' or issuance.get('precision_pass') is not True or report.get('arm')!='public' or report.get('seed')!=issuance['sampler_seed'] or report.get('predictive_seed')!=issuance['predictive_seed'] or fixture.get('predictive_seed')!=issuance['predictive_seed']:raise ValueError('Worker/issuance identity differs')
    if report.get('physical_initial_positions')!=fixture.get('starts') or report.get('coordinates')!='prior_whitened':raise ValueError('Physical starts/coordinates differ')
    interval=numerical_gate(report,fixture)
    if interval!=issuance['predictive_interval_90']:raise ValueError('Published interval differs from admitted worker')
    summary_path=capture/('prefix-summary.json' if provisional else 'summary.json');summary=json.loads(read(summary_path))
    if provisional:
     if summary.get('schema')!='public-receipt-prefix-snapshot-v1' or summary.get('status')!='prefix_snapshot_not_terminal' or summary.get('receipt_prefix',{}).get('cap_clipped'):raise ValueError('Valid later immutable prefix required')
    elif summary.get('schema')!='public-receipt-collector-v2' or summary.get('status') in (None,'started'):raise ValueError('Terminal capture required')
    raw=read(capture/'receipts.jsonl',summary['files_sha256']['receipts.jsonl'])
    for name in ('lifecycle.jsonl','selection.json'):read(capture/name,summary['files_sha256'][name])
    reconciliation=prefix_reconcile(prefix,summary,capture) if provisional else snapshot.reconcile(prefix_path,summary_path);result['reconciliation']=reconciliation
    invalid=reconciliation['requires_rebuild'];label=None
    if not invalid:
     rebuilt=features.build([json.loads(line) for line in raw.splitlines()],origins_ns=[origin],**features.collector_context(summary))['rows'][0]
     invalid=rebuilt['features']!=asof['rows'][-1]['features'];label=rebuilt['label']
    if invalid:result.update(status='invalidated_receipt_coverage',interval=interval)
    elif not label['observed']:result.update(status='outcome_unavailable',reason=label['future_quote'].get('reason'),interval=interval)
    else:
     y=label['log_midpoint_return'];value=baseline_score.interval_score(y,interval)
     result.update(status='scored',scored=True,observed_return=y,interval=interval,nominal_coverage=.9,covered=interval[0]<=y<=interval[1],width=interval[1]-interval[0],interval_score=value)
 except Exception as exc:result.update(status='invalid_issuance',scored=False,error=repr(exc));result.pop('interval_score',None);result.pop('covered',None)
 for p,h in tracked.items():
  if not Path(p).is_file() or digest(Path(p).read_bytes())!=h:result.update(status='invalid_provenance',scored=False,error='Scoring source/input changed');result.pop('interval_score',None);result.pop('covered',None)
 result['input_and_source_sha256']=tracked;return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--issued-dir',type=Path,required=True);p.add_argument('--capture',type=Path,required=True);p.add_argument('--issuance-sha256',required=True);p.add_argument('--provisional',action='store_true');p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=score(a.issued_dir,a.capture,expected_issuance_sha256=a.issuance_sha256,provisional=a.provisional)
 with a.output.open('x') as f:json.dump(r,f,indent=2,allow_nan=False)
