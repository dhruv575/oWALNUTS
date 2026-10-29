import json,sys
from pathlib import Path
import numpy as np
from analyze import ratio_summary

CONFIGS=['walnuts_99','nuts_99','nuts_lowrank99','nuts_drawmass99']
BUDGETS=[3000,6000,12000]


def ladder(rows):
    by={r['draws']:r for r in rows};total=kernel=work=0.;complete=True
    for budget in BUDGETS:
        r=by.get(budget,{})
        total+=r.get('total_seconds',r.get('resource_seconds',0))
        kernel+=r.get('seconds',0);work+=r.get('target_calls',0)
        complete &= 'seconds' in r and 'target_calls' in r
        if r.get('status')=='ok' and r.get('metrics',{}).get('passed'):
            return dict(reached=True,budget=budget,total_seconds=total,sampler_seconds=kernel if complete else None,target_calls=work if complete else None)
    return dict(reached=False,censored=True,total_seconds_spent=total)


def run(root,out):
    root=Path(root);out=Path(out);manifest=json.loads((root/'MANIFEST.json').read_text());final=json.loads((root/'FINAL.json').read_text())
    assert len(manifest['jobs'])==96 and len(final['jobs'])==96 and final['sources_unchanged']
    rows=[]
    for job in final['jobs']:
        index=job['index'];c,r,d=manifest['jobs'][index];path=root/f'{index:03d}-{c}-{r}-{d}'/'result/RESULT.json'
        row=json.loads(path.read_text()) if path.exists() else dict(config=c,rep=r,draws=d,status='resource_failed')
        assert (row['config'],row['rep'],row['draws'])==(c,r,d)
        if job.get('exit_code')!=0 or not job.get('group_drained'):row['status']='resource_failed'
        row['resource_seconds']=job.get('elapsed_seconds',0);rows.append(row)
    methods={}
    for config in CONFIGS:
        subset=[r for r in rows if r['config']==config]
        methods[config]=dict(ladders=[dict(rep=i,**ladder([r for r in subset if r['rep']==i])) for i in range(8)],fixed_budgets={})
        for d in BUDGETS:
            group=[r for r in subset if r['draws']==d and r['status']=='ok']
            methods[config]['fixed_budgets'][str(d)]=dict(planned=8,completed=len(group),passed=sum(r['metrics']['passed'] for r in group),
                median_sampler_seconds=float(np.median([r['seconds'] for r in group])) if group else None,
                median_total_seconds=float(np.median([r['total_seconds'] for r in group])) if group else None,
                median_target_calls=float(np.median([r['target_calls'] for r in group])) if group else None,
                nonfinite_calls=sum(r['nonfinite_calls'] for r in group))
        methods[config]['reached']=sum(r['reached'] for r in methods[config]['ladders'])
    contrasts={}
    for config in CONFIGS[1:]:
        contrasts[config]={}
        for metric in ['total_seconds','sampler_seconds','target_calls']:
            values=[a[metric]/b[metric] for a,b in zip(methods[config]['ladders'],methods['walnuts_99']['ladders']) if a['reached'] and b['reached'] and a.get(metric) is not None and b.get(metric)]
            contrasts[config][metric]=ratio_summary(values,695000000)
    result=dict(planned=96,completed=sum(r['status']=='ok' for r in rows),wall_seconds=final['elapsed_seconds'],methods=methods,nuts_over_walnuts=contrasts,
        scope='Selected-target fresh-seed native-ABI follow-up; all stronger NUTS controls retained; ratios above one favor WALNUTS; not a general benchmark claim')
    out.mkdir(parents=True,exist_ok=False)
    (out/'SUMMARY.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');(out/'ROWS.json').write_text(json.dumps(rows,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(completed=result['completed'],reached={c:v['reached'] for c,v in methods.items()})))


if __name__=='__main__':run(*sys.argv[1:])
