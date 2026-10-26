#!/usr/bin/env python3
"""WP67 analysis: the frozen decision rule, predictions and tables (`STUDIES/trapped_chain_restart_v1`).

Reads artifacts/cells/*.json only; writes artifacts/summary.json and artifacts/results-table.md.
Written with the preregistration, before the first evidence cell.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import run_study as rs

ART = rs.ART


def load() -> dict:
    cells = {}
    for c in rs.manifest():
        p = rs.CELLS / f"{c['id']}.json"
        if p.exists():
            cells[c["id"]] = json.loads(p.read_text(encoding="utf-8"))
    return cells


def pair_id(cell: dict, arm: str) -> str:
    name = "lotka" if cell["kind"] == "lotka" else rs.short(cell["model"])
    return f"{cell['block']}--{name}--{arm}--{cell['seed']}"


def flags_of(c: dict) -> list | None:
    """Flagged chains: actual (restart arm) or emulated (defaults arm). None if unknown."""
    if c is None:
        return None
    if c["arm"] == "restart":
        if c.get("restarted_chains") is not None:
            return sorted(c["restarted_chains"])
        return None
    em = c.get("detector_emulated_from_draw_run") or c.get("detector_emulated_epoch0")
    if em is None:
        return None
    return sorted(em["flagged"]) if em.get("scored") else []


def steps99(c: dict) -> list | None:
    """Per-chain step at transition 99 of the chain's first run."""
    if c is None:
        return None
    if c["arm"] == "restart" and c.get("trapped_chain_checks"):
        out = []
        for recs in c["trapped_chain_checks"]:
            out.append(recs[0]["step"] if recs else None)
        return out
    if c.get("per_chain_step_at_99") is not None and c["arm"] == "defaults":
        return c["per_chain_step_at_99"]
    em = c.get("detector_emulated_epoch0")
    return em["steps"] if em else None


def fingerprint(d: dict, r: dict) -> dict:
    """P4 / clause F for one (defaults, restart) pair."""
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
        # identity can only be checked on completed pairs; a timed-out pair is checked on flags/steps only
        out["identity"] = None
        out["holds"] = out["flag_sets_equal"] and out["steps_at_99_equal"]
        out["why"] = "not both completed: flags and steps only"
        return out
    if not fr:
        out["identity"] = (d["draw_hash"] == r["draw_hash"]) and (d["target_calls_total"] == r["target_calls_total"])
    else:
        keep = [i for i in range(len(d["per_chain_draw_hash"])) if i not in fr]
        out["identity"] = all(d["per_chain_draw_hash"][i] == r["per_chain_draw_hash"][i]
                              and d["per_chain_target_calls"][i] == r["per_chain_target_calls"][i] for i in keep)
    out["holds"] = bool(out["flag_sets_equal"] and out["steps_at_99_equal"] and out["identity"])
    return out


def trapped(c: dict | None) -> list:
    if c is None:
        return []
    return sorted(c.get("trapped_chains") or [])


def geomean(xs: list[float]) -> float:
    xs = [x for x in xs if x is not None and x > 0 and math.isfinite(x)]
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else float("nan")


