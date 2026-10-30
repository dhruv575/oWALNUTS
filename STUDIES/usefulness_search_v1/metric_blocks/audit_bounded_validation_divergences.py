"""Posthoc selected-state diagnostics; selected states are not divergent proposals."""
import json
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent
r=p/'local_recovery/bounded_gp_validation01'
s=json.loads((r/'SUMMARY.json').read_text())
rows=[]
for row in s['rows']:
    if not row.get('divergences',0):continue
    rep=row['seed']-(948700001+2*row['fold'])
    d=r/f"{row['fold']}-{rep}-{row['transform']}-{row['mode']}"
    a=np.load(d/'DRAWS-STATS.npz');v=np.load(d/'FUNCTIONALS.npz')['values']
    div=a['sample_stats__diverging'].astype(bool)
    assert div.sum()==row['divergences']
    events=[]
    for chain,draw in np.argwhere(div):
        item=dict(chain=int(chain),draw=int(draw),rho_selected=float(v[chain,draw,0]),alpha_selected=float(v[chain,draw,1]))
        for key in ['step_size','n_steps','acceptance_rate','energy_error','maxdepth_reached']:
            name='sample_stats__'+key
            if name in a:
                value=a[name][chain,draw]
                if np.ndim(value)==0:item[key]=float(value) if np.isfinite(value) else str(value)
        events.append(item)
    rows.append(dict(fold=row['fold'],seed=row['seed'],transform=row['transform'],mode=row['mode'],events=events,available_stats=list(a.files),rhat=row['rhat'],bulk=row['bulk'],tail=row['tail']))
out=dict(scope='Posthoc diagnostics of selected states at divergent transitions; not divergent integration proposals or causal attribution.',rows=rows)
(p/'local_recovery/bounded_gp_validation_divergence_audit01').mkdir(exist_ok=False)
dest=p/'local_recovery/bounded_gp_validation_divergence_audit01/SUMMARY.json'
dest.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
print(json.dumps(out))
