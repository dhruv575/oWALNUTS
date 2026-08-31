#!/usr/bin/env python3
"""Post-processing for the canonical-v3 study.

Reads `artifacts/numpyro` (arm N3) and `artifacts/owalnuts-v1` (V2-I, V3-D,
V3-A, V2-A), recomputes ArviZ rank-normalised diagnostics on the eight
functionals, evaluates the preregistered gates and agreements, and writes
`summary.json` + `results-table.md` into the oWALNUTS run directory.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import arviz as az
import numpy as np

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text())
FUNCTIONALS = PROTOCOL["functionals"]
GATES = PROTOCOL["gates"]
AGREEMENTS = [("V3-D", "V2-I"), ("V3-A", "V3-D"), ("V3-D", "N3"), ("V3-A", "N3"), ("V2-A", "V2-I")]


def sanitize(obj):
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    if isinstance(obj, np.ndarray):
        return sanitize(obj.tolist())
    return obj


def diagnostics(draws: np.ndarray) -> dict:
    out = {}
    for j, name in enumerate(FUNCTIONALS):
        x = draws[:, :, j]
        if np.ptp(x) <= 1e-12 * (1.0 + abs(float(x[0, 0]))):
            continue  # frozen functional (no variation): skip rather than emit NaN
        bulk = float(az.ess(x, method="bulk"))
        tail = float(az.ess(x, method="tail", prob=(0.05, 0.95)))
        rhat = float(az.rhat(x, method="rank"))
        sd = float(x.std(ddof=1))
        out[name] = {"rhat": rhat, "bulk_ess": bulk, "tail_ess": tail, "mean": float(x.mean()),
                     "sd": sd, "mcse": sd / np.sqrt(max(bulk, 1.0))}
    return out


def gate_row(diag: dict, health: dict) -> dict:
    max_rhat = max(d["rhat"] for d in diag.values())
    min_bulk = min(d["bulk_ess"] for d in diag.values())
    min_tail = min(d["tail_ess"] for d in diag.values())
    return {
        "max_rhat": {"limit": GATES["max_rhat"], "observed": max_rhat, "passed": max_rhat <= GATES["max_rhat"]},
        "min_bulk_ess": {"limit": GATES["min_bulk_ess"], "observed": min_bulk, "passed": min_bulk >= GATES["min_bulk_ess"]},
        "min_tail_ess": {"limit": GATES["min_tail_ess"], "observed": min_tail, "passed": min_tail >= GATES["min_tail_ess"]},
        "retained_divergences": {"limit": 0, "observed": health["divergences"], "passed": health["divergences"] == 0},
        "retained_invalid_evaluations": {"limit": 0, "observed": health["invalid"], "passed": health["invalid"] == 0},
        "retained_refinement_exhaustions": {"limit": 0, "observed": health["exhausted"], "passed": health["exhausted"] == 0},
        "max_depth_rate": {"limit": GATES["max_depth_rate"], "observed": health["cap_rate"], "passed": health["cap_rate"] <= GATES["max_depth_rate"]},
    }


def agreement(diag_a: dict, diag_b: dict) -> dict:
    rows = {}
    worst = 0.0
    for name in [n for n in FUNCTIONALS if n in diag_a and n in diag_b]:
        a, b = diag_a[name], diag_b[name]
        combined = np.sqrt(a["mcse"] ** 2 + b["mcse"] ** 2)
        z = (a["mean"] - b["mean"]) / combined if combined > 0 else float("inf")
        rows[name] = {"mean_a": a["mean"], "mean_b": b["mean"], "combined_mcse": float(combined), "z": float(z)}
        worst = max(worst, abs(float(z)))
    return {"functionals": rows, "max_abs_z": worst, "passed": worst <= GATES["agreement_combined_mcse_multiple"]}


def load_numpyro(dirpath: Path, fixture: str, seed: int):
    path = dirpath / f"{fixture}-N3-{seed}.json"
    if not path.exists():
        return None
    rec = json.loads(path.read_text())
    draws = np.load(dirpath / rec["functionals_file"])
    diag = diagnostics(draws)
    health = {"divergences": rec["sampler"]["divergences"], "invalid": 0, "exhausted": 0,
              "cap_rate": rec["sampler"]["max_depth_rate"]}
    return {
        "fixture": fixture, "arm": "N3", "backend": "numpyro", "seed": seed, "status": "completed",
        "median_depth": rec["sampler"]["median_depth"], "depth_histogram": rec["sampler"]["depth_histogram"],
        "max_depth_rate": rec["sampler"]["max_depth_rate"], "divergences": rec["sampler"]["divergences"],
        "retained_leapfrogs": rec["sampler"]["retained_leapfrogs"],
        "wall_seconds": rec["timing_seconds"]["end_to_end"], "sampling_seconds": rec["timing_seconds"]["sampling"],
        "final_step_sizes": rec["sampler"]["final_step_sizes"],
        "functionals": diag, "gates": gate_row(diag, health), "deviation": rec.get("deviation"),
        "min_bulk_ess_per_work_unit": min(d["bulk_ess"] for d in diag.values()) / rec["sampler"]["retained_leapfrogs"],
        "work_unit": "leapfrog (NumPyro num_steps proxy; not a fused target call)",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owalnuts", type=Path, default=HERE / "artifacts" / "owalnuts-v1")
    ap.add_argument("--numpyro", type=Path, default=HERE / "artifacts" / "numpyro")
    args = ap.parse_args()
    args.owalnuts = args.owalnuts.resolve()
    args.numpyro = args.numpyro.resolve()
    index = json.loads((args.owalnuts / "index.json").read_text())
    results = []
    for fixture in PROTOCOL["fixture_order"]:
        ref = load_numpyro(args.numpyro, fixture, PROTOCOL["seeds"][fixture])
        if ref is not None:
            results.append(ref)
    for stem in index["runs"]:
        rec = json.loads((args.owalnuts / f"{stem}.json").read_text())
        fixture, arm = rec["fixture"], rec["arm"]
        if rec.get("status") == "failed":
            results.append({"fixture": fixture, "arm": arm, "backend": "owalnuts", "seed": rec["seed"], "status": "failed",
                            "error_kind": rec["error_kind"], "error": rec["error"], "wall_seconds": rec["wall_seconds"],
                            "target_calls": rec["target_calls_counter"], "algorithm_revision": rec["algorithm_revision"],
                            "kernel_commit": rec["kernel_commit"]})
            continue
        draws = np.fromfile(args.owalnuts / rec["functionals_file"], dtype="<f8").reshape(
            rec["settings"]["chains"], rec["settings"]["retained"], len(FUNCTIONALS))
        diag = diagnostics(draws)
        health = {"divergences": rec["retained_divergences"], "invalid": rec["retained_invalid_evaluations"],
                  "exhausted": rec["retained_refinement_exhaustions"], "cap_rate": rec["max_depth_rate"]}
        results.append({
            "fixture": fixture, "arm": arm, "backend": "owalnuts", "seed": rec["seed"], "status": "completed",
            "arm_label": rec["arm_label"], "model_revision": rec["model_revision"],
            "algorithm_revision": rec["algorithm_revision"], "paper_adaptation_revision": rec.get("paper_adaptation_revision"),
            "kernel_commit": rec["kernel_commit"], "preflight": rec["preflight"],
            "median_depth": rec["median_depth"], "depth_histogram": rec["depth_histogram"], "max_depth_rate": rec["max_depth_rate"],
            "stops": rec["stops"], "divergences": rec["retained_divergences"], "warmup_divergences": rec["warmup_divergences"],
            "retained_reverse_coarser_rejections": rec["retained_reverse_coarser_rejections"],
            "retained_zero_density_evaluations": rec["retained_zero_density_evaluations"],
            "selected_refinement_level_histogram": rec["selected_refinement_level_histogram"],
            "retained_unrefined_leaf_fraction": rec["retained_unrefined_leaf_fraction"],
            "retained_max_abs_energy_error_quantiles": rec["retained_max_abs_energy_error_quantiles"],
            "retained_orbit_energy_range_quantiles": rec["retained_orbit_energy_range_quantiles"],
            "target_calls": rec["target_calls_counter"], "target_calls_retained": rec["target_calls_retained"],
            "wall_seconds": rec["wall_seconds"], "final_step_sizes": rec["final_step_sizes"], "final_max_error": rec["final_max_error"],
            "final_mass_diagonal_globals": rec["final_mass_diagonal_globals"],
            "paper_adaptation_updates": rec["paper_adaptation_updates"],
            "functionals": diag, "gates": gate_row(diag, health),
            "min_bulk_ess_per_work_unit": min(d["bulk_ess"] for d in diag.values()) / rec["target_calls_retained"],
            "work_unit": "retained fused target call",
        })
    by = {(r["fixture"], r["arm"]): r for r in results if r["status"] == "completed"}
    for r in results:
        if r["status"] == "completed":
            r["all_gates_passed"] = all(g["passed"] for g in r["gates"].values())
            r["agreements"] = {}
    for fixture in PROTOCOL["fixture_order"]:
        for a, b in AGREEMENTS:
            ra, rb = by.get((fixture, a)), by.get((fixture, b))
            if ra is None or rb is None:
                continue
            ra["agreements"][f"vs_{b}"] = agreement(ra["functionals"], rb["functionals"])
    # Efficiency ratios V3-A / V3-D and V3-D / V2-I (min bulk ESS per retained target call).
    ratios = {}
    for fixture in PROTOCOL["fixture_order"]:
        row = {}
        for a, b in [("V3-A", "V3-D"), ("V3-D", "V2-I"), ("V2-A", "V2-I")]:
            ra, rb = by.get((fixture, a)), by.get((fixture, b))
            if ra and rb:
                row[f"{a}/{b}"] = ra["min_bulk_ess_per_work_unit"] / rb["min_bulk_ess_per_work_unit"]
        ratios[fixture] = row
    summary = {"schema": "canonical-v3-scale-noncentered-v1/summary", "arviz": az.__version__, "numpy": np.__version__,
               "owalnuts_dir": str(args.owalnuts.relative_to(HERE)), "numpyro_dir": str(args.numpyro.relative_to(HERE)),
               "index": index, "efficiency_ratios_min_bulk_ess_per_call": ratios, "results": results}
    summary = sanitize(summary)
    (args.owalnuts / "summary.json").write_text(json.dumps(summary, indent=1, allow_nan=False), encoding="utf-8")
    lines = ["| fixture | arm | status | max R-hat | min bulk ESS | min tail ESS | div | exh | cap rate | median depth | work | wall s | min bulk ESS / work | sigma_x mean | max |z| (vs) | gates |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    for r in results:
        if r["status"] != "completed":
            lines.append(f"| {r['fixture']} | {r['arm']} | FAILED {r['error_kind']} | | | | | | | | {r.get('target_calls','')} | {r['wall_seconds']:.0f} | | | | fail |")
            continue
        g = r["gates"]
        work = r.get("target_calls_retained", r.get("retained_leapfrogs"))
        ag = r.get("agreements", {})
        agtxt = "; ".join(f"{v['max_abs_z']:.2f} ({k[3:]})" for k, v in ag.items())
        sx = r["functionals"].get("sigma_x", {}).get("mean", float("nan"))
        lines.append(
            f"| {r['fixture']} | {r['arm']} | ok | {g['max_rhat']['observed']:.4f} | {g['min_bulk_ess']['observed']:.0f} | "
            f"{g['min_tail_ess']['observed']:.0f} | {g['retained_divergences']['observed']} | {g['retained_refinement_exhaustions']['observed']} | "
            f"{g['max_depth_rate']['observed']:.4f} | {r['median_depth']} | {work:,} | {r['wall_seconds']:.0f} | "
            f"{r['min_bulk_ess_per_work_unit']:.2e} | {sx:.5f} | {agtxt} | {'PASS' if r['all_gates_passed'] else 'FAIL'} |")
    lines.append("")
    lines.append("Efficiency ratios (min bulk ESS per retained target call): " + json.dumps(ratios))
    (args.owalnuts / "results-table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
