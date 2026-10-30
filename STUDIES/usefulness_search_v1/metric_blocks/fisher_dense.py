import numpy as np

def covariance_from_scores(position_covariance,score_covariance,gamma=0.):
    c=np.asarray(position_covariance,dtype=float);g=np.asarray(score_covariance,dtype=float)
    if c.ndim!=2 or c.shape!=g.shape or c.shape[0]!=c.shape[1] or not np.isfinite(c).all() or not np.isfinite(g).all() or not np.isfinite(gamma) or gamma<0:
        raise ValueError('invalid covariance inputs')
    c=(c+c.T)/2+gamma*np.eye(len(c));g=(g+g.T)/2+gamma*np.eye(len(g))
    np.linalg.cholesky(c);l=np.linalg.cholesky(g)
    a=l.T@c@l;a=(a+a.T)/2;e,u=np.linalg.eigh(a)
    if min(e)<=0:raise ValueError('nonpositive transformed covariance')
    square=(u*np.sqrt(e))@u.T;li=np.linalg.solve(l,np.eye(len(l)))
    s=li.T@square@li;s=(s+s.T)/2
    if not np.isfinite(s).all():raise ValueError('nonfinite result')
    np.linalg.cholesky(s)
    return s
