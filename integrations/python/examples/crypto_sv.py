"""Headless version of crypto_sv.ipynb: BTC stochastic volatility with oWALNUTS.

Runs the demo-budget cell of the notebook (300 warmup / 500 draws, seconds of
wall time) against the committed BTC data and stage-A calibration in
crypto_sv_assets/. The preregistered evidence runs live in
STUDIES/flagship_crypto_sv_v1 (1,000/3,000, seeds 97001-97003).

Usage:  python crypto_sv.py
"""

import json
import pathlib

import numpy as np
import owalnuts
import pymc as pm
import pytensor.tensor as pt

ASSETS = pathlib.Path(__file__).resolve().parent / "crypto_sv_assets"


def main():
    doc = json.loads((ASSETS / "BTC.json").read_text())
    closes = np.array([row[1] for row in doc["closes"]])
    r = np.log(closes[1:] / closes[:-1])
    t = len(r)
    print(f"BTC-USDT {doc['first']} .. {doc['last']}  (T = {t} returns)")

    with pm.Model() as model:
        mu = pm.Normal("mu", -10, 5)
        phi_raw = pm.Beta("phi_raw", 20, 1.5)
        phi = 2 * phi_raw - 1
        sigma = pm.HalfNormal("sigma", 0.5)
        pm.AR("h", rho=[mu * (1 - phi), phi], sigma=sigma, constant=True,
              init_dist=pm.Normal.dist(mu, sigma / pt.sqrt(1 - phi**2)), shape=t)
        pm.Normal("r", 0.0, pt.exp(model["h"] / 2), observed=r)

    target, dim, _q0, _names, _unravel = owalnuts.from_pymc(model, gil_free=True)

    cal = json.loads((ASSETS / "BTC-calibration-97001.json").read_text())
    phi_h, s2 = cal["phi_hat"], cal["sigma_hat"] ** 2
    h_mean = np.asarray(cal["h_mean"])
    diag = np.full(t, (1 + phi_h**2) / s2)
    diag[[0, -1]] = 1 / s2
    diag += 0.5 * r**2 * np.exp(-h_mean)
    off = np.full(t - 1, -phi_h / s2)
    cov = 2.0 * np.asarray(cal["global_cov"]).reshape(3, 3)
    prec = np.linalg.inv(cov)
    mass = owalnuts.tridiagonal_precision_mass(
        np.array([prec[0, 0], prec[1, 1], prec[2, 2]]),
        np.array([prec[0, 1], prec[1, 2]]),
    ) + owalnuts.tridiagonal_precision_mass(diag, off)

    base = np.concatenate([[cal["mu_hat"], cal["a_hat"], cal["s_hat"]], h_mean])
    starts = base + 0.3 * np.random.default_rng(1).standard_normal((4, dim))
    result = owalnuts.sample(
        target, dim, init=starts, chains=4, warmup=300, draws=500, seed=1, threads=4,
        tuning=owalnuts.Tuning(step_size=0.1, max_depth=9, max_refinement_levels=6),
        adaptation=owalnuts.Adaptation(adapt_mass=False, paper=owalnuts.PaperAdaptation()),
        mass=mass, max_target_evaluations=1_000_000_000,
    )
    print(f"wall {result.wall_seconds:.1f}s, {result.target_calls:,} gradient evaluations, "
          f"divergences {int(result.divergent.sum())}")
    post = result.samples
    phi_draws = 2 / (1 + np.exp(-post[:, :, 1])) - 1
    print(f"phi = {phi_draws.mean():.3f}, sigma = {np.exp(post[:, :, 2]).mean():.3f} (demo budget)")


if __name__ == "__main__":
    main()
