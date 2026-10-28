"""Tail-only wrapper over the byte-pinned existing full predictive CDF."""
import time
import numpy as np
from scipy.optimize import brentq
from scipy.special import stdtrit
PS=(.05,.95)

def roots(cdf):
    center=float(np.median(cdf.beta));width=max(float(np.exp(np.median(cdf.m)/2)),float(np.std(cdf.beta)),1e-10)
    for expansion in range(61):
        lo,hi=center-width,center+width
        if not np.isfinite([lo,hi]).all():raise ValueError('Quantile bracket overflow')
        if cdf(lo)<.05 and cdf(hi)>.95:break
        width*=2
    else:raise ValueError('Failed to bracket predictive tails')
    q=[brentq(lambda x:cdf(x)-p,lo,hi,xtol=1e-12,rtol=1e-12,maxiter=100) for p in PS]
    residual=[abs(cdf(x)-p) for x,p in zip(q,PS)]
    if max(residual)>1e-8 or not q[0]<q[1]:raise ValueError('Tail root residual/order failure')
    return dict(probabilities=list(PS),quantiles=q,residuals=residual,bracket=[lo,hi],bracket_expansions=expansion,cdf_evaluations=cdf.calls,student_t_evaluations=cdf.student_t_evaluations,cached_bytes=cdf.cached_bytes)

def tails(draws,backend_module,deadline):
    started=time.perf_counter();a=np.asarray(draws,dtype=float)
    if a.ndim!=3 or a.shape[0]!=4 or a.shape[2]!=4 or not np.isfinite(a).all():raise ValueError('Finite four-chain compact draws required')
    a=a.reshape(-1,4);sigma=np.exp(a[:,1]);m=a[:,0]+.95*(a[:,3]-a[:,0])
    backend=backend_module.Backend('exact_t5')
    cdfs=[backend_module.ConfiguredReturnCDF(m,sigma,a[:,2],5,n,deadline,64*1024**2,chunk=512,backend=backend) for n in [64,128]]
    rules=[roots(cdf) for cdf in cdfs];q=rules[1]['quantiles'];width=q[1]-q[0]
    if not np.isfinite(width) or width<=0:raise ValueError('Invalid predictive interval width')
    cross=max(abs(cdfs[0](x)-p) for x,p in zip(q,PS));endpoint=max(abs(x-y)/width for x,y in zip(rules[0]['quantiles'],q))
    numerical=dict(rules=rules,cross_cdf_discrepancy=cross,normalized_endpoint_difference=endpoint,backend=backend.metadata)
    if cross>1e-6 or endpoint>1e-6:
        error=ValueError('GH64/128 tail disagreement');error.diagnostics=numerical;raise error
    return dict(status='ok',q05=q[0],q95=q[1],width=width,numerical=numerical,quantile_seconds=time.perf_counter()-started)

def baseline(fit):
    if fit.get('status')!='ok':raise ValueError('Original baseline fit unavailable')
    loc=float(fit['location']);scale=float(fit['scale']);df=float(fit['df'])
    if not np.isfinite([loc,scale,df]).all() or scale<=0 or df!=5:raise ValueError('Invalid original t5 parameters')
    q=loc+scale*stdtrit(5,np.array(PS))
    if not np.isfinite(q).all() or not q[0]<q[1]:raise ValueError('Invalid baseline tails')
    return dict(status='ok',q05=float(q[0]),q95=float(q[1]),width=float(q[1]-q[0]))

def score(quantiles,y):
    if not np.isfinite(y):raise ValueError('Finite original next-return label required')
    low,high=quantiles['q05'],quantiles['q95']
    result={}
    for side,loss,limit in [('long',-y,-low),('short',y,high)]:
        residual=loss-limit;pinball=(.95-float(residual<0))*residual
        if not np.isfinite([limit,pinball]).all() or pinball<0:raise ValueError('Invalid realized risk score')
        result[side]=dict(limit=limit,pinball=pinball,exceedance=int(loss>limit))
    return result

def precision(draws,quantiles,density_module,deadline):
    import arviz as az
    out={}
    for name,q in [('long',quantiles['q05']),('short',quantiles['q95'])]:
        try:
            remaining=deadline-time.perf_counter()
            if remaining<=0:raise TimeoutError('Tail precision deadline')
            v=density_module.evaluate_observation(draws,q,rho=.95,nu=5,orders=(64,128),chunk=512,deadline=time.monotonic()+remaining)
            contributions=v['pit_by_chain_draw'];mcse=0. if np.ptp(contributions)==0 else float(np.asarray(az.mcse(contributions,method='mean')).item());density=float(np.exp(v['logpdf']))
            if not np.isfinite([mcse,density]).all() or mcse<0 or density<=0 or not np.isfinite(mcse/density):raise ValueError('Unavailable quantile precision')
            out[name]=dict(status='available',cdf_mcse=mcse,density_at_root=density,quantile_delta_mcse=mcse/density,cdf_at_root=v['pit'],cdf_by_chain=contributions.mean(axis=1).tolist())
        except Exception as error:out[name]=dict(status='unavailable',error=type(error).__name__,reason=str(error))
    available=sum(v['status']=='available' for v in out.values())
    return dict(status='available' if available==2 else 'partial' if available else 'unavailable',tails=out)
