import unittest
import numpy as np
from scipy.stats import norm, t
from target import Target, Priors


PRIOR = Priors(-10., 2., np.log(.2), .5, .02, .15)


def fixture(k=2):
    return Target([.01, np.nan, -.02, 0.], [[1, .2], [np.nan, np.nan], [1, -.4], [1, .8]],
                  np.array([[.1, -.2], [.4, .1], [-.2, .7], [.8, -.1]])[:, :k],
                  [True, False, True, True], rho=.8, nu=5., priors=PRIOR)


def oracle(model, q):
    """Centered state density + explicit NC change-of-variables Jacobian."""
    mu, logsigma, beta, gamma, z = model.unpack(q)
    sigma = np.exp(logsigma)
    h = model.path(q)
    initial_sd = sigma/np.sqrt(1-model.rho**2)
    value = norm.logpdf(mu, PRIOR.mu_mean, PRIOR.mu_sd)
    value += norm.logpdf(logsigma, PRIOR.log_sigma_mean, PRIOR.log_sigma_sd)
    value += norm.logpdf(beta, 0, PRIOR.beta_sd).sum()
    value += norm.logpdf(gamma, 0, PRIOR.gamma_sd).sum()
    value += norm.logpdf(h[0], mu+model.w[0]@gamma, initial_sd)
    for i in range(1, model.t):
        value += norm.logpdf(h[i], mu+model.rho*(h[i-1]-mu)+model.w[i]@gamma, sigma)
    value += np.log(initial_sd)+(model.t-1)*logsigma
    for i in np.flatnonzero(model.observed):
        value += t.logpdf(model.y[i], model.nu, loc=model.x[i]@beta, scale=np.exp(h[i]/2))
    return value


class Tests(unittest.TestCase):
    def test_short_path_zero_residual_closed_form_gradient(self):
        # Hand-derived recurrence, independent of path() and its centered oracle.
        for n in (1, 2):
            model = Target(np.zeros(n), np.ones((n, 1)),
                           np.array([[.3], [-.7]])[:n], np.ones(n, dtype=bool),
                           rho=-.6, nu=5., priors=PRIOR)
            q = np.array([-9., np.log(.4), 0., .2, .5, -.4])[:4+n]
            mu, log_sigma, _, gamma = q[:4]
            sigma = np.exp(log_sigma)
            a = sigma/.8
            h0 = mu+.3*gamma+a*q[4]
            expected_h = [h0]
            if n == 2:
                expected_h.append(mu-.6*(h0-mu)-.7*gamma+sigma*q[5])
            np.testing.assert_allclose(model.path(q), expected_h, atol=1e-14)
            means = np.array([PRIOR.mu_mean, PRIOR.log_sigma_mean, 0., 0.]+[0.]*n)
            sd = np.array([PRIOR.mu_sd, PRIOR.log_sigma_sd, PRIOR.beta_sd, PRIOR.gamma_sd]+[1.]*n)
            expected = -(q-means)/sd**2
            # At exactly zero residual d loglik/dh=-1/2, d loglik/d beta=0.
            adj0 = -.5 if n == 1 else -.5*(1-.6)
            expected[0] -= .5*n
            expected[1] += adj0*a*q[4]
            expected[3] += adj0*.3
            expected[4] += adj0*a
            if n == 2:
                expected[1] -= .5*sigma*q[5]
                expected[3] += .35
                expected[5] -= .5*sigma
            value, actual = model.value_gradient(q)
            expected_value = norm.logpdf(q, means, sd).sum()
            expected_value += t.logpdf(np.zeros(n), 5., scale=np.exp(np.array(expected_h)/2)).sum()
            self.assertAlmostEqual(value, expected_value, places=12)
            np.testing.assert_allclose(actual, expected, atol=1e-13)

    def test_all_missing_is_exact_prior_with_empty_covariate_blocks(self):
        model = Target([np.nan, np.inf], np.empty((2, 0)), np.empty((2, 0)),
                       [False, False], rho=.99, nu=5., priors=PRIOR)
        q = np.array([-9., -1., .2, -.3])
        means = np.array([PRIOR.mu_mean, PRIOR.log_sigma_mean, 0., 0.])
        sd = np.array([PRIOR.mu_sd, PRIOR.log_sigma_sd, 1., 1.])
        value, gradient = model.value_gradient(q)
        self.assertAlmostEqual(value, norm.logpdf(q, means, sd).sum(), places=12)
        np.testing.assert_allclose(gradient, -(q-means)/sd**2)

    def test_normalized_density_and_gradient_independent_centered_oracle(self):
        rng = np.random.default_rng(982)
        for k in (0, 2):
            model = fixture(k)
            for _ in range(4):
                q = rng.normal(0, .3, model.dimension)
                q[:2] = -10+rng.normal(), np.log(.2)+rng.normal(0, .2)
                q[2:2+model.p] *= .02
                value, gradient = model.value_gradient(q)
                self.assertAlmostEqual(value, oracle(model, q), places=10)
                numeric = []
                for j in range(model.dimension):
                    plus, minus = q.copy(), q.copy()
                    plus[j] += 1e-6
                    minus[j] -= 1e-6
                    numeric.append((oracle(model, plus)-oracle(model, minus))/2e-6)
                np.testing.assert_allclose(gradient, numeric, rtol=3e-6, atol=2e-5)

    def test_missing_row_keeps_state_transition(self):
        model = fixture()
        q = np.zeros(model.dimension)
        q[:2] = -10., np.log(.2)
        changed = q.copy()
        changed[model.offset+1] = 1.
        self.assertNotEqual(model.path(q)[2], model.path(changed)[2])
        _, gradient = model.value_gradient(changed)
        self.assertNotAlmostEqual(gradient[model.offset+1], -1.)

    def test_owned_inputs_and_unknown_scale_covariate_rejected(self):
        model = fixture()
        self.assertFalse(model.y.flags.writeable)
        w = model.w.copy()
        w[1, 0] = np.nan
        with self.assertRaises(ValueError):
            Target(model.y, model.x, w, model.observed, rho=.8, nu=5., priors=PRIOR)

    def test_predictive_contains_observation_and_state_uncertainty(self):
        model = fixture(0)
        q = np.zeros(model.dimension)
        q[:2] = -10., np.log(.2)
        # Independent seeded construction catches omitted future state/noise terms.
        a, b = np.random.default_rng(33), np.random.default_rng(33)
        hnext = -10 + .8*(model.path(q)[-1]+10)+.2*b.normal()
        expected = np.exp(hnext/2)*b.standard_t(5)
        self.assertAlmostEqual(model.predictive_draw(q, [1., .2], [], a), expected, places=14)


if __name__ == '__main__':
    unittest.main()
