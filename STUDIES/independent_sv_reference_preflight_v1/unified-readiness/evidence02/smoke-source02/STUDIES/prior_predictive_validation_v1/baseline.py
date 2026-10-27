"""Matched-information exact NIG lag-return baseline, no fitting on future labels."""
import numpy as np
from scipy.stats import t

def score(window,label):
    y=np.asarray(window,dtype=float)
    if y.shape!=(250,) or not np.isfinite(y).all() or not np.isfinite(label):raise ValueError('finite250-window/label required')
    lag=y[:-1];target=y[1:];center=lag.mean();sd=lag.std();sd=sd if sd>1e-12 else 1.
    X=np.column_stack((np.ones(249),(lag-center)/sd));x=np.array([1.,(y[-1]-center)/sd])
    V=np.linalg.solve(np.eye(2)/100+X.T@X,np.eye(2));m=V@X.T@target
    a=3+249/2;b=.0002+.5*(np.sum((target-X@m)**2)+m@m/100)
    location=float(x@m);scale=float(np.sqrt((b/a)*(1+x@V@x)));df=2*a
    return dict(cdf=float(t.cdf(label,df,loc=location,scale=scale)),logpdf=float(t.logpdf(label,df,loc=location,scale=scale)),location=location,scale=scale,df=df,training_pairs=249)
