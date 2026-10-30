import json,sys,time
from pathlib import Path
import numpy as np,arviz as az
from scipy.special import logsumexp
from common import Target,ROOT
from conditional import propose,COUNTS
seed=int(sys.argv[1]);out=Path(sys.argv[2]);rng=np.random.default_rng(seed);b=Target();prob=np.load(ROOT/'conditional-grid.npz')['prob'];ref=json.loads((ROOT/'REFERENCE.json').read_text());n=16384;q=np.empty((n,13));lq=np.empty(n);lp=np.empty(n);start=time.monotonic()
for i in range(n):
 q[i],lq[i]=propose(rng,prob);lp[i]=b.value(q[i])
 if i%1024==1023:(out/'PROGRESS.json').write_text(json.dumps(dict(draws=i+1,seconds=time.monotonic()-start,counts=COUNTS))+'\n')
lw=lp-lq;assert np.isfinite(lw).any() and not np.isnan(lw).any();w=np.exp(lw-logsumexp(lw));_,k=az.psislw(lw);ess=float(1/np.sum(w*w));a=np.array([b.transform(v) for v in q]);active=w>0;assert np.isfinite(a[active]).all();aa=a[active];ww=w[active];mean=ww@aa;sd=np.sqrt(ww@((aa-mean)**2));mcse=np.sqrt(np.sum((ww[:,None]*(aa-mean))**2,axis=0));rm=np.array(ref['stats']['mean']);rs=np.array(ref['stats']['sd']);rc=np.array(ref['stats']['mcse']);err=np.abs(mean-rm)/rs;serr=np.abs(sd/rs-1);z=np.abs(mean-rm)/np.sqrt(mcse**2+rc**2)
raw=a.mean(0);raw_valid=bool(np.isfinite(raw).all());checks=dict(ess=ess>=400,pareto_k=float(k)<.7,mean_error=float(err.max())<=.1,sd_error=float(serr.max())<=.2,combined_mcse=float(z.max())<=4)
r=dict(seed=seed,n=n,seconds=time.monotonic()-start,counts=COUNTS,stan_calls=b.counts(),ess=ess,pareto_k=float(k),mean=mean.tolist(),sd=sd.tolist(),mcse=mcse.tolist(),mean_error_sd=err.tolist(),relative_sd_error=serr.tolist(),combined_z=z.tolist(),checks=checks,passed=all(checks.values()),uncorrected_proposal_mean=raw.tolist() if raw_valid else None,uncorrected_mean_finite=raw_valid,zero_weight_rows=int((~active).sum()))
np.savez_compressed(out/'draws.npz',q=q,values=a,weight=w,log_weight=lw,log_proposal=lq,log_target=lp);(out/'RESULT.json').write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');print(json.dumps({key:r[key] for key in ['seed','seconds','counts','stan_calls','ess','pareto_k','checks','passed']}))
