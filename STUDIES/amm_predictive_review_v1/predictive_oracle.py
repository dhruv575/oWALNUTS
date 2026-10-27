"""Analytical oracle for the proposed predictive-functional study. No sampler runs.

Distinguishes conditional median scale, predictive scale quantiles, and predictive
return quantiles. Numerical integration uses independent SciPy quad and Hermite
quadrature implementations. This is an implementation diagnostic, not evidence
of market calibration or a frozen qualification study.
"""
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import scipy
from numpy.polynomial.hermite import hermgauss
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.special import ndtr, ndtri, stdtr

QUAD_DIAGNOSTICS = dict(calls=0, max_reported_absolute_error=0.0)


def scale_cdf(x, means, sigmas, weights):
    if x <= 0:
        return 0.0
    return float(np.dot(weights, ndtr((2 * np.log(x) - means) / sigmas)))


def return_cdf_gh(x, means, sigmas, betas, weights, nodes=64):
    z, w = hermgauss(nodes)
    h = means[:, None] + np.sqrt(2) * sigmas[:, None] * z
    conditional = stdtr(5, (x - betas[:, None]) * np.exp(-h / 2))
    return float(np.dot(weights, conditional @ (w / np.sqrt(np.pi))))


def return_cdf_quad(x, means, sigmas, betas, weights):
    parts = []
    for m, s, b in zip(means, sigmas, betas):
        value, error = quad(
            lambda z: stdtr(5, (x - b) * np.exp(-(m + s * z) / 2))
            * np.exp(-z * z / 2) / np.sqrt(2 * np.pi),
            -12, 12, epsabs=1e-12, epsrel=1e-12,
        )
        assert error < 1e-10
        QUAD_DIAGNOSTICS["calls"] += 1
        QUAD_DIAGNOSTICS["max_reported_absolute_error"] = max(
            QUAD_DIAGNOSTICS["max_reported_absolute_error"], float(error))
        parts.append(value)
    return float(np.dot(weights, parts))


def main():
    checks = []
    ps = [0.05, 0.5, 0.95]
    for s in [0.2, 0.4, 1.4]:
        m = 2 * np.log(0.005)
        for p in ps:
            q = np.exp((m + s * ndtri(p)) / 2)
            error = abs(scale_cdf(q, np.array([m]), np.array([s]), np.array([1.0])) - p)
            assert error < 1e-12
            checks.append(dict(kind="analytic_scale_quantile", sigma_h=s, p=p, cdf_error=error))

        analytic_mean = np.exp(m / 2 + s * s / 8)
        integrated_mean = quad(lambda z: np.exp((m + s*z)/2 - z*z/2) / np.sqrt(2*np.pi),
                               -12, 12, epsabs=1e-13)[0]
        assert abs(integrated_mean / analytic_mean - 1) < 1e-12
        checks.append(dict(kind="analytic_scale_mean", sigma_h=s,
                           median=float(np.exp(m/2)), mean=float(analytic_mean)))

    fixtures = [
        (np.array([-10.6]), np.array([0.2]), np.array([0.0]), np.array([1.0])),
        (np.array([-9.6]), np.array([0.4]), np.array([0.002]), np.array([1.0])),
        (np.array([-11.0, -8.8]), np.array([0.2, 1.4]), np.array([-0.001, 0.002]), np.array([0.3, 0.7])),
    ]
    for i, args in enumerate(fixtures):
        for p in ps:
            q = brentq(lambda x: return_cdf_quad(x, *args) - p, -2, 2, xtol=1e-13)
            errors = {str(n): abs(return_cdf_gh(q, *args, nodes=n) - p) for n in [32, 64, 128]}
            assert errors["128"] < 1e-7
            checks.append(dict(kind="predictive_return_quad_vs_hermite", fixture=i, p=p, quantile=q, cdf_errors=errors))

    # Noncentered stationary-first-state AR(1) coordinates do not shift by
    # simply dropping z0: the new initial coordinate combines old z0 and z1.
    def path(z, mu, sigma, rho):
        out = [mu + sigma / np.sqrt(1-rho*rho) * z[0]]
        for innovation in z[1:]:
            out.append(mu + rho*(out[-1]-mu) + sigma*innovation)
        return np.asarray(out)

    for rho in [0.0, 0.5, 0.95, -0.7]:
        for z in [np.array([.3, -.8, 1.2, -.1]), np.array([-1.1, .7, -.5, .9])]:
            old = path(z, -10.6, .4, rho)
            shifted = np.r_[rho*z[0] + np.sqrt(1-rho*rho)*z[1], z[2:], 0.0]
            new = path(shifted, -10.6, .4, rho)
            error = float(np.max(np.abs(old[1:] - new[:-1])))
            assert error < 1e-12
            checks.append(dict(kind="noncentered_window_path_preservation", rho=rho, max_absolute_error=error))

    # Quantiles of conditional medians need not be quantiles of the full
    # mixture, even though a single conditional median has a closed form.
    means, sigmas, _, weights = fixtures[2]
    mixture_p95 = brentq(lambda x: scale_cdf(x, means, sigmas, weights)-.95, 1e-8, 1)
    assert mixture_p95 > max(np.exp(means/2))
    checks.append(dict(kind="mixture_vs_conditional_medians", mixture_p95=float(mixture_p95),
                       largest_conditional_median=float(max(np.exp(means/2)))))

    # A known-parameter oracle isolates the innovation omitted by the current
    # Python documentation example. These are exact analytic quantities.
    omitted = [dict(sigma_h=s, conditional_median_scale=0.005,
                    predictive_scale_p95=float(0.005 * np.exp(s * ndtri(.95) / 2)),
                    relative_error_of_deterministic_p95=float(np.exp(-s * ndtri(.95) / 2) - 1))
               for s in [0.2, 0.4]]
    source = Path(__file__)
    result = dict(status="passed", checks=len(checks), details=checks,
                  predictive_quad_diagnostics=QUAD_DIAGNOSTICS,
                  provenance=dict(python=sys.version, numpy=np.__version__, scipy=scipy.__version__,
                                  platform=platform.platform(), machine=platform.machine(),
                                  source_file=source.name,
                                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                                  source_lf_sha256=hashlib.sha256(source.read_bytes().replace(b"\r\n", b"\n")).hexdigest()),
                  omitted_innovation_examples=omitted,
                  interpretation="Implementation-only oracle; no sampling, timing, calibration, or profitability claim")
    path = Path(__file__).with_name("oracle-results.json")
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(status=result["status"], checks=result["checks"], omitted_innovation_examples=omitted)))


if __name__ == "__main__":
    main()
