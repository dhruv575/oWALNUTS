import json,math,hashlib
from pathlib import Path
folder=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text())
entries={
 'gibbs4k':(folder/'experiment-v1/gibbs/result.json',folder/'experiment-v1/gibbs-hardware.json'),
 'numpyro_centered':(folder/'experiment-v1/numpyro/result.json',folder/'experiment-v1/numpyro-hardware.json'),
 'numpyro_associative_nc':(folder/'experiment-v1/numpyro-nc/result.json',folder/'experiment-v1/numpyro-nc-hardware.json'),
 'owalnuts_corrected':(folder/'owalnuts-corrected-v1/result.json',folder/'owalnuts-corrected-hardware.json'),
 'gibbs16k_followup':(folder/'gibbs16k-v1/result.json',folder/'gibbs16k-hardware.json')}
rows={};bindings={}
for name,(p,hp) in entries.items():
 r=read(p);h=read(hp)
 assert h['returncode']==0 and h['job_active_processes_after_cleanup']==0 and h['realized_cpus']==[0]
 rows[name]=dict(draws=r['draws'],health_pass=r['health_pass'],endpoint_precision_pass=r['endpoint_precision_pass'],contained_worker_seconds=h['elapsed_seconds'],worker_end_to_end_seconds=r['end_to_end_seconds'],compile_seconds=r['compile_seconds'],warmup_compile_seconds=r['warmup_compile_seconds'],warmup_sampling_seconds=r['sampling_including_warmup_seconds'],all_canonical=r['all_canonical'],worst_endpoint_mcse_width=max(v['endpoint_mcse_width'] for v in r['functionals'].values()),functionals=r['functionals'])
 for path in (p,hp):bindings[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
pairs={}
for first in ('owalnuts_corrected','gibbs16k_followup','gibbs4k'):
 for second in ('numpyro_centered','numpyro_associative_nc'):
  comparison=[]
  for name,a in rows[first]['functionals'].items():
   b=rows[second]['functionals'][name];width=b['interval'][1]-b['interval'][0]
   for j,p in enumerate((.05,.95)):
    diff=a['interval'][j]-b['interval'][j];se=math.hypot(a['endpoint_mcse'][j],b['endpoint_mcse'][j]);comparison.append(dict(functional=name,probability=p,difference=diff,difference_reference_width=diff/width,difference_root_sum_squared_mcse=diff/se))
  eligible=all(rows[n]['health_pass'] and rows[n]['endpoint_precision_pass'] for n in (first,second))
  pairs[first+'__'+second]=dict(endpoints=comparison,max_abs_endpoint_difference_reference_width=max(abs(v['difference_reference_width']) for v in comparison),max_abs_endpoint_difference_root_sum_squared_mcse=max(abs(v['difference_root_sum_squared_mcse']) for v in comparison),health_and_precision_both_pass=eligible,descriptive_contained_cost_ratio=rows[second]['contained_worker_seconds']/rows[first]['contained_worker_seconds'] if eligible else None)
result=dict(scope='Single synthetic new-model resource prototype; no posterior accuracy equivalence or general sampler qualification. Shared predictive RNG for4k arms means root-sum-square MCSE comparison is descriptive, not an independence-based test.16k followup uses different prediction stream.',rows=rows,pairs=pairs,retained_failure=dict(path=str(folder/'experiment-v1/owalnuts.log'),reason='normalized constant mismatch before any MCMC; corrected explicitfloat64 constants in separate source',contained_seconds=read(folder/'experiment-v1/owalnuts-hardware.json')['elapsed_seconds']),bindings=bindings)
(folder/'comparison.json').write_text(json.dumps(result,indent=2))
print(json.dumps({n:{k:v[k] for k in ('contained_worker_seconds','health_pass','endpoint_precision_pass','worst_endpoint_mcse_width')} for n,v in rows.items()},indent=2))
print(json.dumps({n:{k:v[k] for k in ('max_abs_endpoint_difference_root_sum_squared_mcse','descriptive_contained_cost_ratio')} for n,v in pairs.items()},indent=2))
