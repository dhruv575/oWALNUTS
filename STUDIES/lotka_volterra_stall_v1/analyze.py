#!/usr/bin/env python3
"""WP57 analysis: artifacts/summary.json and artifacts/results-table.md from artifacts/cells + telemetry.

Implements the frozen decision rule and predictions of protocol.json. Run via `run_study.py analyze`.
"""
from __future__ import annotations

import gzip
import json
import math
import statistics
from pathlib import Path

import numpy as np

import run_study as rs

ART = rs.ART
P = rs.PROTOCOL
MIT = ["best_of_64", "depth6_initial"]
SEEDS = P["blocks"][0]["seeds"]
S12 = ["S1", "S2"]


def med(xs):
    xs = [x for x in xs if x is not None and math.isfinite(x)]
    return statistics.median(xs) if xs else None


def load():
    rec = {}
    for cell in rs.manifest():
        p = rs.CELLS / f"{cell['id']}.json"
        if p.exists():
            rec[cell["id"]] = json.loads(p.read_text(encoding="utf-8"))
    return rec


def telemetry(cid):
    p = rs.TELEM / f"{cid}.json.gz"
    if not p.exists():
        return None
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def init_max_depth(cid):
    t = telemetry(cid)
    if t is None:
        return None
    ix = t["telemetry_fields"].index("depth")
    out = []
    for rows in t["telemetry"]:
        r = np.asarray(rows, dtype=float).reshape(-1, len(t["telemetry_fields"]))
        r = r[r[:, 0] < 75]
        out.append(int(r[:, ix].max()) if len(r) else None)
    return out


def chain_grads(c):
    return [ch["gradients_total"] for ch in c["profile"]["chains"]]


def stalled_chains(c):
    chains = c["profile"]["chains"]
    if not c["stalled"]:
        return []
    if c["status"] != "ok":
        return [ch["chain"] for ch in chains if not ch["finished"]]
    g = chain_grads(c)
    m = statistics.median(g)
    return [i for i, x in enumerate(g) if x > 3 * m]


def slow_chains(c):
    g = chain_grads(c)
    m = statistics.median(g)
    return [i for i, x in enumerate(g) if x > 3 * m]


def window_pool(ch, names):
    """Pooled stats over windows `names` for one chain."""
    ws = [ch["windows"][n] for n in names if ch["windows"][n].get("transitions")]
    n = sum(w["transitions"] for w in ws)
    if not n:
        return {"transitions": 0}
    caps = sum(w["depth_cap_stops"] for w in ws)
    return {"transitions": n, "gradients": sum(w["gradients"] for w in ws),
            "depth_cap_fraction": caps / n,
            "step_median_of_window_medians": med([w["step_median"] for w in ws]),
            "step_min": min(w["step_min"] for w in ws)}


def describe_chain(c, i, healthy_wall):
    ch = c["profile"]["chains"][i]
    others = [o for j, o in enumerate(c["profile"]["chains"]) if j != i and o["eval_us_per_gradient"]]
    other_wall = med([o["eval_us_per_gradient"] for o in others])
    share = ch["gradient_share"]
    top = max(share, key=share.get)
    tw = ch["windows"][top]
    s12 = window_pool(ch, S12)
    return {
        "cell": c["id"], "arm": c["arm"], "seed": c["seed"], "chain": i, "status": c["status"],
        "start_log_density": ch["start_log_density"],
        "other_start_log_densities": [o["start_log_density"] for j, o in enumerate(c["profile"]["chains"]) if j != i],
        "gradients_total": ch["gradients_total"], "median_other_chain_gradients": med(
            [o["gradients_total"] for j, o in enumerate(c["profile"]["chains"]) if j != i]),
        "transitions_done": ch["transitions_done"], "next_window": ch["next_window"],
        "pending_calls": ch["pending_calls"],
        "gradient_share": {k: round(v, 4) for k, v in share.items()},
        "share_S1_S2": share["S1"] + share["S2"],
        "S1_S2": s12,
        "top_window": top, "top_window_share": share[top],
        "top_window_stats": {k: tw.get(k) for k in ("transitions", "complete", "gradients", "step_median", "step_min",
                                                   "depth_median", "depth_cap_fraction", "stop_counts",
                                                   "gradients_per_transition", "refinement_attempts_per_leaf",
                                                   "gradients_per_leaf", "selected_level_mean",
                                                   "selected_level_none_fraction", "divergent", "zero_density",
                                                   "log_density_median", "eval_us_per_gradient")},
        "eval_us_per_gradient": ch["eval_us_per_gradient"],
        "ratio_to_healthy_pool": (ch["eval_us_per_gradient"] / healthy_wall) if (healthy_wall and ch["eval_us_per_gradient"]) else None,
        "ratio_to_same_cell_others": (ch["eval_us_per_gradient"] / other_wall) if (other_wall and ch["eval_us_per_gradient"]) else None,
    }


