import hashlib,json
from pathlib import Path
import numpy as np
import bridgestan as bs
from native_common import model_files
p=Path(__file__).resolve().parent;l=p/'local_recovery';out=l/'gp_fresh_data01';out.mkdir(exist_ok=False)
so,data,source=model_files('gp_pois_regr-gp_pois_regr');original=json.loads(data.read_text());target=bs.StanModel(str(so),data=data.read_text(),seed=1)
names=target.param_names(include_tp=True,include_gq=False);indices=[names.index(f'f.{j}') for j in range(1,12)];rows=[]
for scenario,(rho,alpha) in enumerate([(3.,1.),(3.,2.),(6.,1.),(6.,2.)]):
    seed=949400001+scenario;rng=np.random.default_rng(seed);latent=rng.normal(size=11);q=np.r_[np.log([rho,alpha]),latent]
    f=np.asarray(target.param_constrain(q,include_tp=True,include_gq=False))[indices];rate=np.exp(f);assert np.isfinite(rate).all()
    counts=rng.poisson(rate);cfg=dict(N=original['N'],x=original['x'],k=counts.tolist());d=out/f'scenario-{scenario}';d.mkdir();(d/'DATA.json').write_text(json.dumps(cfg,indent=2)+'\n')
    truth=dict(seed=seed,rho=rho,alpha=alpha,latent=latent.tolist(),log_intensity=f.tolist(),intensity=rate.tolist(),scope='Generative provenance only; forbidden as posterior reference or inference tuning input.')
    (d/'TRUTH.json').write_text(json.dumps(truth,indent=2)+'\n');rows.append(dict(scenario=scenario,seed=seed,total_counts=int(counts.sum()),zero_counts=int((counts==0).sum()),max_count=int(counts.max()),data_sha256=hashlib.sha256((d/'DATA.json').read_bytes()).hexdigest()))
inputs={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),p/'GP-FRESH-DATA-PROTOCOL.md',so,data,source]}
(out/'SUMMARY.json').write_text(json.dumps(dict(completed=True,rows=rows,inputs=inputs),indent=2)+'\n');print(json.dumps(rows))
