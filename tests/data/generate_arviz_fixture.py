"""Generate ``arviz_fixture.json`` for ``owalnuts::diagnostics``.

Run with a Python that has ``numpy`` and ``arviz`` installed::

    python tests/data/generate_arviz_fixture.py

Each case is a fixed-seed synthetic chain set (chains x draws) together with
ArviZ's rank-normalised split R-hat, bulk/tail ESS, mean ESS, MCSE of the
mean, and R type-7 quantiles. The Rust test ``tests/diagnostics_arviz.rs``
reproduces every number to 1e-6 relative tolerance.
"""

import json
import pathlib

import arviz as az
import numpy as np


def ar1(rng, chains, draws, rho, loc=0.0, scale=1.0):
    out = np.empty((chains, draws))
    for c in range(chains):
        x = rng.normal()
        for d in range(draws):
            x = rho * x + np.sqrt(1.0 - rho * rho) * rng.normal()
            out[c, d] = x
    return loc + scale * out


def main():
    rng = np.random.default_rng(20260901)
    cases = {
        "iid_4x200": ar1(rng, 4, 200, 0.0),
        "ar1_0.6_4x400": ar1(rng, 4, 400, 0.6, loc=1.5, scale=2.0),
        "ar1_0.95_2x500": ar1(rng, 2, 500, 0.95),
        "negative_ar1_4x101": ar1(rng, 4, 101, -0.4),
        "shifted_means_4x150": ar1(rng, 4, 150, 0.3) + np.arange(4)[:, None] * 0.8,
        "ties_rounded_3x120": np.round(ar1(rng, 3, 120, 0.5), 1),
        "heavy_tail_4x300": rng.standard_t(2.5, size=(4, 300)),
        "single_chain_1x256": ar1(rng, 1, 256, 0.7),
        "constant_2x40": np.full((2, 40), 3.25),
    }
    fixture = {"generator": "tests/data/generate_arviz_fixture.py", "arviz": az.__version__, "cases": []}
    for name, chains in cases.items():
        entry = {
            "name": name,
            "chains": chains.tolist(),
            "rhat": _num(az.rhat(chains, method="rank")),
            "ess_bulk": _num(az.ess(chains, method="bulk")),
            "ess_tail": _num(az.ess(chains, method="tail")),
            "ess_mean": _num(az.ess(chains, method="mean")),
            "ess_q05": _num(az.ess(chains, method="quantile", prob=0.05)),
            "mcse_mean": _num(az.mcse(chains, method="mean")),
            "mean": float(chains.mean()),
            "sd": float(chains.std(ddof=1)),
            "q05": float(np.quantile(chains, 0.05)),
            "q50": float(np.quantile(chains, 0.50)),
            "q95": float(np.quantile(chains, 0.95)),
        }
        fixture["cases"].append(entry)
    path = pathlib.Path(__file__).with_name("arviz_fixture.json")
    path.write_text(json.dumps(fixture, indent=1), encoding="utf-8")
    print(f"wrote {path} ({len(cases)} cases)")


def _num(value):
    if hasattr(value, "to_array"):
        value = value.to_array().values
    value = float(np.asarray(value).ravel()[0])
    return None if np.isnan(value) else value


if __name__ == "__main__":
    main()
