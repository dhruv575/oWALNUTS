#!/usr/bin/env python3
"""WP64: compare the Linux reproduction with the Windows record (E26 = WP56 v7, E28 = WP62 extension).

    python compare_windows.py     # writes artifacts/reproduction/{summary.json,reproduction-table.md}

Reads, never writes, the Windows artifacts in ../posteriordb_bench_v7/artifacts and
../posteriordb_bench_v7_seed_extension/artifacts. Run after `run_posteriordb.py analyze` and
`run_extension.py analyze`. Every statistic and prediction here is fixed in protocol.json.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
V7P = json.loads((HERE.parent / "posteriordb_bench_v7" / "protocol.json").read_text(encoding="utf-8"))
EXTP = json.loads((HERE.parent / "posteriordb_bench_v7_seed_extension" / "protocol.json").read_text(encoding="utf-8"))
WIN_V7 = HERE.parent / "posteriordb_bench_v7" / "artifacts"
WIN_EXT = HERE.parent / "posteriordb_bench_v7_seed_extension" / "artifacts"
LIN_V7 = HERE / "artifacts" / "v7"
LIN_EXT = HERE / "artifacts" / "ext"
OUT = HERE / "artifacts" / "reproduction"
HOUSE, NEW, FIXED16 = V7P["house_models"], V7P["new_models"], V7P["fixed_non_arma_models"]
DENSE = V7P["descriptive_dense_arm"]["models"]
REL = STUDY["analysis"]["bit_identity"]["relative_tolerance"]


def short(m: str) -> str:
    return m.replace("-", "__")


def load_cell(d: Path, m: str, arm: str, seed: int) -> dict | None:
    p = d / "cells" / f"{short(m)}-{arm}-{seed}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def close(a, b) -> bool:
    if a is None or b is None:
        return a is b
    if isinstance(a, (list, tuple)):
        return isinstance(b, (list, tuple)) and len(a) == len(b) and all(close(x, y) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if not (math.isfinite(a) and math.isfinite(b)):
            return (a == b) or (math.isnan(a) and math.isnan(b))
        return abs(a - b) <= REL * max(abs(a), abs(b), 1e-300)
    return a == b


def identity(lin: dict, win: dict, arm: str) -> dict:
    """Bit-identity indicators (protocol.json analysis.bit_identity)."""
    if lin.get("status") != "ok" or win.get("status") != "ok":
        return {"comparable": False}
    grads = lin.get("gradients_total") == win.get("gradients_total")
    if arm.startswith("owalnuts"):
        steps = close(lin.get("final_step_size"), win.get("final_step_size"))
        li, wi = lin.get("init") or {}, win.get("init") or {}
        starts = close(li.get("start_log_densities"), wi.get("start_log_densities")) and li.get("chosen") == wi.get("chosen")
    else:
        steps = close(lin.get("step_size"), win.get("step_size"))
        starts = None
    lp, wp = lin.get("parameters", {}), win.get("parameters", {})
    means = bool(lp) and set(lp) == set(wp) and all(close(lp[n]["mean"], wp[n]["mean"]) for n in lp)
    worst = max((abs(lp[n]["mean"] - wp[n]["mean"]) / max(wp[n]["sd"], 1e-300) for n in lp if n in wp), default=None)
    return {"comparable": True, "gradients_equal": grads, "step_sizes_equal": steps, "starts_equal": starts,
            "means_equal": means, "bit_identical": bool(grads and steps and means and starts is not False),
            "max_abs_dmean_over_sd_vs_windows": worst}


def wall_pg(c: dict | None) -> float | None:
    if not c or c.get("status") != "ok" or not c.get("gradients_total"):
        return None
    return 1e6 * c["wall_seconds"] / c["gradients_total"]


def geomean(xs: list[float]) -> float:
    xs = [x for x in xs if x is not None and math.isfinite(x) and x > 0]
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs))) if xs else float("nan")


def compare_block(lin_dir: Path, win_dir: Path, models: list[str], arms: list[str], seeds: list[int]) -> dict:
    rows = []
    for m in models:
        for arm in arms:
            for s in seeds:
                lc, wc = load_cell(lin_dir, m, arm, s), load_cell(win_dir, m, arm, s)
                if lc is None and wc is None:
                    continue
                row = {"model": m, "arm": arm, "seed": s,
                       "linux_status": lc and lc.get("status"), "windows_status": wc and wc.get("status"),
                       "linux_passed": bool(lc and lc.get("passed")), "windows_passed": bool(wc and wc.get("passed")),
                       "linux_wall_s": lc and lc.get("wall_seconds"), "windows_wall_s": wc and wc.get("wall_seconds"),
                       "linux_wall_per_gradient_us": wall_pg(lc), "windows_wall_per_gradient_us": wall_pg(wc),
                       "linux_min_bulk_ess_per_gradient": lc and lc.get("min_bulk_ess_per_gradient"),
                       "windows_min_bulk_ess_per_gradient": wc and wc.get("min_bulk_ess_per_gradient"),
                       "linux_execution": lc and lc.get("execution"), "windows_execution": wc and wc.get("execution")}
                row["same_pass"] = row["linux_passed"] == row["windows_passed"]
                row["identity"] = identity(lc, wc, arm) if lc and wc else {"comparable": False}
                rows.append(row)
    return {"rows": rows}


def per_arm(rows: list[dict], arms: list[str], models: list[str]) -> dict:
    out = {}
    for arm in arms:
        rs = [r for r in rows if r["arm"] == arm and r["model"] in models]
        comp = [r for r in rs if r["identity"].get("comparable")]
        # platform wall ratio: geomean over models of seed-median wall/gradient, Linux / Windows
        ratios = []
        for m in models:
            lv = [r["linux_wall_per_gradient_us"] for r in rs if r["model"] == m and r["linux_wall_per_gradient_us"]]
            wv = [r["windows_wall_per_gradient_us"] for r in rs if r["model"] == m and r["windows_wall_per_gradient_us"]]
            if lv and wv:
                ratios.append(statistics.median(lv) / statistics.median(wv))
        out[arm] = {"cells": len(rs), "linux_passed": sum(r["linux_passed"] for r in rs),
                    "windows_passed": sum(r["windows_passed"] for r in rs),
                    "same_pass_cells": sum(r["same_pass"] for r in rs),
                    "differing_cells": [f"{r['model']}/{r['seed']}: linux {r['linux_passed']} ({r['linux_status']}) "
                                        f"windows {r['windows_passed']} ({r['windows_status']})" for r in rs if not r["same_pass"]],
                    "comparable_cells": len(comp),
                    "bit_identical_cells": sum(1 for r in comp if r["identity"]["bit_identical"]),
                    "gradients_equal_cells": sum(1 for r in comp if r["identity"]["gradients_equal"]),
                    "starts_equal_cells": sum(1 for r in comp if r["identity"].get("starts_equal")),
                    "linux_over_windows_wall_per_gradient_geomean": geomean(ratios),
                    "wall_ratio_models": len(ratios)}
    return out


def funnel_compare() -> dict:
    out = {}
    for s in V7P["funnel"]["seeds"]:
        lp, wp = LIN_V7 / "funnel" / f"defaults-owalnuts-{s}.json", WIN_V7 / "funnel" / f"defaults-owalnuts-{s}.json"
        if not (lp.exists() and wp.exists()):
            out[str(s)] = {"present": False}
            continue
        lf, wf = json.loads(lp.read_text(encoding="utf-8")), json.loads(wp.read_text(encoding="utf-8"))
        out[str(s)] = {"present": True, "linux_z": lf["tail_mass"]["z"], "windows_z": wf["tail_mass"]["z"],
                       "linux_estimate": lf["tail_mass"]["estimate"], "windows_estimate": wf["tail_mass"]["estimate"],
                       "target_calls_equal": lf["target_calls_total"] == wf["target_calls_total"],
                       "bit_identical": lf["target_calls_total"] == wf["target_calls_total"]
                       and close(lf["tail_mass"]["estimate"], wf["tail_mass"]["estimate"]),
                       "linux_wall_s": lf["wall_seconds"], "windows_wall_s": wf["wall_seconds"]}
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    arms3 = ["owalnuts", "cmdstan", "nutpie"]
    v7 = compare_block(LIN_V7, WIN_V7, HOUSE + NEW, arms3, V7P["seeds"])
    dense = compare_block(LIN_V7, WIN_V7, DENSE, ["owalnuts-dense"], V7P["seeds"])
    ext = compare_block(LIN_EXT, WIN_EXT, EXTP["models"], ["owalnuts", "cmdstan"], EXTP["seeds"])
    blocks = {"v7_house": per_arm(v7["rows"], arms3, HOUSE), "v7_new": per_arm(v7["rows"], arms3, NEW),
              "v7_all": per_arm(v7["rows"], arms3, HOUSE + NEW), "ext": per_arm(ext["rows"], ["owalnuts", "cmdstan"], EXTP["models"]),
              "dense": per_arm(dense["rows"], ["owalnuts-dense"], DENSE)}
    fun = funnel_compare()
    lin_v7s = json.loads((LIN_V7 / "summary.json").read_text(encoding="utf-8")) if (LIN_V7 / "summary.json").exists() else {}
    lin_exs = json.loads((LIN_EXT / "summary.json").read_text(encoding="utf-8")) if (LIN_EXT / "summary.json").exists() else {}
    win_v7s = json.loads((WIN_V7 / "summary.json").read_text(encoding="utf-8"))
    win_exs = json.loads((WIN_EXT / "summary.json").read_text(encoding="utf-8"))

    pr = STUDY["predictions"]
    exp = pr["L1"]["expected"]
    o = {"house": blocks["v7_house"]["owalnuts"]["linux_passed"], "new": blocks["v7_new"]["owalnuts"]["linux_passed"],
         "ext": blocks["ext"]["owalnuts"]["linux_passed"]}
    complete = (blocks["v7_house"]["owalnuts"]["cells"] == 51 and blocks["v7_new"]["owalnuts"]["cells"] == 15
                and blocks["ext"]["owalnuts"]["cells"] == 48)
    tol = pr["L2"]["tolerance"]
    l2 = {}
    for key, (blk, arm) in {"cmdstan_house": ("v7_house", "cmdstan"), "cmdstan_new": ("v7_new", "cmdstan"),
                            "cmdstan_ext": ("ext", "cmdstan"), "nutpie_house": ("v7_house", "nutpie"),
                            "nutpie_new": ("v7_new", "nutpie")}.items():
        lv, wv = blocks[blk][arm]["linux_passed"], blocks[blk][arm]["windows_passed"]
        l2[key] = {"linux": lv, "windows": wv, "held": abs(lv - wv) <= tol}
    pooled = (lin_exs.get("pooled_six") or {}).get("geomean")
    lo, hi = pr["L3"]["interval"]
    p4 = (lin_v7s.get("predictions") or {}).get("P4_fixed16_wall_per_gradient_vs_cmdstan_le_1.0", {})
    l4_value = p4.get("value")
    ident = blocks["v7_all"]["owalnuts"]["bit_identical_cells"] + blocks["ext"]["owalnuts"]["bit_identical_cells"]
    comparable = blocks["v7_all"]["owalnuts"]["comparable_cells"] + blocks["ext"]["owalnuts"]["comparable_cells"]
    predictions = {
        "L1_owalnuts_pass_counts_reproduce_exactly": {
            "value": o, "expected": exp, "complete": complete,
            "held": (o == exp) if complete else None,
            "per_cell_same_pass": {"v7": blocks["v7_all"]["owalnuts"]["same_pass_cells"], "ext": blocks["ext"]["owalnuts"]["same_pass_cells"]}},
        "L2_competitor_pass_counts_within_tolerance": {"value": l2, "tolerance": tol, "held": all(v["held"] for v in l2.values())},
        "L3_linux_pooled_six_seed_fixed16_ess_per_gradient_in_interval": {
            "value": pooled, "models": len((lin_exs.get("pooled_six") or {}).get("models", [])), "interval": [lo, hi],
            "held": (lo <= pooled <= hi) if pooled is not None and math.isfinite(pooled) else None},
        "L4_linux_fixed16_wall_per_gradient_vs_cmdstan_le_1": {
            "value": l4_value, "models": p4.get("models"), "held": p4.get("held"),
            "value_over_complete_models_if_unevaluable": l4_value},
        "R1_bit_identity_reported": {"owalnuts_bit_identical_cells": ident, "owalnuts_comparable_cells": comparable,
                                     "funnel_bit_identical_seeds": sum(1 for v in fun.values() if v.get("bit_identical")),
                                     "expectation": pr["R1"]["expectation"]},
    }
    head_lin, head_win = lin_v7s.get("head_to_head", {}), win_v7s.get("head_to_head", {})
    heads = {k: {"linux": (head_lin.get(k) or {}).get("value"), "windows": v.get("value"),
                 "linux_models": len((head_lin.get(k) or {}).get("models", []) or []), "windows_models": len(v.get("models", []) or [])}
             for k, v in head_win.items()}
    ext_cmp = {k: {"linux": (lin_exs.get(k) or {}).get("geomean") if isinstance(lin_exs.get(k), dict) else lin_exs.get(k),
                   "windows": (win_exs.get(k) or {}).get("geomean") if isinstance(win_exs.get(k), dict) else win_exs.get(k)}
               for k in ("new_three", "v7_three_recomputed", "pooled_six", "seed_interval", "jackknife_se_pooled_geomean")}
    summary = {"schema": "posteriordb-bench-v7-linux-v1-reproduction", "ledger_id": STUDY["ledger_id"],
               "predictions": predictions, "blocks": blocks, "funnel": fun, "head_to_head_v7": heads,
               "extension_statistics": ext_cmp,
               "v7_predictions_linux": {k: v.get("held") for k, v in (lin_v7s.get("predictions") or {}).items()},
               "v7_predictions_windows": {k: v.get("held") for k, v in win_v7s["predictions"].items()},
               "v7_release_rule_linux": {"primary": lin_v7s.get("release_rule_primary_v6_verbatim"),
                                         "secondary": lin_v7s.get("release_rule_secondary_without_wall")},
               "ext_predictions_linux": {k: v.get("held") for k, v in (lin_exs.get("predictions") or {}).items()},
               "rows": {"v7": v7["rows"], "ext": ext["rows"], "dense": dense["rows"]},
               "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
               "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")

    def f(x, fmt=".3f"):
        return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)

    L = ["# WP64 Linux reproduction of E26 / E28 — comparison with the Windows record", "",
         "| block | arm | Linux passes | Windows passes | same pass/fail cells | bit-identical / comparable | Linux/Windows wall per gradient |",
         "|---|---|---:|---:|---:|---:|---:|"]
    for b, arms in blocks.items():
        for arm, e in arms.items():
            L.append(f"| {b} | {arm} | {e['linux_passed']}/{e['cells']} | {e['windows_passed']}/{e['cells']} | {e['same_pass_cells']} | "
                     f"{e['bit_identical_cells']}/{e['comparable_cells']} | {f(e['linux_over_windows_wall_per_gradient_geomean'])} |")
    L += ["", "## Differing cells", ""]
    for b, arms in blocks.items():
        for arm, e in arms.items():
            for d in e["differing_cells"]:
                L.append(f"- {b} {arm}: {d}")
    L += ["", "## Head-to-head (v7 statistics)", "", "| statistic | Linux | Windows |", "|---|---:|---:|"]
    for k, v in heads.items():
        L.append(f"| {k} | {f(v['linux'])} ({v['linux_models']}) | {f(v['windows'])} ({v['windows_models']}) |")
    L += ["", "## Extension statistics", "", "| statistic | Linux | Windows |", "|---|---|---|"]
    for k, v in ext_cmp.items():
        L.append(f"| {k} | {v['linux']} | {v['windows']} |")
    L += ["", "## Funnel", "", "| seed | Linux z | Windows z | bit-identical | Linux wall s | Windows wall s |", "|---|---:|---:|---|---:|---:|"]
    for s, v in fun.items():
        if v.get("present"):
            L.append(f"| {s} | {v['linux_z']:+.2f} | {v['windows_z']:+.2f} | {v['bit_identical']} | {v['linux_wall_s']:.2f} | {v['windows_wall_s']:.2f} |")
    L += ["", "## Preregistered predictions", "", "| prediction | value | held |", "|---|---|---|"]
    for k, v in predictions.items():
        L.append(f"| {k} | {v.get('value', {k2: v2 for k2, v2 in v.items() if k2 != 'expectation'})} | {v.get('held', 'reported')} |")
    (OUT / "reproduction-table.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
