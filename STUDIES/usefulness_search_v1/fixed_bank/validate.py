import json,time
from pathlib import Path
import numpy as np
from scipy.special import logsumexp
from scipy.stats import multivariate_t,norm
from bank import FixedBank
root=Path(__file__).resolve().parent;rng=np.random.default_rng(942000000);errors=[];flux=[];t=time.monotonic()
for d in [1,3,12]:
 centers=rng.normal(size=(3,d));L=np.array([np.linalg.cholesky((a:=rng.normal(size=(d,d)))@a.T+np.eye(d)) for _ in range(3)]);w=np.array([.2,.3,.5]);bank=FixedBank(centers,L,w)
 for _ in range(100):
  x=rng.normal(size=d);y=rng.normal(size=d);expected=logsumexp([np.log(w[j])+multivariate_t.logpdf(y,loc=centers[j],shape=L[j]@L[j].T,df=5) for j in range(3)])
  errors.append(abs(bank.logq(y)-expected));a=-.5*x@x;b=-.5*y@y;qx=bank.logq(x);qy=bank.logq(y);r=b-a+qx-qy;flux.append(abs(a+qy+min(0,r)-(b+qx+min(0,-r))))
assert max(errors)<=1e-10 and max(flux)<=1e-10
bank=FixedBank([[-8.],[8.]],np.ones((2,1,1)),[.5,.5]);n=12000;component=rng.random((n,4,1))<.8;x=np.where(component,-8,8)+np.where(component,2.,.2)*rng.normal(size=(n,4,1));before=x.copy();after=np.empty_like(x)
def logp(q):return float(np.logaddexp(np.log(.8/2)-.5*((q[0]+8)/2)**2,np.log(.2/.2)-.5*((q[0]-8)/.2)**2))
for i in range(n):after[i],_=bank.sweep(x[i],logp,rng)
assert np.array_equal(x,before);rows=[]
for phase,v in [('before',x),('after',after)]:
 for name,a,truth in [('mean',v[:,:,0].mean(1),-4.8),('second',(v[:,:,0]**2).mean(1),67.208),('positive',(v[:,:,0]>0).mean(1),.8*norm.sf(4)+.2*norm.sf(-40)),('cross',(v[:,0,0]+4.8)*(v[:,1,0]+4.8),0.)]:
  se=float(a.std(ddof=1)/np.sqrt(n));z=float((a.mean()-truth)/se);rows.append(dict(phase=phase,name=name,mean=float(a.mean()),truth=truth,se=se,z=z));assert abs(z)<=4.5
for centers,L,w,df in [([],[],[],5),([[0]],[[[0]]],[1],5),([[0]],[[[1]]],[0],5),([[0]],[[[1]]],[1],0)]:
 try:FixedBank(centers,L,w,df)
 except ValueError:pass
 else:raise AssertionError('Invalid configuration accepted')
y,m=bank.sweep(np.zeros((4,1)),lambda q:0. if q[0]==0 else -np.inf,rng);assert not y.any() and m['invalid']==4
try:bank.sweep(np.zeros((4,1)),lambda q:-np.inf,rng)
except ValueError:pass
else:raise AssertionError('Invalid current density accepted')
r=dict(passed=True,seconds=time.monotonic()-t,max_density_error=max(errors),max_flux_error=max(flux),stationarity=rows);(root/'VALIDATION.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
