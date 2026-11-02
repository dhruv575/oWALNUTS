import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import json,itertools,hashlib
from pathlib import Path
import numpy as np
import bridgestan as bs
from scipy.linalg import solve_triangular
from grid_backend import Native
BASE=Path(__file__).resolve().parent
data=json.loads((BASE/'GP-TRAIN.json').read_text());native=Native(data);model=native.model
stan=bs.StanModel('/home/ubuntu/lanes/spatial-counts-preflight-20261030/spatial_gp_model.so',data=(BASE/'GP-TRAIN.json').read_text(),seed=1)
names=stan.param_names(include_tp=True,include_gq=False);ix=[names.index(f'f.{i}') for i in range(1,201)]
groups=[];probes=[];rng=np.random.default_rng(954100099)
for directory in ['repair01','grid_native01','grid_native_early01','grid_precision01']:
    for f in sorted((BASE/directory).glob('*/artifact/SUMMARY.json')):
        d=json.loads(f.read_text());label=directory+'/'+f.parent.parent.name
        groups.append(dict(label=label,passed=d['passed'],stats=d['stats'],sampling_seconds=d['sampling_seconds'],worker_seconds=d['worker_seconds'],target_calls=d.get('target_calls',d.get('chain_info')),source_sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
        if directory=='repair01':continue
        a=np.load(f.parent/'DRAWS.npz')['q'].reshape(-1,205)
        indices=[int(i) for i in rng.choice(len(a),6,replace=False)]+[int(np.argmax(a[:,0])),int(np.argmax(a[:,1]))]
        for index in indices:
            q=a[index];v,g=native.value(q);py,h=model.evaluate(q)
            factor=model.factor(q[:2]);field=model.apply(factor,q[5:]);zero=q.copy();zero[5:]=0
            offset=stan.param_constrain(zero,include_tp=True,include_gq=False)[ix];columns=[]
            for j in range(200):
                basis=zero.copy();basis[j+5]=1
                columns.append(stan.param_constrain(basis,include_tp=True,include_gq=False)[ix]-offset)
            sq=q.copy();sq[5:]=solve_triangular(np.column_stack(columns),field,lower=True)
            slp=stan.log_density(sq,propto=True,jacobian=True);sf=stan.param_constrain(sq,include_tp=True,include_gq=False)[ix]
            probes.append(dict(group=label,index=index,rho=float(np.exp(q[0])),alpha=float(np.exp(q[1])),native_python_density=abs(v-py),native_python_gradient=float(max(abs(g-h)/np.maximum(1,abs(h)))),stan_density=abs(v-slp),stan_field=float(max(abs(sf-model.field(factor,q[2:]))))))
for index in range(4):
    old=Path('/home/ubuntu/lanes/spatial-counts-reference-20261031'+('' if index==0 else '-v2'))/'results'/str(index)/'SUMMARY.json'
    d=json.loads(old.read_text());groups.append(dict(label='historical/'+str(index),passed=d['passed'],stats=d['stats'],source_sha256=hashlib.sha256(old.read_bytes()).hexdigest()))
pairs=[]
for a,b in itertools.combinations(groups,2):
    x,y=a['stats'],b['stats'];delta=abs(np.array(x['mean'])-y['mean']);sd=(np.array(x['sd'])+y['sd'])/2;mcse=np.sqrt(np.array(x['mcse'])**2+np.array(y['mcse'])**2)
    row=dict(a=a['label'],b=b['label'],max_mean_sd=float(max(delta/sd)),max_z=float(max(delta/mcse)),max_relative_sd=float(max(abs(np.array(x['sd'])-y['sd'])/sd)))
    row['historical_pair_gate_pass']=row['max_mean_sd']<=.05 and row['max_z']<=4 and row['max_relative_sd']<=.1;pairs.append(row)
result=dict(numerical_pass=all(r['native_python_density']<=1e-5 and r['native_python_gradient']<=1e-3 and r['stan_density']<=1e-5 and r['stan_field']<=1e-10 for r in probes),probes=probes,pairs=pairs,groups=groups,scope='Numerical and exploratory physical agreement audit; historical combined reference remains unqualified; no heldout or prediction claims')
(BASE/'SPATIAL-PILOT-AUDIT.json').write_text(json.dumps(result,indent=2));native.close()
print(json.dumps(dict(numerical_pass=result['numerical_pass'],probes=len(probes),groups=len(groups),pair_failures=sum(not r['historical_pair_gate_pass'] for r in pairs)),indent=2))
