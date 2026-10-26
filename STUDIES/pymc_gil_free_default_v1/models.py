"""WP83 breadth models (PREREGISTRATION.md). Every model is built fresh by name.

Data are simulated once from fixed data seeds; `eight` and `hier` come from
callpath_targets.py (WP47, verbatim)."""
from __future__ import annotations

import numpy as np

import callpath_targets as T

MODELS = ["eight", "hier", "logistic", "poisson", "ar1", "simplex_bounded", "data_dims_det",
          "initvals", "initvals_data", "potential", "student_t"]
KIND = {
    "eight": "hierarchical (noncentred Eight Schools)",
    "hier": "hierarchical regression, 157-D",
    "logistic": "GLM, Bernoulli-logit likelihood",
    "poisson": "GLM, Poisson-log likelihood",
    "ar1": "time series: AR(1) with bounded rho ~ Uniform(-1, 1)",
    "simplex_bounded": "transformed/bounded: Dirichlet simplex, Beta, Uniform(0, 10) scale, Multinomial and Binomial likelihoods",
    "data_dims_det": "pm.Data inputs, coords/dims on observed, Deterministics",
    "initvals": "explicit initvals (no pm.Data)",
    "initvals_data": "explicit initvals together with pm.Data (the known PyMC >= 5.28 snapshot limitation)",
    "potential": "pm.Potential soft sum-to-zero constraint",
    "student_t": "robust regression, StudentT likelihood with nu ~ Gamma",
}


def _glm_data(seed, n=200, k=4):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((n, k))
    beta = np.array([0.8, -0.5, 0.3, 0.0])[:k]
    return rng, x, beta


def build(name: str):
    import pymc as pm

    if name in ("eight", "hier"):
        return T.pymc_model(name)
    with pm.Model() as m:
        if name == "logistic":
            rng, x, beta = _glm_data(8383001)
            y = rng.binomial(1, 1 / (1 + np.exp(-(0.2 + x @ beta))))
            a = pm.Normal("a", 0, 2)
            b = pm.Normal("b", 0, 1, shape=x.shape[1])
            pm.Bernoulli("y", logit_p=a + pm.math.dot(x, b), observed=y)
        elif name == "poisson":
            rng, x, beta = _glm_data(8383002)
            y = rng.poisson(np.exp(0.5 + 0.5 * (x @ beta)))
            a = pm.Normal("a", 0, 2)
            b = pm.Normal("b", 0, 1, shape=x.shape[1])
            pm.Poisson("y", mu=pm.math.exp(a + pm.math.dot(x, b)), observed=y)
        elif name == "ar1":
            rng = np.random.default_rng(8383003)
            y = np.zeros(200)
            for t in range(1, 200):
                y[t] = 0.3 + 0.7 * y[t - 1] + 0.5 * rng.standard_normal()
            c = pm.Normal("c", 0, 1)
            rho = pm.Uniform("rho", -1, 1)
            sigma = pm.HalfNormal("sigma", 1)
            pm.Normal("y", c + rho * y[:-1], sigma, observed=y[1:])
        elif name == "simplex_bounded":
            rng = np.random.default_rng(8383004)
            counts = rng.multinomial(300, [0.5, 0.3, 0.15, 0.05])
            k = rng.binomial(20, 0.3, size=30)
            z = rng.normal(1.0, 2.0, size=50)
            w = pm.Dirichlet("w", np.ones(4))
            p = pm.Beta("p", 2, 2)
            s = pm.Uniform("s", 0, 10)
            pm.Multinomial("counts", n=300, p=w, observed=counts)
            pm.Binomial("k", n=20, p=p, observed=k)
            pm.Normal("z", 0, s, observed=z)
        elif name == "data_dims_det":
            rng = np.random.default_rng(8383005)
            xv = rng.standard_normal(60)
            g = np.repeat(np.arange(6), 10)
            yv = 1.0 + 0.5 * xv + rng.normal(0, 0.3, 6)[g] + rng.normal(0, 0.5, 60)
            m.add_coords({"obs": np.arange(60), "group": np.arange(6)})
            x = pm.Data("x", xv, dims="obs")
            gi = pm.Data("g", g, dims="obs")
            a = pm.Normal("a", 0, 5, dims="group")
            b = pm.Normal("b", 0, 1)
            sigma = pm.HalfNormal("sigma", 1)
            mu = pm.Deterministic("mu", a[gi] + b * x, dims="obs")
            pm.Deterministic("effect_ratio", b / sigma)
            pm.Normal("y", mu, sigma, observed=yv, dims="obs")
        elif name in ("initvals", "initvals_data"):
            rng = np.random.default_rng(8383006)
            xv = rng.standard_normal(40)
            yv = 0.7 * xv + rng.normal(0, 0.4, 40)
            x = pm.Data("x", xv) if name == "initvals_data" else xv
            sigma = pm.HalfNormal("sigma", 1.0, initval=0.7)
            beta = pm.Normal("beta", 0.0, 1.0, initval=0.2)
            pm.Normal("y", beta * x, sigma, observed=yv)
        elif name == "potential":
            rng = np.random.default_rng(8383007)
            yv = rng.normal(np.array([1.0, -0.5, -0.5]).repeat(10), 1.0)
            th = pm.Normal("theta", 0, 3, shape=3)
            pm.Potential("sum_to_zero", pm.logp(pm.Normal.dist(0, 0.01), th.sum()))
            pm.Normal("y", th.repeat(10), 1.0, observed=yv)
        elif name == "student_t":
            rng, x, beta = _glm_data(8383008, n=150, k=2)
            yv = 0.5 + x @ beta + rng.standard_t(3, 150)
            a = pm.Normal("a", 0, 2)
            b = pm.Normal("b", 0, 1, shape=2)
            sigma = pm.HalfNormal("sigma", 2)
            nu = pm.Gamma("nu", 2, 0.1)
            pm.StudentT("y", nu=nu, mu=a + pm.math.dot(x, b), sigma=sigma, observed=yv)
        else:
            raise ValueError(name)
    return m
