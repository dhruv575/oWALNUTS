import json,hashlib
from pathlib import Path
import numpy as np,arviz as az
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_lengthscale_diagnostic01';r.mkdir(exist_ok=False);refpath=l/'localscaled01/REFERENCES.json';ref=json.loads(refpath.read_text())['gp_pois_regr-gp_pois_regr'];j=ref['names'].index('rho');rows=[];hashes={str(refpath):hashlib.sha256(refpath.read_bytes()).hexdigest()}
for seed in range(946500001,946500009):
    for mode in ['low_rank','walnuts_dense']:
        folder=l/'gp_wal_selected_validation01'/f'{mode}-{seed}';f=folder/'FUNCTIONALS.npz';hashes[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
        with np.load(f) as z:x=z['values'][:,:,j]
        threshold=float(ref['mean'][j]+2*ref['sd'][j]);chains=[]
        for ci,a in enumerate(x):
            high=a>threshold;changes=np.flatnonzero(np.r_[True,high[1:]!=high[:-1],True]);lengths=np.diff(changes);states=high[changes[:-1]];acf=np.corrcoef(a[:-1],a[1:])[0,1]
            chains.append(dict(chain=ci,mean=float(a.mean()),sd=float(a.std(ddof=1)),quantiles=np.quantile(a,[.01,.05,.5,.95,.99]).tolist(),maximum=float(a.max()),upper_threshold=threshold,upper_visits=int(high.sum()),longest_upper_run=int(max(lengths[states],default=0)),longest_nonupper_run=int(max(lengths[~states],default=0)),lag1=float(acf),block_means=[float(v.mean()) for v in np.array_split(a,10)],block_upper_counts=[int(v.sum()) for v in np.array_split(high,10)]))
        ds=az.convert_to_dataset({'rho':x});row=dict(seed=seed,mode=mode,rhat=float(az.rhat(ds).rho),bulk=float(az.ess(ds,method='bulk').rho),tail=float(az.ess(ds,method='tail').rho),chains=chains);rows.append(row)
(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,scope='Posthoc descriptive saved-trace diagnosis; threshold is reference mean+2SD, not a known tail probability; no fresh inference or seed exclusion',rows=rows,inputs=hashes),indent=2)+'\n')
for row in rows:
    print(json.dumps(dict(seed=row['seed'],mode=row['mode'],bulk=row['bulk'],tail=row['tail'],means=[c['mean'] for c in row['chains']],maxima=[c['maximum'] for c in row['chains']],upper=[c['upper_visits'] for c in row['chains']],runs=[c['longest_upper_run'] for c in row['chains']]),allow_nan=False))
