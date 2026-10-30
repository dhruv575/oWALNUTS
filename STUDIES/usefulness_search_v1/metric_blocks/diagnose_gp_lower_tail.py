import json,hashlib
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_lengthscale_diagnostic01';prior=json.loads((r/'SUMMARY.json').read_text());ref=json.loads((l/'localscaled01/REFERENCES.json').read_text())['gp_pois_regr-gp_pois_regr'];j=ref['names'].index('rho');rows=[]
for row in prior['rows']:
    folder=l/'gp_wal_selected_validation01'/f"{row['mode']}-{row['seed']}"
    with np.load(folder/'FUNCTIONALS.npz') as z:x=z['values'][:,:,j]
    with np.load(folder/'DRAWS-STATS.npz') as z:q=z['sample_stats__unconstrained_draw']
    threshold=float(np.quantile(x,.05));chains=[]
    for ci,a in enumerate(x):
        low=a<=threshold;edges=np.flatnonzero(np.r_[True,low[1:]!=low[:-1],True]);runs=[dict(start=int(start),length=int(stop-start),minimum=float(a[start:stop].min()),maximum=float(a[start:stop].max())) for start,stop in zip(edges[:-1],edges[1:]) if low[start]];runs.sort(key=lambda v:v['length'],reverse=True)
        same=np.all(q[ci,1:]==q[ci,:-1],axis=1);e=np.flatnonzero(np.r_[True,same[1:]!=same[:-1],True]);repeat=max([int(stop-start) for start,stop in zip(e[:-1],e[1:]) if same[start]],default=0)
        chains.append(dict(chain=ci,minimum=float(a.min()),pooled_q05=threshold,low_count=int(low.sum()),longest_runs=runs[:3],unchanged_transition_count=int(same.sum()),longest_unchanged_transitions=repeat,block_means=[float(v.mean()) for v in np.array_split(a,10)],block_lower_counts=[int(v.sum()) for v in np.array_split(low,10)]))
    rows.append(dict(seed=row['seed'],mode=row['mode'],chains=chains))
(r/'LOWER-TAIL.json').write_text(json.dumps(dict(completed=True,scope='Posthoc empirical pooled5% tail; not reference quantile or stationary-probability estimate',rows=rows,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2)+'\n')
for row in rows:
    if row['seed']==946500006:print(json.dumps(row))
