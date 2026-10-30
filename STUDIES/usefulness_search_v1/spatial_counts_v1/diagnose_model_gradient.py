import hashlib,json
from pathlib import Path
import numpy as np,bridgestan as bs
base=Path(__file__).resolve().parent;so=base/'model01/spatial_gp_model.so';target=bs.StanModel(str(so),data=(base/'data01/GP-TRAIN.json').read_text(),seed=1);points=np.random.default_rng(952100001).normal(scale=.25,size=(8,205));rows=[]
for i,q in enumerate(points):
    _,g=target.log_density_gradient(q)
    for j in [0,1]:
        checks=[]
        for step in [1e-2,1e-3,1e-4,1e-5,1e-6]:
            plus=q.copy();minus=q.copy();plus[j]+=step;minus[j]-=step;fd=(target.log_density(plus)-target.log_density(minus))/(2*step);checks.append(dict(step=step,finite_difference=float(fd),scaled_error=float(abs(fd-g[j])/max(1,abs(g[j])))))
        rows.append(dict(point=i,coordinate=j,autodiff=float(g[j]),checks=checks))
result=dict(scope='Diagnostic step-size sweep only; original preflight remains failed',library_sha256=hashlib.sha256(so.read_bytes()).hexdigest(),rows=rows);(base/'GRADIENT-DIAGNOSTIC.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(max_scaled_error_by_step={str(h):max(next(c['scaled_error'] for c in row['checks'] if c['step']==h) for row in rows) for h in [1e-2,1e-3,1e-4,1e-5,1e-6]})))
