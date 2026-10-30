"""Existing Fisher estimator from float64 QR factors and small MP matrices."""
import numpy as np
import mpmath as mp

def covariance_from_samples(positions,scores,gamma=0.):
    x=np.asarray(positions,dtype=float);y=np.asarray(scores,dtype=float)
    if x.ndim!=2 or y.shape!=x.shape or len(x)<2 or x.shape[1]<1 or not np.isfinite(x).all() or not np.isfinite(y).all() or not np.isfinite(gamma) or gamma<0:
        raise ValueError('invalid sample inputs')
    a=(x-x.mean(0))/np.sqrt(len(x)-1);b=(y-y.mean(0))/np.sqrt(len(y)-1)
    if gamma:
        a=np.vstack([a,np.sqrt(gamma)*np.eye(x.shape[1])]);b=np.vstack([b,np.sqrt(gamma)*np.eye(x.shape[1])])
    if np.linalg.matrix_rank(a)<x.shape[1] or np.linalg.matrix_rank(b)<x.shape[1]:raise ValueError('rank deficient sample factors')
    _,r=np.linalg.qr(a,mode='reduced');_,t=np.linalg.qr(b,mode='reduced')
    with mp.workdps(80):
        r=mp.matrix(r.tolist());t=mp.matrix(t.tolist());c=r.T*r;g=t.T*t
        l=mp.cholesky(g);mp.cholesky(c);a=l.T*c*l;a=(a+a.T)/2
        e,u=mp.eigsy(a)
        if min(e)<=0:raise ValueError('nonpositive transformed covariance')
        square=u*mp.diag([mp.sqrt(v) for v in e])*u.T;li=l**-1;s=li.T*square*li
        result=np.asarray(s.tolist(),dtype=float);result=(result+result.T)/2
    if not np.isfinite(result).all():raise ValueError('nonfinite result')
    np.linalg.cholesky(result)
    return result
