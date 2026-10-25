"""Phase 1b (amendments A2/A3) and phase 2 (fix vs baseline) analysis for python_callpath_v1."""
from __future__ import annotations

import json
import math
from collections import defaultdict

from analyze_callpath import ART, PROTOCOL, SEEDS, TARGETS, fmt, gm, load, ok


def _agg(cells, build, target, arm, t):
    good = [cells[(build, target, arm, t, s)] for s in SEEDS if ok(cells.get((build, target, arm, t, s)))]
    wpc = sorted(r["wall_per_call_us"] for r in good)
    return {"n_ok": len(good), "ess_per_second_gm": gm([r["ess_per_second"] for r in good]),
            "wall_per_call_us_median": wpc[len(wpc) // 2] if wpc else None,
            "ess_per_call_gm": gm([r["ess_per_call"] for r in good]),
            "max_rhat": max((r["max_rhat"] for r in good), default=None),
            "min_bulk": min((r["min_bulk_ess"] for r in good), default=None),
            "min_tail": min((r["min_tail_ess"] for r in good), default=None),
            "divergences": sum(r["health"]["divergences"] for r in good)}


def phase1b(out: dict, md: list[str]) -> None:
    if not (ART / "phase1b" / "cells").exists():
        return
    cells, _ = load("phase1b")
    p1, _ = load("phase1")
    b = "baseline"
    md.append("\n## Phase 1b (amendments A2/A3: `cfunc-guarded`, primed targets; run after phase 1; wall CONTENDED)\n")
    md.append("| target | arm | threads | ok | ESS/s (gm) | wall/call µs | ESS/call (gm) | max R-hat | min bulk | min tail | div |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|")
    agg = {}
    for target in TARGETS:
        for arm in PROTOCOL["phases"]["phase1b"]["arms"]:
            for t in PROTOCOL["threads"]:
                a = _agg(cells, b, target, arm, t)
                agg[f"{target}|{arm}|t{t}"] = a
                md.append(f"| {target} | {arm} | {t} | {a['n_ok']}/3 | {fmt(a['ess_per_second_gm'])} | "
                          f"{fmt(a['wall_per_call_us_median'])} | {fmt(a['ess_per_call_gm'], 4)} | {fmt(a['max_rhat'], 4)} | "
                          f"{fmt(a['min_bulk'])} | {fmt(a['min_tail'])} | {a['divergences']} |")
    out["phase1b_cells"] = agg
    bit = defaultdict(list)
    for target in TARGETS:
        for s in SEEDS:
            for t in PROTOCOL["threads"]:
                g = cells.get((b, target, "cfunc-guarded", t, s))
                for other, src in (("py-njit(phase1)", p1.get((b, target, "py-njit", t, s))),
                                   ("cfunc(phase1)", p1.get((b, target, "cfunc", t, s)))):
                    bit[f"cfunc-guarded=={other}|{target}"].append(
                        (g["samples_sha256"] == src["samples_sha256"]) if ok(g) and ok(src) else None)
                for arm in ("py-njit", "cfunc"):
                    a, c = p1.get((b, target, arm, t, s)), cells.get((b, target, arm, t, s))
                    bit[f"{arm} phase1==phase1b|{target}"].append(
                        (a["samples_sha256"] == c["samples_sha256"]) if ok(a) and ok(c) else None)
            g1, g4 = cells.get((b, target, "cfunc-guarded", 1, s)), cells.get((b, target, "cfunc-guarded", 4, s))
            bit[f"t1==t4|cfunc-guarded|{target}"].append(
                (g1["samples_sha256"] == g4["samples_sha256"]) if ok(g1) and ok(g4) else None)
    out["phase1b_bit_identity"] = dict(bit)
    md.append("\n| comparison | identical / compared |\n|---|---|")
    for k, v in bit.items():
        md.append(f"| {k} | {sum(1 for x in v if x)}/{sum(1 for x in v if x is not None)} |")
    rs = {}
    for target in TARGETS:
        for t in PROTOCOL["threads"]:
            vals, calls = [], []
            for s in SEEDS:
                g, n = cells.get((b, target, "cfunc-guarded", t, s)), p1.get((b, target, "nutpie", t, s))
                if ok(g) and ok(n):
                    vals.append(g["ess_per_second"] / n["ess_per_second"])
                    calls.append(g["ess_per_call"] / n["ess_per_call"])
            rs[f"cfunc-guarded / nutpie (phase 1) ESS/s|{target}|t{t}"] = gm(vals)
            rs[f"cfunc-guarded / nutpie ESS per gradient|{target}|t{t}"] = gm(calls)
        for arm in ("cfunc-guarded", "py-njit", "cfunc"):
            a1 = agg[f"{target}|{arm}|t1"]["ess_per_second_gm"]
            a4 = agg[f"{target}|{arm}|t4"]["ess_per_second_gm"]
            rs[f"{arm} t4/t1 ESS/s (primed)|{target}"] = a4 / a1 if a1 and a4 else None
    out["phase1b_ratios"] = rs
    md.append("\n| ratio (geomean over seeds) | value |\n|---|---|")
    for k, v in rs.items():
        md.append(f"| {k} | {fmt(v, 3)} |")


def phase2(out: dict, md: list[str]) -> None:
    if not (ART / "phase2" / "cells").exists():
        return
    cells, micro = load("phase2")
    ph = PROTOCOL["phases"]["phase2"]
    arms = ph["arms"]
    res = {}
    for target in TARGETS:
        for arm in arms:
            for t in PROTOCOL["threads"]:
                rs, ident, notes = [], [], []
                for s in SEEDS:
                    a, f = cells.get(("baseline", target, arm, t, s)), cells.get(("fix", target, arm, t, s))
                    if ok(a) and ok(f):
                        rs.append(f["ess_per_second"] / a["ess_per_second"])
                        ident.append(a["samples_sha256"] == f["samples_sha256"])
                    elif ok(f) and a is not None and a.get("status") == "process_error":
                        rs.append(float("inf"))
                        ident.append(None)
                        notes.append(f"seed {s}: baseline {a.get('error', '')[:20]}, fix ok")
                    else:
                        ident.append(None)
                        notes.append(f"seed {s}: baseline {a.get('status') if a else 'missing'}, "
                                     f"fix {f.get('status') if f else 'missing'}")
                fin = [x for x in rs if math.isfinite(x)]
                fixed = _agg(cells, "fix", target, arm, t)
                base = _agg(cells, "baseline", target, arm, t)
                res[f"{target}|{arm}|t{t}"] = {
                    "paired_ratio_gm": float("inf") if any(math.isinf(x) for x in rs) else gm(fin),
                    "ratios": rs, "bit_identical": ident, "notes": notes, "fix": fixed, "baseline": base}
    out["phase2_paired"] = res

    def ratios(keys):
        return {k: res[k]["paired_ratio_gm"] for k in keys if res[k]["paired_ratio_gm"] is not None}

    touched = ph["touched_arms"]
    f3 = [f"{t}|jax|t1" for t in TARGETS]
    f6 = [f"{t}|{a}|t4" for t in TARGETS for a in ("py-numpy", "py-njit", "torch", "pymc", "pymc-numba")]
    t1 = [f"{t}|{a}|t1" for t in TARGETS for a in ("py-numpy", "py-njit", "torch", "pymc", "pymc-numba")]
    joint = [f"{t}|jax|t4" for t in TARGETS]
    ctl = [f"{t}|cfunc-guarded|t{th}" for t in TARGETS for th in PROTOCOL["threads"]]
    all_touched = [k for k in res if k.split("|")[1] in touched]
    ident_all = [x for k in all_touched + ctl for x in res[k]["bit_identical"] if x is not None]
    v_all = ratios(all_touched)
    rule = {"i_bit_identical": bool(ident_all) and all(ident_all),
            "identical_compared": [sum(ident_all), len(ident_all)],
            "ii_ge_1.3_somewhere": any(v >= 1.3 for v in v_all.values()),
            "iii_none_below_0.9": all(v >= 0.9 for v in v_all.values()),
            "below_0.9": {k: v for k, v in v_all.items() if v < 0.9}}
    rule["merge"] = bool(rule["i_bit_identical"] and rule["ii_ge_1.3_somewhere"] and rule["iii_none_below_0.9"])
    dec = {"rule": rule, "F3_jax_t1": ratios(f3), "F6_t4": ratios(f6), "t1_no_regression": ratios(t1),
           "jax_t4_joint": ratios(joint), "control": ratios(ctl)}
    for name, keys in (("F3", f3), ("F6", f6)):
        v = list(ratios(keys).values())
        own_ident = [x for k in keys for x in res[k]["bit_identical"] if x is not None]
        dec[f"{name}_passes_own_cells"] = bool(all(own_ident) and any(x >= 1.3 for x in v) and all(x >= 0.9 for x in v))
    out["phase2_decision"] = dec

    mt = {}
    for k, r in micro.items():
        if ok(r):
            mt["|".join(k)] = {c: v["median_us"] for c, v in r["components"].items()}
    out["phase2_micro_median_us"] = mt
    md.append("\n## Phase 2 — fix vs baseline (paired, builds interleaved, same seeds, primed; wall CONTENDED)\n")
    md.append("| target | arm | threads | fix/baseline ESS/s (gm) | per seed | bit-identical | wall/call µs base → fix | ESS/s base → fix (gm) | fix ok | notes |")
    md.append("|---|---|---|---|---|---|---|---|---|---|")
    for k, v in res.items():
        target, arm, t = k.split("|")
        r = v["paired_ratio_gm"]
        md.append(f"| {target} | {arm} | {t[1:]} | {'inf (baseline timeout)' if r == float('inf') else fmt(r, 3)} | "
                  f"{', '.join('inf' if math.isinf(x) else f'{x:.2f}' for x in v['ratios'])} | "
                  f"{sum(1 for x in v['bit_identical'] if x)}/{sum(1 for x in v['bit_identical'] if x is not None)} | "
                  f"{fmt(v['baseline']['wall_per_call_us_median'])} → {fmt(v['fix']['wall_per_call_us_median'])} | "
                  f"{fmt(v['baseline']['ess_per_second_gm'])} → {fmt(v['fix']['ess_per_second_gm'])} | {v['fix']['n_ok']}/3 | "
                  f"{'; '.join(v['notes'])} |")
    md.append("\n### Phase 2 micro (median µs per call through the adapter)\n")
    md.append("| target | path | baseline | fix |\n|---|---|---|---|")
    for target in TARGETS:
        for path in arms:
            bm, fm = mt.get(f"baseline|{target}|{path}", {}), mt.get(f"fix|{target}|{path}", {})
            md.append(f"| {target} | {path} | {fmt(bm.get('adapter_call'))} | {fmt(fm.get('adapter_call'))} |")
    md.append("\n**Decision:**\n\n```json\n" + json.dumps(dec, indent=1, default=str) + "\n```")


def phase1c(out: dict, md: list[str]) -> None:
    """Amendment A5: cfunc-safe (error_model='numpy' + guard), primed."""
    if not (ART / "phase1c" / "cells").exists():
        return
    cells, micro = load("phase1c")
    p1, _ = load("phase1")
    p1b, _ = load("phase1b")
    b = "baseline"
    md.append("\n## Phase 1c (amendment A5: `cfunc-safe`, primed; run after phase 2; wall CONTENDED)\n")
    md.append("| target | threads | ok | ESS/s (gm) | wall/call µs | ESS/call (gm) | max R-hat | min bulk | min tail | div | vs nutpie ESS/s (phase 1) | vs nutpie ESS/gradient | vs py-njit primed ESS/s (phase 1b) |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    agg = {}
    for target in TARGETS:
        for t in PROTOCOL["threads"]:
            a = _agg(cells, b, target, "cfunc-safe", t)
            vn, vg, vj = [], [], []
            for s in SEEDS:
                c, n, j = cells.get((b, target, "cfunc-safe", t, s)), p1.get((b, target, "nutpie", t, s)), p1b.get((b, target, "py-njit", t, s))
                if ok(c) and ok(n):
                    vn.append(c["ess_per_second"] / n["ess_per_second"])
                    vg.append(c["ess_per_call"] / n["ess_per_call"])
                if ok(c) and ok(j):
                    vj.append(c["ess_per_second"] / j["ess_per_second"])
            a.update(vs_nutpie_ess_per_second=gm(vn), vs_nutpie_ess_per_gradient=gm(vg), vs_py_njit_primed=gm(vj))
            agg[f"{target}|t{t}"] = a
            md.append(f"| {target} | {t} | {a['n_ok']}/3 | {fmt(a['ess_per_second_gm'])} | {fmt(a['wall_per_call_us_median'])} | "
                      f"{fmt(a['ess_per_call_gm'], 4)} | {fmt(a['max_rhat'], 4)} | {fmt(a['min_bulk'])} | {fmt(a['min_tail'])} | "
                      f"{a['divergences']} | {fmt(a['vs_nutpie_ess_per_second'], 3)} | {fmt(a['vs_nutpie_ess_per_gradient'], 3)} | {fmt(a['vs_py_njit_primed'], 3)} |")
        a1, a4 = agg[f"{target}|t1"]["ess_per_second_gm"], agg[f"{target}|t4"]["ess_per_second_gm"]
        agg[f"{target}|t4/t1"] = a4 / a1 if a1 and a4 else None
    out["phase1c_cells"] = agg
    bit = defaultdict(list)
    for target in TARGETS:
        for s in SEEDS:
            for t in PROTOCOL["threads"]:
                c = cells.get((b, target, "cfunc-safe", t, s))
                for other, src in (("py-njit(phase1)", p1.get((b, target, "py-njit", t, s))),
                                   ("py-njit(phase1b)", p1b.get((b, target, "py-njit", t, s))),
                                   ("cfunc(phase1)", p1.get((b, target, "cfunc", t, s))),
                                   ("cfunc-guarded(phase1b)", p1b.get((b, target, "cfunc-guarded", t, s)))):
                    bit[f"cfunc-safe=={other}|{target}"].append(
                        (c["samples_sha256"] == src["samples_sha256"]) if ok(c) and ok(src) else None)
    out["phase1c_bit_identity"] = dict(bit)
    md.append("\n| comparison | identical / compared |\n|---|---|")
    for k, v in bit.items():
        md.append(f"| {k} | {sum(1 for x in v if x)}/{sum(1 for x in v if x is not None)} |")
    md.append("\n| target | cfunc-safe t4/t1 ESS/s |\n|---|---|")
    for target in TARGETS:
        md.append(f"| {target} | {fmt(agg[f'{target}|t4/t1'], 3)} |")
