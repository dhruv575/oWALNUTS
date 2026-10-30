import numpy as np
import mpmath as mp

def covariance_from_samples(positions,scores,gamma=0.):
    x=np.asarray(positions,dtype=float);y=np.asarray(scores,dtype=float)
    if x.ndim!=2 or y.shape!=x.shape or len(x)<2 or x.shape[1]<1 or not np.isfinite(x).all() or not np.isfinite(y).all() or not np.isfinite(gamma) or gamma<0:
        raise ValueError('invalid sample inputs')
    if gamma==0 and (np.linalg.matrix_rank(x-x.mean(0))<x.shape[1] or np.linalg.matrix_rank(y-y.mean(0))<x.shape[1]):
        raise ValueError('rank deficient sample factors')
    with mp.workdps(80):
        n,d=x.shape
        def cov(a):
            m=mp.matrix(a.tolist());means=[mp.fsum(m[i,j] for i in range(n))/n for j in range(d)]
            m=mp.matrix([[m[i,j]-means[j] for j in range(d)] for i in range(n)])
            return m.T*m/(n-1)+mp.mpf(float(gamma))*mp.eye(d)
        c=cov(x);g=cov(y);l=mp.cholesky(g);mp.cholesky(c)
        a=l.T*c*l;a=(a+a.T)/2;e,u=mp.eigsy(a)
        if min(e)<=0:raise ValueError('nonpositive transformed covariance')
        square=u*mp.diag([mp.sqrt(v) for v in e])*u.T;li=l**-1
        s=li.T*square*li
        result=np.asarray(s.tolist(),dtype=float);result=(result+result.T)/2
    if not np.isfinite(result).all():raise ValueError('nonfinite result')
    np.linalg.cholesky(result)
    return result
