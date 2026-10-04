"""Optional fixed-shape masked NC target with explicit runtime data arguments.

No sampler/session ownership. Callers snapshot each dataset and reset adaptation
for every changed posterior; immutable CFunc adapter behavior is unchanged.
"""

def snapshot(data):
    """Copy/sanitize host inputs before dispatch; no references to caller arrays."""
    import numpy as np
    from masked_flow import validate
    y,x,mask=validate(data)
    result=[]
    for value in [np.where(mask,y,0.),np.where(mask,x,0.),mask.copy(),np.asarray(data['rho'],dtype=np.float64),np.asarray(data['nu'],dtype=np.float64)]:
        array=np.array(value,copy=True);array.setflags(write=False);result.append(array)
    return tuple(result)


def canonical(q,y,x,mask,rho,nu):
    import jax
    import jax.numpy as jnp
    _shape(q,y,x,mask,rho,nu)
    g=y.shape[1];k=4+2*g;z=q[k:];mu=q[2];sigma=jnp.exp(q[3])
    a=jnp.full(z.shape,rho).at[0].set(0.)
    b=(mu*(1-rho)+sigma*z).at[0].set(mu+sigma*z[0]/jnp.sqrt(1-rho*rho))
    def compose(left,right):
        a0,b0=left;a1,b1=right
        return a1*a0,b1+a1*b0
    _,h=jax.lax.associative_scan(compose,(a,b))
    return jnp.concatenate((q[:k],h))


def _shape(q,y,x,mask,rho,nu):
    import jax.numpy as jnp
    if y.ndim!=2 or min(y.shape)<1 or x.shape!=y.shape or mask.shape!=y.shape or mask.dtype!=jnp.bool_:raise ValueError('Fixed nonempty T-by-G arrays and explicit boolean mask required')
    if q.ndim!=1 or q.shape[0]!=4+2*y.shape[1]+y.shape[0] or rho.ndim!=0 or nu.ndim!=0:raise ValueError('Exact NC vector and scalar rho/nu required')


def log_density(q,y,x,mask,rho,nu):
    """Normalized target. Validate values via snapshot before calling jitted code.

    Array shapes/dtypes are static; observed count and rho/nu remain runtime.
    No boolean gathering, so a different mask does not change likelihood shape.
    """
    import jax.numpy as jnp
    from jax.scipy.special import gammaln
    _shape(q,y,x,mask,rho,nu)
    t,g=y.shape;k=4+2*g
    def normal(value,mean,sd):return jnp.sum(-.5*((value-mean)/sd)**2-jnp.log(sd)-.5*jnp.log(2*jnp.pi))
    lp=normal(q[:4],jnp.array([0.,-1.,-1.,-1.5]),jnp.array([.5,.5,1.,.5]))+normal(q[4:],0.,1.)
    h=canonical(q,y,x,mask,rho,nu)[k:]
    # Sanitize before residual arithmetic and exponentiation, not by multiplying
    # an already invalid log likelihood by zero. All-missing rows still advance h.
    safe_y=jnp.where(mask,y,0.);safe_x=jnp.where(mask,x,0.)
    logs=jnp.where(mask,h[:,None]/2,0.)
    location=jnp.where(mask,.3*q[4:4+g]+(q[0]+jnp.exp(q[1])*q[4+g:k])*safe_x,0.)
    residual=(safe_y-location)*jnp.exp(-logs)
    likelihood=gammaln((nu+1)/2)-gammaln(nu/2)-.5*jnp.log(nu*jnp.pi)-logs-(nu+1)/2*jnp.log1p(residual**2/nu)
    return lp+jnp.sum(jnp.where(mask,likelihood,0.))
