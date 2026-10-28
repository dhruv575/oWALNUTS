"""Deterministic initialization heuristic, never a new posterior draw."""
import numpy as np

def physical_path(q,rho=.95):
    q=np.asarray(q,dtype=float)
    if q.shape!=(253,) or not np.isfinite(q).all() or not abs(rho)<1:raise ValueError('Finite T250 state and stationary rho required')
    sigma=np.exp(q[1])
    if not np.isfinite(sigma) or sigma<=0:raise ValueError('Finite positive innovation scale')
    h=np.empty(250);h[0]=q[0]+sigma*q[3]/np.sqrt(1-rho*rho)
    for i in range(1,250):h[i]=q[0]+rho*(h[i-1]-q[0])+sigma*q[3+i]
    if not np.isfinite(h).all():raise ValueError('Finite path required')
    return h

def remap(q,rho=.95):
    q=np.asarray(q,dtype=float);h=physical_path(q,rho);result=q.copy();sigma=np.exp(q[1])
    shifted=np.r_[h[1:],q[0]+rho*(h[-1]-q[0])]
    result[3]=np.sqrt(1-rho*rho)*(shifted[0]-q[0])/sigma
    result[4:]=(shifted[1:]-q[0]-rho*(shifted[:-1]-q[0]))/sigma
    return result

def initialization_center(last_states):
    last_states=np.asarray(last_states,dtype=float)
    if last_states.shape!=(4,253):raise ValueError('Four terminal chain states required')
    mapped=np.stack([remap(q) for q in last_states])
    return mapped.mean(axis=0),mapped
