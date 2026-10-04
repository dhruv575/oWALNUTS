"""Independent mixed-coordinate development audit; run only after all six cells terminal."""
import argparse,json,hashlib,math,struct
from pathlib import Path
NAMES=['beta_bar','tau','mu_h','sigma_h','h_terminal','h_mean']+[s+str(g) for g in range(4) for s in ['alpha_','beta_']]

def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def normalized(d):return {str(Path(k).resolve()).casefold():v for k,v in d.items()}
def starts(path,key="initial_positions"):
    with Path(path).open('rb') as f:f.seek(max(0,Path(path).stat().st_size-1000000));tail=f.read().decode()
    marker='"'+key+'":';i=tail.rfind(marker)
    if i<0:raise ValueError('Raw initial positions not in bounded tail')
    return json.JSONDecoder().raw_decode(tail[i+len(marker):].lstrip())[0]
def matrix_equal(a,b):return len(a)==len(b) and all(len(x)==len(y) for x,y in zip(a,b)) and all(math.isfinite(x) and abs(x-y)<1e-12 for aa,bb in zip(a,b) for x,y in zip(aa,bb))
def gate(fit,cell):
    e=fit['evaluation'];d=list(e['functionals'].values())+list(e['canonical_parameter_diagnostics'].values())
    health=e['chain_count']==4 and len(e['canonical_parameter_diagnostics'])==cell['dimension'] and fit['retained_divergences']==0 and all(math.isfinite(v[k]) and (0<v[k]<=1.01 if k=='rhat' else v[k]>=400) for v in d for k in ['rhat','bulk_ess','tail_ess'])
    values={k:max(v['endpoint_mcse'])/(v['interval_90'][1]-v['interval_90'][0]) for k,v in e['functionals'].items()}
    values.update({f'forecast{i}':max(v['endpoint_mcse'])/(v['upper']-v['lower']) for i,v in enumerate(e['forecast']['rows'])})
    scope=set(e['functionals'])==set(NAMES) and set(e['canonical_parameter_diagnostics'])=={f'q_{j}' for j in range(cell['dimension'])} and [(r['horizon'],r['group']) for r in e['forecast']['rows']]==[(h,g) for h in range(1,cell['forecast_rows']//4+1) for g in range(4)]
    intervals=[(v['interval_90'],v['endpoint_mcse']) for v in e['functionals'].values()]+[([v['lower'],v['upper']],v['endpoint_mcse']) for v in e['forecast']['rows']]
    precision=all(len(i)==len(m)==2 and all(math.isfinite(v) for v in [*i,*m]) and i[1]>i[0] and min(m)>=0 and max(m)/(i[1]-i[0])<=.02 for i,m in intervals)
    return dict(health=health,precision=precision,scope=scope,passed=fit.get('status')=='completed' and health and precision and scope,ratios=values,divergences=fit['retained_divergences'])
PIN='3df6b35311b9d31ceedb74b29dedecbe41df76bcdd95020a61d53bdafaa84288'
ARMS=['ow_mixed','numpyro_nc','numpyro_mixed']
def sampling_starts(canonical,rho,mixed):
 result=[]
 for q in canonical:
  u=list(q);sigma=math.exp(q[3]);mu=q[2]
  if mixed:
   for j in range(4):u[8+j]=q[0]+math.exp(q[1])*q[8+j]
  u[12]=(q[12]-mu)*math.sqrt(1-rho*rho)/sigma
  for j in range(13,len(q)):u[j]=(q[j]-mu-rho*(q[j-1]-mu))/sigma
  result.append(u)
 return result

def audit(directory):
 root=Path(directory);pp=root/'plan.json';plan=load(pp);checks={};results={};inventory={}
 def ck(k,v):checks[k]=bool(v)
 ck('pinned_plan',sha(pp)==PIN==(root/'plan.sha256').read_text().strip() and plan['frozen'] is True)
 ck('six_intended',plan['expected']==6 and len(plan['cells'])==6 and {c['id'] for c in plan['cells']}=={f'pair{i}-{a}' for i in range(2) for a in ARMS})
 ck('study_sources',all(sha(k)==v for k,v in plan['study_bindings'].items()));ck('bound_build_runtime',all(sha(k)==v for k,v in plan['bound_files'].items()))
 for pair in range(2):
  cells=[c for c in plan['cells'] if c['id'].startswith(f'pair{pair}-')]
  ck(f'pair{pair}_matched_scope',len(cells)==3 and {c['arm'] for c in cells}==set(ARMS) and all(c['seed']==105110001+pair and c['predictive_seed']==c['seed']+130000 and c['fixture_sha256']==cells[0]['fixture_sha256'] and c['starts']==cells[0]['starts'] and c['dimension']==1012 and c['forecast_rows']==4 for c in cells))
 for cell in plan['cells']:
  name=cell['id'];out=root/name;candidate=cell['arm'].startswith('ow_');mixed=cell['coordinates']=='mixed_slopes';row=dict(success=False,status='missing',cost=None);results[name]=row
  try:
   status=load(root/(name+'-status.json'));row.update(status=status['status'],cost=status.get('elapsed_seconds'));ck(name+'_terminal',True)
   if status['status']=='unattempted_provenance_abort':ck(name+'_attempted',False);continue
   hp=root/(name+'-hardware.json');hardware=load(hp)
   ck(name+'_hardware_hash',sha(hp)==status['hardware_sha256']);ck(name+'_containment',hardware['job_active_processes_after_cleanup']==0 and hardware['realized_cpus']==[0] and hardware['containment']['assigned_before_worker_execution'] is True)
   ck(name+'_cost',isinstance(row['cost'],(float,int)) and math.isfinite(row['cost']) and math.isfinite(hardware['elapsed_seconds']) and row['cost']>=hardware['elapsed_seconds']>0);row['wrapper_seconds']=hardware['elapsed_seconds']
   ck(name+'_start_exit',load(root/(name+'-started.json'))['plan_sha256']==PIN and load(root/(name+'-exit.json'))['returncode']==status['returncode']==hardware['returncode'])
   command=cell['command'];ck(name+'_command',status['command']==command and hardware['command']==command[command.index('--')+1:])
   fixture=load(cell['fixture']);ck(name+'_fixture',sha(cell['fixture'])==cell['fixture_sha256'] and matrix_equal(fixture['data']['initial_positions'],cell['starts']))
   if hardware['status']=='worker-timeout':
    ck(name+'_timeout',status['returncode']==124 and hardware['elapsed_seconds']>=1800 and not status['success']);row['status']='budgeted_computational_timeout';row['partial_attempts']=[]
    for n in [1000,2000,4000,8000]:
     fp=out/(f'draws-{n}/fit-report.json' if candidate else f'draws-{n}-report.json')
     if fp.exists():inventory[str(fp)]=sha(fp);row['partial_attempts'].append(dict(draws=n,**gate(load(fp),cell)))
    continue
   rp=out/('python-pymc-flow-report.json' if candidate else 'report.json' if mixed else 'numpyro-continuation-report.json');r=load(rp);inventory[str(rp)]=sha(rp);ck(name+'_report_hash',sha(rp)==status['report_sha256'])
   if r['status']!='completed':row.update(status='worker_failed',error=r.get('error'));ck(name+'_failed_not_success',not status['success']);continue
   if cell['arm']=='numpyro_mixed':ck(name+'_actual_associative',r.get('implementation')=='associative' and r['settings'].get('implementation')=='associative' and r['parity'].get('implementation')=='associative' and '--implementation' in command and command[command.index('--implementation')+1]=='associative')
   settings=r['settings'];ck(name+'_identity',r['seed']==cell['seed'] and r['coordinates']==cell['coordinates'] and settings['chains']==4 and settings['warmup']==1000)
   expected_sampling=sampling_starts(cell['starts'],fixture['data']['rho'],mixed)
   if candidate or mixed:
    expected=normalized(plan['study_bindings']);expected[str(Path(cell['fixture']).resolve()).casefold()]=cell['fixture_sha256'];expected[str(Path(plan['python']).resolve()).casefold()]=sha(plan['python'])
    if candidate:expected.update({k:v for k,v in normalized(plan['bound_files']).items() if Path(k).name in ['__init__.py','_owalnuts.pyd']})
    actual=normalized(r['bindings']);ck(name+'_runtime',all(actual.get(k)==v for k,v in expected.items()))
    ck(name+'_starts',matrix_equal(r['initial_positions'],cell['starts']) and matrix_equal(r['sampling_initial_positions'],expected_sampling));ck(name+'_predictive_seed',r['predictive_seed']==cell['predictive_seed']);ck(name+'_worker_cpu',r['hardware_control']['realized_cpus']==[0])
    ck(name+'_parity',r['parity']['passed'] is True and len(r['parity']['cases'])==3 and all(math.isfinite(v) and v>=0 for case in r['parity']['cases'] for k,v in case.items() if k.endswith('error')))
    if mixed:ck(name+'_normalized_jacobian_x64',r['parity']['jax_enable_x64'] is True and r['parity']['normalized_canonical_jacobian_value_and_gradient'] is True)
    ck(name+'_precision_names',r['precision_plan']['names']==NAMES and r['precision_plan']['forecast_rows']==4)
    if candidate:ck(name+'_block',r['model']=='flow' and settings['block_size']==32 and settings['threads']==1)
    else:ck(name+'_reference_settings',settings['target_accept']==.9 and settings['batch']==1000 and settings['tiers']==[1000,2000,4000,8000])
   else:
    ck(name+'_runtime',r['source_sha256']=={Path(k).name:v for k,v in plan['study_bindings'].items()} and r['fixture_sha256']==cell['fixture_sha256']);ck(name+'_reference_acceptance',settings['target_accept']==.9)
   attempts=[];calls=r['warmup_target_calls'] if candidate else None
   for i,a in enumerate(r['attempts']):
    n=a['draws'];fp=out/(f'draws-{n}/fit-report.json' if candidate else f'draws-{n}-report.json');fit=load(fp);inventory[str(fp)]=sha(fp);g=gate(fit,cell);attempts.append(dict(draws=n,**g))
    ck(f'{name}_{n}_gate',g['passed']==a['screen']['pass'] and set(a['screen']['parameter_functionals'])==set(NAMES) and a['screen']['forecast_rows']==4 and a['screen']['threshold']==.02)
    ck(f'{name}_{n}_outcomes',all(v['observed']==fixture['holdout']['y'][v['horizon']-1][v['group']] for v in fit['evaluation']['forecast']['rows']))
    if candidate or mixed:
     raw=out/f'draws-{n}/python-pymc-flow-raw.json' if candidate else out/f'draws-{n}-raw.json'
     ck(f'{name}_{n}_raw_starts',matrix_equal(starts(raw),cell['starts']) and matrix_equal(starts(raw,'sampling_initial_positions'),expected_sampling))
    if candidate:
     ck(f'{name}_{n}_frozen_metric',starts(raw,'adapted_metadata')==r['adapted_metadata']);calls+=a['added_target_calls'];ck(f'{name}_{n}_callback',calls==a['cumulative_target_calls']);ck(f'{name}_{n}_increments',a['added_draws']==n-(r['attempts'][i-1]['draws'] if i else 0))
   draws=[a['draws'] for a in attempts];final=gate(r,cell)
   ck(name+'_firstpass',draws==[1000,2000,4000,8000][:len(draws)] and not any(a['passed'] for a in attempts[:-1]) and (final['passed'] or draws[-1]==8000));ck(name+'_final_gate',final=={k:v for k,v in attempts[-1].items() if k!='draws'} and r['precision_pass']==final['passed'])
   success=final['passed'] and status['returncode']==0 and hardware['status']=='completed';ck(name+'_status_outcome',success==status['success']);row.update(success=success,attempts=attempts)
   inv=load(out/'invocation-timing.json');worker=next(v for k,v in inv.items() if k.startswith('seconds_'));ck(name+'_worker_cost',hardware['elapsed_seconds']>=worker>=r['end_to_end_seconds']>0);row['worker_seconds']=worker
   if candidate:
    ck(name+'_terminal_callbacks',calls==r['total_target_calls']==r['session_progress_before_close']['target_calls'] and 0<=r['initialization_target_calls']<=r['warmup_target_calls']);ck(name+'_transitions',r['session_progress_before_close']['completed_transitions']==[1000+draws[-1]]*4)
   else:
    if not mixed:
     raw=out/'numpyro-continuation-raw.json';ck(name+'_raw_starts',matrix_equal(starts(raw),cell['starts']) and matrix_equal(starts(raw,'sampling_initial_positions'),expected_sampling))
    cp=r['checkpoints'];ck(name+'_frozen_reference',len({c['adaptation_sha256'] for c in cp})==1 and [c['draws_per_chain'] for c in cp]==list(range(1000,draws[-1]+1,1000)))
    ck(name+'_reference_iterations',all(len(c['start_iterations'])==len(c['end_iterations'])==4 and all(b-a==1000 for a,b in zip(c['start_iterations'],c['end_iterations'])) and (i==0 or c['start_iterations']==cp[i-1]['end_iterations']) for i,c in enumerate(cp)))
    if not mixed:ck(name+'_sampling_cost',worker>=r['warmup_seconds']+sum(c['seconds'] for c in cp))
   if candidate or mixed:
    ck(name+'_sampling_cost',math.isclose(r['total_sampling_seconds'],r['adapt_seconds']+sum(a['sampling_seconds'] for a in r['attempts']),rel_tol=1e-12,abs_tol=1e-7) and worker>=r['total_sampling_seconds']+r['parity_seconds']);row['sampling_seconds']=r['total_sampling_seconds'];row['parity_seconds']=r['parity_seconds']
  except (KeyError,TypeError,ValueError,OSError,IndexError,StopIteration) as exc:ck(name+'_audit_complete',False);row.update(success=False,audit_error=f'{type(exc).__name__}: {exc}')
 ck('sources_after_audit',all(sha(k)==v for k,v in plan['study_bindings'].items()) and all(sha(k)==v for k,v in plan['bound_files'].items()))
 pairs=[]
 for pair in range(2):
  for a,b in [('ow_mixed','numpyro_mixed'),('numpyro_nc','numpyro_mixed'),('ow_mixed','numpyro_nc')]:
   x=results[f'pair{pair}-{a}'];y=results[f'pair{pair}-{b}'];pairs.append(dict(pair=pair,a=a,b=b,b_over_a=y['cost']/x['cost'] if x['success'] and y['success'] and all(checks.values()) else None))
 return dict(phase='development',qualified=False,expected=6,integrity_pass=all(checks.values()),checks=checks,results=results,pairs=pairs,artifact_sha256=inventory,total_driver_seconds=sum(v['cost'] for v in results.values() if isinstance(v['cost'],(float,int)) and math.isfinite(v['cost'])),limitations=['One fixed T1000 development posterior and two fresh sampler seeds; not fresh datasets, reliability breadth or calibration.','Both NumPyro AR graphs are associative; hierarchy coordinates differ. Complete backend workflows still have different implementations and overhead.','Forward/reverse order leaves NC in middle twice; no order-neutrality claim.','All6 failed/missing outcomes retained; ratios only for matched successful pairs.','Normalized parity and diagnostics do not replace independent endpoint accuracy.','Canonical and sampling starts read in bounded raw tails; posterior arrays not reestimated.'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--out',required=True);a=p.parse_args();r=audit(a.directory)
 with Path(a.out).open('x') as f:json.dump(r,f,indent=2,allow_nan=False)
