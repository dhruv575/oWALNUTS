import unittest
import numpy as np
from geometry import FixedGeometry,solve_lower,solve_upper,tridiagonal_cholesky,transformed_log_density


def data(t=8,g=2):
    return dict(y=np.zeros((t,g)).tolist(),x=np.zeros((t,g)).tolist(),rho=.95,nu=5.)


class GeometryTests(unittest.TestCase):
    def test_inverse_and_determinant_small_and_long(self):
        rng=np.random.default_rng(611)
        for t in [1,2,1000]:
            for shear in [False,True]:
                geom=FixedGeometry.from_data(data(t),shear)
                q=rng.normal(size=(2,3,geom.dimension))
                np.testing.assert_allclose(geom.to_canonical(geom.to_transformed(q)),q,atol=1e-13)
                self.assertTrue(np.isfinite(geom.log_abs_det_jacobian))
                if t<=2:
                    zero=np.zeros(geom.dimension)
                    jac=np.stack([geom.to_canonical(e)-geom.to_canonical(zero) for e in np.eye(geom.dimension)],axis=1)
                    self.assertAlmostEqual(np.linalg.slogdet(jac)[1],geom.log_abs_det_jacobian,places=12)

    def test_gaussian_path_whitening_mass_is_precision(self):
        geom=FixedGeometry.from_data(data())
        k=np.diag(geom.precision_diagonal)+np.diag(geom.prior_off_diagonal,1)+np.diag(geom.prior_off_diagonal,-1)
        l=np.diag(geom.lower_diagonal)+np.diag(geom.lower_subdiagonal,-1)
        np.testing.assert_allclose(l@l.T,k,atol=1e-13)
        jac=solve_upper(np.eye(len(l)),geom.lower_diagonal,geom.lower_subdiagonal).T
        np.testing.assert_allclose(jac.T@k@jac,np.eye(len(l)),atol=1e-13)
        self.assertAlmostEqual(-.5*np.linalg.slogdet(k)[1],geom.log_abs_det_jacobian,places=12)

    def test_shear_cancels_mean_cross_hessian(self):
        geom=FixedGeometry.from_data(data(),True);n=len(geom.shear)
        q=np.diag(geom.prior_diagonal)+np.diag(geom.prior_off_diagonal,1)+np.diag(geom.prior_off_diagonal,-1)
        k=q+np.diag(geom.precision_diagonal-geom.prior_diagonal)
        b=-q@np.ones(n)
        hess=np.block([[np.array([[1+np.ones(n)@q@np.ones(n)]]),b[None,:]], [b[:,None],k]])
        j=np.zeros((n+1,n+1));j[0,0]=1;j[1:,0]=geom.shear
        j[1:,1:]=solve_upper(np.eye(n),geom.lower_diagonal,geom.lower_subdiagonal).T
        whitened=j.T@hess@j
        np.testing.assert_allclose(whitened[0,1:],0.,atol=1e-13)
        np.testing.assert_allclose(whitened[1:,1:],np.eye(n),atol=1e-13)
        self.assertGreater(np.linalg.eigvalsh(whitened).min(),0.)

    def test_no_observed_or_truth_dependency(self):
        d=data();a=FixedGeometry.from_data(d,True)
        d['y']=np.full((8,2),1e100).tolist();d['x']=np.full((8,2),-99).tolist();d['truth']=[999]
        b=FixedGeometry.from_data(d,True)
        np.testing.assert_array_equal(a.lower_diagonal,b.lower_diagonal)
        np.testing.assert_array_equal(a.shear,b.shear)

    def test_invalid_precision_rejected(self):
        with self.assertRaises(ValueError):tridiagonal_cholesky([1.,1.],[2.])
        with self.assertRaises(ValueError):FixedGeometry.from_data(dict(data(),rho=1.))

    def test_jax_solve_density_and_gradient_contract(self):
        import jax
        jax.config.update('jax_enable_x64',True)
        import jax.numpy as jnp
        from model import log_density
        from jax.scipy.special import gammaln
        rng=np.random.default_rng(613)
        for t in [1,2,12]:
            d=data(t)
            for shear in [False,True]:
                geom=FixedGeometry.from_data(d,shear)
                q=rng.normal(size=geom.dimension);q[3]=-1.5
                u=geom.to_transformed(q)
                np.testing.assert_allclose(geom.to_canonical(jnp.asarray(u),jnp),q,atol=1e-13)
                value,grad=jax.value_and_grad(lambda z:transformed_log_density(z,d,geom,jnp))(jnp.asarray(u))
                expected,canonical_grad=jax.value_and_grad(lambda z:log_density(z,d,jnp,gammaln))(jnp.asarray(q))
                self.assertAlmostEqual(float(value-expected),geom.log_abs_det_jacobian,places=10)
                np.testing.assert_allclose(grad,geom.pullback_gradient(canonical_grad),rtol=2e-11,atol=2e-10)
                np.testing.assert_allclose(grad,geom.pullback_gradient(canonical_grad,jnp),rtol=2e-11,atol=2e-10)


if __name__=='__main__':unittest.main()
