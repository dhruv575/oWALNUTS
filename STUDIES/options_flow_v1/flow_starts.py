"""Canonical flow starts and exact coordinate conversion shared by reference workers."""
import numpy as np

def canonical_starts(data,chains):
    t,g=np.asarray(data['y']).shape
    if isinstance(chains,bool) or not isinstance(chains,(int,np.integer)) or chains<1:
        raise ValueError('chains must be a positive integer')
    if 'initial_positions' in data and data['initial_positions'] is not None:
        starts=np.asarray(data['initial_positions'],dtype=float)
        if starts.shape!=(chains,4+2*g+t) or not np.isfinite(starts).all():
            raise ValueError('initial_positions must be a finite canonical chain-by-dimension matrix matching chains')
        return starts.copy()
    return np.tile(np.r_[0.,-1.,-1.,-1.5,np.zeros(2*g),np.full(t,-1.)],(chains,1))

def to_noncentered(q,data):
    q=np.array(q,dtype=float,copy=True);g=len(data['y'][0]);k=4+2*g
    h=q[...,k:].copy();mu=q[...,2:3];sig=np.exp(q[...,3:4]);rho=data['rho']
    q[...,k:k+1]=(h[...,:1]-mu)*np.sqrt(1-rho*rho)/sig
    q[...,k+1:]=(h[...,1:]-mu-rho*(h[...,:-1]-mu))/sig
    return q
