import numpy as np
from scipy.linalg import solve_sylvester
from fisher_factor import covariance_from_samples as initial_estimate

def covariance_from_samples(positions,scores,gamma=0.):
    s=initial_estimate(positions,scores,gamma)
    x=np.asarray(positions,dtype=float);y=np.asarray(scores,dtype=float)
    a=(x-x.mean(0))/np.sqrt(len(x)-1);b=(y-y.mean(0))/np.sqrt(len(y)-1)
    if gamma:
        a=np.vstack([a,np.sqrt(gamma)*np.eye(x.shape[1])]);b=np.vstack([b,np.sqrt(gamma)*np.eye(x.shape[1])])
    c=a.T@a;g=b.T@b
    for _ in range(5):
        bs=b@s;res=c-bs.T@bs
        delta=solve_sylvester(bs.T@b,b.T@bs,res);delta=(delta+delta.T)/2
        candidate=(s+delta);candidate=(candidate+candidate.T)/2
        np.linalg.cholesky(candidate)
        old=np.linalg.norm(res);new=np.linalg.norm(c-(b@candidate).T@(b@candidate))
        if new>=old:break
        s=candidate
    return s
