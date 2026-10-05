import json,hashlib,math
from pathlib import Path
import numpy as np
p=Path('target/sv-historical-pilot-v1');L=lambda x:json.loads(x.read_text());c=L(p/'prepared/config-frozen.json');e=L(p/'run-v1/execution.json');checks=[]
for name,h in {**c['bindings'],**c['runtime_bindings']}.items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h,name
rows=[];raw=[];reports={}
for cell in e['records']:
 d=p/'run-v1'/cell['id'];r=L(d/'report.json');reports[cell['id']]=r;hw=L(p/'run-v1'/(cell['id']+'-hardware.json'));assert hw['returncode']==cell['returncode']==0 and hw['job_active_processes_after_cleanup']==0 and hw['realized_cpus']==[0,1,2,3] and hw['containment']['assigned_before_worker_execution'];assert r['status']=='completed' and r['precision_pass']
 if cell['arm']=='public':assert r['runtime_bindings']==c['runtime_bindings'] and r['jax_initialized'] is False
 else:
  runtime=r['reference_runtime_bindings'];assert len(runtime)==3 and all(c['bindings'].get(f)==h and hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in runtime.items());checks.append(dict(id=cell['id'],runtime_keys=[k for k in r if 'runtime' in k]))
 fixture=L(Path(cell['fixture']));pr=fixture['priors'];P=len(fixture['data']['x'][0]);K=len(fixture['data']['w'][0]);T=len(fixture['data']['y']);mean=np.r_[pr['mu_mean'],pr['log_sigma_mean'],np.zeros(P+K+T)];sd=np.r_[pr['mu_sd'],pr['log_sigma_sd'],np.full(P,pr['beta_sd']),np.full(K,pr['gamma_sd']),np.ones(T)]
 for a in r['attempts']:
  ev=a['evaluation'];assert ev['canonical']['all_finite'] and all(v['all_finite'] for v in ev['functionals'].values());n=a['draws'];q=np.load(d/f'draws-{n}.npy',allow_pickle=False);u=np.load(d/f'sampling-u-{n}.npy',allow_pickle=False);assert np.array_equal(q,mean+sd*u)
 a=r['attempts'][-1];ph=dict(admission=r['admission_seconds'],adapt=r['adapt_seconds'],sampling=sum(x['sampling_seconds'] for x in r['attempts']),evaluation=sum(x['evaluation_seconds'] for x in r['attempts']),serialization=sum(x['serialization_seconds'] for x in r['attempts']));ph['unallocated_outer']=cell['outer_seconds']-sum(ph.values())
 rows.append(dict(id=cell['id'],arm=cell['arm'],selected_draws=a['draws'],outer_seconds=cell['outer_seconds'],phases=ph,canonical=a['evaluation']['canonical'],max_endpoint_ratio=max(v['ratio'] for v in a['evaluation']['functionals'].values()),predictive=a['evaluation']['functionals']['next_observed'],divergences=a['divergences']))
 for f in d.glob('*.npy'):
  with f.open('rb') as z:h=hashlib.file_digest(z,'sha256').hexdigest()
  raw.append(dict(path=str(f.resolve()),sha256=h,bytes=f.stat().st_size))
agreement=[]
for arm in ['neither','mean','scale','both']:
 a=reports[arm+'-public']['attempts'][-1]['evaluation']['functionals'];b=reports[arm+'-reference']['attempts'][-1]['evaluation']['functionals'];diff=[]
 for key in a:
  for i in [0,1]:
   delta=abs(a[key]['interval'][i]-b[key]['interval'][i]);diff.append(dict(name=key,endpoint=i,width_fraction=delta/(b[key]['interval'][1]-b[key]['interval'][0]),combined_mcse=delta/math.hypot(a[key]['endpoint_mcse'][i],b[key]['endpoint_mcse'][i])))
 agreement.append(dict(ablation=arm,rows=diff,max_combined_mcse=max(x['combined_mcse'] for x in diff),max_reference_width_fraction=max(x['width_fraction'] for x in diff)))
result=dict(qualified=False,integrity_pass=True,intended=8,passed=8,rows=rows,agreement=agreement,campaign_outer_seconds=e['outer_seconds'],arm_total_seconds={arm:sum(x['outer_seconds'] for x in rows if x['arm']==arm) for arm in ['public','reference']},runtime_inspection=checks,scope='One fixed September15 validation origin; posterior computation and agreement only, not market-quality or ablation-selection evidence')
(p/'summary.json').write_text(json.dumps(result,indent=2));(p/'raw-manifest.json').write_text(json.dumps(raw,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ['rows','agreement']},indent=2));print([(a['ablation'],a['max_combined_mcse']) for a in agreement])
