"""Optional chunked parameter quantiles; unchanged scalar fallbacks and RNG.

No default analyze routing. Caller supplies original random.Random multiplicities.
"""
import math
import numpy as np
from reference_bank import cached_parameter


def batch_cached_parameter(fits,cache,length,name,p,multiplicities,chunk_size=512):
    if type(chunk_size)!=int or chunk_size<1 or not 0<p<1:raise ValueError('Invalid batch quantile policy')
    ordered,candidates=cache[(length,name)];ids=[f['id'] for f in fits]
    sizes=[len(ordered[k]) for k in ids]
    if not sizes or not min(sizes):raise ValueError('Empty fit draws')
    for counts in multiplicities:
        values=[counts.get(k,0) for k in ids]
        if any(type(v)!=int or v<0 for v in values) or not sum(values) or sum(values)*max(sizes)>np.iinfo(np.int64).max:raise ValueError('Invalid or overflowing integer multiplicities')
    # Preserve math.fsum/tolerance semantics for heterogeneous fit sizes.
    if len(set(sizes))!=1:return [cached_parameter(fits,cache,length,name,p,c) for c in multiplicities]
    n=sizes[0];values=np.asarray(candidates);arrays=[np.asarray(ordered[k]) for k in ids];result=[]
    for start in range(0,len(multiplicities),chunk_size):
        rows=multiplicities[start:start+chunk_size]
        raw_counts=[[c.get(k,0) for k in ids] for c in rows]
        if any(type(v)!=int or v<0 for row in raw_counts for v in row):raise ValueError('Integer nonnegative multiplicities required')
        if any(sum(row)*n>np.iinfo(np.int64).max for row in raw_counts):raise ValueError('Integer cumulative mass overflow')
        counts=np.asarray(raw_counts,dtype=np.int64)
        if np.any(counts<0):raise ValueError('Negative multiplicity')
        totals=counts.sum(axis=1)
        if np.any(totals<=0):raise ValueError('Empty bootstrap mass')
        if int(totals.max())>np.iinfo(np.int64).max//n:raise ValueError('Integer cumulative mass overflow')
        thresholds=np.asarray([(p*int(total)-8*math.ulp(int(total)))*n for total in totals])
        lo=np.zeros(len(rows),dtype=np.int64);hi=np.full(len(rows),len(values)-1,dtype=np.int64)
        while np.any(lo<hi):
            mid=(lo+hi)//2;query=values[mid];mass=np.zeros(len(rows),dtype=np.int64)
            for j,array in enumerate(arrays):mass+=counts[:,j]*np.searchsorted(array,query,side='right')
            choose=mass>=thresholds;active=lo<hi
            hi=np.where(active&choose,mid,hi);lo=np.where(active&~choose,mid+1,lo)
        # Near an integer threshold the scalar sum of rounded divisions and its
        # tolerance could differ from integer arithmetic. Preserve exact legacy
        # semantics by falling back for those rows (not changing the convention).
        near=np.abs(thresholds-np.rint(thresholds))<=64*np.finfo(float).eps*np.maximum(1.,np.abs(thresholds))
        result.extend(cached_parameter(fits,cache,length,name,p,c) if near[i] else float(values[lo[i]]) for i,c in enumerate(rows))
    return result


