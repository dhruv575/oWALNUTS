import numpy as np
from scipy.special import ndtr,logsumexp
import owalnuts

def features(q,pred,threshold):
    sigma=np.exp(q[:,-1]);exceed=ndtr((pred[:,-2:]-np.log(threshold))/sigma[:,None])
    return np.column_stack([q,pred,exceed])

def summarize(values,div=0,depth=0,min_ess=400):
    rows=owalnuts.summary(np.ascontiguousarray(values),[f'f{i}' for i in range(values.shape[-1])])
    mean=values.mean(axis=(0,1));sd=values.reshape(-1,values.shape[-1]).std(axis=0)
    rh=np.array([r['rhat'] for r in rows]);es=np.array([[r['ess_bulk'],r['ess_tail']] for r in rows]);mc=np.array([r['mcse_mean'] for r in rows])
    valid=bool(np.isfinite(rh).all() and np.isfinite(es).all() and np.isfinite(mc).all())
    def finite(v):return float(v) if np.isfinite(v) else None
    return dict(mean=mean.tolist(),sd=sd.tolist(),mcse=[finite(x) for x in mc],rhat_max=finite(rh.max()),ess_min=finite(es.min()),diagnostic_pass=bool(valid and rh.max()<=1.01 and es.min()>=min_ess and div==0 and depth==0),divergences=div,depth_hits=depth)

def predictions(b,q):
    flat=q.reshape(-1,q.shape[-1]);return np.array([b.predict(x) for x in flat]).reshape(*q.shape[:2],-1)

def heldout(q,pred,obs):
    if not obs:return None
    sigma=np.exp(q[:,:,-1]).reshape(-1);mu=pred[:,:,-len(obs):].reshape(-1,len(obs));y=np.asarray(obs)
    lp=-np.log(y)[None,:]-np.log(sigma)[:,None]-.5*np.log(2*np.pi)-.5*((np.log(y)[None,:]-mu)/sigma[:,None])**2
    return dict(log_predictive_density=(logsumexp(lp,axis=0)-np.log(len(lp))).tolist())
