import hashlib,json,sys,time
from pathlib import Path
import numpy as np,bridgestan as bs
from scipy.special import roots_hermitenorm,logsumexp,gammaln
base=Path(__file__).resolve().parent;job=json.loads((base/'JOBS.json').read_text())[int(sys.argv[1])];out=base/'repair01'/job['name'];hashes=json.loads((base/'INPUT-HASHES.json').read_text())
for n,h in hashes.items():assert hashlib.sha256(Path(n).read_bytes()).hexdigest()==h,n
source=Path(job['draws']);assert hashlib.sha256(source.read_bytes()).hexdigest()==job['draws_sha256'];a=np.load(source);q=a['q'] if job['kind']=='importance' else a['sample_stats__unconstrained_draw'][job['chain']];assert q.shape[1]==81
labels=json.loads((base/'HELDOUT.json').read_text());observed=[x for x in labels if x['count'] is not None];years=np.array([x['year'] for x in observed]);y=np.array([x['count'] for x in observed]);select=years-1931;assert len(y)==30
target=bs.StanModel(str(base/'predictive_gp_model.so'),data=(base/'DATA.json').read_text(),seed=1);rng=target.new_rng(951700002);names=target.param_names(include_tp=True,include_gq=True);mx=[names.index(f'future_mean.{j}') for j in range(1,32)];vx=[names.index(f'future_variance.{j}') for j in range(1,32)];start=time.perf_counter();mu=np.empty((len(q),31));var=np.empty_like(mu)
for i,x in enumerate(q):
    v=np.asarray(target.param_constrain(x,include_tp=True,include_gq=True,rng=rng));mu[i]=v[mx];var[i]=v[vx]
assert np.isfinite(mu).all() and np.isfinite(var).all() and np.min(var)>=0
probabilities={}
for nodes in [128,256]:
    z,w=roots_hermitenorm(nodes);logw=np.log(w)-.5*np.log(2*np.pi);p=np.empty((len(q),30));lp=np.empty_like(p)
    for first in range(0,len(q),32):
        m=mu[first:first+32,select];s=np.sqrt(var[first:first+32,select]);f=m[:,:,None]+s[:,:,None]*z
        with np.errstate(over='ignore'):loglike=y[None,:,None]*f-np.exp(f)-gammaln(y[None,:,None]+1)
        lp[first:first+32]=logsumexp(loglike+logw,axis=2);p[first:first+32]=np.exp(lp[first:first+32])
    assert np.isfinite(p).all() and np.min(p)>=0 and np.max(p)<=1 and np.all(lp[p==0]<=np.log(np.finfo(float).tiny));probabilities['p'+str(nodes)]=p;probabilities['logp'+str(nodes)]=lp
np.savez_compressed(out/'PREDICTIVE.npz',mu=mu,variance=var,years=years,**probabilities)
assert hashlib.sha256(source.read_bytes()).hexdigest()==job['draws_sha256']
for n,h in hashes.items():assert hashlib.sha256(Path(n).read_bytes()).hexdigest()==h,n
result=dict(worker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),completed=True,job=job,draws=len(q),seconds=time.perf_counter()-start,min_variance=float(np.min(var)),scope='Conditional moments and quadrature only; aggregation and accuracy gates pending')
(out/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(job=job['name'],completed=True)),flush=True)
