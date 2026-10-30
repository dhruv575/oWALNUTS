import json,time,zipfile
from pathlib import Path
import numpy as np,arviz as az
from scipy.optimize import minimize
from common import Target,ROOT,NAME
b=Target();rng=np.random.default_rng(943000001);base=np.zeros(13);base[:2]=np.log([6.,2.]);trials=[];t=time.monotonic()
def objective(q):
 lp,g=b.gradient(q)
 return (-lp,-g) if np.isfinite(lp) and np.isfinite(g).all() else (1e100,np.zeros(13))
def hessian(q,h):
 H=np.column_stack([-(b.gradient(q+np.eye(13)[j]*h)[1]-b.gradient(q-np.eye(13)[j]*h)[1])/(2*h) for j in range(13)])
 return (H+H.T)/2
for i in range(4):
 start=base.copy() if i==0 else base+.2*rng.normal(size=13);r=minimize(objective,start,jac=True,method='BFGS',options=dict(maxiter=1000,gtol=1e-6));lp,g=b.gradient(r.x);H=hessian(r.x,1e-4);eig=np.linalg.eigvalsh(H);passed=bool(np.isfinite(lp) and np.max(np.abs(g))<1e-3 and np.isfinite(H).all() and eig.min()>0)
 trials.append(dict(index=i,start=start.tolist(),q=r.x.tolist(),logp=float(lp),gradient_max=float(np.max(np.abs(g))),min_eigenvalue=float(eig.min()),optimizer_success=bool(r.success),message=str(r.message),nit=int(r.nit),passed=passed))
 (ROOT/'OPTIMIZERS.json').write_text(json.dumps(trials,indent=2)+'\n')
best=max((r for r in trials if r['passed']),key=lambda r:r['logp']);q=np.array(best['q']);H=hessian(q,1e-4);H2=hessian(q,2e-4);herr=float(np.linalg.norm(H-H2)/np.linalg.norm(H));assert herr<.002
cov=np.linalg.inv(H);L=np.linalg.cholesky(cov);errs=[]
for _ in range(10):
 p=q+.1*L@rng.normal(size=13);g=b.gradient(p)[1];h=1e-5;fd=np.array([(b.value(p+np.eye(13)[j]*h)-b.value(p-np.eye(13)[j]*h))/(2*h) for j in range(13)]);errs.append(float(np.max(np.abs(g-fd)/(1+np.abs(g)))))
assert max(errs)<1e-4
refpath=Path('/home/ubuntu/infra/posteriordb/posterior_database/reference_posteriors/draws/draws')/(NAME+'.json.zip')
with zipfile.ZipFile(refpath) as z:ref=json.loads(z.read(z.namelist()[0]))
names=['rho','alpha']+[f'f[{i}]' for i in range(1,12)];a=np.array([[c[n] for n in names] for c in ref]).transpose(0,2,1);a=np.concatenate([a,np.exp(a[:,:,2:])],axis=2);ds=az.convert_to_dataset({'p':a})
stats={k:np.asarray(fn(ds).p).tolist() for k,fn in [('rhat',lambda d:az.rhat(d,method='rank')),('bulk',lambda d:az.ess(d,method='bulk')),('tail',lambda d:az.ess(d,method='tail')),('mcse',lambda d:az.mcse(d,method='mean'))]}
stats.update(mean=a.mean((0,1)).tolist(),sd=a.reshape(-1,24).std(0,ddof=1).tolist());qualified=bool(np.isfinite(a).all() and max(stats['rhat'])<=1.01 and min(stats['bulk'])>=400 and min(stats['tail'])>=400)
np.savez_compressed(ROOT/'reference.npz',values=a);(ROOT/'REFERENCE.json').write_text(json.dumps(dict(names=names+[f'intensity[{i}]' for i in range(1,12)],stats=stats,qualified=qualified),indent=2)+'\n');assert qualified
r=dict(mode=q.tolist(),cov=cov.tolist(),L=L.tolist(),selected_start=best['index'],hessian_relative_error=herr,gradient_max_scaled_error=max(errs),calls=b.counts(),seconds=time.monotonic()-t);(ROOT/'PREPARED.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k not in ['mode','cov','L']}))