def early(c, i):
    em = c["wp44_emulated_by_window"]
    wall = c["wall_seconds_contended"]
    res = {"by_rule": {}, "lag": None}
    for w in S12:
        e = em.get(w, {})
        if e.get("scored") and str(i) in e.get("flags", {}):
            res["by_rule"][w] = {"rules": e["flags"][str(i)], "known_at_seconds": e["known_at_seconds"],
                                 "fraction_of_wall": e["known_at_seconds"] / wall}
    # lag: the other chains finished S2 while chain i had not
    chains = c["profile"]["chains"]
    others = [o for j, o in enumerate(chains) if j != i]
    s2_done = [o["windows"]["S2"].get("t_end_seconds") for o in others if o["windows"]["S2"].get("complete")]
    me = chains[i]["windows"]["S2"]
    if len(s2_done) == len(others):
        known = max(s2_done)
        my_end = me.get("t_end_seconds") if me.get("complete") else None
        lagging = my_end is None or my_end > known
        res["lag"] = {"others_finished_S2_at_seconds": known, "chain_finished_S2_at_seconds": my_end,
                      "lagging": lagging, "fraction_of_wall": known / wall}
    cands = [v["fraction_of_wall"] for v in res["by_rule"].values()]
    if res["lag"] and res["lag"]["lagging"]:
        cands.append(res["lag"]["fraction_of_wall"])
    res["identified"] = bool(cands)
    res["earliest_fraction_of_wall"] = min(cands) if cands else None
    res["early_before_25pct"] = bool(cands) and min(cands) < 0.25
    return res


