import hashlib,json,time
from pathlib import Path
import numpy as np
from scipy.stats import multivariate_normal,multivariate_t
from conditional_proposal import ConditionalProposal
base=Path(__file__).resolve().parent;out=base/'proposal_preflight01';out.mkdir(exist_ok=False)
data=base/'data01/GP-TRAIN.json';p=ConditionalProposal(json.loads(data.read_text()));rng=np.random.default_rng(951300001);errors=[];grad=[];start=time.perf_counter()
for _ in range(16):
    h=np.log([rng.uniform(2,10),rng.uniform(.5,4)]);mode,C,L,_=p.solve(h);_,rate=p.objective(mode,L);grad.append(float(max(abs(L.T@(p.y-rate)-mode))))
    cov=np.linalg.inv(C@C.T);assert np.allclose((C@C.T)@cov,np.eye(p.d),rtol=1e-10,atol=1e-10)
    z=mode+np.linalg.solve(C.T,rng.normal(size=p.d))
    ref=np.logaddexp(np.log(.9)+multivariate_normal.logpdf(z,mean=mode,cov=cov),np.log(.1)+multivariate_t.logpdf(z,loc=mode,shape=2.25*cov,df=5));errors.append(abs(p.conditional_logq(z,mode,C)-ref))
assert max(grad)<1e-7 and max(errors)<1e-8
prob,scores=p.grid();assert abs(.95*prob.sum()+.05-1)<1e-12
for _ in range(64):
    q,lq=p.propose(rng,prob);assert q.shape==(81,) and np.isfinite(q).all() and np.isfinite(lq)
np.savez_compressed(out/'GRID.npz',prob=prob,scores=scores)
result=dict(passed=True,seconds=time.perf_counter()-start,max_gradient=max(grad),max_logq_error=max(errors),counts=p.counts,scope='Normalized proposal correctness only; exact-target importance accuracy untested',inputs={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),base/'conditional_proposal.py',base/'PROPOSAL-PREFLIGHT-PROTOCOL.md',data]})
(out/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
