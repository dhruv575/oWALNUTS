import json,sys,time
from pathlib import Path
import numpy as np
from scipy.special import gammaln,logsumexp
import arviz as az
from native import Native,ROOT
from predictive import features,prediction,data
seed,out=sys.argv[1:];seed=int(seed);out=Path(out);out.mkdir(exist_ok=False);rng=np.random.default_rng(seed);p=json.loads((ROOT/'PREPARED.json').read_text());m=json.loads((ROOT/'MODES.json').read_text());mu0=np.array(p['mode']);L0=np.array(p['L']);mus=np.array(m['secondary_mode']);Ls=np.array(m['secondary_L']);d=43;df=5.;weights=np.array([.8,.1,.1]);b=Native();start=time.monotonic();fit=[]
mu=mu0.copy();L=L0.copy()
def sample(n):
 labels=rng.choice(3,size=n,p=weights);q=np.empty((n,d))
 for k,(center,scale) in enumerate([(mu,L),(mu0,1.5*L0),(mus,1.5*Ls)]):
  select=labels==k;z=rng.normal(size=(select.sum(),d))
  if k:z/=np.sqrt(rng.chisquare(df,size=(select.sum(),1))/df)
  q[select]=z@scale.T+center
 return q

def density(q):
 terms=[]
 for k,(center,scale) in enumerate([(mu,L),(mu0,1.5*L0),(mus,1.5*Ls)]):
  z=np.linalg.solve(scale,(q-center).T).T;r2=np.sum(z*z,axis=1);logdet=np.log(np.diag(scale)).sum()
  lp=-.5*r2-.5*d*np.log(2*np.pi)-logdet if k==0 else gammaln((df+d)/2)-gammaln(df/2)-.5*d*np.log(df*np.pi)-logdet-(df+d)/2*np.log1p(r2/df)
  terms.append(lp+np.log(weights[k]))
 return logsumexp(terms,axis=0)

def weighted(q):
 logw=np.array([b.density(x) for x in q])-density(q);logw-=logsumexp(logw);w=np.exp(logw);return logw,w
for iteration in range(2):
 q=sample(32768);logw,w=weighted(q);mu=w@q;z=np.linalg.solve(L0,(q-mu).T).T;cov=(z*w[:,None]).T@z;cov=.95*cov+.05*np.eye(d);ev,U=np.linalg.eigh(cov);cov=(U*np.clip(ev,.1,100))@U.T;L=np.linalg.cholesky(L0@cov@L0.T)
 fit.append(dict(iteration=iteration,ess=float(1/np.sum(w*w)),largest_weight=float(w.max()),mu=mu.tolist(),L=L.tolist()))
q=sample(262144);logw,w=weighted(q);_,k=az.psislw(logw);zero_weight_count=int(np.sum(w==0));positive=w>0;q=q[positive];w=w[positive];f=features(q);assert np.isfinite(f).all();mean=w@f;var=w@(f-mean)**2;mcse=np.sqrt((w*w)@((f-mean)**2)/(1-np.sum(w*w)))
def scores(q,w):
 logmu=prediction(q);obs=data()[-1].ravel();sigma=np.exp(q[:,-1,None]);loglik=-np.log(obs)-np.log(sigma)-.5*np.log(2*np.pi)-.5*((np.log(obs)-logmu)/sigma)**2
 with np.errstate(divide='ignore'):logw=np.log(w)
 return logsumexp(loglik+logw[:,None],axis=0).reshape(12,2).sum(axis=1).tolist()
ess=float(1/np.sum(w*w));importance=dict(mean=mean.tolist(),variance=var.tolist(),mcse=mcse.tolist(),ess=ess,pareto_k=float(k),largest_weight=float(w.max()),primary_mode_mass=float(w@(q[:,0]>q[:,1])),weight_gate=bool(ess>=1000 and k<.7),subject_log_scores=scores(q,w));del f,q
rng=np.random.default_rng(seed+100000);q=rng.normal(size=(262144,d))@L0.T+mu0;f=features(q);finite=np.isfinite(f).all(axis=0);safe=f[:,finite];means=np.full(68,np.nan);variances=means.copy();errors=means.copy();means[finite]=safe.mean(0);variances[finite]=safe.var(0,ddof=1);errors[finite]=safe.std(0,ddof=1)/np.sqrt(len(f));clean=lambda a:[float(v) if np.isfinite(v) else None for v in a];laplace=dict(mean=clean(means),variance=clean(variances),mcse=clean(errors),nonfinite_by_functional=np.sum(~np.isfinite(f),axis=0).tolist(),subject_log_scores=scores(q,np.full(len(q),1/len(q))))
r=dict(seed=seed,seconds=time.monotonic()-start,calls_errors=b.counts(),adaptation=fit,zero_weight_count=zero_weight_count,importance=importance,laplace=laplace,reference_compared=False);(out/'RESULT.json').write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');b.close();print(json.dumps(dict(seed=seed,seconds=r['seconds'],ess=ess,k=float(k),weight_gate=importance['weight_gate'])))
