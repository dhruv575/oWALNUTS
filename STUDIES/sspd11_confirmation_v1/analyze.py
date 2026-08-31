#!/usr/bin/env python3
"""Post-processing only for the WP12 confirmation study.

Primary: reads `primary/artifacts/primary-v1` (arms I and P, three seeds),
recomputes ArviZ rank-normalised diagnostics on the eight functionals,
evaluates WP4b's per-run gates, the P-vs-I (same seed) and P-vs-N (WP4b
NumPyro reference) agreement gates, the confirmation rule, and the P/I
ESS-per-call ratio.  Secondary: reads `stock_watson/artifacts/A{1,2,3}.json`
and applies WP10's Stock–Watson gates.  Writes `artifacts/summary.json` and
`artifacts/RESULTS.md`.  It never invokes a sampler.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import arviz as az
import numpy as np

HERE = Path(__file__).resolve().parent
PRIMARY = HERE / "primary"
PROTOCOL = json.loads((PRIMARY / "protocol.json").read_text(encoding="utf-8"))
FUNCTIONALS = PROTOCOL["functionals"]
GATES = PROTOCOL["gates"]
SW = HERE / "stock_watson"
SW_PROTOCOL = json.loads((SW / "protocol.json").read_text(encoding="utf-8"))
SW_GATES = SW_PROTOCOL["gates"]
REPO = HERE.parents[1]


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
    """draws: (chains, retained, k)."""
    out = {}
    for j, name in enumerate(names):
        x = draws[:, :, j]
        bulk = float(az.ess(x, method="bulk"))
        tail = float(az.ess(x, method="tail", prob=(0.05, 0.95)))
        rhat = float(az.rhat(x, method="rank"))
        sd = float(x.std(ddof=1))
        out[name] = {"rhat": rhat, "bulk_ess": bulk, "tail_ess": tail, "mean": float(x.mean()),
                     "sd": sd, "mcse": sd / math.sqrt(max(bulk, 1.0))}
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


def agreement(diag_a: dict, diag_b: dict, multiple: float) -> dict:
    rows, worst = {}, 0.0
    for name in FUNCTIONALS:
        a, b = diag_a[name], diag_b[name]
        combined = math.sqrt(a["mcse"] ** 2 + b["mcse"] ** 2)
        z = (a["mean"] - b["mean"]) / combined if combined > 0 else float("inf")
        rows[name] = {"mean_a": a["mean"], "mean_b": b["mean"], "combined_mcse": combined, "z": z}
        worst = max(worst, abs(z))
    return {"functionals": rows, "max_abs_z": worst, "passed": worst <= multiple}


def load_reference() -> dict:
    ref = PROTOCOL["reference"]
    json_path = REPO / ref["file"]
    npy_path = REPO / ref["functionals_npy"]
    assert sha256(json_path) == ref["sha256"], "reference JSON hash mismatch"
    assert sha256(npy_path) == ref["functionals_npy_sha256"], "reference .npy hash mismatch"
    rec = json.loads(json_path.read_text(encoding="utf-8"))
    draws = np.load(npy_path)
    return {"record": {k: v for k, v in rec.items() if k in ("seed", "settings", "software", "sampler")},
            "diag": diagnostics(draws, FUNCTIONALS), "json_sha256": ref["sha256"], "npy_sha256": ref["functionals_npy_sha256"]}


def primary() -> dict:
    run_dir = PRIMARY / "artifacts" / "primary-v1"
    index = json.loads((run_dir / "index.json").read_text(encoding="utf-8"))
    log = (run_dir.parent / "primary-v1-log.txt")
    reference = load_reference()
    runs = {}
    for stem in index["runs"]:
        rec = json.loads((run_dir / f"{stem}.json").read_text(encoding="utf-8"))
        if rec.get("status") == "failed":
            runs[stem] = {"status": "failed", "arm": rec["arm"], "seed": rec["seed"], "error_kind": rec["error_kind"],
                          "error": rec["error"], "wall_seconds": rec["wall_seconds"], "target_calls": rec["target_calls_counter"]}
            continue
        draws = np.fromfile(run_dir / rec["functionals_file"], dtype="<f8").reshape(
            rec["settings"]["chains"], rec["settings"]["retained"], len(FUNCTIONALS))
        diag = diagnostics(draws, FUNCTIONALS)
        health = {"divergences": rec["retained_divergences"], "invalid": rec["retained_invalid_evaluations"],
                  "exhausted": rec["retained_refinement_exhaustions"], "cap_rate": rec["max_depth_rate"]}
        gates = gate_row(diag, health)
        assert rec["preflight"]["callbacks_started"] == 0, f"{stem}: preflight started callbacks"
        assert rec["algorithm_revision"] == PROTOCOL["kernel"]["expected_algorithm_revision"], stem
        runs[stem] = {
            "status": "completed", "arm": rec["arm"], "seed": rec["seed"], "centeredness": rec["centeredness"],
            "algorithm_revision": rec["algorithm_revision"], "kernel_commit": rec["kernel_commit"],
            "preflight": rec["preflight"], "median_depth": rec["median_depth"], "depth_histogram": rec["depth_histogram"],
            "max_depth_rate": rec["max_depth_rate"], "stops": rec["stops"],
            "retained_reverse_coarser_rejections": rec["retained_reverse_coarser_rejections"],
            "selected_refinement_level_histogram": rec["selected_refinement_level_histogram"],
            "target_calls": rec["target_calls_counter"], "target_calls_retained": rec["target_calls_retained"],
            "wall_seconds": rec["wall_seconds"], "final_step_sizes": rec["final_step_sizes"],
            "functionals": diag, "gates": gates,
            "min_bulk_ess": min(d["bulk_ess"] for d in diag.values()),
            "min_bulk_ess_per_retained_call": min(d["bulk_ess"] for d in diag.values()) / rec["target_calls_retained"],
            "functionals_file_sha256": sha256(run_dir / rec["functionals_file"]),
            "extra": rec.get("extra", {}),
        }
        runs[stem]["all_run_gates_passed"] = all(g["passed"] for g in gates.values())
    seeds = PROTOCOL["seeds"]["sspd-11"]
    per_seed = []
    for seed in seeds:
        i_run = runs.get(f"sspd-11-I-{seed}")
        p_run = runs.get(f"sspd-11-P-{seed}")
        row = {"seed": seed}
        if p_run and p_run["status"] == "completed":
            if i_run and i_run["status"] == "completed":
                p_run["agreement_vs_I"] = agreement(p_run["functionals"], i_run["functionals"], GATES["agreement_P_vs_I_combined_mcse_multiple"])
                row["ess_per_call_ratio_P_over_I"] = p_run["min_bulk_ess_per_retained_call"] / i_run["min_bulk_ess_per_retained_call"]
            p_run["agreement_vs_N"] = agreement(p_run["functionals"], reference["diag"], GATES["agreement_P_vs_N_combined_mcse_multiple"])
            p_run["all_gates_passed"] = p_run["all_run_gates_passed"] and p_run.get("agreement_vs_I", {"passed": False})["passed"] and p_run["agreement_vs_N"]["passed"]
        if i_run and i_run["status"] == "completed":
            i_run["agreement_vs_N"] = agreement(i_run["functionals"], reference["diag"], GATES["agreement_P_vs_N_combined_mcse_multiple"])
            i_run["all_gates_passed"] = i_run["all_run_gates_passed"]
        row["I_passed"] = bool(i_run and i_run.get("all_gates_passed", False))
        row["P_passed"] = bool(p_run and p_run.get("all_gates_passed", False))
        per_seed.append(row)
    ratios = [r["ess_per_call_ratio_P_over_I"] for r in per_seed if "ess_per_call_ratio_P_over_I" in r]
    confirmation = {
        "I": {"passes": sum(r["I_passed"] for r in per_seed), "of": len(seeds), "confirmed": all(r["I_passed"] for r in per_seed)},
        "P": {"passes": sum(r["P_passed"] for r in per_seed), "of": len(seeds), "confirmed": all(r["P_passed"] for r in per_seed)},
        "ess_per_call_ratio_P_over_I": {"per_seed": ratios,
                                        "geometric_mean": float(np.exp(np.mean(np.log(ratios)))) if ratios else None,
                                        "min": min(ratios) if ratios else None, "max": max(ratios) if ratios else None},
    }
    preds = PROTOCOL["predictions"]
    verdicts = [
        {"prediction": preds[0], "held": confirmation["P"]["confirmed"]},
        {"prediction": preds[1], "held": confirmation["I"]["confirmed"]},
        {"prediction": preds[2], "held": bool(ratios) and confirmation["ess_per_call_ratio_P_over_I"]["geometric_mean"] >= 2.0},
        {"prediction": preds[3], "held": all(runs[f"sspd-11-P-{s}"].get("agreement_vs_I", {}).get("passed", False)
                                            and runs[f"sspd-11-P-{s}"].get("agreement_vs_N", {}).get("passed", False)
                                            for s in seeds if runs.get(f"sspd-11-P-{s}", {}).get("status") == "completed") and
                                        all(runs.get(f"sspd-11-P-{s}", {}).get("status") == "completed" for s in seeds)},
        {"prediction": preds[4], "held": all(runs.get(f"sspd-11-P-{s}", {}).get("median_depth") == 6 for s in seeds) and
                                        all(runs.get(f"sspd-11-I-{s}", {}).get("median_depth") == 8 and runs.get(f"sspd-11-I-{s}", {}).get("max_depth_rate", 1) <= 0.01 for s in seeds)},
    ]
    return {"index": index, "log_sha256": sha256(log) if log.exists() else None, "reference": reference,
            "runs": runs, "per_seed": per_seed, "confirmation": confirmation, "predictions": verdicts}


def stock_watson() -> dict:
    out = {}
    for name in SW_PROTOCOL["arms"]:
        path = SW / "artifacts" / f"{name}.json"
        if not path.is_file():
            out[name] = {"status": "missing"}
            continue
        a = json.loads(path.read_text(encoding="utf-8"))
        f = np.asarray(a["functionals"], dtype=np.float64)
        names = a["functional_names"]
        diag = diagnostics(f, names)
        ret = [c["retained"] for c in a["chains"]]
        health = {k: sum(c[k] for c in ret) for k in ("target_calls", "divergences", "invalid_evaluation_stops",
                                                        "refinement_exhaustion_stops", "maximum_depth_stops")}
        transitions = sum(sum(c["depth_histogram"]) for c in ret)
        health["retained_transitions"] = transitions
        health["maximum_depth_rate"] = health["maximum_depth_stops"] / max(transitions, 1)
        gates = {}
        for label in SW_GATES["functionals"]:
            gates[f"rhat_{label}"] = diag[label]["rhat"] <= SW_GATES["rhat_max"]
            gates[f"bulk_ess_{label}"] = diag[label]["bulk_ess"] >= SW_GATES["bulk_ess_min"]
            gates[f"tail_ess_{label}"] = diag[label]["tail_ess"] >= SW_GATES["tail_ess_min"]
        gates["divergences"] = health["divergences"] <= SW_GATES["retained_divergences_max"]
        gates["invalid_evaluations"] = health["invalid_evaluation_stops"] <= SW_GATES["retained_invalid_evaluations_max"]
        gates["refinement_exhaustions"] = health["refinement_exhaustion_stops"] <= SW_GATES["retained_refinement_exhaustions_max"]
        gates["maximum_depth_rate"] = health["maximum_depth_rate"] <= SW_GATES["maximum_depth_rate_max"]
        gated = [diag[l] for l in SW_GATES["functionals"]]
        out[name] = {
            "status": "completed", "base_seed": a["base_seed"], "algorithm_revision": a["algorithm_revision"],
            "wall_seconds": a["wall_seconds_including_discarded"], "functionals": diag, "health": health, "gates": gates,
            "all_gates_passed": all(gates.values()),
            "max_rhat_gated": max(x["rhat"] for x in gated), "min_bulk_ess_gated": min(x["bulk_ess"] for x in gated),
            "min_tail_ess_gated": min(x["tail_ess"] for x in gated),
            "max_rhat_all_reported": max(d["rhat"] for d in diag.values()),
            "final_tuning_per_chain": [c["final_tuning"] for c in a["chains"]],
            "bulk_ess_per_million_calls": min(x["bulk_ess"] for x in gated) / max(health["target_calls"], 1) * 1e6,
            "artifact_sha256": sha256(path),
        }
    done = [v for v in out.values() if v.get("status") == "completed"]
    return {"arms": out, "pass_rate": f"{sum(v['all_gates_passed'] for v in done)}/{len(done)}",
            "max_rhat_per_seed": {k: v["max_rhat_gated"] for k, v in out.items() if v.get("status") == "completed"}}


def table(summary: dict) -> str:
    lines = ["## Primary — sspd-11, kernel v10, seeds 91001–91003", "",
             "| seed | arm | max R-hat | min bulk ESS | min tail ESS | div/inv/exh | cap rate | median depth | retained calls | wall s | min bulk ESS/call | max |z| vs I | max |z| vs N | run gates | confirmed-run |",
             "|---:|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    for stem, r in summary["primary"]["runs"].items():
        if r["status"] != "completed":
            lines.append(f"| {r['seed']} | {r['arm']} | FAILED {r['error_kind']} | | | | | | {r['target_calls']:,} | {r['wall_seconds']:.0f} | | | | fail | no |")
            continue
        g = r["gates"]
        zi = r.get("agreement_vs_I", {}).get("max_abs_z")
        zn = r.get("agreement_vs_N", {}).get("max_abs_z")
        lines.append(
            f"| {r['seed']} | {r['arm']} | {g['max_rhat']['observed']:.4f} | {g['min_bulk_ess']['observed']:.0f} | {g['min_tail_ess']['observed']:.0f} | "
            f"{g['retained_divergences']['observed']}/{g['retained_invalid_evaluations']['observed']}/{g['retained_refinement_exhaustions']['observed']} | "
            f"{g['max_depth_rate']['observed']:.4f} | {r['median_depth']} | {r['target_calls_retained']:,} | {r['wall_seconds']:.0f} | "
            f"{r['min_bulk_ess_per_retained_call']:.2e} | {'' if zi is None else f'{zi:.2f}'} | {'' if zn is None else f'{zn:.2f}'} | "
            f"{'PASS' if r['all_run_gates_passed'] else 'FAIL'} | {'yes' if r.get('all_gates_passed') else 'no'} |")
    c = summary["primary"]["confirmation"]
    lines += ["", f"Confirmation: I {c['I']['passes']}/{c['I']['of']} → **{'confirmed' if c['I']['confirmed'] else 'not confirmed'}**; "
              f"P {c['P']['passes']}/{c['P']['of']} → **{'confirmed' if c['P']['confirmed'] else 'not confirmed'}**.",
              f"P/I min-bulk-ESS-per-retained-call ratio: per seed {[round(x, 3) for x in c['ess_per_call_ratio_P_over_I']['per_seed']]}, "
              f"geometric mean {c['ess_per_call_ratio_P_over_I']['geometric_mean']:.3f}, range [{c['ess_per_call_ratio_P_over_I']['min']:.3f}, {c['ess_per_call_ratio_P_over_I']['max']:.3f}]."
              if c["ess_per_call_ratio_P_over_I"]["per_seed"] else "P/I ratio unavailable.", "", "Predictions:"]
    for v in summary["primary"]["predictions"]:
        lines.append(f"- {v['prediction']} — **{'held' if v['held'] else 'failed'}**")
    sw = summary["stock_watson"]
    lines += ["", "## Secondary — Stock–Watson arm A (paper-mode v3, kernel v10), seeds 91011–91013", "",
              "| arm | seed | max R-hat (gated) | min bulk ESS | min tail ESS | div/inv/exh | cap rate | calls | wall s | final δ / h per chain | gates |",
              "|---|---:|---:|---:|---:|---|---:|---:|---:|---|---|"]
    for name, r in sw["arms"].items():
        if r.get("status") != "completed":
            lines.append(f"| {name} | | missing | | | | | | | | |")
            continue
        h = r["health"]
        tune = "; ".join(f"{t.get('max_error', float('nan')):.3f}/{t.get('step_size', float('nan')):.4f}" for t in r["final_tuning_per_chain"])
        lines.append(f"| {name} | {r['base_seed']} | {r['max_rhat_gated']:.4f} | {r['min_bulk_ess_gated']:.0f} | {r['min_tail_ess_gated']:.0f} | "
                     f"{h['divergences']}/{h['invalid_evaluation_stops']}/{h['refinement_exhaustion_stops']} | {h['maximum_depth_rate']:.4f} | "
                     f"{h['target_calls']:,} | {r['wall_seconds']:.0f} | {tune} | {'PASS' if r['all_gates_passed'] else 'FAIL'} |")
    lines.append(f"\nPass rate {sw['pass_rate']}; max gated R-hat per seed {json.dumps({k: round(v, 4) for k, v in sw['max_rhat_per_seed'].items()})}.")
    return "\n".join(lines) + "\n"


def main() -> int:
    summary = {"schema": "sspd11-confirmation-v1/summary", "arviz": az.__version__, "numpy": np.__version__,
               "protocol_sha256": sha256(PRIMARY / "protocol.json"), "sw_protocol_sha256": sha256(SW / "protocol.json"),
               "preregistration_sha256": sha256(HERE / "PREREGISTRATION.md"),
               "primary": primary(), "stock_watson": stock_watson()}
    summary = sanitize(summary)
    (HERE / "artifacts").mkdir(exist_ok=True)
    (HERE / "artifacts" / "summary.json").write_text(json.dumps(summary, indent=1, allow_nan=False), encoding="utf-8")
    md = table(summary)
    (HERE / "artifacts" / "RESULTS.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
