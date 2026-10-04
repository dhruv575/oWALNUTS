"""Independent stdlib sparse-market v2 postrun audit. Never run during timing."""
import argparse,hashlib,json,math,random
from pathlib import Path
PIN='428ed3b09064883e974b51564ad10a90894c903b4c2862431a47dc508c1ae92c'
NAMES=['beta_bar','tau','mu_h','sigma_h','h_terminal','h_mean']+[p+str(g) for g in range(4) for p in ['alpha_','beta_']]
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def norm(d):return {str(Path(k).resolve()).casefold():v for k,v in d.items()}
def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def require(v,s):
 if not v:raise ValueError(s)
def tail(p,key):
 with Path(p).open('rb') as f:f.seek(max(0,Path(p).stat().st_size-1000000));text=f.read().decode()
 marker=json.dumps(key)+':';i=text.rfind(marker);require(i>=0,'Missing raw '+key)
 return json.JSONDecoder().raw_decode(text[i+len(marker):].lstrip())[0]
def matrix_equal(a,b):return len(a)==len(b) and all(len(x)==len(y) and all(finite(v) and abs(v-w)<=1e-12 for v,w in zip(x,y)) for x,y in zip(a,b))
def reconstructed_starts(rho,seed):
 rng=random.Random(seed);starts=[]
 for _ in range(4):
  q=[m+.25*s*rng.gauss(0.,1.) for m,s in zip([0.,-1.,-1.,-1.5],[.5,.5,1.,.5])];z=[.25*rng.gauss(0.,1.) for _ in range(8)];mu=q[2];sig=math.exp(q[3]);h=[mu+sig*.25*rng.gauss(0.,1.)/math.sqrt(1-rho*rho)]
  for _ in range(95):h.append(mu+rho*(h[-1]-mu)+sig*.25*rng.gauss(0.,1.))
  starts.append(q+z+h)
 return starts

def gate(report,fixture):
 e=report['evaluation'];fs=e['functionals'];qs=e['canonical_parameter_diagnostics'];forecast=e['forecast'];rows=forecast['rows'];future=fixture['holdout']
 require(set(fs)==set(NAMES) and set(qs)=={f'q_{i}' for i in range(108)},'Diagnostic family mismatch')
 require(e['chain_count']==4,'Chain count mismatch')
 health=report.get('retained_divergences')==0 and all(all(finite(d[k]) for k in ['rhat','bulk_ess','tail_ess']) and 0<d['rhat']<=1.01 and d['bulk_ess']>=400 and d['tail_ess']>=400 for d in [*fs.values(),*qs.values()])
 ratios={}
 def endpoint(key,bounds,mcse):
  require(isinstance(bounds,list) and isinstance(mcse,list) and len(bounds)==len(mcse)==2 and all(finite(v) for v in bounds+mcse) and bounds[1]>bounds[0] and min(mcse)>=0,'Invalid interval')
  ratios[key]=max(mcse)/(bounds[1]-bounds[0])
 for name,row in fs.items():endpoint(name,row['interval_90'],row['endpoint_mcse'])
 keys=[(r['horizon'],r['group']) for r in rows];require(len(keys)==192 and set(keys)=={(h,g) for h in range(1,49) for g in range(4)},'Forecast family mismatch')
 ym=future.get('y_available',future.get('observation_mask'));scores=[]
 for row in rows:
  h,g=row['horizon'],row['group'];observed=ym[h-1][g];available=future['x_available'][h-1][g]
  require(row['target_observed'] is observed and row['forecast_available'] is available and row['grid_index']==future['grid_index'][h-1],'Forecast mask/grid mismatch')
  require(row['observed']==(future['y'][h-1][g] if observed else None),'Observed outcome mismatch')
  require(row['width']==row['upper']-row['lower'],'Width mismatch');endpoint(f'forecast{h},{g}',[row['lower'],row['upper']],row['endpoint_mcse'])
  if not observed:require(row['covered'] is None and row['interval_score'] is None,'Missing target scored')
  else:
   y=row['observed'];covered=row['lower']<=y<=row['upper'];score=row['width']+20*max(row['lower']-y,0)+20*max(y-row['upper'],0)
   require(row['covered'] is covered and math.isclose(row['interval_score'],score,rel_tol=1e-12,abs_tol=1e-12),'Observed score mismatch');scores.append(covered)
 require(forecast['scheduled_cells']==192 and forecast['available_forecast_cells']==192 and forecast['observed_target_cells']==forecast['scored_cells']==4,'Forecast denominator mismatch')
 require(forecast.get('operational_forecast_qualified') is False,'Scenario mislabeled operational')
 precision=all(v<=.02 for v in ratios.values())
 return dict(passed=report.get('status')=='completed' and health and precision,health=health,precision=precision,divergences=report['retained_divergences'],max_endpoint_ratio=max(ratios.values()),worst_endpoint=max(ratios,key=ratios.get),ratios=ratios,observed_labels=4,covered_labels=sum(scores))

