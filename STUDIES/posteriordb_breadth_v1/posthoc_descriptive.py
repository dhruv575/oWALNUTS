#!/usr/bin/env python3
"""POST-HOC, DESCRIPTIVE ONLY (written after the cells were seen; not part of the frozen analysis).

Lists, over every completed cell including passing ones, (1) chains whose final step is below
0.2x the cell's median final step, with that chain's warmup depth caps, installed-over-empirical
metric variance and per-chain ESS; (2) the warmup share of gradients per cell, and the cell's
gradients relative to the median cell of the same posterior. Output: artifacts/posthoc-descriptive.json
and artifacts/posthoc-descriptive.md.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
CELLS = HERE / "artifacts" / "cells"


def main() -> None:
    rows, collapses = [], []
    by_model: dict[str, list[dict]] = {}
    for p in sorted(CELLS.glob("*.json")):
        c = json.loads(p.read_text(encoding="utf-8"))
        if c.get("status") != "ok":
            continue
        by_model.setdefault(c["model"], []).append(c)
    for model, cells in by_model.items():
        med_grads = statistics.median(c["gradients_total"] for c in cells)
        for c in cells:
            warm = c["gradients_total"] - c["gradients_sampling"]
            rows.append({
                "model": model, "seed": c["seed"], "passed": c["passed"],
                "gradients_total": c["gradients_total"],
                "warmup_share": warm / c["gradients_total"],
                "gradients_over_model_median": c["gradients_total"] / med_grads,
            })
            steps = c["final_step_size"]
            med = statistics.median(steps)
            for i, h in enumerate(steps):
                if h < 0.2 * med:
                    collapses.append({
                        "model": model, "seed": c["seed"], "chain": i, "passed": c["passed"],
                        "step": h, "median_step": med, "ratio": h / med,
                        "warmup_depth_caps": c["warmup_depth_caps_per_chain"][i],
                        "retained_depth_caps": c["depth_caps_per_chain"][i],
                        "metric_installed_over_empirical_max": c["metric_installed_over_empirical_variance_max"][i],
                        "chain_bulk_ess_min": c["per_chain_bulk_ess_min"][i],
                        "chain_h0_median": (c["retained_initial_hamiltonian_quantiles"][i] or {}).get("q50"),
                        "other_chains_h0_median": statistics.median(
                            q["q50"] for j, q in enumerate(c["retained_initial_hamiltonian_quantiles"]) if j != i and q),
                        "refinement_exhaustions": c["refinement_exhaustions_per_chain"][i],
                        "cell_gradients_over_model_median": c["gradients_total"] / med_grads,
                    })
    out = {"note": "post-hoc descriptive; not a preregistered statistic", "step_collapsed_chains": collapses, "cells": rows}
    (HERE / "artifacts" / "posthoc-descriptive.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    lines = ["# Post-hoc descriptive telemetry (not preregistered)", "",
             "## Chains with final step < 0.2 x the cell median (all completed cells, passing included)", "",
             "| model | seed | chain | cell passed | step | median step | ratio | warmup caps | retained caps | metric installed/empirical max | chain min bulk ESS | chain H0 median - others | exhaustions | cell grads / model median |",
             "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in collapses:
        dh = (r["chain_h0_median"] - r["other_chains_h0_median"]) if r["chain_h0_median"] is not None else float("nan")
        lines.append(f"| {r['model']} | {r['seed']} | {r['chain']} | {r['passed']} | {r['step']:.3g} | {r['median_step']:.3g} | {r['ratio']:.3f} | "
                     f"{r['warmup_depth_caps']} | {r['retained_depth_caps']} | {r['metric_installed_over_empirical_max']:.3g} | "
                     f"{r['chain_bulk_ess_min']:.0f} | {dh:+.1f} | {r['refinement_exhaustions']} | {r['cell_gradients_over_model_median']:.2f} |")
    lines += ["", f"{len(collapses)} collapsed chains in {len({(r['model'], r['seed']) for r in collapses})} cells.", "",
              "## Gradient cost per cell", "", "| model | seed | passed | gradients | warmup share | / model median |", "|---|---:|---|---:|---:|---:|"]
    for r in rows:
        lines.append(f"| {r['model']} | {r['seed']} | {r['passed']} | {r['gradients_total']:,} | {r['warmup_share']:.2f} | {r['gradients_over_model_median']:.2f} |")
    (HERE / "artifacts" / "posthoc-descriptive.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:len(collapses) + 8]))


if __name__ == "__main__":
    main()
