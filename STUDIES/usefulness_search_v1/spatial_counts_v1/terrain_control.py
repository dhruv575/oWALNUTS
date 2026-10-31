"""Independent low-dimensional control; never opens heldout outcomes."""
import hashlib
import importlib.metadata
import json
import time
from pathlib import Path
import numpy as np
import arviz as az
from scipy.optimize import minimize
from scipy.special import logsumexp
from scipy.stats import multivariate_t
from numpy.polynomial.hermite import hermgauss

base=Path(__file__).resolve().parent
out=base/'terrain_control01'
out.mkdir(exist_ok=False)
paths=[Path(__file__),base/'TERRAIN-CONTROL-PROTOCOL.md',base/'data01/GP-TRAIN.json']
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
(out/'INPUT-HASHES.json').write_text(json.dumps(hashes,indent=2))
start=time.perf_counter()
d=json.loads((base/'data01/GP-TRAIN.json').read_text())
x=np.asarray(d['design']);y=np.asarray(d['y']);exposure=d['exposure']
precision=1/np.square(d['coef_scale'])
assert x.shape==(200,3) and y.sum()==712 and exposure==.2

def objective(beta):
    f=x@beta;mu=exposure*np.exp(f)
    value=mu.sum()-y@f+.5*np.sum(beta*beta*precision)
    gradient=x.T@(mu-y)+precision*beta
    hessian=(x.T*mu)@x+np.diag(precision)
    return value,gradient,hessian

mode_result=minimize(lambda b:objective(b)[0],np.array([np.log(y.mean()/exposure),0.,0.]),
                     jac=lambda b:objective(b)[1],hess=lambda b:objective(b)[2],
                     method='trust-exact',options={'gtol':1e-8,'maxiter':100})
mode=mode_result.x;value,gradient,hessian=objective(mode)
assert np.max(abs(gradient))<=1e-5 and np.min(np.linalg.eigvalsh(hessian))>0
cov=np.linalg.inv(hessian);chol=np.linalg.cholesky(cov)
derivatives=[]
for b in [mode,mode+np.array([.1,-.1,.05]),mode+np.array([-.2,.05,-.1])]:
    v,g,h=objective(b);eps=1e-5;basis=np.eye(3)*eps
    fd=np.array([(objective(b+e)[0]-objective(b-e)[0])/(2*eps) for e in basis])
    fh=np.column_stack([(objective(b+e)[1]-objective(b-e)[1])/(2*eps) for e in basis])
    ge=float(np.max(abs(fd-g)/np.maximum(1,abs(g))));he=float(np.max(abs(fh-h)/np.maximum(1,abs(h))))
    assert ge<=1e-5 and he<=1e-5
    derivatives.append(dict(gradient=ge,hessian=he))

def logtarget(beta):
    f=beta@x.T
    return f@y-exposure*np.exp(f).sum(1)-.5*(beta*beta*precision).sum(1)

def functionals(beta):
    f=beta@x.T
    return np.concatenate([beta,f,np.exp(f)],axis=1)

def moments(beta,logweights):
    weights=np.exp(logweights-logsumexp(logweights))
    mean=np.zeros(403);second=np.zeros(403)
    for lo in range(0,len(beta),2048):
        f=functionals(beta[lo:lo+2048]);w=weights[lo:lo+2048]
        mean+=w@f;second+=w@(f*f)
    variance=second-mean*mean
    assert np.min(variance)>0 and np.isfinite(mean).all()
    sd=np.sqrt(variance);mcse2=np.zeros(403)
    for lo in range(0,len(beta),2048):
        f=functionals(beta[lo:lo+2048]);w=weights[lo:lo+2048]
        mcse2+=(w*w)@((f-mean)**2)
    return mean,sd,np.sqrt(mcse2),float(1/np.sum(weights**2))

def target_batches(beta):
    return np.concatenate([logtarget(beta[i:i+2048]) for i in range(0,len(beta),2048)])

