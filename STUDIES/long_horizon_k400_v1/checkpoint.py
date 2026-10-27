"""Fixed checkpoint functionals; numerical evaluator is an unchanged injected dependency."""
import hashlib
import numpy as np
import arviz as az
from query_grid import query_grid
from scale_functional import evaluate_scale

def mean_mcse(a):
    a=np.asarray(a)
    if a.ndim!=2 or not np.isfinite(a).all():raise ValueError('finite chain/draw array required')
    value=0. if np.ptp(a)==0 else float(np.asarray(az.mcse(a,method='mean')).item())
    if not np.isfinite(value) or value<0:raise ValueError('unavailable mean MCSE')
    return value

def precision(score):
    density=score['density_mcse'];den=float(density['mean_scaled_density'])
    if not np.isfinite(den) or den<=0:raise ValueError('invalid density normalization')
    return dict(status='available',cdf_mcse=mean_mcse(score['pit_by_chain_draw']),logpdf_delta_mcse=mean_mcse(density['scaled_density'])/den)

def checkpoint(draws,window,label,tick,evaluator):
    out=dict(tick=tick,status='ok',queries=[],scale=None)
    try:grid=query_grid(window);out['grid']=grid
    except Exception as exc:grid=None;out.update(status='partial',grid_error=repr(exc))
    queries=[('grid',i,None) for i in range(5)] if grid is None else [('grid',i,x) for i,x in enumerate(grid['queries'])]
    queries.append(('observed_label',None,float(label)))
    for role,index,value in queries:
        row=dict(role=role,index=index,value=value,query_sha256=hashlib.sha256(np.float64(value).tobytes()).hexdigest() if value is not None else None,status='unavailable')
        try:
            if value is None:raise ValueError(out['grid_error'])
            score=evaluator(draws,value)
            if not np.isfinite([score['cdf'],score['logpdf']]).all() or not 0<=score['cdf']<=1:raise ValueError('invalid fixed-evaluator score')
            row.update(status='ok',forecast=score)
            try:row['precision']=precision(score)
            except Exception as exc:row['precision']=dict(status='unavailable',error=repr(exc));out['status']='partial'
        except Exception as exc:
            row['error']=repr(exc);row['numerical_failure']=getattr(exc,'diagnostics',None);out['status']='partial'
        out['queries'].append(row)
    if grid is None:
        out['unavailable_grid_queries']=list(range(5))
    try:out['scale']=dict(status='ok',**evaluate_scale(draws,mean_mcse))
    except Exception as exc:out['scale']=dict(status='unavailable',error=repr(exc));out['status']='partial'
    return out

def reference_reliability(draws,scored,divergences):
    variables={name:draws[:,:,i] for i,name in enumerate(('mu','log_sigma','beta','h_last'))};metrics={};globals_good=True;complete=sum(q['role']=='grid' for q in scored['queries'])==5;label_good=True
    for query in scored['queries']:
        key=str(query['role'])+'_'+str(query['index'])
        if query['status']!='ok':
            if query['role']=='grid':complete=False
            else:label_good=False
            continue
        score=query['forecast'];variables[key+'_cdf']=score['pit_by_chain_draw'];variables[key+'_density']=score['density_mcse']['scaled_density']
        p=query.get('precision') or {}
        if p.get('status')!='available' or p.get('cdf_mcse',float('inf'))>.005 or p.get('logpdf_delta_mcse',float('inf'))>.01:
            if query['role']=='grid':complete=False
            else:label_good=False
    for name,values in variables.items():
        try:
            v=dict(rhat=float(np.asarray(az.rhat(values)).item()),bulk_ess=float(np.asarray(az.ess(values,method='bulk')).item()),tail_ess=float(np.asarray(az.ess(values,method='tail')).item()))
            good=np.isfinite(list(v.values())).all() and v['rhat']<=1.01 and v['bulk_ess']>=1000 and v['tail_ess']>=1000;v['reliable']=bool(good)
            if not good:
                if name.startswith('observed_label'):label_good=False
                else:
                    complete=False
                    if name in ('mu','log_sigma','beta','h_last'):globals_good=False
        except Exception as exc:
            v=dict(reliable=False,error=repr(exc))
            if name.startswith('observed_label'):label_good=False
            else:
                complete=False
                if name in ('mu','log_sigma','beta','h_last'):globals_good=False
        metrics[name]=v
    return dict(reliable=bool(complete and sum(divergences)==0),observed_label_reliable=bool(label_good and globals_good and sum(divergences)==0),metrics=metrics,divergences=divergences,scope='Primary query CDF/density and global/endpoint reliability; secondary scale uncertainty reported separately')
