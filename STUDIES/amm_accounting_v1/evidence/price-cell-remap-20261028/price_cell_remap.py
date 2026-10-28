"""One-cell warm initialization transport, not posterior transport."""
import numpy as np


def shift(positions,mass,steps,old_lower,old_upper,new_lower,new_upper,rho=.95):
    """Return owned arrays; mixed/appended coordinates use unit diagonal mass.

    Price endpoints must share an unchanged coordinate origin. The caller must
    supply one common, explicit initial price when compiling the new target.
    """
    q=np.asarray(positions,dtype=float);m=np.asarray(mass,dtype=float);s=np.asarray(steps,dtype=float)
    cells=[np.asarray(a,dtype=float) for a in (old_lower,old_upper,new_lower,new_upper)]
    lo,hi,nlo,nhi=cells
    if lo.ndim!=1 or len(lo)<2 or any(a.shape!=lo.shape for a in cells):raise ValueError('At least two cells, identical shapes')
    n=len(lo)
    if any(not np.isfinite(a).all() for a in cells) or not np.all(hi>lo) or not np.all(nhi>nlo):raise ValueError('Finite positive cells')
    if not np.array_equal(lo[1:],nlo[:-1]) or not np.array_equal(hi[1:],nhi[:-1]):raise ValueError('Overlapping cells must agree exactly')
    if q.ndim!=2 or q.shape[0]<1 or q.shape[1]!=3+2*n or m.shape!=q.shape or s.shape!=(q.shape[0],):raise ValueError('State shape')
    if not np.isfinite(q).all() or not np.isfinite(m).all() or not np.all(m>0) or not np.isfinite(s).all() or not np.all(s>0):raise ValueError('Finite state and positive metric/steps')
    if not np.isfinite(rho) or not -1<rho<1:raise ValueError('Stationary rho')
    result=np.zeros_like(q);metric=np.ones_like(m)
    result[:,:3]=q[:,:3];metric[:,:3]=m[:,:3]
    result[:,3]=rho*q[:,3]+np.sqrt(1-rho*rho)*q[:,4]
    result[:,4:3+n-1]=q[:,5:3+n];metric[:,4:3+n-1]=m[:,5:3+n]
    result[:,3+n:-1]=q[:,4+n:];metric[:,3+n:-1]=m[:,4+n:]
    if not np.isfinite(result).all():raise ValueError('Nonfinite remap')
    return result,metric,s.copy()
