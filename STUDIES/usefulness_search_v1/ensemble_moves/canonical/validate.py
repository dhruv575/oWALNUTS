import json,time
from pathlib import Path
import numpy as np
from scipy.stats import multivariate_t,norm
from scipy.special import logsumexp
from move import EnsembleMove
root=Path(__file__).resolve().parent;rng=np.random.default_rng(940000001);start=time.monotonic();errors=[];flux=[]
for d in [1,3,12]:
 factors=np.array([np.linalg.cholesky((A:=rng.normal(size=(d,d)))@A.T+np.eye(d)) for _ in range(4)]);move=EnsembleMove(factors)
 for _ in range(30):
  x=rng.normal(size=(4,d));y=rng.normal(size=d)
  for i in range(4):
   expected=logsumexp([multivariate_t.logpdf(y,loc=x[j],shape=factors[j]@factors[j].T,df=5) for j in range(4) if j!=i])-np.log(3)
   errors.append(abs(move.logq(y,x,i)-expected));a=-.5*np.sum(x[i]**2);b=-.5*np.sum(y*y);qy=move.logq(y,x,i);qx=move.logq(x[i],x,i);ratio=b-a+qx-qy
   flux.append(abs((a+qy+min(0,ratio))-(b+qx+min(0,-ratio))))
assert max(errors)<1e-10 and max(flux)<1e-10
checks=[]
for target,d in [('normal',3),('unequal_mixture',1)]:
 n=12000
 if target=='normal':
  x=rng.normal(size=(n,4,d));logp=lambda q:float(-.5*np.sum(q*q));mu=0.;second=1.;prob=.5
 else:
  component=rng.random((n,4,1))<.8;x=np.where(component,-8.,8.)+np.where(component,2.,.2)*rng.normal(size=(n,4,1));logp=lambda q:float(np.logaddexp(np.log(.8)-np.log(2.)-.5*((q[0]+8)/2)**2,np.log(.2)-np.log(.2)-.5*((q[0]-8)/.2)**2));mu=-4.8;second=.8*(64+4)+.2*(64+.04);prob=.8*norm.sf(4)+.2*norm.sf(-40)
 factors=np.array([np.eye(d)*s for s in [.3,.8,1.7,3.] ]);move=EnsembleMove(factors);original=x.copy();updated=np.empty_like(x);accepted=0
 for k in range(n):updated[k],meta=move.sweep(x[k],logp,rng);accepted+=sum(meta['accepted'])
 assert np.array_equal(x,original) and np.array_equal(move.L,factors)
 for phase,a in [('before',x),('after',updated)]:
  values=[a[:,:,0].mean(1),(a[:,:,0]**2).mean(1),(a[:,:,0]>0).mean(1),(a[:,0,0]-mu)*(a[:,1,0]-mu)]
  for name,v,truth in zip(['mean','second_moment','positive_mass','cross_walker_covariance'],values,[mu,second,prob,0.]):
   se=float(v.std(ddof=1)/np.sqrt(n));estimate=float(v.mean());z=(estimate-truth)/se;checks.append(dict(target=target,phase=phase,functional=name,estimate=estimate,truth=truth,se=se,z=z));assert abs(z)<=4.5,(target,phase,name,z)
for factors,df in [(np.zeros((4,2,2)),5),(np.ones((1,1,1)),5),(np.ones((4,1,1)),0)]:
 try:EnsembleMove(factors,df)
 except ValueError:pass
 else:raise AssertionError('Bad configuration accepted')
m=EnsembleMove(np.ones((4,1,1)))
for x,fn in [(np.full((4,1),np.nan),lambda q:0.),(np.zeros((4,1)),lambda q:-np.inf)]:
 try:m.sweep(x,fn,rng)
 except ValueError:pass
 else:raise AssertionError('Bad current state accepted')
x=np.zeros((4,1));y,meta=m.sweep(x,lambda q:0. if q[0]==0 else -np.inf,rng);assert np.array_equal(x,y) and meta['invalid']==4 and not any(meta['accepted'])
r=dict(passed=True,seconds=time.monotonic()-start,max_log_density_error=max(errors),max_flux_error=max(flux),stationarity=checks);(root/'VALIDATION.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
