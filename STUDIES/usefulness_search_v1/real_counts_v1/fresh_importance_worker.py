import hashlib,json,sys,time
from pathlib import Path
import numpy as np,arviz as az,bridgestan as bs
from scipy.special import logsumexp
from conditional_proposal import ConditionalProposal
base=Path(__file__).resolve().parent;runtime=Path('/home/ubuntu/lanes/gp-portable-runtime-20261030');sys.path.insert(0,str(runtime))
from native_common import counter_handle,counter_read
rep=int(sys.argv[2]);seed=951600001+rep;out=Path(sys.argv[1]);data=base/'GP-TRAIN.json';so=runtime/'models/raw.so';shim=runtime/'preflight/raw/counted_model.so'
hashes=json.loads((base/'INPUT-HASHES.json').read_text());assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in hashes.items())
assert hashlib.sha256(data.read_bytes()).hexdigest()=='8c328146cfe6e1956256af63bb3b39cfc0d27be4b8ea7b796d842240056b5576'
p=ConditionalProposal(json.loads(data.read_text()));target=bs.StanModel(str(shim),data=data.read_text(),seed=1);names=target.param_names(include_tp=True,include_gq=False);ix=[names.index(n) for n in ['rho','alpha']+[f'f.{j}' for j in range(1,80)]]
c=counter_handle(shim);c.ow_reset_target_calls();rng=np.random.default_rng(seed);start=time.perf_counter();prob,scores=p.grid();q=np.empty((4096,81));values=np.empty((4096,160));lt=np.empty(4096);lq=np.empty(4096)
for i in range(4096):
    q[i],lq[i]=p.propose(rng,prob);lt[i]=target.log_density(q[i]);v=np.asarray(target.param_constrain(q[i],include_tp=True,include_gq=False))[ix];values[i]=np.r_[v,np.exp(v[2:])]
assert np.isfinite(q).all() and np.isfinite(values).all() and np.isfinite(lt).all() and np.isfinite(lq).all()
counts=counter_read(c);assert counts==dict(value=4096,gradient=0,hessian=0,hvp=0)
lw=lt-lq;w=np.exp(lw-logsumexp(lw));mean=w@values;sd=np.sqrt(w@((values-mean)**2));mcse=np.sqrt(np.sum((w[:,None]*(values-mean))**2,axis=0));_,pk=az.psislw(lw)
np.savez_compressed(out/'DRAWS.npz',q=q,values=values,log_target=lt,log_proposal=lq,log_weight=lw,weight=w)
np.savez_compressed(out/'GRID.npz',prob=prob,scores=scores)
result=dict(rep=rep,seed=seed,completed=True,seconds=time.perf_counter()-start,ess=float(1/(w@w)),pareto_k=float(pk),stats=dict(mean=mean.tolist(),sd=sd.tolist(),mcse=mcse.tolist()),counts=counts,proposal_counts=p.counts,scope='Accuracy awaits independently qualified reference; no timing or predictive claim')
assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in hashes.items())
(out/'SUMMARY.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({k:result[k] for k in ['rep','completed','ess','pareto_k','seconds']}),flush=True)
