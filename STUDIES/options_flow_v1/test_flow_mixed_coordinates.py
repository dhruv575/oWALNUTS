"""Prospective mixed-coordinate checks; authored statically, not yet executed."""
import numpy as np
import pytest
from flow_mixed_coordinates import to_mixed,to_canonical,log_jacobian,jax_log_density,build_model


def data(t,g):return dict(y=np.linspace(-.2,.3,t*g).reshape(t,g).tolist(),x=np.linspace(-1.,1.,t*g).reshape(t,g).tolist(),rho=.8,nu=5.)


@pytest.mark.parametrize('t,g',[(1,1),(7,4)])
def test_roundtrip_and_all_physical_functionals(t,g):
    from flow_starts import canonical_starts
    from model import functionals
    d=data(t,g);q=np.repeat(canonical_starts(d,4)[:,None,:],3,axis=1)
    q+=np.random.default_rng(817).normal(0,.05,q.shape)
    u=to_mixed(q,d);returned=to_canonical(u,d)
    np.testing.assert_allclose(returned,q,rtol=1e-12,atol=1e-12)
    for name,values in functionals(q,g).items():np.testing.assert_allclose(functionals(returned,g)[name],values,rtol=1e-12,atol=1e-12)
    for logtau in [-9.,2.]:
        q[...,1]=logtau
        np.testing.assert_allclose(to_canonical(to_mixed(q,d),d),q,rtol=1e-8,atol=1e-8)


def test_signed_jacobian_and_normalized_density_independent_transform():
    import jax
    jax.config.update('jax_enable_x64',True)
    import jax.numpy as jnp
    from jax.scipy.special import gammaln
    from model import log_density
    d=data(3,2);k=8
    def transform(u):
        mu=u[2];sig=jnp.exp(u[3]);h=[mu+sig*u[k]/jnp.sqrt(1-d['rho']**2)]
        for z in u[k+1:]:h.append(mu+d['rho']*(h[-1]-mu)+sig*z)
        return jnp.concatenate([u[:6],(u[6:8]-u[0])*jnp.exp(-u[1]),jnp.stack(h)])
    u=jnp.asarray([.2,-.9,-.8,-1.3,.1,-.2,.4,-.1,.3,-.4,.2])
    actual=jnp.linalg.slogdet(jax.jacfwd(transform)(u))[1]
    np.testing.assert_allclose(actual,log_jacobian(u,d,jnp),rtol=1e-12,atol=1e-12)
    transformed=lambda v:log_density(transform(v),d,jnp,gammaln)+log_jacobian(v,d,jnp)
    a,ga=jax.value_and_grad(lambda v:jax_log_density(v,d))(u)
    b,gb=jax.value_and_grad(transformed)(u)
    np.testing.assert_allclose(a,b,rtol=1e-12,atol=1e-11)
    np.testing.assert_allclose(ga,gb,rtol=1e-10,atol=1e-9)


@pytest.mark.parametrize('t,g',[(1,1),(7,4)])
def test_public_pymc_gradient_matches_independent_jax(t,g):
    import jax
    jax.config.update('jax_enable_x64',True)
    import jax.numpy as jnp
    import owalnuts
    from pymc_workflow import evaluate_cfunc
    from flow_starts import canonical_starts
    d=data(t,g);target,dimension,initial,names,_=owalnuts.from_pymc(build_model(d),gil_free=True)
    assert names==['q'] and dimension==4+2*g+t
    vg=jax.jit(jax.value_and_grad(lambda u:jax_log_density(u,d)))
    q=canonical_starts(d,4)[0];q[4:4+2*g]=np.linspace(-.2,.3,2*g)
    for logtau in [-7.,-1.,1.]:
        q[1]=logtau;u=to_mixed(q,d);value,gradient=evaluate_cfunc(target,u);ref,grad=vg(jnp.asarray(u))
        np.testing.assert_allclose(value,ref,rtol=1e-10,atol=1e-8)
        np.testing.assert_allclose(gradient,grad,rtol=1e-9,atol=1e-7)


def test_invalid_shape_masks_and_unrepresentable_scales():
    d=data(1,1)
    with pytest.raises(ValueError):to_mixed(np.zeros(6),d)
    for coordinate in [1,3]:
        for scale in [-1000.,1000.]:
            u=np.zeros(7);u[coordinate]=scale
            with np.errstate(over='ignore',under='ignore',invalid='ignore',divide='ignore'):
                with pytest.raises(ValueError):to_mixed(u,d)
                with pytest.raises(ValueError):to_canonical(u,d)
    with pytest.raises(ValueError,match='mask'):to_mixed(np.zeros(7),dict(d,observation_mask=[[True]]))
