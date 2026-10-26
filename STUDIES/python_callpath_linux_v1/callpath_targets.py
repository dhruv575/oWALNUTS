"""Targets of python_callpath_v1 in every call path (see PREREGISTRATION.md).

Every backend uses the same unconstrained layout as PyMC's value variables
(creation order, log transform for positive scales), so a draw means the same
thing in every path:

* ``gauss100``: x (100), standard normal.
* ``eight``: noncentered Eight Schools, (mu, tau_log__, z[8]); mu ~ N(0, 5),
  tau ~ HalfCauchy(5), z ~ N(0, 1), y ~ N(mu + tau z, se).
* ``hier``: hierarchical regression, (mu_beta[3], tau_log__[3], z[50, 3],
  sigma_log__) = 157 coordinates; mu_beta ~ N(0, 5), tau ~ HalfNormal(1),
  z ~ N(0, 1), sigma ~ HalfNormal(1), beta_j = mu_beta + tau * z_j,
  y_ji ~ N(x_ji . beta_j, sigma), 50 groups x 20 observations.

The numpy, numba, JAX and PyTorch densities omit additive constants; PyMC
keeps them. Gradients are identical up to rounding.
"""
from __future__ import annotations

import math

import numpy as np

TARGETS = ["gauss100", "eight", "hier"]
DIM = {"gauss100": 100, "eight": 10, "hier": 157}
Y8 = np.array([28.0, 8.0, -3.0, 7.0, -1.0, 1.0, 18.0, 12.0])
SE8 = np.array([15.0, 10.0, 16.0, 11.0, 9.0, 11.0, 10.0, 18.0])
J, NJ, K = 50, 20, 3
HIER_DATA_SEED = 4747900


def hier_data() -> tuple[np.ndarray, np.ndarray]:
    """(X (J, NJ, K) with intercept column, y (J, NJ)), fixed data seed."""
    rng = np.random.default_rng(HIER_DATA_SEED)
    x = np.ones((J, NJ, K))
    x[..., 1:] = rng.standard_normal((J, NJ, K - 1))
    mu = np.array([1.0, 0.5, -0.3])
    tau = np.array([0.5, 0.3, 0.2])
    beta = mu + tau * rng.standard_normal((J, K))
    y = np.einsum("jik,jk->ji", x, beta) + rng.standard_normal((J, NJ))
    return np.ascontiguousarray(x), np.ascontiguousarray(y)


# ── plain numpy (the README idiom) ───────────────────────────────────────


def numpy_target(name: str):
    if name == "gauss100":
        def f(q):
            return -0.5 * float(q @ q), -q
        return f
    if name == "eight":
        y, se2 = Y8, SE8 ** 2

        def f(q):
            mu, log_tau, z = q[0], q[1], q[2:]
            tau = math.exp(log_tau)
            resid = y - (mu + tau * z)
            lg = resid / se2
            value = (-0.02 * mu * mu - math.log1p(tau * tau / 25.0) + log_tau
                     - 0.5 * float(resid @ lg) - 0.5 * float(z @ z))
            g = np.empty(10)
            g[0] = -mu / 25.0 + lg.sum()
            g[1] = 1.0 - 2.0 * tau * tau / (25.0 + tau * tau) + tau * float(lg @ z)
            g[2:] = tau * lg - z
            return value, g
        return f
    x, y = hier_data()
    n = J * NJ

    def f(q):
        mu = q[0:3]
        log_tau = q[3:6]
        tau = np.exp(log_tau)
        z = q[6:156].reshape(J, K)
        log_sigma = q[156]
        sigma = math.exp(log_sigma)
        beta = mu + tau * z
        resid = y - np.einsum("jik,jk->ji", x, beta)
        ss = float(np.sum(resid * resid))
        inv_s2 = 1.0 / (sigma * sigma)
        value = (-0.02 * float(mu @ mu) + float(np.sum(log_tau - 0.5 * tau * tau)) - 0.5 * float(np.sum(z * z))
                 + log_sigma - 0.5 * sigma * sigma - n * log_sigma - 0.5 * ss * inv_s2)
        gb = np.einsum("ji,jik->jk", resid, x) * inv_s2
        g = np.empty(157)
        g[0:3] = gb.sum(0) - mu / 25.0
        g[3:6] = tau * np.sum(gb * z, 0) + 1.0 - tau * tau
        g[6:156] = (gb * tau - z).ravel()
        g[156] = 1.0 - sigma * sigma - n + ss * inv_s2
        return value, g
    return f