def main() -> None:
    cells = load()
    manifest = rs.manifest()
    n_expected = len(manifest)
    pairs = {}
    for c in manifest:
        if c["arm"] != "defaults":
            continue
        key = (c["block"], c["model"], c["seed"])
        pairs[key] = {"defaults": cells.get(pair_id(c, "defaults")), "restart": cells.get(pair_id(c, "restart")),
                      "block": c["block"], "model": c["model"], "seed": c["seed"], "kind": c["kind"]}

    # ---------------- lotka
    lotka_rows, det = [], {"tp": 0, "fn": 0, "fp": 0, "tn": 0, "fn_not_reached": 0}
    tot = {b: {"defaults": 0, "restart": 0, "chains": 0, "pass_d": 0, "pass_r": 0, "grads_d": 0, "grads_r": 0,
               "cells_d": 0, "cells_r": 0} for b in ("L1", "L2")}
    retrapped = 0
    restarts_total = 0
    for key, p in pairs.items():
        if p["kind"] != "lotka":
            continue
        d, r = p["defaults"], p["restart"]
        td, tr = trapped(d), trapped(r)
        fd = flags_of(d) or []
        fr = flags_of(r) or []
        fp_ = fingerprint(d, r)
        b = p["block"]
        tot[b]["defaults"] += len(td)
        tot[b]["restart"] += len(tr)
        tot[b]["chains"] += 4
        tot[b]["pass_d"] += int(bool(d and d.get("passed")))
        tot[b]["pass_r"] += int(bool(r and r.get("passed")))
        tot[b]["cells_d"] += int(d is not None)
        tot[b]["cells_r"] += int(r is not None)
        tot[b]["grads_d"] += (d or {}).get("target_calls_total") or 0
        tot[b]["grads_r"] += (r or {}).get("target_calls_total") or 0
        restarts_total += len(fr)
        retrapped += len(set(fr) & set(tr))
        s99 = steps99(d) if d else None
        for ch in range(4):
            reached = s99 is not None and ch < len(s99) and s99[ch] is not None
            is_t, is_f = ch in td, ch in fd
            if is_t and not reached:
                det["fn_not_reached"] += 1
            elif is_t and is_f:
                det["tp"] += 1
            elif is_t:
                det["fn"] += 1
            elif is_f:
                det["fp"] += 1
            else:
                det["tn"] += 1
        lotka_rows.append({
            "block": b, "seed": p["seed"],
            "defaults": None if d is None else {"status": d["status"], "passed": d.get("passed"), "trapped": td,
                                                "flags_emulated": fd, "rhat": d.get("max_rank_rhat"),
                                                "min_bulk": d.get("min_bulk_ess"), "grads": d.get("target_calls_total"),
                                                "wall": d.get("wall_seconds_pinned_cotenanted"),
                                                "shift": d.get("per_chain_shift_ref_sd"), "hash": d.get("draw_hash"),
                                                "ratios": (d.get("detector_emulated_from_draw_run") or d.get("detector_emulated_epoch0") or {}).get("ratios")},
            "restart": None if r is None else {"status": r["status"], "passed": r.get("passed"), "trapped": tr,
                                               "restarted": fr, "rhat": r.get("max_rank_rhat"),
                                               "min_bulk": r.get("min_bulk_ess"), "grads": r.get("target_calls_total"),
                                               "wall": r.get("wall_seconds_pinned_cotenanted"),
                                               "shift": r.get("per_chain_shift_ref_sd"), "hash": r.get("draw_hash")},
            "fingerprint": fp_,
        })

    # ---------------- regression
    reg_rows, per_model = [], {}
    pass_d = pass_r = wrong_d = wrong_r = 0
    reg_firing = 0
    for key, p in pairs.items():
        if p["kind"] != "regression":
            continue
        d, r = p["defaults"], p["restart"]
        fp_ = fingerprint(d, r)
        pass_d += int(bool(d and d.get("passed")))
        pass_r += int(bool(r and r.get("passed")))
        wrong_d += int(bool(d and d.get("wrong_chain_cell")))
        wrong_r += int(bool(r and r.get("wrong_chain_cell")))
        fr = flags_of(r) or []
        reg_firing += int(bool(fr))
        if d and r and d.get("completed") and r.get("completed"):
            per_model.setdefault(p["model"], []).append(
                (d["min_bulk_ess_per_gradient"], r["min_bulk_ess_per_gradient"]))
        reg_rows.append({"model": p["model"], "seed": p["seed"],
                         "defaults": None if d is None else {"status": d["status"], "passed": d.get("passed"),
                                                             "rhat": d.get("max_rank_rhat"), "min_bulk": d.get("min_bulk_ess"),
                                                             "min_tail": d.get("min_tail_ess"), "div": d.get("divergences"),
                                                             "ess_per_grad": d.get("min_bulk_ess_per_gradient"),
                                                             "wrong_chain_cell": d.get("wrong_chain_cell"),
                                                             "flags_emulated": flags_of(d),
                                                             "ratios": (d.get("detector_emulated_from_draw_run") or {}).get("ratios")},
                         "restart": None if r is None else {"status": r["status"], "passed": r.get("passed"),
                                                            "rhat": r.get("max_rank_rhat"), "min_bulk": r.get("min_bulk_ess"),
                                                            "min_tail": r.get("min_tail_ess"), "div": r.get("divergences"),
                                                            "ess_per_grad": r.get("min_bulk_ess_per_gradient"),
                                                            "wrong_chain_cell": r.get("wrong_chain_cell"), "restarted": fr},
                         "fingerprint": fp_})
    model_ratio = {}
    for m, xs in per_model.items():
        model_ratio[m] = geomean([b for _, b in xs]) / geomean([a for a, _ in xs])
    eff = geomean(list(model_ratio.values())) if len(model_ratio) == len(rs.REGRESSION) else float("nan")

    # ---------------- clauses
    pooled_d = tot["L1"]["defaults"] + tot["L2"]["defaults"]
    pooled_r = tot["L1"]["restart"] + tot["L2"]["restart"]
    fp_all = [row["fingerprint"] for row in lotka_rows + reg_rows]
    F = all(f.get("holds") for f in fp_all if f.get("evaluable")) and any(f.get("evaluable") for f in fp_all)
    E_evaluable = pooled_d >= 2
    E = E_evaluable and pooled_r <= pooled_d // 2
    Gc = (tot["L1"]["pass_r"] + tot["L2"]["pass_r"]) >= (tot["L1"]["pass_d"] + tot["L2"]["pass_d"])
    R1 = pass_r >= pass_d
    R2 = math.isfinite(eff) and eff >= 0.95
    R3 = wrong_r <= wrong_d
    complete = len(cells) == n_expected
    if not complete:
        verdict = f"INCOMPLETE ({len(cells)}/{n_expected} cells): no verdict under the frozen rule"
    elif not F:
        verdict = "FAILED (implementation): the fingerprint clause F does not hold"
    elif not E_evaluable:
        verdict = "INCONCLUSIVE: fewer than 2 trapped defaults chains pooled over L1 and L2, efficacy not evaluable"
    elif E and Gc and R1 and R2 and R3:
        verdict = "SUPPORTED: recommend a default-flip confirmation study"
    else:
        verdict = "NOT SUPPORTED: no default change proposed"
    preds = {
        "P1": {"text": rs.PROTOCOL["predictions"]["P1"], "observed": tot["L1"]["defaults"],
               "held": 1 <= tot["L1"]["defaults"] <= 3},
        "P2": {"text": rs.PROTOCOL["predictions"]["P2"], "observed": tot["L1"]["restart"],
               "held": tot["L1"]["restart"] <= 1},
        "P3": {"text": rs.PROTOCOL["predictions"]["P3"], "observed": det,
               "held": det["fn"] == 0 and det["fp"] <= 1},
        "P4": {"text": rs.PROTOCOL["predictions"]["P4"], "observed": f"{sum(bool(f.get('holds')) for f in fp_all)}/{len(fp_all)} pairs",
               "held": F},
        "P5": {"text": rs.PROTOCOL["predictions"]["P5"], "observed": f"{reg_firing}/{len(reg_rows)} firing; ratio {eff:.4f}",
               "held": reg_firing == 0},
        "P6": {"text": rs.PROTOCOL["predictions"]["P6"],
               "observed": {"grads_defaults": tot["L1"]["grads_d"] + tot["L2"]["grads_d"],
                            "grads_restart": tot["L1"]["grads_r"] + tot["L2"]["grads_r"], "restarts": restarts_total},
               "held": None if restarts_total == 0 else
               (tot["L1"]["grads_r"] + tot["L2"]["grads_r"]) < (tot["L1"]["grads_d"] + tot["L2"]["grads_d"])},
        "P7": {"text": rs.PROTOCOL["predictions"]["P7"], "observed": retrapped, "held": retrapped <= 1},
    }
    summary = {
        "cells_written": len(cells), "cells_expected": n_expected, "complete": complete,
        "lotka_totals": tot, "pooled_trapped": {"defaults": pooled_d, "restart": pooled_r},
        "detector_lotka_defaults": det, "restarts_total_lotka": restarts_total, "retrapped": retrapped,
        "regression": {"passes_defaults": pass_d, "passes_restart": pass_r, "wrong_defaults": wrong_d,
                       "wrong_restart": wrong_r, "firing_cells": reg_firing, "per_model_ratio": model_ratio,
                       "geomean_ratio": eff},
        "clauses": {"E": E, "E_evaluable": E_evaluable, "F": F, "G": Gc, "R1": R1, "R2": R2, "R3": R3},
        "verdict": verdict, "predictions": preds, "lotka_rows": lotka_rows, "regression_rows": reg_rows,
    }
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n", encoding="utf-8")
    lines = [f"# WP67 results ({len(cells)}/{n_expected} cells)", "", f"**Verdict:** {verdict}", "",
             "| clause | holds |", "|---|---|"]
    for k, v in summary["clauses"].items():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## Lotka (trapped chains / 48 per block)", "",
              "| block | defaults trapped | restart trapped | defaults passes | restart passes | defaults gradients | restart gradients |",
              "|---|---|---|---|---|---|---|"]
    for b in ("L1", "L2"):
        t = tot[b]
        lines.append(f"| {b} | {t['defaults']} | {t['restart']} | {t['pass_d']}/{t['cells_d']} | {t['pass_r']}/{t['cells_r']} | {t['grads_d']} | {t['grads_r']} |")
    lines += ["", "| block | seed | defaults status | trapped | flags (emulated) | min ratio | R-hat | restart status | restarted | trapped | R-hat | fingerprint |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for row in lotka_rows:
        d, r = row["defaults"] or {}, row["restart"] or {}
        ratios = d.get("ratios")
        mr = f"{min(ratios):.4f}" if ratios else "-"
        rh = lambda x: "-" if x is None else f"{x:.3f}"  # noqa: E731
        lines.append(f"| {row['block']} | {row['seed']} | {d.get('status')} | {d.get('trapped')} | {d.get('flags_emulated')} | {mr} | "
                     f"{rh(d.get('rhat'))} | {r.get('status')} | {r.get('restarted')} | {r.get('trapped')} | {rh(r.get('rhat'))} | "
                     f"{row['fingerprint'].get('holds')} |")
    lines += ["", f"Detector on lotka defaults chains: {det}", "", "## Regression arm", "",
              f"Passes: defaults {pass_d}, restart {pass_r} of {len(reg_rows)}; wrong-chain cells {wrong_d} vs {wrong_r}; "
              f"firing cells {reg_firing}; geomean ESS/gradient ratio {eff:.4f}", "",
              "| model | seed | d passed | d R-hat | d min bulk | d ESS/grad | min step ratio | r passed | restarted | r ESS/grad | fingerprint |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for row in reg_rows:
        d, r = row["defaults"] or {}, row["restart"] or {}
        ratios = d.get("ratios")
        mr = f"{min(ratios):.3f}" if ratios else "-"
        f = lambda x, s: "-" if x is None else format(x, s)  # noqa: E731
        lines.append(f"| {row['model']} | {row['seed']} | {d.get('passed')} | {f(d.get('rhat'), '.4f')} | {f(d.get('min_bulk'), '.0f')} | "
                     f"{f(d.get('ess_per_grad'), '.3e')} | {mr} | {r.get('passed')} | {r.get('restarted')} | {f(r.get('ess_per_grad'), '.3e')} | "
                     f"{row['fingerprint'].get('holds')} |")
    lines += ["", "## Predictions", "", "| id | observed | held |", "|---|---|---|"]
    for k, v in preds.items():
        lines.append(f"| {k} | {v['observed']} | {v['held']} |")
    (ART / "results-table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:12]))


if __name__ == "__main__":
    main()
