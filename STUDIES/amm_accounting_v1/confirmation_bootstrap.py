"""Paired circular-block means with bounded intermediate memory."""
import numpy as np

def circular_indices(starts,n,block):
    s=np.asarray(starts)
    if n<1 or not 1<=block<=n or s.ndim!=2 or s.shape[1]!=(n+block-1)//block:raise ValueError('Block shape')
    if not np.issubdtype(s.dtype,np.integer) or np.any((s<0)|(s>=n)):raise ValueError('Block start')
    return ((s[:,:,None]+np.arange(block))%n).reshape(len(s),-1)[:,:n]

def paired_means(scores,expected_n,block,seed,replicates=20000,chunk=64):
    x=np.asarray(scores,dtype=float)
    if x.ndim!=2 or x.shape[0]!=expected_n or not x.shape[1] or not np.isfinite(x).all():raise ValueError('Complete finite score matrix required')
    if type(block)is not int or not 1<=block<=expected_n:raise ValueError('Block length')
    if type(seed)is not int or seed<0 or replicates<1 or chunk<1:raise ValueError('Resampling settings')
    rng=np.random.Generator(np.random.PCG64(seed));out=np.empty((replicates,x.shape[1]))
    for lo in range(0,replicates,chunk):
        count=min(chunk,replicates-lo)
        starts=rng.integers(0,expected_n,size=(count,(expected_n+block-1)//block))
        ix=circular_indices(starts,expected_n,block)
        out[lo:lo+count]=x[ix].mean(axis=1)
    return out

def summarize(scores,expected_n,block,seed,replicates=20000):
    draws=paired_means(scores,expected_n,block,seed,replicates)
    return dict(mean=np.asarray(scores).mean(axis=0).tolist(),lower_9875=np.quantile(draws,.0125,axis=0,method='linear').tolist(),interval_95=np.quantile(draws,[.025,.975],axis=0,method='linear').T.tolist(),block=block,replicates=replicates,seed=seed,quantile_method='linear',rng='PCG64')
