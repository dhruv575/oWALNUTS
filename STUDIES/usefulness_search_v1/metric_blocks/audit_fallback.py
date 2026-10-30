import hashlib,json,time,traceback,zipfile
from pathlib import Path
import numpy as np
from metric_criterion import criterion
from fisher_high_precision import covariance_from_samples
from selector_full_shape import select
root=Path(__file__).resolve().parent;work=root.parent;inputs={};rows=[];start=time.monotonic()
def read(p):
    raw=p.read_bytes();inputs[str(p)]=hashlib.sha256(raw).hexdigest();return json.loads(raw)
refpath=Path('/home/ubuntu/infra/posteriordb/posterior_database/reference_posteriors/draws/draws/sblrc-blr.json.zip')
inputs[str(refpath)]=hashlib.sha256(refpath.read_bytes()).hexdigest()
with zipfile.ZipFile(refpath) as z:ref=json.loads(z.read(z.namelist()[0]))
names=[f'beta[{i}]' for i in range(1,6)]+['sigma'];a=np.asarray([[c[n] for n in names] for c in ref]).transpose(0,2,1)
a[:,:,-1]=np.log(a[:,:,-1]);rc=np.cov(a.reshape(-1,6),rowvar=False);rl=np.linalg.cholesky(rc)
def geometry(c):
    z=np.linalg.solve(rl,c);z=np.linalg.solve(rl,z.T).T;e=np.linalg.eigvalsh((z+z.T)/2)
    assert min(e)>0
    return dict(condition=float(max(e)/min(e)),diagonal_ratio=(np.diag(c)/np.diag(rc)).tolist())
for chunk in range(1,5):
    parent=work/f'hybrid0{chunk}';summary=read(parent/'SUMMARY.json')
    for row in [r for r in summary['rows'] if r['arm']=='hybrid']:
        prefix=f"{row['model']}-{row['seed']}";pilot=read(parent/'runs'/(prefix+'-pilot')/'RESULT.json');fit=read(parent/'runs'/(prefix+'-fit')/'RESULT.json')
        x=np.array(pilot['draws']);d=x.shape[-1];y=np.array(fit['scores']).reshape(x.shape)
        coarse=np.array(fit['coarse']).reshape(4,4,d,d);fine=np.array(fit['fine']).reshape(4,4,d,d)
        entry=dict(model=row['model'],seed=row['seed'],branch=fit['branch'],folds=[])
        if row['model']=='sblrc-blr':
            fc=np.linalg.inv(fit['fisher_mass']);vc=np.linalg.inv(fit['v4_mass']);reconstructed,info=select(fit['coarse'],fit['fine'],np.diag(fc))
            entry['geometry']={k:geometry(c) for k,c in [('fisher',fc),('v4',vc),('fisher_scaled_block',reconstructed)]}
        for held in range(4):
            train=[i for i in range(4) if i!=held];tx=x[train].reshape(-1,d);ty=y[train].reshape(-1,d)
            v=np.maximum(x[train].var(axis=1,ddof=1).mean(0),1e-8);hc=np.cov(x[held],rowvar=False)
            fold=dict(held_chain=held,metrics={})
            try:
                fc=covariance_from_samples(tx,ty);bc,info=select(coarse[train].reshape(-1,d,d),fine[train].reshape(-1,d,d),v)
                candidates=dict(fisher=fc,block=bc,diagonal=np.diag(v),empirical=np.cov(tx,rowvar=False))
                for name,c in candidates.items():fold['metrics'][name]=criterion(c,fine[held],hc)
                fold['blocks']=info['blocks']
            except Exception:fold['error']=traceback.format_exc()
            entry['folds'].append(fold)
        if all('error' not in f for f in entry['folds']):
            entry['worst_fold_scores']={k:max(f['metrics'][k]['maximum'] for f in entry['folds']) for k in ['fisher','block','diagonal','empirical']}
            entry['preferred']=min(entry['worst_fold_scores'],key=entry['worst_fold_scores'].get)
        rows.append(entry)
        (root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n')
sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('*.py')}
result=dict(hypothesis_development_only=True,rows=rows,inputs=inputs,sources=sources,seconds=time.monotonic()-start,target_calls=0,
    unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in inputs.items()))
(root/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(cells=len(rows),seconds=result['seconds'],failed_cells=sum('preferred' not in r for r in rows))))
