import unittest
import numpy as np
import jax
jax.config.update('jax_enable_x64', True)
import jax.numpy as jnp
from reference_continuation import ContinuedReference


class ContinuationTests(unittest.TestCase):
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

    def test_requires_warmup_and_valid_starts(self):
        fit = ContinuedReference(lambda q: jnp.sum(q*q), [[0.], [1.]], 1, 2, 2)
        with self.assertRaises(RuntimeError): fit.append()
        with self.assertRaises(RuntimeError): _ = fit.samples
        with self.assertRaises(ValueError): ContinuedReference(lambda q: 0., [[np.nan]], 1)


if __name__ == '__main__': unittest.main()
