import json,hashlib,math
from pathlib import Path
p=Path(__file__).resolve().parent;L=lambda f:json.loads(f.read_text());c=L(p/'prepared/config-frozen.json');e=L(p/'run-v1/execution.json')
for f,h in c['bindings'].items():assert hashlib.sha256(Path(f).read_bytes()).hexdigest()==h,f
rows=[];raw=[]
for cell in e['records']:
 d=p/'run-v1'/cell['id'];r=L(d/'report.json');hw=L(p/'run-v1'/(cell['id']+'-hardware.json'));assert hw['job_active_processes_after_cleanup']==0 and hw['realized_cpus']==[0,1,2,3];assert r['precision_pass'] and r['status']=='completed';a=r['attempts'][-1]
 for attempt in r['attempts']:
  ev=attempt['evaluation'];assert all(all(math.isfinite(v[k]) for k in ['rhat','bulk_ess','tail_ess']) for v in ev['canonical']['all_parameters']);assert all(all(math.isfinite(v[k]) for k in ['rhat','bulk_ess','tail_ess','ratio']) for v in ev['functionals'].values())
 phases=dict(admission=r['admission_seconds'],adapt=r['adapt_seconds'],sampling=sum(x['sampling_seconds'] for x in r['attempts']),evaluation=sum(x['evaluation_seconds'] for x in r['attempts']),serialization=sum(x['serialization_seconds'] for x in r['attempts']));phases['unallocated_outer']=cell['outer_seconds']-sum(phases.values())
 rows.append(dict(id=cell['id'],arm=cell['arm'],selected_draws=a['draws'],outer_seconds=cell['outer_seconds'],phases=phases,max_endpoint_ratio=max(v['ratio'] for v in a['evaluation']['functionals'].values()),public_jax_initialized=r.get('jax_initialized'),retained_divergences=a['divergences']))
 for f in d.glob('*.npy'):
  with f.open('rb') as stream:h=hashlib.file_digest(stream,'sha256').hexdigest()
  raw.append(dict(path=str(f.resolve()),sha256=h,bytes=f.stat().st_size))
pairs=[]
for i in range(6):
 a=next(x for x in rows if x['id']==f'fixture{i}-public');b=next(x for x in rows if x['id']==f'fixture{i}-reference');pairs.append(dict(fixture=i,public_seconds=a['outer_seconds'],reference_seconds=b['outer_seconds'],reference_over_public=b['outer_seconds']/a['outer_seconds'],public_draws=a['selected_draws'],reference_draws=b['selected_draws']))
result=dict(qualified=False,integrity_pass=True,intended=12,usable=dict(public=6,reference=6),rows=rows,pairs=pairs,total_outer_seconds=e['outer_seconds'],arm_total_seconds={arm:sum(x['outer_seconds'] for x in rows if x['arm']==arm) for arm in ['public','reference']},scope='Six fresh prior-generated development fixtures, not coverage or speed qualification; full costs and all attempts retained')
(p/'summary.json').write_text(json.dumps(result,indent=2));(p/'raw-manifest.json').write_text(json.dumps(raw,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
