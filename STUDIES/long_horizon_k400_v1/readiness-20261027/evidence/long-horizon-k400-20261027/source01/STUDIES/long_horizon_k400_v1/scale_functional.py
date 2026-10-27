"""Predictive-scale analytic CDF inversion reused from warm_precision_diagnostic_v1.
Only adapts the explicit joint[mu,log_sigma,beta,h_last] columns to[0,1,3].
No posterior generation, no simulated future innovation, no qualification rule.
"""
import math,time
import numpy as np
import arviz as az
from scipy.optimize import brentq
from scipy.special import ndtr
PS=(.5,.95)

def analytic(a):
    start=time.perf_counter()
    m=a[...,0]+.95*(a[...,2]-a[...,0]);sd=np.exp(a[...,1])
    if not np.isfinite(sd).all() or (sd<=0).any():raise ValueError('invalid conditional scale')
    lo,hi=float(np.min(m-12*sd)),float(np.max(m+12*sd));roots=[];residuals=[]
    for p in PS:
        f=lambda h:float(ndtr((h-m)/sd).mean())-p
        if not f(lo)<0<f(hi):raise ValueError('invalid CDF bracket')
        h=brentq(f,lo,hi,xtol=1e-12,rtol=1e-12,maxiter=100);residual=abs(f(h))
        if residual>1e-9:raise ValueError('CDF inversion residual too large')
        roots.append(float(h));residuals.append(float(residual))
    q=np.exp(np.array(roots)/2)
    if not np.isfinite(q).all() or (q<=0).any():raise ValueError('invalid analytic quantile')
    return dict(quantiles=q.tolist(),roots=roots,residuals=residuals,bracket=[lo,hi],arithmetic_seconds=time.perf_counter()-start)

def evaluate_scale(joint,mean_mcse=None):
    joint=np.asarray(joint)
    if joint.ndim!=3 or joint.shape[0]!=4 or joint.shape[2]!=4 or not np.isfinite(joint).all():raise ValueError('four-chain full joint compact required')
    a=joint[:,:,[0,1,3]]
    result=analytic(a);m=a[...,0]+.95*(a[...,2]-a[...,0]);sd=np.exp(a[...,1]);mcse=[];cdfs=[]
    if mean_mcse is None:mean_mcse=lambda v:0. if np.ptp(v)==0 else float(np.asarray(az.mcse(v,method='mean')).item())
    for h,q in zip(result['roots'],result['quantiles']):
        z=(h-m)/sd;f_scale=float(np.mean(2*np.exp(-z*z/2)/(np.sqrt(2*np.pi)*q*sd)))
        if f_scale<=0 or not np.isfinite(f_scale):raise ValueError('invalid mixture density')
        cdf=ndtr(z);value=float(mean_mcse(cdf))/(q*f_scale)
        if not np.isfinite(value) or value<0:raise ValueError('invalid scale MCSE')
        mcse.append(value);cdfs.append(cdf)
    result.update(probabilities=list(PS),joint_columns=[0,1,3],relative_mcse=mcse,cdf_by_chain_draw=np.stack(cdfs,axis=-1))
    return result
