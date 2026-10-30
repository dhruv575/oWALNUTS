import hashlib,json,sys
from pathlib import Path
import numpy as np,bridgestan as bs
from scipy.special import roots_hermite,gammaln,logsumexp
from scipy.linalg import solve_triangular
base=Path(__file__).resolve().parent;index=int(sys.argv[1]);job=json.loads((base/'JOBS.json').read_text())[index];name=job['name'];out=base/'audit01'/name;source=Path(job['draws']);assert hashlib.sha256(source.read_bytes()).hexdigest()==job['draws_sha256'];a=np.load(source);q=a['q'] if job['kind']=='importance' else a['sample_stats__unconstrained_draw'][job['chain']]
folder=base/('repair01' if name in ['screen-0-importance','screen-1-importance','fresh-0-importance'] else 'results')/name;saved=np.load(folder/'PREDICTIVE.npz');cfg=json.loads((base/'DATA.json').read_text());model=bs.StanModel(str(base/'predictive_gp_model.so'),data=(base/'DATA.json').read_text(),seed=1);rng=model.new_rng(951700002);names=model.param_names(include_tp=True,include_gq=True);mx=[names.index(f'future_mean.{j}') for j in range(1,32)];vx=[names.index(f'future_variance.{j}') for j in range(1,32)]
actual=np.asarray([model.param_constrain(x,include_tp=True,include_gq=True,rng=rng)[mx+vx] for x in q]);mu=actual[:,:31];var=actual[:,31:];assert np.allclose(mu,saved['mu'],rtol=1e-10,atol=1e-10) and np.allclose(var,saved['variance'],rtol=1e-10,atol=1e-10)
labels=[x for x in json.loads((base/'HELDOUT.json').read_text()) if x['count'] is not None];y=np.array([x['count'] for x in labels]);years=np.array([x['year'] for x in labels]);select=years-1931;assert np.array_equal(saved['years'],years);errors=[]
for nodes in [128,256]:
    z,w=roots_hermite(nodes);logw=np.log(w)-.5*np.log(np.pi);maxerr=0.
    for start in range(0,len(q),32):
        f=mu[start:start+32,select,None]+np.sqrt(2*var[start:start+32,select,None])*z
        with np.errstate(over='ignore'):lp=logsumexp(logw+y[None,:,None]*f-np.exp(f)-gammaln(y[None,:,None]+1),axis=2)
        p=np.exp(lp);prior=saved['p'+str(nodes)][start:start+32];assert np.allclose(p,prior,rtol=1e-8,atol=1e-10);maxerr=max(maxerr,float(np.max(abs(p-prior))))
    errors.append(dict(nodes=nodes,max_abs_probability_error=maxerr))
raw=bs.StanModel('/home/ubuntu/lanes/gp-portable-runtime-20261030/models/raw.so',data=(base/'GP-TRAIN.json').read_text(),seed=1);rn=raw.param_names(include_tp=True,include_gq=False);fi=[rn.index(f'f.{j}') for j in range(1,80)];chosen=np.unique(np.r_[0,len(q)-1,np.random.default_rng(951900001+index).integers(0,len(q),6)]);independent=[]
for i in chosen:
    point=q[i];rho,alpha=np.exp(point[:2]);basis=np.r_[point[:2],np.zeros(79)];L=np.empty((79,79))
    for j in range(79):
        basis[2+j]=1;L[:,j]=np.asarray(raw.param_constrain(basis,include_tp=True,include_gq=False))[fi];basis[2+j]=0
    B=alpha**2*np.exp(-.5*((np.asarray(cfg['x'])[:,None]-np.asarray(cfg['x_future'])[None,:])/rho)**2);A=solve_triangular(L,B,lower=True);m=A.T@point[2:];v=alpha**2+1e-10-np.sum(A*A,axis=0);me=float(max(abs(m-mu[i])));ve=float(max(abs(v-var[i])));assert me<=1e-6 and ve<=1e-6;independent.append(dict(draw=int(i),mean_error=me,variance_error=ve))
result=dict(passed=True,name=name,all_draws_replayed=len(q),quadrature_errors=errors,original_model_checks=independent,predictive_sha256=hashlib.sha256((folder/'PREDICTIVE.npz').read_bytes()).hexdigest(),worker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest());(out/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(name=name,passed=True)),flush=True)
