"""Independent stdlib allocation audit. Execute only after controller terminal."""
import argparse,json,hashlib,math
from pathlib import Path
PIN='a67f4dda5eb27ef8953ce3078f12963ed5d17b9a2bdda89af0c31997dfbf9c55'
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def exact_binomial(k,n,alpha=.05):
 if n<=0:return None
 def cdf(k,p):return sum(math.comb(n,j)*p**j*(1-p)**(n-j) for j in range(k+1))
 def solve(k,target):
  lo,hi=0.,1.
  for _ in range(80):
   mid=(lo+hi)/2
   if cdf(k,mid)>target:lo=mid
   else:hi=mid
  return (lo+hi)/2
 return [0. if k==0 else solve(k-1,1-alpha/2),1. if k==n else solve(k,alpha/2)]
def audit(plan_path,out):
 p=load(plan_path);out=Path(out);checks={};rows=[];inventory={}
 def ck(k,v):checks[k]=bool(v)
 def read(path):inventory[str(path)]=sha(path);return load(path)
 ck('pinned_plan',sha(plan_path)==PIN and p['frozen'] is True)
 here=Path(plan_path).resolve().parents[2]
 ck('sources',all(sha(here/k)==v for k,v in p['source'].items()))
 ck('vectorized_policy',p['implementation']=='vectorized' and p['wall_seconds']==3600 and 'reference_bank_vectorized.py' in p['source'])
 ck('interpreter_bytes',sha(p['interpreter']['path'])==p['interpreter']['sha256'])
 seed=read(p['seed_audit']['path']);ck('seed_inventory',sha(p['seed_audit']['path'])==p['seed_audit']['sha256'] and seed['reserved_seeds']==p['reserved_seeds'] and all(sha(f)==v for f,v in seed['inventory_files'].items()))
 streams=[s for c in p['cells'] for s in c['fit_seeds']+c['init_seeds']+[c['bootstrap_seed']]];ck('streams',streams==list(range(1950000000,1950011156)) and not set(streams)&set(p['reserved_seeds']))
 expected=read(out/'expected.json');ck('expected148',expected['plan_sha256']==PIN and expected['cells']==p['cells'] and len(p['cells'])==148)
 summary=read(out/'summary.json');ck('summary148',summary['expected']==148 and len(summary['rows'])==148 and summary['integrity_error'] is None)
 for c in p['cells']:
  name=c['id'];r=read(out/(name+'.json'));rows.append(r);ck(name+'_summary_row',r==next(x for x in summary['rows'] if x['id']==name));ck(name+'_plan',r['plan_sha256']==PIN);cellout=out/name
  if r['status']=='not_started':ck(name+'_not_attempted',r['outer_seconds']==0 and not cellout.exists());continue
  marker=read(cellout/'started.json');end=read(cellout/'exit.json');ck(name+'_markers',marker['cell']==c and marker['plan_sha256']==PIN and end['status']==r['status'] and end['outer_seconds']==r['outer_seconds']);ck(name+'_cost',math.isfinite(r['outer_seconds']) and r['outer_seconds']>0)
  hp=cellout/'hardware.json'
  if hp.exists():
   hw=read(hp);exit=read(cellout/'worker-exit.json');ck(name+'_cleanup',hw['job_active_processes_after_cleanup']==0 and hw['containment']['assigned_before_worker_execution'] is True);ck(name+'_exit',exit['returncode']==r['worker_exit_code']==hw['returncode']);ck(name+'_cost_enclosure',r['outer_seconds']>=hw['elapsed_seconds']>0)
  else:ck(name+'_hardware_missing_failure',r['status']=='failed')
  if r['status']!='completed':continue
  result=read(cellout/'result.json');resource=read(cellout/'resources.json');bank=read(cellout/'bank.json');ck(name+'_result_fields',all(r[k]==v for k,v in result.items()) and result['cell']==c and result['qualified'] is False)
  ck(name+'_memory',resource==r['resources'] and resource['peak_committed_bytes'] is not None and 0<resource['peak_committed_bytes']<=p['memory_bytes'])
  ck(name+'_bank_bytes',result['bank_serialized_bytes']==(cellout/'bank.json').stat().st_size);ck(name+'_analytic_truth',all(abs(x-y)<1e-12 for x,y in zip(result['truth'],[-1.6448536269514729,1.6448536269514722])))
  bounds=[bank['endpoints'][n] for n in ['lo','hi']];r['audit_group']=[c['fits_per_backend'],c['lengths'][-1],c['rho'],c['backend_b_shift']];ck(name+'_bounds',bounds==result['bounds'] and result['bank_status']==bank['status'] and result['bank_reasons']==bank['reasons']);ck(name+'_truth_coverage',result['both_endpoints_cover_truth']==all(b['lower']<=t<=b['upper'] for b,t in zip(bounds,result['truth'])))
  ck(name+'_bootstrap_count',len(bank['joint_bootstrap_endpoints'])==30000)
  width=bounds[1]['estimate']-bounds[0]['estimate'];conservative=bounds[1]['lower']-bounds[0]['upper']
  screen=(width>0 and conservative>0 and all(b['half_width']<=p['relative_half_width']*width and max(map(abs,b['backend_difference_interval']))<=p['backend_equivalence_relative_width']*width and max(map(abs,b['paired_length_difference_interval']))<=p['length_equivalence_relative_width']*width for b in bounds))
  ck(name+'_declared_component_screen',screen==(bank['status']=='numerically_resolved_under_declared_checks'))

  cov=result['shared_reference_covariance'];ck(name+'_covariance_finite',len(cov)==2 and all(len(a)==2 and all(math.isfinite(v) for v in a) for a in cov) and cov[0][0]>0 and cov[1][1]>0 and abs(cov[0][1]-cov[1][0])<1e-12)
  ck(name+'_analysis_cost',result['bank_analysis_seconds']>0 and math.isclose(result['analysis_seconds_per_bootstrap_including_setup']*30000,result['bank_analysis_seconds'],rel_tol=1e-12))
 projection=read(out/'projection.json');sentinels=rows[:4];projected=max(r['outer_seconds'] for r in sentinels)*144*4 if all(r['status']=='completed' for r in sentinels) else None;ck('projection',projection['projected_seconds']==projected)
 if projected is None or projected>projection['remaining_seconds']-15:ck('projection_stopped_campaign',all(r['status']=='not_started' and r['reason']=='sentinel_cost_or_failure' for r in rows[4:]))
 counts={s:sum(r['status']==s for r in rows) for s in ['completed','failed','not_started']};ck('counts',sum(counts.values())==148 and all(summary[k]==v for k,v in counts.items()));ck('total_cost',summary['total_seconds']>=sum(r['outer_seconds'] for r in rows) and summary['qualified'] is False)
 groups={}
 for c,r in zip(p['cells'],rows):
  if c['phase']!='campaign':continue
  key=f"F{c['fits_per_backend']}-N{c['lengths'][-1]}-rho{c['rho']}-shift{c['backend_b_shift']}"
  g=groups.setdefault(key,dict(intended=0,completed=0,failed=0,not_started=0,resolved=0,resolved_truth_misses=0,both_endpoints_cover_truth=0,cost_seconds=0.,peak_committed_bytes=None))
  g['intended']+=1;g[r['status']]+=1;g['cost_seconds']+=r['outer_seconds']
  if r['status']=='completed':
   g['resolved']+=r['bank_status']=='numerically_resolved_under_declared_checks';g['resolved_truth_misses']+=r['bank_status']=='numerically_resolved_under_declared_checks' and not r['both_endpoints_cover_truth'];g['both_endpoints_cover_truth']+=r['both_endpoints_cover_truth'];peak=r['resources']['peak_committed_bytes'];g['peak_committed_bytes']=max(g['peak_committed_bytes'] or 0,peak)
 for key,g in groups.items():
  g['resolved_over_intended']=g['resolved']/g['intended'];g['conditional_truth_coverage']=g['both_endpoints_cover_truth']/g['completed'] if g['completed'] else None
  complete=g['completed']==g['intended']==8
  g['resolved_exact95_ci']=exact_binomial(g['resolved'],8) if complete else None
  g['truth_coverage_exact95_ci']=exact_binomial(g['both_endpoints_cover_truth'],8) if complete else None
  null=key.endswith('shift0.0')
  g['exploratory_progression_pass']=(g['resolved']>=6 and g['both_endpoints_cover_truth']>=7 and g['resolved_truth_misses']==0 if null else g['resolved']==0) if complete else None
  g['uncertainty_scope']='Per-configuration unadjusted exact binomial bounds, eight independent analytic trials only; no simultaneous or posterior calibration claim.'

 return dict(integrity_pass=all(checks.values()),qualified=False,checks=checks,counts=counts,allocation_groups=groups,screening_criteria={k:p[k] for k in ['alpha','minimum_tail_count','relative_half_width','backend_equivalence_relative_width','length_equivalence_relative_width']},projection=projection,total_seconds=summary['total_seconds'],sentinels=[{k:r.get(k) for k in ['id','status','outer_seconds','bank_status','bank_reasons','bounds','resources']} for r in sentinels],artifact_sha256=inventory,limitations=['Analytic normal/AR1 controls only; no posterior accuracy or calibrated inference claim.','Finite-fit percentile bootstrap is approximate.','All148 intended cells retained including projection-rejected campaign.','Shared covariance broadcast is bookkeeping, not downstream inference validation.','Budget reserves cleanup inside3600seconds; scheduler/bookkeeping overruns charged.'])
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--plan',required=True);ap.add_argument('--directory',required=True);ap.add_argument('--output',required=True);a=ap.parse_args();r=audit(a.plan,a.directory)
 with Path(a.output).open('x') as f:json.dump(r,f,indent=2,allow_nan=False)
 print(json.dumps({'integrity_pass':r['integrity_pass'],'failed':[k for k,v in r['checks'].items() if not v]}))
