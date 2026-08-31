#!/usr/bin/env python3
"""Analyze outer-selection-bps-vs-multinomial-v1 cells.

Reads artifacts/cell-*.json, computes ArviZ 1.3 bulk/tail ESS and rank R-hat
per functional (and per squared functional), ESS per retained target call,
lag-1 ACF, self-retention, E-BFMI, depth/leaf distributions, the safety gates
and the primary estimand, and writes artifacts/summary.json and
artifacts/RESULTS.md. It never samples.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import arviz as az
import numpy as np

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
FUNCTIONALS = PROTOCOL["functionals"]
ARMS = ["bps", "multinomial"]
SEEDS = PROTOCOL["seeds"]
GATES = PROTOCOL["health_gates_per_cell"]


def functionals(samples: np.ndarray) -> dict[str, np.ndarray]:
    """samples: [chain, draw, 10] unconstrained -> functional arrays [chain, draw]."""
    mu = samples[..., 0]
    tau = np.exp(samples[..., 1])
    z = samples[..., 2:]
    theta = mu[..., None] + tau[..., None] * z
    return {
        "mu": mu,
        "tau": tau,
        "mean_theta": theta.mean(axis=-1),
        "sd_theta": theta.std(axis=-1, ddof=0),
        "theta_1": theta[..., 0],
        "theta_8": theta[..., 7],
    }


def lag1(x: np.ndarray) -> float:
    vals = []
    for chain in x:
        c = chain - chain.mean()
        denom = float(np.dot(c, c))
        vals.append(float(np.dot(c[:-1], c[1:]) / denom) if denom > 0 else float("nan"))
    return float(np.mean(vals))


def e_bfmi(energy: np.ndarray) -> float:
    d = np.diff(energy)
    v = np.var(energy)
    return float(np.mean(d * d) / v) if v > 0 else float("nan")


def load_cell(arm: str, seed: int) -> dict:
    return json.loads((ART / f"cell-{arm}-{seed}.json").read_text(encoding="utf-8"))


def analyze_cell(cell: dict) -> dict:
    chains = cell["chains"]
    samples = np.asarray([c["samples"] for c in chains], dtype=float)  # [chain, draw, dim]
    finite = bool(np.isfinite(samples).all())
    f = functionals(samples)
    retained_calls = sum(c["retained_work"]["target_calls_total"] for c in chains)
    retained_transitions = sum(c["retained"] for c in chains)
    stats = {}
    for name, arr in f.items():
        bulk = float(az.ess(arr, method="bulk"))
        tail = float(az.ess(arr, method="tail", prob=(0.05, 0.95)))
        rhat = float(az.rhat(arr))
        sq = arr * arr
        bulk_sq = float(az.ess(sq, method="bulk"))
        stats[name] = {
            "mean": float(arr.mean()),
            "sd": float(arr.std(ddof=1)),
            "rhat": rhat,
            "bulk_ess": bulk,
            "tail_ess": tail,
            "bulk_ess_per_call": bulk / retained_calls,
            "tail_ess_per_call": tail / retained_calls,
            "squared_bulk_ess": bulk_sq,
            "squared_bulk_ess_per_call": bulk_sq / retained_calls,
            "squared_rhat": float(az.rhat(sq)),
            "lag1_acf": lag1(arr),
            "squared_lag1_acf": lag1(sq),
        }
    depth_all = np.concatenate([np.asarray(c["retained_transitions"]["depth"]) for c in chains])
    leaves_all = np.concatenate([np.asarray(c["retained_transitions"]["leaves_built"]) for c in chains])
    calls_all = np.concatenate([np.asarray(c["retained_transitions"]["target_evaluations"]) for c in chains])
    depth_counts = {int(k): int(v) for k, v in zip(*np.unique(depth_all, return_counts=True))}
    stops = {}
    for c in chains:
        for s in c["retained_transitions"]["stop"]:
            stops[s] = stops.get(s, 0) + 1
    max_depth_stops = sum(c["retained_work"]["maximum_depth_stops"] for c in chains)
    divergences = sum(c["retained_work"]["divergences"] for c in chains)
    invalid = sum(c["retained_work"]["invalid_evaluation_stops"] for c in chains)
    self_ret = sum(c["self_retained_transitions"] for c in chains)
    self_cmp = sum(c["self_retention_comparisons"] for c in chains)
    ebfmi = [e_bfmi(np.asarray(c["retained_transitions"]["initial_hamiltonian"])) for c in chains]
    max_rhat = max(s["rhat"] for s in stats.values())
    min_bulk = min(s["bulk_ess"] for s in stats.values())
    min_tail = min(s["tail_ess"] for s in stats.values())
    depth_rate = max_depth_stops / retained_transitions
    health = {
        "finite": finite,
        "max_rhat": max_rhat,
        "min_bulk_ess": min_bulk,
        "min_tail_ess": min_tail,
        "max_depth_rate": depth_rate,
        "divergences": divergences,
        "invalid_evaluation_stops": invalid,
        "passed": bool(
            finite
            and max_rhat <= GATES["rank_rhat_max"]
            and min_bulk >= GATES["bulk_ess_min"]
            and min_tail >= GATES["tail_ess_min"]
            and depth_rate <= GATES["max_depth_rate_max"]
            and divergences == 0
            and invalid == 0
        ),
    }
    return {
        "arm": cell["arm"],
        "seed": cell["seed"],
        "algorithm_revision": cell["algorithm_revision"],
        "sampler_wall_seconds": cell["sampler_wall_seconds"],
        "target_callbacks_total": cell["target_callbacks_total"],
        "retained_target_calls": retained_calls,
        "warmup_target_calls": sum(c["warmup_work"]["target_calls_total"] for c in chains),
        "retained_transitions": retained_transitions,
        "final_step_sizes": [c["final_step_size"] for c in chains],
        "functionals": stats,
        "health": health,
        "mechanism": {
            "self_retention_rate": self_ret / self_cmp if self_cmp else float("nan"),
            "self_retained_transitions": self_ret,
            "e_bfmi": ebfmi,
            "depth_counts": depth_counts,
            "mean_depth": float(depth_all.mean()),
            "mean_leaves_built": float(leaves_all.mean()),
            "mean_target_evaluations": float(calls_all.mean()),
            "stops": stops,
            "max_depth_stops": max_depth_stops,
        },
    }


def geomean(values) -> float:
    values = [float(v) for v in values]
    if any(v <= 0 or not math.isfinite(v) for v in values):
        return float("nan")
    return float(math.exp(sum(math.log(v) for v in values) / len(values)))


def main() -> None:
    cells = {arm: {seed: analyze_cell(load_cell(arm, seed)) for seed in SEEDS} for arm in ARMS}
    per_arm = {}
    for arm in ARMS:
        per_arm[arm] = {}
        for name in FUNCTIONALS:
            per_arm[arm][name] = {
                key: geomean(cells[arm][s]["functionals"][name][key] for s in SEEDS)
                for key in ("bulk_ess_per_call", "tail_ess_per_call", "squared_bulk_ess_per_call")
            }
    ratio = {
        name: {
            key: per_arm["bps"][name][key] / per_arm["multinomial"][name][key]
            for key in ("bulk_ess_per_call", "tail_ess_per_call", "squared_bulk_ess_per_call")
        }
        for name in FUNCTIONALS
    }
    primary = geomean(ratio[n]["bulk_ess_per_call"] for n in FUNCTIONALS)
    min_tail_ratio = min(ratio[n]["tail_ess_per_call"] for n in FUNCTIONALS)
    min_sq_ratio = min(ratio[n]["squared_bulk_ess_per_call"] for n in FUNCTIONALS)

    def pooled_depth_rate(arm):
        stops = sum(cells[arm][s]["mechanism"]["max_depth_stops"] for s in SEEDS)
        trans = sum(cells[arm][s]["retained_transitions"] for s in SEEDS)
        return stops / trans

    depth_delta = pooled_depth_rate("bps") - pooled_depth_rate("multinomial")
    zero_div = all(
        cells[arm][s]["health"]["divergences"] == 0 and cells[arm][s]["health"]["invalid_evaluation_stops"] == 0
        for arm in ARMS
        for s in SEEDS
    )
    all_healthy = all(cells[arm][s]["health"]["passed"] for arm in ARMS for s in SEEDS)
    gates = {
        "zero_divergences_and_invalid_evaluations": zero_div,
        "depth_cap_delta_le_0_005": bool(depth_delta <= 0.005),
        "depth_cap_delta": depth_delta,
        "min_tail_ess_per_call_ratio_ge_0_95": bool(min_tail_ratio >= 0.95),
        "min_tail_ess_per_call_ratio": min_tail_ratio,
        "min_squared_bulk_ess_per_call_ratio_ge_0_95": bool(min_sq_ratio >= 0.95),
        "min_squared_bulk_ess_per_call_ratio": min_sq_ratio,
        "all_cells_passed_health_gates": all_healthy,
    }
    safety = zero_div and gates["depth_cap_delta_le_0_005"] and gates["min_tail_ess_per_call_ratio_ge_0_95"] and gates["min_squared_bulk_ess_per_call_ratio_ge_0_95"]
    if not all_healthy:
        verdict = "primary_estimand_not_evaluable_health_gate_failure"
    elif primary >= 1.10 and safety:
        verdict = "bps_advantage_confirmed_default_stands"
    elif 0.90 < primary < 1.10:
        verdict = "no_material_difference_no_source_change"
    elif primary <= 0.90:
        verdict = "finding_against_default_multinomial_better"
    else:
        verdict = "bps_faster_but_safety_gate_failed"
    mech = {
        arm: {
            "self_retention_rate_mean": float(np.mean([cells[arm][s]["mechanism"]["self_retention_rate"] for s in SEEDS])),
            "e_bfmi_range": [
                float(min(min(cells[arm][s]["mechanism"]["e_bfmi"]) for s in SEEDS)),
                float(max(max(cells[arm][s]["mechanism"]["e_bfmi"]) for s in SEEDS)),
            ],
            "mean_depth": float(np.mean([cells[arm][s]["mechanism"]["mean_depth"] for s in SEEDS])),
            "mean_leaves_built": float(np.mean([cells[arm][s]["mechanism"]["mean_leaves_built"] for s in SEEDS])),
            "mean_target_evaluations_per_transition": float(np.mean([cells[arm][s]["mechanism"]["mean_target_evaluations"] for s in SEEDS])),
            "lag1_acf_mean_over_seeds": {
                n: float(np.mean([cells[arm][s]["functionals"][n]["lag1_acf"] for s in SEEDS])) for n in FUNCTIONALS
            },
            "wall_seconds": [cells[arm][s]["sampler_wall_seconds"] for s in SEEDS],
            "retained_target_calls": [cells[arm][s]["retained_target_calls"] for s in SEEDS],
        }
        for arm in ARMS
    }
    summary = {
        "schema": "owalnuts-outer-selection-ablation-summary/v1",
        "protocol": PROTOCOL["name"],
        "work_unit": PROTOCOL["work_unit"],
        "primary_ratio_bps_over_multinomial": primary,
        "advancement_criterion_met": bool(primary >= 1.10 and safety and all_healthy),
        "safety_gates": gates,
        "verdict": verdict,
        "per_functional_ratio_bps_over_multinomial": ratio,
        "per_arm_geomean_over_seeds": per_arm,
        "mechanism": mech,
        "cells": {arm: {str(s): cells[arm][s] for s in SEEDS} for arm in ARMS},
    }
    (ART / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")

    lines = ["# Results: outer-selection-bps-vs-multinomial-v1", ""]
    lines.append(f"Primary ratio (BPS / multinomial, bulk ESS per retained target call, geomean over six functionals): **{primary:.4f}**")
    lines.append(f"Verdict: **{verdict}**")
    lines.append("")
    lines.append("## Per-functional ratios (BPS / multinomial)")
    lines.append("")
    lines.append("| functional | bulk ESS/call | tail ESS/call | squared bulk ESS/call | lag-1 ACF bps | lag-1 ACF multinomial |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for n in FUNCTIONALS:
        lines.append(
            f"| {n} | {ratio[n]['bulk_ess_per_call']:.4f} | {ratio[n]['tail_ess_per_call']:.4f} | {ratio[n]['squared_bulk_ess_per_call']:.4f} | {mech['bps']['lag1_acf_mean_over_seeds'][n]:+.4f} | {mech['multinomial']['lag1_acf_mean_over_seeds'][n]:+.4f} |"
        )
    lines.append("")
    lines.append("## Safety gates")
    lines.append("")
    for k, v in gates.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Per-cell health")
    lines.append("")
    lines.append("| arm | seed | max R-hat | min bulk ESS | min tail ESS | depth-cap rate | div | invalid | retained calls | wall s | passed |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for arm in ARMS:
        for s in SEEDS:
            c = cells[arm][s]
            h = c["health"]
            lines.append(
                f"| {arm} | {s} | {h['max_rhat']:.5f} | {h['min_bulk_ess']:.1f} | {h['min_tail_ess']:.1f} | {h['max_depth_rate']:.5f} | {h['divergences']} | {h['invalid_evaluation_stops']} | {c['retained_target_calls']} | {c['sampler_wall_seconds']:.3f} | {h['passed']} |"
            )
    lines.append("")
    lines.append("## Mechanism")
    lines.append("")
    lines.append("| arm | self-retention | E-BFMI range | mean depth | mean leaves built | mean calls/transition |")
    lines.append("|---|---:|---|---:|---:|---:|")
    for arm in ARMS:
        m = mech[arm]
        lines.append(
            f"| {arm} | {m['self_retention_rate_mean']:.5f} | {m['e_bfmi_range'][0]:.3f}–{m['e_bfmi_range'][1]:.3f} | {m['mean_depth']:.3f} | {m['mean_leaves_built']:.2f} | {m['mean_target_evaluations_per_transition']:.2f} |"
        )
    lines.append("")
    lines.append("## Per-cell, per-functional bulk ESS")
    lines.append("")
    lines.append("| arm | seed | " + " | ".join(FUNCTIONALS) + " |")
    lines.append("|---|---:|" + "---:|" * len(FUNCTIONALS))
    for arm in ARMS:
        for s in SEEDS:
            c = cells[arm][s]
            lines.append(f"| {arm} | {s} | " + " | ".join(f"{c['functionals'][n]['bulk_ess']:.1f}" for n in FUNCTIONALS) + " |")
    (ART / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
