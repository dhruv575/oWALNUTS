"""Terminal-only independent resource pilot review; never launches workers."""
import argparse,hashlib,json,math,sys,zipfile
from pathlib import Path
PIN='14d13a8ae084bfda46a4bbbc241622a8f5491668ed7d5206c4ebcd0dea7bade6'
def load(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main(directory):
 d=Path(directory).resolve();p=load(d/'plan.json');checks={};errors={};inventory={};rows=[]
 def ck(k,v):checks[k]=bool(v)
 def attempt(k,fn):
  try:fn();ck(k,True)
  except Exception as exc:ck(k,False);errors[k]=repr(exc)
 ck('frozen_pin',sha(d/'plan.json')==PIN==(d/'plan.sha256').read_text().strip())
 sys.path.insert(0,p['study'])
 from posterior_resource.controller import verify_frozen,validate_outputs
 from posterior_resource.resource_worker import validate_report
 from asof_rolling_execute import validate_hardware
 attempt('frozen_sources_runtime',lambda:verify_frozen(d/'plan.json',PIN))
 terminal=load(d/'terminal.json');ck('four_recorded',terminal['expected']==terminal['recorded']==4)
 for c in p['cells']:
  cid=c['id'];r=load(d/(cid+'-status.json'));base=Path(c['out']);entry=dict(id=cid,backend=c['backend'],status=r['status'],success=r['success'],seconds=r['elapsed_seconds'])
  ck(cid+':identity',r['id']==cid and r['resource_only'] is True);ck(cid+':cost',math.isfinite(r['elapsed_seconds']) and r['elapsed_seconds']>=0)
  started=d/(cid+'-started.json')
  if started.exists():
   start=load(started);ck(cid+':start_binding',start['plan_sha256']==PIN and start['posterior_sha256']==p['posterior_sha256'] and 0<start['timeout_seconds']<=1800)
   hp=d/(cid+'-hardware.json');h=load(hp);cmd=[p['python'],'-m','posterior_resource.resource_worker','--plan',str(d/'plan.json'),'--cell',cid]
   args=[p['python'],str(Path(p['study'])/'hardware_control.py'),'--cpus','0','--record',str(hp),'--timeout',str(start['timeout_seconds']),'--',*cmd]
   attempt(cid+':hardware',lambda:validate_hardware(h,args,r['returncode'],start['timeout_seconds']))
   ck(cid+':exit_preserved',load(d/(cid+'-exit.json'))['returncode']==r['returncode'])
  rp=base/'resource-result.json'
  if rp.exists():
   result=load(rp);attempt(cid+':resource_outputs',lambda:validate_outputs(p,c,result));entry['resource']=result
   public=c['backend']=='public';fit=base/'fit';underpath=fit/('python-pymc-flow-report.json' if public else 'report.json')
   if underpath.exists():
    under=load(underpath);entry['underlying_sampler']=dict(status=under.get('status'),draws=under.get('draws'),healthy=under.get('healthy'),precision_pass=under.get('precision_pass'),retained_divergences=under.get('retained_divergences'),parity=under.get('parity'),resource_completion_inferred=False)
    ck(cid+':saved_sampler_binding',sha(underpath)==result.get('worker_report_sha256'))
    if public and result['status']=='failed':
     entry['adapter_failure']=result.get('error');entry['sampler_returncode']=result.get('sampler_returncode')
     actual={str(Path(k).resolve()).casefold():v for k,v in under.get('bindings',{}).items()}
     expected={str(Path(k).resolve()).casefold():v for k,v in p['worker_bindings'].items()}
     expected.update({str(Path(k).resolve()).casefold():v for k,v in p['bindings'].items() if Path(k).name in ['__init__.py','_owalnuts.pyd']})
     expected[str(Path(c['fixture']).resolve()).casefold()]=c['fixture_sha256']
     entry['adapter_binding_mismatches']=[dict(path=k,expected=v,actual=actual.get(k)) for k,v in expected.items() if actual.get(k)!=v]
   if result['status']=='resource_completed':
    ck(cid+':success_definition',r['success'] is (r['returncode']==0))
    public=c['backend']=='public';fit=base/'fit';reportpath=fit/('python-pymc-flow-report.json' if public else 'report.json');raw=fit/'draws-8000'/'python-pymc-flow-raw.json' if public else fit/'draws-8000-raw.json';report=load(reportpath)
    attempt(cid+':actual_fixed8k_report',lambda:validate_report(report,c,load(c['fixture']),p,raw))
    ck(cid+':worker_report_binding',sha(reportpath)==result['worker_report_sha256'])
    ck(cid+':streamed_raw_hash',sha(raw)==result['extraction']['raw_sha256'])
    entry['checkpoint_health']={}
    for n in [4000,8000]:
     checkpoint=load(base/f'checkpoint-{n}.json');cdf=load(base/f'predictive-cdf-{n}.json')
     entry['checkpoint_health'][str(n)]=dict(healthy=checkpoint['healthy'],full_gate_pass=checkpoint['screen']['pass'],divergences=checkpoint['retained_divergences'],predictive_cdf=cdf)
   elif r['success']:ck(cid+':failed_never_success',False)
  elif r['success']:ck(cid+':success_report_required',False)
  for f in base.rglob('*') if base.exists() else []:
   if f.is_file() and f.suffix in ['.json','.npy','.npz','.log']:inventory[str(f)]=dict(bytes=f.stat().st_size,sha256=sha(f))
  rows.append(entry)
 ck('totalcost_encloses_cells',terminal['elapsed_seconds']+1e-6>=sum(r['seconds'] for r in rows))
 result=dict(integrity_pass=all(checks.values()),plan_sha256=PIN,checks=checks,errors=errors,rows=rows,total_seconds=terminal['elapsed_seconds'],summed_cell_seconds=sum(r['seconds'] for r in rows),inventory=inventory,qualified=False,reference_bank_resolved=False,limitations=['Four fixed8k fits with dependent4k prefixes: resource feasibility, not calibrated posterior accuracy.','Resource completion, full diagnostic precision, and predictive quadrature convergence are separate outcomes.','All four outcomes and charged failed costs retained; no time-to-first-pass speed ratio.'])
 with (d/'independent-terminal-audit.json').open('x') as f:json.dump(result,f,indent=2)
 copy=d/'independent-terminal-auditor.py'
 with copy.open('xb') as f:f.write(Path(__file__).read_bytes())
 with zipfile.ZipFile(d/'independent-terminal-source.zip','x',zipfile.ZIP_DEFLATED) as z:
  for path in p['worker_bindings']:
   if path.endswith('.py'):z.write(path,'study/'+Path(path).name)
  for path in p['package_inventory']:z.write(path,'posterior_resource/'+str(Path(path).relative_to(Path(p['study'])/'posterior_resource')))
 with (d/'independent-terminal-provenance.json').open('x') as f:json.dump(dict(auditor_sha256=sha(copy),source_zip_sha256=sha(d/'independent-terminal-source.zip'),result_sha256=sha(d/'independent-terminal-audit.json'),plan_sha256=PIN,runtime=p['runtime']),f,indent=2)
 print(json.dumps(dict(integrity_pass=result['integrity_pass'],failed_checks=[k for k,v in checks.items() if not v],outcomes=[dict(id=r['id'],status=r['status'],seconds=r['seconds']) for r in rows])))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('directory');main(a.parse_args().directory)