quadrature=[]
for order in [16,24,32,48]:
    nodes,weights=hermgauss(order)
    mesh=np.meshgrid(nodes,nodes,nodes,indexing='ij');z=np.stack(mesh,axis=-1).reshape(-1,3)*np.sqrt(2)
    meshw=np.meshgrid(np.log(weights),np.log(weights),np.log(weights),indexing='ij')
    logw=sum(meshw).ravel()-1.5*np.log(np.pi)
    beta=mode+z@chol.T
    logq=-1.5*np.log(2*np.pi)-np.log(np.diag(chol)).sum()-.5*(z*z).sum(1)
    corrected=logw+target_batches(beta)-logq
    mean,sd,_,_=moments(beta,corrected)
    quadrature.append(dict(order=order,log_normalizer=float(logsumexp(corrected)),mean=mean.tolist(),sd=sd.tolist()))
    print(json.dumps(dict(event='quadrature',order=order)),flush=True)
reference=quadrature[-1];previous=quadrature[-2]
refmean=np.array(reference['mean']);refsd=np.array(reference['sd'])
convergence=dict(log_normalizer=abs(reference['log_normalizer']-previous['log_normalizer']),
                 max_mean_sd=float(np.max(abs(refmean-previous['mean'])/refsd)),
                 max_relative_sd=float(np.max(abs(refsd-previous['sd'])/refsd)))
quadrature_passed=convergence['log_normalizer']<=1e-6 and convergence['max_mean_sd']<=1e-4 and convergence['max_relative_sd']<=1e-4
importance=[]
for seed in [952300001,952300002]:
    proposal=multivariate_t(loc=mode,shape=2.25*cov,df=8)
    beta=proposal.rvs(size=65536,random_state=np.random.default_rng(seed))
    lw=target_batches(beta)-proposal.logpdf(beta)
    _,k=az.psislw(lw)
    mean,sd,mcse,ess=moments(beta,lw)
    max_mcse=float(np.max(mcse/sd));max_z=float(np.max(abs(mean-refmean)/mcse))
    passed=float(k)<.7 and ess>=5000 and max_mcse<=.02 and max_z<=4
    np.savez_compressed(out/f'IMPORTANCE-{seed}.npz',beta=beta,logweights=lw)
    importance.append(dict(seed=seed,pareto_k=float(k),ess=ess,max_mcse_sd=max_mcse,max_z=max_z,
                           passed=bool(passed),mean=mean.tolist(),sd=sd.tolist(),mcse=mcse.tolist()))
laplace_mean=np.r_[mode,x@mode,np.exp(x@mode+.5*np.einsum('ij,jk,ik->i',x,cov,x))]
fv=np.einsum('ij,jk,ik->i',x,cov,x)
laplace_sd=np.r_[np.sqrt(np.diag(cov)),np.sqrt(fv),np.sqrt(np.expm1(fv)*np.exp(2*x@mode+fv))]
assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in hashes.items())
result=dict(passed=bool(quadrature_passed and all(i['passed'] for i in importance)),
            scope='Training-only terrain model; no heldout scores or spatial GP fidelity claim',
            seconds=time.perf_counter()-start,versions={n:importlib.metadata.version(n) for n in ['numpy','scipy','arviz']},
            mode=mode.tolist(),mode_gradient_max=float(np.max(abs(gradient))),covariance=cov.tolist(),
            derivative_checks=derivatives,quadrature=quadrature,convergence=convergence,
            quadrature_passed=bool(quadrature_passed),importance=importance,
            laplace_max_mean_sd=float(np.max(abs(laplace_mean-refmean)/refsd)),
            laplace_max_relative_sd=float(np.max(abs(laplace_sd-refsd)/refsd)))
(out/'SUMMARY.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:result[k] for k in ['passed','seconds','convergence','laplace_max_mean_sd','laplace_max_relative_sd']}),flush=True)