def audit(directory):
 root=Path(directory);plan=load(root/'plan.json');checks={};results={};inventory={}
 def ck(key,v):checks[key]=bool(v)
 ck('plan',sha(root/'plan.json')==PIN==(root/'plan.sha256').read_text().strip() and plan['frozen'] is True)
 ck('four_intended',plan['expected']==4 and len(plan['cells'])==4 and len({c['id'] for c in plan['cells']})==4)
 for rep in range(2):
  pair=[c for c in plan['cells'] if c['id'].startswith(f'rep{rep}-')]
  ck(f'rep{rep}_paired_scope',len(pair)==2 and {c['arm'] for c in pair}=={'owalnuts_continuation','numpyro_continuation'} and pair[0]['seed']==pair[1]['seed'] and pair[0]['predictive_seed']==pair[1]['predictive_seed']==pair[0]['seed']+130000 and pair[0]['starts']==pair[1]['starts']==plan['starts'])
 ck('sources',all(sha(k)==v for k,v in plan['study_bindings'].items()));ck('bound_runtime_build',all(sha(k)==v for k,v in plan['bound_files'].items()))
 fixture=load(plan['fixture']);original=load(plan['original_fixture']);data=fixture['data'];future=fixture['holdout'];ym=future.get('y_available',future.get('observation_mask'))
 ck('fixture_hashes',sha(plan['fixture'])==plan['fixture_sha256'] and sha(plan['original_fixture'])==plan['original_fixture_sha256'])
 ck('fixed_regular_grid',data['grid_index']==list(range(96)) and future['grid_index'] in [list(range(48)),list(range(96,144))])
 ck('masks',data['observation_mask']==original['data']['observation_mask'] and sum(map(sum,data['observation_mask']))==18 and sum(map(sum,ym))==4 and sum(map(sum,future['x_available']))==192)
 ck('masked_target_preserved',all(data[k][i][g]==original['data'][k][i][g] if data['observation_mask'][i][g] else data[k][i][g]==0. for i in range(96) for g in range(4) for k in ['x','y']) and all(data[k]==original['data'][k] for k in ['rho','nu']))
 of=original['holdout'];oy=of.get('y_available',of.get('observation_mask'))
 ck('future_preserved',future['x_available']==of['x_available'] and ym==oy and future['grid_index']==of['grid_index'] and all(future['x'][i][g]==of['x'][i][g] for i in range(48) for g in range(4)) and all(future['y'][i][g]==of['y'][i][g] for i in range(48) for g in range(4) if ym[i][g]))
 ck('independent_start_formula',matrix_equal(reconstructed_starts(data['rho'],plan['initialization']['seed']),plan['starts']) and matrix_equal(data['initial_positions'],plan['starts']))
 ck('scope',plan['schema']['dimension']==108 and plan['schema']['precision_names']==NAMES and plan['schema']['forecast_cells']==[[h,g] for h in range(1,49) for g in range(4)])
 for cell in plan['cells']:
  name=cell['id'];out=root/name;row=dict(success=False,status='missing',cost=None);results[name]=row;candidate=cell['arm']=='owalnuts_continuation'
  try:
   sp=root/(name+'-status.json');status=load(sp);row.update(status=status['status'],cost=status.get('elapsed_seconds'));ck(name+'_terminal',True)
   if status['status']=='unattempted_provenance_abort':ck(name+'_attempted',False);continue
   hpath=root/(name+'-hardware.json');h=load(hpath)
   ck(name+'_hardware_hash',sha(hpath)==status['hardware_sha256']);ck(name+'_containment',h['job_active_processes_after_cleanup']==0 and h['realized_cpus']==[0] and h['containment']['assigned_before_worker_execution'] is True)
   ck(name+'_cost',finite(row['cost']) and finite(h['elapsed_seconds']) and row['cost']>=h['elapsed_seconds']>0);row['wrapper_seconds']=h['elapsed_seconds']
   ck(name+'_start_exit',load(root/(name+'-started.json'))['plan_sha256']==PIN and load(root/(name+'-exit.json'))['returncode']==status['returncode']==h['returncode'])
   cmd=cell['command'];ck(name+'_command',status['command']==cmd and h['command']==cmd[cmd.index('--')+1:])
   if h['status']=='worker-timeout':
    ck(name+'_timeout',status['returncode']==124 and h['elapsed_seconds']>=900 and not status['success']);row['status']='budgeted_computational_timeout';continue
   rp=out/('python-pymc-flow-report.json' if candidate else 'report.json');report=load(rp);inventory[str(rp)]=sha(rp);ck(name+'_report_hash',sha(rp)==status['report_sha256'])
   if report['status']!='completed':row.update(status='worker_failed',error=report.get('error'));ck(name+'_failed_not_success',not status['success']);continue
   ck(name+'_seed',report['seed']==cell['seed']);settings=report['settings'] if candidate else report['plan']
   ck(name+'_settings',settings['warmup']==1000 and settings['chains']==4)
   if candidate:
    actual=norm(report['bindings']);expected=norm(plan['study_bindings']);expected.update({k:v for k,v in norm(plan['bound_files']).items() if Path(k).name in ['python.exe','__init__.py','_owalnuts.pyd']});expected[str(Path(plan['fixture']).resolve()).casefold()]=plan['fixture_sha256']
    ck(name+'_runtime',all(actual.get(k)==v for k,v in expected.items()));ck(name+'_target',report['model']=='masked-flow' and settings['block_size']==32 and settings['threads']==1 and report['parity']['passed'] is True and bool(report['parity']['cases']))
    ck(name+'_reported_starts',matrix_equal(report['initial_positions'],plan['starts']) and report['predictive_seed']==cell['predictive_seed']);ck(name+'_precision_family',report['precision_plan']['forecast_expected_cells']==plan['schema']['forecast_cells'] and report['precision_plan']['names']==NAMES)
   else:
    ck(name+'_runtime',settings['source']=={Path(k).name:v for k,v in plan['study_bindings'].items()} and settings['fixture_sha256']==plan['fixture_sha256'] and all(settings['runtime'][k]==plan['runtime']['packages'][k] for k in ['numpy','scipy','jax','jaxlib','numpyro','arviz']))
    ck(name+'_target',settings['target_accept']==.9 and settings['batch']==1000 and settings['cpu_affinity']==[0] and settings['predictive_seed']==cell['predictive_seed'])
    ck(name+'_precision_family',settings['forecast_cells']==plan['schema']['forecast_cells'] and settings['parameter_functionals']==NAMES)
   attempts=[]
   for attempt in report['attempts']:
    n=attempt['draws'];fp=out/(f'draws-{n}/fit-report.json' if candidate else f'draws-{n}-report.json');fit=load(fp);inventory[str(fp)]=sha(fp);g=gate(fit,fixture);ck(f'{name}_{n}_gate',g['passed']==attempt['screen']['pass'] and fit['draws']==n);attempts.append(dict(draws=n,**g))
    if candidate:
     raw=out/f'draws-{n}/python-pymc-flow-raw.json';ck(f'{name}_{n}_raw_starts',matrix_equal(tail(raw,'initial_positions'),plan['starts']));ck(f'{name}_{n}_frozen_metric',tail(raw,'adapted_metadata')==report['adapted_metadata'])
   draws=[v['draws'] for v in attempts];final=gate(report,fixture);ck(name+'_firstpass',draws==[1000,2000,4000,8000][:len(draws)] and not any(v['passed'] for v in attempts[:-1]) and (final['passed'] or draws[-1]==8000));ck(name+'_final',final=={k:v for k,v in attempts[-1].items() if k!='draws'} and report['precision_pass']==final['passed'])
   success=final['passed'] and status['returncode']==0 and h['status']=='completed';ck(name+'_outcome',success==status['success']);row.update(success=success,attempts=attempts)
   if candidate:
    inv=load(out/'invocation-timing.json');worker=inv['seconds_including_imports_and_report'];calls=report['warmup_target_calls']
    for attempt in report['attempts']:calls+=attempt['added_target_calls'];ck(f"{name}_{attempt['draws']}_calls",calls==attempt['cumulative_target_calls'])
    ck(name+'_terminal_calls',calls==report['total_target_calls']==report['session_progress_before_close']['target_calls']);ck(name+'_transitions',report['session_progress_before_close']['completed_transitions']==[1000+draws[-1]]*4)
    ck(name+'_sampling_cost',math.isclose(report['total_sampling_seconds'],report['adapt_seconds']+sum(a['sampling_seconds'] for a in report['attempts']),rel_tol=1e-12,abs_tol=1e-7));row['sampling_seconds']=report['total_sampling_seconds']
   else:
    worker=report['end_to_end_seconds'];ck(name+'_raw_starts',matrix_equal(tail(out/'raw.json','initial_positions'),plan['starts']));cp=report['checkpoints']
    ck(name+'_frozen_state',len({v['adaptation_sha256'] for v in cp})==1 and [v['draws_per_chain'] for v in cp]==list(range(1000,draws[-1]+1,1000)))
    ck(name+'_iterations',all(len(v['start_iterations'])==len(v['end_iterations'])==4 and all(b-a==1000 for a,b in zip(v['start_iterations'],v['end_iterations'])) and (i==0 or v['start_iterations']==cp[i-1]['end_iterations']) for i,v in enumerate(cp)))
    ck(name+'_stage_cost',worker>=report['warmup_seconds']+sum(v['seconds'] for v in cp))
   ck(name+'_worker_cost',finite(worker) and h['elapsed_seconds']>=worker>=report['end_to_end_seconds']);row['worker_seconds']=worker
  except (OSError,ValueError,KeyError,TypeError,IndexError) as exc:ck(name+'_complete_audit',False);row.update(success=False,audit_error=str(exc))
 ck('sources_after_audit',all(sha(k)==v for k,v in plan['study_bindings'].items()) and all(sha(k)==v for k,v in plan['bound_files'].items()))
 pairs=[]
 for rep in range(2):
  c=results[f'rep{rep}-owalnuts_continuation'];r=results[f'rep{rep}-numpyro_continuation'];pairs.append(dict(rep=rep,reference_over_candidate=r['cost']/c['cost'] if c['success'] and r['success'] and all(checks.values()) else None))
 return dict(qualified=False,phase='development_computational_only',expected=4,checks=checks,integrity_pass=all(checks.values()),results=results,pairs=pairs,artifact_sha256=inventory,total_driver_seconds=sum(r['cost'] for r in results.values() if finite(r['cost'])),limitations=['Single sparse posterior, two paired sampler seeds; not reliability breadth or calibration.','All192 supplied-future-x scenarios precision-gated; only4 labels scored; no operational forecast or market-value claim.','All failed cells and costs retained; no ratio for unsuccessful pairs.','Gates recomputed from diagnostics; raw canonical starts read in bounded tails; posterior accuracy not independently established.'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--out',required=True);args=p.parse_args();result=audit(args.directory)
 with Path(args.out).open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
