#!/usr/bin/env python3
"""Analysis of nutpie_per_gradient_gap_v1 (WP58): the frozen statistics of protocol.json.

    python analyze_gap.py      # writes artifacts/summary.json and artifacts/results-table.md
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
ART = HERE / "artifacts"
CELLS = ART / "cells"
SEEDS = PROTOCOL["seeds"]
MODELS = PROTOCOL["models"]
PYMC = PROTOCOL["pymc_models"]
PDB2 = ["gp_pois_regr", "lotka_volterra"]


def load() -> dict:
    out: dict = {}
    for p in sorted(CELLS.glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        out.setdefault(r["model"], {}).setdefault(r["arm"], {})[int(r["seed"])] = r
    return out


def gm(xs) -> float:
    xs = [x for x in xs if x is not None and x > 0 and math.isfinite(x)]
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs))) if xs else float("nan")


def ok(cells: dict) -> list[dict]:
    return [c for c in cells.values() if c.get("status") == "ok"]


def arm_stats(cells: dict) -> dict:
    good = ok(cells)
    if not good:
        return {"cells_ok": 0, "cells": len(cells)}

    def med(k):
        v = [c[k] for c in good if c.get(k) is not None]
        return float(np.median(v)) if v else None

    acc = [c["acceptance_statistic"] for c in good if c.get("acceptance_statistic") is not None]
    return {
        "cells": len(cells), "cells_ok": len(good),
        "statuses": {s: [c["status"] for c in cells.values()].count(s) for s in {c["status"] for c in cells.values()}},
        "ess_per_gradient_gm": gm(c["ess_per_gradient"] for c in good),
        "ess_per_gradient_sampling_gm": gm(c["ess_per_gradient_sampling"] for c in good),
        "ess_per_gradient_by_seed": {str(c["seed"]): c["ess_per_gradient"] for c in good},
        "gates_passed": sum(bool(c["passed"]) for c in good),
        "min_bulk_ess_median": med("min_bulk_ess"),
        "min_tail_ess_median": med("min_tail_ess"),
        "max_rhat_max": max(c["max_rhat"] for c in good),
        "divergences_by_seed": [c["divergences"] for c in good],
        "gradients_total_median": med("gradients_total"),
        "gradients_warmup_median": med("gradients_warmup"),
        "gradients_sampling_median": med("gradients_sampling"),
        "gradients_start_selection_median": med("gradients_start_selection"),
        "warmup_fraction_median": float(np.median([c["gradients_warmup"] / c["gradients_total"] for c in good])),
        "step_size_mean": float(np.mean([np.mean(c["final_step_size"]) for c in good])),
        "mean_depth": float(np.mean([c["mean_depth"] for c in good])),
        "gradients_per_transition": float(np.mean([c["mean_gradients_per_transition"] for c in good])),
        "fraction_selected_refined": (float(np.mean([c["fraction_selected_refined"] for c in good]))
                                      if good[0].get("fraction_selected_refined") is not None else None),
        "reverse_call_fraction": (float(np.mean([c["retained_reverse_calls"] / c["gradients_sampling"] for c in good]))
                                  if good[0].get("retained_reverse_calls") is not None else None),
        "refinement_overhead_fraction": (
            float(np.mean([1 - c["retained_leaves_built"] / c["gradients_sampling"] for c in good]))
            if good[0].get("retained_leaves_built") is not None else None),
        "acceptance_statistic_mean": float(np.mean(acc)) if acc else None,
        "accounting_checks": [c.get("accounting_check") for c in good],
        "gradients_counted_callbacks": [c.get("gradients_counted_callbacks") for c in good],
    }


def main() -> None:
    data = load()
    stats = {m: {a: arm_stats(cells) for a, cells in arms.items()} for m, arms in data.items()}

    a1 = PROTOCOL.get("amendment_A1", {})

    def e(m, a, key="ess_per_gradient_gm"):
        # Amendment A1: on lotka_volterra the init="uniform" py-* arms stand in for the init=None ones.
        if m in a1.get("added_models", []) and f"{a}-uinit" in a1.get("added_arms", []):
            a = f"{a}-uinit"
        return stats.get(m, {}).get(a, {}).get(key, float("nan"))

    paths = {"python": "py-default", "rust": "rs-default"}
    gaps = {p: {m: math.log(e(m, "nutpie")) - math.log(e(m, d)) for m in MODELS} for p, d in paths.items()}
    gaps_s = {p: {m: math.log(e(m, "nutpie", "ess_per_gradient_sampling_gm"))
                  - math.log(e(m, d, "ess_per_gradient_sampling_gm")) for m in MODELS} for p, d in paths.items()}

    def frac(arm: str, path: str, models: list[str], numer=None) -> dict:
        d = paths[path]
        per = {}
        num = den = 0.0
        for m in models:
            if numer is None:
                n = math.log(e(m, arm)) - math.log(e(m, d))
            else:
                n = numer(m)
            g = gaps[path][m]
            per[m] = n / g if g else float("nan")
            num += n
            den += g
        return {"pooled": num / den if den else float("nan"), "per_model": per}

    fractions = {}
    for arm in ["py-delta2", "py-levels1", "py-nutpiemetric"]:
        fractions[arm] = {"pymc": frac(arm, "python", PYMC), "all": frac(arm, "python", MODELS)}
    for arm in ["rs-delta2", "rs-levels1", "rs-meanaccept", "rs-nutslike", "rs-nutpiemetric"]:
        fractions[arm] = {"pymc": frac(arm, "rust", PYMC), "all": frac(arm, "rust", MODELS)}
    for path in ("python", "rust"):
        fractions[f"nutpie-gradient-metric-share ({path})"] = {
            "pymc": frac("nutpie", path, PYMC, numer=lambda m: math.log(e(m, "nutpie")) - math.log(e(m, "nutpie-drawmetric"))),
            "all": frac("nutpie", path, MODELS, numer=lambda m: math.log(e(m, "nutpie")) - math.log(e(m, "nutpie-drawmetric"))),
        }

    # Accounting: counted callbacks instead of reported counts, both sides (Python path, PyMC models).
    acc = {}
    num = den = 0.0
    for m in PYMC:
        pyd = ok(data[m]["py-default"])
        own_factor = gm(c["gradients_counted_callbacks"] / c["gradients_total"] for c in pyd)
        npc = ok(data[m].get("nutpie-counted", {}))
        np_factor = gm(c["gradients_counted_callbacks"] / c["gradients_total"] for c in npc)
        reported = gaps["python"][m]
        verified = reported - math.log(np_factor) + math.log(own_factor)
        acc[m] = {"owalnuts_counted_over_reported": own_factor, "nutpie_counted_over_n_steps": np_factor,
                  "gap_reported": reported, "gap_verified": verified,
                  "share": abs(reported - verified) / reported}
        num += abs(reported - verified)
        den += reported
    acc_pooled = num / den
    # Start selection: Python 0 calls, Rust 64; its share of the Rust gap.
    start_share = {}
    for m in MODELS:
        rs = ok(data[m]["rs-default"])
        f = gm(c["gradients_total"] / (c["gradients_total"] - c["gradients_start_selection"]) for c in rs)
        start_share[m] = {"total_over_without_start": f, "share_of_rust_gap": math.log(f) / gaps["rust"][m]}

    # Predictions.
    p = {}
    p["P1"] = {"value": acc_pooled, "held": acc_pooled < 0.15}
    f_l = fractions["py-levels1"]["pymc"]["pooled"]
    f_d = fractions["py-delta2"]["pymc"]["pooled"]
    p["P2"] = {"value": f_l, "held": f_l >= 0.5}
    p["P3"] = {"value": {"py-delta2": f_d, "py-levels1": f_l}, "held": f_d < f_l}
    p4 = {f"{m} {path}": e(m, d) / e(m, "nutpie") for m in PDB2 for path, d in paths.items()}
    p["P4"] = {"value": p4, "held": all(v >= 0.9 for v in p4.values())}
    f_ma = fractions["rs-meanaccept"]["pymc"]["pooled"]
    f_nm = fractions["rs-nutpiemetric"]["pymc"]["pooled"]
    p["P5"] = {"value": {"rs-meanaccept": f_ma, "rs-nutpiemetric": f_nm}, "held": f_ma >= 0.5 and f_ma > f_nm}
    g_nm = {path: fractions[a]["pymc"]["per_model"]["gauss100"] for path, a in
            (("python", "py-nutpiemetric"), ("rust", "rs-nutpiemetric"))}
    h_nm = fractions["rs-nutpiemetric"]["pymc"]["per_model"]["hier"]
    h_ma = fractions["rs-meanaccept"]["pymc"]["per_model"]["hier"]
    p["P6"] = {"value": {"gauss100_nutpiemetric_f": g_nm, "hier_rs_nutpiemetric_f": h_nm, "hier_rs_meanaccept_f": h_ma},
               "held": all(abs(v) < 0.25 for v in g_nm.values()) and h_nm < h_ma}
    r7 = math.exp(gaps["rust"]["eight_nc"]) / math.exp(gaps["python"]["eight"])
    p["P7"] = {"value": {"eight_nc_rust_ratio": math.exp(gaps["rust"]["eight_nc"]),
                         "eight_python_ratio": math.exp(gaps["python"]["eight"]), "quotient": r7},
               "held": 0.8 <= r7 <= 1.25}
    r8 = {m: e(m, "rs-default") / e(m, "py-default") for m in PYMC}
    p["P8"] = {"value": r8, "held": all(0.8 <= v <= 1.25 for v in r8.values())}

    # Decision rule.
    rule = {}
    for arm in ("levels1", "delta2"):
        f = fractions[f"py-{arm}"]["pymc"]["pooled"]
        g_arm = sum(stats[m][f"rs-{arm}"]["gates_passed"] for m in PDB2)
        g_def = sum(stats[m]["rs-default"]["gates_passed"] for m in PDB2)
        rule[arm] = {"pooled_fraction_closed_pymc_python": f, "rust_gates_pdb2": g_arm, "rust_gates_pdb2_default": g_def,
                     "passes": f >= 0.5 and g_arm >= g_def and g_arm >= 5}
    decision = ("recommend a preregistered default-candidate study for "
                + ", ".join(a for a, r in rule.items() if r["passes"])) if any(
        r["passes"] for r in rule.values()) else "report the decomposition; documentation only"

    summary = {"study": PROTOCOL["study"], "ledger_id": PROTOCOL["ledger_id"], "per_model": stats,
               "gaps_ln": gaps, "gaps_ratio": {p_: {m: math.exp(g) for m, g in v.items()} for p_, v in gaps.items()},
               "gaps_sampling_only_ratio": {p_: {m: math.exp(g) for m, g in v.items()} for p_, v in gaps_s.items()},
               "fractions_closed": fractions, "accounting": {"per_model": acc, "pooled_share": acc_pooled},
               "start_selection": start_share, "predictions": p, "decision_rule": rule, "decision": decision,
               "cell_status": {s: sum(1 for m in data.values() for a in m.values() for c in a.values()
                                      if c.get("status") == s)
                               for s in {c.get("status") for m in data.values() for a in m.values() for c in a.values()}}}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, default=float), encoding="utf-8")
    write_table(summary)
    print(json.dumps({"predictions": {k: v["held"] for k, v in p.items()}, "decision": decision,
                      "accounting": acc_pooled}, indent=1))


def write_table(s: dict) -> None:
    L = ["# nutpie_per_gradient_gap_v1 (WP58) — results", "",
         "ESS/grad = geometric mean over 3 seeds of min bulk ESS / total gradients (x1e3); "
         "`samp` = the same per sampling gradient; gates = cells passing R-hat <= 1.01, bulk/tail ESS >= 400, "
         "no retained divergence; h = mean final step; depth = mean retained tree depth; "
         "grad/tr = gradients per retained transition; warm = median warmup share of gradients; "
         "refined = fraction of selected leaves above level 0; rev = reverse-check share of sampling gradients; "
         "acc = acceptance statistic (nutpie: mean_tree_accept; rs-*: the arm's own warmup statistic, last 100).", "",
         "| model | arm | ESS/grad | samp | vs nutpie | gates | min bulk ESS | max R-hat | div | h | depth | grad/tr | warm | refined | rev | acc |",
         "|---|---|---:|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|"]
    order = (PROTOCOL["python_nutpie_arms"] + PROTOCOL["python_owalnuts_arms"]
             + PROTOCOL.get("amendment_A1", {}).get("added_arms", []) + PROTOCOL["rust_arms"])
    for m in MODELS:
        ref = s["per_model"][m]["nutpie"]["ess_per_gradient_gm"]
        for a in order:
            st = s["per_model"][m].get(a)
            if not st:
                continue
            if not st.get("cells_ok"):
                L.append(f"| {m} | {a} | — | — | — | 0/{st['cells']} | | | | | | | | | | |")
                continue
            f = lambda v, fmt: "—" if v is None else format(v, fmt)  # noqa: E731
            L.append(
                f"| {m} | {a} | {1e3 * st['ess_per_gradient_gm']:.3f} | {1e3 * st['ess_per_gradient_sampling_gm']:.3f} | "
                f"{st['ess_per_gradient_gm'] / ref:.3f} | {st['gates_passed']}/{st['cells']} | {st['min_bulk_ess_median']:.0f} | "
                f"{st['max_rhat_max']:.4f} | {','.join(map(str, st['divergences_by_seed']))} | {st['step_size_mean']:.3g} | "
                f"{st['mean_depth']:.2f} | {st['gradients_per_transition']:.1f} | {st['warmup_fraction_median']:.2f} | "
                f"{f(st['fraction_selected_refined'], '.3f')} | {f(st['reverse_call_fraction'], '.3f')} | "
                f"{f(st['acceptance_statistic_mean'], '.3f')} |")
    L += ["", "## Gap (nutpie / default ESS per gradient) and fraction closed", "",
          "| model | gap python | gap rust | gap python, sampling only | gap rust, sampling only |",
          "|---|---:|---:|---:|---:|"]
    for m in MODELS:
        L.append(f"| {m} | {s['gaps_ratio']['python'][m]:.3f} | {s['gaps_ratio']['rust'][m]:.3f} | "
                 f"{s['gaps_sampling_only_ratio']['python'][m]:.3f} | {s['gaps_sampling_only_ratio']['rust'][m]:.3f} |")
    L += ["", "| arm | pooled f (PyMC) | " + " | ".join(MODELS) + " |", "|---|---:|" + "---:|" * len(MODELS)]
    for a, fr in s["fractions_closed"].items():
        per = fr["all"]["per_model"]
        L.append(f"| {a} | {fr['pymc']['pooled']:.3f} | " + " | ".join(f"{per[m]:.3f}" for m in MODELS) + " |")
    L += ["", "## Accounting", "",
          "| model | oWALNUTS counted / reported | nutpie counted / n_steps | gap reported | gap verified | share |",
          "|---|---:|---:|---:|---:|---:|"]
    for m, a in s["accounting"]["per_model"].items():
        L.append(f"| {m} | {a['owalnuts_counted_over_reported']:.5f} | {a['nutpie_counted_over_n_steps']:.5f} | "
                 f"{math.exp(a['gap_reported']):.4f} | {math.exp(a['gap_verified']):.4f} | {a['share']:.4f} |")
    L.append(f"\nPooled accounting share: {s['accounting']['pooled_share']:.4f}.\n")
    L += ["Start selection (Rust best-of-16): total / (total - start calls) and its share of the Rust gap:", "",
          "| model | factor | share |", "|---|---:|---:|"]
    for m, v in s["start_selection"].items():
        L.append(f"| {m} | {v['total_over_without_start']:.5f} | {v['share_of_rust_gap']:.4f} |")
    L += ["", "## Predictions", ""]
    for k, v in s["predictions"].items():
        L.append(f"* {k}: held = {v['held']}; value = {json.dumps(v['value'], default=float)}")
    L += ["", "## Decision rule", ""]
    for k, v in s["decision_rule"].items():
        L.append(f"* {k}: {json.dumps(v, default=float)}")
    L.append(f"\n**Decision: {s['decision']}.**")
    (ART / "results-table.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
