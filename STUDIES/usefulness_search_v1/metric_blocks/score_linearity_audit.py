"""Post-hoc hypothesis audit, never independent validation."""
import hashlib,json,time
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parent;work=root.parent;rows=[];hashes={};start=time.monotonic()
controls=json.loads((work/'fishercompare01/SUMMARY.json').read_text())['rows']
for row in controls:
    prefix=f"{row['model']}-{row['seed']}";pp=work/'broad01/runs'/(prefix+'-pilot')/'RESULT.json';fp=work/'fishercompare01/runs'/(prefix+'-fit')/'RESULT.json'
    for p in [pp,fp]:hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    x=np.array(json.loads(pp.read_text())['draws']);y=np.array(json.loads(fp.read_text())['scores']).reshape(x.shape);folds=[]
    for held in range(4):
        train=[i for i in range(4) if i!=held];tx=x[train].reshape(-1,x.shape[-1]);ty=y[train].reshape(tx.shape)
        mean=tx.mean(0);scale=tx.std(0,ddof=1);assert min(scale)>0
        design=np.column_stack([np.ones(len(tx)),(tx-mean)/scale]);coef,_,rank,_=np.linalg.lstsq(design,ty,rcond=None)
        assert rank==design.shape[1]
        pred=np.column_stack([np.ones(len(x[held])),(x[held]-mean)/scale])@coef;e=y[held]-pred
        centered=y[held]-y[held].mean(0);_,r=np.linalg.qr(centered,mode='reduced')
        # Worst directional relative squared error, including prediction bias.
        relative=np.linalg.solve(r.T,e.T).T
        r2=1-float(np.linalg.norm(relative,ord=2)**2)
        individual=1-(e*e).sum(0)/(centered*centered).sum(0)
        folds.append(dict(held_chain=held,worst_direction_r2=r2,min_coordinate_r2=float(min(individual)),
            test_score_factor_condition=float(np.linalg.cond(r)),design_condition=float(np.linalg.cond(design))))
    rows.append(dict(model=row['model'],seed=row['seed'],fisher_passed=row['passed'],folds=folds,
        worst_direction_r2=min(f['worst_direction_r2'] for f in folds),min_coordinate_r2=min(f['min_coordinate_r2'] for f in folds)))
result=dict(hypothesis_development_only=True,rows=rows,seconds=time.monotonic()-start,target_calls=0,inputs=hashes,
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(root/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(rows))
