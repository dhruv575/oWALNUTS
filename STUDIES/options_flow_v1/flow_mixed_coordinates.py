"""Optional dense-flow study target: centered group slopes, NC volatility path.

Optional target; focused correctness and tiny-worker tests passed, no timed trial.
u=[beta_bar,log_tau,mu_h,log_sigma_h,z_alpha[G],beta[G],z_path[T]].
"""
import numpy as np


def _data(data):
    from model import validate
    if 'observation_mask' in data:raise ValueError('Dense mixed target cannot ignore observation mask')
    return validate(data)


def _position(q,data):
    y,_=_data(data);t,g=y.shape
    q=np.asarray(q,dtype=np.float64)
    if q.ndim<1 or q.shape[-1]!=4+2*g+t or not np.isfinite(q).all():raise ValueError('Finite mixed/canonical positions of exact dimension required')
    return q,t,g


def to_mixed(q,data):
    q,t,g=_position(q,data)
    # Existing flow helper handles batches of chains, but use a local vectorized
    # inverse AR recurrence to also support chain-by-draw arrays.
    u=q.copy();k=4+2*g;rho=float(data['rho']);mu=q[...,2];sig=np.exp(q[...,3]);tau=np.exp(q[...,1]);h=q[...,k:]
    if not np.isfinite(sig).all() or not np.isfinite(tau).all() or (sig<=0).any() or (tau<=0).any():raise ValueError('Unrepresentable positive scale')
    u[...,4+g:k]=q[...,0,None]+tau[...,None]*q[...,4+g:k]
    u[...,k]=(h[...,0]-mu)*np.sqrt(1-rho*rho)/sig
    u[...,k+1:]=(h[...,1:]-mu[...,None]-rho*(h[...,:-1]-mu[...,None]))/sig[...,None]
    if not np.isfinite(u).all():raise ValueError('Nonfinite mixed conversion')
    return u


def to_canonical(u,data):
    u,t,g=_position(u,data);q=u.copy();k=4+2*g;rho=float(data['rho']);mu=u[...,2];sig=np.exp(u[...,3]);tau=np.exp(u[...,1])
    if not np.isfinite(sig).all() or not np.isfinite(tau).all() or (sig<=0).any() or (tau<=0).any():raise ValueError('Unrepresentable positive scale')
    q[...,4+g:k]=(u[...,4+g:k]-u[...,0,None])/tau[...,None]
    q[...,k]=mu+sig*u[...,k]/np.sqrt(1-rho*rho)
    for i in range(1,t):q[...,k+i]=mu+rho*(q[...,k+i-1]-mu)+sig*u[...,k+i]
    if not np.isfinite(q).all():raise ValueError('Nonfinite canonical conversion')
    return q


def log_jacobian(u,data,xp=np):
    """log|d canonical / d mixed|, including NC-path and centered-beta factors."""
    y,_=_data(data);t,g=y.shape
    return -g*u[...,1]+t*u[...,3]-.5*xp.log1p(-data['rho']**2)


def jax_log_density(u,data):
    """Independent normalized density; no hand gradients, linear-time AR scan."""
    import jax.numpy as jnp
    from jax import lax
    from jax.scipy.special import gammaln
    y,x=_data(data);t,g=y.shape;k=4+2*g;rho=data['rho'];nu=data['nu']
    def normal(value,mean,logsd):
        return jnp.sum(-.5*((value-mean)*jnp.exp(-logsd))**2-logsd-.5*jnp.log(2*jnp.pi))
    lp=normal(u[:4],jnp.array([0.,-1.,-1.,-1.5]),jnp.log(jnp.array([.5,.5,1.,.5])))
    lp+=normal(u[4:4+g],0.,0.)+normal(u[4+g:k],u[0],u[1])+normal(u[k:],0.,0.)
    mu=u[2];sig=jnp.exp(u[3]);first=mu+sig*u[k]/jnp.sqrt(1-rho*rho)
    def step(previous,z):
        current=mu+rho*(previous-mu)+sig*z
        return current,current
    _,tail=lax.scan(step,first,u[k+1:]);h=jnp.concatenate([first[None],tail])
    location=.3*u[4:4+g]+u[4+g:k]*jnp.asarray(x);logs=h[:,None]/2
    residual=(jnp.asarray(y)-location)*jnp.exp(-logs)
    lp+=jnp.sum(gammaln((nu+1)/2)-gammaln(nu/2)-.5*jnp.log(nu*jnp.pi)-logs-(nu+1)/2*jnp.log1p(residual**2/nu))
    return lp


def jax_to_canonical(u,data):
    """Differentiable inverse used only by independent normalized parity checks."""
    import jax.numpy as jnp
    from jax import lax
    y,_=_data(data);t,g=y.shape;k=4+2*g;rho=data['rho'];mu=u[2];sig=jnp.exp(u[3])
    first=mu+sig*u[k]/jnp.sqrt(1-rho*rho)
    def step(previous,z):
        current=mu+rho*(previous-mu)+sig*z
        return current,current
    _,tail=lax.scan(step,first,u[k+1:])
    return jnp.concatenate([u[:4+g],(u[4+g:k]-u[0])*jnp.exp(-u[1]),first[None],tail])