def main():
    rec = load()
    missing = [c["id"] for c in rs.manifest() if c["id"] not in rec]
    by = {(c["arm"], c["seed"]): c for c in rec.values()}
    arms = [b["arm"] for b in P["blocks"]]

    def arm_cells(arm):
        return [c for c in rec.values() if c["arm"] == arm]

    # healthy pool (defaults, non-stalled cells, non-slow chains)
    healthy = []
    for c in arm_cells("defaults"):
        if c["stalled"] or c["status"] != "ok":
            continue
        slow = slow_chains(c)
        healthy += [ch["eval_us_per_gradient"] for ch in c["profile"]["chains"] if ch["chain"] not in slow]
    healthy_wall = med(healthy)

    per_arm = {}
    for arm in arms:
        cs = sorted(arm_cells(arm), key=lambda c: c["seed"])
        per_arm[arm] = {
            "cells": len(cs), "stalled": sum(c["stalled"] for c in cs),
            "stalled_seeds": [c["seed"] for c in cs if c["stalled"]],
            "timeouts": [c["seed"] for c in cs if c["status"] == "timeout"],
            "completed": sum(c["status"] == "ok" for c in cs),
            "passed_gates": sum(bool(c.get("passed")) for c in cs),
            "gradients_total_incl_unfinished": sum(sum(chain_grads(c)) for c in cs),
            "slow_chain_cells": {str(c["seed"]): slow_chains(c) for c in cs if c["status"] == "ok" and slow_chains(c)},
            "max_abs_z_max": max([c["max_abs_z"] for c in cs if c["status"] == "ok"], default=None),
            "wall_seconds_median_contended": med([c["wall_seconds_contended"] for c in cs]),
        }

    # characterisation of stalled and slow chains
    stalled_desc, slow_desc = [], []
    for c in sorted(rec.values(), key=lambda c: c["ordinal"]):
        for i in stalled_chains(c):
            d = describe_chain(c, i, healthy_wall)
            d["early"] = early(c, i)
            d["chain_warnings_named"] = (i in c.get("chain_warning_chains", [])) if c["status"] == "ok" else None
            stalled_desc.append(d)
        if c["status"] == "ok" and not c["stalled"]:
            for i in slow_chains(c):
                d = describe_chain(c, i, healthy_wall)
                d["early"] = early(c, i)
                d["chain_warnings_named"] = i in c.get("chain_warning_chains", [])
                slow_desc.append(d)

    # decision rule
    defaults_init_depth = {s: init_max_depth(by[("defaults", s)]["id"]) for s in SEEDS if ("defaults", s) in by}
    decision = {}
    for arm in MIT:
        rows = []
        r3 = True
        for s in SEEDS:
            d, m = by.get(("defaults", s)), by.get((arm, s))
            if d is None or m is None:
                r3 = False
                continue
            row = {"seed": s, "defaults_stalled": d["stalled"], "arm_stalled": m["stalled"]}
            if not d["stalled"]:
                if arm == "best_of_64":
                    possible = m["starts_hash"] == d["starts_hash"]
                else:
                    depths = defaults_init_depth.get(s) or []
                    possible = bool(depths) and all(x is not None and x <= 6 for x in depths)
                row["identity_possible_by_construction"] = possible
                identical = m["status"] == "ok" and d["status"] == "ok" and m.get("draw_hash") == d.get("draw_hash")
                row["bit_identical"] = identical
                if possible:
                    ok = identical
                else:
                    ok = m["status"] == "ok" and m["max_abs_z"] <= 3.0
                row["max_abs_z"] = m.get("max_abs_z")
                row["r3_ok"] = ok
                r3 = r3 and ok
            rows.append(row)
        r1 = per_arm[arm]["stalled"] == 0 and per_arm[arm]["cells"] == 12
        r2 = per_arm[arm]["passed_gates"] >= per_arm["defaults"]["passed_gates"]
        decision[arm] = {"R1_zero_stalls": r1, "R2_gates_ge_defaults": r2, "R3_identity_or_z": r3,
                         "recommend": bool(r1 and r2 and r3 and not missing), "seeds": rows,
                         "bit_identical_seeds": sum(bool(r.get("bit_identical")) for r in rows)}
    passing = [a for a in MIT if decision[a]["recommend"]]
    if len(passing) == 2:
        a, b = passing
        ka = (decision[a]["bit_identical_seeds"], -per_arm[a]["gradients_total_incl_unfinished"])
        kb = (decision[b]["bit_identical_seeds"], -per_arm[b]["gradients_total_incl_unfinished"])
        passing = [a if ka >= kb else b]
    decision["recommended"] = passing[0] if passing else None
    decision["defaults_never_stalled"] = per_arm["defaults"]["stalled"] == 0

    # predictions
    st_def = [d for d in stalled_desc if d["arm"] in ("defaults", "uniform")]
    all_st = stalled_desc
    preds = {
        "P1_defaults_le_2_of_12_stall": per_arm["defaults"]["stalled"] <= 2,
        "P1_value": per_arm["defaults"]["stalled"],
        "P2_stalled_chains_S1S2_gt70pct_cap_gt50pct_step_lt1e-3": (all(
            d["share_S1_S2"] > 0.7 and d["S1_S2"].get("depth_cap_fraction", 0) > 0.5
            and (d["S1_S2"].get("step_median_of_window_medians") or 1) < 1e-3 for d in all_st) if all_st else None),
        "P2_values": [{"cell": d["cell"], "chain": d["chain"], "share_S1_S2": d["share_S1_S2"],
                       "S1_S2_cap_fraction": d["S1_S2"].get("depth_cap_fraction"),
                       "S1_S2_step_median": d["S1_S2"].get("step_median_of_window_medians"),
                       "top_window": d["top_window"], "top_window_share": d["top_window_share"]} for d in all_st],
        "P3_stalled_per_gradient_wall_gt_2x_healthy": (all((d["ratio_to_healthy_pool"] or 0) > 2 for d in all_st)
                                                       if all_st else None),
        "P3_values": [{"cell": d["cell"], "chain": d["chain"], "ratio_to_healthy_pool": d["ratio_to_healthy_pool"],
                       "ratio_to_same_cell_others": d["ratio_to_same_cell_others"]} for d in all_st],
        "P4_one_mitigation_zero_stalls_and_identity": any(
            decision[a]["R1_zero_stalls"] and all(r.get("bit_identical") for r in decision[a]["seeds"]
                                                  if r.get("identity_possible_by_construction")) for a in MIT),
        "P5_uniform_ge_3_of_4_stall": per_arm.get("uniform", {}).get("stalled", 0) >= 3,
        "P5_value": per_arm.get("uniform", {}).get("stalled"),
        "P6_every_stalled_chain_identified_before_25pct": (all(d["early"]["early_before_25pct"] for d in all_st)
                                                           if all_st else None),
        "P6_values": [{"cell": d["cell"], "chain": d["chain"], "identified": d["early"]["identified"],
                       "earliest_fraction_of_wall": d["early"]["earliest_fraction_of_wall"]} for d in all_st],
    }
    summary = {"schema": "lotka-volterra-stall-v1-summary", "missing_cells": missing, "n_cells": len(rec),
               "healthy_eval_us_per_gradient_median_contended": healthy_wall, "per_arm": per_arm,
               "stalled_chains": stalled_desc, "slow_chains_in_completed_cells": slow_desc,
               "defaults_initial_phase_max_depth": {str(k): v for k, v in defaults_init_depth.items()},
               "decision": decision, "predictions": preds,
               "stage_mismatch_rows_total": sum(c.get("profile", {}).get("stage_mismatch_rows", 0) for c in rec.values())}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    # table
    L = ["# WP57 results table", "",
         "Wall is contended (sibling agents). `grads/chain` includes an unfinished transition's calls. "
         "`ident` = draw hash equals the defaults cell of the same seed.", "",
         "| cell | status | wall s | stalled | grads/chain | start log dens (min) | R-hat | min bulk | min tail | div | max abs z | gates | warnings | ident |",
         "|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|---|---|"]
    for c in sorted(rec.values(), key=lambda c: c["ordinal"]):
        d = by.get(("defaults", c["seed"]))
        ident = "" if c["arm"] in ("defaults", "uniform") or d is None else str(
            c.get("draw_hash") is not None and c.get("draw_hash") == d.get("draw_hash"))
        g = "/".join(f"{x / 1e3:.0f}k" for x in chain_grads(c))
        ok = c["status"] == "ok"
        fg = ("all" if c.get("passed") else ",".join(k for k, v in c["gates"].items() if not v)) if ok else "-"
        L.append(f"| {c['id']} | {c['status']} | {c['wall_seconds_contended']:.0f} | {c['stalled']} | {g} | "
                 f"{min(c['start_log_densities']):.4g} | {c['max_rank_rhat'] if not ok else round(c['max_rank_rhat'], 4) if ok else ''} | "
                 f"{round(c['min_bulk_ess']) if ok else ''} | {round(c['min_tail_ess']) if ok else ''} | "
                 f"{c.get('divergences', '') if ok else ''} | {round(c['max_abs_z'], 2) if ok else ''} | {fg} | "
                 f"{c.get('chain_warning_chains', '') if ok else ''} | {ident} |")
    L += ["", "## Stalled chains", "",
          "| cell | chain | start ld | grads | done | share S1+S2 | top window (share) | top: step med | top: cap frac | top: grads/leaf | top: sel level | us/grad | x healthy | x same-cell | early (frac wall) |",
          "|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for d in stalled_desc + slow_desc:
        t = d["top_window_stats"]
        L.append(f"| {d['cell']}{'' if d in stalled_desc else ' (slow, not stalled)'} | {d['chain']} | {d['start_log_density']:.4g} | "
                 f"{d['gradients_total']:.0f} | {d['transitions_done']} | {d['share_S1_S2']:.2f} | {d['top_window']} ({d['top_window_share']:.2f}) | "
                 f"{t['step_median']:.3g} | {t['depth_cap_fraction']:.2f} | {t['gradients_per_leaf'] or 0:.2f} | "
                 f"{t['selected_level_mean'] if t['selected_level_mean'] is None else round(t['selected_level_mean'], 2)} | "
                 f"{d['eval_us_per_gradient']:.0f} | {d['ratio_to_healthy_pool'] or 0:.2f} | {d['ratio_to_same_cell_others'] or 0:.2f} | "
                 f"{d['early']['earliest_fraction_of_wall'] if d['early']['earliest_fraction_of_wall'] is None else round(d['early']['earliest_fraction_of_wall'], 3)} |")
    L += ["", f"Healthy-chain median per-gradient wall (contended): {healthy_wall} us", "",
          "## Per arm", "", "```", json.dumps(per_arm, indent=1), "```", "",
          "## Decision", "", "```", json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != 'seeds'})
                                                 for k, v in decision.items()}, indent=1), "```"]
    (ART / "results-table.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(json.dumps(per_arm, indent=1))
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != 'seeds'})
                      for k, v in decision.items()}, indent=1))
    print(json.dumps(preds, indent=1))


if __name__ == "__main__":
    main()
