"""Posthoc diagnostics of two completed raw low-rank calibration failures."""
import hashlib,json
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';out=l/'native_repair_mixing_audit01';out.mkdir(exist_ok=False)
rows=[];inputs={}
for accept in [.999,.9999]:
    d=l/'bounded_gp_native_repair01'/f'1-raw-low_rank-{accept}'
    summary=json.loads((d/'SUMMARY.json').read_text());assert not summary['passed']
    supervision=json.loads((d/'SUPERVISION.json').read_text());assert supervision['exit_code']==0 and supervision['group_drained']
    for name in ['SUMMARY.json','SUPERVISION.json','DRAWS-STATS.npz','FUNCTIONALS.npz']:
        f=d/name;inputs[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
    a=np.load(d/'DRAWS-STATS.npz');v=np.load(d/'FUNCTIONALS.npz')['values'];chains=[]
    for chain in range(4):
        item=dict(chain=chain,rho_quantiles=np.quantile(v[chain,:,0],[0,.5,1]).tolist(),alpha_quantiles=np.quantile(v[chain,:,1],[0,.5,1]).tolist(),retained_divergences=int(a['sample_stats__diverging'][chain].sum()),maxdepth_hits=int(a['sample_stats__maxdepth_reached'][chain].sum()),step_size=float(a['sample_stats__step_size'][chain,-1]),steps_quantiles=np.quantile(a['sample_stats__n_steps'][chain],[0,.5,.95,1]).tolist(),first_half_means=v[chain,:4000].mean(0).tolist(),second_half_means=v[chain,4000:].mean(0).tolist())
        chains.append(item)
    rows.append(dict(accept=accept,chains=chains))
result=dict(scope='Posthoc chain diagnostics of completed failures; association, not causal attribution or a changed calibration gate.',inputs=inputs,rows=rows)
(out/'SUMMARY.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps([dict(accept=row['accept'],chains=[{k:v for k,v in c.items() if k not in ['first_half_means','second_half_means']} for c in row['chains']]) for row in rows]))
