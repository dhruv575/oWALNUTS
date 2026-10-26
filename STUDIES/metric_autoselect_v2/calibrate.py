#!/usr/bin/env python3
"""WP79 calibration from the WP75 records (no sampling): the Hessian-fit statistics on WP75's recorded draws.

    python3 calibrate.py <wp75_draws_dir> <models_dir> <out.json>
    python3 calibrate.py funnel <out.json>


For every house model and every WP75 seed, the WP75 `diag`-arm retained unconstrained draws (4 chains x 1,000,
`<model>-diag-<seed>.npz`) are cut into six windows of 150 consecutive draws per chain (the length of slow windows
1 + 2), the log-density gradient is evaluated at every draw through BridgeStan (jacobian on, as the sampler's
target), and the statistic of `src/walnutpie.rs::hessian_auto_select_statistics` is computed on the pooled
within-chain moments: the linear fit g ~ x gives B; linearity = min_i R^2_i of that fit; P = -sym(B),
Sigma = P^-1, and G_H = kappa_diag / kappa_dense of Sigma whitened by its Stan-regularised (n = 500) diagonal and
dense estimates. The WP75 dense-arm draws are processed too (descriptive).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

HOUSE = ["eight_schools-eight_schools_noncentered", "eight_schools-eight_schools_centered", "diamonds-diamonds",
         "earnings-logearn_interaction", "mesquite-logmesquite_logvash", "kidiq-kidscore_momhsiq", "sblrc-blr",
         "nes2000-nes", "arK-arK", "arma-arma11", "garch-garch11", "gp_pois_regr-gp_pois_regr", "hmm_example-hmm_example",
         "bball_drive_event_0-hmm_drive_0", "one_comp_mm_elim_abs-one_comp_mm_elim_abs", "hudson_lynx_hare-lotka_volterra",
         "mcycle_gp-accel_gp"]
SEEDS = [757501, 757502, 757503]


def cond(m):
    ev = np.linalg.eigvalsh(0.5 * (m + m.T))
    return ev[-1] / ev[0] if ev[0] > 0 else math.inf


def statistics(xs, gs):
    """xs, gs: lists (one per chain) of (n, d) arrays."""
    d = xs[0].shape[1]
    zc = [np.hstack([x - x.mean(0), g - g.mean(0)]) for x, g in zip(xs, gs)]
    n = sum(len(z) for z in zc)
    c = sum(z.T @ z for z in zc) / (n - len(zc))
    cxx, cgx, cgg = c[:d, :d], c[d:, :d], c[d:, d:]
    try:
        np.linalg.cholesky(cxx)
    except np.linalg.LinAlgError:
        return {"linearity": float("nan"), "hessian_gain": float("nan"), "note": "Cxx not SPD"}
    bt = np.linalg.solve(cxx, cgx.T)  # B^T = Cxx^-1 Cxg
    b = bt.T
    explained = np.einsum("ik,ki->i", cgx, bt)
    r2 = explained / np.diag(cgg)
    lin = float(np.min(r2))
    p = -0.5 * (b + b.T)
    try:
        np.linalg.cholesky(p)
    except np.linalg.LinAlgError:
        return {"linearity": lin, "hessian_gain": float("nan"), "note": "P not SPD"}
    sigma = np.linalg.inv(p)
    sigma = 0.5 * (sigma + sigma.T)
    m = 500.0
    a = m / (m + 5) * sigma + 1e-3 * 5 / (m + 5) * np.eye(d)
    s = 1 / np.sqrt(np.maximum(np.diag(a), 1e-10))
    kd = cond(sigma * np.outer(s, s))
    li = np.linalg.inv(np.linalg.cholesky(a))
    kn = cond(li @ sigma @ li.T)
    return {"linearity": lin, "hessian_gain": float(kd / kn) if math.isfinite(kd) and math.isfinite(kn) else float("nan"),
            "kappa_diag": float(kd), "kappa_dense": float(kn), "r2": [float(x) for x in r2]}


def funnel(out_path):
    """Neal's 10-D funnel (the F block's target): exact independent draws, 200 sets of 4 x 150 (seed 797900)."""
    rng = np.random.default_rng(797900)
    vals = []
    for _ in range(200):
        xs, gs = [], []
        for _c in range(4):
            omega = 3.0 * rng.standard_normal(150)
            x = rng.standard_normal((150, 9)) * np.exp(0.5 * omega)[:, None]
            inv = np.exp(-omega)
            g0 = -omega / 9.0 - 4.5 + 0.5 * inv * (x * x).sum(1)
            xs.append(np.column_stack([omega, x]))
            gs.append(np.column_stack([g0, -inv[:, None] * x]))
        vals.append(statistics(xs, gs))
    lin = [v["linearity"] for v in vals]
    gh = [v["hessian_gain"] for v in vals]
    row = {"sets": len(vals), "linearity_min": min(lin), "linearity_median": float(np.median(lin)),
           "linearity_max": max(lin), "hessian_gain_finite": int(sum(math.isfinite(x) for x in gh)),
           "hessian_gain_median": float(np.nanmedian(gh)) if any(math.isfinite(x) for x in gh) else None,
           "notes": sorted({v.get("note", "") for v in vals})}
    print(json.dumps(row), flush=True)
    Path(out_path).write_text(json.dumps({"funnel10": row}, indent=1) + "\n")


def main():
    if sys.argv[1] == "funnel":
        return funnel(sys.argv[2])
    import bridgestan as bs

    draws, models, out_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    out = {}
    for model in HOUSE:
        sm = bs.StanModel(str(models / f"{model}_model.so"), data=(models / f"{model}.data.json").read_text(), seed=1)
        rows = {}
        for arm in ("diag", "dense"):
            vals = []
            for seed in SEEDS:
                f = draws / f"{model}-{arm}-{seed}.npz"
                if not f.exists():
                    continue
                unc = np.load(f)["unconstrained"]  # (chains, draws, d)
                grads = np.empty_like(unc)
                for c in range(unc.shape[0]):
                    for i in range(unc.shape[1]):
                        grads[c, i] = sm.log_density_gradient(unc[c, i], propto=True, jacobian=True)[1]
                for k in range(6):
                    sl = slice(150 * k, 150 * (k + 1))
                    st = statistics([unc[c, sl] for c in range(unc.shape[0])], [grads[c, sl] for c in range(unc.shape[0])])
                    st.update({"seed": seed, "window": k})
                    vals.append(st)
            lin = [v["linearity"] for v in vals if math.isfinite(v["linearity"])]
            gh = [v["hessian_gain"] for v in vals if math.isfinite(v["hessian_gain"])]
            rows[arm] = {"windows": len(vals),
                         "linearity_min": min(lin) if lin else None, "linearity_median": float(np.median(lin)) if lin else None,
                         "linearity_q10": float(np.quantile(lin, 0.1)) if lin else None, "linearity_max": max(lin) if lin else None,
                         "hessian_gain_median": float(np.median(gh)) if gh else None,
                         "hessian_gain_min": min(gh) if gh else None, "hessian_gain_max": max(gh) if gh else None,
                         "values": vals}
        out[model] = {"dimension": int(sm.param_unc_num()), **rows}
        d = rows["diag"]
        print(f"{model[:32]:32s} d{sm.param_unc_num():3d} lin min {d['linearity_min']} med {d['linearity_median']} "
              f"G_H med {d['hessian_gain_median']} [{d['hessian_gain_min']}, {d['hessian_gain_max']}]", flush=True)
    out_path.write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
