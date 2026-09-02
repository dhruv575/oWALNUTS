"""Cross-check ``owalnuts::export::CmdStanCsv`` output against ArviZ.

Usage: ``python check_cmdstan_export.py <dir>`` where ``<dir>`` holds the
``chain-*.csv`` files and ``summary.json`` written by
``tests/export_cmdstan.rs`` (run that test with ``OWALNUTS_ARVIZ_PYTHON`` set
to invoke this script automatically). Exits non-zero on any disagreement.
"""

import glob
import json
import os
import sys

import arviz as az
import numpy as np

RTOL = 1e-6


def check(name, actual, expected, rtol=RTOL, atol=0.0):
    ok = bool(np.isclose(actual, expected, rtol=rtol, atol=atol))
    print(f"{'ok ' if ok else 'BAD'} {name:<20} rust={expected!r:<24} arviz={actual!r}")
    return ok


def main(directory):
    paths = sorted(glob.glob(os.path.join(directory, "chain-*.csv")))
    with open(os.path.join(directory, "summary.json"), encoding="utf-8") as handle:
        rust = json.load(handle)
    idata = az.from_cmdstan(posterior=paths)
    post, stats = idata.posterior, idata.sample_stats
    print(f"loaded {len(paths)} chains: posterior dims {dict(post.sizes)}")
    print(f"sample_stats: {sorted(stats.data_vars)}")
    good = True

    table = az.summary(idata, round_to="none", kind="all")
    for row in rust["parameters"]:
        r = table.loc[row["name"]]
        for key, col in [
            ("mean", "mean"),
            ("sd", "sd"),
            ("mcse_mean", "mcse_mean"),
            ("ess_bulk", "ess_bulk"),
            ("ess_tail", "ess_tail"),
            ("rhat", "r_hat"),
        ]:
            good &= check(f"{row['name']}.{key}", float(r[col]), row[key])

    h = rust["health"]
    good &= check("diverging.sum", int(stats["diverging"].values.sum()), h["divergences"])
    good &= check("n_steps.sum", int(stats["n_steps"].values.sum()), h["target_calls"])
    good &= check("tree_depth.mean", float(stats["tree_depth"].values.mean()), h["mean_tree_depth"])
    good &= check("step_size.mean", float(stats["step_size"].values.mean()), h["step_size"])
    good &= check("draws", int(post.sizes["chain"] * post.sizes["draw"]), h["transitions"])

    scales = np.asarray(rust["scales"])
    draws = np.stack([post[p["name"]].values for p in rust["parameters"]], axis=-1)
    lp_expected = -0.5 * ((draws / scales) ** 2).sum(axis=-1)
    lp_error = float(np.abs(stats["lp"].values - lp_expected).max())
    good &= check("lp.max_abs_err", lp_error, 0.0, rtol=0.0, atol=1e-9)
    good &= check("energy.finite", float(np.isfinite(stats["energy"].values).all()), 1.0)

    print("ALL OK" if good else "MISMATCH")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
