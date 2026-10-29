import json,sys
from pathlib import Path
import numpy as np
from worker import CONFIGS
from targets import SIZES

def ratio(a,b,metric):
    x=np.array([n[metric]/w[metric] for n,w in zip(a,b) if n.get('passed') and w.get('passed')])
    if len(x)==0:return dict(pairs=0,median=None,interval95=None)
    rng=np.random.default_rng(835000000);boot=np.median(x[rng.integers(0,len(x),(10000,len(x)))],axis=1)
    return dict(pairs=len(x),median=float(np.median(x)),interval95=np.quantile(boot,[.025,.975]).tolist())

def run(root,out):
    root=Path(root);m=json.loads((root/'MANIFEST.json').read_text());f=json.loads((root/'FINAL.json').read_text())
    assert len(m['jobs'])==len(f['jobs'])==24 and f['sources_unchanged']
    rows=[]
    for job in f['jobs']:
        i=job['index'];case,config,rep=m['jobs'][i];p=root/f'{i:03d}'/'result/RESULT.json'
        r=json.loads(p.read_text()) if p.exists() else dict(case=case,config=config,rep=rep,status='resource_failed')
        assert (r['case'],r['config'],r['rep'])==(case,config,rep)
        if job.get('exit_code')!=0 or not job.get('group_drained'):r['status']='resource_failed'
        r['passed']=r['status']=='ok' and r['metrics']['passed']
        if r['status']=='ok':r['kernel']=r['seconds']+r['materialize_seconds']
        rows.append(r)
    summary=dict(planned=24,completed=sum(r['status']=='ok' for r in rows),drained=sum(bool(j.get('group_drained')) for j in f['jobs']),wall_seconds=f['elapsed_seconds'],cases={})
    for case,n in [(1,SIZES[1])]:
        v=dict(n=n,methods={},comparisons_over_walnuts={});groups={}
        for c in ('walnuts_full','nuts_full','nuts_lowrank_full'):
            g=sorted([r for r in rows if r['case']==case and r['config']==c],key=lambda r:r['rep']);groups[c]=g
            v['methods'][c]=dict(completed=sum(r['status']=='ok' for r in g),passed=sum(r['passed'] for r in g),
                median_kernel=float(np.median([r['kernel'] for r in g if r['status']=='ok'])) if any(r['status']=='ok' for r in g) else None,
                median_total=float(np.median([r['total_seconds'] for r in g if r['status']=='ok'])) if any(r['status']=='ok' for r in g) else None,
                median_calls=float(np.median([r['target_calls'] for r in g if r['status']=='ok'])) if any(r['status']=='ok' for r in g) else None)
        for c in ('walnuts_full','nuts_full','nuts_lowrank_full'):
            if c!='walnuts_full':v['comparisons_over_walnuts'][c]={metric:ratio(groups[c],groups['walnuts_full'],metric) for metric in ('kernel','total_seconds','target_calls')}
        assert len(set(r['data_sha256'] for r in rows if r['case']==case and r['status']=='ok'))==1
        summary['cases'][str(case)]=v
    out=Path(out);out.mkdir(exist_ok=False)
    for name,data in [('SUMMARY.json',summary),('ROWS.json',rows)]: (out/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summary))

if __name__=='__main__':run(*sys.argv[1:])
