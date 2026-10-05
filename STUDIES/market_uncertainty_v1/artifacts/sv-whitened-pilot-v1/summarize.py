import json,math,hashlib
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;L=lambda f:json.loads(f.read_text());f=L(p/'fixture.json');pr=f['priors'];mean=np.r_[pr['mu_mean'],pr['log_sigma_mean'],np.zeros(260)];sd=np.r_[pr['mu_sd'],pr['log_sigma_sd'],np.full(2,pr['beta_sd']),np.full(2,pr['gamma_sd']),np.ones(256)]
rows=[];reports={}
for d in (p/'run-v1').glob('pair*'):
 if not d.is_dir():continue
 r=L(d/'report.json');reports[d.name]=r;checks=[]
 for a in r['attempts']:
  n=a['draws'];q=np.load(d/f'draws-{n}.npy',allow_pickle=False);u=np.load(d/f'sampling-u-{n}.npy',allow_pickle=False);assert np.array_equal(q,mean+sd*u)
  e=a['evaluation'];assert e['canonical']['all_finite'] and all(v['all_finite'] for v in e['functionals'].values());checks.append(n)
 rows.append(dict(fit=d.name,selected_draws=r['attempts'][-1]['draws'],passed=r['precision_pass'],physical_transform_exact_tiers=checks,all_stats_finite=True))
agreement=[]
for pair in [0,1]:
 a=reports[f'pair{pair}-public']['attempts'][-1]['evaluation']['functionals'];b=reports[f'pair{pair}-reference']['attempts'][-1]['evaluation']['functionals'];diff=[]
 for name in a:
  for endpoint in [0,1]:
   delta=abs(a[name]['interval'][endpoint]-b[name]['interval'][endpoint]);diff.append(dict(name=name,endpoint=endpoint,difference=delta,width_fraction=delta/(b[name]['interval'][1]-b[name]['interval'][0]),combined_mcse=delta/math.hypot(a[name]['endpoint_mcse'][endpoint],b[name]['endpoint_mcse'][endpoint])))
 agreement.append(dict(pair=pair,rows=diff,max_combined=max(x['combined_mcse'] for x in diff),max_width_fraction=max(x['width_fraction'] for x in diff)))
result=dict(qualified=False,rows=rows,agreement=agreement,scope='Two development pairs; shared predictive random stream, descriptive agreement only',execution=L(p/'run-v1/execution.json'))
(p/'comparison.json').write_text(json.dumps(result,indent=2));print([(x['pair'],x['max_combined'],x['max_width_fraction']) for x in agreement])
