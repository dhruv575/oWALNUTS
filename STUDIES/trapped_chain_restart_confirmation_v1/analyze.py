#!/usr/bin/env python3
"""WP69 analysis: the frozen decision rule, predictions and tables
(`STUDIES/trapped_chain_restart_confirmation_v1`). Pair / fingerprint helpers copied from WP67's
analyze.py. Reads artifacts/cells/*.json only; writes artifacts/summary.json and
artifacts/results-table.md. Written with the preregistration, before the first evidence cell.
"""
from __future__ import annotations

import json
import math
import statistics

import run_study as rs

ART = rs.ART


def load() -> dict:
    out = {}
    for c in rs.manifest():
        p = rs.CELLS / f"{c['id']}.json"
        if p.exists():
            out[c["id"]] = json.loads(p.read_text(encoding="utf-8"))
    return out


def flags_of(c):
    if c is None:
        return None
    if c["arm"] == "restart":
        return sorted(c["restarted_chains"]) if c.get("restarted_chains") is not None else None
    em = c.get("detector_emulated_from_draw_run") or c.get("detector_emulated_epoch0")
    if em is None:
        return None
    return sorted(em["flagged"]) if em.get("scored") else []


def steps99(c):
    if c is None:
        return None
    if c["arm"] == "restart" and c.get("trapped_chain_checks"):
        return [recs[0]["step"] if recs else None for recs in c["trapped_chain_checks"]]
    if c["arm"] == "defaults" and c.get("per_chain_step_at_99") is not None:
        return c["per_chain_step_at_99"]
    em = c.get("detector_emulated_epoch0")
    return em["steps"] if em else None


def fingerprint(d, r) -> dict:
    out = {"evaluable": d is not None and r is not None}
    if not out["evaluable"]:
        return {**out, "holds": False, "why": "missing cell"}
    fd, fr = flags_of(d), flags_of(r)
    out["flags_defaults_emulated"], out["flags_restart"] = fd, fr
    out["flag_sets_equal"] = fd is not None and fr is not None and fd == fr
    sd, sr = steps99(d), steps99(r)
    out["steps_at_99_equal"] = sd is not None and sr is not None and len(sd) == len(sr) and all(
        a is not None and b is not None and a == b for a, b in zip(sd, sr))
    if not (d.get("completed") and r.get("completed")):
        out["identity"] = None
        out["holds"] = out["flag_sets_equal"] and out["steps_at_99_equal"]
        return out
    if not fr:
        out["identity"] = d["draw_hash"] == r["draw_hash"] and d["target_calls_total"] == r["target_calls_total"]
    else:
        keep = [i for i in range(len(d["per_chain_draw_hash"])) if i not in fr]
        out["identity"] = all(d["per_chain_draw_hash"][i] == r["per_chain_draw_hash"][i]
                              and d["per_chain_target_calls"][i] == r["per_chain_target_calls"][i] for i in keep)
    out["holds"] = bool(out["flag_sets_equal"] and out["steps_at_99_equal"] and out["identity"])
    return out


def trapped(c) -> list:
    return sorted((c or {}).get("trapped_chains") or [])


def geomean(xs):
    xs = [x for x in xs if x is not None and x > 0 and math.isfinite(x)]
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else float("nan")


