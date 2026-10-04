"""Optional associative-prefix implementation of the unchanged dense mixed target.

No worker/default routing changes. Physical beta stays centered; only the
volatility innovation recurrence uses the existing optimized affine prefix.
"""
from flow_mixed_coordinates import _data


def _shape(u,data):
    y,x=_data(data)
    if getattr(u,'ndim',None)!=1 or u.shape[0]!=4+2*y.shape[1]+y.shape[0]:raise ValueError('Exact mixed coordinate vector dimension required')
    return y,x


def jax_to_canonical(u,data):
    import jax.numpy as jnp
    from optimized_reference import canonical_noncentered
    _,x=_shape(u,data);g=x.shape[1];k=4+2*g
    # The helper reads only globals and path innovations for h, and copies its
    # prefix unchanged. Replace the beta block explicitly; never interpret the
    # centered beta values as canonical z_beta or call the NC density on u.
    h=canonical_noncentered(u,data)[k:]
    return jnp.concatenate((u[:4+g],(u[4+g:k]-u[0])*jnp.exp(-u[1]),h))


def jax_log_density(u,data):
    import jax.numpy as jnp
    from jax.scipy.special import gammaln
    from optimized_reference import canonical_noncentered
    y,x=_shape(u,data);t,g=y.shape;k=4+2*g;nu=data['nu']
    def normal(value,mean,logsd):
        return jnp.sum(-.5*((value-mean)*jnp.exp(-logsd))**2-logsd-.5*jnp.log(2*jnp.pi))
    lp=normal(u[:4],jnp.array([0.,-1.,-1.,-1.5]),jnp.log(jnp.array([.5,.5,1.,.5])))
    lp+=normal(u[4:4+g],0.,0.)+normal(u[4+g:k],u[0],u[1])+normal(u[k:],0.,0.)
    h=canonical_noncentered(u,data)[k:]
    location=.3*u[4:4+g]+u[4+g:k]*jnp.asarray(x);logs=h[:,None]/2
    residual=(jnp.asarray(y)-location)*jnp.exp(-logs)
    return lp+jnp.sum(gammaln((nu+1)/2)-gammaln(nu/2)-.5*jnp.log(nu*jnp.pi)-logs-(nu+1)/2*jnp.log1p(residual**2/nu))


def normalized_parity(data,points):
    """Check the actual associative potential against an independent transform."""
    import hashlib
    import numpy as np
    import jax
    jax.config.update('jax_enable_x64',True)
    import jax.numpy as jnp
    from jax.scipy.special import gammaln
    from model import log_density
    from flow_mixed_coordinates import jax_to_canonical as sequential_canonical,log_jacobian
    direct=jax.jit(jax.value_and_grad(lambda u:jax_log_density(u,data)))
    independent=jax.jit(jax.value_and_grad(lambda u:log_density(sequential_canonical(u,data),data,jnp,gammaln)+log_jacobian(u,data,jnp)))
    rows=[]
    for point in points:
        v,g=direct(jnp.asarray(point));other,gradient=independent(jnp.asarray(point))
        if not np.isfinite(v) or not np.isfinite(g).all():raise ValueError('Nonfinite associative parity point')
        np.testing.assert_allclose(v,other,rtol=1e-10,atol=1e-8)
        np.testing.assert_allclose(g,gradient,rtol=1e-8,atol=1e-6)
        rows.append(dict(value_error=abs(float(v-other)),gradient_max_error=float(np.max(np.abs(np.asarray(g-gradient)))),point_sha256=hashlib.sha256(np.asarray(point,dtype=np.float64).tobytes()).hexdigest()))
    if not rows:raise ValueError('Nonempty parity points required')
    return dict(passed=True,implementation='associative',cases=rows,normalized_canonical_jacobian_value_and_gradient=True,jax_enable_x64=True)

