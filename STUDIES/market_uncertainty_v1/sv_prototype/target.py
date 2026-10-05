"""Research target: heavy-tailed returns with flow in mean and log volatility.

Noncentered latent path, exact normalized density and reverse-mode gradient.
Priors are explicit inputs; no market-prior calibration or sampler adapter here.
"""
from dataclasses import dataclass
import math
import numpy as np
from scipy.special import gammaln


@dataclass(frozen=True)
class Priors:
    mu_mean: float
    mu_sd: float
    log_sigma_mean: float
    log_sigma_sd: float
    beta_sd: float
    gamma_sd: float


class Target:
    """q = [mu, log_sigma, beta[P], gamma[K], z[T]].

    x[i], w[i] must be known before y[i]. All scheduled latent transitions are
    retained. Unknown volatility covariates are rejected, never filled with zero.
    w may have zero columns for the no-flow-in-scale ablation.

    The initial state has mean mu + w[0] @ gamma and variance
    sigma**2/(1-rho**2): the variance is the no-flow stationary baseline,
    not a claim that a forced path starts in its stationary distribution.
    Priors are directly on log_sigma and standard-normal innovations z;
    no additional log-sigma or path Jacobian belongs in this coordinate density.
    """

    def __init__(self, y, x, w, observed, *, rho, nu, priors):
        y, x, w = [np.array(a, dtype=np.float64, copy=True) for a in (y, x, w)]
        observed = np.array(observed, copy=True)
        if (y.ndim != 1 or not len(y) or x.ndim != 2 or w.ndim != 2
                or x.shape[0] != len(y) or w.shape[0] != len(y)
                or observed.shape != y.shape or observed.dtype != np.bool_):
            raise ValueError('Expected T outcomes/mask and T-by-P/T-by-K covariates')
        if not np.isfinite(w).all() or not np.isfinite(x[observed]).all() or not np.isfinite(y[observed]).all():
            raise ValueError('Finite observed data and every volatility covariate required')
        if not math.isfinite(rho) or not abs(rho) < 1 or not math.isfinite(nu) or nu <= 2:
            raise ValueError('Stationary baseline rho and finite-variance Student-t required')
        if not isinstance(priors, Priors) or not all(math.isfinite(v) for v in vars(priors).values()):
            raise ValueError('Explicit finite prior parameters required')
        if min(priors.mu_sd, priors.log_sigma_sd, priors.beta_sd, priors.gamma_sd) <= 0:
            raise ValueError('Positive prior scales required')
        y[~observed] = 0
        x[~observed] = 0
        for a in (y, x, w, observed):
            a.setflags(write=False)
        self.y, self.x, self.w, self.observed = y, x, w, observed
        self.rho, self.nu, self.priors = float(rho), float(nu), priors
        self.t, self.p, self.k = len(y), x.shape[1], w.shape[1]
        self.offset = 2 + self.p + self.k
        self.dimension = self.offset + self.t

    def unpack(self, q):
        q = np.asarray(q, dtype=np.float64)
        if q.shape != (self.dimension,) or not np.isfinite(q).all():
            raise ValueError('Finite exact-dimension parameter vector required')
        return q[0], q[1], q[2:2+self.p], q[2+self.p:self.offset], q[self.offset:]

    def path(self, q):
        mu, logsigma, beta, gamma, z = self.unpack(q)
        sigma = math.exp(logsigma)
        h = np.empty(self.t)
        h[0] = mu + self.w[0] @ gamma + sigma * z[0] / math.sqrt(1-self.rho**2)
        for i in range(1, self.t):
            h[i] = mu + self.rho*(h[i-1]-mu) + self.w[i] @ gamma + sigma*z[i]
        return h

    def value_gradient(self, q):
        q = np.asarray(q, dtype=np.float64)
        mu, logsigma, beta, gamma, z = self.unpack(q)
        pr = self.priors
        means = np.zeros(self.dimension)
        means[:2] = pr.mu_mean, pr.log_sigma_mean
        scales = np.ones(self.dimension)
        scales[:2] = pr.mu_sd, pr.log_sigma_sd
        scales[2:2+self.p] = pr.beta_sd
        scales[2+self.p:self.offset] = pr.gamma_sd
        standardized = (q-means)/scales
        lp = float(np.sum(-.5*standardized**2 - np.log(scales) - .5*np.log(2*np.pi)))
        gradient = -(q-means)/scales**2
        h = self.path(q)
        residual = self.y - self.x @ beta
        with np.errstate(divide='ignore'):
            logabs = np.log(np.abs(residual))
        logdenom = np.logaddexp(np.log(self.nu)+h, 2*logabs)
        logratio = 2*logabs - np.log(self.nu)-h
        likelihood = (gammaln((self.nu+1)/2)-gammaln(self.nu/2)
                      -.5*np.log(self.nu*np.pi)-.5*h
                      -.5*(self.nu+1)*np.logaddexp(0., logratio))
        lp += float(likelihood[self.observed].sum())
        dh = np.where(self.observed, -.5+.5*(self.nu+1)*np.exp(2*logabs-logdenom), 0.)
        dlocation = np.where(self.observed, (self.nu+1)*np.sign(residual)*np.exp(logabs-logdenom), 0.)
        gradient[2:2+self.p] += self.x.T @ dlocation
        sigma = math.exp(logsigma)
        for i in range(self.t-1, -1, -1):
            gradient[2+self.p:self.offset] += dh[i]*self.w[i]
            multiplier = sigma / math.sqrt(1-self.rho**2) if i == 0 else sigma
            gradient[self.offset+i] += dh[i]*multiplier
            gradient[1] += dh[i]*multiplier*z[i]
            gradient[0] += dh[i]*(1 if i == 0 else 1-self.rho)
            if i:
                dh[i-1] += self.rho*dh[i]
        return lp, gradient

    def predictive_draw(self, q, x_next, w_next, rng):
        """One next return per posterior draw, including state and observation noise."""
        mu, logsigma, beta, gamma, _ = self.unpack(q)
        x_next, w_next = np.asarray(x_next), np.asarray(w_next)
        if x_next.shape != (self.p,) or w_next.shape != (self.k,) or not np.isfinite(x_next).all() or not np.isfinite(w_next).all():
            raise ValueError('Finite future-origin covariates of exact shape required')
        h = mu + self.rho*(self.path(q)[-1]-mu) + w_next @ gamma + math.exp(logsigma)*rng.normal()
        return float(x_next @ beta + math.exp(h/2)*rng.standard_t(self.nu))
