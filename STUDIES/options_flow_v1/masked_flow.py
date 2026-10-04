"""Experimental observed-only flow likelihood on an unchanged regular latent grid.

Conditioning on which trades/returns/features are observed is an explicit model
limitation. Informative trade arrival, missing quotes or stale features can bias
inference; this module neither models selection nor imputes missing returns.
"""
import numpy as np
from scipy.special import gammaln


def validate(data):
    y=np.asarray(data['y'],dtype=np.float64);x=np.asarray(data['x'],dtype=np.float64)
    mask=np.asarray(data['observation_mask'])
    if y.ndim!=2 or x.shape!=y.shape or mask.shape!=y.shape or min(y.shape)<1:raise ValueError('Nonempty matching T-by-G arrays required')
    if mask.dtype!=np.bool_:raise ValueError('observation_mask must contain explicit booleans')
    if not np.isfinite(y[mask]).all() or not np.isfinite(x[mask]).all():raise ValueError('Observed rows require finite y and available finite x')
    rho=float(data['rho']);nu=float(data['nu'])
    if not np.isfinite([rho,nu]).all() or abs(rho)>=1 or nu<=2:raise ValueError('Finite abs(rho)<1 and nu>2 required')
    grid=np.asarray(data['grid_index'])
    if grid.shape!=(len(y),) or not np.issubdtype(grid.dtype,np.integer) or np.issubdtype(grid.dtype,np.bool_) or not np.array_equal(grid,np.arange(len(y))):raise ValueError('grid_index must preserve every regular step 0..T-1')
    return y,x,mask


def from_arrays(y,x,*,y_available,x_available,rho=.95,nu=5.,grid_index=None):
    """Availability supplied explicitly; missing covariates exclude that likelihood.

    Caller remains responsible for timestamp alignment and feature availability
    before the forecast origin. A zero placeholder never means an observed zero.
    """
    y=np.asarray(y,dtype=np.float64);x=np.asarray(x,dtype=np.float64)
    ya=np.asarray(y_available);xa=np.asarray(x_available)
    if ya.dtype!=np.bool_ or xa.dtype!=np.bool_ or ya.shape!=y.shape or xa.shape!=y.shape:raise ValueError('Explicit matching boolean availability arrays required')
    mask=ya&xa
    data=dict(y=y.tolist(),x=x.tolist(),observation_mask=mask.tolist(),rho=float(rho),nu=float(nu),grid_index=list(range(len(y))) if grid_index is None else list(grid_index),
        missingness=dict(excluded_y=int((~ya).sum()),excluded_x=int((ya&~xa).sum()),observed=int(mask.sum()),
            assumption='Conditional on observation/trade-arrival pattern; selection mechanism not modeled'))
    validate(data)
    # Frozen finite placeholders simplify serialization; likelihood gathers only
    # true observations before any arithmetic, so placeholder values never enter AD.
    data['y']=np.where(mask,y,0.).tolist();data['x']=np.where(mask,x,0.).tolist()
    return data


def canonical(q,data,xp=np):
    y,_,_=validate(data);t,g=y.shape;k=4+2*g;z=q[k:];mu=q[2];sig=xp.exp(q[3]);rho=data['rho']
    first=mu+sig*z[0]/xp.sqrt(1-rho*rho)
    if xp is np:
        h=np.empty(t);h[0]=first
        for i in range(1,t):h[i]=mu+rho*(h[i-1]-mu)+sig*z[i]
    else:
        from jax import lax
        def step(previous,zi):
            current=mu+rho*(previous-mu)+sig*zi
            return current,current
        _,tail=lax.scan(step,first,z[1:]);h=xp.concatenate((first[None],tail))
    return xp.concatenate((q[:k],h))


def log_density(q,data,xp=np,gamma=gammaln,noncentered=False):
    y,x,mask=validate(data);t,g=y.shape;k=4+2*g
    def normal(value,mean,sd):return xp.sum(-.5*((value-mean)/sd)**2-xp.log(sd)-.5*xp.log(2*xp.pi))
    lp=normal(q[:4],xp.asarray([0.,-1.,-1.,-1.5]),xp.asarray([.5,.5,1.,.5]))
    lp+=normal(q[4:k],0.,1.)
    if noncentered:
        lp+=normal(q[k:],0.,1.)
        if not mask.any():return lp
        h=canonical(q,data,xp)[k:]
    else:
        h=q[k:];mu=q[2];sig=xp.exp(q[3]);rho=data['rho']
        lp+=normal(h[0],mu,sig/xp.sqrt(1-rho*rho))+normal(h[1:],mu+rho*(h[:-1]-mu),sig)
    # Gather FIRST: no NaN/Inf placeholders participate in residual arithmetic.
    ti,gi=np.nonzero(mask)
    observed_y=xp.asarray(y[ti,gi]);observed_x=xp.asarray(x[ti,gi]);nu=data['nu']
    location=.3*q[4+gi]+(q[0]+xp.exp(q[1])*q[4+g+gi])*observed_x
    logs=h[ti]/2;residual=(observed_y-location)*xp.exp(-logs)
    return lp+xp.sum(gamma((nu+1)/2)-gamma(nu/2)-.5*xp.log(nu*xp.pi)-logs-(nu+1)/2*xp.log1p(residual**2/nu))
