#!/usr/bin/env python3
"""Post-processing only (never invokes a sampler).

Reads every cell artifact under `artifacts/{state_space,numpyro,funnel}`,
recomputes ArviZ diagnostics from the exported draws through one code path for
both backends, applies the preregistered gates, computes the paired estimands
and prediction verdicts, and writes `artifacts/summary.json` and
`artifacts/RESULTS.md`.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import arviz as az
import numpy as np

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
SEEDS = PROTOCOL["seeds"]["evidence"]
SS_FUNCTIONALS = PROTOCOL["functionals"]["state_space"]
MT_FUNCTIONALS = PROTOCOL["functionals"]["matched_timing_subset"]
SS_GATES = PROTOCOL["gates"]["state_space"]
FN_GATES = PROTOCOL["gates"]["funnel"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gmean(values):
    values = [v for v in values if v is not None and v > 0]
    return math.exp(sum(math.log(v) for v in values) / len(values)) if values else None


def diagnostics(x: np.ndarray) -> dict:
    """x: (chains, draws)."""
    return {
        "rhat": float(az.rhat(x, method="rank")),
        "bulk_ess": float(az.ess(x, method="bulk")),
        "tail_ess": float(az.ess(x, method="tail", prob=(0.05, 0.95))),
        "mean": float(x.mean()),
        "sd": float(x.std(ddof=1)),
    }


# ----------------------------------------------------------------------------
# State-space cells (parts 1 and 2)
# ----------------------------------------------------------------------------

def load_owalnuts_ss(part_key: str, arm: str, seed: int):
    fixture = PROTOCOL["parts"][part_key]["fixture"]
    path = ART / "state_space" / f"{fixture}-{arm}-{seed}.json"
    if not path.is_file():
        return None
    cell = json.loads(path.read_text(encoding="utf-8"))
    if cell.get("status") == "failed":
        return {"cell": cell, "draws": None, "failed": True}
    s = cell["settings"]
    raw = np.fromfile(ART / "state_space" / cell["functionals_file"], dtype="<f8")
    draws = raw.reshape(s["chains"], s["retained"], len(SS_FUNCTIONALS))
    return {"cell": cell, "draws": draws, "failed": False}


def load_numpyro_ss(part_key: str, arm: str, seed: int):
    fixture = PROTOCOL["parts"][part_key]["fixture"]
    path = ART / "numpyro" / f"{fixture}-{arm}-{seed}.json"
    if not path.is_file():
        return None
    cell = json.loads(path.read_text(encoding="utf-8"))
    draws = np.load(ART / "numpyro" / cell["functionals_file"])
    return {"cell": cell, "draws": draws, "failed": False}


def ss_row(part_key: str, arm: str, seed: int, backend: str) -> dict | None:
    loaded = load_owalnuts_ss(part_key, arm, seed) if backend == "owalnuts" else load_numpyro_ss(part_key, arm, seed)
    if loaded is None:
        return None
    cell = loaded["cell"]
    row = {"part": part_key, "arm": arm, "backend": backend, "seed": seed}
    if loaded["failed"]:
        row.update({"status": "failed", "error": cell.get("error"), "gates_passed": False})
        return row
    d = {name: diagnostics(loaded["draws"][:, :, j]) for j, name in enumerate(SS_FUNCTIONALS)}
    row["functionals"] = d
    row["max_rhat"] = max(v["rhat"] for v in d.values())
    row["argmax_rhat"] = max(d, key=lambda k: d[k]["rhat"])
    row["min_bulk_ess"] = min(v["bulk_ess"] for v in d.values())
    row["min_tail_ess"] = min(v["tail_ess"] for v in d.values())
    if backend == "owalnuts":
        row.update({
            "divergences": cell["retained_divergences"],
            "invalid": cell["retained_invalid_evaluations"],
            "exhaustions": cell["retained_refinement_exhaustions"],
            "max_depth_rate": cell["max_depth_rate"],
            "median_depth": cell["median_depth"],
            "wall_total_sampling": cell["wall_seconds_total_sampler_call"],
            "work_total": cell["target_calls_telemetry_total"],
            "work_retained": cell["target_calls_retained"],
            "work_unit": "fused target calls",
            "final_step_sizes": cell["final_step_sizes"],
            "algorithm_revision": cell["algorithm_revision"],
            "kernel_commit": cell["kernel_commit"],
        })
    else:
        sp = cell["sampler"]
        row.update({
            "divergences": sp["divergences"], "invalid": 0, "exhaustions": 0,
            "max_depth_rate": sp["max_depth_rate"], "median_depth": sp["median_depth"],
            "wall_total_sampling": cell["timing_seconds"]["total_sampling"],
            "work_total": sp["retained_leapfrogs"] + sp["warmup_leapfrogs"],
            "work_retained": sp["retained_leapfrogs"],
            "work_unit": "leapfrog num_steps (proxy)",
            "final_step_sizes": sp["final_step_sizes"],
            "software": cell["software"],
        })
    g = SS_GATES
    gates = {
        "max_rhat": row["max_rhat"] <= g["max_rhat"],
        "min_bulk_ess": row["min_bulk_ess"] >= g["min_bulk_ess"],
        "min_tail_ess": row["min_tail_ess"] >= g["min_tail_ess"],
        "divergences": row["divergences"] <= g["retained_divergences"],
        "invalid": row["invalid"] <= g["retained_invalid_evaluations"],
        "exhaustions": row["exhaustions"] <= g["retained_refinement_exhaustions"],
        "max_depth_rate": row["max_depth_rate"] <= g["max_depth_rate"],
    }
    row["gates"] = gates
    row["gates_passed"] = all(gates.values())
    row["status"] = "pass" if row["gates_passed"] else "fail"
    # POST-HOC, labelled: the matched-timing-v1 gate used only the four
    # matched-timing functionals (mu, sigma_x, nu, x_initial) plus the health
    # gates. Reported so the v7 comparison is like-for-like; the preregistered
    # gate above (nine functionals) is the decision-bearing one.
    mt = {n: d[n] for n in MT_FUNCTIONALS}
    row["posthoc_matched_timing_v1_gate"] = {
        "max_rhat": max(v["rhat"] for v in mt.values()),
        "min_bulk_ess": min(v["bulk_ess"] for v in mt.values()),
        "min_tail_ess": min(v["tail_ess"] for v in mt.values()),
        "passed": (max(v["rhat"] for v in mt.values()) <= g["max_rhat"]
                   and min(v["bulk_ess"] for v in mt.values()) >= g["min_bulk_ess"]
                   and min(v["tail_ess"] for v in mt.values()) >= g["min_tail_ess"]
                   and gates["divergences"] and gates["invalid"] and gates["exhaustions"] and gates["max_depth_rate"]),
    }
    # per-functional efficiency
    row["bulk_ess_per_second"] = {n: d[n]["bulk_ess"] / row["wall_total_sampling"] for n in SS_FUNCTIONALS}
    row["tail_ess_per_second"] = {n: d[n]["tail_ess"] / row["wall_total_sampling"] for n in SS_FUNCTIONALS}
    row["bulk_ess_per_work_total"] = {n: d[n]["bulk_ess"] / row["work_total"] for n in SS_FUNCTIONALS}
    row["bulk_ess_per_work_retained"] = {n: d[n]["bulk_ess"] / row["work_retained"] for n in SS_FUNCTIONALS}
    row["tail_ess_per_work_total"] = {n: d[n]["tail_ess"] / row["work_total"] for n in SS_FUNCTIONALS}
    return row


def paired_ratio(rows, num_arm, den_arm, key, functionals, gate="gates_passed"):
    """Geometric-mean ratio over seeds and functionals; only seeds where both cells pass `gate`."""
    def passed(r):
        if gate == "gates_passed":
            return bool(r.get("gates_passed"))
        return bool(r.get("posthoc_matched_timing_v1_gate", {}).get("passed"))
    per_seed = {}
    for seed in SEEDS:
        a = next((r for r in rows if r["arm"] == num_arm and r["seed"] == seed), None)
        b = next((r for r in rows if r["arm"] == den_arm and r["seed"] == seed), None)
        if not a or not b or not passed(a) or not passed(b):
            per_seed[str(seed)] = None
            continue
        per_seed[str(seed)] = {n: a[key][n] / b[key][n] for n in functionals}
    eligible = [v for v in per_seed.values() if v]
    per_functional = {n: gmean([v[n] for v in eligible]) for n in functionals} if eligible else {}
    overall = gmean([v[n] for v in eligible for n in functionals]) if eligible else None
    return {"numerator": num_arm, "denominator": den_arm, "key": key, "functionals": functionals,
            "per_seed": per_seed, "per_functional_geomean": per_functional, "overall_geomean": overall,
            "eligible_seeds": sum(1 for v in per_seed.values() if v)}


def analyze_state_space(part_key: str) -> dict:
    part = PROTOCOL["parts"][part_key]
    rows = []
    for arm, spec in part["arms"].items():
        for seed in SEEDS:
            r = ss_row(part_key, arm, seed, spec["backend"])
            if r:
                rows.append(r)
    out = {"rows": rows}
    passes = {arm: sum(1 for r in rows if r["arm"] == arm and r.get("gates_passed")) for arm in part["arms"]}
    present = {arm: sum(1 for r in rows if r["arm"] == arm) for arm in part["arms"]}
    out["pass_counts"] = {arm: f"{passes[arm]}/{present[arm]}" for arm in part["arms"]}
    if part_key == "1_sspd05_timing":
        out["primary_TF_over_TN_bulk_ess_per_second"] = paired_ratio(rows, "T-F", "T-N", "bulk_ess_per_second", MT_FUNCTIONALS)
        out["secondary"] = {
            "TF_over_TN_tail_ess_per_second": paired_ratio(rows, "T-F", "T-N", "tail_ess_per_second", MT_FUNCTIONALS),
            "TF_over_TN_bulk_ess_per_work_total_LABELLED": paired_ratio(rows, "T-F", "T-N", "bulk_ess_per_work_total", MT_FUNCTIONALS),
            "TI_over_TN_bulk_ess_per_second": paired_ratio(rows, "T-I", "T-N", "bulk_ess_per_second", MT_FUNCTIONALS),
            "TP_over_TN_bulk_ess_per_second": paired_ratio(rows, "T-P", "T-N", "bulk_ess_per_second", MT_FUNCTIONALS),
            "TP_over_TI_bulk_ess_per_work_retained": paired_ratio(rows, "T-P", "T-I", "bulk_ess_per_work_retained", SS_FUNCTIONALS),
            "TP_over_TI_min_bulk_ess_per_retained_call_per_seed": {
                str(seed): (lambda a, b: (a["min_bulk_ess"] / a["work_retained"]) / (b["min_bulk_ess"] / b["work_retained"]) if a and b else None)(
                    next((r for r in rows if r["arm"] == "T-P" and r["seed"] == seed and r.get("gates") is not None), None),
                    next((r for r in rows if r["arm"] == "T-I" and r["seed"] == seed and r.get("gates") is not None), None))
                for seed in SEEDS},
        }
        out["posthoc_matched_timing_v1_gate"] = {
            "note": "POST-HOC, labelled: gate on the four matched-timing-v1 functionals only (as the v7 study did); not decision-bearing",
            "pass_counts": {arm: f"{sum(1 for r in rows if r['arm'] == arm and r.get('posthoc_matched_timing_v1_gate', {}).get('passed'))}/{present[arm]}" for arm in part["arms"]},
            "TF_over_TN_bulk_ess_per_second": paired_ratio(rows, "T-F", "T-N", "bulk_ess_per_second", MT_FUNCTIONALS, gate="posthoc"),
            "TF_over_TN_tail_ess_per_second": paired_ratio(rows, "T-F", "T-N", "tail_ess_per_second", MT_FUNCTIONALS, gate="posthoc"),
            "TI_over_TN_bulk_ess_per_second": paired_ratio(rows, "T-I", "T-N", "bulk_ess_per_second", MT_FUNCTIONALS, gate="posthoc"),
            "TP_over_TN_bulk_ess_per_second": paired_ratio(rows, "T-P", "T-N", "bulk_ess_per_second", MT_FUNCTIONALS, gate="posthoc"),
        }
        probe = ART / "numpyro" / "1_sspd05_timing-T-N-compile-probe.json"
        out["numpyro_compile_probe"] = json.loads(probe.read_text()) if probe.is_file() else None
        primary = out["primary_TF_over_TN_bulk_ess_per_second"]["overall_geomean"]
        tp_ti = out["secondary"]["TP_over_TI_min_bulk_ess_per_retained_call_per_seed"]
        out["predictions"] = {
            "P1_TF_over_TN_ge_3": {"observed": primary, "held": primary is not None and primary >= 3},
            "P2_TF_TI_TN_pass_3of3": {"observed": {a: out["pass_counts"][a] for a in ("T-F", "T-I", "T-N")},
                                       "held": all(passes[a] == 3 and present[a] == 3 for a in ("T-F", "T-I", "T-N"))},
            "P3_TP_over_TI_ge_2_every_seed": {"observed": tp_ti,
                                              "held": all(v is not None and v >= 2 for v in tp_ti.values())},
        }
    if part_key == "2_rm48":
        out["secondary"] = {
            "RB_over_RN_bulk_ess_per_second": paired_ratio(rows, "R-B", "R-N", "bulk_ess_per_second", SS_FUNCTIONALS),
            "RI_over_RN_bulk_ess_per_second": paired_ratio(rows, "R-I", "R-N", "bulk_ess_per_second", SS_FUNCTIONALS),
            "RB_over_RN_bulk_ess_per_work_total_LABELLED": paired_ratio(rows, "R-B", "R-N", "bulk_ess_per_work_total", SS_FUNCTIONALS),
            "RI_over_RN_bulk_ess_per_work_total_LABELLED": paired_ratio(rows, "R-I", "R-N", "bulk_ess_per_work_total", SS_FUNCTIONALS),
        }
        probe = ART / "numpyro" / "2_rm48-R-N-compile-probe.json"
        out["numpyro_compile_probe"] = json.loads(probe.read_text()) if probe.is_file() else None
        med = lambda arm: [r["median_depth"] for r in rows if r["arm"] == arm and r.get("median_depth") is not None]
        rb, ri = med("R-B"), med("R-I")
        out["predictions"] = {
            "P4_RB_RI_pass_3of3_cap_le_1pct": {"observed": {a: out["pass_counts"][a] for a in ("R-B", "R-I")},
                                               "cap_rates": {a: [r.get("max_depth_rate") for r in rows if r["arm"] == a] for a in ("R-B", "R-I")},
                                               "held": all(passes[a] == 3 and present[a] == 3 for a in ("R-B", "R-I"))},
            "P5_RN_pass_3of3": {"observed": out["pass_counts"]["R-N"], "held": passes["R-N"] == 3 and present["R-N"] == 3},
            "P6_RI_median_depth_le_RB": {"observed": {"R-I": ri, "R-B": rb},
                                          "held": bool(rb and ri) and all(i <= b for i, b in zip(ri, rb))},
        }
    return out


# ----------------------------------------------------------------------------
# Funnel cells (part 3)
# ----------------------------------------------------------------------------

def funnel_row(arm: str, seed: int, backend: str) -> dict | None:
    if backend == "owalnuts":
        path = ART / "funnel" / f"funnel-{arm}-{seed}.json"
        if not path.is_file():
            return None
        cell = json.loads(path.read_text(encoding="utf-8"))
        raw = np.fromfile(ART / "funnel" / cell["draws_file"], dtype="<f8")
        draws = raw.reshape(cell["chains"], cell["retained_per_chain"], 2)
    else:
        path = ART / "numpyro" / f"funnel-{arm}-{seed}.json"
        if not path.is_file():
            return None
        cell = json.loads(path.read_text(encoding="utf-8"))
        draws = np.load(ART / "numpyro" / cell["draws_file"])
    omega, x1 = draws[:, :, 0], draws[:, :, 1]
    d = {"omega": diagnostics(omega), "x_1": diagnostics(x1)}
    pooled = omega.reshape(-1)
    row = {"part": "3_funnel", "arm": arm, "backend": backend, "seed": seed,
           "chains": int(draws.shape[0]), "retained_per_chain": int(draws.shape[1]), "functionals": d,
           "omega_mean": float(pooled.mean()), "omega_variance": float(pooled.var(ddof=1)),
           "omega_q01": float(np.quantile(pooled, 0.01)), "omega_q005": float(np.quantile(pooled, 0.005))}
    tails = []
    for thr, exact, tol in zip(FN_GATES["tail_mass_thresholds"], FN_GATES["tail_mass_exact"], FN_GATES["tail_mass_abs_tolerance"]):
        p = float((pooled < thr).mean())
        se = math.sqrt(exact * (1 - exact) / max(d["omega"]["tail_ess"], 1))
        tails.append({"threshold": thr, "observed": p, "exact": exact, "tolerance": tol, "mc_se": se,
                      "z": (p - exact) / se, "within_tolerance": abs(p - exact) <= tol,
                      "under_covers": p < exact - tol, "per_chain": [float((c < thr).mean()) for c in omega]})
    row["tail_mass"] = tails
    if backend == "owalnuts":
        ret = [c["retained"] for c in cell["chains_detail"]]
        row.update({
            "divergences": sum(c["divergences"] for c in ret),
            "invalid": sum(c["invalid_evaluation_stops"] for c in ret),
            "exhaustions": sum(c["refinement_exhaustion_stops"] for c in ret),
            "max_depth_stops": sum(c["maximum_depth_stops"] for c in ret),
            "work_total": cell["target_callbacks_started"], "work_unit": "fused target calls",
            "work_retained": sum(c["target_calls"] for c in ret),
            "wall_total_sampling": cell["wall_seconds_total_sampler_call"],
            "final_step_sizes": [c["qualified_step_size"] for c in cell["chains_detail"]],
            "final_max_error": [c["final_max_error"] for c in cell["chains_detail"]],
            "algorithm_revision": cell["algorithm_revision"], "mode": cell["mode"],
        })
    else:
        sp = cell["sampler"]
        row.update({
            "divergences": sp["divergences"], "invalid": 0, "exhaustions": 0,
            "max_depth_stops": int(round(sp["max_depth_rate"] * draws.shape[0] * draws.shape[1])),
            "work_total": sp["retained_leapfrogs"] + sp["warmup_leapfrogs"], "work_unit": "leapfrog num_steps (proxy)",
            "work_retained": sp["retained_leapfrogs"],
            "wall_total_sampling": cell["timing_seconds"]["total_sampling"],
            "final_step_sizes": sp["final_step_sizes"], "software": cell["software"],
            "target_accept": cell["settings"]["target_accept"],
        })
    gates = {
        "max_rhat": max(v["rhat"] for v in d.values()) <= FN_GATES["max_rhat"],
        "min_bulk_ess": min(v["bulk_ess"] for v in d.values()) >= FN_GATES["min_bulk_ess"],
        "min_tail_ess": min(v["tail_ess"] for v in d.values()) >= FN_GATES["min_tail_ess"],
        "divergences": row["divergences"] <= FN_GATES["retained_divergences"],
        "invalid": row["invalid"] <= FN_GATES["retained_invalid_evaluations"],
        "exhaustions": row["exhaustions"] <= FN_GATES["retained_refinement_exhaustions"],
        "tail_mass_minus5": tails[0]["within_tolerance"],
        "tail_mass_minus6": tails[1]["within_tolerance"],
        "omega_variance": FN_GATES["omega_variance_interval"][0] <= row["omega_variance"] <= FN_GATES["omega_variance_interval"][1],
    }
    row["gates"] = gates
    row["gates_passed"] = all(gates.values())
    row["under_covers_neck"] = tails[0]["under_covers"]
    row["bulk_ess_omega_per_work_total"] = d["omega"]["bulk_ess"] / row["work_total"]
    row["bulk_ess_omega_per_second"] = d["omega"]["bulk_ess"] / row["wall_total_sampling"]
    return row


def analyze_funnel() -> dict:
    part = PROTOCOL["parts"]["3_funnel"]
    rows = []
    for arm, spec in part["arms"].items():
        for seed in SEEDS:
            r = funnel_row(arm, seed, spec["backend"])
            if r:
                rows.append(r)
    passes = {arm: sum(1 for r in rows if r["arm"] == arm and r["gates_passed"]) for arm in part["arms"]}
    present = {arm: sum(1 for r in rows if r["arm"] == arm) for arm in part["arms"]}
    under = {arm: sum(1 for r in rows if r["arm"] == arm and r["under_covers_neck"]) for arm in part["arms"]}
    div = {arm: sum(1 for r in rows if r["arm"] == arm and r["divergences"] > 0) for arm in part["arms"]}
    probes = {}
    for arm in ("FN-N80", "FN-N95"):
        p = ART / "numpyro" / f"3_funnel-{arm}-compile-probe.json"
        probes[arm] = json.loads(p.read_text()) if p.is_file() else None
    return {
        "rows": rows,
        "pass_counts": {a: f"{passes[a]}/{present[a]}" for a in part["arms"]},
        "under_coverage_counts": {a: f"{under[a]}/{present[a]}" for a in part["arms"]},
        "divergent_cell_counts": {a: f"{div[a]}/{present[a]}" for a in part["arms"]},
        "numpyro_compile_probes": probes,
        "predictions": {
            "P7_FNF_FNA_pass_3of3": {"observed": {a: f"{passes[a]}/{present[a]}" for a in ("FN-F", "FN-A")},
                                     "held": all(passes[a] == 3 and present[a] == 3 for a in ("FN-F", "FN-A"))},
            "P8_FNN80_undercovers_ge2_div_3of3": {"observed": {"under": under["FN-N80"], "div": div["FN-N80"], "n": present["FN-N80"]},
                                                  "held": present["FN-N80"] == 3 and under["FN-N80"] >= 2 and div["FN-N80"] == 3},
            "P9_FNN95_undercovers_ge2_div_ge2": {"observed": {"under": under["FN-N95"], "div": div["FN-N95"], "n": present["FN-N95"]},
                                                 "held": present["FN-N95"] == 3 and under["FN-N95"] >= 2 and div["FN-N95"] >= 2},
            "P10_no_numpyro_cell_passes": {"observed": {a: f"{passes[a]}/{present[a]}" for a in ("FN-N80", "FN-N95")},
                                           "held": present["FN-N80"] + present["FN-N95"] > 0 and passes["FN-N80"] + passes["FN-N95"] == 0},
        },
    }


# ----------------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------------

def f2(x, nd=2):
    return "—" if x is None else f"{x:.{nd}f}"


def results_md(summary: dict) -> str:
    L = []
    L.append("# Results — oWALNUTS v10 vs NumPyro NUTS (WP14)\n")
    L.append(f"Kernel `{summary['kernel']['algorithm_revision']}` at `{summary['kernel']['commit']}`; seeds {SEEDS}; "
             "diagnostics ArviZ rank R-hat / bulk / tail ESS from exported draws (same code path for both backends). "
             "`work` is fused target calls (oWALNUTS) or leapfrog `num_steps` (NumPyro) — different operations, labelled, never equated.\n")
    for part_key, title in (("1_sspd05_timing", "Part 1 — sspd-05 matched timing"), ("2_rm48", "Part 2 — real-market T=48")):
        p = summary[part_key]
        L.append(f"\n## {title}\n")
        L.append("| arm | seed | max R-hat (fn) | min bulk | min tail | div/inv/exh | cap | depth | work total | wall s | min bulk ESS/s | bulk ESS/work (×1e3) | gates |")
        L.append("|---|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---|")
        for r in p["rows"]:
            if r.get("status") == "failed":
                L.append(f"| {r['arm']} | {r['seed']} | FAILED: {r.get('error','')[:60]} | | | | | | | | | | FAIL |")
                continue
            L.append(f"| {r['arm']} ({r['backend']}) | {r['seed']} | {r['max_rhat']:.4f} ({r['argmax_rhat']}) | {r['min_bulk_ess']:.0f} | {r['min_tail_ess']:.0f} | "
                     f"{r['divergences']}/{r['invalid']}/{r['exhaustions']} | {100*r['max_depth_rate']:.2f}% | {r['median_depth']} | {r['work_total']:,} | "
                     f"{r['wall_total_sampling']:.1f} | {r['min_bulk_ess']/r['wall_total_sampling']:.0f} | {1e3*min(r['bulk_ess_per_work_total'].values()):.3f} | "
                     f"{'PASS' if r['gates_passed'] else 'FAIL'} |")
        L.append(f"\nPass counts: {p['pass_counts']}\n")
        if part_key == "1_sspd05_timing":
            pr = p["primary_TF_over_TN_bulk_ess_per_second"]
            L.append(f"**Primary** T-F / T-N bulk ESS per total sampling second (matched-timing functionals): per functional {{{', '.join(f'{k}: {f2(v)}' for k, v in pr['per_functional_geomean'].items())}}}, "
                     f"overall geometric mean **{f2(pr['overall_geomean'])}** ({pr['eligible_seeds']}/3 eligible seeds).\n")
            for k, v in p["secondary"].items():
                if isinstance(v, dict) and "overall_geomean" in v:
                    L.append(f"- {k}: overall {f2(v['overall_geomean'])} ({v['eligible_seeds']}/3 eligible)")
                else:
                    L.append(f"- {k}: {json.dumps({kk: (None if vv is None else round(vv, 3)) for kk, vv in v.items()})}")
            if p.get("numpyro_compile_probe"):
                c = p["numpyro_compile_probe"]
                L.append(f"- NumPyro compile probe (non-evidence): end-to-end {c['end_to_end_seconds_including_compile']:.1f} s, of which sampling {c['sampling_seconds']:.1f} s → implied compile {c['implied_compile_seconds']:.1f} s")
            ph = p["posthoc_matched_timing_v1_gate"]
            L.append("\n*Post-hoc, labelled — matched-timing-v1 four-functional gate (mu, sigma_x, nu, x_initial), as the v7 study gated:* pass counts " + str(ph['pass_counts']) + "; "
                     f"T-F/T-N bulk ESS/s {f2(ph['TF_over_TN_bulk_ess_per_second']['overall_geomean'])} ({ph['TF_over_TN_bulk_ess_per_second']['eligible_seeds']}/3 eligible), "
                     f"tail {f2(ph['TF_over_TN_tail_ess_per_second']['overall_geomean'])}; T-I/T-N {f2(ph['TI_over_TN_bulk_ess_per_second']['overall_geomean'])} ({ph['TI_over_TN_bulk_ess_per_second']['eligible_seeds']}/3); "
                     f"T-P/T-N {f2(ph['TP_over_TN_bulk_ess_per_second']['overall_geomean'])} ({ph['TP_over_TN_bulk_ess_per_second']['eligible_seeds']}/3). Per-seed table columns 'max R-hat / min ESS' above are the nine-functional preregistered gate.")
        else:
            for k, v in p["secondary"].items():
                L.append(f"- {k}: overall {f2(v['overall_geomean'])} ({v['eligible_seeds']}/3 eligible)")
            if p.get("numpyro_compile_probe"):
                c = p["numpyro_compile_probe"]
                L.append(f"- NumPyro compile probe (non-evidence): end-to-end {c['end_to_end_seconds_including_compile']:.1f} s, sampling {c['sampling_seconds']:.1f} s")
        L.append("\nPredictions:")
        for k, v in p["predictions"].items():
            L.append(f"- {k}: **{'held' if v['held'] else 'failed'}** — observed {json.dumps(v['observed'], default=lambda o: round(o, 3) if isinstance(o, float) else str(o))}")
    p = summary["3_funnel"]
    L.append("\n## Part 3 — Neal's funnel\n")
    L.append("| arm | seed | P(ω<−5) (exact .0478) | z | P(ω<−6) (exact .0228) | var ω (9) | q1% (−6.98) | div | inv/exh | depth-cap | R-hat ω | bulk/tail ESS ω | work total | wall s | under-covers | gates |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|---:|---:|---|---|")
    for r in p["rows"]:
        t5, t6 = r["tail_mass"]
        L.append(f"| {r['arm']} ({r['backend']}) | {r['seed']} | {t5['observed']:.4f} | {t5['z']:+.2f} | {t6['observed']:.4f} | {r['omega_variance']:.2f} | {r['omega_q01']:.2f} | "
                 f"{r['divergences']} | {r['invalid']}/{r['exhaustions']} | {r['max_depth_stops']} | {r['functionals']['omega']['rhat']:.4f} | "
                 f"{r['functionals']['omega']['bulk_ess']:.0f}/{r['functionals']['omega']['tail_ess']:.0f} | {r['work_total']:,} | {r['wall_total_sampling']:.1f} | "
                 f"{'yes' if r['under_covers_neck'] else 'no'} | {'PASS' if r['gates_passed'] else 'FAIL'} |")
    L.append(f"\nPass counts: {p['pass_counts']}; under-coverage counts: {p['under_coverage_counts']}; cells with divergences: {p['divergent_cell_counts']}\n")
    L.append("Predictions:")
    for k, v in p["predictions"].items():
        L.append(f"- {k}: **{'held' if v['held'] else 'failed'}** — observed {json.dumps(v['observed'])}")
    return "\n".join(L) + "\n"


def main() -> int:
    import subprocess
    commit = subprocess.run(["git", "-C", str(HERE.parents[1]), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    summary = {
        "schema": "numpyro-comparisons-v10/summary/v1",
        "protocol_sha256": sha256(HERE / "protocol.json"),
        "kernel": {"algorithm_revision": PROTOCOL["kernel"]["expected_algorithm_revision"], "commit": commit},
        "seeds": SEEDS,
        "1_sspd05_timing": analyze_state_space("1_sspd05_timing"),
        "2_rm48": analyze_state_space("2_rm48"),
        "3_funnel": analyze_funnel(),
    }

    def sanitize(o):
        if isinstance(o, dict):
            return {k: sanitize(v) for k, v in o.items()}
        if isinstance(o, list):
            return [sanitize(v) for v in o]
        if isinstance(o, float) and not math.isfinite(o):
            return None
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        if isinstance(o, np.bool_):
            return bool(o)
        return o

    summary = sanitize(summary)
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, allow_nan=False), encoding="utf-8")
    (ART / "RESULTS.md").write_text(results_md(summary), encoding="utf-8")
    print((ART / "RESULTS.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
