#!/usr/bin/env python3
"""Summarise the freeze_mode_v1 arm table and side checks.

    python analyze.py     # artifacts/summary.json + artifacts/results-table.md
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
TABLE = HERE / "artifacts" / "table"
CHECKS = HERE / "artifacts" / "checks"
ARMS = ["baseline", "exhaust-accept", "mean-accept", "stan-style", "step-floor", "exhaust-signed",
        "exhaust-signed+mean-accept", "stan-style+exhaust-signed", "warmup-signed"]
MODELS = {"arma__arma11": "arma11", "hudson_lynx_hare__lotka_volterra": "lotka_volterra"}
SEEDS = [78101, 78102, 78103]


def fmt(x, digits=3):
    if x is None:
        return "—"
    if isinstance(x, float):
        if x != x:
            return "nan"
        if abs(x) >= 1e5 or (abs(x) < 1e-3 and x != 0):
            return f"{x:.{digits - 1}e}"
        return f"{x:.{digits}g}"
    return str(x)


def main() -> None:
    cells = {}
    for f in sorted(TABLE.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        cells[(d["model"].replace("_model", ""), d["variant"], d["seed"])] = d
    summary = {"schema": "freeze-mode-v1-summary", "cells": {}, "arms": {}}
    lines = ["# freeze_mode_v1 — results", "",
             "Per cell: frozen chains / min bulk ESS (unconstrained coordinates) / gradients (x1e3, warmup + retained) / "
             "min bulk ESS per gradient x1e3 / escape transition per chain (`-` = never) / final h per chain.", ""]
    for model_key, model in MODELS.items():
        lines += [f"## {model}", "", "| arm | seed | frozen | min bulk ESS | max R-hat | grads x1e3 | ESS/grad x1e3 | escape | final h | wall s |", "|---|---:|---:|---:|---:|---:|---:|---|---|---:|"]
        for arm in ARMS:
            per_seed = []
            for seed in SEEDS:
                d = cells.get((model_key, arm, seed))
                if d is None:
                    lines.append(f"| {arm} | {seed} | (missing) | | | | | | | |")
                    continue
                esc = " ".join("-" if c["escape_transition"] is None else str(c["escape_transition"]) for c in d["chains_data"])
                hs = " ".join(f"{c['final_step_size']:.1e}" for c in d["chains_data"])
                lines.append(f"| {arm} | {seed} | {d['frozen_chains']} | {fmt(d['min_bulk_ess'], 4)} | {fmt(d['max_rhat'], 4)} | "
                             f"{d['gradients_total'] / 1e3:.0f} | {fmt(d['min_bulk_ess_per_gradient'] * 1e3)} | {esc} | {hs} | {d['wall_seconds']:.1f} |")
                per_seed.append(d)
                summary["cells"][f"{model}-{arm}-{seed}"] = {
                    "frozen_chains": d["frozen_chains"], "min_bulk_ess": d["min_bulk_ess"], "max_rhat": d["max_rhat"],
                    "gradients_total": d["gradients_total"], "min_bulk_ess_per_gradient": d["min_bulk_ess_per_gradient"],
                    "final_step_sizes": [c["final_step_size"] for c in d["chains_data"]],
                    "escape_transitions": [c["escape_transition"] for c in d["chains_data"]],
                    "wall_seconds": d["wall_seconds"],
                }
            if per_seed:
                summary["arms"].setdefault(arm, {})[model] = {
                    "frozen_chains_total": sum(d["frozen_chains"] for d in per_seed),
                    "median_min_bulk_ess": statistics.median(d["min_bulk_ess"] for d in per_seed),
                    "median_min_bulk_ess_per_gradient": statistics.median(d["min_bulk_ess_per_gradient"] for d in per_seed),
                    "seeds_passing_ess_400": sum(d["min_bulk_ess"] >= 400 for d in per_seed),
                }
        lines.append("")
    lines += ["## Seed medians", "", "| arm | " + " | ".join(f"{m} frozen (of 12) / seeds with min ESS >= 400 / median min ESS / median ESS per grad x1e3" for m in MODELS.values()) + " |",
              "|---|" + "---|" * len(MODELS)]
    for arm in ARMS:
        row = [arm]
        for model in MODELS.values():
            a = summary["arms"].get(arm, {}).get(model)
            row.append("(missing)" if a is None else f"{a['frozen_chains_total']} / {a['seeds_passing_ess_400']}/3 / {fmt(a['median_min_bulk_ess'], 4)} / {fmt(a['median_min_bulk_ess_per_gradient'] * 1e3)}")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    checks = {}
    for f in sorted(CHECKS.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        checks[f.stem] = d
    if checks:
        lines += ["## Side checks", "", "| check | variant | grads | retained exhaustions | warmup exhaustions | divergences | min bulk ESS | max R-hat | tail mass (exact 0.0478) | z |", "|---|---|---:|---:|---:|---:|---:|---:|---|---:|"]
        for name, d in checks.items():
            tm = d.get("tail_mass")
            lines.append(f"| {d['target']} | {d['variant']} | {d['gradients_total']} | {d['retained_exhaustions']} | {d['warmup_exhaustions']} | {d['retained_divergences']} | "
                         f"{fmt(d['min_bulk_ess'], 4)} | {fmt(d['max_rhat'], 4)} | {'' if tm is None else f'{tm['estimate']:.4f} +- {tm['batch_means_se']:.4f}'} | {'' if tm is None else f'{tm['z']:.2f}'} |")
        summary["checks"] = {k: {kk: vv for kk, vv in v.items() if kk != "per_coordinate"} for k, v in checks.items()}
    (HERE / "artifacts" / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    (HERE / "artifacts" / "results-table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
