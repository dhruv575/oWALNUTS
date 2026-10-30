"""Exact conjugate controls; importing this module never reads holdout labels."""
import numpy as np
from scipy.special import gammaln,logsumexp

def log_evidence(counts):
 y=np.asarray(counts,dtype=float);assert np.isfinite(y).all() and np.all(y>=0) and np.all(y==np.floor(y));n=len(y);s=float(y.sum())
 return float(gammaln(1+s)-(1+s)*np.log1p(n)-gammaln(y+1).sum())

def predictive_logpmf(k,shape,rate,exposure=1.):
 k=np.asarray(k);assert np.all(k>=0) and shape>0 and rate>0 and exposure>0
 return gammaln(shape+k)-gammaln(shape)-gammaln(k+1)+shape*np.log(rate/(rate+exposure))+k*np.log(exposure/(rate+exposure))

def fit_controls(rows):
 observed=[r for r in rows if r['count'] is not None];years=np.asarray([r['year'] for r in observed]);y=np.asarray([r['count'] for r in observed]);assert len(set(r['year'] for r in rows))==len(rows)
 constant=dict(shape=1+int(y.sum()),rate=1+len(y),log_evidence=log_evidence(y))
 switches=np.arange(min(r['year'] for r in rows),max(r['year'] for r in rows)+1);parts=[]
 for year in switches:
  early=y[years<=year];late=y[years>year];parts.append(dict(year=int(year),early_shape=1+int(early.sum()),early_rate=1+len(early),late_shape=1+int(late.sum()),late_rate=1+len(late),log_evidence=log_evidence(early)+log_evidence(late)))
 logw=np.asarray([r['log_evidence'] for r in parts])-np.log(len(parts));evidence=float(logsumexp(logw));w=np.exp(logw-evidence);assert abs(w.sum()-1)<1e-12
 for row,weight in zip(parts,w):row['probability']=float(weight)
 return dict(constant=constant,changepoint=dict(log_evidence=evidence,components=parts),training_observed=len(y))
