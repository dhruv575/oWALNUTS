import json,sys
from pathlib import Path
import numpy as np
from targets import CASES
from worker import CONFIGS,BUDGETS

def rows(root):
    root=Path(root);manifest=json.loads((root/'MANIFEST.json').read_text());final=json.loads((root/'FINAL.json').read_text())
    assert len(final['jobs'])==len(manifest['jobs']) and final['sources_unchanged']
    result=[]
    for job in final['jobs']:
        i=job['index'];case,slot,config,rep,draws=manifest['jobs'][i];p=root/f'{i:03d}'/'result/RESULT.json'
        r=json.loads(p.read_text()) if p.exists() else dict(case=case,config=config,rep=rep,draws=draws,status='resource_failed')
        assert (r['case'],r['config'],r['rep'],r['draws'])==(case,config,rep,draws)
        r['slot']=slot;r['resource_seconds']=job.get('elapsed_seconds',0)
        if job.get('exit_code')!=0 or not job.get('group_drained'):r['status']='resource_failed'
        result.append(r)
    return result

def score(r):
    if r['status']!='ok':return 1e12
    m=r['metrics']
    if any(m.get(k) is None for k in ('max_error_ratio','max_mcse_ratio','rhat_max','ess_min')):return 1e12
    return max(m['max_error_ratio'],m['max_mcse_ratio'],(m['rhat_max']-1)/.01,400/max(m['ess_min'],1e-12),1+m['divergences'],1+m['depth_hits'])

def select(root,out):
    data=rows(root);assert len(data)==144;selected={};details={}
    for case in range(len(CASES)):
        selected[str(case)]={};details[str(case)]={}
        for engine in ('walnuts','nuts'):
            options=[]
            for config,c in CONFIGS.items():
                group=[r for r in data if r['case']==case and r['config']==config]
                if c['engine']!=engine or not group:continue
                passes=sum(r['status']=='ok' and r['metrics']['passed'] for r in group)
                seconds=float(np.median([r.get('seconds',1e12) for r in group]));worst=max(map(score,group))
                options.append(dict(config=config,passes=passes,worst_gate=worst,seconds=seconds))
            options.sort(key=lambda r:(-r['passes'],0 if r['passes']==2 else r['worst_gate'],r['seconds'],r['config']))
            selected[str(case)][engine]=options[0]['config'];details[str(case)][engine]=options
    result=dict(selected=selected,calibration=details)
    with Path(out).open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(selected))

def ladder(group):
    total=kernel=calls=0.;complete=True
    for budget in BUDGETS:
        r=next((r for r in group if r['draws']==budget),None)
        if r is None:return dict(reached=False,censored=True)
        total+=r.get('total_seconds',r.get('resource_seconds',0));kernel+=r.get('seconds',0)+r.get('materialize_seconds',0);calls+=r.get('target_calls',0)
        complete &= 'seconds' in r and 'target_calls' in r
        if r['status']=='ok' and r['metrics']['passed']:return dict(reached=True,budget=budget,total=total,kernel=kernel if complete else None,calls=calls if complete else None)
    return dict(reached=False,censored=True,total_spent=total)

def ratios(a,b,metric):
    x=np.array([v[metric]/w[metric] for v,w in zip(a,b) if v['reached'] and w['reached'] and v.get(metric) is not None and w.get(metric)])
    if not len(x):return dict(n=0,median=None,interval95=None)
    rng=np.random.default_rng(745000000);boot=np.median(x[rng.integers(0,len(x),(10000,len(x)))],axis=1)
    return dict(n=len(x),median=float(np.median(x)),interval95=np.quantile(boot,[.025,.975]).tolist())

def report(root,out):
    data=rows(root);assert len(data)==384;result={}
    for case,(dim,b) in enumerate(CASES):
        v=dict(dim=dim,curvature=b,methods={});ladders={}
        for slot in ('walnuts','nuts','default','reparam'):
            group=[r for r in data if r['case']==case and r['slot']==slot]
            series=[ladder([r for r in group if r['rep']==rep]) for rep in range(8)];ladders[slot]=series
            v['methods'][slot]=dict(config=group[0]['config'],reached=sum(r['reached'] for r in series),ladders=series,fixed={})
            for d in BUDGETS:
                g=[r for r in group if r['draws']==d and r['status']=='ok']
                v['methods'][slot]['fixed'][str(d)]=dict(completed=len(g),passed=sum(r['metrics']['passed'] for r in g),median_seconds=float(np.median([r['seconds']+r['materialize_seconds'] for r in g])) if g else None,median_calls=float(np.median([r['target_calls'] for r in g])) if g else None)
        v['comparison_over_selected_walnuts']={slot:{m:ratios(ladders[slot],ladders['walnuts'],m) for m in ('total','kernel','calls')} for slot in ('nuts','default','reparam')}
        result[str(case)]=v
    out=Path(out);out.mkdir(exist_ok=False)
    (out/'SUMMARY.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');(out/'ROWS.json').write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:{s:m['reached'] for s,m in v['methods'].items()} for k,v in result.items()}))

if __name__=='__main__':globals()[sys.argv[1]](*sys.argv[2:])
