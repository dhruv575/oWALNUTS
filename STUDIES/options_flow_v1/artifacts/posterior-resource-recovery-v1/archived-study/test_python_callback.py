"""Run these checks in the isolated environment containing the built extension."""
import importlib.util
import unittest
import numpy as np


@unittest.skipUnless(importlib.util.find_spec('owalnuts'), 'Source-built Python extension not installed in this environment')
class PublicPythonTests(unittest.TestCase):
    def test_local_target_matches_normalized_density_and_physical_starts(self):
        from python_callback import target_and_starts
        from local_level import simulate, log_density
        fixture = simulate(99067011, 8, 2)
        target, starts, initial, canonical = target_and_starts(fixture, 'local_level', 4)
        self.assertEqual(starts.shape, (4, 10))
        np.testing.assert_array_equal(starts, initial)
        self.assertFalse(np.array_equal(starts[0], starts[1]))
        value, gradient = target(starts[0])
        self.assertAlmostEqual(value, log_density(starts[0], fixture['data']), places=9)
        self.assertEqual(gradient.shape, (10,))
        np.testing.assert_array_equal(canonical(starts[:, None, :])[:, 0], initial)

    def test_flow_transformed_target_preserves_physical_starts(self):
        from python_callback import target_and_starts
        from model import simulate, log_density
        fixture = simulate(99067012, 8, 2, 2)
        target, starts, initial, canonical = target_and_starts(fixture, 'flow', 4)
        physical = canonical(starts[:, None, :])[:, 0]
        np.testing.assert_allclose(physical, initial, atol=1e-12)
        value, gradient = target(starts[0])
        jacobian = 8*initial[0, 3]-.5*np.log(1-fixture['data']['rho']**2)
        self.assertAlmostEqual(value, log_density(initial[0], fixture['data'])+jacobian, places=9)
        self.assertEqual(gradient.shape, starts[0].shape)
        self.assertTrue(np.isfinite(gradient).all())


if __name__ == '__main__':
    unittest.main()
