"""Analysis for python_callpath_v1: artifacts/summary.json + artifacts/results-table.md."""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
TARGETS = PROTOCOL["targets"]
SEEDS = PROTOCOL["seeds"]


def gm(xs):
    xs = [x for x in xs if x is not None and x > 0 and math.isfinite(x)]
    return math.exp(sum(map(math.log, xs)) / len(xs)) if xs else None


def load(phase: str):
    cells, micro = {}, {}
    for p in sorted((ART / phase / "cells").glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        if "step" in r:
            _, _, b, target, arm, t, seed = r["step"]
            r.update(build=b, target=target, arm=arm, threads=int(t), seed=int(seed))
        cells[(r["build"], r["target"], r["arm"], r["threads"], r["seed"])] = r
    for p in sorted((ART / phase / "micro").glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        if "step" in r:
            _, _, b, target, path = r["step"]
            r.update(build=b, target=target, path=path)
        micro[(r["build"], r["target"], r["path"])] = r
    return cells, micro


def ok(r):
    return r is not None and r.get("status") == "ok"


def fmt(x, nd=2):
    if x is None:
        return "—"
    if isinstance(x, str):
        return x
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    if abs(x) >= 100:
        return f"{x:.0f}"
    return f"{x:.{nd}f}"


def phase1(out: dict, md: list[str]) -> None:
    cells, micro = load("phase1")
    b = "baseline"
    arms = PROTOCOL["owalnuts_arms"] + PROTOCOL["nutpie_arms"]
    agg = {}
    for target in TARGETS:
        for arm in arms:
            for t in PROTOCOL["threads"]:
                rs = [cells.get((b, target, arm, t, s)) for s in SEEDS]
                good = [r for r in rs if ok(r)]
                agg[(target, arm, t)] = {
                    "n_ok": len(good), "status": [r.get("status") if r else "missing" for r in rs],
                    "ess_per_second_gm": gm([r["ess_per_second"] for r in good]),
                    "ess_per_call_gm": gm([r["ess_per_call"] for r in good]),
                    "min_bulk_ess_min": min((r["min_bulk_ess"] for r in good), default=None),
                    "min_tail_ess_min": min((r["min_tail_ess"] for r in good), default=None),
                    "max_rhat": max((r["max_rhat"] for r in good), default=None),
                    "divergences": sum(r["health"]["divergences"] for r in good),
                    "max_depth_stops": sum(r["health"]["maximum_depth_stops"] for r in good),
                    "wall_gm": gm([r["wall_seconds"] for r in good]),
                    "wall_per_call_us_median": sorted(r.get("wall_per_call_us", r["wall_seconds"] * 1e6 / r["target_calls"]) for r in good)[len(good) // 2] if good else None,
                    "attached_fraction_mean": (sum(r.get("attached_fraction") or 0 for r in good) / len(good)) if good else None,
                    "calls_gm": gm([r["target_calls"] for r in good]),
                    "sha": [r["samples_sha256"][:16] if ok(r) else None for r in rs],
                }
    out["phase1_cells"] = {f"{k[0]}|{k[1]}|t{k[2]}": v for k, v in agg.items()}

    # micro table
    mt = {}
    for target in TARGETS:
        for path in PROTOCOL["micro_paths"]:
            r = micro.get((b, target, path))
            if ok(r):
                mt[f"{target}|{path}"] = {k: v["median_us"] for k, v in r["components"].items()}
                mt[f"{target}|{path}"]["construct_seconds"] = r["construct_seconds"]
            else:
                mt[f"{target}|{path}"] = {"status": r.get("status") if r else "missing"}
    out["phase1_micro_median_us"] = mt

    md.append("## Phase 1 — micro (median µs per call through the Python surface)\n")
    comps = sorted({c for v in mt.values() for c in v if c not in ("status", "construct_seconds")})
    for target in TARGETS:
        md.append(f"\n### {target}\n\n| path | in-sampler wall/call t1 (µs) | " + " | ".join(comps) + " |")
        md.append("|---|---|" + "---|" * len(comps))
        for path in PROTOCOL["micro_paths"]:
            v = mt[f"{target}|{path}"]
            ins = agg[(target, path, 1)]["wall_per_call_us_median"]
            md.append(f"| {path} | {fmt(ins)} | " + " | ".join(fmt(v.get(c)) for c in comps) + " |")

    md.append("\n## Phase 1 — sampler cells (geomean over 3 seeds; wall CONTENDED)\n")
    for target in TARGETS:
        md.append(f"\n### {target}\n")
        md.append("| arm | threads | ok | ESS/s (gm) | ESS/call (gm) | wall s (gm) | calls (gm) | wall/call µs | attached frac | min bulk | min tail | max R-hat | div | depth stops |")
        md.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for arm in arms:
            for t in PROTOCOL["threads"]:
                a = agg[(target, arm, t)]
                md.append(f"| {arm} | {t} | {a['n_ok']}/3 | {fmt(a['ess_per_second_gm'])} | {fmt(a['ess_per_call_gm'], 4)} | "
                          f"{fmt(a['wall_gm'])} | {fmt(a['calls_gm'])} | {fmt(a['wall_per_call_us_median'])} | "
                          f"{fmt(a['attached_fraction_mean'])} | {fmt(a['min_bulk_ess_min'])} | {fmt(a['min_tail_ess_min'])} | "
                          f"{fmt(a['max_rhat'], 4)} | {a['divergences']} | {a['max_depth_stops']} |")

    # bit identity
    def same(k1, k2):
        r1, r2 = cells.get(k1), cells.get(k2)
        if not (ok(r1) and ok(r2)):
            return None
        return r1["samples_sha256"] == r2["samples_sha256"]

    bit = defaultdict(list)
    for target in TARGETS:
        for s in SEEDS:
            for t in PROTOCOL["threads"]:
                bit[f"py-njit==cfunc|{target}"].append(same((b, target, "py-njit", t, s), (b, target, "cfunc", t, s)))
                bit[f"pymc-numba==pymc-gilfree|{target}"].append(same((b, target, "pymc-numba", t, s), (b, target, "pymc-gilfree", t, s)))
                bit[f"pymc==pymc-numba|{target}"].append(same((b, target, "pymc", t, s), (b, target, "pymc-numba", t, s)))
                bit[f"py-numpy==py-njit|{target}"].append(same((b, target, "py-numpy", t, s), (b, target, "py-njit", t, s)))
                bit[f"jax==py-njit|{target}"].append(same((b, target, "jax", t, s), (b, target, "py-njit", t, s)))
                bit[f"torch==py-njit|{target}"].append(same((b, target, "torch", t, s), (b, target, "py-njit", t, s)))
            for arm in PROTOCOL["owalnuts_arms"]:
                bit[f"t1==t4|{arm}|{target}"].append(same((b, target, arm, 1, s), (b, target, arm, 4, s)))
    out["phase1_bit_identity"] = dict(bit)
    md.append("\n## Phase 1 — bit identity (sha256 of retained draws; one entry per seed x threads, or per seed for t1==t4)\n")
    md.append("| comparison | identical / compared |")
    md.append("|---|---|")
    for k, v in bit.items():
        md.append(f"| {k} | {sum(1 for x in v if x)}/{sum(1 for x in v if x is not None)} |")

    # ratios
    ratios = {}
    for target in TARGETS:
        for arm in arms:
            a1, a4 = agg[(target, arm, 1)]["ess_per_second_gm"], agg[(target, arm, 4)]["ess_per_second_gm"]
            ratios[f"t4/t1|{arm}|{target}"] = (a4 / a1) if a1 and a4 else None
        for arm in PROTOCOL["owalnuts_arms"]:
            for t in PROTOCOL["threads"]:
                # paired per-seed ratio vs nutpie at matched threads/cores
                rs = []
                for s in SEEDS:
                    r, n = cells.get((b, target, arm, t, s)), cells.get((b, target, "nutpie", t, s))
                    if ok(r) and ok(n):
                        rs.append(r["ess_per_second"] / n["ess_per_second"])
                ratios[f"vs_nutpie|{arm}|t{t}|{target}"] = gm(rs)
            rs = []
            for s in SEEDS:
                r, c = cells.get((b, target, arm, 1, s)), cells.get((b, target, "cfunc", 1, s))
                if ok(r) and ok(c):
                    rs.append(r["ess_per_call"] / c["ess_per_call"])
            ratios[f"ess_per_call_vs_cfunc|{arm}|{target}"] = gm(rs)
        rs = []
        for s in SEEDS:
            n, c = cells.get((b, target, "nutpie", 1, s)), cells.get((b, target, "cfunc", 1, s))
            if ok(n) and ok(c):
                rs.append(n["ess_per_call"] / c["ess_per_call"])
        ratios[f"ess_per_call_vs_cfunc|nutpie|{target}"] = gm(rs)
    out["phase1_ratios"] = ratios
    md.append("\n## Phase 1 — ratios (geomean over seeds)\n")
    md.append("| target | arm | t4/t1 ESS/s | vs nutpie t1 (cores 1) | vs nutpie t4 (cores 4) | ESS/call vs cfunc |")
    md.append("|---|---|---|---|---|---|")
    for target in TARGETS:
        for arm in arms:
            md.append(f"| {target} | {arm} | {fmt(ratios.get(f't4/t1|{arm}|{target}'))} | "
                      f"{fmt(ratios.get(f'vs_nutpie|{arm}|t1|{target}'), 3)} | {fmt(ratios.get(f'vs_nutpie|{arm}|t4|{target}'), 3)} | "
                      f"{fmt(ratios.get(f'ess_per_call_vs_cfunc|{arm}|{target}'), 3)} |")

    # transport overhead estimate P1b
    tr = {}
    for target in TARGETS:
        cf = agg[(target, "cfunc", 1)]["wall_per_call_us_median"]
        for path in ("py-numpy", "py-njit", "jax", "torch", "pymc", "pymc-numba"):
            ins = agg[(target, path, 1)]["wall_per_call_us_median"]
            w = mt[f"{target}|{path}"].get("wrap_callable(adapter)")
            tr[f"{path}|{target}"] = (ins - w - cf) if None not in (ins, w, cf) else None
    out["phase1_transport_overhead_us"] = tr
    md.append("\n## Phase 1 — callable transport overhead estimate (in-sampler wall/call t1 − micro wrap_callable(adapter) − cfunc wall/call), µs\n")
    md.append("| path | " + " | ".join(TARGETS) + " |")
    md.append("|---|" + "---|" * len(TARGETS))
    for path in ("py-numpy", "py-njit", "jax", "torch", "pymc", "pymc-numba"):
        md.append(f"| {path} | " + " | ".join(fmt(tr[f'{path}|{t}']) for t in TARGETS) + " |")

    health = []
    for k, r in cells.items():
        if r.get("arm") in PROTOCOL["owalnuts_arms"]:
            if not ok(r):
                health.append({"cell": list(k), "status": r.get("status"), "error": (r.get("error") or "")[:300]})
            elif (r["max_rhat"] > 1.01 or r["health"]["divergences"] > 0 or r["min_bulk_ess"] < 400 or r["min_tail_ess"] < 400):
                health.append({"cell": list(k), "max_rhat": r["max_rhat"], "div": r["health"]["divergences"],
                               "min_bulk": r["min_bulk_ess"], "min_tail": r["min_tail_ess"]})
    out["phase1_health_exceptions"] = health
    nut_fail = [{"cell": list(k), "status": r.get("status"), "error": (r.get("error") or "")[:300]}
                for k, r in cells.items() if r.get("arm") == "nutpie" and not ok(r)]
    out["phase1_nutpie_failures"] = nut_fail
    md.append(f"\n## Phase 1 — owalnuts health exceptions: {len(health)}\n")
    for h in health:
        md.append(f"- {h}")
    if nut_fail:
        md.append(f"\nnutpie failures: {nut_fail}")


def phase2(out: dict, md: list[str]) -> None:
    if not (ART / "phase2" / "cells").exists():
        return
    cells, micro = load("phase2")
    arms = PROTOCOL["phases"]["phase2"]["arms"]
    res = {}
    for target in TARGETS:
        for arm in arms:
            for t in PROTOCOL["threads"]:
                rs, ident = [], []
                for s in SEEDS:
                    a, f = cells.get(("baseline", target, arm, t, s)), cells.get(("fix", target, arm, t, s))
                    if ok(a) and ok(f):
                        rs.append(f["ess_per_second"] / a["ess_per_second"])
                        ident.append(a["samples_sha256"] == f["samples_sha256"])
                    else:
                        ident.append(None)
                res[f"{target}|{arm}|t{t}"] = {"paired_ratio_gm": gm(rs), "ratios": rs, "bit_identical": ident,
                                               "wall_per_call_baseline": [cells[("baseline", target, arm, t, s)].get("wall_per_call_us") for s in SEEDS if ok(cells.get(("baseline", target, arm, t, s)))],
                                               "wall_per_call_fix": [cells[("fix", target, arm, t, s)].get("wall_per_call_us") for s in SEEDS if ok(cells.get(("fix", target, arm, t, s)))]}
    out["phase2_paired"] = res
    touched = PROTOCOL["phases"]["phase2"].get("touched_arms", arms)
    all_ident = all(x is True for k, v in res.items() if k.split("|")[1] in touched for x in v["bit_identical"])
    best = max(((k, v["paired_ratio_gm"]) for k, v in res.items() if k.split("|")[1] in touched and v["paired_ratio_gm"]),
               key=lambda kv: kv[1], default=(None, None))
    worst = min(((k, v["paired_ratio_gm"]) for k, v in res.items() if k.split("|")[1] in touched and v["paired_ratio_gm"]),
                key=lambda kv: kv[1], default=(None, None))
    decision = {"bit_identical_all_touched": all_ident, "best": best, "worst": worst,
                "merge": bool(all_ident and best[1] and best[1] >= 1.3 and worst[1] and worst[1] >= 0.9)}
    out["phase2_decision"] = decision
    mt = {}
    for k, r in micro.items():
        if ok(r):
            mt["|".join(k)] = {c: v["median_us"] for c, v in r["components"].items()}
    out["phase2_micro_median_us"] = mt
    md.append("\n## Phase 2 — fix vs baseline (paired, interleaved, same seeds)\n")
    md.append("| target | arm | threads | fix/baseline ESS/s (gm) | per-seed | bit-identical | wall/call µs base → fix |")
    md.append("|---|---|---|---|---|---|---|")
    for k, v in res.items():
        target, arm, t = k.split("|")
        wb = v["wall_per_call_baseline"]
        wf = v["wall_per_call_fix"]
        md.append(f"| {target} | {arm} | {t[1:]} | {fmt(v['paired_ratio_gm'], 3)} | {', '.join(f'{x:.2f}' for x in v['ratios'])} | "
                  f"{sum(1 for x in v['bit_identical'] if x)}/{len(v['bit_identical'])} | "
                  f"{fmt(sorted(wb)[len(wb)//2] if wb else None)} → {fmt(sorted(wf)[len(wf)//2] if wf else None)} |")
    md.append("\n### Phase 2 micro (median µs)\n")
    for k, v in sorted(mt.items()):
        md.append(f"- {k}: " + ", ".join(f"{c} {fmt(x)}" for c, x in v.items()))
    md.append(f"\n**Decision:** {decision}")


def main() -> None:
    out: dict = {"protocol_sha256": __import__("hashlib").sha256((HERE / "protocol.json").read_bytes()).hexdigest()}
    md = ["# python_callpath_v1 results (generated by analyze_callpath.py)\n",
          "Walls are CONTENDED (shared 16-core machine, ~10 concurrent agents); ESS/call and bit identity are machine-independent.\n"]
    phase1(out, md)
    phase2(out, md)
    (ART / "summary.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    (ART / "results-table.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
