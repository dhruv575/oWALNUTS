import unittest
import numpy as np
from target import Target, Priors
from synthetic import ABLATIONS, ILLUSTRATIVE_PRIORS, simulate, covariates, prior_predictive

class Tests(unittest.TestCase):
    def test_all_ablations_match_target_initial_and_transitions(self):
        for n in (1, 2, 128):
            for arm in ABLATIONS:
                f = simulate(n, 4101, arm, priors=ILLUSTRATIVE_PRIORS)
                m = Target(**f['data'], priors=ILLUSTRATIVE_PRIORS)
                np.testing.assert_allclose(m.path(f['truth']['q']), f['truth']['h'], atol=1e-14)
                self.assertTrue(np.isfinite(m.value_gradient(f['truth']['q'])[0]))
                self.assertEqual(m.p, 2 if arm in ('mean','both') else 1)
                self.assertEqual(m.k, 2 if arm in ('scale','both') else 0)

    def test_mask_and_length_do_not_change_causal_covariates(self):
        a = simulate(12, 4102, 'both', priors=ILLUSTRATIVE_PRIORS)
        mask = np.arange(12)%2 == 0
        b = simulate(12, 4102, 'both', priors=ILLUSTRATIVE_PRIORS, observed=mask)
        for key in ('q','h','y_complete'):
            np.testing.assert_array_equal(a['truth'][key], b['truth'][key])
        self.assertTrue(np.isnan(b['data']['y'][~mask]).all())
        for short, long in zip(covariates(12,'both'),covariates(24,'both')):
            np.testing.assert_array_equal(short, long[:12])

    def test_extreme_prior_is_exposed_not_normalized(self):
        huge = Priors(1500., .1, -3., .1, .002, .03)
        r = prior_predictive(3, [4103,4104], 'neither', priors=huge)
        self.assertEqual(r['intended_returns'], 6)
        self.assertEqual(r['nonfinite_returns'], 6)
        self.assertIsNone(r['finite_only_abs_return_quantiles'])
        self.assertFalse(r['qualified'])

    def test_deterministic_diagnostics_and_seed_validation(self):
        kwargs = dict(priors=ILLUSTRATIVE_PRIORS)
        a = prior_predictive(8, [4105,4106], 'both', **kwargs)
        self.assertEqual(a, prior_predictive(8, [4105,4106], 'both', **kwargs))
        with self.assertRaises(ValueError): prior_predictive(8,[1,1],'both',**kwargs)
        with self.assertRaises(ValueError): simulate(8,True,'both',**kwargs)

if __name__ == '__main__': unittest.main()
