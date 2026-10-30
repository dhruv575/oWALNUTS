import json,statistics
from pathlib import Path
root=Path(__file__).resolve().parent
result=json.loads((root/'SUMMARY.json').read_text());assert result['unchanged']
rows=result['rows'];assert len(rows)==64
groups={}
for model in sorted({r['model'] for r in rows}):
    rr=[r for r in rows if r['model']==model]
    groups[model]=g=dict(passes={a:sum(r['passed'] for r in rr if r['arm']==a) for a in ['candidate','diag','dense','auto']},ratios={})
    for arm in ['diag','dense','auto']:
        pairs=[]
        for seed in range(928400001,928400005):
            c=next(r for r in rr if r['arm']=='candidate' and r['seed']==seed)
            b=next(r for r in rr if r['arm']==arm and r['seed']==seed)
            pairs.append(dict(seed=seed,valid=c['passed'] and b['passed'],
                efficiency_ratio=c['efficiency']/b['efficiency'] if 'efficiency' in c and 'efficiency' in b else None,
                call_ratio=c['calls']/b['calls'] if 'calls' in c and 'calls' in b else None))
        valid=all(p['valid'] for p in pairs)
        g['ratios'][arm]=dict(pairs=pairs,all_valid=valid,
            qualified_median=statistics.median(p['efficiency_ratio'] for p in pairs) if valid else None)
    g['continue_gate']=g['passes']['candidate']==4 and all(
        v['all_valid'] and v['qualified_median']>=1.2 for v in g['ratios'].values())
    g['candidate_selections']=[dict(seed=r['seed'],selection=r.get('selection'),error=r.get('error')) for r in rr if r['arm']=='candidate']
    g['candidate_failures']=[dict(seed=r['seed'],rhat=r.get('rhat'),bulk=r.get('bulk'),tail=r.get('tail'),
        divergences=r.get('divergences'),max_z=r.get('max_z'),max_mean_sd=r.get('max_mean_sd'),
        max_sd_error=r.get('max_sd_error'),error=r.get('error')) for r in rr if r['arm']=='candidate' and not r['passed']]
(root/'COMPARISON.json').write_text(json.dumps(groups,indent=2)+'\n');print(json.dumps(groups,indent=2))