# ── numba: one njit kernel shared by the callable and the cfunc paths ────


def njit_core(name: str, error_model: str = "python"):
    """``core(q, g) -> logp`` compiled with numba (writes the gradient).

    ``error_model="python"`` (numba's default) raises ZeroDivisionError on a
    float division by zero; ``"numpy"`` returns IEEE inf/nan instead
    (amendment A5)."""
    import numba

    if name == "gauss100":
        @numba.njit(cache=False, error_model=error_model)
        def core(q, g):
            s = 0.0
            for i in range(q.shape[0]):
                g[i] = -q[i]
                s += q[i] * q[i]
            return -0.5 * s
        return core
    if name == "eight":
        y, se2 = Y8.copy(), SE8 ** 2

        @numba.njit(cache=False, error_model=error_model)
        def core(q, g):
            mu = q[0]
            log_tau = q[1]
            tau = math.exp(log_tau)
            value = -0.02 * mu * mu - math.log1p(tau * tau / 25.0) + log_tau
            g0 = -mu / 25.0
            g1 = 1.0 - 2.0 * tau * tau / (25.0 + tau * tau)
            for i in range(8):
                z = q[2 + i]
                resid = y[i] - (mu + tau * z)
                lg = resid / se2[i]
                value += -0.5 * resid * lg - 0.5 * z * z
                g0 += lg
                g1 += tau * lg * z
                g[2 + i] = tau * lg - z
            g[0] = g0
            g[1] = g1
            return value
        return core
    x, y = hier_data()
    n = float(J * NJ)

    @numba.njit(cache=False, error_model=error_model)
    def core(q, g):
        tau = np.empty(3)
        value = 0.0
        for k in range(3):
            tau[k] = math.exp(q[3 + k])
            value += -0.02 * q[k] * q[k] + q[3 + k] - 0.5 * tau[k] * tau[k]
            g[k] = -q[k] / 25.0
            g[3 + k] = 1.0 - tau[k] * tau[k]
        log_sigma = q[156]
        sigma = math.exp(log_sigma)
        inv_s2 = 1.0 / (sigma * sigma)
        ss = 0.0
        beta = np.empty(3)
        for j in range(50):
            for k in range(3):
                zjk = q[6 + 3 * j + k]
                value += -0.5 * zjk * zjk
                beta[k] = q[k] + tau[k] * zjk
            gb0 = 0.0
            gb1 = 0.0
            gb2 = 0.0
            for i in range(20):
                r = y[j, i] - (x[j, i, 0] * beta[0] + x[j, i, 1] * beta[1] + x[j, i, 2] * beta[2])
                ss += r * r
                gb0 += r * x[j, i, 0]
                gb1 += r * x[j, i, 1]
                gb2 += r * x[j, i, 2]
            gb0 *= inv_s2
            gb1 *= inv_s2
            gb2 *= inv_s2
            gbs = (gb0, gb1, gb2)
            for k in range(3):
                zjk = q[6 + 3 * j + k]
                g[k] += gbs[k]
                g[3 + k] += tau[k] * gbs[k] * zjk
                g[6 + 3 * j + k] = gbs[k] * tau[k] - zjk
        value += log_sigma - 0.5 * sigma * sigma - n * log_sigma - 0.5 * ss * inv_s2
        g[156] = 1.0 - sigma * sigma - n + ss * inv_s2
        return value
    return core


