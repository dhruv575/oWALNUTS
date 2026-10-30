import json,numpy as np
from metric_criterion import criterion
rng=np.random.default_rng(929400000);rows=[]
for d in [2,5,10]:
    a=rng.normal(size=(d,d));c=a@a.T+np.eye(d);h=np.linalg.inv(c);perm=rng.permutation(d)
    base=criterion(c,[h],c)['maximum'];scaled=criterion(37*c,[h],c)['maximum']
    pc=criterion(c[np.ix_(perm,perm)],[h[np.ix_(perm,perm)]],c[np.ix_(perm,perm)])['maximum']
    rows.append(dict(d=d,passed=abs(base-1)<1e-10 and abs(scaled-base)<1e-10 and abs(pc-base)<1e-10))
try:criterion(np.diag([1.,-1.]),[np.eye(2)],np.eye(2));bad=False
except np.linalg.LinAlgError:bad=True
rows.append(dict(test='indefinite_rejected',passed=bad));print(json.dumps(dict(passed=all(r['passed'] for r in rows),rows=rows)));assert all(r['passed'] for r in rows)
