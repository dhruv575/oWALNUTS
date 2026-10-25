#!/usr/bin/env python3
"""WP55 post-hoc, descriptive only (written after the cells were seen; changes no verdict).

Writes artifacts/posthoc.json and artifacts/posthoc.md:
* per-cell max-chain refined-leaf rate R and step-collapse factor S, positives-wrong vs negatives-clean;
  the rank AUC of each and the best achievable threshold (post hoc, NOT evidence);
* the same with R measured relative to the cell's own median chain (a within-cell outlier score);
* whether the highest-R chain is the chain furthest from the reference (the "stuck" chain);
* per-model median R, depth of refined leaves, and divergences.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import run_study as rs

ART = rs.ART


def auc(pos: list[float], neg: list[float]) -> float:
    if not pos or not neg:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def best_cut(pos: list[float], neg: list[float]) -> dict:
    best = None
    for t in sorted(set(pos + neg)):
        sens = sum(p > t for p in pos) / len(pos)
        spec = sum(n <= t for n in neg) / len(neg)
        if best is None or sens + spec > best["sens"] + best["spec"]:
            best = {"threshold": t, "sens": sens, "spec": spec}
    return best


def main() -> None:
    cells = [c for c in rs.load_cells() if c["status"] == "ok"]
    pos = [c for c in cells if c["block"] == "positive" and c["wrong"]]
    neg = [c for c in cells if c["block"] == "negative" and not c["wrong"]]

    def cmax(c, key):
        v = [s[key] for s in c["chain_stats"] if math.isfinite(s[key])]
        return max(v) if v else float("nan")

    def rel(c):
        r = [s["refined_leaf_rate"] for s in c["chain_stats"]]
        m = rs.median7(r)
        return max(r) / m if m > 0 else (math.inf if max(r) > 0 else 1.0)

    scores = {
        "R_cell_max": lambda c: cmax(c, "refined_leaf_rate"),
        "S_cell_max": lambda c: cmax(c, "step_collapse_factor"),
        "R_max_over_cell_median": rel,
        "depth_given_refined_cell_max": lambda c: cmax(c, "mean_refinement_depth_given_refined"),
    }
    out = {"note": "post hoc and descriptive; not evidence", "n_pos": len(pos), "n_neg": len(neg), "scores": {}}
    for name, f in scores.items():
        p = [f(c) for c in pos]
        n = [f(c) for c in neg]
        out["scores"][name] = {"auc": auc(p, n), "best_cut_post_hoc": best_cut(p, n),
                               "positives": {f"{c['model']}/{c['seed']}": f(c) for c in pos},
                               "negatives_top5": sorted(((f(c), f"{c['model']}/{c['seed']}") for c in neg), reverse=True)[:5]}
    stuck = {}
    for c in cells:
        if c["block"] != "positive":
            continue
        r = [s["refined_leaf_rate"] for s in c["chain_stats"]]
        d = c["max_chain_dmean_ref_sd"]
        stuck[f"{c['model']}/{c['seed']}"] = {"highest_R_chain": int(max(range(4), key=lambda k: r[k])),
                                              "furthest_chain": int(max(range(4), key=lambda k: d[k])),
                                              "chain_dmean_ref_sd": d, "R": r}
    out["highest_R_vs_furthest_chain"] = stuck
    (ART / "posthoc.json").write_text(json.dumps(out, indent=1, default=float) + "\n", encoding="utf-8")
    lines = ["# WP55 post-hoc descriptive analysis (not evidence)", "",
             f"{len(pos)} positive (positives-list, wrong) cells, {len(neg)} negative (negatives-list, clean) cells.", "",
             "| score | AUC | best post-hoc cut | sens | spec |", "|---|---:|---:|---:|---:|"]
    for name, v in out["scores"].items():
        b = v["best_cut_post_hoc"]
        lines.append(f"| {name} | {v['auc']:.3f} | {b['threshold']:.4g} | {b['sens']:.2f} | {b['spec']:.2f} |")
    lines += ["", "Top-5 negatives per score:", ""]
    for name, v in out["scores"].items():
        lines.append(f"* {name}: " + ", ".join(f"{m} {x:.4g}" for x, m in v["negatives_top5"]))
    lines += ["", "| positive cell | highest-R chain | furthest chain | chain distance (ref sd) | R per chain |", "|---|---:|---:|---|---|"]
    for k, v in stuck.items():
        lines.append(f"| {k} | {v['highest_R_chain']} | {v['furthest_chain']} | "
                     f"{' '.join(f'{x:.2f}' for x in v['chain_dmean_ref_sd'])} | {' '.join(f'{x:.4f}' for x in v['R'])} |")
    (ART / "posthoc.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
