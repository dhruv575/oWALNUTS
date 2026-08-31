#!/usr/bin/env python3
"""Post-processing for the exact state-space ground-truth study.

Reads `artifacts/index.json`, per-run summaries, raw draws and exact truth;
computes ArviZ rank-normalised diagnostics, z-scores against the exact
posterior, and writes `artifacts/summary.json` plus a Markdown table.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import arviz as az
import numpy as np

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze_run(stem: str, index: dict) -> dict:
    run = json.loads((ART / "runs" / f"{stem}.json").read_text())
    truth = json.loads((ART / f"truth-T{run['t']}.json").read_text())
    chains, retained, t = index["chains"], index["retained"], run["t"]
    draws = np.fromfile(ART / "draws" / f"{stem}.f64", dtype="<f8").reshape(chains, retained, t)
    exact_mean = np.asarray(truth["exact_mean"])
    exact_var = np.asarray(truth["exact_var"])

    bulk = np.asarray(az.ess(draws, method="bulk"))
    tail = np.asarray(az.ess(draws, method="tail", prob=(0.05, 0.95)))
    rhat = np.asarray(az.rhat(draws, method="rank"))
    mean = draws.reshape(-1, t).mean(axis=0)
    var = draws.reshape(-1, t).var(axis=0, ddof=1)
    mcse = np.sqrt(exact_var / np.maximum(bulk, 1.0))
    z = (mean - exact_mean) / mcse
    var_ratio = var / exact_var
    level = draws.mean(axis=2)  # path mean functional per draw
    level_bulk = float(np.asarray(az.ess(level[:, :, None], method="bulk"))[0])
    level_tail = float(np.asarray(az.ess(level[:, :, None], method="tail", prob=(0.05, 0.95)))[0])
    level_rhat = float(np.asarray(az.rhat(level[:, :, None], method="rank"))[0])
    exact_level_mean = float(exact_mean.mean())
    # exact variance of the path mean needs the full covariance; use the
    # sampled variance only as a descriptive value.
    total_calls = run["target_calls_counter"]
    retained_calls = run["target_calls_retained"]
    out = {
        "stem": stem,
        "arm": run["arm"],
        "t": t,
        "seed": run["seed"],
        "prediction": run["prediction"],
        "median_depth": run["median_depth"],
        "depth_histogram": run["depth_histogram"],
        "max_depth_rate": run["max_depth_rate"],
        "retained_divergences": run["retained_divergences"],
        "warmup_divergences": run["warmup_divergences"],
        "retained_invalid_evaluations": run["retained_invalid_evaluations"],
        "retained_refinement_exhaustions": run["retained_refinement_exhaustions"],
        "final_step_sizes": run["final_step_sizes"],
        "wall_seconds": run["wall_seconds"],
        "target_calls_total": total_calls,
        "target_calls_retained": retained_calls,
        "preflight": run["preflight"],
        "min_bulk_ess": float(bulk.min()),
        "median_bulk_ess": float(np.median(bulk)),
        "min_tail_ess": float(tail.min()),
        "max_rhat": float(rhat.max()),
        "min_bulk_ess_per_retained_call": float(bulk.min() / retained_calls),
        "median_bulk_ess_per_retained_call": float(np.median(bulk) / retained_calls),
        "min_bulk_ess_per_second": float(bulk.min() / run["wall_seconds"]),
        "max_abs_z": float(np.abs(z).max()),
        "mean_z_squared": float((z * z).mean()),
        "retained_reverse_coarser_stops": run["retained_reverse_coarser_stops"],
        "retained_reverse_coarser_rejections": run["retained_reverse_coarser_rejections"],
        "selected_refinement_level_histogram": run["selected_refinement_level_histogram"],
        "fraction_abs_z_gt_3": float((np.abs(z) > 3).mean()),
        "any_abs_z_gt_5": bool((np.abs(z) > 5).any()),
        "var_ratio_p05": float(np.percentile(var_ratio, 5)),
        "var_ratio_p50": float(np.percentile(var_ratio, 50)),
        "var_ratio_p95": float(np.percentile(var_ratio, 95)),
        "level_functional": {
            "bulk_ess": level_bulk,
            "tail_ess": level_tail,
            "rhat": level_rhat,
            "mc_mean": float(level.mean()),
            "exact_mean": exact_level_mean,
        },
    }
    pred = run["prediction"]
    depth_ok = (run["max_depth_rate"] > 0.5) if pred["cap"] else (abs(run["median_depth"] - pred["depth"]) <= 1)
    accuracy_ok = out["fraction_abs_z_gt_3"] < 0.01 and not out["any_abs_z_gt_5"]
    variance_ok = 0.8 <= out["var_ratio_p05"] and out["var_ratio_p95"] <= 1.25
    health_ok = (
        run["retained_divergences"] == 0
        and run["retained_invalid_evaluations"] == 0
        and run["retained_refinement_exhaustions"] == 0
    )
    out["gates"] = {
        "depth_prediction_held": bool(depth_ok),
        "accuracy_ok": bool(accuracy_ok),
        "variance_ok": bool(variance_ok),
        "health_ok": bool(health_ok),
    }
    return out


def main() -> int:
    index = json.loads((ART / "index.json").read_text())
    results = [analyze_run(stem, index) for stem in index["runs"]]
    summary = {
        "schema": "exact-state-space-ground-truth-v1/summary",
        "arviz": az.__version__,
        "numpy": np.__version__,
        "index": index,
        "results": results,
    }
    (ART / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    lines = [
        "| T | seed | arm | kappa (pred) | depth pred | median depth | cap rate | min bulk ESS | min tail ESS | max R-hat | min bulk ESS/call | max abs z | mean z^2 | frac abs z>3 | var ratio p05-p95 | level ESS | calls | wall s | step |",
        "|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|",
    ]
    for r in results:
        p = r["prediction"]
        lines.append(
            f"| {r['t']} | {r['seed']} | {r['arm']} | {p['kappa']:.3g} | {p['depth']}{'*' if p['cap'] else ''} | "
            f"{r['median_depth']} | {r['max_depth_rate']:.3f} | {r['min_bulk_ess']:.0f} | {r['min_tail_ess']:.0f} | "
            f"{r['max_rhat']:.4f} | {r['min_bulk_ess_per_retained_call']:.2e} | {r['max_abs_z']:.2f} | {r['mean_z_squared']:.2f} | "
            f"{r['fraction_abs_z_gt_3']:.4f} | {r['var_ratio_p05']:.2f}-{r["var_ratio_p95"]:.2f} | "
            f"{r['level_functional']['bulk_ess']:.0f} | {r['target_calls_total']:,} | {r['wall_seconds']:.1f} | "
            f"{np.mean(r['final_step_sizes']):.4f} |"
        )
    (ART / "results-table.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