def njit_callable(name: str):
    """Plain Python callable around the njit kernel (transport control)."""
    core = njit_core(name)
    dim = DIM[name]

    def f(q):
        g = np.empty(dim)
        return core(q, g), g
    return f, core


def cfunc_target(name: str):
    """``owalnuts.from_cfunc`` of the identical njit kernel."""
    import numba
    import owalnuts

    core = njit_core(name)
    dim = DIM[name]

    @numba.cfunc(owalnuts.numba_raw_signature(), nopython=True)
    def raw(n, q_ptr, g_ptr, _user):
        q = numba.carray(q_ptr, (dim,))
        g = numba.carray(g_ptr, (dim,))
        return core(q, g)

    return owalnuts.from_cfunc(raw, dim), raw, core


def cfunc_safe_target(name: str):
    """Amendment A5: the guarded cfunc of a kernel compiled with
    ``error_model="numpy"`` so a division by zero yields inf/nan (caught by
    the guard) instead of a Python exception that cannot cross the C ABI."""
    import numba
    import owalnuts

    core = njit_core(name, error_model="numpy")
    dim = DIM[name]

    @numba.cfunc(owalnuts.numba_raw_signature(), nopython=True, error_model="numpy")
    def raw(n, q_ptr, g_ptr, _user):
        q = numba.carray(q_ptr, (dim,))
        g = numba.carray(g_ptr, (dim,))
        value = core(q, g)
        finite = np.isfinite(value)
        for i in range(dim):
            if not np.isfinite(g[i]):
                finite = False
        if not finite:
            for i in range(dim):
                g[i] = 0.0
            return -np.inf
        return value

    return owalnuts.from_cfunc(raw, dim), raw, core


def cfunc_guarded_target(name: str):
    """Amendment A2: the same njit kernel in a cfunc that applies the callable
    transport's default policy -- any nonfinite value or gradient element
    becomes a zero-density point (gradient zeroed, return -inf)."""
    import numba
    import owalnuts

    core = njit_core(name)
    dim = DIM[name]

    @numba.cfunc(owalnuts.numba_raw_signature(), nopython=True)
    def raw(n, q_ptr, g_ptr, _user):
        q = numba.carray(q_ptr, (dim,))
        g = numba.carray(g_ptr, (dim,))
        value = core(q, g)
        finite = np.isfinite(value)
        for i in range(dim):
            if not np.isfinite(g[i]):
                finite = False
        if not finite:
            for i in range(dim):
                g[i] = 0.0
            return -np.inf
        return value

    return owalnuts.from_cfunc(raw, dim), raw, core


# ── JAX / PyTorch ────────────────────────────────────────────────────────


def jax_logp(name: str):
    import jax
    jax.config.update("jax_enable_x64", True)
    import jax.numpy as jnp

    if name == "gauss100":
        return lambda q: -0.5 * jnp.sum(q * q)
    if name == "eight":
        y, se = jnp.asarray(Y8), jnp.asarray(SE8)

        def logp(q):
            mu, log_tau, z = q[0], q[1], q[2:]
            tau = jnp.exp(log_tau)
            resid = y - (mu + tau * z)
            return (-0.02 * mu * mu - jnp.log1p(tau * tau / 25.0) + log_tau
                    - 0.5 * jnp.sum(resid * resid / se ** 2) - 0.5 * jnp.sum(z * z))
        return logp
    x, y = hier_data()
    xj, yj = jnp.asarray(x), jnp.asarray(y)
    n = J * NJ

    def logp(q):
        mu, log_tau, z, log_sigma = q[0:3], q[3:6], q[6:156].reshape(J, K), q[156]
        tau, sigma = jnp.exp(log_tau), jnp.exp(log_sigma)
        resid = yj - jnp.einsum("jik,jk->ji", xj, mu + tau * z)
        return (-0.02 * jnp.sum(mu * mu) + jnp.sum(log_tau - 0.5 * tau * tau) - 0.5 * jnp.sum(z * z)
                + log_sigma - 0.5 * sigma * sigma - n * log_sigma - 0.5 * jnp.sum(resid * resid) / sigma ** 2)
    return logp


