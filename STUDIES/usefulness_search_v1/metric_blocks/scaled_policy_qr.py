import time,traceback
import numpy as np
from selector_full_shape import select
from hybrid_gate import evaluate

POLICIES=['scaled','hybrid','v4','fisher','dense','auto']

def install(c):
    d=len(c);m=np.linalg.inv(c);m=(m+m.T)/2
    if not np.isfinite(m).all() or min(np.linalg.eigvalsh(m))<=0 or np.linalg.norm(c@m-np.eye(d))>1e-7:
        raise ValueError('unsafe metric installation')
    return m

def prepare(x,target,policy):
    assert policy in POLICIES
    if policy in ['dense','auto']:return dict(mode=policy,mass=None,calls=0,branch=policy)
    x=np.asarray(x);d=x.shape[-1];calls=0;detail={};fc=None;fm=None
    if policy in ['fisher','hybrid','scaled']:
        from fisher_qr_mp import covariance_from_samples
        flat=x.reshape(-1,d);scores=[]
        for q in flat:scores.append(target.log_density_gradient(q)[1]);calls+=1
        scores=np.asarray(scores);detail['scores']=scores.tolist()
        try:fc=covariance_from_samples(flat,scores);fm=install(fc)
        except Exception:
            detail['fisher_error']=traceback.format_exc()
            if policy=='fisher':raise
        if policy=='fisher':return dict(mode='fixed_dense',mass=fm.tolist(),calls=calls,branch='fisher',**detail)
        gate=evaluate(x,scores.reshape(x.shape));detail['gate']=gate
    coarse=[];fine=[]
    for chain in x:
        for q in chain[[0,24,49,99]]:
            matrices=[]
            for step in [1e-4,5e-5]:
                h=np.empty((d,d))
                for j in range(d):
                    delta=np.eye(d)[j]*step*(1+abs(q[j]))
                    _,gp=target.log_density_gradient(q+delta);calls+=1
                    _,gm=target.log_density_gradient(q-delta);calls+=1
                    h[:,j]=-(np.asarray(gp)-np.asarray(gm))/(2*delta[j])
                matrices.append(h)
            coarse.append(matrices[0]);fine.append(matrices[1])
    v=np.maximum(x.var(axis=1,ddof=1).mean(0),1e-8);bc,info=select(coarse,fine,v);bm=install(bc)
    detail.update(coarse=np.asarray(coarse).tolist(),fine=np.asarray(fine).tolist(),variances=v.tolist(),selection=info)
    branch='v4' if info['blocks'] else 'auto';mass=bm
    if policy in ['hybrid','scaled'] and detail['gate']['use_fisher'] and fm is not None:
        branch='fisher';mass=fm
    elif policy=='scaled' and info['blocks'] and fm is not None:
        try:
            corrected,ci=select(coarse,fine,np.diag(np.linalg.inv(fm)))
            if ci['blocks']!=info['blocks']:raise ValueError('scale repair changed selected blocks')
            mass=install(corrected);branch='scaled_block';detail['scaled_selection']=ci
        except Exception:detail['scale_error']=traceback.format_exc()
    return dict(mode='auto' if branch=='auto' else 'fixed_dense',mass=mass.tolist() if branch!='auto' else None,
        branch=branch,calls=calls,**detail)
