"""Causal indexing, physical reconstruction and score-decomposition invariants."""
import numpy as np

def cell(index):
    if type(index)is not int or not 0<=index<72:raise ValueError('Fixed cell index')
    return index//3,[.5,1.,2.][index%3],398141000+16*index

def physical_draws(samples,cap,rho=.95):
    s=np.asarray(samples,dtype=float)
    if s.ndim!=3 or s.shape[2]<4 or not np.isfinite(s).all():raise ValueError('Finite chain/draw/coordinate arrays')
    l=np.log(cap)-np.logaddexp(0.,s[:,:,1]);sigma=np.exp(l);z=s[:,:,3:]
    a=z[:,:,0]/np.sqrt(1-rho*rho);total=a.copy()
    for i in range(1,z.shape[2]):a=rho*a+z[:,:,i];total+=a
    hlast=s[:,:,0]+sigma*a;hbar=s[:,:,0]+sigma*total/z.shape[2]
    beta=np.exp(hbar/2)*s[:,:,2]
    values=dict(mu=s[:,:,0],log_sigma=l,beta=beta,z=z,b=s[:,:,2])
    joint=np.stack([values['mu'],l,beta,hlast],axis=-1)
    if not np.isfinite(joint).all():raise ValueError('Nonfinite physical reconstruction')
    return values,joint

def differences(nuts,walnuts,baseline):
    a=np.asarray([nuts,walnuts,baseline],dtype=float)
    if not np.isfinite(a).all():raise ValueError('Finite scores')
    model=nuts-baseline;inference=walnuts-nuts;total=walnuts-baseline
    assert abs(model+inference-total)<=64*np.finfo(float).eps*max(1.,abs(a).max())
    return dict(model=model,inference=inference,total=total)
