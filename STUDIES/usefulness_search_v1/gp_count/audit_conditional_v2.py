import json,time
import numpy as np
from scipy.special import logsumexp
from scipy.stats import multivariate_normal,multivariate_t
from common import Target,ROOT
from conditional_v2 import *
b=Target();rng=np.random.default_rng(944000001);offset=[];grad=[];qerr=[];start=time.monotonic()
for _ in range(40):
 h=np.log([rng.uniform(2,10),rng.uniform(.5,4)]);z=rng.normal(size=D);L=kernel(h);v,_=objective(z,L);offset.append(b.value(np.r_[h,z])-(prior(h)+v));mode,C,L,v=solve(h);grad.append(float(np.max(np.abs(b.gradient(np.r_[h,mode])[1][2:]))));cov=np.linalg.inv(C@C.T);q=mode+np.linalg.solve(C.T,rng.normal(size=D))
 expected=np.logaddexp(np.log(.9)+multivariate_normal.logpdf(q,mean=mode,cov=cov),np.log(.1)+multivariate_t.logpdf(q,loc=mode,shape=2.25*cov,df=5));qerr.append(abs(conditional_logq(q,mode,C)-expected))
print(json.dumps(dict(offset=offset,gradient=grad,proposal_error=qerr)));raise SystemExit(0)
scores=np.empty((41,41))
for i in range(41):
 for j in range(41):
  h=LO+(np.array([i,j])+.5)*WIDTH;z,C,L,v=solve(h);scores[i,j]=prior(h)+v-np.log(np.diag(C)).sum()
prob=np.exp(scores-logsumexp(scores));assert abs(prob.sum()-1)<1e-12
np.savez_compressed(ROOT/'conditional-grid.npz',prob=prob,scores=scores,lo=LO,hi=HI)
r=dict(passed=True,seconds=time.monotonic()-start,offset_spread=float(np.ptp(offset)),latent_gradient_max=max(grad),proposal_log_error=max(qerr),counts=COUNTS,stan_calls=b.counts(),grid_cells=1681,hyperproposal_integral=.95*float(prob.sum())+.05)
(ROOT/'CONDITIONAL-PREFLIGHT.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
