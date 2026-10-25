#!/usr/bin/env python3
"""Pre-execution input to the predictions (not evidence): for every model, the posterior variance of each
unconstrained coordinate from the posteriordb reference draws (BridgeStan `param_unconstrain`), and the variance each
regularisation would install from a final slow window of n = 500 draws if that window measured the posterior
variance exactly. Writes `artifacts/prediction-scales.json` and prints a table.

    python predict_scales.py
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_scalefree as rs  # noqa: E402

N = 500.0


def installed(var: np.ndarray, rule: str) -> np.ndarray:
    m = float(np.median(var))
    if not (math.isfinite(m) and m > 0):
        m = 1.0
    w = 5.0 / (N + 5.0)
    prior = {"da": 1e-3 * w, "sfmed": m * w, "sfstan": 1e-3 * m * w, "toward_unit": w}[rule]
    return (N / (N + 5.0)) * var + prior


def main() -> None:
    import bridgestan as bs

    out = {}
    print(f"{'model':45s} dim  median var  min var   max var  | max inflation (installed/posterior): da  sfmed  sfstan  toward_unit")
    for model in rs.PROTOCOL["models"]:
        so, data = rs.prepare_bridgestan(model)
        bs.compile.windows_dll_path_setup()
        sm = bs.StanModel(str(so), data=data.read_text(encoding="utf-8"), seed=1)
        p = rs.posterior(model)
        ref = p.reference_draws()
        names = sm.param_names(include_tp=False, include_gq=False)
        ref_names = list(ref[0].keys())
        ref_set = set(ref_names)
        idx = {n: (n if n in ref_set else rs.bridgestan_name(n)) for n in names}
        missing = [n for n in names if idx[n] not in ref_set]
        if missing:
            print(f"{model}: reference draws lack {missing[:3]}; skipped")
            out[model] = {"skipped": f"reference draws lack {missing[:5]}"}
            continue
        rows = []
        for chain in ref:
            for d in range(len(chain[ref_names[0]])):
                theta = np.asarray([chain[idx[n]][d] for n in names], dtype=np.float64)
                rows.append(sm.param_unconstrain(theta))
        u = np.asarray(rows)
        var = u.var(0, ddof=1)
        infl = {r: (installed(var, r) / var) for r in ("da", "sfmed", "sfstan", "toward_unit")}
        out[model] = {
            "dimension": int(var.size), "posterior_variance": var.tolist(),
            "median_variance": float(np.median(var)),
            "inflation": {r: v.tolist() for r, v in infl.items()},
            "max_inflation": {r: float(v.max()) for r, v in infl.items()},
        }
        print(f"{model:45s} {var.size:3d}  {np.median(var):9.3g}  {var.min():8.3g}  {var.max():8.3g} | "
              + "  ".join(f"{infl[r].max():7.3g}" for r in ("da", "sfmed", "sfstan", "toward_unit")))
    (rs.ART / "prediction-scales.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
