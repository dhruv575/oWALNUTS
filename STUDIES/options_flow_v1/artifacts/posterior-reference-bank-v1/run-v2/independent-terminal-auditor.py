"""Terminal-only audit of frozen64fit bank; never launches inference."""
import argparse,hashlib,json,math,sys,zipfile
from pathlib import Path
PIN='0d8b13c4c2defb57fc268cf83e41e4756bab78fb1469a8fcf51dd4b68ae349df'
def load(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main(directory):
 d=Path(directory).resolve();p=load(d/'plan.json');checks={};errors={};rows=[];inventory={}
 def ck(k,v):checks[k]=bool(v)
 def attempt(k,fn):
  try:fn();ck(k,True)
  except Exception as exc:ck(k,False);errors[k]=repr(exc)
 ck('plan_pin',sha(d/'plan.json')==PIN==(d/'plan.sha256').read_text().strip())
 sys.path.insert(0,p['study'])
 from posterior_resource.bank_controller import verify_frozen,verify_analysis_link
 from posterior_resource.controller import validate_outputs
 from posterior_resource.resource_worker import validate_report
 from asof_rolling_execute import validate_hardware
 from precision_tiers import precision_screen
 attempt('frozen_sources_runtime',lambda:verify_frozen(d/'plan.json'))
 attempt('analysis_intent_link',lambda:verify_analysis_link(d/'plan.json',PIN))
 terminal=load(d/'terminal.json');ck('64terminal',terminal['expected']==terminal['recorded']==64 and len(p['cells'])==64)
 for c in p['cells']:
  cid=c['id'];base=Path(c['out']);sp=d/(cid+'-status.json')
  if not sp.exists():ck(cid+':status_present',False);rows.append(dict(id=cid,status='missing',resource_completed=False,both_prefixes_pass=False));continue
  row=dict(id=cid,backend=c['backend'],status='audit_read_failed',seconds=0.,resource_completed=False,both_prefixes_pass=False)
  try:
   r=load(sp);row=dict(id=cid,backend=c['backend'],status=r['status'],seconds=r['elapsed_seconds'],resource_completed=False,both_prefixes_pass=False)
   ck(cid+':identity',r['id']==cid);ck(cid+':cost',type(r['elapsed_seconds']) in (int,float) and math.isfinite(r['elapsed_seconds']) and r['elapsed_seconds']>=0)
   started=d/(cid+'-started.json')
   if started.exists():
    s=load(started);ck(cid+':started_binding',s['id']==cid and s['plan_sha256']==PIN and s['posterior_sha256']==p['posterior_sha256'] and 0<s['timeout_seconds']<=1800)
    hp=d/(cid+'-hardware.json');ep=d/(cid+'-exit.json')
    if hp.exists() and ep.exists():
     h=load(hp);cmd=[p['python'],'-m','posterior_resource.resource_worker','--plan',str(d/'plan.json'),'--cell',cid]
     attempt(cid+':hardware',lambda:validate_hardware(h,['--',*cmd],r['returncode'],s['timeout_seconds']))
     ck(cid+':exit',load(ep)['returncode']==r['returncode'])
     ck(cid+':hardware_status_exit',(h['status']=='completed' and r['returncode']==0) or (h['status']=='worker-failed' and r['returncode'] not in [0,124]) or (h['status']=='worker-timeout' and r['returncode']==124))
     if r['status']=='resource_completed':ck(cid+':completed_hardware',h['status']=='completed' and r['returncode']==0 and r['success'] is True)
     elif r['status']=='budgeted_timeout':ck(cid+':timeout_hardware',h['status']=='worker-timeout' and r['returncode']==124 and r['success'] is False)
     elif r['status']=='failed':ck(cid+':failed_hardware',h['status']=='worker-failed' and r['returncode']!=0 and r['success'] is False)
     elif r['status']=='worker_or_validation_failed':ck(cid+':validation_failure',r['success'] is False and bool(r.get('error')))
     else:ck(cid+':known_attempted_status',False)
    else:ck(cid+':hardware_exit_required',False)
   else:ck(cid+':unattempted_label',r['status'] in ['unattempted_provenance_abort','unattempted_global_budget'] and r['success'] is False)
   rp=base/'resource-result.json'
   if rp.exists():
    result=load(rp);attempt(cid+':resource_schema',lambda:validate_outputs(p,c,result));row['worker_resource_status']=result['status'];row['resources']=result.get('resources')
    if 'resource_result_sha256' in r:ck(cid+':controller_result_hash',sha(rp)==r['resource_result_sha256'])
    row['resource_completed']=r['success'] is True and r['status']=='resource_completed' and result['status']=='resource_completed' and r['returncode']==0
    public=c['backend']=='public';fit=base/'fit';reportpath=fit/('python-pymc-flow-report.json' if public else 'report.json');raw=fit/'draws-8000'/'python-pymc-flow-raw.json' if public else fit/'draws-8000-raw.json'
    if row['resource_completed']:
     ck(cid+':required_report',reportpath.is_file());ck(cid+':required_raw',raw.is_file())
    if reportpath.exists():
     report=load(reportpath);row['underlying_sampler']=dict(status=report.get('status'),draws=report.get('draws'),healthy=report.get('healthy'),precision_pass=report.get('precision_pass'),divergences=report.get('retained_divergences'))
     if row['resource_completed']:
      attempt(cid+':worker_report_contract',lambda:validate_report(report,c,load(c['fixture']),p,raw))
      ck(cid+':sampler_report_hash',sha(reportpath)==result['worker_report_sha256'])
      ck(cid+':raw_extraction_hash',sha(raw)==result['extraction']['raw_sha256'])
    if row['resource_completed']:
     checkpoint_rows=[]
     for n in [4000,8000]:
      v=load(base/f'checkpoint-{n}.json');e=v['evaluation'];ds=[*e['functionals'].values(),*e['canonical_parameter_diagnostics'].values()]
      healthy=v['retained_divergences']==0 and all(all(math.isfinite(x[k]) for k in ['rhat','bulk_ess','tail_ess']) and 0<x['rhat']<=1.01 and min(x['bulk_ess'],x['tail_ess'])>=400 for x in ds)
      ck(cid+f':{n}:scope',e['chain_count']==4 and set(e['canonical_parameter_diagnostics'])=={f'q_{i}' for i in range(1012)} and set(e['functionals'])==set(p['full_gate']['functional_names']) and len(e['forecast']['rows'])==4)
      ck(cid+f':{n}:health',healthy==v['healthy']);screen=precision_screen(v,.02,names=p['full_gate']['functional_names'],require_forecast=True)
      ck(cid+f':{n}:screen',screen==v['screen']);cdf=load(base/f'predictive-cdf-{n}.json')
      checkpoint_rows.append(dict(draws=n,healthy=healthy,full_gate_pass=screen['pass'],divergences=v['retained_divergences'],cdf_status=cdf['status'],numerical_reference_ready=cdf['numerical_reference_ready']))
     row['checkpoints']=checkpoint_rows;row['both_prefixes_pass']=len(checkpoint_rows)==2 and all(v['full_gate_pass'] and v['numerical_reference_ready'] for v in checkpoint_rows) and all(v for k,v in checks.items() if k.startswith(cid+':'))
   elif r['success']:ck(cid+':success_requires_result',False)
   for f in base.rglob('*') if base.exists() else []:
    if f.is_file() and f.suffix in ['.json','.npy','.npz','.log']:inventory[str(f)]=dict(bytes=f.stat().st_size,sha256=sha(f))
   for suffix in ['-status.json','-started.json','-hardware.json','-exit.json','.log']:
    f=d/(cid+suffix)
    if f.exists():inventory[str(f)]=dict(bytes=f.stat().st_size,sha256=sha(f))
  except Exception as exc:
   ck(cid+':artifact_read_or_validation',False);errors[cid+':artifact_read_or_validation']=repr(exc);row['audit_error']=repr(exc);row['both_prefixes_pass']=False
  rows.append(row)
 ck('64outcomes',len(rows)==64);total=sum(r.get('seconds',0) for r in rows);ck('elapsed_encloses_cells',terminal['elapsed_seconds']+1e-6>=total)
 attempt('final_frozen_sources_runtime',lambda:verify_frozen(d/'plan.json'));attempt('final_intent_link',lambda:verify_analysis_link(d/'plan.json',PIN))
 result=dict(integrity_pass=all(checks.values()),plan_sha256=PIN,checks=checks,errors=errors,rows=rows,resource_completed=sum(r['resource_completed'] for r in rows),both_prefixes_pass=sum(r['both_prefixes_pass'] for r in rows),total_seconds=terminal['elapsed_seconds'],summed_cell_seconds=total,inventory=inventory,qualified=False,limitations=['Resource completion and both-prefix diagnostic/numerical admission are distinct.','All64 intended outcomes retained; no survivor-only bank.','Fixed posterior resource evidence, not calibrated posterior accuracy or independent truth.'])
 with (d/'independent-terminal-audit.json').open('x') as f:json.dump(result,f,indent=2)
 copy=d/'independent-terminal-auditor.py'
 with copy.open('xb') as f:f.write(Path(__file__).read_bytes())
 with zipfile.ZipFile(d/'independent-terminal-source.zip','x',zipfile.ZIP_DEFLATED) as z:
  for path in p['worker_bindings']:
   if path.endswith('.py'):z.write(path,'study/'+Path(path).name)
  for path in p['package_inventory']:z.write(path,'posterior_resource/'+str(Path(path).relative_to(Path(p['study'])/'posterior_resource')))
 with (d/'independent-terminal-provenance.json').open('x') as f:json.dump(dict(auditor_sha256=sha(copy),audit_sha256=sha(d/'independent-terminal-audit.json'),source_zip_sha256=sha(d/'independent-terminal-source.zip'),plan_sha256=PIN,runtime=p['runtime']),f,indent=2)
 print(json.dumps(dict(integrity_pass=result['integrity_pass'],failed_checks=[k for k,v in checks.items() if not v],resource_completed=result['resource_completed'],both_prefixes_pass=result['both_prefixes_pass'])))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('directory');main(a.parse_args().directory)
