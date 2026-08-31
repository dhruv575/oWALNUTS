#!/usr/bin/env python3
"""Analyse the v9 Eight Schools re-benchmark against the frozen v38 (v7) evidence."""
from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path

import arviz as az
import numpy as np

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
V38 = Path(PROTOCOL["reference_evidence"]["v38_confirmation_analysis"])
V3 = Path(PROTOCOL["reference_evidence"]["release_v3_finalized"])
FUNCTIONALS = PROTOCOL["functionals"]
PAIRED = PROTOCOL["seeds"]["paired_v38"]
FRESH = PROTOCOL["seeds"]["fresh"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def functionals(q: np.ndarray) -> dict[str, np.ndarray]:
    mu = q[..., 0]
    tau = np.exp(q[..., 1])
    theta = mu[..., None] + tau[..., None] * q[..., 2:]
    return {
        "mu": mu,
        "tau": tau,
        "mean_theta": theta.mean(-1),
        "sd_theta": theta.std(-1),
        "theta_1": theta[..., 0],
        "theta_8": theta[..., 7],
    }


def cell_metrics(cell: dict) -> dict:
    q = np.asarray([c["samples"] for c in cell["chains_data"]], dtype=np.float64)
    assert q.shape == (4, 1000, 10)
    walls = cell["wall_seconds"]
    wall = statistics.median(walls)
    work = int(statistics.median(cell["callbacks_started"]))
    assert len(set(cell["callbacks_started"])) == 1, "work differs across repetitions"
    retained = 4 * 1000
    div = sum(int(c["divergences"]) for c in cell["chains_data"])
    depth = sum(int(c["maximum_depth_stops"]) for c in cell["chains_data"])
    invalid = sum(int(c["invalid_stops"]) for c in cell["chains_data"])
    exhaust = sum(int(c["refinement_exhaustions"]) for c in cell["chains_data"])
    reasons = []
    if div / retained > 0.01:
        reasons.append("divergence_rate > 0.01")
    if depth / retained > 0.01:
        reasons.append("max_depth_rate > 0.01")
    if invalid:
        reasons.append("invalid_stops != 0")
    if exhaust:
        reasons.append("refinement_exhaustions != 0")
    if not np.isfinite(q).all():
        reasons.append("nonfinite samples")
    out = {}
    for name, x in functionals(q).items():
        bulk = float(az.ess(x, method="bulk"))
        tail = float(az.ess(x, method="tail", prob=(0.05, 0.95)))
        rhat = float(az.rhat(x))
        mcse = float(az.mcse(x, method="mean"))
        out[name] = {
            "rank_rhat": rhat,
            "bulk_ess": bulk,
            "tail_ess": tail,
            "posterior_mean": float(x.mean()),
            "posterior_sd": float(x.std(ddof=1)),
            "mean_mcse": mcse,
            "bulk_ess_per_total_second": bulk / wall,
            "tail_ess_per_total_second": tail / wall,
            "bulk_ess_per_total_second_min_wall": bulk / min(walls),
            "bulk_ess_per_total_second_max_wall": bulk / max(walls),
            "bulk_ess_per_work": bulk / work,
            "tail_ess_per_work": tail / work,
        }
        if rhat > 1.01:
            reasons.append(f"{name}: rank Rhat > 1.01")
        if bulk < 400:
            reasons.append(f"{name}: bulk ESS < 400")
        if tail < 400:
            reasons.append(f"{name}: tail ESS < 400")
    return {
        "seed": cell["seed"],
        "seed_class": cell["seed_class"],
        "algorithm_revision": cell["algorithm_revision"],
        "wall_seconds_median": wall,
        "wall_seconds_min": min(walls),
        "wall_seconds_max": max(walls),
        "wall_seconds_all": walls,
        "work": work,
        "warmup_target_calls": sum(int(c["warmup_target_calls"]) for c in cell["chains_data"]),
        "retained_target_calls": sum(int(c["retained_target_calls"]) for c in cell["chains_data"]),
        "final_step_sizes": [c["final_step_size"] for c in cell["chains_data"]],
        "health": {
            "divergences": div,
            "maximum_depth_stops": depth,
            "invalid_stops": invalid,
            "refinement_exhaustions": exhaust,
            "passed": not reasons,
            "reasons": sorted(set(reasons)),
        },
        "functionals": out,
    }


def aggregate(rows: list[dict]) -> dict:
    """Both aggregations over a set of per-seed rows."""
    result = {}
    for metric in ("bulk_ess_per_total_second", "tail_ess_per_total_second", "bulk_ess_per_work", "tail_ess_per_work"):
        by_functional = {
            name: [r["functionals"][name][metric] for r in rows] for name in FUNCTIONALS
        }
        result[metric] = {
            "release_style_min_of_across_seed_median": min(
                statistics.median(v) for v in by_functional.values()
            ),
            "true_minimum_over_seeds_and_functionals": min(
                x for v in by_functional.values() for x in v
            ),
            "median_over_seeds_and_functionals": statistics.median(
                x for v in by_functional.values() for x in v
            ),
            "argmin": min(
                ((x, name, rows[i]["seed"]) for name, v in by_functional.items() for i, x in enumerate(v)),
                key=lambda t: t[0],
            )[1:],
        }
    return result


def v38_rows() -> list[dict]:
    doc = json.loads(V38.read_text(encoding="utf-8"))
    rows = []
    for cell in doc["cell_metrics"]:
        if cell["backend"] != "rust":
            continue
        rows.append(
            {
                "seed": cell["seed"],
                "wall_seconds_median": cell["wall_seconds"],
                "work": cell["work"]["value"],
                "functionals": cell["functionals"],
                "health": cell["health"],
            }
        )
    rows.sort(key=lambda r: PAIRED.index(r["seed"]))
    return rows


def agreement(v9: dict, v7: dict) -> dict:
    out = {}
    for name in FUNCTIONALS:
        a, b = v9["functionals"][name], v7["functionals"][name]
        pooled_sd = 0.5 * (a["posterior_sd"] + b["posterior_sd"])
        pooled_mcse = 0.5 * (a["mean_mcse"] + b["mean_mcse"])
        mean_bound = 0.10 * pooled_sd + 2 * pooled_mcse
        sd_bound = 0.15 * pooled_sd + 2 * pooled_mcse
        mean_err = abs(a["posterior_mean"] - b["posterior_mean"])
        sd_err = abs(a["posterior_sd"] - b["posterior_sd"])
        out[name] = {
            "mean_error": mean_err,
            "mean_bound": mean_bound,
            "sd_error": sd_err,
            "sd_bound": sd_bound,
            "passed": mean_err <= mean_bound and sd_err <= sd_bound,
        }
    return out


def main() -> None:
    v3 = json.loads(V3.read_text(encoding="utf-8"))
    strict = {k: v3["competitors"][k] for k in ("cmdstan", "blackjax", "numpyro")}
    release_owalnuts = v3["competitors"]["owalnuts"]

    cells = {}
    for seed in PAIRED + FRESH:
        path = ART / f"cell-{seed}.json"
        cells[seed] = cell_metrics(json.loads(path.read_text(encoding="utf-8")))
    revisions = {c["algorithm_revision"] for c in cells.values()}
    assert revisions == {PROTOCOL["kernel_under_test"]["algorithm_revision_required"]}, revisions

    paired_v9 = [cells[s] for s in PAIRED]
    fresh_v9 = [cells[s] for s in FRESH]
    paired_v7 = v38_rows()

    agg_v7 = aggregate(paired_v7)
    agg_v9_paired = aggregate(paired_v9)
    agg_v9_fresh = aggregate(fresh_v9)
    agg_v9_all = aggregate(paired_v9 + fresh_v9)

    # Sanity: the release figure must be reproduced from the v38 file.
    rel_b = agg_v7["bulk_ess_per_total_second"]["release_style_min_of_across_seed_median"]
    rel_t = agg_v7["tail_ess_per_total_second"]["release_style_min_of_across_seed_median"]
    release_reproduced = (
        abs(rel_b - release_owalnuts["min_bulk_ess_s"]) < 1e-6
        and abs(rel_t - release_owalnuts["min_tail_ess_s"]) < 1e-6
    )

    def beats_all(bulk: float, tail: float) -> dict:
        return {
            name: bool(bulk > c["min_bulk_ess_s"] and tail > c["min_tail_ess_s"])
            for name, c in strict.items()
        }

    verdict = {}
    for label, agg in (("v7_paired", agg_v7), ("v9_paired", agg_v9_paired), ("v9_fresh", agg_v9_fresh), ("v9_all_seven_seeds", agg_v9_all)):
        verdict[label] = {}
        for style in ("release_style_min_of_across_seed_median", "true_minimum_over_seeds_and_functionals"):
            b = agg["bulk_ess_per_total_second"][style]
            t = agg["tail_ess_per_total_second"][style]
            per = beats_all(b, t)
            verdict[label][style] = {
                "bulk_ess_s": b,
                "tail_ess_s": t,
                "beats": per,
                "beats_all_strict": all(per.values()),
                "margin_over_best_competitor_bulk": b / max(c["min_bulk_ess_s"] for c in strict.values()),
                "margin_over_best_competitor_tail": t / max(c["min_tail_ess_s"] for c in strict.values()),
            }

    paired_ratios = {}
    for v9, v7 in zip(paired_v9, paired_v7):
        assert v9["seed"] == v7["seed"]
        paired_ratios[str(v9["seed"])] = {
            "work_v9_over_v7": v9["work"] / v7["work"],
            "wall_v9_over_v7": v9["wall_seconds_median"] / v7["wall_seconds_median"],
            "bulk_ess_per_work_v9_over_v7": {
                n: v9["functionals"][n]["bulk_ess_per_work"] / v7["functionals"][n]["bulk_ess_per_work"] for n in FUNCTIONALS
            },
            "tail_ess_per_work_v9_over_v7": {
                n: v9["functionals"][n]["tail_ess_per_work"] / v7["functionals"][n]["tail_ess_per_work"] for n in FUNCTIONALS
            },
            "agreement_vs_v7": agreement(v9, v7),
        }
    geo = lambda xs: float(np.exp(np.mean(np.log(xs))))
    bulk_ratio_geo = geo([r["bulk_ess_per_work_v9_over_v7"][n] for r in paired_ratios.values() for n in FUNCTIONALS])
    tail_ratio_geo = geo([r["tail_ess_per_work_v9_over_v7"][n] for r in paired_ratios.values() for n in FUNCTIONALS])

    summary = {
        "schema": "eight-schools-v9-rebench-v1-summary",
        "protocol_sha256": sha256(HERE / "protocol.json"),
        "v38_analysis_sha256": sha256(V38),
        "v38_analysis_sha256_expected": PROTOCOL["reference_evidence"]["v38_confirmation_analysis_sha256"],
        "v3_finalized_sha256": sha256(V3),
        "release_figure_reproduced_from_v38_file": release_reproduced,
        "release_figure": release_owalnuts,
        "strict_competitors_v3": strict,
        "cells_v9": {str(s): cells[s] for s in PAIRED + FRESH},
        "cells_v7_paired": {str(r["seed"]): r for r in paired_v7},
        "aggregates": {
            "v7_paired": agg_v7,
            "v9_paired": agg_v9_paired,
            "v9_fresh": agg_v9_fresh,
            "v9_all_seven_seeds": agg_v9_all,
        },
        "paired_ratios": paired_ratios,
        "paired_geomean_bulk_ess_per_work_v9_over_v7": bulk_ratio_geo,
        "paired_geomean_tail_ess_per_work_v9_over_v7": tail_ratio_geo,
        "all_v9_health_passed": all(c["health"]["passed"] for c in cells.values()),
        "all_paired_agreement_passed": all(
            f["passed"] for r in paired_ratios.values() for f in r["agreement_vs_v7"].values()
        ),
        "verdict": verdict,
    }
    (ART / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = ["| kernel | seeds | aggregation | bulk ESS/s | tail ESS/s | bulk ESS/call | tail ESS/call | beats all strict |", "|---|---|---|---:|---:|---:|---:|---|"]
    for label, agg in (("v7", agg_v7), ("v9", agg_v9_paired), ("v9", agg_v9_fresh), ("v9", agg_v9_all)):
        seeds = {id(agg_v7): "paired 4", id(agg_v9_paired): "paired 4", id(agg_v9_fresh): "fresh 3", id(agg_v9_all): "all 7"}[id(agg)]
        key = {id(agg_v7): "v7_paired", id(agg_v9_paired): "v9_paired", id(agg_v9_fresh): "v9_fresh", id(agg_v9_all): "v9_all_seven_seeds"}[id(agg)]
        for style, short in (("release_style_min_of_across_seed_median", "min of seed-median"), ("true_minimum_over_seeds_and_functionals", "true min")):
            lines.append(
                f"| {label} | {seeds} | {short} | {agg['bulk_ess_per_total_second'][style]:,.2f} | {agg['tail_ess_per_total_second'][style]:,.2f} | "
                f"{agg['bulk_ess_per_work'][style]:.5f} | {agg['tail_ess_per_work'][style]:.5f} | {verdict[key][style]['beats_all_strict']} |"
            )
    (ART / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print("release figure reproduced from v38 file:", release_reproduced)
    print("paired geomean ESS/call v9/v7: bulk", round(bulk_ratio_geo, 4), "tail", round(tail_ratio_geo, 4))
    print("all v9 health passed:", summary["all_v9_health_passed"], "| paired agreement passed:", summary["all_paired_agreement_passed"])


if __name__ == "__main__":
    main()
