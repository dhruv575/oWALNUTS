"""Symmetric SV reporting; exact declared gates and nested predictive RNG order."""
import math
import numpy as np
import arviz as az


def terminal_path(draws,model):
    """Loop over scheduled time, vectorize independent chain/draw paths.

    Scalar math.exp and each small dot product deliberately match Target.path.
    Arrays are not modified. Missing observations do not remove transitions.
    """
    q=np.asarray(draws,dtype=np.float64)
    if q.ndim!=3 or q.shape[-1]!=model.dimension or not np.isfinite(q).all():
        raise ValueError('Finite chain/draw/exact-dimension array required')
    mu=q[...,0];sigma=np.fromiter((math.exp(x) for x in q[...,1].flat),float,count=mu.size).reshape(mu.shape)
    gamma=q[...,2+model.p:model.offset];z=q[...,model.offset:]
    # np.matmul invokes the same dot primitive separately for each small vector.
    forcing=lambda i:np.matmul(model.w[i],gamma[...,None])[...,0]
    h=mu+forcing(0)+sigma*z[...,0]/math.sqrt(1-model.rho**2)
    for i in range(1,model.t):h=mu+model.rho*(h-mu)+forcing(i)+sigma*z[...,i]
    return h


def diagnostics(a):
    if a.ndim==3:
        rows=[diagnostics(a[:,:,j]) for j in range(a.shape[-1])]
        return dict(rhat=max(v['rhat'] for v in rows),bulk_ess=min(v['bulk_ess'] for v in rows),tail_ess=min(v['tail_ess'] for v in rows),all_parameters=rows,all_finite=all(v['all_finite'] for v in rows))
    row=dict(rhat=float(az.rhat(a,method='rank')),bulk_ess=float(az.ess(a,method='bulk')),tail_ess=float(az.ess(a,method='tail',prob=(.05,.95))))
    row['all_finite']=all(np.isfinite(v) for v in row.values());return row


def summarize(q,model,future,*,predictive_seed=6501):
    q=np.asarray(q,dtype=float);m=model
    h=terminal_path(q,m);mu=q[:,:,0];sig=np.exp(q[:,:,1]);rng=np.random.default_rng(predictive_seed)
    x=np.asarray(future['x'],dtype=float);w=np.asarray(future['w'],dtype=float)
    if x.shape!=(m.p,) or w.shape!=(m.k,) or not np.isfinite(x).all() or not np.isfinite(w).all():raise ValueError('Exact finite scenario covariates required')
    futureh=mu+m.rho*(h-mu)+q[:,:,2+m.p:m.offset]@w+sig*rng.normal(size=h.shape)
    pred=q[:,:,2:2+m.p]@x+np.exp(futureh/2)*rng.standard_t(m.nu,size=h.shape)
    values={'mu':mu,'sigma':sig,'h_terminal':h,'next_observed':pred}
    for i in range(m.p):values['beta_'+str(i)]=q[:,:,2+i]
    for i in range(m.k):values['gamma_'+str(i)]=q[:,:,2+m.p+i]
    rows={}
    for name,a in values.items():
        interval=np.quantile(a,[.05,.95]);mc=[float(az.mcse(a,method='quantile',prob=p)) for p in [.05,.95]]
        rows[name]=dict(interval=interval,endpoint_mcse=mc,ratio=max(mc)/(interval[1]-interval[0]),**diagnostics(a))
    health=diagnostics(q);healthy=health['all_finite'] and health['rhat']<=1.01 and health['bulk_ess']>=400 and health['tail_ess']>=400
    passed=healthy and all(v['all_finite'] and np.isfinite(v['interval']).all() and np.isfinite(v['endpoint_mcse']).all() and np.isfinite(v['ratio']) and v['rhat']<=1.01 and v['bulk_ess']>=400 and v['tail_ess']>=400 and v['ratio']<=.02 for v in rows.values())
    return dict(canonical=health,functionals=rows,healthy=healthy,precision_pass=passed)
