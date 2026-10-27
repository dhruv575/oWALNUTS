"""Warm-refresh microbenchmark for the Python transport (WP95): the per-call
cost of ``WarmSession.refresh`` (draws back to Python, quote computed with
numpy) against ``refresh_functionals`` with the quote functionals compiled
as numba ``cfunc``s (GIL-free) and with one of them as a Python callable
(the interpreter attached once per draw per chain).

The target is the Student-t stochastic-volatility model of
``examples/warm_session_bench.rs`` as a numba ``cfunc`` (``from_cfunc``),
on the WP84 shape (N = 250 returns, 253 coordinates) and a 50-latent
window (53 coordinates); 4 chains; ``threads`` 4 and 1; K in {5, 10, 50}
transitions per chain; the median and P95 wall per call over 100 timed
calls after 10 warm-up calls. Every arm starts from the same adapted
state and follows the session seed rule, so call ``n`` of each does the
same transitions; the functional values are checked against the
functionals of the draws.

    .venv\\Scripts\\python integrations\\python\\bench\\warm_functionals_bench.py [--calls 100] [--warmup-calls 10]
"""
from __future__ import annotations

import argparse
import math
import time

import numba
import numpy as np

import owalnuts

CHAINS = 4
SEED = 0x5EED_0095
RHO = 0.95
NU = 7.0


