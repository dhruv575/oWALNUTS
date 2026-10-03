"""Correctness only: no sampling or performance qualification."""
import unittest
import numpy as np
import local_level
import local_observation_residual as residual


class ResidualTests(unittest.TestCase):
    def data(self, t=7):
        return dict(y=np.linspace(-.2,.3,t).tolist(), dt=np.linspace(.2,1.8,t-1).tolist(),
                    anchor=.1, anchor_mode='exogenous', nu=5.)

    def points(self, data):
        t=len(data['y'])
        for lo,lr in [(-2.5,-2.1),(-9.,-1.),(-1.,-9.),(2.,1.)]:
            yield np.r_[np.linspace(-.7,.9,t),lo,lr]

    def test_roundtrip_and_normalized_jacobian(self):
        for t in [1,7,128]:
            data=self.data(t)
            starts=residual.canonical_starts(data,4)
            np.testing.assert_allclose(residual.to_canonical(residual.to_residual(starts,data),data),starts,atol=1e-14)
            for u in self.points(data):
                q=residual.to_canonical(u,data)
                np.testing.assert_allclose(residual.to_residual(q,data),u,rtol=1e-10,atol=1e-10)
                expected=local_level.log_density(q,data)+t*u[-2]
                np.testing.assert_allclose(residual.log_density(u,data),expected,rtol=1e-12,atol=1e-9)

    def test_bad_shapes_and_inputs(self):
        data=self.data()
        for q in [np.zeros(8),np.full(9,np.nan),0.]:
            with self.assertRaises(ValueError):residual.to_canonical(q,data)
        for chains in [0,1.5,True]:
            with self.assertRaises(ValueError):residual.canonical_starts(data,chains)
        for lo in [-1000.,1000.]:
            q=np.r_[np.ones(7),lo,-2.]
            with self.assertRaises(ValueError):residual.to_residual(q,data)
            with self.assertRaises(ValueError):residual.to_canonical(q,data)

    def test_jax_change_of_variables_gradient(self):
        import jax
        jax.config.update('jax_enable_x64',True)
        import jax.numpy as jnp
        from jax.scipy.special import gammaln
        for t in [1,7]:
            data=self.data(t)
            def transformed(u):
                q=jnp.concatenate((jnp.asarray(data['y'])+jnp.exp(u[-2])*u[:-2],u[-2:]))
                return local_level.log_density(q,data,jnp,gammaln)+t*u[-2]
            independent=jax.value_and_grad(lambda u:residual.log_density(u,data,jnp))
            original=jax.value_and_grad(transformed)
            for u in self.points(data):
                lp,g=independent(u); ref,rg=original(u)
                np.testing.assert_allclose(lp,ref,rtol=1e-12,atol=1e-9)
                np.testing.assert_allclose(g,rg,rtol=1e-10,atol=1e-8)

    def test_public_compilation_density_gradient_and_snapshot(self):
        import jax
        jax.config.update('jax_enable_x64',True)
        import jax.numpy as jnp
        from pymc_workflow import evaluate_cfunc
        for t in [1,7]:
            data=self.data(t)
            start=residual.to_residual(residual.canonical_starts(data,4),data)[2]
            target, dim, initial, names, unravel=residual.compile_target(data,initial=start)
            self.assertEqual(dim,t+2)
            np.testing.assert_array_equal(initial,start)
            vg=jax.value_and_grad(lambda u:residual.log_density(u,data,jnp))
            for u in self.points(data):
                lp,g=evaluate_cfunc(target,u); ref,rg=vg(u)
                np.testing.assert_allclose(lp,ref,rtol=1e-10,atol=1e-8)
                np.testing.assert_allclose(g,rg,rtol=1e-9,atol=1e-7)
            before=evaluate_cfunc(target,start)
            data['y'][0]+=2.
            after=evaluate_cfunc(target,start)
            self.assertEqual(before[0],after[0])
            np.testing.assert_array_equal(before[1],after[1])


if __name__ == '__main__':unittest.main()
