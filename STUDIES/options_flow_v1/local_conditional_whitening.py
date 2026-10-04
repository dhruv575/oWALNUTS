"""Exploratory exact Gaussian-guide coordinates for the local Student-t target.

No target approximation: h=m(scales)+L(scales)^(-T)z, with exact Jacobian.
The stable filtering-information recurrence avoids subtractive Cholesky pivots.
"""
import numpy as np
from scipy.special import gammaln
from local_level import validate


def _guide(log_obs, log_rw, data, xp=np):
    """Independent NumPy/JAX implementation, supports leading batch dimensions."""
    t=len(data['y'])
    w=xp.exp(-2*log_obs)
    r=xp.exp(-2*log_rw)[...,None]/xp.asarray(data.get('dt',np.ones(t-1)))
    f=[w+1/1.5**2]
    for i in range(t-1):
        small=xp.minimum(r[...,i],f[-1]);large=xp.maximum(r[...,i],f[-1])
        f.append(w+small/(1+small/large))
    f=xp.stack(f,axis=-1)
    outgoing=xp.concatenate((r,xp.zeros_like(w)[...,None]),axis=-1)
    diag=xp.sqrt(f+outgoing)
    sub=-r/diag[...,:-1]
    b=w[...,None]*xp.asarray(data['y'])
    v=[(b[...,0]+data['anchor']/1.5**2)/diag[...,0]]
    for i in range(1,t):v.append((b[...,i]-sub[...,i-1]*v[-1])/diag[...,i])
    v=xp.stack(v,axis=-1)
    m=_backsolve(v,diag,sub,xp)
    return m,diag,sub


def _backsolve(rhs,diag,sub,xp=np):
    values=[rhs[...,-1]/diag[...,-1]]
    for i in range(rhs.shape[-1]-2,-1,-1):
        values.append((rhs[...,i]-sub[...,i]*values[-1])/diag[...,i])
    return xp.stack(values[::-1],axis=-1)


def _position(q,data):
    validate(data)
    q=np.asarray(q,dtype=float)
    if q.ndim<1 or q.shape[-1]!=len(data['y'])+2 or not np.isfinite(q).all():
        raise ValueError('Require finite positions with final dimension T+2')
    with np.errstate(over='ignore',under='ignore'):
        precisions=np.exp(-2*q[...,-2:])
    if not np.isfinite(precisions).all() or (precisions==0).any():
        raise ValueError('Scale precision outside representable range')
    return q


def to_canonical(u,data):
    u=_position(u,data)
    with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
        m,d,e=_guide(u[...,-2],u[...,-1],data)
        h=m+_backsolve(u[...,:-2],d,e)
    if not np.isfinite(h).all() or not np.isfinite(d).all() or (d<=0).any():
        raise ValueError('Nonfinite guide conversion')
    return np.concatenate((h,u[...,-2:]),axis=-1)


def to_whitened(q,data):
    q=_position(q,data)
    with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
        m,d,e=_guide(q[...,-2],q[...,-1],data)
        delta=q[...,:-2]-m
        z=d*delta
        z[...,:-1]+=e*delta[...,1:]
    if not np.isfinite(z).all() or not np.isfinite(d).all() or (d<=0).any():
        raise ValueError('Nonfinite guide inverse')
    return np.concatenate((z,q[...,-2:]),axis=-1)


def log_density(u,data,xp=np,gaussian=False):
    """Normalized independent joint in guide coordinates; JAX differentiable."""
    u=xp.asarray(u);t=len(data['y'])
    if u.ndim!=1 or u.shape[0]!=t+2:raise ValueError('Expected T+2 vector')
    z,lo,lr=u[:-2],u[-2],u[-1]
    m,d,e=_guide(lo,lr,data,xp)
    h=m+_backsolve(z,d,e,xp)
    def normal(v,mean,sd):
        return xp.sum(-.5*((v-mean)/sd)**2-xp.log(sd)-.5*np.log(2*np.pi))
    lp=normal(lo,np.log(.08),1.)+normal(lr,np.log(.12),1.)
    lp+=normal(h[0],data['anchor'],1.5)
    lp+=normal(h[1:]-h[:-1],0.,xp.exp(lr)*xp.sqrt(xp.asarray(data.get('dt',np.ones(t-1)))))
    residual=(xp.asarray(data['y'])-h)/xp.exp(lo)
    if gaussian:lp+=normal(residual,0.,1.)-t*lo
    else:lp+=xp.sum(gammaln(3.)-gammaln(2.5)-.5*np.log(5*np.pi)-lo-3*xp.log1p(residual**2/5))
    return lp-xp.sum(xp.log(d))


def _jax_backsolve(rhs,d,e):
    import jax
    import jax.numpy as jnp
    last=rhs[-1]/d[-1]
    def step(previous,parts):
        ri,ei,di=parts
        value=(ri-ei*previous)/di
        return value,value
    _,rest=jax.lax.scan(step,last,(rhs[:-1][::-1],e[::-1],d[:-1][::-1]))
    return jnp.concatenate((rest[::-1],last[None]))