def simulate(n: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    mu, sigma = -1.0, 0.3
    h = mu + sigma / math.sqrt(1 - RHO * RHO) * rng.normal()
    y = np.empty(n)
    for i in range(n):
        if i > 0:
            h = mu + RHO * (h - mu) + sigma * rng.normal()
        y[i] = math.exp(h / 2) * rng.standard_t(NU)
    return y


def make_target(y: np.ndarray) -> owalnuts.CFuncTarget:
    """``q = [mu, log sigma, beta, z_1..z_n]``; the Rust ``Sv`` target."""
    n = len(y)
    y = np.ascontiguousarray(y, dtype=np.float64)
    cst = math.lgamma((NU + 1) / 2) - math.lgamma(NU / 2) - 0.5 * math.log(NU * math.pi)
    ln2pi = math.log(2 * math.pi)
    mu_mean, mu_sd, ls_mean, ls_sd, beta_sd = -1.0, 2.0, -1.5, 1.0, 0.1

    @numba.cfunc(owalnuts.numba_raw_signature(), nopython=True, error_model="numpy")
    def logp_grad(dim, q_ptr, g_ptr, user):
        q = numba.carray(q_ptr, (dim,))
        g = numba.carray(g_ptr, (dim,))
        mu, ls, beta = q[0], q[1], q[2]
        sigma = math.exp(ls)
        u = (mu - mu_mean) / mu_sd
        g[0] = -u / mu_sd
        lp = -0.5 * u * u - math.log(mu_sd) - 0.5 * ln2pi
        u = (ls - ls_mean) / ls_sd
        g[1] = -u / ls_sd
        lp += -0.5 * u * u - math.log(ls_sd) - 0.5 * ln2pi
        u = beta / beta_sd
        g[2] = -u / beta_sd
        lp += -0.5 * u * u - math.log(beta_sd) - 0.5 * ln2pi
        for i in range(n):
            z = q[3 + i]
            lp += -0.5 * z * z - 0.5 * ln2pi
            g[3 + i] = -z
        s0 = sigma / math.sqrt(1.0 - RHO * RHO)
        h = np.empty(n)
        h[0] = mu + s0 * q[3]
        for i in range(1, n):
            h[i] = mu + RHO * (h[i - 1] - mu) + sigma * q[3 + i]
        dh = np.zeros(n)
        for i in range(n):
            r = y[i] - beta
            e = math.exp(-h[i])
            a = r * r * e / NU
            lp += cst - 0.5 * h[i] - 0.5 * (NU + 1.0) * math.log1p(a)
            dh[i] = -0.5 + 0.5 * (NU + 1.0) * a / (1.0 + a)
            g[2] += (NU + 1.0) * r * e / NU / (1.0 + a)
        for i in range(n - 1, -1, -1):
            m = s0 if i == 0 else sigma
            g[3 + i] += dh[i] * m
            g[1] += dh[i] * m * q[3 + i]
            g[0] += dh[i] * (1.0 if i == 0 else 1.0 - RHO)
            if i > 0:
                dh[i - 1] += RHO * dh[i]
        if not math.isfinite(lp):
            return -math.inf
        for i in range(dim):
            if not math.isfinite(g[i]):
                return -math.inf
        return lp

    return owalnuts.from_cfunc(logp_grad, 3 + n)


def sigma_next_numpy(q: np.ndarray) -> np.ndarray:
    """``exp(h_{n+1} / 2)`` with ``h_{n+1} = mu + rho (h_n - mu)``; vectorised
    over the leading axes of ``q``."""
    mu, sigma = q[..., 0], np.exp(q[..., 1])
    h = mu + sigma / math.sqrt(1 - RHO * RHO) * q[..., 3]
    for i in range(4, q.shape[-1]):
        h = mu + RHO * (h - mu) + sigma * q[..., i]
    return np.exp((mu + RHO * (h - mu)) / 2)


def sigma_next_callable(q: np.ndarray) -> np.ndarray:
    return np.atleast_1d(sigma_next_numpy(q))


def cfunc_functionals():
    sig = owalnuts.numba_functional_signature()

    @numba.cfunc(sig, nopython=True, error_model="numpy")
    def sigma_next(dim, q_ptr, out, n_out, user):
        q = numba.carray(q_ptr, (dim,))
        mu, sigma = q[0], math.exp(q[1])
        h = mu + sigma / math.sqrt(1.0 - RHO * RHO) * q[3]
        for i in range(4, dim):
            h = mu + RHO * (h - mu) + sigma * q[i]
        out[0] = math.exp((mu + RHO * (h - mu)) / 2.0)

    @numba.cfunc(sig, nopython=True, error_model="numpy")
    def last_five(dim, q_ptr, out, n_out, user):
        q = numba.carray(q_ptr, (dim,))
        for j in range(n_out):
            out[j] = q[dim - n_out + j]

    return [owalnuts.from_cfunc_functional(sigma_next, 1), owalnuts.from_cfunc_functional(last_five, 5)]


def summarise(walls: list[float]) -> tuple[float, float]:
    walls = np.sort(np.asarray(walls))
    return float(np.quantile(walls, 0.5)), float(np.quantile(walls, 0.95))


def run_arm(session, calls, warmup_calls, call):
    walls = []
    last = None
    for n in range(warmup_calls + calls):
        started = time.perf_counter()
        last = call(session)
        wall = time.perf_counter() - started
        if n >= warmup_calls:
            walls.append(wall)
    return summarise(walls), last


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calls", type=int, default=100)
    parser.add_argument("--warmup-calls", type=int, default=10)
    parser.add_argument("--adapt", type=int, default=1000)
    args = parser.parse_args()
    y = simulate(250)
    compiled = cfunc_functionals()
    print(f"warm_functionals_bench: {CHAINS} chains, {args.calls} timed calls after {args.warmup_calls} warm-up calls; "
          "wall per call in ms (median / P95), one laptop, indicative")
    print(f"{'target':<22} | {'threads':>7} | {'K':>3} | {'refresh + numpy':>18} | {'functionals cfunc':>18} | "
          f"{'functionals callable':>21} | {'grads/call':>10}")
    print("-" * 120)
    for name, data in [("sv N=250 (dim 253)", y), ("sv window 50 (dim 53)", y[200:])]:
        target = make_target(data)
        state0 = owalnuts.sample(target, target.dim, chains=CHAINS, warmup=args.adapt, draws=100, seed=SEED,
                                 threads=4).warm_state()
        for threads in (4, 1):
            for draws in (5, 10, 50):
                def refresh_and_quote(session):
                    chunk = session.refresh(draws)
                    sigma = sigma_next_numpy(chunk.samples)
                    return np.quantile(sigma.reshape(-1), [0.5, 0.95]), chunk

                def functionals_cfunc(session):
                    chunk = session.refresh_functionals(draws, compiled)
                    return chunk.quantile([0.5, 0.95], 0), chunk

                def functionals_callable(session):
                    chunk = session.refresh_functionals(draws, [sigma_next_callable, compiled[1]])
                    return chunk.quantile([0.5, 0.95], 0), chunk

                results = []
                for call in (refresh_and_quote, functionals_cfunc, functionals_callable):
                    with owalnuts.WarmSession(target, state0, seed=SEED, threads=threads) as session:
                        timing, last = run_arm(session, args.calls, args.warmup_calls, call)
                        results.append((timing, last))
                (plain_t, (plain_q, plain_chunk)), (cf_t, (cf_q, cf_chunk)), (py_t, (py_q, py_chunk)) = results
                expected = sigma_next_numpy(plain_chunk.samples)
                np.testing.assert_array_equal(cf_chunk.output(0), expected)
                np.testing.assert_array_equal(py_chunk.output(0), expected)
                np.testing.assert_array_equal(cf_chunk.functional(1), plain_chunk.samples[:, :, -5:])
                np.testing.assert_array_equal(cf_q, plain_q)
                grads = plain_chunk.target_calls
                print(f"{name:<22} | {threads:>7} | {draws:>3} | {plain_t[0] * 1e3:>7.2f} / {plain_t[1] * 1e3:>7.2f} | "
                      f"{cf_t[0] * 1e3:>7.2f} / {cf_t[1] * 1e3:>7.2f} | {py_t[0] * 1e3:>9.2f} / {py_t[1] * 1e3:>8.2f} | "
                      f"{grads:>10}")
    print("refresh + numpy: draws (chains x K x dim) back to Python, sigma_next by a numpy recursion over the latents, numpy quantile.")
    print("functionals cfunc: sigma_next and the last five latents as numba cfuncs evaluated on the worker threads; values (chains x K x 6) back.")
    print("functionals callable: sigma_next as a Python callable (GIL attached once per draw per chain), last five as a cfunc.")


if __name__ == "__main__":
    main()
