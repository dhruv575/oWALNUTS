"""Prototype bounded-downside integration; not yet admitted for empirical use."""
import time
import numpy as np
from scipy.integrate import quad_vec
COST=.0005
ABS_TOL=1e-8
TAIL_BOUND=1e-10
A=float(np.log(1/TAIL_BOUND))

def realized_downside(r):
    r=np.asarray(r,dtype=float)
    if not np.isfinite(r).all():raise ValueError('Finite realized returns required')
    # Never exponentiate positive returns; their positive long downside is zero.
    return np.where(r<0,-np.expm1(np.minimum(r,0)),0.)

def action(mean):
    if not np.isfinite(mean) or not 0<=mean<=1:raise ValueError('Bounded forecast mean required')
    return 'convert' if mean>COST else 'retain'

def score(mean,r):
    y=float(realized_downside(r));a=action(mean)
    return dict(realized_downside=y,squared_error=(mean-y)**2,action=a,decision_cost=COST if a=='convert' else y,always_retain_cost=y,always_convert_cost=COST)

def split_points(beta,log_scale):
    """Fixed parameter-only landmarks, including a geometric layer near zero."""
    beta=np.asarray(beta);log_scale=np.asarray(log_scale)
    if not np.isfinite(beta).all() or not np.isfinite(log_scale).all():raise ValueError('Finite split parameters required')
    center=float(np.median(beta));scale=float(np.exp(np.clip(np.median(log_scale),-700,700)))
    candidates=list(np.quantile(beta,[0,.1,.5,.9,1]))
    negatives=beta[beta<0]
    if len(negatives):candidates.append(float(negatives.max()))
    candidates += [center+sign*factor*scale for sign in (-1,1) for factor in (.1,1.,10.)]
    candidates += [-A*10.**(-k) for k in range(1,11)]
    return sorted(set(float(x) for x in candidates if -A<x<0))

def integrate_cdf_components(cdf,points,deadline,*,epsabs=ABS_TOL,limit=512):
    evaluations=0
    def integrand(r):
        nonlocal evaluations
        if time.perf_counter()>=deadline:raise TimeoutError('Bounded integral deadline')
        evaluations+=1;values=np.asarray(cdf(r),dtype=float)
        if not np.isfinite(values).all() or np.any((values<0)|(values>1)):raise ValueError('Invalid CDF contributions')
        return np.exp(r)*values
    value,error,info=quad_vec(integrand,-A,0,epsabs=epsabs,epsrel=0,norm='max',cache_size=32*1024**2,limit=limit,workers=1,points=points,quadrature='gk21',full_output=True)
    if not info.success or not np.isfinite(error) or error>epsabs:raise ValueError('Outer integration failed its estimated-error check')
    value=np.asarray(value,dtype=float)
    if not np.isfinite(value).all() or np.any((value<0)|(value>1)):raise ValueError('Integrated loss outside bounded domain')
    return value,dict(cdf_evaluations=evaluations,estimated_max_component_error=float(error),omitted_tail_bound=TAIL_BOUND,intervals=len(info.intervals),status=int(info.status),split_points=list(points),error_interpretation='Only omitted-tail bound is rigorous; adaptive error estimate is not a full predictive certificate')

def evaluate(draws,backend_module,deadline):
    started=time.perf_counter();a=np.asarray(draws,dtype=float)
    if a.ndim!=3 or a.shape[0]!=4 or a.shape[2]!=4 or not np.isfinite(a).all():raise ValueError('Four-chain finite compact draws required')
    shape=a.shape[:2];flat=a.reshape(-1,4);m=flat[:,0]+.95*(flat[:,3]-flat[:,0]);sigma=np.exp(flat[:,1]);beta=flat[:,2]
    points=split_points(beta,m/2);backend=backend_module.Backend('exact_t5');rules={};values={}
    for nodes in (64,128):
        cdf=backend_module.ConfiguredReturnCDF(m,sigma,beta,5,nodes,deadline,64*1024**2,chunk=512,backend=backend)
        def per_draw(r):
            chunks=[]
            for lo in range(0,len(m),cdf.chunk):
                cdf.budget();hi=min(lo+cdf.chunk,len(m));inv=cdf.cache.get(lo)
                if inv is None:inv=cdf.inverse_scales(lo,hi)
                with np.errstate(over='raise',invalid='raise'):z=(r-beta[lo:hi,None])*inv
                chunks.append(backend.cdf(5,z)@cdf.weights)
            return np.concatenate(chunks)
        value,diagnostics=integrate_cdf_components(per_draw,points,deadline);values[nodes]=value;rules[str(nodes)]=diagnostics
    difference=abs(float(values[64].mean()-values[128].mean()))
    if difference>ABS_TOL:raise ValueError('GH64/128 bounded-mean disagreement')
    mean=float(values[128].mean());actions={str(n):action(float(values[n].mean())) for n in (64,128)}
    return dict(status='ok',mean_downside=mean,per_chain_draw_downside=values[128].reshape(shape),numerical=dict(rules=rules,gh_mean_discrepancy=difference,max_component_gh_discrepancy=float(np.max(np.abs(values[64]-values[128]))),rule_actions=actions,action_disagreement=len(set(actions.values()))>1,estimated_threshold_ambiguity=abs(mean-COST)<=max(v['estimated_max_component_error'] for v in rules.values())+TAIL_BOUND+difference),seconds=time.perf_counter()-started)

def baseline(fit,backend,deadline):
    if fit.get('status')!='ok':raise ValueError('Original fit unavailable')
    loc=float(fit['location']);scale=float(fit['scale'])
    if fit['df']!=5 or not np.isfinite([loc,scale]).all() or scale<=0:raise ValueError('Invalid saved t5 fit')
    points=split_points(np.array([loc]),np.array([np.log(scale)]))
    value,diagnostics=integrate_cdf_components(lambda r:backend.cdf(5,np.array([(r-loc)/scale])),points,deadline)
    mean=float(value[0]);return dict(status='ok',mean_downside=mean,numerical=dict(rule=diagnostics,estimated_threshold_ambiguity=abs(mean-COST)<=diagnostics['estimated_max_component_error']+TAIL_BOUND))

def precision(values):
    import arviz as az
    values=np.asarray(values)
    if values.ndim!=2 or values.shape[0]!=4 or not np.isfinite(values).all() or np.any((values<0)|(values>1)):raise ValueError('Invalid chain functional values')
    mcse=0. if np.ptp(values)==0 else float(np.asarray(az.mcse(values,method='mean')).item())
    if not np.isfinite(mcse) or mcse<0:raise ValueError('Unavailable bounded-mean MCSE')
    return dict(status='available',mean_mcse=mcse,chain_means=values.mean(axis=1).tolist(),interpretation='Chain-aware MCSE of mean bounded-loss functional; descriptive, not a gate')
