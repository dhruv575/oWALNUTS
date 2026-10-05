"""Independent normalized JAX/NumPyro reference; immutable fixed-data target."""
import numpy as np
import jax
import jax.numpy as jnp
from jax.scipy.special import gammaln
jax.config.update('jax_enable_x64', True)


def make_reference(target):
    """Snapshot validated Target inputs, returning (log_density, path).

    No analytical Target density/gradient is called. The associative affine scan
    preserves every scheduled state, including missing-outcome transitions.
    """
    t,p,k=target.t,target.p,target.k;offset=2+p+k;dimension=offset+t
    rho,nu=target.rho,target.nu;prior=target.priors
    observed=np.flatnonzero(target.observed)
    y=jnp.asarray(np.array(target.y[observed],copy=True))
    x=jnp.asarray(np.array(target.x[observed],copy=True))
    w=jnp.asarray(np.array(target.w,copy=True))
    indices=jnp.asarray(observed)
    means=jnp.asarray([prior.mu_mean,prior.log_sigma_mean]+[0.]*(dimension-2))
    scales=jnp.asarray([prior.mu_sd,prior.log_sigma_sd]+[prior.beta_sd]*p+[prior.gamma_sd]*k+[1.]*t)
    def check(q):
        q=jnp.asarray(q,dtype=jnp.float64)
        if q.shape!=(dimension,):raise ValueError('Exact one-dimensional q layout required')
        return q
    def path(q):
        q=check(q);mu,logsigma=q[0],q[1];gamma=q[2+p:offset];z=q[offset:];sigma=jnp.exp(logsigma)
        b=(1-rho)*mu+w@gamma+sigma*z
        b=b.at[0].set(mu+w[0]@gamma+sigma*z[0]/jnp.sqrt(1-rho*rho))
        a=jnp.full((t,),rho,dtype=jnp.float64).at[0].set(0.)
        def compose(left,right):
            al,bl=left;ar,br=right
            return ar*al,ar*bl+br
        return jax.lax.associative_scan(compose,(a,b))[1]
    def log_density(q):
        q=check(q)
        lp=jnp.sum(-.5*((q-means)/scales)**2-jnp.log(scales)-.5*jnp.log(2*jnp.pi))
        h=path(q)[indices];residual=y-x@q[2:2+p]
        # Guard log(0) before autodiff, preserving the exact zero-residual limit.
        nonzero=residual!=0
        logabs=jnp.log(jnp.where(nonzero,jnp.abs(residual),1.))
        tail=jnp.where(nonzero,jnp.logaddexp(0.,2*logabs-jnp.log(nu)-h),0.)
        likelihood=gammaln((nu+1)/2)-gammaln(nu/2)-.5*jnp.log(nu*jnp.pi)-.5*h-.5*(nu+1)*tail
        return lp+jnp.sum(likelihood)
    return log_density,path


def make_kernel(target, *, target_accept=.9, max_tree_depth=10):
    """NumPyro NUTS potential with the same unconstrained q and normalized law."""
    from numpyro.infer import NUTS
    if isinstance(target_accept,bool) or not np.isfinite(target_accept) or not 0<target_accept<1:
        raise ValueError('Acceptance probability must be finite in (0,1)')
    log_density,_=make_reference(target)
    return NUTS(potential_fn=lambda q:-log_density(q),target_accept_prob=float(target_accept),max_tree_depth=max_tree_depth)