def main() -> None:
    cells = load()
    man = rs.manifest()
    pairs = {}
    sync = []
    for c in man:
        if c["kind"] == "sync":
            sync.append(cells.get(c["id"]))
            continue
        if c["arm"] != "defaults":
            continue
        rid = c["id"].replace("--defaults--", "--restart--")
        pairs[c["id"]] = {**c, "d": cells.get(c["id"]), "r": cells.get(rid)}
    fps = {k: fingerprint(p["d"], p["r"]) for k, p in pairs.items()}
    sync_ok = [x for x in sync if x and x.get("status") == "ok"]
    F = all(f["holds"] for f in fps.values()) and len(sync_ok) == len(sync) and all(x["identical"] for x in sync_ok)

    # ---- arm A
    A = {"trapped_d": 0, "trapped_r": 0, "tp": 0, "fn": 0, "fp": 0, "tn": 0, "fn_not_reached": 0,
         "pass_d": 0, "pass_r": 0, "grads_d": 0, "grads_r": 0, "wall_d": 0.0, "wall_r": 0.0,
         "restarts": 0, "retrapped": 0, "cells": 0, "rows": []}
    for k, p in pairs.items():
        if p["block"] != "A":
            continue
        d, r = p["d"], p["r"]
        A["cells"] += 1
        td, tr, fd, fr = trapped(d), trapped(r), flags_of(d) or [], flags_of(r) or []
        A["trapped_d"] += len(td)
        A["trapped_r"] += len(tr)
        A["pass_d"] += int(bool(d and d.get("passed")))
        A["pass_r"] += int(bool(r and r.get("passed")))
        A["grads_d"] += (d or {}).get("target_calls_total") or 0
        A["grads_r"] += (r or {}).get("target_calls_total") or 0
        A["wall_d"] += (d or {}).get("wall_seconds_pinned_cotenanted") or 0.0
        A["wall_r"] += (r or {}).get("wall_seconds_pinned_cotenanted") or 0.0
        A["restarts"] += len(fr)
        A["retrapped"] += len(set(fr) & set(tr))
        s99 = steps99(d)
        for ch in range(4):
            reached = s99 is not None and ch < len(s99) and s99[ch] is not None
            it, ifl = ch in td, ch in fd
            key = "fn_not_reached" if (it and not reached) else "tp" if (it and ifl) else "fn" if it else "fp" if ifl else "tn"
            A[key] += 1
        if td or tr or fd or fr or not (d and d.get("passed")) or not (r and r.get("passed")):
            A["rows"].append({"seed": p["seed"], "trapped_d": td, "trapped_r": tr, "flags_d": fd, "restarted": fr,
                              "rhat_d": (d or {}).get("max_rank_rhat"), "rhat_r": (r or {}).get("max_rank_rhat"),
                              "passed_d": (d or {}).get("passed"), "passed_r": (r or {}).get("passed"),
                              "status_d": (d or {}).get("status"), "status_r": (r or {}).get("status"),
                              "grads_d": (d or {}).get("target_calls_total"), "grads_r": (r or {}).get("target_calls_total"),
                              "wall_d": (d or {}).get("wall_seconds_pinned_cotenanted"),
                              "wall_r": (r or {}).get("wall_seconds_pinned_cotenanted"),
                              "ratios_d": ((d or {}).get("detector_emulated_from_draw_run") or (d or {}).get("detector_emulated_epoch0") or {}).get("ratios"),
                              "fingerprint": fps[k]["holds"]})
    healthy_ratios = []
    for k, p in pairs.items():
        if p["block"] == "A" and p["d"]:
            em = p["d"].get("detector_emulated_from_draw_run") or p["d"].get("detector_emulated_epoch0") or {}
            for i, x in enumerate(em.get("ratios") or []):
                if i not in trapped(p["d"]):
                    healthy_ratios.append(x)
    A["min_healthy_ratio"] = min(healthy_ratios) if healthy_ratios else None
    clause_a = A["trapped_d"] >= 1 and A["trapped_r"] < A["trapped_d"] and A["fp"] == 0

    # ---- arm B
    B = {"pass_d": 0, "pass_r": 0, "firing_cells": [], "flagged_chains": 0, "fp_b": 0, "per_model": {}, "rows": []}
    per_model = {}
    for k, p in pairs.items():
        if p["block"] != "B":
            continue
        d, r = p["d"], p["r"]
        B["pass_d"] += int(bool(d and d.get("passed")))
        B["pass_r"] += int(bool(r and r.get("passed")))
        fr = flags_of(r) or []
        B["flagged_chains"] += len(fr)
        if fr:
            B["firing_cells"].append(k)
            if d and d.get("passed"):
                B["fp_b"] += len(fr)
        if d and r and d.get("completed") and r.get("completed"):
            per_model.setdefault(p["model"], []).append((d["min_bulk_ess_per_gradient"], r["min_bulk_ess_per_gradient"]))
        ratios = ((d or {}).get("detector_emulated_from_draw_run") or {}).get("ratios")
        B["rows"].append({"model": p["model"], "seed": p["seed"], "passed_d": (d or {}).get("passed"),
                          "passed_r": (r or {}).get("passed"), "status_d": (d or {}).get("status"),
                          "status_r": (r or {}).get("status"), "rhat_d": (d or {}).get("max_rank_rhat"),
                          "rhat_r": (r or {}).get("max_rank_rhat"), "restarted": fr,
                          "min_ratio": min(ratios) if ratios else None,
                          "trapped_d": trapped(d), "trapped_r": trapped(r),
                          "wall_d": (d or {}).get("wall_seconds_pinned_cotenanted"),
                          "wall_r": (r or {}).get("wall_seconds_pinned_cotenanted"),
                          "fingerprint": fps[k]["holds"]})
    for m, xs in per_model.items():
        B["per_model"][m] = geomean([b for _, b in xs]) / geomean([a for a, _ in xs])
    B["geomean_ratio"] = geomean(list(B["per_model"].values())) if len(B["per_model"]) == len(rs.HOUSE) else float("nan")
    unflagged_identical = all(fps[k]["holds"] for k, p in pairs.items() if p["block"] == "B")
    clause_b = (B["pass_r"] >= B["pass_d"] and math.isfinite(B["geomean_ratio"]) and B["geomean_ratio"] >= 0.99
                and unflagged_identical and B["fp_b"] == 0)
    # descriptive: wall ratio on non-firing breadth cells (sync cost + noise on real models)
    wr = [x["wall_r"] / x["wall_d"] for x in B["rows"] if not x["restarted"] and x["wall_d"] and x["wall_r"]]
    B["nonfiring_wall_ratio_median"] = statistics.median(wr) if wr else None

    # ---- arm C
    C = {"firings": 0, "rows": []}
    for k, p in pairs.items():
        if p["block"] not in ("C", "M"):
            continue
        d, r = p["d"], p["r"]
        fd, fr = flags_of(d) or [], flags_of(r) or []
        C["firings"] += int(bool(fd)) + int(bool(fr))
        row = {"block": p["block"], "seed": p["seed"], "targeted": p["targeted"], "flags_d": fd, "restarted": fr,
               "fingerprint": fps[k]["holds"]}
        for arm, c in (("d", d), ("r", r)):
            c = c or {}
            ratios = (c.get("detector_emulated_from_draw_run") or {}).get("ratios")
            if p["block"] == "C":
                second = trapped(c)
                row[arm] = {"status": c.get("status"), "second_mode_chains": second,
                            "shifts": c.get("per_chain_shift_ref_sd"), "rhat": c.get("max_rank_rhat"),
                            "passed": c.get("passed"), "warnings": c.get("chain_warnings"),
                            "warning_reports": bool(c.get("chain_warnings")), "min_ratio": min(ratios) if ratios else None}
            else:
                row[arm] = {"status": c.get("status"), "mixed": c.get("mixed_end_modes"),
                            "end_minor": c.get("chains_ending_minor"), "rhat": c.get("max_split_rhat"),
                            "warnings": c.get("chain_warning_chains"), "warning_reports": bool(c.get("chain_warnings")),
                            "min_ratio": min(ratios) if ratios else None}
        C["rows"].append(row)
    clause_c = C["firings"] == 0
    second_mode_cells = [(row, arm) for row in C["rows"] for arm in ("d", "r")
                         if (row["block"] == "C" and row[arm].get("second_mode_chains"))
                         or (row["block"] == "M" and row[arm].get("mixed"))]
    C["second_mode_cells"] = len(second_mode_cells)
    C["warning_reports_second_mode"] = sum(int(row[arm]["warning_reports"]) for row, arm in second_mode_cells)
    C["rhat_reports_second_mode"] = sum(int((row[arm].get("rhat") or 0) > 1.01) for row, arm in second_mode_cells)

    # ---- arm D
    D = {}
    for chains in (1, 4, 16):
        rs_ = [x["wall_ratio_restart_over_defaults"] for x in sync_ok if x["chains"] == chains]
        D[chains] = {"ratios": rs_, "median_ratio": statistics.median(rs_) if rs_ else None,
                     "overhead": statistics.median(rs_) - 1 if rs_ else None, "repeats": len(rs_)}
    clause_d = all(D[c]["overhead"] is not None and D[c]["overhead"] < 0.02 and D[c]["repeats"] == 5 for c in (4, 16))

    complete = len(cells) == len(man)
    if not complete:
        verdict = f"INCOMPLETE ({len(cells)}/{len(man)} cells): no verdict under the frozen rule"
    elif not F:
        verdict = "FAILED (implementation): fingerprint does not hold"
    elif clause_a and clause_b and clause_c and clause_d:
        verdict = "PROPOSE THE DEFAULT (would bump ALGORITHM_REVISION; v7-style validation needed after the flip)"
    else:
        verdict = "DO NOT PROPOSE the default"
    preds = {
        "P1": {"observed": f"defaults {A['trapped_d']}/240, restart {A['trapped_r']}/240",
               "held": 4 <= A["trapped_d"] <= 16 and A["trapped_r"] <= 1},
        "P2": {"observed": {k: A[k] for k in ("tp", "fn", "fp", "tn", "fn_not_reached")}, "held": A["fn"] == 0 and A["fp"] == 0},
        "P3": {"observed": f"firing {B['firing_cells']}; fp_b {B['fp_b']}; passes {B['pass_d']} vs {B['pass_r']}; ratio {B['geomean_ratio']:.4f}",
               "held": all("lotka" in k for k in B["firing_cells"]) and B["fp_b"] == 0 and B["pass_r"] >= B["pass_d"]
               and B["geomean_ratio"] >= 1.0},
        "P4": {"observed": f"firings {C['firings']}; second-mode cells {C['second_mode_cells']}, warning reports {C['warning_reports_second_mode']}, R-hat reports {C['rhat_reports_second_mode']}",
               "held": C["firings"] == 0 and C["warning_reports_second_mode"] == C["second_mode_cells"]},
        "P5": {"observed": {c: D[c]["overhead"] for c in D}, "held": clause_d},
        "P6": {"observed": f"{sum(f['holds'] for f in fps.values())}/{len(fps)} pairs; sync identical {sum(x['identical'] for x in sync_ok)}/{len(sync)}",
               "held": F},
    }
    summary = {"cells_written": len(cells), "cells_expected": len(man), "complete": complete,
               "clauses": {"a": clause_a, "b": clause_b, "c": clause_c, "d": clause_d, "fingerprint": F},
               "verdict": verdict, "A": A, "B": B, "C": C, "D": D, "predictions": preds}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n", encoding="utf-8")
    L = [f"# WP69 results ({len(cells)}/{len(man)} cells)", "", f"**Verdict:** {verdict}", "",
         "| clause | holds |", "|---|---|"] + [f"| {k} | {v} |" for k, v in summary["clauses"].items()]
    L += ["", "## Arm A (lotka, 60 fresh seeds x 4 chains)", "",
          f"Trapped chains: defaults {A['trapped_d']}/240, restart {A['trapped_r']}/240; detector TP {A['tp']} FN {A['fn']} "
          f"FP {A['fp']} TN {A['tn']} (not reached {A['fn_not_reached']}); min healthy ratio {A['min_healthy_ratio']}; "
          f"passes {A['pass_d']} vs {A['pass_r']} of 60; gradients {A['grads_d']} vs {A['grads_r']}; "
          f"wall {A['wall_d']:.1f} vs {A['wall_r']:.1f} s (pinned, co-tenanted); restarts {A['restarts']}, re-trapped {A['retrapped']}", "",
          "| seed | trapped d | flags d | restarted | trapped r | R-hat d | R-hat r | passed d/r | grads d | grads r | wall d | wall r | fingerprint |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    f = lambda x, s: "-" if x is None else format(x, s)  # noqa: E731
    for x in A["rows"]:
        L.append(f"| {x['seed']} | {x['trapped_d']} | {x['flags_d']} | {x['restarted']} | {x['trapped_r']} | {f(x['rhat_d'], '.3f')} | "
                 f"{f(x['rhat_r'], '.3f')} | {x['passed_d']}/{x['passed_r']} | {x['grads_d']} | {x['grads_r']} | {f(x['wall_d'], '.1f')} | "
                 f"{f(x['wall_r'], '.1f')} | {x['fingerprint']} |")
    L += ["", "## Arm B (17 house models x 3 seeds)", "",
          f"Passes {B['pass_d']} vs {B['pass_r']} of 51; flagged chains {B['flagged_chains']} in {len(B['firing_cells'])} cells "
          f"{B['firing_cells']}; false positives (flag on a cell passing at defaults) {B['fp_b']}; geomean ESS/gradient ratio "
          f"{B['geomean_ratio']:.4f}; median wall ratio on non-firing cells {f(B['nonfiring_wall_ratio_median'], '.4f')}", "",
          "| model | seed | passed d | passed r | R-hat d | R-hat r | min step ratio | restarted | shifted d | fingerprint |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for x in B["rows"]:
        L.append(f"| {x['model']} | {x['seed']} | {x['passed_d']} | {x['passed_r']} | {f(x['rhat_d'], '.4f')} | {f(x['rhat_r'], '.4f')} | "
                 f"{f(x['min_ratio'], '.3f')} | {x['restarted']} | {x['trapped_d']} | {x['fingerprint']} |")
    L += ["", "Per-model ESS/gradient ratio: " + ", ".join(f"{m.split('-')[-1]} {v:.4f}" for m, v in B["per_model"].items()),
          "", "## Arm C (genuine second modes)", "",
          f"Firings {C['firings']}; second-mode cells {C['second_mode_cells']}; chain-disagreement warning non-empty on "
          f"{C['warning_reports_second_mode']}; R-hat > 1.01 on {C['rhat_reports_second_mode']}", "",
          "| block | seed | targeted | arm | second-mode chains / mixed | R-hat | warning | min step ratio | restarted |",
          "|---|---|---|---|---|---|---|---|---|"]
    for x in C["rows"]:
        for arm in ("d", "r"):
            y = x[arm]
            sm = y.get("second_mode_chains") if x["block"] == "C" else f"mixed={y.get('mixed')} end_minor={y.get('end_minor')}"
            L.append(f"| {x['block']} | {x['seed']} | {x['targeted']} | {arm} | {sm} | {f(y.get('rhat'), '.3f')} | {y.get('warnings')} | "
                     f"{f(y.get('min_ratio'), '.3f')} | {x['restarted'] if arm == 'r' else x['flags_d']} |")
    L += ["", "## Arm D (sync point, 100-D Gaussian)", "", "| chains | repeat ratios | median | overhead |", "|---|---|---|---|"]
    for c, v in D.items():
        L.append(f"| {c} | {', '.join(f'{r:.4f}' for r in v['ratios'])} | {f(v['median_ratio'], '.4f')} | {f(v['overhead'], '+.4f')} |")
    L += ["", "## Predictions", "", "| id | observed | held |", "|---|---|---|"] + [
        f"| {k} | {v['observed']} | {v['held']} |" for k, v in preds.items()]
    (ART / "results-table.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:12]))


if __name__ == "__main__":
    main()
