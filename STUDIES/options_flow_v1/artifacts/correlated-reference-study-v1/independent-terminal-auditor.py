"""Execute only after root releases the correlated campaign timing hold."""
import argparse,hashlib,json,math,sys,zipfile
from pathlib import Path
PIN='7775e4d6e579def8b196e35752f709bbbf26c9173c591855a77e1a390b975ca2'
def load(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main(directory):
 d=Path(directory).resolve();p=load(d/'plan.json');out=d/'run';checks={};errors={};inventory={}
 if not (out/'summary.json').exists():
  found=list(d.glob('*/summary.json'))
  if len(found)!=1:raise ValueError('Supply campaign directory with one terminal run summary')
  out=found[0].parent
 def ck(k,v):checks[k]=bool(v)
 def attempt(k,fn):
  try:fn();ck(k,True)
  except Exception as exc:ck(k,False);errors[k]=repr(exc)
 ck('plan_pin',sha(d/'plan.json')==PIN==(d/'plan.sha256').read_text().strip())
 sys.path.insert(0,p['study']);from correlated_reference_study import read_frozen,validate_outputs
 from asof_rolling_execute import validate_hardware
 from hardware_control import wrapper_command
 attempt('frozen_source_runtime_inventory',lambda:read_frozen(d/'plan.json'))
 s=load(out/'summary.json');rows=s['rows'];ck('full28',s['expected']==28 and len(rows)==28 and [r['id'] for r in rows]==[c['id'] for c in p['cells']]);ck('final_integrity',s['integrity_error'] is None)
 ck('intention',load(out/'expected.json')==dict(plan_sha256=PIN,cells=p['cells']))
 records=[]
 for c,r in zip(p['cells'],rows):
  cid=c['id'];folder=out/cid;ck(cid+':row',load(out/(cid+'.json'))==r);ck(cid+':cost',math.isfinite(r['seconds']) and r['seconds']>=0)
  entry=dict(cell=c,status=r['status'],seconds=r['seconds'],resolved=False,both_covered=False)
  if r['status']!='not_started':
   h=load(folder/'hardware.json');ck(cid+':hardware_hash',sha(folder/'hardware.json')==r.get('hardware_sha256'))
   cmd=[p['python'],str(Path(p['study'])/'correlated_reference_study.py'),'worker','--plan',str(d/'plan.json'),'--out',str(folder),'--index',str(p['cells'].index(c))]
   wrapped=wrapper_command(cmd,[0],folder/'hardware.json',timeout=3600)
   attempt(cid+':hardware',lambda:validate_hardware(h,wrapped,r['returncode'],3600))
   ck(cid+':exit',load(folder/'worker-exit.json')['returncode']==r['returncode'])
   for name in ['worker.log','hardware.json','worker-exit.json','resources.json','cell-resources.json']:
    f=folder/name
    if f.exists():inventory[str(f)]=dict(sha256=sha(f),bytes=f.stat().st_size)
   if r['status']=='failed':
    log=(folder/'worker.log').read_text();entry['failure_path_type_error']="TypeError: unsupported operand type(s) for /: 'str' and 'str'" in log
  if r['status']=='completed':
   attempt(cid+':outputs',lambda:validate_outputs(folder,c,p));b=load(folder/'bank.json');result=load(folder/'result.json')
   truth=result['truth'];covered=all(b['endpoints'][k]['lower']<=t<=b['endpoints'][k]['upper'] for k,t in zip(['lo','hi'],truth))
   ck(cid+':coverage',covered==result['both_endpoints_cover_truth'])
   resolved=b['status']=='numerically_resolved_under_declared_checks';ck(cid+':status',b['status']==result['bank_status'])
   entry.update(resolved=resolved,both_covered=covered,reasons=b['reasons'],bounds=b['endpoints'],wholeworker_resources=load(folder/'resources.json'))
   for name in ['bank.json','result.json','resources.json','prefix-diagnostic.json','hardware.json']:
    f=folder/name;inventory[str(f)]=dict(sha256=sha(f),bytes=f.stat().st_size)
  records.append(entry)
 projection=load(out/'projection.json');sentinels=rows[:4]
 expected=max(r['seconds'] for r in sentinels)*24*4 if all(r['status']=='completed' for r in sentinels) else None
 ck('projection_exact',projection['projected_seconds']==expected)
 admitted=expected is not None and expected<=projection['remaining_seconds']-15
 ck('projection_admission',admitted or all(r['status']=='not_started' for r in rows[4:]))
 from scipy.stats import beta
 def ci(k,n):return [0. if k==0 else float(beta.ppf(.025,k,n-k+1)),1. if k==n else float(beta.ppf(.975,k+1,n-k))]
 groups={}
 for name,rho,shift,n in [('correlated_null',.9,0.,12),('iid_null',0.,0.,4),('shift_01',.9,.1,4),('shift_05',.9,.5,4)]:
  rr=[r for r in records if r['cell']['phase']=='main' and r['cell']['rho']==rho and r['cell']['backend_b_shift']==shift];complete=sum(r['status']=='completed' for r in rr);resolved=sum(r['resolved'] for r in rr);covered=sum(r['both_covered'] for r in rr);miss=sum(r['resolved'] and not r['both_covered'] for r in rr);rule=p['progression'][name]
  progress=None if complete!=n else resolved>=rule.get('minimum_resolved',0) and resolved<=rule.get('maximum_resolved',n) and covered>=rule.get('minimum_both_covered',0) and miss<=rule.get('maximum_resolved_miss',n)
  groups[name]=dict(intended=n,completed=complete,failed=sum(r['status']=='failed' for r in rr),not_started=sum(r['status']=='not_started' for r in rr),resolved=resolved,both_covered=covered,resolved_misses=miss,progression=progress,resolution_binomial_95=ci(resolved,n) if complete==n else None,coverage_binomial_95=ci(covered,n) if complete==n else None)
 result=dict(integrity_pass=all(checks.values()),plan_sha256=PIN,checks=checks,errors=errors,records=records,groups=groups,projection=projection,seconds=s['seconds'],inventory=inventory,qualified=False,limitations=['Analytic Gaussian AR resource experiment, not posterior calibration.','Quantile delta covariance approximate; reported binomial intervals descriptive, unadjusted and undefined if incomplete.','All28 intended outcomes retained; main24 progression excludes only preregistered sentinels.'])
 with (d/'independent-terminal-audit.json').open('x') as f:json.dump(result,f,indent=2)
 copy=d/'independent-terminal-auditor.py'
 with copy.open('xb') as f:f.write(Path(__file__).read_bytes())
 with zipfile.ZipFile(d/'independent-terminal-source.zip','x',zipfile.ZIP_DEFLATED) as z:
  for n in p['source']:z.write(Path(p['study'])/n,n)
 with (d/'independent-terminal-provenance.json').open('x') as f:json.dump(dict(auditor_sha256=sha(copy),source_zip_sha256=sha(d/'independent-terminal-source.zip'),audit_sha256=sha(d/'independent-terminal-audit.json'),plan_sha256=PIN,runtime=p['runtime']),f,indent=2)
 print(json.dumps(dict(integrity_pass=result['integrity_pass'],failed_checks=[k for k,v in checks.items() if not v],groups=groups)))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('directory');main(a.parse_args().directory)
