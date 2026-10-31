import hashlib
import json
import time
from pathlib import Path
import numpy as np
from scipy.special import gammaln
from scipy.stats import poisson
base=Path(__file__).resolve().parent
out=base/'cheap_controls01';out.mkdir(exist_ok=False)
paths=[Path(__file__),base/'CHEAP-CONTROLS-PROTOCOL.md',base/'data01/GP-TRAIN.json']
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
started=time.perf_counter()
d=json.loads((base/'data01/GP-TRAIN.json').read_text());y=np.array(d['y']);x=np.array(d['x']);e=d['exposure']
assert y.shape==(200,) and y.sum()==712 and e==.2
folds=np.random.default_rng(952400001).multinomial(y,np.full(5,.2)).T
assert folds.shape==(5,200) and np.array_equal(folds.sum(0),y)

def log_predict(y,a,b,exposure):
    return gammaln(a+y)-gammaln(a)-gammaln(y+1)+a*np.log(b/(b+exposure))+y*np.log(exposure/(b+exposure))

for a,b,exposure in [(1.,1.,.8),(.5,.025,.04),(20.,2.,.8)]:
    k=np.arange(10000);prob=np.exp(log_predict(k,a,b,exposure));mean=exposure*a/b;var=mean*(1+exposure/b)
    assert abs(prob.sum()-1)<1e-10 and abs(prob@k-mean)<1e-8 and abs(prob@((k-mean)**2)-var)<1e-7

distance2=np.sum((x[:,None,:]-x[None,:,:])**2,axis=2)
kernel_grid=[]
for bandwidth in [.25,.5,1.,2.,4.,8.]:
    k=np.exp(-distance2/(2*bandwidth**2));k/=k.sum(1,keepdims=True)
    assert np.allclose(k@np.full(200,7.),7.,rtol=1e-13,atol=1e-13)
    scores=[]
    for validation in folds:
        train=y-validation;rate=k@train/(e*.8)
        assert np.isfinite(rate).all() and (rate>0).all()
        scores.append(float(poisson.logpmf(validation,e*.2*rate).sum()))
    kernel_grid.append(dict(bandwidth=bandwidth,fold_scores=scores,score=sum(scores)))
selected=max(kernel_grid,key=lambda r:(r['score'],r['bandwidth']))
k=np.exp(-distance2/(2*selected['bandwidth']**2));k/=k.sum(1,keepdims=True)
kernel_rate=k@y/e
shrinkage_grid=[]
for alpha in [.1,.25,.5,1.,2.,4.,8.,16.,32.,64.,128.,256.,1000000.]:
    scores=[]
    for validation in folds:
        train=y-validation;mean=train.mean()/(e*.8);prior_rate=alpha/mean
        scores.append(float(log_predict(validation,alpha+train,prior_rate+e*.8,e*.2).sum()))
    shrinkage_grid.append(dict(alpha=alpha,fold_scores=scores,score=sum(scores)))
chosen=max(shrinkage_grid,key=lambda r:(r['score'],r['alpha']))
alpha=chosen['alpha'];mean=y.mean()/e
result=dict(passed=True,scope='Training-selected controls only; no heldout scores',seconds=time.perf_counter()-started,
            seed=952400001,fold_counts=folds.tolist(),kernel_grid=kernel_grid,shrinkage_grid=shrinkage_grid,
            kernel=dict(bandwidth=selected['bandwidth'],rate=kernel_rate.tolist(),uncertainty='Plug-in Poisson'),
            empirical_bayes=dict(alpha=alpha,prior_mean=float(mean),shape=(alpha+y).tolist(),rate=float(alpha/mean+e),
                                 uncertainty='Conditional on training-estimated hyperparameters'),
            fixed_cell=dict(shape=(y+.5).tolist(),rate=e+.025),
            homogeneous=dict(shape=float(y.sum()+.5),rate=float(len(y)*e+.025)),inputs=hashes)
assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in hashes.items())
(out/'SUMMARY.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps(dict(passed=True,bandwidth=selected['bandwidth'],alpha=alpha,seconds=result['seconds'])),flush=True)