def normalized_parity(data,points,target=None):
    """Mandatory direct-vs-canonical+Jacobian value/gradient checks, JAX64."""
    import hashlib
    import jax
    jax.config.update('jax_enable_x64',True)
    import jax.numpy as jnp
    from jax.scipy.special import gammaln
    from model import log_density
    direct=jax.jit(jax.value_and_grad(lambda u:jax_log_density(u,data)))
    transformed=jax.jit(jax.value_and_grad(lambda u:log_density(jax_to_canonical(u,data),data,jnp,gammaln)+log_jacobian(u,data,jnp)))
    rows=[]
    for point in points:
        u=jnp.asarray(point);value,gradient=direct(u);other,other_gradient=transformed(u)
        if not np.isfinite(value) or not np.isfinite(gradient).all():raise ValueError('Nonfinite mixed parity point')
        np.testing.assert_allclose(value,other,rtol=1e-10,atol=1e-8)
        np.testing.assert_allclose(gradient,other_gradient,rtol=1e-9,atol=1e-8)
        row=dict(value_error=abs(float(value-other)),gradient_max_error=float(np.max(np.abs(np.asarray(gradient-other_gradient)))),
            point_sha256=hashlib.sha256(np.asarray(point,dtype=np.float64).tobytes()).hexdigest())
        if target is not None:
            from pymc_workflow import evaluate_cfunc
            native_value,native_gradient=evaluate_cfunc(target,point)
            np.testing.assert_allclose(native_value,value,rtol=1e-10,atol=1e-8)
            np.testing.assert_allclose(native_gradient,gradient,rtol=1e-9,atol=1e-8)
            row.update(native_value_error=abs(native_value-float(value)),native_gradient_max_error=float(np.max(np.abs(native_gradient-np.asarray(gradient)))))
        rows.append(row)
    if not rows:raise ValueError('Nonempty mixed parity points required')
    return dict(passed=True,cases=rows,normalized_canonical_jacobian_value_and_gradient=True,jax_enable_x64=True)


def build_model(data,block_size=32,likelihood_variant="pymc_student_t"):
    if likelihood_variant not in ("pymc_student_t","shared_logvol_student_t_v1"):raise ValueError("Unknown likelihood variant")
    if likelihood_variant!="pymc_student_t" and block_size!=32:raise ValueError("Candidate likelihood requires block32")
    import pymc as pm
    import pytensor.tensor as pt
    from flow_starts import canonical_starts
    from pymc_flow_workflow import ar_path
    y,x=_data(data);t,g=y.shape;k=4+2*g
    chains=len(data['initial_positions']) if 'initial_positions' in data else 1
    initial=to_mixed(canonical_starts(data,chains),data)[0]
    with pm.Model() as model:
        u=pm.Flat('q',shape=k+t,initval=initial)
        lp=pt.sum(pm.logp(pm.Normal.dist(mu=np.array([0.,-1.,-1.,-1.5]),sigma=np.array([.5,.5,1.,.5])),u[:4]))
        lp+=pt.sum(pm.logp(pm.Normal.dist(mu=np.float64(0),sigma=np.float64(1)),u[4:4+g]))
        lp+=pt.sum(pm.logp(pm.Normal.dist(mu=u[0],sigma=pt.exp(u[1])),u[4+g:k]))
        lp+=pt.sum(pm.logp(pm.Normal.dist(mu=np.float64(0),sigma=np.float64(1)),u[k:]))
        h=ar_path(u[k:],u[2],pt.exp(u[3]),np.float64(data['rho']),t,block_size)
        location=np.float64(.3)*u[4:4+g]+u[4+g:k]*np.array(x,copy=True)
        if likelihood_variant=="pymc_student_t":
            lp+=pt.sum(pm.logp(pm.StudentT.dist(nu=np.float64(data['nu']),mu=location,sigma=pt.exp(h[:,None]/np.float64(2))),np.array(y,copy=True)))
        else:
            # Optional algebra with automatic gradients; exp(-h) retains known
            # extreme-domain numerical limitations. This is not a new model.
            import math
            nu=float(data['nu']);constant=math.lgamma((nu+1)/2)-math.lgamma(nu/2)-.5*math.log(nu*math.pi)
            residual=np.array(y,copy=True)-location
            lp+=np.float64(t*g*constant)-np.float64(g/2)*pt.sum(h)-np.float64((nu+1)/2)*pt.sum(pt.log1p(residual**2*pt.exp(-h[:,None])/np.float64(nu)))
        pm.Potential('normalized_mixed_flow',lp)
    return model
