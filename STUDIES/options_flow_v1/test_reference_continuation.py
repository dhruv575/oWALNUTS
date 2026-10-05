import unittest
import numpy as np
import jax
jax.config.update('jax_enable_x64', True)
import jax.numpy as jnp
from reference_continuation import ContinuedReference


class ContinuationTests(unittest.TestCase):
    @unittest.skipUnless(jax.local_device_count() >= 4, 'Requires four configured local JAX devices')
    def test_parallel_chunks_preserve_draws_and_frozen_adaptation(self):
        potential=lambda q:.5*jnp.sum(q*q/jnp.array([.5,2.]))
        starts=np.array([[-.4,.2],[.3,-.5],[.1,.6],[-.2,-.3]])
        split=ContinuedReference(potential,starts,99068013,warmup=20,batch_size=8,target_accept=.9,chain_method='parallel')
        full=ContinuedReference(potential,starts,99068013,warmup=20,batch_size=16,target_accept=.9,chain_method='parallel')
        split.adapt();full.adapt();digest=split.adaptation_sha256
        split.append();split.append();full.append()
        np.testing.assert_array_equal(split.samples,full.samples)
        self.assertEqual(split.samples.shape,(4,16,2))
        self.assertEqual(split.adaptation_sha256,digest)
        self.assertEqual(split.adaptation_sha256,full.adaptation_sha256)
        self.assertEqual(split.checkpoints[-1]['end_iterations'],[36]*4)
        self.assertEqual(split.divergences,full.divergences)

    def test_parallel_refuses_silent_device_fallback(self):
        from unittest.mock import patch
        with patch('reference_continuation.jax.local_device_count',return_value=1):
            with self.assertRaisesRegex(ValueError,'local device'):
                ContinuedReference(lambda q:jnp.sum(q*q),np.zeros((4,2)),1,chain_method='parallel')
        with self.assertRaises(ValueError):
            ContinuedReference(lambda q:jnp.sum(q*q),[[0.]],1,chain_method='invalid')

    def test_chunks_match_uninterrupted_retention_and_freeze_adaptation(self):
        potential = lambda q: .5*jnp.sum(q*q/jnp.array([.5, 2.]))
        starts = np.array([[-.4, .2], [.3, -.5]])
        split = ContinuedReference(potential, starts, 99068011, warmup=20, batch_size=8)
        full = ContinuedReference(potential, starts, 99068011, warmup=20, batch_size=16)
        split.adapt(); full.adapt()
        split.append(); split.append(); full.append()
        np.testing.assert_array_equal(split.samples, full.samples)
        self.assertEqual(split.adaptation_sha256, full.adaptation_sha256)
        self.assertEqual(split.divergences, full.divergences)
        self.assertEqual(split.checkpoints[0]['end_iterations'], [28, 28])
        self.assertEqual(split.checkpoints[1]['start_iterations'], [28, 28])
        self.assertEqual(split.checkpoints[1]['end_iterations'], [36, 36])
        with self.assertRaises(RuntimeError): split.adapt()

    def test_higher_acceptance_preserves_continuation_and_frozen_adaptation(self):
        potential=lambda q:.5*jnp.sum(q*q/jnp.array([.5,2.]))
        starts=np.array([[-.4,.2],[.3,-.5]])
        split=ContinuedReference(potential,starts,99068012,warmup=20,batch_size=8,target_accept=.9)
        full=ContinuedReference(potential,starts,99068012,warmup=20,batch_size=16,target_accept=.9)
        self.assertEqual(split.target_accept,.9)
        split.adapt();full.adapt();digest=split.adaptation_sha256
        split.append();split.append();full.append()
        np.testing.assert_array_equal(split.samples,full.samples)
        self.assertEqual(split.adaptation_sha256,digest)
        self.assertEqual(split.adaptation_sha256,full.adaptation_sha256)
        self.assertEqual(split.divergences,full.divergences)
        self.assertEqual(split.checkpoints[-1]['end_iterations'],[36,36])

    def test_target_accept_reaches_nuts_constructor(self):
        from unittest.mock import patch
        with patch('reference_continuation.NUTS') as nuts, patch('reference_continuation.MCMC'):
            ContinuedReference(lambda q:0.,[[0.]],1,target_accept=.9)
            self.assertEqual(nuts.call_args.kwargs['target_accept_prob'],.9)

    def test_target_accept_validation_and_default(self):
        potential=lambda q:jnp.sum(q*q)
        for value in [0.,1.,-.1,1.1,np.nan,np.inf,-np.inf,True,False,'0.9',None]:
            with self.assertRaises(ValueError):ContinuedReference(potential,[[0.]],1,target_accept=value)
        self.assertEqual(ContinuedReference(potential,[[0.]],1).target_accept,.8)

    def test_requires_warmup_and_valid_starts(self):
        fit = ContinuedReference(lambda q: jnp.sum(q*q), [[0.], [1.]], 1, 2, 2)
        with self.assertRaises(RuntimeError): fit.append()
        with self.assertRaises(RuntimeError): _ = fit.samples
        with self.assertRaises(ValueError): ContinuedReference(lambda q: 0., [[np.nan]], 1)


if __name__ == '__main__': unittest.main()
