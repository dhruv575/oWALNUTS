"""Terminal-only saved-draw audit; no inference or sampler execution."""
import argparse,hashlib,json,math,sys,zipfile
from pathlib import Path
PIN='97c058225c6c0f8567000e770e193f857e9f25483be9a3672adf33d377db6a2d'
def load(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main(directory):
 d=Path(directory).resolve();p=load(d/'cohort.json');checks={};errors={};rows=[];inventory={}
 def ck(k,v):checks[k]=bool(v)
 def attempt(k,fn):
  try:fn();ck(k,True)
  except Exception as exc:ck(k,False);errors[k]=repr(exc)
 ck('frozen_pin',sha(d/'cohort.json')==PIN==(d/'cohort.sha256').read_text().strip())
 sys.path.insert(0,str(d/'code'));from recover import verify
 terminal=load(d/'recovery-terminal.json');ck('two_denominator',terminal['expected']==terminal['recorded']==2 and len(terminal['results'])==2)
 for sp in p['specs']:
  spec=load(sp);cid=spec['cell_id'];base=Path(spec['out']);attempt(cid+':immutable_sources_raw_and_originals',lambda:verify(spec));ck(cid+':spec_hash',sha(sp)==p['spec_hashes'][sp]==Path(sp).with_suffix('.sha256').read_text().strip())
  status=load(str(base)+'-status.json');start=load(str(base)+'-started.json');h=load(str(base)+'-hardware.json');sys.path.insert(0,spec['archived_study_directory'])
  from asof_rolling_execute import validate_hardware
  args=start['command'];timeout=float(args[args.index('--timeout')+1]);attempt(cid+':hardware',lambda:validate_hardware(h,args,status['returncode'],timeout))
  ck(cid+':exit',load(str(base)+'-exit.json')['returncode']==status['returncode'])
  ck(cid+':old_failed',load(spec['original_status'])['status']=='failed')
  ck(cid+':cost',math.isfinite(status['additional_outer_seconds']) and status['additional_outer_seconds']>0)
  record=dict(id=cid,status=status['status'],additional_seconds=status['additional_outer_seconds'],checkpoints=[])
  rp=base/'recovery-result.json'
  if rp.exists():
   r=load(rp);ck(cid+':result_hash',sha(rp)==status.get('result_sha256'));ck(cid+':posthoc_only',r['posthoc'] is True and r['resampled'] is False and r['qualified'] is False)
   if r['status']=='posthoc_analysis_completed':
    ck(cid+':fixed_prefixes',[v['draws'] for v in r['checkpoints']]==[4000,8000]);ck(cid+':raw_identity',r['extraction']['raw_sha256']==r['original_raw_sha256']==sha(spec['raw']))
    for name,key in [('canonical.npy','canonical_sha256'),('compact.npz','compact_sha256')]:ck(cid+':'+key,sha(base/'extracted'/name)==r['extraction'][key])
    from precision_tiers import precision_screen
    for row in r['checkpoints']:
     n=row['draws'];cp=base/f'checkpoint-{n}.json';cdf=base/f'predictive-cdf-{n}.json';v=load(cp);q=load(cdf);e=v['evaluation'];diagnostics=[*e['functionals'].values(),*e['canonical_parameter_diagnostics'].values()]
     healthy=v['retained_divergences']==0 and all(all(math.isfinite(x[k]) for k in ['rhat','bulk_ess','tail_ess']) and 0<x['rhat']<=1.01 and min(x['bulk_ess'],x['tail_ess'])>=400 for x in diagnostics)
     ck(cid+f':{n}:scope',e['chain_count']==4 and set(e['canonical_parameter_diagnostics'])=={f'q_{i}' for i in range(1012)} and len(e['functionals'])==14 and len(e['forecast']['rows'])==4)
     ck(cid+f':{n}:healthy',healthy==v['healthy']);screen=precision_screen(v,.02,names=list(e['functionals']),require_forecast=True)
     ck(cid+f':{n}:gate',screen==v['screen'] and screen['pass']==row['full_gate_pass']);ck(cid+f':{n}:binding',sha(cp)==row['checkpoint_sha256'] and sha(cdf)==row['predictive_cdf_sha256'] and q==row['predictive_cdf'])
     record['checkpoints'].append(dict(draws=n,healthy=healthy,full_gate_pass=screen['pass'],cdf_status=q['status'],numerical_reference_ready=q['numerical_reference_ready'],quantiles=q['quantiles']))
   record['resources']=r.get('resources')
  for f in base.rglob('*'):
   if f.is_file():inventory[str(f)]=dict(bytes=f.stat().st_size,sha256=sha(f))
  rows.append(record)
 ck('cohort_cost',terminal['additional_outer_seconds']+1e-6>=sum(r['additional_seconds'] for r in rows))
 out=dict(integrity_pass=all(checks.values()),checks=checks,errors=errors,rows=rows,additional_outer_seconds=terminal['additional_outer_seconds'],inventory=inventory,qualified=False,resampled=False,limitations=['Posthoc recovery of existing draws, not a replacement prospective resource run.','Original two public resource failures and their costs remain unchanged.','Full diagnostic gates and Gaussian-innovation numerical integration do not establish posterior reference accuracy.'])
 with (d/'independent-terminal-audit.json').open('x') as f:json.dump(out,f,indent=2)
 copy=d/'independent-terminal-auditor.py'
 with copy.open('xb') as f:f.write(Path(__file__).read_bytes())
 with zipfile.ZipFile(d/'independent-terminal-recovery-code.zip','x',zipfile.ZIP_DEFLATED) as z:
  for f in (d/'code').glob('*'):
   if f.is_file():z.write(f,f.name)
 with (d/'independent-terminal-provenance.json').open('x') as f:json.dump(dict(auditor_sha256=sha(copy),result_sha256=sha(d/'independent-terminal-audit.json'),code_zip_sha256=sha(d/'independent-terminal-recovery-code.zip'),cohort_sha256=PIN),f,indent=2)
 print(json.dumps(dict(integrity_pass=out['integrity_pass'],failed_checks=[k for k,v in checks.items() if not v],rows=rows)))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('directory');main(a.parse_args().directory)
