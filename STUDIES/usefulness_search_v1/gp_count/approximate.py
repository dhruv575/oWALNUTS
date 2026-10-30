import json,sys,time
from pathlib import Path
import numpy as np,arviz as az
from scipy.special import logsumexp
from scipy.stats import multivariate_normal,multivariate_t
from common import Target,ROOT
seed=int(sys.argv[1]);out=Path(sys.argv[2]);p=json.loads((ROOT/'PREPARED.json').read_text());ref=json.loads((ROOT/'REFERENCE.json').read_text());mu=np.array(p['mode']);L=np.array(p['L']);cov=np.array(p['cov']);n=32768;d=13;b=Target();t=time.monotonic();rows=[];rngs=[np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(2)]
for arm,rng in zip(['laplace','importance'],rngs):
 start=time.monotonic();q=mu+rng.normal(size=(n,d))@L.T
 if arm=='importance':
  component=rng.random(n)<.5;qt=mu+1.5*(rng.normal(size=(n,d))@L.T)/np.sqrt(rng.chisquare(5,size=n)/5)[:,None];q[component]=qt[component]
  lq=np.logaddexp(multivariate_normal.logpdf(q,mean=mu,cov=cov),multivariate_t.logpdf(q,loc=mu,shape=2.25*cov,df=5))-np.log(2)
  lp=np.array([b.value(x) for x in q]);lw=lp-lq;assert np.isfinite(lw).any() and not np.isnan(lw).any();w=np.exp(lw-logsumexp(lw));_,k=az.psislw(lw);ess=float(1/np.sum(w*w))
 else:lw=np.zeros(n);w=np.full(n,1/n);k=None;ess=float(n)
 a=np.zeros((n,24));active=w>0
 for i in np.flatnonzero(active):a[i]=b.transform(q[i])
 assert np.isfinite(a[active]).all()
 mean=w@a;sd=np.sqrt(w@((a-mean)**2));mcse=np.sqrt((w*w)@((a-mean)**2));rmean=np.array(ref['stats']['mean']);rsd=np.array(ref['stats']['sd']);rmcse=np.array(ref['stats']['mcse']);err=np.abs(mean-rmean)/rsd;serr=np.abs(sd/rsd-1);z=np.abs(mean-rmean)/np.sqrt(mcse**2+rmcse**2)
 checks=dict(ess=ess>=400,pareto_k=k is None or float(k)<.7,mean_error=float(err.max())<=.1,sd_error=float(serr.max())<=.2,combined_mcse=float(z.max())<=4)
 r=dict(arm=arm,seed=seed,n=n,ess=ess,pareto_k=None if k is None else float(k),mean=mean.tolist(),sd=sd.tolist(),mcse=mcse.tolist(),mean_error_sd=err.tolist(),relative_sd_error=serr.tolist(),combined_z=z.tolist(),checks=checks,passed=all(checks.values()),seconds=time.monotonic()-start,zero_weight_rows=int((~active).sum()))
 np.savez_compressed(out/(arm+'.npz'),q=q,values=a,weight=w,log_weight=lw);rows.append(r)
(out/'RESULT.json').write_text(json.dumps(dict(rows=rows,calls=b.counts(),seconds=time.monotonic()-t),indent=2,allow_nan=False)+'\n');print(json.dumps([dict(arm=r['arm'],passed=r['passed'],ess=r['ess'],k=r['pareto_k'],max_mean_error=max(r['mean_error_sd']),max_sd_error=max(r['relative_sd_error']),max_z=max(r['combined_z'])) for r in rows]))
