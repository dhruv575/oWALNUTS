import json
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parent
s=json.loads((root/'SUMMARY.json').read_text());assert s['unchanged'] and len(s['rows'])==72
rows=s['rows'];groups={};losses=[]
for model in sorted({r['model'] for r in rows}):
    rr=[r for r in rows if r['model']==model]
    g=dict(passes={a:sum(r['passed'] for r in rr if r['arm']==a) for a in ['candidate','dense','auto']},comparisons={})
    for arm in ['dense','auto']:
        pairs=[]
        for seed in range(929100001,929100005):
            c=next(r for r in rr if r['seed']==seed and r['arm']=='candidate')
            b=next(r for r in rr if r['seed']==seed and r['arm']==arm)
            if arm=='auto' and b['passed'] and not c['passed']:losses.append(dict(model=model,seed=seed))
            pairs.append(dict(seed=seed,qualified=c['passed'] and b['passed'],
                efficiency_ratio=c['efficiency']/b['efficiency'] if 'efficiency' in c and 'efficiency' in b else None,
                call_ratio=c['calls']/b['calls'] if 'calls' in c and 'calls' in b else None))
        valid=all(p['qualified'] for p in pairs)
        comp=dict(pairs=pairs,qualified=valid)
        if valid:
            ratio=np.array([p['efficiency_ratio'] for p in pairs]);comp.update(geometric_mean=float(np.exp(np.log(ratio).mean())),worst=float(ratio.min()),best=float(ratio.max()))
        g['comparisons'][arm]=comp
    g['signal']=all(c['qualified'] and c['geometric_mean']>=1.2 for c in g['comparisons'].values())
    g['selections']=[dict(seed=r['seed'],selection=r.get('selection'),error=r.get('error')) for r in rr if r['arm']=='candidate']
    groups[model]=g
result=dict(models=groups,paired_accuracy_losses_vs_auto=losses,
    continuation_gate=not losses and any(g['signal'] for g in groups.values()),
    interpretation='Four-seed broader screen; surviving signal requires larger independent validation and strong baselines.')
(root/'COMPARISON.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
