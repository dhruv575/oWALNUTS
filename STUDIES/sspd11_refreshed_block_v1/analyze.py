#!/usr/bin/env python3
"""Post-processing only for the WP16 refreshed-block study.

Reads `artifacts/run-2000` and `artifacts/run-4000` (arms I, P, R × three
seeds on sspd-11) plus the report-only sanity cell, recomputes ArviZ
rank-normalised diagnostics on the eight functionals, evaluates the WP12
gates, agreement (P and R vs I same seed/draws, and vs the WP4b NumPyro
reference), the per-arm confirmation rule, ESS-per-call ratios, and the five
preregistered predictions. Writes `artifacts/summary.json` and
`artifacts/RESULTS.md`. Never invokes a sampler.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import arviz as az
import numpy as np

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
FUNCTIONALS = PROTOCOL["functionals"]
GATES = PROTOCOL["gates"]
REPO = HERE.parents[1]
SEEDS = PROTOCOL["seeds"]["sspd-11"]
VARIANTS = PROTOCOL["retained_variants"]
CHAINS = PROTOCOL["owalnuts_common"]["chains"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sanitize(obj):
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, np.ndarray):
        return sanitize(obj.tolist())
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    return obj


def diagnostics(draws: np.ndarray, names: list[str]) -> dict:
    out = {}
    for j, name in enumerate(names):
        x = draws[:, :, j]
        bulk = float(az.ess(x, method="bulk"))
        tail = float(az.ess(x, method="tail", prob=(0.05, 0.95)))
        rhat = float(az.rhat(x, method="rank"))
        sd = float(x.std(ddof=1))
        out[name] = {
            "mean": float(x.mean()),
            "sd": sd,
            "rhat": rhat,
            "bulk_ess": bulk,
            "tail_ess": tail,
            "mcse": sd / math.sqrt(max(bulk, 1.0)),
        }
    return out


def load_run(run_dir: Path, fixture: str, arm: str, seed: int, retained: int):
    record = json.loads((run_dir / f"{fixture}-{arm}-{seed}.json").read_text(encoding="utf-8"))
    if record.get("status") == "failed":
        return record, None
    raw = np.fromfile(run_dir / record["functionals_file"], dtype="<f8")
    draws = raw.reshape(CHAINS, retained, len(FUNCTIONALS))
    return record, draws


def gate_row(diag: dict, record: dict) -> dict:
    worst_rhat = max(v["rhat"] for v in diag.values())
    min_bulk = min(v["bulk_ess"] for v in diag.values())
    min_tail = min(v["tail_ess"] for v in diag.values())
    checks = {
        "max_rhat": worst_rhat <= GATES["max_rhat"],
        "min_bulk_ess": min_bulk >= GATES["min_bulk_ess"],
        "min_tail_ess": min_tail >= GATES["min_tail_ess"],
        "retained_divergences": record["retained_divergences"] == 0,
        "retained_refinement_exhaustions": record["retained_refinement_exhaustions"] == 0,
        "max_depth_rate": record["max_depth_rate"] <= GATES["max_depth_rate"],
    }
    return {
        "worst_rhat": worst_rhat,
        "min_bulk_ess": min_bulk,
        "min_tail_ess": min_tail,
        "max_depth_rate": record["max_depth_rate"],
        "checks": checks,
        "pass": all(checks.values()),
    }


def agreement(diag_a: dict, diag_b: dict, multiple: float) -> dict:
    rows, ok = {}, True
    for name in FUNCTIONALS:
        a, b = diag_a[name], diag_b[name]
        combined = math.sqrt(a["mcse"] ** 2 + b["mcse"] ** 2)
        z = (a["mean"] - b["mean"]) / combined if combined > 0 else math.inf
        ok = ok and abs(z) <= multiple
        rows[name] = {"mean_a": a["mean"], "mean_b": b["mean"], "z": z}
    return {"rows": rows, "max_abs_z": max(abs(r["z"]) for r in rows.values()), "pass": ok}


def load_reference() -> dict:
    ref = PROTOCOL["reference"]
    json_path = REPO / ref["file"]
    npy_path = REPO / ref["functionals_npy"]
    assert sha256(json_path) == ref["sha256"], "reference JSON hash mismatch"
    assert sha256(npy_path) == ref["functionals_npy_sha256"], "reference .npy hash mismatch"
    return {"diag": diagnostics(np.load(npy_path), FUNCTIONALS)}


def main() -> int:
    reference = load_reference()
    summary = {"schema": "sspd11-refreshed-block-v1/summary", "variants": {}}
    for retained in VARIANTS:
        run_dir = HERE / "artifacts" / f"run-{retained}"
        variant = {"arms": {}}
        diags = {}
        for arm in ("I", "P", "R"):
            rows = {}
            for seed in SEEDS:
                record, draws = load_run(run_dir, "sspd-11", arm, seed, retained)
                if draws is None:
                    rows[str(seed)] = {"status": "failed", "error": record.get("error")}
                    continue
                diag = diagnostics(draws, FUNCTIONALS)
                diags[(arm, seed)] = diag
                row = gate_row(diag, record)
                row["functionals"] = diag
                row["retained_calls"] = record["target_calls_retained"]
                row["total_calls"] = record["target_calls_telemetry_total"]
                row["wall_seconds"] = record["wall_seconds"]
                row["median_depth"] = record["median_depth"]
                row["ess_per_retained_call"] = row["min_bulk_ess"] / record["target_calls_retained"]
                if arm == "R":
                    row["installed"] = record["extra"]["installed"]
                    row["refresh_failures"] = record["extra"]["refresh_failures"]
                rows[str(seed)] = row
            variant["arms"][arm] = rows
        # Agreement and ratios.
        for arm in ("P", "R"):
            for seed in SEEDS:
                key = (arm, seed)
                if key not in diags or ("I", seed) not in diags:
                    continue
                row = variant["arms"][arm][str(seed)]
                row["agreement_vs_I"] = agreement(
                    diags[key], diags[("I", seed)], GATES["agreement_P_vs_I_combined_mcse_multiple"]
                )
                row["agreement_vs_N"] = agreement(
                    diags[key], reference["diag"], GATES["agreement_P_vs_N_combined_mcse_multiple"]
                )
                row["pass"] = row["pass"] and row["agreement_vs_I"]["pass"] and row["agreement_vs_N"]["pass"]
        for arm in ("I", "P", "R"):
            rows = variant["arms"][arm]
            passes = [r.get("pass", False) for r in rows.values()]
            variant["arms"][arm + "_confirmed"] = all(passes)
            variant["arms"][arm + "_pass_count"] = sum(passes)
        variant["ratios"] = {}
        for seed in SEEDS:
            row = {}
            for pair in (("R", "P"), ("R", "I"), ("P", "I")):
                a, b = pair
                ra = variant["arms"][a].get(str(seed), {})
                rb = variant["arms"][b].get(str(seed), {})
                if "ess_per_retained_call" in ra and "ess_per_retained_call" in rb:
                    row[f"{a}_over_{b}"] = ra["ess_per_retained_call"] / rb["ess_per_retained_call"]
            variant["ratios"][str(seed)] = row
        summary["variants"][str(retained)] = variant

    # Predictions.
    v2, v4 = summary["variants"]["2000"], summary["variants"]["4000"]
    p1 = all(
        v["arms"]["R"][str(seed)].get("refresh_failures", 1) == 0
        and v["arms"]["R"][str(seed)].get("installed", 0) >= CHAINS
        for v in (v2, v4)
        for seed in SEEDS
        if "installed" in v["arms"]["R"].get(str(seed), {})
    )
    p2 = v4["arms"]["R_confirmed"]
    p3_hits = sum(
        1
        for seed in SEEDS
        if v2["arms"]["R"][str(seed)].get("worst_rhat", math.inf)
        <= v2["arms"]["P"][str(seed)].get("worst_rhat", math.inf)
    )
    ratios_rp = [
        v["ratios"][str(seed)].get("R_over_P")
        for v in (v2, v4)
        for seed in SEEDS
        if v["ratios"][str(seed)].get("R_over_P") is not None
    ]
    ratios_ri = [
        v["ratios"][str(seed)].get("R_over_I")
        for v in (v2, v4)
        for seed in SEEDS
        if v["ratios"][str(seed)].get("R_over_I") is not None
    ]
    p4 = all(0.8 <= r <= 1.6 for r in ratios_rp) and all(r >= 2.0 for r in ratios_ri)
    p5 = v4["arms"]["P_confirmed"]
    summary["predictions"] = {
        "P1_installs_no_failures": p1,
        "P2_R_confirmed_at_4000": p2,
        "P3_R_rhat_le_P_at_2000_hits": p3_hits,
        "P3_pass": p3_hits >= 2,
        "P4_efficiency_band": p4,
        "P4_R_over_P_range": [min(ratios_rp), max(ratios_rp)] if ratios_rp else None,
        "P4_R_over_I_range": [min(ratios_ri), max(ratios_ri)] if ratios_ri else None,
        "P5_P_confirmed_at_4000": p5,
    }

    # Sanity cell (report only).
    sanity_dir = HERE / "artifacts" / "sanity"
    sanity = {}
    if sanity_dir.exists():
        for arm in ("I", "R"):
            path = sanity_dir / f"sspd-05-{arm}-{PROTOCOL['sanity']['seed']}.json"
            if path.exists():
                record, draws = load_run(
                    sanity_dir, "sspd-05", arm, PROTOCOL["sanity"]["seed"], PROTOCOL["sanity"]["retained"]
                )
                if draws is not None:
                    diag = diagnostics(draws, FUNCTIONALS)
                    sanity[arm] = gate_row(diag, record)
    summary["sanity_sspd05_report_only"] = sanity

    out = HERE / "artifacts"
    (out / "summary.json").write_text(
        json.dumps(sanitize(summary), indent=1), encoding="utf-8"
    )

    lines = ["# WP16 results", ""]
    for retained in VARIANTS:
        v = summary["variants"][str(retained)]
        lines.append(f"## 4×500/{retained}")
        lines.append("")
        lines.append("| arm | seed | worst R-hat | min bulk | min tail | cap | pass | ESS/call | vs I max|z| | vs N max|z| |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for arm in ("I", "P", "R"):
            for seed in SEEDS:
                r = v["arms"][arm][str(seed)]
                if r.get("status") == "failed":
                    lines.append(f"| {arm} | {seed} | failed | | | | FAIL | | | |")
                    continue
                ai = r.get("agreement_vs_I", {}).get("max_abs_z")
                an = r.get("agreement_vs_N", {}).get("max_abs_z")
                lines.append(
                    f"| {arm} | {seed} | {r['worst_rhat']:.4f} | {r['min_bulk_ess']:.0f} | "
                    f"{r['min_tail_ess']:.0f} | {r['max_depth_rate']:.4f} | "
                    f"{'pass' if r['pass'] else 'FAIL'} | {r['ess_per_retained_call']:.2e} | "
                    f"{'' if ai is None else f'{ai:.2f}'} | {'' if an is None else f'{an:.2f}'} |"
                )
        for arm in ("I", "P", "R"):
            lines.append(
                f"- {arm}: {v['arms'][arm + '_pass_count']}/{len(SEEDS)}"
                f"{' — confirmed' if v['arms'][arm + '_confirmed'] else ''}"
            )
        lines.append("")
    lines.append("## Predictions")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(sanitize(summary["predictions"]), indent=1))
    lines.append("```")
    (out / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(sanitize(summary["predictions"]), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
