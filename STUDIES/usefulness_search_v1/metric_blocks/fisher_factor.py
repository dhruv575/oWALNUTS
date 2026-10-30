"""Existing Fisher estimator, evaluated from centered sample factors."""
import numpy as np

def covariance_from_samples(positions,scores,gamma=0.):
    x=np.asarray(positions,dtype=float);y=np.asarray(scores,dtype=float)
    if x.ndim!=2 or y.shape!=x.shape or len(x)<2 or x.shape[1]<1 or not np.isfinite(x).all() or not np.isfinite(y).all() or not np.isfinite(gamma) or gamma<0:
        raise ValueError('invalid sample inputs')
    a=(x-x.mean(0))/np.sqrt(len(x)-1);b=(y-y.mean(0))/np.sqrt(len(y)-1)
    if gamma:
        a=np.vstack([a,np.sqrt(gamma)*np.eye(x.shape[1])]);b=np.vstack([b,np.sqrt(gamma)*np.eye(x.shape[1])])
    if np.linalg.matrix_rank(a)<x.shape[1] or np.linalg.matrix_rank(b)<x.shape[1]:
        raise ValueError('rank deficient sample factors')
    _,r=np.linalg.qr(a,mode='reduced');_,t=np.linalg.qr(b,mode='reduced')
    # C=R'R, G=T'T. Polar factor of R T' avoids squaring its condition.
    u,s,vt=np.linalg.svd(r@t.T)
    if min(s)<=0:raise ValueError('nonpositive cross factor singular value')
    # S=R' U V' T^-T; right solve via transposition.
    metric=np.linalg.solve(t,(r.T@u@vt).T).T
    metric=(metric+metric.T)/2
    if not np.isfinite(metric).all():raise ValueError('nonfinite metric')
    np.linalg.cholesky(metric)
    return metric
