#!/usr/bin/env python3
"""WP74 analysis (`STUDIES/chain_disagreement_splits_v1`), written before the first evidence cell.

Reads artifacts/cells/*.json, applies the frozen definitions and decision rule of protocol.json /
PREREGISTRATION.md, writes artifacts/summary.json and artifacts/results-table.md.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
ART = Path(os.environ["WP74_ART"]) if os.environ.get("WP74_ART") else HERE / "artifacts"
STUDIES = HERE.parent


def load_cells() -> list[dict]:
    import run_study

    order = {c["id"]: i for i, c in enumerate(run_study.manifest())}
    cells = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ART / "cells").glob("*.json"))]
    return sorted(cells, key=lambda c: order.get(c["id"], 10**9))


def ok(c: dict) -> bool:
    return c.get("status") == "ok"


def named(c: dict, rule: str) -> list[int]:
    r = c["split_rules"]
    return {"current": r["current"]["disagreement_chains"], "K": r["pair_clusters"]["named"],
            "cand_K": r["candidate_k"]["chains"], "S": r["split_rhat"]["named"],
            "G": r["density_clusters"]["named"], "cand_S": r["candidate_s"]["chains"],
            "cand_G": r["candidate_g"]["chains"]}[rule]


def split_of(c: dict):
    """(is_split, kind, groups) per the frozen definitions; None when undefined (unscored / failed)."""
    if not ok(c):
        return None
    if c["kind"] == "two_mode":
        return c["split"], c["split_kind"], [c["mode_groups"]["minor"], c["mode_groups"]["major"]]
    if not c.get("scored"):
        return None
    off = c["off_chains"]
    k = min(len(off), 4 - len(off))
    on = [i for i in range(4) if i not in off]
    return bool(off), (f"{4 - k}-{k}" if off else None), [off, on]


def split_row(c: dict) -> dict:
    sp = split_of(c)
    row = {"id": c["id"], "status": c.get("status"), "role": c.get("role")}
    if sp is None:
        return {**row, "split": None}
    is_split, kind, groups = sp
    row.update({"split": is_split, "split_kind": kind, "groups": groups,
                "max_rhat": c.get("max_split_rhat", c.get("max_rank_rhat")),
                "current": named(c, "current"), "K": named(c, "K"), "S": named(c, "S"), "G": named(c, "G"),
                "reported_current": bool(named(c, "current")), "reported_K": bool(named(c, "cand_K")),
                "reported_S": bool(named(c, "cand_S")),
                "reported_G": bool(named(c, "cand_G")),
                "S_max_rhat_unconstrained": c["split_rules"]["split_rhat"].get("max_rhat"),
                "K_clusters": c["split_rules"]["pair_clusters"].get("clusters"),
                "K_pairs": c["split_rules"]["pair_clusters"].get("pairs"),
                "S_partitions": c["split_rules"]["split_rhat"].get("partitions"),
                "G_max_gap_over_threshold": {w: c["split_rules"]["density_clusters"][w].get("max_gap_over_threshold")
                                             for w in ("warmup_end", "sampling_end")}})
    if is_split:
        gs = [sorted(g) for g in groups]
        row["K_names_a_true_group"] = sorted(named(c, "K")) in gs if named(c, "K") else None
        row["S_names_a_true_group"] = sorted(named(c, "S")) in gs if named(c, "S") else None
        row["G_names_a_true_group"] = sorted(named(c, "G")) in gs if named(c, "G") else None
    return row


def arm_i(cells: list[dict], block: str) -> dict:
    rows = [split_row(c) for c in cells if c["block"] == block]
    splits = [r for r in rows if r.get("split")]
    undefined = [r["id"] for r in rows if r.get("split") is None]
    res = {"cells": rows, "undefined_cells": undefined, "split_cells": [r["id"] for r in splits],
           "n_split": len(splits), "n_2_2": sum(r["split_kind"] == "2-2" for r in splits),
           "n_3_1": sum(r["split_kind"] == "3-1" for r in splits)}
    for rule in ("current", "K", "S", "G"):
        rep = [r["id"] for r in splits if r[f"reported_{rule}"]]
        res[f"reported_{rule}"] = rep
        res[f"missed_{rule}"] = [r["id"] for r in splits if not r[f"reported_{rule}"]]
    res["non_split_new_K"] = [r["id"] for r in rows if r.get("split") is False and r["K"]]
    res["non_split_new_S"] = [r["id"] for r in rows if r.get("split") is False and r["S"]]
    res["non_split_new_G"] = [r["id"] for r in rows if r.get("split") is False and r["G"]]
    for rule in ("K", "S", "G"):
        res[f"clause_i_{rule}"] = (not undefined and res["n_2_2"] >= 1 and not res[f"missed_{rule}"])
    res["tested"] = res["n_2_2"] >= 1
    return res


def arm_ii(cells: list[dict]) -> dict:
    rows = []
    for c in cells:
        if c["block"] != "II":
            continue
        if not ok(c):
            rows.append({"id": c["id"], "status": c.get("status"), "passed": False})
            continue
        rows.append({"id": c["id"], "model": c["model"], "seed": c["seed"], "status": "ok", "passed": c["passed"],
                     "max_rank_rhat": c["max_rank_rhat"], "off_chains": c["off_chains"],
                     "S_max_rhat_unconstrained": c["split_rules"]["split_rhat"].get("max_rhat"),
                     "current": named(c, "current"), "K": named(c, "K"), "S": named(c, "S"), "G": named(c, "G"),
                     "G_max_gap_over_threshold": {w: c["split_rules"]["density_clusters"][w].get("max_gap_over_threshold")
                                                  for w in ("warmup_end", "sampling_end")}})
    passing = [r for r in rows if r.get("passed")]
    failing = [r for r in rows if r.get("status") == "ok" and not r["passed"]]
    res = {"cells": rows, "n": len(rows), "n_completed": sum(r.get("status") == "ok" for r in rows),
           "n_passing": len(passing), "n_failing_completed": len(failing),
           "not_completed": [r["id"] for r in rows if r.get("status") != "ok"]}
    for rule in ("K", "S", "G"):
        res[f"fp_{rule}"] = [r["id"] for r in passing if r[rule]]
        res[f"failing_new_{rule}"] = [{"id": r["id"], "named": r[rule], "off_chains": r["off_chains"],
                                       "named_off": bool(set(r[rule]) & set(r["off_chains"]))}
                                      for r in failing if r[rule]]
        res[f"clause_ii_{rule}"] = not res[f"fp_{rule}"]
    res["current_on_passing"] = [r["id"] for r in passing if r["current"]]
    res["max_G_gap_over_threshold_passing"] = max(
        [v for r in passing for v in r["G_max_gap_over_threshold"].values() if v is not None], default=None)
    return res


def recorded(c: dict):
    """The warning chains the source study recorded for a replayed cell (context, not decision)."""
    m, seed = c["model"], c["seed"]
    name = "funnel10" if m == "funnel10" else m.replace("-", "__")
    if seed in (97464, 97465, 97466, 97467, 97468):
        p = STUDIES / "chain_disagreement_warning_v1" / "artifacts" / "cells" / f"{name}-{seed}.json"
        if not p.exists():
            return None
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("status") != "ok":
            return {"status": d.get("status")}
        lines = d.get("warning_lines") or []
        return {"status": "ok", "chains": sorted({int(l.split("chain ")[1].split()[0]) for l in lines})}
    if seed in (731401, 731402, 731403):
        p = STUDIES / "silent_funnel_diagnostic_v1" / "artifacts" / "cells" / f"{name}-{seed}.json"
        if not p.exists():
            return None
        d = json.loads(p.read_text(encoding="utf-8"))
        return {"status": d.get("status"),
                "chains": sorted({w["chain"] for w in (d.get("wp44_warnings") or []) if w.get("check") != "other"})}
    if seed in (5701103, 5701106):
        p = STUDIES / "trapped_chain_restart_v1" / "artifacts" / "cells" / f"L1--lotka--defaults--{seed}.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        return {"status": d.get("status"), "chains": sorted(set(d.get("chain_warning_chains") or [])),
                "draw_hash": d.get("draw_hash")}
    return None


def arm_iii(cells: list[dict]) -> dict:
    rows = []
    for c in cells:
        if c["block"] != "III":
            continue
        row = {"id": c["id"], "status": c.get("status"), "recorded": recorded(c)}
        if ok(c):
            cur, ck, cs, cg = named(c, "current"), named(c, "cand_K"), named(c, "cand_S"), named(c, "cand_G")
            row.update({"current": cur, "K": named(c, "K"), "S": named(c, "S"), "G": named(c, "G"),
                        "cand_K": ck, "cand_S": cs, "cand_G": cg, "regression_K": sorted(set(cur) - set(ck)),
                        "regression_S": sorted(set(cur) - set(cs)), "regression_G": sorted(set(cur) - set(cg)),
                        "scored": c.get("scored", False), "off_chains": c.get("off_chains"),
                        "passed": c.get("passed"), "max_rank_rhat": c.get("max_rank_rhat"),
                        "S_max_rhat_unconstrained": c["split_rules"]["split_rhat"].get("max_rhat"),
                        "draw_hash": c.get("draw_hash")})
            rec = row["recorded"]
            if rec and rec.get("status") == "ok":
                row["recorded_fired"] = bool(rec["chains"])
                row["replay_fired_current"] = bool(cur)
                if "draw_hash" in rec:
                    row["hash_reproduced"] = rec["draw_hash"] == c.get("draw_hash")
        rows.append(row)
    done = [r for r in rows if r["status"] == "ok"]
    res = {"cells": rows, "n": len(rows), "n_completed": len(done),
           "not_completed": [r["id"] for r in rows if r["status"] != "ok"],
           "current_fired": [r["id"] for r in done if r["current"]],
           "recorded_fired": [r["id"] for r in rows if (r.get("recorded") or {}).get("chains")]}
    for rule in ("K", "S", "G"):
        res[f"regressions_{rule}"] = [r["id"] for r in done if r[f"regression_{rule}"]]
        res[f"new_{rule}"] = [{"id": r["id"], "named": r[rule], "off_chains": r["off_chains"]} for r in done if r[rule]]
        res[f"clause_iii_{rule}"] = not res[f"regressions_{rule}"]
    return res


def replay_hashes(cells: list[dict]) -> dict:
    ref = PROTOCOL["replay_reference_hashes"]
    out = {}
    for c in cells:
        k = c["id"]
        if k in ref:
            out[k] = {"expected": ref[k], "observed": c.get("draw_hash"), "equal": ref[k] == c.get("draw_hash")}
    return out


def main() -> None:
    cells = load_cells()
    impl = [c["id"] for c in cells if ok(c) and not c.get("implementation_check")]
    a1, a1m = arm_i(cells, "I"), arm_i(cells, "IV")
    a2, a3 = arm_ii(cells), arm_iii(cells)
    clauses = {rule: {"i": a1[f"clause_i_{rule}"], "ii": a2[f"clause_ii_{rule}"], "iii": a3[f"clause_iii_{rule}"]}
               for rule in ("K", "S", "G")}
    if impl:
        verdict = "FAILED (implementation)"
    elif all(clauses["K"].values()):
        verdict = "PROPOSE K"
    elif all(clauses["S"].values()):
        verdict = "PROPOSE S"
    elif all(clauses["G"].values()):
        verdict = "PROPOSE G"
    else:
        verdict = "DO NOT PROPOSE"
    summary = {
        "schema": "chain-disagreement-splits-v1-summary", "n_cells": len(cells),
        "n_ok": sum(ok(c) for c in cells), "not_ok": [(c["id"], c.get("status")) for c in cells if not ok(c)],
        "implementation_mismatches": impl, "clauses": clauses, "verdict": verdict,
        "arm_i": a1, "motivating_replay": a1m, "arm_ii": a2, "arm_iii": a3, "replay_hashes": replay_hashes(cells),
    }
    (ART / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")

    L = [f"# WP74 results ({len(cells)} cells, {summary['n_ok']} ok)", "",
         f"**Verdict: {verdict}.** Implementation mismatches: {len(impl)}.", "",
         "| clause | K | S | G |", "|---|---|---|---|"]
    for k in ("i", "ii", "iii"):
        L.append(f"| ({k}) | {clauses['K'][k]} | {clauses['S'][k]} | {clauses['G'][k]} |")
    for title, a in (("Arm (i), fresh (block I)", a1), ("Motivating replay (block IV, not decision)", a1m)):
        L += ["", f"## {title}", "",
              f"splits {a['n_split']} (2-2: {a['n_2_2']}, 3-1: {a['n_3_1']}); undefined {a['undefined_cells']}; "
              f"missed: current {a['missed_current']}, K {a['missed_K']}, S {a['missed_S']}, G {a['missed_G']}; "
              f"non-split firings K {a['non_split_new_K']} S {a['non_split_new_S']} G {a['non_split_new_G']}", "",
              "| cell | split | groups | max R-hat | current | K | S | G | K true group | K clusters | G gap/thr (warm, samp) |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in a["cells"]:
            if r.get("split") is None:
                L.append(f"| {r['id']} | undefined ({r['status']}) | | | | | | | | | |")
                continue
            gg = r["G_max_gap_over_threshold"]
            fmt = lambda v: "-" if v is None else f"{v:.2f}"
            L.append(f"| {r['id']} | {r['split_kind'] or 'none'} | {r['groups']} | {r['max_rhat']:.3f} | {r['current']} | "
                     f"{r['K']} | {r['S']} | {r['G']} | {r.get('K_names_a_true_group')} | {r['K_clusters']} | "
                     f"{fmt(gg['warmup_end'])}, {fmt(gg['sampling_end'])} |")
    L += ["", "## Arm (ii), 17 house models x 3 fresh seeds", "",
          f"completed {a2['n_completed']}/{a2['n']}; passing {a2['n_passing']}; not completed {a2['not_completed']}; "
          f"FP K {a2['fp_K']}; FP S {a2['fp_S']}; FP G {a2['fp_G']}; shipped warning on passing cells {a2['current_on_passing']}; "
          f"max G gap/threshold on passing cells {a2['max_G_gap_over_threshold_passing']}", "",
          f"New K firings on failing cells: {a2['failing_new_K']}", "",
          f"New S firings on failing cells: {a2['failing_new_S']}", "",
          f"New G firings on failing cells: {a2['failing_new_G']}", "",
          "| cell | passed | R-hat | off | max R (unc) | current | K | S | G |", "|---|---|---|---|---|---|---|---|---|"]
    for r in a2["cells"]:
        if r.get("status") != "ok":
            L.append(f"| {r['id']} | {r.get('status')} | | | | | | | |")
            continue
        sm = r["S_max_rhat_unconstrained"]
        L.append(f"| {r['id']} | {r['passed']} | {r['max_rank_rhat']:.4f} | {r['off_chains']} | "
                 f"{'-' if sm is None else f'{sm:.4f}'} | {r['current']} | {r['K']} | {r['S']} | {r['G']} |")
    L += ["", "## Arm (iii), replays", "",
          f"completed {a3['n_completed']}/{a3['n']}; regressions K {a3['regressions_K']} S {a3['regressions_S']} "
          f"G {a3['regressions_G']}; "
          f"shipped warning fired on {a3['current_fired']}; source studies recorded it on {a3['recorded_fired']}", "",
          "| cell | status | recorded (source) | current | K | S | G | off | passed | hash reproduced |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in a3["cells"]:
        rec = r.get("recorded") or {}
        L.append(f"| {r['id']} | {r['status']} | {rec.get('chains', rec.get('status'))} | {r.get('current')} | "
                 f"{r.get('K')} | {r.get('S')} | {r.get('G')} | {r.get('off_chains')} | {r.get('passed')} | {r.get('hash_reproduced', '-')} |")
    L += ["", "## Replay hashes", ""]
    for k, v in summary["replay_hashes"].items():
        L.append(f"- {k}: expected {v['expected']}, observed {v['observed']}, equal {v['equal']}")
    (ART / "results-table.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"verdict: {verdict}; clauses {clauses}; impl mismatches {len(impl)}")


if __name__ == "__main__":
    main()
