import hashlib,json
from pathlib import Path
import numpy as np
from native import Native,ROOT
inputs={}
paths=list(Path('/dev/shm/population-pk-20261029/run01').glob('*/result/RESULT.json'))
fits=[]
for p in paths:
 r=json.loads(p.read_text())
 if r['kind']=='linear' and r['qualified']:fits.append((r,p))
r,p=max(fits,key=lambda item:item[0]['lp']);inputs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();mode=np.array(r['q']);b=Native();rows=[]
for scale in (0.,.01,.1):
 for rep in range(4):
  q=mode+scale*np.random.default_rng(929000000+rep).normal(size=43);v,g=b.value(q);vv,gg=b.model.value(q);vo=b.density(q)
  rows.append(dict(scale=scale,rep=rep,log_density_error=abs(v-vv),gradient_error=float(np.max(abs(g-gg)/(1+abs(gg)))),value_only_offset=vo-v))
assert max(r['log_density_error'] for r in rows)<1e-8 and max(r['gradient_error'] for r in rows)<1e-8
assert np.ptp([r['value_only_offset'] for r in rows])<1e-8
h=1e-4;H=np.empty((43,43))
for j in range(43):
 e=np.zeros(43);e[j]=h;H[:,j]=-(b.value(mode+e)[1]-b.value(mode-e)[1])/(2*h)
H=(H+H.T)/2;eig,V=np.linalg.eigh(H);assert eig.min()>0
cov=(V/eig)@V.T;L=np.linalg.cholesky(cov);white=Native(center=mode,A=L)
for rep in range(4):
 x=.1*np.random.default_rng(929100000+rep).normal(size=43);v,g=white.value(x);vv,gg=b.value(mode+L@x)
 assert abs(v-vv)<1e-8 and np.max(abs(g-L.T@gg))<1e-7
white.close();b.close()
starts=mode+(.3*np.sin(np.arange(1,5)[:,None]*np.arange(1,44)[None,:]))@L.T
for n,d in [('NATIVE-CHECK',dict(rows=rows,hessian_min=float(eig.min()),hessian_max=float(eig.max()),whitening_pass=True)),('PREPARED',dict(mode=mode.tolist(),L=L.tolist(),cov=cov.tolist(),starts=starts.tolist(),source_fit=str(p))),('PREPARE-INPUTS',inputs)]:
 (ROOT/(n+'.json')).write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
print(json.dumps(dict(points=len(rows),hessian_min=float(eig.min()),hessian_max=float(eig.max()),max_gradient_error=max(r['gradient_error'] for r in rows),density_offset_range=float(np.ptp([r['value_only_offset'] for r in rows])))))
