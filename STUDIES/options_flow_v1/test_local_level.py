import unittest
import numpy as np
from scipy.stats import norm, t
from local_level import (application_data, canonicalize, log_density, noncenter,
                         predict, simulate, validate)


class LocalLevelTests(unittest.TestCase):
    def test_normalized_target_matches_independent_scipy(self):
        f = simulate(8821, periods=7)
        q = np.asarray(f['truth']); d = f['data']; h = q[:-2]
        expected = norm.logpdf(q[-2:], np.log([.08,.12]), 1).sum()
        expected += norm.logpdf(h[0], d['anchor'], 1.5)
        expected += norm.logpdf(h[1:], h[:-1], np.exp(q[-1])).sum()
        expected += t.logpdf(d['y'], 5, loc=h, scale=np.exp(q[-2])).sum()
        self.assertAlmostEqual(log_density(q,d), expected, places=11)

    def test_noncentered_density_has_correct_jacobian(self):
        f = simulate(8822, periods=6); d = f['data']
        d['dt'] = [.5,1.,2.,3.,.25]
        q = np.asarray(f['truth']); z = noncenter(q,d)
        np.testing.assert_allclose(canonicalize(z,d,'noncentered'),q,atol=1e-14)
        logdet = np.log(1.5)+5*q[-1]+.5*np.log(d['dt']).sum()
        self.assertAlmostEqual(log_density(z,d,parameterization='noncentered'),
                               log_density(q,d)+logdet,places=10)

    def test_anchor_semantics_are_explicit(self):
        f = simulate(8823,periods=3,anchor=2.)
        self.assertEqual(f['data']['anchor'],2.)
        self.assertNotEqual(f['data']['anchor'],f['data']['y'][0])
        d = application_data(f['data']['y'])
        self.assertEqual(d['anchor'],d['y'][0])
        d['anchor'] += 1
        with self.assertRaises(ValueError): validate(d)

    def test_predictive_noise_and_joint_horizons(self):
        d = application_data([0.])
        q = np.tile([0.,np.log(.3),np.log(.2)],(100000,1))
        p = predict(q,d,[1.,4.],8824)
        latent, obs = p['latent_log'],p['observed_log']
        np.testing.assert_allclose(latent.var(axis=0),[.04,.16],rtol=.02)
        self.assertAlmostEqual(np.cov(latent.T)[0,1],.04,delta=.002)
        np.testing.assert_allclose((obs-latent).var(axis=0), [.15,.15],rtol=.04)
        self.assertGreater(np.quantile(obs[:,0],.95),np.quantile(latent[:,0],.95))
        np.testing.assert_array_equal(predict(q[:5],d,[1.,4.],2)['observed_log'],
                                      predict(q[:5],d,[1.,4.],2)['observed_log'])

    def test_single_period_and_invalid_horizons(self):
        f = simulate(8825,periods=1,holdout=0)
        q = np.asarray(f['truth']); d=f['data']
        self.assertTrue(np.isfinite(log_density(q,d)))
        np.testing.assert_allclose(canonicalize(noncenter(q,d),d,'noncentered'),q)
        with self.assertRaises(ValueError): predict(q[None,:],d,[2.,1.],1)

    def test_jax_gradient_matches_finite_difference(self):
        try:
            import jax
            jax.config.update('jax_enable_x64',True)
            import jax.numpy as jnp
            from jax.scipy.special import gammaln
        except ImportError:
            self.skipTest('JAX unavailable')
        f=simulate(8826,periods=5); d=f['data']
        for mode in ['centered','noncentered']:
            q=np.asarray(f['truth'])
            if mode=='noncentered': q=noncenter(q,d)
            grad=np.asarray(jax.grad(lambda a:log_density(a,d,jnp,gammaln,mode))(jnp.asarray(q)))
            eps=1e-5; eye=np.eye(len(q))*eps
            numeric=np.array([(log_density(q+v,d,parameterization=mode)-log_density(q-v,d,parameterization=mode))/(2*eps) for v in eye])
            np.testing.assert_allclose(grad,numeric,rtol=2e-5,atol=2e-5)


if __name__=='__main__': unittest.main()
