"""Independent saved target benchmark audit; no compiled calls or timing reruns."""
import json,hashlib,math,statistics,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];ROOT=BASE.parents[1];sys.path.insert(0,str(ROOT/'STUDIES/options_flow_v1'))
from asof_rolling_execute import validate_hardware
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 c=read(BASE/'benchmark-config-v3.json');run=BASE/'benchmark-run-v3';summary=read(run/'summary.json');execution=read(run/'benchmark-execution.json');checks=[]
 def check(name,ok):checks.append(dict(name=name,passed=bool(ok)))
 for p,h in c['bindings'].items():check('binding:'+p,sha(p)==h)
 check('exact_frozen_design',c['blocks']==6 and c['calls_per_block']==1500 and c['orders']==['AB','BA'] and c['memory_bytes']==8*1024**3 and c['timeout_seconds']==600)
 check('both_processes_intended',len(execution['records'])==2 and [r['order'] for r in execution['records']]==['AB','BA'])
 profile=read(c['profile']);validation=read(c['validation']);boundary=read(c['boundary']);all_blocks=[];ratios=[];processes={}
 check('normalized_validation',validation['status']=='passed' and validation['normalized_parity']['passed'] is True)
 new_rejects=sum(r['baseline']['finite'] and not r['candidate']['finite'] for r in boundary['rows']);shared_rejects=sum(not r['baseline']['finite'] and not r['candidate']['finite'] for r in boundary['rows'])
 check('boundary_counts',new_rejects==boundary['new_rejections']==0)
 for order,exitrecord in zip(c['orders'],execution['records']):
  r=read(run/f'benchmark-{order}.json');hardware=read(run/f'benchmark-{order}-hardware.json');started=read(run/f'benchmark-{order}-started.json');terminal=read(run/f'benchmark-{order}-exit.json')
  check(order+':identity',r['order']==order and r['status']=='completed' and r['qualified'] is False and r['config_sha256']==sha(BASE/'benchmark-config-v3.json')==exitrecord['config_sha256']==started['config_sha256'])
  check(order+':exit',exitrecord==terminal and exitrecord['returncode']==0 and exitrecord['config_unchanged'] is True and started['command']==exitrecord['command'])
  validate_hardware(hardware,exitrecord['command'],0,600);check(order+':contained',hardware['status']=='completed' and hardware['job_active_processes_after_cleanup']==0)
  check(order+':command',Path(exitrecord['command'][0]).resolve()==Path(c['python']).resolve() and str((BASE/'benchmark_v3.py').resolve()) in exitrecord['command'] and str((BASE/'benchmark-config-v3.json').resolve()) in exitrecord['command'] and exitrecord['command'][exitrecord['command'].index('--order')+1]==order)
  check(order+':cost_enclosure',0<r['elapsed_seconds']<=hardware['elapsed_seconds']<=exitrecord['seconds']<600)
  runtime=r['runtime'];check(order+':runtime_binary',runtime['extension_sha256']==next(h for p,h in c['bindings'].items() if p.endswith('_owalnuts.pyd')) and runtime['adapter_sha256']==next(h for p,h in c['bindings'].items() if p.replace('\\','/').endswith('owalnuts/__init__.py')))
  expected=[(point['id'],name) for point in profile['points'] for name in (['baseline','candidate'] if order=='AB' else ['candidate','baseline'])]
  check(order+':all_saved_parity_points',len(r['checks'])==10 and [(x['id'],x['implementation']) for x in r['checks']]==expected and all(math.isfinite(x[k]) and x[k]>=0 for x in r['checks'] for k in ('value_error','gradient_max_error')))
  pairs=[];sequence=[];baseorder=['baseline','candidate'] if order=='AB' else ['candidate','baseline']
  for block in range(6):
   subset=r['blocks'][2*block:2*block+2];expected_order=baseorder if block%2==0 else baseorder[::-1]
   check(order+f':block{block}',[b['implementation'] for b in subset]==expected_order and all(b['block']==block and b['calls']==1500 and b['seconds']>0 and b['cpu_seconds']>=0 and math.isclose(b['seconds_per_call'],b['seconds']/1500,rel_tol=1e-12) for b in subset))
   d={b['implementation']:b for b in subset};pairs.append(d['baseline']['seconds']/d['candidate']['seconds']);sequence.extend(expected_order)
  check(order+':12blocks',len(r['blocks'])==12)
  stats=dict(median_microseconds={name:statistics.median(b['seconds_per_call'] for b in r['blocks'] if b['implementation']==name)*1e6 for name in ('baseline','candidate')},paired_ratios=pairs,median_paired_ratio=statistics.median(pairs),max_value_error=max(x['value_error'] for x in r['checks']),max_gradient_error=max(x['gradient_max_error'] for x in r['checks']))
  for name,value in stats.items():
   expected_value=summary['processes'][order][name]
   if isinstance(value,dict):ok=all(math.isclose(value[k],expected_value[k],rel_tol=1e-12) for k in value)
   elif isinstance(value,list):ok=all(math.isclose(x,y,rel_tol=1e-12) for x,y in zip(value,expected_value)) and len(value)==len(expected_value)
   else:ok=math.isclose(value,expected_value,rel_tol=1e-12,abs_tol=1e-20)
   check(order+':summary:'+name,ok)
  all_blocks.extend(r['blocks']);ratios.extend(pairs);processes[order]=stats
 pooled={n:statistics.median(b['seconds_per_call'] for b in all_blocks if b['implementation']==n)*1e6 for n in ('baseline','candidate')}
 check('all24blocks36000calls',len(all_blocks)==summary['all_blocks']==24 and sum(b['calls'] for b in all_blocks)==summary['all_target_calls']==36000)
 check('pooled_summary',all(math.isclose(pooled[n],summary['pooled_median_microseconds'][n],rel_tol=1e-12) for n in pooled) and math.isclose(statistics.median(ratios),summary['pooled_median_paired_ratio'],rel_tol=1e-12) and summary['paired_ratio_range']==[min(ratios),max(ratios)])
 check('execution_summary',summary['execution']==execution and sum(r['seconds'] for r in execution['records'])<=execution['total_seconds'])
 evidence=dict(integrity_pass=all(x['passed'] for x in checks),checks=checks,processes=processes,pooled_median_microseconds=pooled,pooled_median_paired_ratio=statistics.median(ratios),ratio_range=[min(ratios),max(ratios)],target_calls=36000,shared_extreme_rejections=shared_rejects,candidate_only_rejections=new_rejects,qualified=False,scope='Target-call microbenchmark at five fixed archived positions, not MCMC/workflow/calibration evidence. Timing aggregates and saved error maxima independently recomputed; value/gradient outputs not rerun. Stress assertions are source-bound; full stress gradients are not stored in benchmark outputs. Shared extreme-domain rejections remain unresolved; disk/compiler cache state uncontrolled.',bindings={str(p):sha(p) for p in [Path(__file__),BASE/'benchmark-config-v3.json',BASE/'benchmark_v3.py',BASE/'launch_benchmark_v3.py',Path(c['validation']),Path(c['boundary']),*run.glob('*.json')]})
 with Path(__file__).with_name('result.json').open('x') as f:json.dump(evidence,f,indent=2,allow_nan=False)
 print(json.dumps(dict(integrity_pass=evidence['integrity_pass'],checks=len(checks),failed=[x for x in checks if not x['passed']],ratio=evidence['pooled_median_paired_ratio'],shared_rejections=shared_rejects)))
if __name__=='__main__':main()
