#!/usr/bin/env python3
"""WP81 analysis: installed diagonal metric vs posterior variance, and the two research regularisations.

    python analyze_shrinkage.py      # writes artifacts/summary.json and artifacts/results-table.md

Part 1 (descriptive): per cell and coordinate, ratio_i = median over chains of the installed inverse mass
(oWALNUTS 1 / mass_diagonal; nutpie mass_matrix_inv at the last retained draw) over the variance of the
cell's own retained unconstrained draws (pooled over chains), and over the posteriordb reference variance on
the unconstrained scale where it exists. Per model: per coordinate the median over seeds.
Part 2 (candidates): the frozen rule of protocol.json ("rule") for lowanchor and coordcap against the default
on the same seeds. All constants are in protocol.json.
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
R = STUDY["rule"]
D = STUDY["descriptive"]
MODELS = STUDY["models"]
SEEDS = STUDY["seeds"]
ART = HERE / "artifacts"
CANDIDATES = ["owalnuts-lowanchor", "owalnuts-coordcap"]
BAND = D["band"]


def short(m: str) -> str:
    return m.replace("-", "__")


def jload(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


_CELLS: dict = {}


def cell(m, a, s):
    """Cached read of one cell (WP81 amendment A-1: performance only)."""
    k = (m, a, s)
    if k not in _CELLS:
        _CELLS[k] = jload(ART / "cells" / f"{short(m)}-{a}-{s}.json")
    return _CELLS[k]


def ok(c, key="min_bulk_ess_per_gradient") -> bool:
    return bool(c) and c.get("status") == "ok" and c.get(key) is not None and math.isfinite(c[key]) and c[key] > 0


def geomean(xs) -> float:
    xs = [x for x in xs if x is not None and math.isfinite(x) and x > 0]
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs))) if xs else float("nan")


def f(x, fmt=".3f"):
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)


# --------------------------------------------------------------------------- part 1


def installed(m, a, s):
    """(inverse mass (chains, dim), steps (chains,), unconstrained draws (chains, draws, dim)) or None."""
    if a == "nutpie":
        p = ART / "telemetry" / f"{short(m)}-nutpie-{s}.npz"
        if not p.exists():
            return None
        z = np.load(p)
        return np.asarray(z["mass_matrix_inv"], float), np.asarray(z["step_size"], float), np.asarray(z["unconstrained"], float)
    p = ART / "telemetry" / f"{short(m)}-{a}-{s}.json.gz"
    dp = ART / "draws" / f"{short(m)}-{a}-{s}.npz"
    if not (p.exists() and dp.exists()):
        return None
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        t = json.load(fh)
    minv = 1.0 / np.asarray([c["mass_diagonal"] for c in t["chains"]], float)
    steps = np.asarray([c["final_step_size"] for c in t["chains"]], float)
    return minv, steps, np.asarray(np.load(dp)["unconstrained"], float)


def part1(refvar: dict) -> dict:
    out = {}
    for m in MODELS:
        e = {}
        rv = refvar.get(m, {})
        rvar = np.asarray(rv["variance"], float) if rv.get("status") == "ok" else None
        for a in ["owalnuts", "nutpie"] + CANDIDATES:
            per_seed, per_seed_ref, steps = [], [], []
            for s in SEEDS:
                c = cell(m, a, s)
                got = installed(m, a, s) if c and c.get("status") == "ok" else None
                if got is None:
                    continue
                minv, st, unc = got
                var = unc.reshape(-1, unc.shape[-1]).var(axis=0, ddof=1)
                with np.errstate(all="ignore"):
                    per_seed.append(np.median(minv / var[None, :], axis=0))
                    if rvar is not None and rvar.shape == var.shape:
                        per_seed_ref.append(np.median(minv / rvar[None, :], axis=0))
                steps.append(float(np.median(st)))
            if not per_seed:
                e[a] = {"seeds": 0}
                continue
            r = np.median(np.asarray(per_seed), axis=0)
            x = {"seeds": len(per_seed), "dimension": int(r.size), "ratio_per_coordinate": r.tolist(),
                 "ratio_min": float(np.nanmin(r)), "ratio_max": float(np.nanmax(r)),
                 "outside_band": int(np.sum((r < BAND[0]) | (r > BAND[1]))),
                 "log_ratio_sd": float(np.nanstd(np.log(r))), "step_median": float(statistics.median(steps))}
            if per_seed_ref:
                rr = np.median(np.asarray(per_seed_ref), axis=0)
                x.update({"ref_ratio_per_coordinate": rr.tolist(), "ref_ratio_min": float(np.nanmin(rr)),
                          "ref_ratio_max": float(np.nanmax(rr)), "ref_outside_band": int(np.sum((rr < BAND[0]) | (rr > BAND[1])))})
            e[a] = x
        if e["owalnuts"].get("seeds") and e["nutpie"].get("seeds"):
            e["step_ratio_nutpie_over_owalnuts"] = e["nutpie"]["step_median"] / e["owalnuts"]["step_median"]
        out[m] = e
    gap = D["step_gap_models"]
    d1 = {m: {"owalnuts_outside": out[m]["owalnuts"].get("outside_band"), "nutpie_outside": out[m]["nutpie"].get("outside_band")} for m in gap}
    for m in gap:
        d1[m]["held"] = bool((d1[m]["owalnuts_outside"] or 0) >= 1 and d1[m]["nutpie_outside"] == 0)
    d1b = {}
    for m, want in STUDY["predictions"]["D1b"]["owalnuts_outside_at_least"].items():
        d1b[m] = {"value": out[m]["owalnuts"].get("outside_band"), "held": (out[m]["owalnuts"].get("outside_band") or 0) >= want}
    for m in STUDY["predictions"]["D1b"]["owalnuts_all_inside"]:
        d1b[m] = {"value": out[m]["owalnuts"].get("outside_band"), "held": out[m]["owalnuts"].get("outside_band") == 0}
    return {"per_model": out, "D1": {"per_model": d1, "held": all(v["held"] for v in d1.values())},
            "D1b": {"per_model": d1b, "held": all(v["held"] for v in d1b.values())}}


# --------------------------------------------------------------------------- part 2


def ratios_c(seeds, cand, key="min_bulk_ess_per_gradient") -> dict:
    need = math.ceil(R["min_ok_fraction"] * len(seeds))
    out = {}
    for m in MODELS:
        r = [cell(m, cand, s)[key] / cell(m, "owalnuts", s)[key] for s in seeds
             if ok(cell(m, cand, s), key) and ok(cell(m, "owalnuts", s), key)]
        if len(r) >= need:
            out[m] = statistics.median(r)
    return out


def funnel(arm) -> dict:
    est, zs, div, status = [], [], [], []
    for s in STUDY["funnel"]["seeds"]:
        c = jload(ART / "funnel" / f"funnel-{arm}-{s}.json")
        if not c or "tail_mass" not in c:
            status.append(f"{s}: {c.get('status') if c else 'missing'}")
            continue
        est.append(c["tail_mass"]["estimate"])
        zs.append(c["tail_mass"]["z"])
        div.append(sum(ch["divergences"] for ch in c["chains_data"]))
    exact = STUDY["funnel"]["exact"]
    mean = float(np.mean(est)) if est else float("nan")
    se = float(np.std(est, ddof=1) / math.sqrt(len(est))) if len(est) > 1 else float("nan")
    return {"seeds": len(est), "mean": mean, "se": se, "deviation_in_se": (mean - exact) / se if se else float("nan"),
            "held": bool(len(est) == len(STUDY["funnel"]["seeds"]) and abs(mean - exact) <= R["funnel_se_multiple"] * se),
            "z_per_seed": zs, "divergences_per_seed": div, "non_ok": status}


def part2() -> dict:
    out = {}
    base_pass = sum(bool(cell(m, "owalnuts", s) and cell(m, "owalnuts", s).get("passed")) for m in MODELS for s in SEEDS)
    fd = funnel("owalnuts")
    fp = (HERE / "artifacts" / "fingerprint-test.txt")
    fingerprint = fp.exists() and "test result: ok" in fp.read_text(encoding="utf-8") and "FAILED" not in fp.read_text(encoding="utf-8")
    for cand in CANDIDATES:
        r = ratios_c(SEEDS, cand)
        g = geomean(r.values())
        lomo = {m: geomean(v for mm, v in r.items() if mm != m) for m in r}
        rng = np.random.default_rng(R["bootstrap"]["rng_seed"])
        idx = rng.integers(0, len(SEEDS), size=(R["bootstrap"]["resamples"], len(SEEDS)))
        boot = np.asarray([geomean(ratios_c([SEEDS[i] for i in row], cand).values()) for row in idx])
        boot = boot[np.isfinite(boot)]
        passed = sum(bool(cell(m, cand, s) and cell(m, cand, s).get("passed")) for m in MODELS for s in SEEDS)
        new_div = [f"{m}/{s}" for m in MODELS for s in SEEDS
                   if cell(m, cand, s) and cell(m, "owalnuts", s) and (cell(m, cand, s).get("divergences") or 0) > 0
                   and (cell(m, "owalnuts", s).get("divergences") or 0) == 0]
        identical = [f"{m}/{s}" for m in MODELS for s in SEEDS
                     if cell(m, cand, s) and cell(m, "owalnuts", s)
                     and all(cell(m, cand, s).get(k) == cell(m, "owalnuts", s).get(k) for k in ("status", "gradients_total", "min_bulk_ess"))]
        fu = funnel(cand)
        crit = {
            "R1_gates_not_lower": {"value": f"{passed} vs default {base_pass}", "held": passed >= base_pass},
            "R2_headline_geomean_ge_1.10": {"value": g, "held": g >= R["headline_min"]},
            "R3_per_model_median_ge_1.05": {"value": statistics.median(r.values()) if r else float("nan"),
                                            "held": bool(r) and statistics.median(r.values()) >= R["per_model_median_min"]},
            "R4_lomo_min_ge_1.00": {"value": min(lomo.values()) if lomo else float("nan"),
                                    "held": bool(lomo) and min(lomo.values()) >= R["lomo_min"]},
            "R5_no_new_divergences": {"value": new_div, "held": not new_div},
            "R6_funnel_mean_within_1se": {"value": fu, "held": fu["held"]},
            "R7_fingerprint_flags_off": {"value": fingerprint, "held": fingerprint},
        }
        out[cand] = {"per_model": r, "geomean": g, "interval": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))] if boot.size else None,
                     "models": len(r), "lomo": lomo, "passed": passed, "identical_cells": len(identical), "identical_list": identical,
                     "criteria": crit, "meets_rule": all(v["held"] for v in crit.values())}
    return {"default_passed": base_pass, "default_funnel": fd, "candidates": out}


def main() -> None:
    refvar = jload(ART / "reference-unconstrained-variance.json") or {}
    p1, p2 = part1(refvar), part2()
    pr = STUDY["predictions"]
    preds = {
        "D1": p1["D1"]["held"], "D1b": p1["D1b"]["held"],
        "C1_both_fail_R2": all(not p2["candidates"][c]["criteria"]["R2_headline_geomean_ge_1.10"]["held"] for c in CANDIDATES),
        "C2_both_fail_R3": all(not p2["candidates"][c]["criteria"]["R3_per_model_median_ge_1.05"]["held"] for c in CANDIDATES),
        "C3_sblrc_ratio_ge_1.5_both": all((p2["candidates"][c]["per_model"].get("sblrc-blr") or 0) >= 1.5 for c in CANDIDATES),
        "C4_identical_cells_ge": {c: {"value": p2["candidates"][c]["identical_cells"], "held": p2["candidates"][c]["identical_cells"] >= pr["C4"]["at_least"]} for c in CANDIDATES},
        "C5_R1_R5_R6_hold_both": all(p2["candidates"][c]["criteria"][k]["held"] for c in CANDIDATES for k in ("R1_gates_not_lower", "R5_no_new_divergences", "R6_funnel_mean_within_1se")),
    }
    summary = {"schema": "diagonal-metric-shrinkage-v1-summary", "ledger_id": STUDY["ledger_id"], "part1": p1, "part2": p2,
               "predictions": preds, "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
               "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    L = ["# WP81 diagonal metric shrinkage — results", "", "## Part 1: installed inverse mass / posterior variance", "",
         f"Per coordinate: median over chains, then over {len(SEEDS)} seeds; band {BAND}. 'own' = the cell's retained draws; 'ref' = posteriordb reference (unconstrained).", "",
         "| model | dim | oWALNUTS own min..max (outside) | oWALNUTS ref min..max | nutpie own min..max (outside) | nutpie ref min..max | step o / n | lowanchor own max | coordcap own max |",
         "|---|---:|---|---|---|---|---|---:|---:|"]
    for m in MODELS:
        e = p1["per_model"][m]
        o, n = e["owalnuts"], e["nutpie"]

        def rng(x, k=""):
            return f"{f(x.get(k + 'ratio_min'), '.2f')}..{f(x.get(k + 'ratio_max'), '.2f')}" if x.get("seeds") and x.get(k + "ratio_min") is not None else "—"
        L.append(f"| {m} | {o.get('dimension', '—')} | {rng(o)} ({o.get('outside_band', '—')}) | {rng(o, 'ref_')} | {rng(n)} ({n.get('outside_band', '—')}) | {rng(n, 'ref_')} | "
                 f"{f(o.get('step_median'), '.4f')} / {f(n.get('step_median'), '.4f')} | {f(e['owalnuts-lowanchor'].get('ratio_max'), '.2f')} | {f(e['owalnuts-coordcap'].get('ratio_max'), '.2f')} |")
    L += ["", f"D1 (coordinator: step-gap models have oWALNUTS coordinates outside the band, nutpie none): {p1['D1']['held']} — "
          + ", ".join(f"{m.split('-')[-1]} {v['owalnuts_outside']}/{v['nutpie_outside']} {v['held']}" for m, v in p1["D1"]["per_model"].items()),
          f"D1b (this study): {p1['D1b']['held']} — " + ", ".join(f"{m.split('-')[-1]} {v['value']} {v['held']}" for m, v in p1["D1b"]["per_model"].items()), "",
          "## Part 2: candidates against the frozen rule", "",
          f"Default: {p2['default_passed']}/{len(MODELS) * len(SEEDS)} cells pass; funnel mean {f(p2['default_funnel']['mean'], '.4f')} ± {f(p2['default_funnel']['se'], '.4f')} "
          f"({f(p2['default_funnel']['deviation_in_se'], '.2f')} s.e.)", "",
          "| criterion | " + " | ".join(CANDIDATES) + " |", "|---|---|---|"]
    for k in p2["candidates"][CANDIDATES[0]]["criteria"]:
        cells = []
        for c in CANDIDATES:
            v = p2["candidates"][c]["criteria"][k]
            val = v["value"]
            if isinstance(val, dict):
                val = f"mean {f(val['mean'], '.4f')} ± {f(val['se'], '.4f')} ({f(val['deviation_in_se'], '.2f')} s.e.)"
            elif isinstance(val, float):
                val = f(val)
            elif isinstance(val, list):
                val = ", ".join(val) or "none"
            cells.append(f"{val} — {'held' if v['held'] else 'FAILED'}")
        L.append(f"| {k} | " + " | ".join(cells) + " |")
    L.append("| meets rule | " + " | ".join(str(p2["candidates"][c]["meets_rule"]) for c in CANDIDATES) + " |")
    L.append("| headline interval | " + " | ".join(f"[{f(p2['candidates'][c]['interval'][0])}, {f(p2['candidates'][c]['interval'][1])}]" if p2["candidates"][c]["interval"] else "—" for c in CANDIDATES) + " |")
    L.append("| cells identical to default | " + " | ".join(f"{p2['candidates'][c]['identical_cells']}/{len(MODELS) * len(SEEDS)}" for c in CANDIDATES) + " |")
    L += ["", "| model | " + " | ".join(CANDIDATES) + " |", "|---|---:|---:|"]
    for m in MODELS:
        L.append(f"| {m} | " + " | ".join(f(p2["candidates"][c]["per_model"].get(m)) for c in CANDIDATES) + " |")
    L += ["", "## Predictions", "", "| prediction | held |", "|---|---|"] + [f"| {k} | {v} |" for k, v in preds.items()]
    (ART / "results-table.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
