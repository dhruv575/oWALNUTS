import json
import numpy as np
from hybrid_gate import evaluate
rng=np.random.default_rng(929299999);x=rng.normal(size=(4,100,5));q=rng.normal(size=(5,5));precision=q@q.T+np.eye(5);y=-x@precision
rows=[]
g=evaluate(x,y);rows.append(dict(test='affine_score',passed=g['use_fisher'] and min(f['worst_direction_r2'] for f in g['folds'])>1-1e-10))
perm=rng.permutation(5);p=evaluate(x[:,:,perm],y[:,:,perm]);rows.append(dict(test='coordinate_permutation',passed=p['use_fisher']==g['use_fisher']))
a=rng.normal(size=(5,5))+4*np.eye(5);t=evaluate(x@a,y@np.linalg.inv(a).T);rows.append(dict(test='invertible_coordinate_change',passed=t['use_fisher']))
n=evaluate(x,x*x);rows.append(dict(test='quadratic_score_declined',passed=not n['use_fisher']))
for name,xx,yy in [('singular',np.zeros_like(x),np.zeros_like(y)),('nonfinite',x,np.full_like(y,np.nan)),('wrong_shape',x,y[:3])]:
    rows.append(dict(test=name,passed=not evaluate(xx,yy)['use_fisher']))
print(json.dumps(dict(passed=all(r['passed'] for r in rows),rows=rows)))
assert all(r['passed'] for r in rows)
