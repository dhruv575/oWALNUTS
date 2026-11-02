import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import json,time
from pathlib import Path
import numpy as np
from grid_backend import Native
BASE=Path(__file__).resolve().parent
data=json.loads((BASE/'GP-TRAIN.json').read_text());native=Native(data);model=native.model;rng=np.random.default_rng(954000003)
rows=[];points=[]
for rho in [.1,.3,.7,1.,2.,4.]:
    for repeat in range(4):
        q=rng.normal(0,.2,205);q[:2]=[np.log(rho),rng.uniform(-1,1)];points.append(q)
        a,g=native.value(q);b,h=model.evaluate(q)
        fd=[]
        for j in [0,1,2,5,204]:
            d=np.eye(205)[j]*1e-4;v=(native.value(q+d)[0]-native.value(q-d)[0])/2e-4
            fd.append(abs(v-g[j])/max(1.,abs(g[j])))
        rows.append(dict(rho=rho,alpha=float(np.exp(q[1])),density_error=abs(a-b),gradient_error=float(np.max(abs(g-h)/np.maximum(1,abs(h)))),fd_error=float(max(fd))))
timings=[]
for repeat in range(5):
    row={}
    for name,fn in [('native',native.value),('python',model.evaluate)] if repeat%2 else [('python',model.evaluate),('native',native.value)]:
        start=time.perf_counter()
        for _ in range(10):
            for q in points:fn(q)
        row[name]=(time.perf_counter()-start)/240
    timings.append(row)
passed=all(r['density_error']<=1e-5 and r['gradient_error']<=1e-3 and r['fd_error']<=1e-3 for r in rows)
result=dict(passed=passed,rows=rows,timings=timings,counts=native.counts());native.close()
(BASE/'GRID-NATIVE-PREFLIGHT.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));assert passed
