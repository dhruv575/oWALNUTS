#!/usr/bin/env python3
"""Post-processing for the real-target path-metric study.

Reads the NumPyro reference results (`artifacts/numpyro`) and one oWALNUTS
run directory (`artifacts/owalnuts-v<k>`), computes ArviZ rank-normalised
diagnostics on the eight functionals, evaluates the preregistered gates
(including P-versus-N posterior agreement), and writes `summary.json` plus a
Markdown table into the oWALNUTS run directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import arviz as az
import numpy as np

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text())
FUNCTIONALS = PROTOCOL["functionals"]
GATES = PROTOCOL["gates"]


def sanitize(obj):
    """Replace non-finite floats with None so the summary stays JSON-compliant."""
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    if isinstance(obj, np.ndarray):
        return sanitize(obj.tolist())
    return obj


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def diagnostics(draws: np.ndarray) -> dict:
    """draws: (chains, retained, 8)."""
    out = {}
    for j, name in enumerate(FUNCTIONALS):
        x = draws[:, :, j]
        bulk = float(az.ess(x, method="bulk"))
        tail = float(az.ess(x, method="tail", prob=(0.05, 0.95)))
        rhat = float(az.rhat(x, method="rank"))
        sd = float(x.std(ddof=1))
        out[name] = {"rhat": rhat, "bulk_ess": bulk, "tail_ess": tail, "mean": float(x.mean()),
                     "sd": sd, "mcse": sd / np.sqrt(max(bulk, 1.0))}
    return out


def load_numpyro(dirpath: Path, fixture: str, a: float, seed: int) -> dict | None:
    stem = f"{fixture}-N-a{a:g}-{seed}"
    path = dirpath / f"{stem}.json"
    if not path.exists():
        return None
    rec = json.loads(path.read_text())
    draws = np.load(dirpath / rec["functionals_file"])
    rec["recomputed"] = diagnostics(draws)
    rec["draws"] = draws
    return rec


def gate_row(diag: dict, health: dict) -> dict:
    max_rhat = max(d["rhat"] for d in diag.values())
    min_bulk = min(d["bulk_ess"] for d in diag.values())
    min_tail = min(d["tail_ess"] for d in diag.values())
    gates = {
        "max_rhat": {"limit": GATES["max_rhat"], "observed": max_rhat, "passed": max_rhat <= GATES["max_rhat"]},
        "min_bulk_ess": {"limit": GATES["min_bulk_ess"], "observed": min_bulk, "passed": min_bulk >= GATES["min_bulk_ess"]},
        "min_tail_ess": {"limit": GATES["min_tail_ess"], "observed": min_tail, "passed": min_tail >= GATES["min_tail_ess"]},
        "retained_divergences": {"limit": 0, "observed": health["divergences"], "passed": health["divergences"] == 0},
        "retained_invalid_evaluations": {"limit": 0, "observed": health["invalid"], "passed": health["invalid"] == 0},
        "retained_refinement_exhaustions": {"limit": 0, "observed": health["exhausted"], "passed": health["exhausted"] == 0},
        "max_depth_rate": {"limit": GATES["max_depth_rate"], "observed": health["cap_rate"], "passed": health["cap_rate"] <= GATES["max_depth_rate"]},
    }
    return gates


def agreement(diag_a: dict, diag_b: dict) -> dict:
    rows = {}
    worst = 0.0
    for name in [n for n in FUNCTIONALS if n in diag_a and n in diag_b]:
        a, b = diag_a[name], diag_b[name]
        combined = np.sqrt(a["mcse"] ** 2 + b["mcse"] ** 2)
        z = (a["mean"] - b["mean"]) / combined if combined > 0 else float("inf")
        rows[name] = {"mean_a": a["mean"], "mean_b": b["mean"], "combined_mcse": float(combined), "z": float(z)}
        worst = max(worst, abs(float(z)))
    return {"functionals": rows, "max_abs_z": worst, "passed": worst <= GATES["agreement_P_vs_N_combined_mcse_multiple"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owalnuts", type=Path, default=HERE / "artifacts" / "owalnuts-v1")
    ap.add_argument("--numpyro", type=Path, default=HERE / "artifacts" / "numpyro")
    ap.add_argument("--posthoc", type=Path, default=None, help="optional post-hoc run directory merged into the table (labelled)")
    args = ap.parse_args(); args.owalnuts = args.owalnuts.resolve(); args.numpyro = args.numpyro.resolve()
    index = json.loads((args.owalnuts / "index.json").read_text())
    run_dirs = [(args.owalnuts, stem, False) for stem in index["runs"]]
    if args.posthoc is not None:
        args.posthoc = args.posthoc.resolve()
        ph = json.loads((args.posthoc / "index.json").read_text())
        run_dirs += [(args.posthoc, stem, True) for stem in ph["runs"]]
    results = []
    refs = {}
    for fixture in PROTOCOL["fixture_order"]:
        seed = PROTOCOL["seeds"][fixture]
        for a in (1.0, 0.75):
            ref = load_numpyro(args.numpyro, fixture, a, seed)
            if ref is None:
                continue
            refs[(fixture, a)] = ref
            health = {"divergences": ref["sampler"]["divergences"], "invalid": 0, "exhausted": 0,
                      "cap_rate": ref["sampler"]["max_depth_rate"]}
            results.append({
                "fixture": fixture, "arm": "N", "backend": "numpyro", "centeredness": a, "seed": seed,
                "status": "completed", "median_depth": ref["sampler"]["median_depth"],
                "depth_histogram": ref["sampler"]["depth_histogram"], "max_depth_rate": ref["sampler"]["max_depth_rate"],
                "retained_leapfrogs": ref["sampler"]["retained_leapfrogs"],
                "wall_seconds": ref["timing_seconds"]["end_to_end"], "sampling_seconds": ref["timing_seconds"]["sampling"],
                "final_step_sizes": ref["sampler"]["final_step_sizes"],
                "functionals": ref["recomputed"], "gates": gate_row(ref["recomputed"], health),
                "deviation": ref.get("deviation"),
            })
    for run_dir, stem, posthoc in run_dirs:
        rec = json.loads((run_dir / f"{stem}.json").read_text())
        fixture, arm = rec["fixture"], rec["arm"]
        if rec.get("status") == "failed":
            results.append({"fixture": fixture, "arm": arm, "backend": "owalnuts", "centeredness": rec.get("centeredness"),
                            "seed": rec["seed"], "status": "failed", "error_kind": rec["error_kind"], "error": rec["error"],
                            "wall_seconds": rec["wall_seconds"], "target_calls": rec["target_calls_counter"],
                            "algorithm_revision": rec["algorithm_revision"], "kernel_commit": rec["kernel_commit"]})
            continue
        draws = np.fromfile(run_dir / rec["functionals_file"], dtype="<f8").reshape(
            rec["settings"]["chains"], rec["settings"]["retained"], len(FUNCTIONALS))
        frozen = {name for j, name in enumerate(FUNCTIONALS)
                  if np.ptp(draws[:, :, j]) <= 1e-9 * (1.0 + abs(float(draws[0, 0, j])))}
        diag = diagnostics(draws)
        if frozen:
            diag = {k: d for k, d in diag.items() if k not in frozen}
        health = {"divergences": rec["retained_divergences"], "invalid": rec["retained_invalid_evaluations"],
                  "exhausted": rec["retained_refinement_exhaustions"], "cap_rate": rec["max_depth_rate"]}
        gates = gate_row(diag, health)
        row = {
            "fixture": fixture, "arm": arm, "backend": "owalnuts", "centeredness": rec["centeredness"], "seed": rec["seed"],
            "posthoc": posthoc, "arm_label": rec.get("arm_label"), "frozen_functionals": sorted(frozen),
            "status": "completed", "algorithm_revision": rec["algorithm_revision"], "kernel_commit": rec["kernel_commit"],
            "preflight": rec["preflight"], "median_depth": rec["median_depth"], "depth_histogram": rec["depth_histogram"],
            "max_depth_rate": rec["max_depth_rate"], "stops": rec["stops"],
            "retained_reverse_coarser_rejections": rec["retained_reverse_coarser_rejections"],
            "selected_refinement_level_histogram": rec["selected_refinement_level_histogram"],
            "target_calls": rec["target_calls_counter"], "target_calls_retained": rec["target_calls_retained"],
            "wall_seconds": rec["wall_seconds"], "final_step_sizes": rec["final_step_sizes"],
            "final_mass_diagonal_globals": rec["final_mass_diagonal_globals"],
            "functionals": diag, "gates": gates,
            "min_bulk_ess_per_retained_call": min(d["bulk_ess"] for d in diag.values()) / rec["target_calls_retained"],
            "extra": rec.get("extra", {}),
        }
        ref = refs.get((fixture, 1.0))
        if ref is not None:
            row["agreement_vs_N_a1"] = agreement(diag, {k: v for k, v in ref["recomputed"].items() if k in diag})
        results.append(row)
    for r in results:
        if r["status"] == "completed":
            r["all_gates_passed"] = all(g["passed"] for g in r["gates"].values())
    summary = {"schema": "real-target-path-metric-v1/summary", "arviz": az.__version__, "numpy": np.__version__,
               "owalnuts_dir": str(args.owalnuts.relative_to(HERE)), "numpyro_dir": str(args.numpyro.relative_to(HERE)),
               "index": {k: v for k, v in index.items()}, "results": results}
    summary = sanitize(summary)
    (args.owalnuts / "summary.json").write_text(json.dumps(summary, indent=1, allow_nan=False), encoding="utf-8")
    lines = ["| fixture | arm | a | status | max R-hat | min bulk ESS | min tail ESS | div | cap rate | median depth | calls / leapfrogs | wall s | max |z| vs N | gates |",
             "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for r in results:
        if r["status"] != "completed":
            lines.append(f"| {r['fixture']} | {r['arm']} | {r.get('centeredness')} | FAILED {r['error_kind']} | | | | | | | {r.get('target_calls','')} | {r['wall_seconds']:.0f} | | fail |")
            continue
        g = r["gates"]
        work = r.get("target_calls", r.get("retained_leapfrogs"))
        z = (r.get("agreement_vs_N_a1") or {}).get("max_abs_z")
        label = r['arm'] + (" (post-hoc)" if r.get("posthoc") else "")
        lines.append(
            f"| {r['fixture']} | {label} | {r['centeredness']:g} | ok | {g['max_rhat']['observed']:.4f} | "
            f"{g['min_bulk_ess']['observed']:.0f} | {g['min_tail_ess']['observed']:.0f} | {g['retained_divergences']['observed']} | "
            f"{g['max_depth_rate']['observed']:.4f} | {r['median_depth']} | {work:,} | {r['wall_seconds']:.0f} | "
            f"{'' if z is None else f'{z:.2f}'} | {'PASS' if r['all_gates_passed'] else 'FAIL'} |")
    (args.owalnuts / "results-table.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
