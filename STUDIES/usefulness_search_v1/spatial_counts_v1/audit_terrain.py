"""Recompute the training control from raw proposals and independent density code."""
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.special import logsumexp,roots_hermitenorm
from scipy.stats import norm,poisson,multivariate_t
import arviz as az

base=Path(__file__).resolve().parent;root=base/'terrain_control01'
s=json.loads((root/'SUMMARY.json').read_text())
for name,digest in json.loads((root/'INPUT-HASHES.json').read_text()).items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest
supervision=json.loads((base/'terrain_supervision01/SUPERVISION.json').read_text())
assert supervision['status']=='exited' and supervision['exit_code']==0 and supervision['group_drained']
d=json.loads((base/'data01/GP-TRAIN.json').read_text());x=np.asarray(d['design']);y=np.asarray(d['y'])
mode=np.asarray(s['mode']);cov=np.asarray(s['covariance']);h=x.T@(d['exposure']*np.exp(x@mode)[:,None]*x)+np.diag(1/np.square(d['coef_scale']))
assert np.allclose(h@cov,np.eye(3),atol=1e-10,rtol=1e-10)

def target(b):
    return poisson.logpmf(y,d['exposure']*np.exp(b@x.T)).sum(1)+norm.logpdf(b,scale=d['coef_scale']).sum(1)

def collect(b,logw):
    w=np.exp(logw-logsumexp(logw));mu=np.zeros(403);v=np.zeros(403);se=np.zeros(403)
    for i in range(0,len(b),1024):
        z=b[i:i+1024];f=z@x.T;vals=np.column_stack([z,f,np.exp(f)])
        mu+=np.sum(w[i:i+1024,None]*vals,axis=0)
    for i in range(0,len(b),1024):
        z=b[i:i+1024];f=z@x.T;vals=np.column_stack([z,f,np.exp(f)])
        v+=np.sum(w[i:i+1024,None]*(vals-mu)**2,axis=0)
        se+=np.sum(w[i:i+1024,None]**2*(vals-mu)**2,axis=0)
    return mu,np.sqrt(v),np.sqrt(se),1/np.sum(w*w)

audits=[]
for row in s['importance']:
    a=np.load(root/f"IMPORTANCE-{row['seed']}.npz");b=a['beta'];raw=a['logweights'];assert b.shape==(65536,3)
    expected=multivariate_t(loc=mode,shape=2.25*cov,df=8).rvs(size=65536,random_state=np.random.default_rng(row['seed']))
    assert np.array_equal(b,expected)
    lw=np.concatenate([target(b[i:i+1024]) for i in range(0,len(b),1024)])-multivariate_t.logpdf(b,loc=mode,shape=2.25*cov,df=8)
    offset=lw-raw;assert np.ptp(offset)<1e-9
    mean,sd,se,ess=collect(b,lw)
    for name,values in [('mean',mean),('sd',sd),('mcse',se)]:assert np.allclose(values,row[name],rtol=1e-8,atol=1e-9),name
    _,k=az.psislw(lw);assert abs(k-row['pareto_k'])<1e-8 and abs(ess-row['ess'])<1e-6
    max_z=float(np.max(abs(mean-s['quadrature'][-1]['mean'])/se));max_mcse=float(np.max(se/sd))
    qualified=k<.7 and ess>=5000 and max_z<=4 and max_mcse<=.02
    assert bool(qualified)==row['passed']
    audits.append(dict(seed=row['seed'],qualified=bool(qualified),density_offset_spread=float(np.ptp(offset))))
# Independent Hermite convention and explicit normalized probability densities.
z,w=roots_hermitenorm(32);mesh=np.meshgrid(z,z,z,indexing='ij');q=np.stack(mesh,axis=-1).reshape(-1,3)
lw=sum(np.meshgrid(np.log(w),np.log(w),np.log(w),indexing='ij')).ravel()-1.5*np.log(2*np.pi)
b=mode+q@np.linalg.cholesky(cov).T
logq=-1.5*np.log(2*np.pi)-.5*np.linalg.slogdet(cov)[1]-.5*(q*q).sum(1)
weighted=lw+np.concatenate([target(b[i:i+1024]) for i in range(0,len(b),1024)])-logq
mean,sd,_,_=collect(b,weighted)
ref=s['quadrature'][-1]
mean_error=float(np.max(abs(mean-ref['mean'])/ref['sd']));sd_error=float(np.max(abs(sd-ref['sd'])/ref['sd']))
assert mean_error<1e-4 and sd_error<1e-4
assert s['passed'] and s['quadrature_passed'] and all(r['qualified'] for r in audits)
result=dict(passed=True,raw_proposals_verified=131072,importance=audits,quadrature_mean_sd_error=mean_error,
            quadrature_sd_relative_error=sd_error,scope='Training-only terrain control; heldout not opened',
            auditor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(base/'TERRAIN-AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