def torch_logp(name: str):
    import torch

    if name == "gauss100":
        return lambda q: -0.5 * torch.sum(q * q)
    if name == "eight":
        y, se = torch.tensor(Y8), torch.tensor(SE8)

        def logp(q):
            mu, log_tau, z = q[0], q[1], q[2:]
            tau = torch.exp(log_tau)
            resid = y - (mu + tau * z)
            return (-0.02 * mu * mu - torch.log1p(tau * tau / 25.0) + log_tau
                    - 0.5 * torch.sum(resid * resid / se ** 2) - 0.5 * torch.sum(z * z))
        return logp
    x, y = hier_data()
    xt, yt = torch.tensor(x), torch.tensor(y)
    n = J * NJ

    def logp(q):
        mu, log_tau, z, log_sigma = q[0:3], q[3:6], q[6:156].reshape(J, K), q[156]
        tau, sigma = torch.exp(log_tau), torch.exp(log_sigma)
        resid = yt - torch.einsum("jik,jk->ji", xt, mu + tau * z)
        return (-0.02 * torch.sum(mu * mu) + torch.sum(log_tau - 0.5 * tau * tau) - 0.5 * torch.sum(z * z)
                + log_sigma - 0.5 * sigma * sigma - n * log_sigma - 0.5 * torch.sum(resid * resid) / sigma ** 2)
    return logp


# ── PyMC ─────────────────────────────────────────────────────────────────


def pymc_model(name: str):
    import pymc as pm

    with pm.Model() as model:
        if name == "gauss100":
            pm.Normal("x", 0.0, 1.0, shape=100)
        elif name == "eight":
            mu = pm.Normal("mu", 0.0, 5.0)
            tau = pm.HalfCauchy("tau", 5.0)
            z = pm.Normal("z", 0.0, 1.0, shape=8)
            pm.Normal("y", mu + tau * z, SE8, observed=Y8)
        else:
            x, y = hier_data()
            mu = pm.Normal("mu_beta", 0.0, 5.0, shape=3)
            tau = pm.HalfNormal("tau", 1.0, shape=3)
            z = pm.Normal("z", 0.0, 1.0, shape=(J, K))
            sigma = pm.HalfNormal("sigma", 1.0)
            beta = mu + tau * z
            eta = (x * beta[:, None, :]).sum(-1)
            pm.Normal("y", eta, sigma, observed=y)
    return model


def unconstrained_from_posterior(name: str, post) -> np.ndarray:
    """(chains, draws, dim) unconstrained array from an InferenceData posterior
    (nutpie output), in the shared layout."""
    def arr(v):
        a = np.asarray(post[v].values, dtype=np.float64)
        return a.reshape(a.shape[0], a.shape[1], -1)
    if name == "gauss100":
        return arr("x")
    if name == "eight":
        return np.concatenate([arr("mu"), np.log(arr("tau")), arr("z")], -1)
    return np.concatenate([arr("mu_beta"), np.log(arr("tau")), arr("z"), np.log(arr("sigma"))], -1)


def functionals(name: str, s: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """Every unconstrained coordinate (bulk/tail ESS are rank-based, hence
    invariant to the monotone constraining transforms) plus, for Eight
    Schools, theta_1..theta_8."""
    dim = s.shape[-1]
    names = [f"q{i}" for i in range(dim)]
    if name == "eight":
        theta = s[..., :1] + np.exp(s[..., 1:2]) * s[..., 2:]
        s = np.concatenate([s, theta], -1)
        names += [f"theta_{i + 1}" for i in range(8)]
    return np.ascontiguousarray(s), names