def _jax_guide(lo,lr,data):
    """Linear-size compiled scan graph; NumPy/Python-loop guide stays independent."""
    import jax
    import jax.numpy as jnp
    t=len(data['y']);w=jnp.exp(-2*lo)
    r=jnp.exp(-2*lr)/jnp.asarray(data.get('dt',np.ones(t-1)))
    first=w+1/1.5**2
    def filter_step(previous,ri):
        small=jnp.minimum(ri,previous);large=jnp.maximum(ri,previous)
        value=w+small/(1+small/large)
        return value,value
    _,rest=jax.lax.scan(filter_step,first,r)
    f=jnp.concatenate((first[None],rest))
    d=jnp.sqrt(f+jnp.concatenate((r,jnp.zeros(1,dtype=lo.dtype))))
    e=-r/d[:-1]
    b=w*jnp.asarray(data['y'])
    v0=(b[0]+data['anchor']/1.5**2)/d[0]
    def forward(previous,parts):
        bi,ei,di=parts
        value=(bi-ei*previous)/di
        return value,value
    _,vrest=jax.lax.scan(forward,v0,(b[1:],e,d[1:]))
    v=jnp.concatenate((v0[None],vrest))
    return _jax_backsolve(v,d,e),d,e


def jax_log_density(u,data,gaussian=False):
    """Normalized scan-based potential for NumPyro; no Python path-length loops."""
    import jax.numpy as jnp
    u=jnp.asarray(u);t=len(data['y'])
    if u.ndim!=1 or u.shape[0]!=t+2:raise ValueError('Expected T+2 vector')
    lo,lr=u[-2],u[-1]
    m,d,e=_jax_guide(lo,lr,data)
    h=m+_jax_backsolve(u[:-2],d,e)
    def normal(v,mean,sd):
        return jnp.sum(-.5*((v-mean)/sd)**2-jnp.log(sd)-.5*np.log(2*np.pi))
    lp=normal(lo,np.log(.08),1.)+normal(lr,np.log(.12),1.)
    lp+=normal(h[0],data['anchor'],1.5)
    lp+=normal(h[1:]-h[:-1],0.,jnp.exp(lr)*jnp.sqrt(jnp.asarray(data.get('dt',np.ones(t-1)))))
    residual=(jnp.asarray(data['y'])-h)/jnp.exp(lo)
    if gaussian:lp+=normal(residual,0.,1.)-t*lo
    else:lp+=jnp.sum(gammaln(3.)-gammaln(2.5)-.5*np.log(5*np.pi)-lo-3*jnp.log1p(residual**2/5))
    return lp-jnp.log(d).sum()


def _pytensor_guide(lo,lr,data):
    """Scan recurrences; separate symbolic implementation for parity checks."""
    import pytensor
    import pytensor.tensor as pt
    y,dt=validate(data);t=len(y)
    w=pt.exp(-2*lo);r=pt.exp(-2*lr)/pt.constant(dt)
    f0=w+np.float64(1/1.5**2)
    if t==1:
        d=pt.sqrt(f0)[None];e=pt.constant(np.empty(0,dtype=np.float64))
        return (w*y+np.float64(data['anchor']/1.5**2))/(d*d),d,e
    def update(ri,previous,wi):
        small=pt.minimum(ri,previous);large=pt.maximum(ri,previous)
        return wi+small/(np.float64(1.)+small/large)
    rest,_=pytensor.scan(update,sequences=[r],outputs_info=[f0],non_sequences=[w],strict=True)
    f=pt.concatenate((f0[None],rest))
    d=pt.sqrt(f+pt.concatenate((r,pt.zeros((1,),dtype='float64'))));e=-r/d[:-1]
    b=w*pt.constant(y)
    v0=(b[0]+np.float64(data['anchor']/1.5**2))/d[0]
    vrest,_=pytensor.scan(lambda bi,ei,di,prev:(bi-ei*prev)/di,
        sequences=[b[1:],e,d[1:]],outputs_info=[v0],strict=True)
    v=pt.concatenate((v0[None],vrest))
    return _pytensor_backsolve(v,d,e),d,e


def _pytensor_backsolve(rhs,d,e):
    import pytensor
    import pytensor.tensor as pt
    last=rhs[-1]/d[-1]
    rest,_=pytensor.scan(lambda ri,ei,di,prev:(ri-ei*prev)/di,
        sequences=[rhs[:-1][::-1],e[::-1],d[:-1][::-1]],outputs_info=[last],strict=True)
    return pt.concatenate((rest[::-1],last[None]))


def build_model(data):
    import pymc as pm
    import pytensor.tensor as pt
    from local_observation_residual import canonical_starts
    y,dt=validate(data);t=len(y)
    initial=to_whitened(np.r_[y,np.log(.08),np.log(.12)],data)
    with pm.Model() as model:
        u=pm.Flat('position',shape=t+2,initval=initial)
        z,lo,lr=u[:-2],u[-2],u[-1]
        m,d,e=_pytensor_guide(lo,lr,data)
        delta=z/d if t==1 else _pytensor_backsolve(z,d,e)
        h=m+delta
        lp=pm.logp(pm.Normal.dist(mu=np.float64(np.log(.08)),sigma=np.float64(1.)),lo)
        lp+=pm.logp(pm.Normal.dist(mu=np.float64(np.log(.12)),sigma=np.float64(1.)),lr)
        lp+=pm.logp(pm.Normal.dist(mu=np.float64(data['anchor']),sigma=np.float64(1.5)),h[0])
        lp+=pm.logp(pm.Normal.dist(mu=h[:-1],sigma=pt.exp(lr)*pt.sqrt(pt.constant(dt))),h[1:]).sum()
        lp+=pm.logp(pm.StudentT.dist(nu=np.float64(5.),mu=h,sigma=pt.exp(lo)),pt.constant(y.copy())).sum()
        pm.Potential('normalized_target',lp-pt.log(d).sum())
    return model
