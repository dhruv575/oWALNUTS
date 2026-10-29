"""Common Python callback path; timings are not native-engine speed claims."""
import time
import numpy as np
from scipy.optimize import minimize
from models import functional


def laplace(target,seed,draws=4000):
    start=time.monotonic()
    fit=minimize(lambda q:(-target(q)[0],-target(q)[1]),target.mean.copy(),jac=True,method='BFGS',options={'gtol':1e-6,'maxiter':500})
    if np.max(np.abs(target(fit.x)[1]))>1e-4:raise ValueError('MAP not stationary')
    h=1e-4;H=np.column_stack([-(target(fit.x+np.eye(target.dim)[i]*h)[1]-target(fit.x-np.eye(target.dim)[i]*h)[1])/(2*h) for i in range(target.dim)])
    H=(H+H.T)/2
    if np.linalg.eigvalsh(H).min()<=0:raise ValueError('Nonpositive Hessian')
    cov=np.linalg.inv(H);samples=np.random.default_rng(seed).multivariate_normal(fit.x,cov,draws)
    return samples,dict(status='ok',qualified=True,seconds=time.monotonic()-start,mean=fit.x.tolist(),covariance=cov.tolist(),qualification_scope='Optimizer and Hessian only; not posterior calibration')


def sample(target,method,seed,warmup,draws):
    import owalnuts
    start=time.monotonic()
    initial=np.tile(target.mean,(4,1))+np.random.default_rng(seed).normal(0,.15,(4,target.dim))
    if method=='walnuts':
        result=owalnuts.sample(target,dim=target.dim,init=initial,chains=4,warmup=warmup,draws=draws,seed=seed,threads=1,
            tuning=owalnuts.Tuning(max_depth=9),adaptation=owalnuts.Adaptation(target_accept=.9))
        samples=result.samples
        divergences=int(result.divergent[:,warmup:].sum());depth=int((result.depth[:,warmup:]>=9).sum())
    else:
        import nutpie
        from nutpie.compiled_pyfunc import from_pyfunc
        def make_logp():return target
        def make_expand(*args):return lambda q:{'x':np.array(q,dtype=float)}
        compiled=from_pyfunc(target.dim,make_logp,make_expand,[np.dtype('float64')],[(target.dim,)],['x'],
            make_initial_point_fn=lambda s:target.mean+np.random.default_rng(s).normal(0,.15,target.dim))
        data=nutpie.sample(compiled,chains=4,cores=1,tune=warmup,draws=draws,seed=seed,progress_bar=False,save_warmup=False,target_accept=.9,maxdepth=9,low_rank_modified_mass_matrix=False,transform_adapt=False)
        samples=np.asarray(data.posterior.x.values)
        divergences=int(data.sample_stats.diverging.sum());depth=int(data.sample_stats.maxdepth_reached.sum())
        data.close()
    elapsed=time.monotonic()-start;start=time.monotonic()
    if samples.shape!=(4,draws,target.dim) or not np.isfinite(samples).all():raise ValueError('Invalid draws')
    rows=owalnuts.summary(samples,[f'q{i}' for i in range(target.dim)])
    rhat=max(float(r['rhat']) for r in rows);ess=min(min(float(r['ess_bulk']),float(r['ess_tail'])) for r in rows)
    qualified=bool(np.isfinite(rhat) and np.isfinite(ess) and rhat<=1.05 and ess>=100 and divergences==0 and depth==0)
    return samples,dict(status='ok',qualified=qualified,strict_reference_qualified=bool(qualified and rhat<=1.01 and ess>=400),
        seconds=elapsed,diagnostic_seconds=time.monotonic()-start,rhat_max=rhat,ess_min=ess,divergences=divergences,depth_hits=depth,
        coordinate_summary=rows,warmup=warmup,draws=draws,chains=4,callback='Python callable for both engines')


def functional_summary(problem,samples,candidate):
    import owalnuts
    v=functional(problem,samples.reshape(-1,samples.shape[-1]),candidate)
    if candidate in ['hierarchical_ab','revenue_ab']:v=v[...,1]-v[...,0]
    v=v.reshape(samples.shape[0],samples.shape[1],-1)
    return owalnuts.summary(np.ascontiguousarray(v),[f'decision_functional_{i}' for i in range(v.shape[-1])])
