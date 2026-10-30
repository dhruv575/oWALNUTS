import hashlib,json,time
from pathlib import Path
import numpy as np
from selector_full_shape import select
root=Path(__file__).resolve().parent;old=root.parent/'ablation01'
checks=[];inputs={};begin=time.monotonic()
def check(name,value):checks.append(dict(name=name,passed=bool(value)))
cov=np.array([[.01,.9,0],[.9,100.,0],[0,0,2.]])
p=np.linalg.inv(cov);h=np.array([p*s for s in [1.,10.,100.,1000.]])
v=np.array([1e-5,1e6,2.]);c,info=select(h,h,v)
check('block_discovery',info['blocks']==[[0,1]])
check('relative_shape',np.allclose(c[:2,:2]/np.trace(c[:2,:2]),cov[:2,:2]/np.trace(cov[:2,:2]),atol=1e-12))
check('positive_definite',np.linalg.eigvalsh(c).min()>0)
identity=np.tile(np.eye(3),(4,1,1));fallback,fi=select(identity,identity,v)
check('exact_fallback',np.array_equal(fallback,np.diag(v)) and not fi['blocks'])
rng=np.random.default_rng(928700000)
for i in range(12):
    perm=rng.permutation(3);cm,ii=select(h[:,perm,:][:,:,perm],h[:,perm,:][:,:,perm],v[perm])
    check(f'permutation_{i}',np.allclose(cm,c[np.ix_(perm,perm)],atol=1e-10,rtol=1e-10))
    units=np.exp(rng.uniform(-5,5,3));hp=h/np.outer(units,units);cm,ii=select(hp,hp,v*units**2)
    check(f'exact_shape_units_{i}',np.allclose(cm,c*np.outer(units,units),atol=1e-10,rtol=1e-9))
diagnosis=json.loads((old/'DIAGNOSIS.json').read_text());exact=np.array(diagnosis['exact_unconstrained_covariance']);precision=np.linalg.inv(exact)
rows=[]
for seed in range(928600001,928600017):
    path=old/f'{seed}-MATRICES.json';inputs[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest();m=json.loads(path.read_text())
    cm,ii=select(m['coarse'],m['fine'],m['variances']);check(f'discovery_{seed}',ii['blocks']==m['selection']['blocks'])
    l=np.linalg.cholesky(cm);w=l.T@precision@l;e=np.linalg.eigvalsh((w+w.T)/2);condition=float(e[-1]/e[0])
    prior=next(r for r in diagnosis['rows'] if r['seed']==seed and r['arm']=='curvature')
    ratio=prior['condition_proxy']/condition
    if not prior['passed']:check(f'failed_geometry_{seed}',ratio>=10)
    rows.append(dict(seed=seed,old_passed=prior['passed'],old_condition=prior['condition_proxy'],
        new_condition=condition,condition_reduction=ratio,covariance=cm.tolist(),selection=ii))
for p in [root/'selector.py',root/'selector_full_shape.py',root/'preflight_full_shape.py',root/'FULL-SHAPE-PROTOCOL.md',old/'DIAGNOSIS.json']:
    inputs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
result=dict(passed=all(c['passed'] for c in checks),checks=checks,rows=rows,seconds=time.monotonic()-begin,inputs=inputs,target_calls=0)
(root/'SUMMARY.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(result))
if not result['passed']:raise SystemExit(1)
