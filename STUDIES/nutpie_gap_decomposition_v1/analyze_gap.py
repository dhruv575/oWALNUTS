#!/usr/bin/env python3
"""WP80 analysis: where nutpie's per-gradient lead over oWALNUTS on the fixed 16 comes from.

    python analyze_gap.py      # writes artifacts/summary.json and artifacts/results-table.md

Part 1 (descriptive, cells already on disk): per model, the paired per-seed log gap
    G = ln(nutpie ESS/grad / oWALNUTS ESS/grad) = A + B + C   (exact; both arms retain 4 x 1,000 draws)
    A = ln(min bulk ESS nutpie / oWALNUTS)                         ESS per draw
    B = ln(sampling gradients per draw oWALNUTS / nutpie)          sampling cost per draw
    C = ln((total/sampling gradients) oWALNUTS / nutpie)           warmup overhead
over the 18 seeds (oWALNUTS: WP64 v7 + ext and WP72 cells; nutpie: WP76 cells), averaged over paired ok seeds.

Part 3 (telemetry cells of this study, three carrying models + diamonds, seeds 720701-720703):
    B = B4 + B1 + B2   (exact)
    B4 = ln(sum target evaluations / sum leaves attempted)          oWALNUTS refinement + reverse-check spend (H4)
    B1 = ln(e_nutpie / e_oWALNUTS)                                  effective step in posterior-scale units (H1)
    B2 = B - B4 - B1 = ln(D_oWALNUTS / D_nutpie)                    distance per draw, D = steps per draw x e (H2)
    H3: S = SD over coordinates of ln(inverse mass_i / sigma_i^2); supported per model if S_o - S_n >= 0.35.
All rules are fixed in protocol.json ("analysis").
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import statistics
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
STUDY = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
A = STUDY["analysis"]
MODELS = STUDY["models"]
SEEDS = STUDY["seeds"]
ALL = SEEDS["all"]
TEL = STUDY["telemetry"]
WP64 = HERE.parent / "posteriordb_bench_v7_linux_v1" / "artifacts"
WP72 = HERE.parent / "posteriordb_ratio_robustness_v1" / "artifacts"
WP76 = HERE.parent / "nutpie_18seed_v1" / "artifacts"
OWN = HERE / "artifacts"
SOURCES = {
    "owalnuts": [(WP64 / "v7", SEEDS["wp64_v7"]), (WP64 / "ext", SEEDS["wp64_ext"]), (WP72, SEEDS["wp72"])],
    "nutpie": [(WP76, ALL)],
}
DRAWS_PER_ARM = 4000


def short(m: str) -> str:
    return m.replace("-", "__")


def jload(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def ok(c) -> bool:
    return bool(c) and c.get("status") == "ok" and all(
        c.get(k) is not None and math.isfinite(c[k]) and c[k] > 0
        for k in ("min_bulk_ess", "gradients_total", "gradients_sampling"))


def mean(xs):
    xs = [x for x in xs if x is not None and math.isfinite(x)]
    return float(sum(xs) / len(xs)) if xs else float("nan")


def split(o: dict, n: dict) -> dict:
    """The exact cell-level split G = A + B + C of one paired seed (o = oWALNUTS cell, n = nutpie cell)."""
    a = math.log(n["min_bulk_ess"] / o["min_bulk_ess"])
    b = math.log(o["gradients_sampling"] / n["gradients_sampling"])
    c = math.log((o["gradients_total"] / o["gradients_sampling"]) / (n["gradients_total"] / n["gradients_sampling"]))
    g = math.log((n["min_bulk_ess"] / n["gradients_total"]) / (o["min_bulk_ess"] / o["gradients_total"]))
    out = {"G": g, "A": a, "B": b, "C": c, "closure": g - (a + b + c)}
    lb = o.get("retained_leaves_built")
    out["B4_cell_built"] = math.log(o["gradients_sampling"] / lb) if lb else float("nan")
    out["grad_per_draw_o"] = o["gradients_sampling"] / DRAWS_PER_ARM
    out["grad_per_draw_n"] = n["gradients_sampling"] / DRAWS_PER_ARM
    out["warmup_grad_o"] = o["gradients_total"] - o["gradients_sampling"]
    out["warmup_grad_n"] = n["gradients_total"] - n["gradients_sampling"]
    return out


# --------------------------------------------------------------------------- part 1


def part1() -> dict:
    data = {m: {a: {} for a in SOURCES} for m in MODELS}
    for a, srcs in SOURCES.items():
        for d, seeds in srcs:
            for m in MODELS:
                for s in seeds:
                    data[m][a][s] = jload(d / "cells" / f"{short(m)}-{a}-{s}.json")
    need = math.ceil(A["min_ok_fraction"] * len(ALL))
    per = {}
    for m in MODELS:
        rows = {s: split(data[m]["owalnuts"][s], data[m]["nutpie"][s]) for s in ALL
                if ok(data[m]["owalnuts"].get(s)) and ok(data[m]["nutpie"].get(s))}
        e = {"paired_ok_seeds": len(rows), "enters": len(rows) >= need}
        for k in ("G", "A", "B", "C", "B4_cell_built", "closure"):
            e[k] = mean(r[k] for r in rows.values())
        for k in ("grad_per_draw_o", "grad_per_draw_n", "warmup_grad_o", "warmup_grad_n"):
            e[k] = statistics.median(r[k] for r in rows.values()) if rows else None
        # WP76's per-model statistic (c), oWALNUTS/nutpie per gradient: median over seeds of the paired ratio
        e["c_ratio_o_over_n"] = statistics.median(math.exp(-r["G"]) for r in rows.values()) if rows else None
        e["per_seed"] = {str(s): r for s, r in rows.items()}
        per[m] = e
    entering = [m for m in MODELS if per[m]["enters"]]
    total = sum(per[m]["G"] for m in entering)
    for m in entering:
        per[m]["share_of_sum_G"] = per[m]["G"] / total if total else float("nan")
    ranked = sorted(entering, key=lambda m: per[m]["G"], reverse=True)
    geo = {k: mean(per[m][k] for m in entering) for k in ("G", "A", "B", "C", "B4_cell_built")}
    top3 = ranked[:3]
    return {"per_model": per, "entering": entering, "ranked_by_G": ranked, "top3": top3, "bottom3": ranked[-3:],
            "mean_over_models": geo, "lead_mean_of_logs": math.exp(geo["G"]),
            "lead_from_c_geomean": 1.0 / math.exp(mean(math.log(per[m]["c_ratio_o_over_n"]) for m in entering)),
            "P1_top3_predicted": STUDY["predictions"]["P1"]["top3"],
            "P1_held": set(top3) == set(STUDY["predictions"]["P1"]["top3"]),
            "top3_share_of_sum_G": sum(per[m]["share_of_sum_G"] for m in top3)}


# --------------------------------------------------------------------------- part 3 (telemetry)


def robust_scale(x: np.ndarray) -> np.ndarray:
    """1.4826 x MAD per coordinate of pooled draws (rows = draws); the sd where the MAD is zero."""
    med = np.median(x, axis=0)
    s = 1.4826 * np.median(np.abs(x - med), axis=0)
    sd = x.std(axis=0)
    return np.where(s > 0, s, sd)


def owalnuts_tel(m: str, s: int) -> dict | None:
    p = OWN / "telemetry" / f"{short(m)}-owalnuts-{s}.json.gz"
    if not p.exists():
        return None
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def telemetry_cell(m: str, s: int) -> dict:
    o = jload(OWN / "cells" / f"{short(m)}-owalnuts-{s}.json")
    n = jload(OWN / "cells" / f"{short(m)}-nutpie-{s}.json")
    r: dict = {"owalnuts_status": o and o.get("status"), "nutpie_status": n and n.get("status"),
               "owalnuts_passed": o and o.get("passed"), "nutpie_passed": n and n.get("passed")}
    # bit-identity with the WP72 / WP76 cells of the same seed (same build recipe, same box)
    for arm, cur, old in (("owalnuts", o, jload(WP72 / "cells" / f"{short(m)}-owalnuts-{s}.json")),
                          ("nutpie", n, jload(WP76 / "cells" / f"{short(m)}-nutpie-{s}.json"))):
        keys = ("status", "gradients_total", "gradients_sampling", "min_bulk_ess", "divergences")
        r[f"identical_to_prior_{arm}"] = bool(cur and old and all(cur.get(k) == old.get(k) for k in keys))
    if not (ok(o) and ok(n)):
        r["usable"] = False
        return r
    r["usable"] = True
    r.update({k: v for k, v in split(o, n).items() if k in ("G", "A", "B", "C")})
    t = owalnuts_tel(m, s)
    zt = np.load(OWN / "telemetry" / f"{short(m)}-nutpie-{s}.npz")
    zo = np.load(OWN / "draws" / f"{short(m)}-owalnuts-{s}.npz")
    ch = t["chains"]
    te = np.concatenate([np.asarray(c["telemetry_retained"]["target_evaluations"], float) for c in ch])
    la = np.concatenate([np.asarray(c["telemetry_retained"]["leaves_attempted"], float) for c in ch])
    lb = np.concatenate([np.asarray(c["telemetry_retained"]["leaves_built"], float) for c in ch])
    od = np.concatenate([np.asarray(c["telemetry_retained"]["depth"], float) for c in ch])
    ost = np.concatenate([np.asarray(c["telemetry_retained"]["orbit_states"], float) for c in ch])
    lvl = np.concatenate([np.asarray([-1 if v is None else v for v in c["telemetry_retained"]["selected_refinement_level"]], float) for c in ch])
    ra = np.concatenate([np.asarray(c["telemetry_retained"]["refinement_attempts"], float) for c in ch])
    rcr = np.concatenate([np.asarray(c["telemetry_retained"]["reverse_coarser_rejections"], float) for c in ch])
    nsteps = np.asarray(zt["retained__n_steps"], float)
    ndepth = np.asarray(zt["retained__depth"], float)
    r["telemetry_sum_te_equals_cell_gradients_sampling"] = int(te.sum()) == o["gradients_sampling"]
    r["telemetry_sum_n_steps_equals_cell_gradients_sampling"] = int(nsteps.sum()) == n["gradients_sampling"]
    B_tel = math.log(te.sum() / nsteps.sum())
    r["B_telemetry"] = B_tel
    r["B4"] = math.log(te.sum() / la.sum())
    # metrics and effective steps
    unc_o = np.asarray(zo["unconstrained"], float)  # (chains, draws, dim)
    unc_n = np.asarray(zt["retained__unconstrained_draw"], float)
    pooled = np.concatenate([unc_o.reshape(-1, unc_o.shape[-1]), unc_n.reshape(-1, unc_n.shape[-1])])
    sig = robust_scale(pooled)
    minv_o = 1.0 / np.asarray([c["mass_diagonal"] for c in ch], float)  # K = 0.5 sum p^2 / M_i: inverse mass 1/M_i
    eps_o = np.asarray([c["final_step_size"] for c in ch], float)
    minv_n = np.asarray(zt["retained__mass_matrix_inv"], float)[:, -1, :]  # fixed after warmup; last retained draw
    eps_n = np.asarray(zt["retained__step_size"], float)[:, -1]
    ret_step_o = np.concatenate([np.asarray(c["telemetry_retained"]["step_size"], float) for c in ch])
    r["owalnuts_retained_step_constant_per_chain"] = all(
        len(set(c["telemetry_retained"]["step_size"])) == 1 for c in ch)
    r["nutpie_retained_step_constant_per_chain"] = bool(np.all(np.ptp(np.asarray(zt["retained__step_size"], float), axis=1) == 0))

    def eff(eps, minv):  # (chains,), (chains, dim) -> ln e: mean over chains of the median over coordinates
        le = np.log(eps)[:, None] + 0.5 * np.log(minv) - np.log(sig)[None, :]
        return float(np.mean(np.median(le, axis=1)))

    def spread(minv):
        return float(np.mean(np.std(np.log(minv) - 2 * np.log(sig)[None, :], axis=1)))

    le_o, le_n = eff(eps_o, minv_o), eff(eps_n, minv_n)
    r["ln_e_owalnuts"], r["ln_e_nutpie"] = le_o, le_n
    r["B1"] = le_n - le_o
    r["B2"] = B_tel - r["B4"] - r["B1"]
    r["S_owalnuts"], r["S_nutpie"] = spread(minv_o), spread(minv_n)
    r["S_diff"] = r["S_owalnuts"] - r["S_nutpie"]
    # level of the metric relative to the posterior scale (absorbed by the step; reported)
    r["median_ln_minv_over_sigma2_owalnuts"] = float(np.median(np.log(minv_o) - 2 * np.log(sig)[None, :]))
    r["median_ln_minv_over_sigma2_nutpie"] = float(np.median(np.log(minv_n) - 2 * np.log(sig)[None, :]))
    r["raw_step_owalnuts"] = [float(x) for x in eps_o]
    r["raw_step_nutpie"] = [float(x) for x in eps_n]
    r["retained_step_owalnuts_median"] = float(np.median(ret_step_o))
    # descriptive orbit statistics
    r["owalnuts"] = {"grad_per_draw": float(te.mean()), "leaves_attempted_per_draw": float(la.mean()),
                     "leaves_built_per_draw": float(lb.mean()), "orbit_states_per_draw": float(ost.mean()),
                     "unmerged_built_fraction": float(1 - (ost - 1).sum() / lb.sum()) if lb.sum() else None,
                     "depth_hist": np.bincount(od.astype(int), minlength=11).tolist(),
                     "refined_transition_fraction": float(np.mean(lvl > 0)),
                     "refinement_attempts_per_draw": float(ra.mean()),
                     "reverse_coarser_rejections_per_draw": float(rcr.mean()),
                     "distance_per_draw_ln": float(math.log(la.mean()) + le_o)}
    r["nutpie"] = {"grad_per_draw": float(nsteps.mean()), "depth_hist": np.bincount(ndepth.astype(int).ravel(), minlength=11).tolist(),
                   "n_steps_median": float(np.median(nsteps)),
                   "mean_tree_accept": float(np.mean(zt["retained__mean_tree_accept"])) if "retained__mean_tree_accept" in zt else None,
                   "distance_per_draw_ln": float(math.log(nsteps.mean()) + le_n)}
    return r


def part3(p1: dict) -> dict:
    cells = {m: {str(s): telemetry_cell(m, s) for s in TEL["seeds"]} for m in TEL["models"]}
    comps = ["A", "C", "B4", "B1", "B2"]
    per = {}
    for m in TEL["models"]:
        u = [c for c in cells[m].values() if c.get("usable")]
        e = {"usable_seeds": len(u)}
        for k in comps + ["G", "B", "B_telemetry", "S_owalnuts", "S_nutpie", "S_diff", "ln_e_owalnuts", "ln_e_nutpie"]:
            e[k] = mean(c[k] for c in u)
        per[m] = e
    carrying = TEL["carrying_models"]
    thr = math.log(A["component_threshold_ratio"])
    hyp = {}
    for h, comp in (("H1_step", "B1"), ("H2_distance_per_draw", "B2"), ("H4_refinement_spend", "B4"), ("H5_ess_per_draw", "A")):
        votes = {m: per[m][comp] >= thr for m in carrying}
        hyp[h] = {"component": comp, "per_model": {m: per[m][comp] for m in carrying}, "votes": votes,
                  "supported": sum(votes.values()) >= A["min_models_supporting"], "criterion": f"{comp} >= ln {A['component_threshold_ratio']} on >= {A['min_models_supporting']} of 3"}
    votes = {m: per[m]["S_diff"] >= A["H3_spread_threshold"] for m in carrying}
    hyp["H3_metric_match"] = {"component": "S_owalnuts - S_nutpie", "per_model": {m: per[m]["S_diff"] for m in carrying},
                              "votes": votes, "supported": sum(votes.values()) >= A["min_models_supporting"],
                              "criterion": f"S_o - S_n >= {A['H3_spread_threshold']} on >= {A['min_models_supporting']} of 3"}
    ranking = sorted(({"component": k, "mean_over_carrying": mean(per[m][k] for m in carrying),
                       "per_model": {m: per[m][k] for m in carrying}} for k in comps),
                     key=lambda x: x["mean_over_carrying"], reverse=True)
    ident = {arm: sum(c[f"identical_to_prior_{arm}"] for mm in cells.values() for c in mm.values()) for arm in ("owalnuts", "nutpie")}
    return {"cells": cells, "per_model": per, "hypotheses": hyp, "ranking": ranking, "identical_to_prior": ident,
            "cells_total": sum(len(v) for v in cells.values()), "P2_first_ranked_predicted": STUDY["predictions"]["P2"]["first"],
            "P2_held": ranking[0]["component"] == STUDY["predictions"]["P2"]["first"]}


# --------------------------------------------------------------------------- report


def f(x, fmt=".3f"):
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)


def main() -> None:
    p1 = part1()
    p3 = part3(p1)
    summary = {"schema": "nutpie-gap-decomposition-v1-summary", "ledger_id": STUDY["ledger_id"], "part1": p1, "part3": p3,
               "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
               "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    OWN.mkdir(parents=True, exist_ok=True)
    (OWN / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=bool) + "\n", encoding="utf-8")
    L = ["# WP80 nutpie gap decomposition — results", "",
         "## Part 1: per-model split over 18 seeds (cells on disk)", "",
         "Logs are nutpie over oWALNUTS (positive = nutpie ahead); mean over paired ok seeds. G = A + B + C exactly.", "",
         f"Mean over the {len(p1['entering'])} entering models: G {f(p1['mean_over_models']['G'])} (lead x{f(p1['lead_mean_of_logs'])}; "
         f"from WP76's per-model (c): x{f(p1['lead_from_c_geomean'])}), A {f(p1['mean_over_models']['A'])}, "
         f"B {f(p1['mean_over_models']['B'])}, C {f(p1['mean_over_models']['C'])}. "
         f"P1 (top three = {', '.join(p1['P1_top3_predicted'])}): held = {p1['P1_held']}; top-three share of sum G {f(p1['top3_share_of_sum_G'])}.", "",
         "| rank | model | seeds | (c) o/n | G | A ESS/draw | B sampling grad/draw | C warmup | share of sum G | grad/draw o / n | B4 (cell, built) |",
         "|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|"]
    for i, m in enumerate(p1["ranked_by_G"], 1):
        e = p1["per_model"][m]
        L.append(f"| {i} | {m} | {e['paired_ok_seeds']} | {f(e['c_ratio_o_over_n'])} | {f(e['G'])} | {f(e['A'])} | {f(e['B'])} | {f(e['C'])} | "
                 f"{f(e['share_of_sum_G'])} | {f(e['grad_per_draw_o'], '.1f')} / {f(e['grad_per_draw_n'], '.1f')} | {f(e['B4_cell_built'])} |")
    for m in MODELS:
        if m not in p1["entering"]:
            L.append(f"| — | {m} (excluded: {p1['per_model'][m]['paired_ok_seeds']} paired ok seeds) | | | | | | | | | |")
    L += ["", "## Part 3: telemetry (seeds 720701-720703)", "",
          f"Same-seed identity with WP72 / WP76 cells: oWALNUTS {p3['identical_to_prior']['owalnuts']}/{p3['cells_total']}, "
          f"nutpie {p3['identical_to_prior']['nutpie']}/{p3['cells_total']}.", "",
          "| model | seeds | G | A | C | B | B4 refinement | B1 step | B2 distance | ln e o / n | S o / n |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    for m, e in p3["per_model"].items():
        L.append(f"| {m} | {e['usable_seeds']} | {f(e['G'])} | {f(e['A'])} | {f(e['C'])} | {f(e['B'])} | {f(e['B4'])} | {f(e['B1'])} | {f(e['B2'])} | "
                 f"{f(e['ln_e_owalnuts'])} / {f(e['ln_e_nutpie'])} | {f(e['S_owalnuts'])} / {f(e['S_nutpie'])} |")
    L += ["", "| hypothesis | criterion | per carrying model | supported |", "|---|---|---|---|"]
    for h, v in p3["hypotheses"].items():
        L.append(f"| {h} | {v['criterion']} | {', '.join(f'{m.split(chr(45))[-1]} {f(x)}' for m, x in v['per_model'].items())} | {v['supported']} |")
    L += ["", "| rank | component | mean over carrying models |", "|---:|---|---:|"]
    for i, r in enumerate(p3["ranking"], 1):
        L.append(f"| {i} | {r['component']} | {f(r['mean_over_carrying'])} |")
    L += ["", f"P2 (first-ranked = {p3['P2_first_ranked_predicted']}): held = {p3['P2_held']}", "",
          "## Orbit telemetry per cell", "", "| model | seed | o grad/draw | o leaves att/built/orbit | o depth mode | o refined frac | n grad/draw | n depth mode | n accept | step o / n (raw) |",
          "|---|---:|---:|---|---:|---:|---:|---:|---:|---|"]
    for m, cs in p3["cells"].items():
        for s, c in cs.items():
            if not c.get("usable"):
                L.append(f"| {m} | {s} | not usable ({c['owalnuts_status']}/{c['nutpie_status']}) | | | | | | | |")
                continue
            o, n = c["owalnuts"], c["nutpie"]
            L.append(f"| {m} | {s} | {f(o['grad_per_draw'], '.1f')} | {f(o['leaves_attempted_per_draw'], '.1f')}/{f(o['leaves_built_per_draw'], '.1f')}/{f(o['orbit_states_per_draw'], '.1f')} | "
                     f"{int(np.argmax(o['depth_hist']))} | {f(o['refined_transition_fraction'])} | {f(n['grad_per_draw'], '.1f')} | {int(np.argmax(n['depth_hist']))} | "
                     f"{f(n['mean_tree_accept'])} | {f(statistics.median(c['raw_step_owalnuts']), '.4f')} / {f(statistics.median(c['raw_step_nutpie']), '.4f')} |")
    (OWN / "results-table.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
