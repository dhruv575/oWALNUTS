#!/usr/bin/env python3
"""WP86 analysis: artifacts/summary.json and artifacts/results-table.md from artifacts/procs/."""
from __future__ import annotations

import hashlib
import json
import statistics
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
ART = HERE / "artifacts"


def load():
    recs = {}
    for f in sorted((ART / "procs").rglob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        recs.setdefault(r["arm"], {}).setdefault(r["model"], []).append(r)
    for arm in recs.values():
        for m in arm.values():
            m.sort(key=lambda r: r["index"])
    return recs


def ok(r):
    return r.get("status") == "ok"


def d2(r):
    return ok(r) and r["identical_same_fn"] and r["gradient_probe"]["points_bit_different"] == 0


def per_model(rs):
    okr = [r for r in rs if ok(r)]
    out = {"processes": len(rs), "ok": len(okr),
           "statuses": sorted({r.get("status") for r in rs}),
           "d2_pass": {c: sum(1 for r in okr if r["cache"] == c and d2(r)) for c in ("cold", "warm")},
           "d2_of": {c: sum(1 for r in okr if r["cache"] == c) for c in ("cold", "warm")},
           "draws_identical_same_fn": {c: sum(1 for r in okr if r["cache"] == c and r["identical_same_fn"]) for c in ("cold", "warm")},
           "gradient_bit_different_processes": {c: sum(1 for r in okr if r["cache"] == c and r["gradient_probe"]["points_bit_different"]) for c in ("cold", "warm")},
           "gradient_points_bit_different_max": max((r["gradient_probe"]["points_bit_different"] for r in okr), default=None),
           "max_ulp_grad": max((r["gradient_probe"]["max_ulp_grad"] for r in okr if r["gradient_probe"]["max_ulp_grad"] is not None), default=None),
           "max_ulp_logp": max((r["gradient_probe"]["max_ulp_logp"] for r in okr if r["gradient_probe"]["max_ulp_logp"] is not None), default=None),
           "max_abs_diff_grad": max((r["gradient_probe"]["max_abs_diff_grad"] or 0 for r in okr), default=None),
           "within_1e-15_all": all(r["gradient_probe"]["within_1e-15_relative"] in (True, None) for r in okr),
           "gilfree_hashes": len({r["gilfree_t1"]["sha256"] for r in okr}),
           "gilfree_hashes_by_cache": {c: len({r["gilfree_t1"]["sha256"] for r in okr if r["cache"] == c}) for c in ("cold", "warm")},
           "same_fn_hashes": len({r["callable_same_fn_t1"]["sha256"] for r in okr}),
           "cfunc_grad_hashes": len({r["gradient_probe"]["cfunc_sha256"] for r in okr}),
           "fn_grad_hashes": len({r["gradient_probe"]["fn_sha256"] for r in okr}),
           "cfunc_asm_hashes_by_cache": {c: len({r["cfunc_ir"].get("asm_sha256") for r in okr if r["cache"] == c}) for c in ("cold", "warm")},
           "cfunc_llvm_chars_by_cache": {c: sorted({r["cfunc_ir"].get("llvm_chars") for r in okr if r["cache"] == c}) for c in ("cold", "warm")},
           "cfunc_vfmadd_by_cache": {c: sorted({r["cfunc_ir"].get("asm_vfmadd") for r in okr if r["cache"] == c}) for c in ("cold", "warm")},
           "inner_cache_hits_by_cache": {c: sorted({json.dumps(r["inner_dispatcher"].get("cache_hits")) for r in okr if r["cache"] == c}) for c in ("cold", "warm")},
           "gilfree_wall_per_call_us_median": statistics.median([r["gilfree_t1"]["wall_per_call_us"] for r in okr]) if okr else None}
    out["d1"] = out["ok"] == out["processes"] and out["gilfree_hashes"] == 1
    out["d2_all"] = out["ok"] == out["processes"] and sum(out["d2_pass"].values()) == out["processes"]
    t4 = [r for r in okr if "identical_t1_t4" in r]
    if t4:
        out["d3_pass"] = {c: sum(1 for r in t4 if r["cache"] == c and r["identical_t1_t4"]) for c in ("cold", "warm")}
        out["d3_of"] = {c: sum(1 for r in t4 if r["cache"] == c) for c in ("cold", "warm")}
    ctl = [r for r in okr if "identical_wp83_control" in r]
    if ctl:
        out["wp83_control_identical"] = {c: sum(1 for r in ctl if r["cache"] == c and r["identical_wp83_control"]) for c in ("cold", "warm")}
    return out


def main():
    recs = load()
    arms = {a: {m: per_model(rs) for m, rs in models.items()} for a, models in recs.items()}
    affected = P["models"]["affected"]
    A = arms.get("A", {})
    preds = {}
    preds["H1"] = all(A[m]["d2_pass"]["warm"] == A[m]["d2_of"]["warm"] for m in affected if m in A) and \
        all(A[m]["d2_all"] for m in P["models"]["unaffected"] if m in A) and \
        all((A[m]["max_ulp_grad"] or 0) <= 4 and (A[m]["max_ulp_grad"] or 0) >= 0 for m in A)
    preds["H2"] = all(A[m]["same_fn_hashes"] == 1 for m in A)
    preds["H3"] = all(arms.get("B", {}).get(m, {}).get("d1") and arms["B"][m]["d2_all"] for m in A)
    preds["H4"] = all(not all(arms.get(a, {}).get(m, {}).get("d2_all") for m in affected) for a in ("C", "D"))
    E = arms.get("E", {})
    preds["H5"] = all(E.get(m, {}).get("d1") for m in E) and all(sum(E[m]["d2_pass"].values()) == 0 for m in affected if m in E)
    T = arms.get("T", {})
    preds["H6"] = all(sum(T[m].get("d3_pass", {}).values()) == T[m]["ok"] for m in T) and \
        all(T[m]["d2_pass"]["warm"] == T[m]["d2_of"]["warm"] for m in T)
    qualifies = {a: all(arms.get(a, {}).get(m, {}).get("d1") and arms[a][m]["d2_all"] for m in A) and len(arms.get(a, {})) == len(A)
                 for a in ("B", "C", "D", "E")}
    warm_only = {m: {"d2_warm": f"{A[m]['d2_pass']['warm']}/{A[m]['d2_of']['warm']}",
                     "warm_hashes": A[m]["gilfree_hashes_by_cache"]["warm"]} for m in A}
    order = [a for a in ("C", "D", "B", "E") if qualifies[a]]
    summary = {"schema": "pymc-gil-free-determinism-v1-summary", "arms": arms, "predictions": preds,
               "fix_rule": {"qualifies": qualifies, "proposed": order[0] if order else None,
                            "cache_warming_descriptive": warm_only},
               "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
               "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    L = ["# WP86 results", "", f"Seed {P['seed']}; 4 chains x 1,000/1,000; pinned to cores 4-7, co-tenanted.", "",
         "| arm | model | ok | D2 cold | D2 warm | draws = same fn (cold/warm) | grad-diff processes (cold/warm) | max ulp grad / logp | gil_free hashes (all; cold/warm) | same-fn hashes | t1 = t4 (cold/warm) | = WP83 control (cold/warm) | cfunc asm variants (cold/warm) | vfmadd (cold/warm) | inner cache hits (cold/warm) | gf us/call |",
         "|---|---|---:|---:|---:|---|---|---|---|---:|---|---|---|---|---|---:|"]
    for a, models in arms.items():
        for m, s in models.items():
            d3 = f"{s['d3_pass']['cold']}/{s['d3_of']['cold']}, {s['d3_pass']['warm']}/{s['d3_of']['warm']}" if "d3_pass" in s else "—"
            w = s.get("wp83_control_identical")
            wtxt = f"{w['cold']}, {w['warm']}" if w else "—"
            L.append(f"| {a} | {m} | {s['ok']}/{s['processes']} | {s['d2_pass']['cold']}/{s['d2_of']['cold']} | {s['d2_pass']['warm']}/{s['d2_of']['warm']} | "
                     f"{s['draws_identical_same_fn']['cold']}, {s['draws_identical_same_fn']['warm']} | {s['gradient_bit_different_processes']['cold']}, {s['gradient_bit_different_processes']['warm']} | "
                     f"{s['max_ulp_grad']} / {s['max_ulp_logp']} | {s['gilfree_hashes']}; {s['gilfree_hashes_by_cache']['cold']}/{s['gilfree_hashes_by_cache']['warm']} | {s['same_fn_hashes']} | {d3} | {wtxt} | "
                     f"{s['cfunc_asm_hashes_by_cache']['cold']}/{s['cfunc_asm_hashes_by_cache']['warm']} | {s['cfunc_vfmadd_by_cache']['cold']} / {s['cfunc_vfmadd_by_cache']['warm']} | "
                     f"{s['inner_cache_hits_by_cache']['cold']} / {s['inner_cache_hits_by_cache']['warm']} | {s['gilfree_wall_per_call_us_median']:.2f} |"
                     if s["gilfree_wall_per_call_us_median"] is not None else f"| {a} | {m} | {s['ok']}/{s['processes']} | {s['statuses']} |")
    L += ["", "## Predictions", ""] + [f"- {k}: {v}" for k, v in preds.items()]
    L += ["", "## Fix rule", "", f"- qualifies: {qualifies}", f"- proposed: {summary['fix_rule']['proposed']}",
          f"- cache warming (arm A warm processes, descriptive): {warm_only}"]
    (ART / "results-table.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
