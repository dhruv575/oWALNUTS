import json
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parent
data=json.loads((root/'SUMMARY.json').read_text());assert data['unchanged']
rows=data['rows'];assert len(rows)==80
arms=['fixed_diag','empirical','curvature','dense','auto']
passes={arm:sum(r['passed'] for r in rows if r['arm']==arm) for arm in arms}
rng=np.random.default_rng(928699999);indices=rng.integers(0,16,size=(10000,16));comparisons={}
for arm in ['fixed_diag','empirical','dense','auto']:
    pairs=[]
    for seed in range(928600001,928600017):
        c=next(r for r in rows if r['seed']==seed and r['arm']=='curvature')
        b=next(r for r in rows if r['seed']==seed and r['arm']==arm)
        pairs.append(dict(seed=seed,valid=c['passed'] and b['passed'],
            ratio=c['efficiency']/b['efficiency'] if 'efficiency' in c and 'efficiency' in b else None,
            call_ratio=c['calls']/b['calls'] if 'calls' in c and 'calls' in b else None))
    valid=all(p['valid'] for p in pairs);summary=dict(pairs=pairs,qualified=valid)
    if valid:
        logs=np.log([p['ratio'] for p in pairs]);boot=np.exp(logs[indices].mean(1))
        summary.update(geometric_mean=float(np.exp(logs.mean())),ci95=np.quantile(boot,[.025,.975]).tolist(),
            worst=float(np.exp(logs.min())),best=float(np.exp(logs.max())),median=float(np.exp(np.median(logs))))
    comparisons[arm]=summary
gate=passes['curvature']==16 and all(comparisons[a]['qualified'] and comparisons[a]['geometric_mean']>=1.2
    and comparisons[a]['ci95'][0]>1 for a in ['empirical','dense'])
result=dict(passes=passes,comparisons=comparisons,curvature_signal=gate,
    interpretation='Mechanism ablation only; exact direct posterior disqualifies earnings as an MCMC application.')
(root/'COMPARISON.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
