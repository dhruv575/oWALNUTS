import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import json,time
from pathlib import Path
import numpy as np
from scipy.linalg import solve_triangular
import bridgestan as bs
from grid import GridGP,JITTER
BASE=Path(__file__).resolve().parent
data=json.loads((BASE/'GP-TRAIN.json').read_text());model=GridGP(data)
target=bs.StanModel('/home/ubuntu/lanes/spatial-counts-preflight-20261030/spatial_gp_model.so',data=(BASE/'GP-TRAIN.json').read_text(),seed=1)
rng=np.random.default_rng(954000001);rows=[];points=[]
names=target.param_names(include_tp=True,include_gq=False);ix=[names.index(f'f.{i}') for i in range(1,201)]
for rho in [.3,.7,1.,2.]:
    q=rng.normal(0,.2,205);q[:2]=[np.log(rho),np.log(1.2)]
    factor=model.factor(q[:2]);field=model.apply(factor,q[5:]);k=1.2**2*np.exp(-.5*model.dist/rho**2)+JITTER*np.eye(200)
    stanq=q.copy();stanq[5:]=solve_triangular(np.linalg.cholesky(k),field,lower=True)
    gridlp=model.evaluate(q)[0];stanlp=target.log_density(stanq,propto=True,jacobian=True)
    f=target.param_constrain(stanq,include_tp=True,include_gq=False)[ix]
    rows.append(dict(rho=rho,density_difference=float(gridlp-stanlp),field_error=float(np.max(abs(f-model.field(factor,q[2:])))),prior_norm_error=float(abs(q[5:]@q[5:]-stanq[5:]@stanq[5:]))));points.append((q,stanq))
timings=[]
for repeat in range(5):
    row={}
    for name in (['grid','stan'] if repeat%2 else ['stan','grid']):
        start=time.perf_counter()
        for _ in range(50):
            for q,sq in points:
                if name=='grid':model.evaluate(q)
                else:target.log_density_gradient(sq,propto=True,jacobian=True)
        row[name]=(time.perf_counter()-start)/200
    timings.append(row)
result=dict(rows=rows,timings=timings,scope='Same physical field; distinct whitening. Timings include Python API overhead. Near-singular root conversion can amplify floating-point error.')
(BASE/'GRID-STAN-CHECK.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
