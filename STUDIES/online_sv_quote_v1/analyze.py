#!/usr/bin/env python3
"""WP84 analysis: per-tick quantities, validity, latency, drift, decision rule (protocol.json)."""
import json, sys, warnings
from pathlib import Path
import numpy as np
warnings.filterwarnings("ignore")
import arviz as az

HERE = Path(__file__).resolve().parent
PROTO = json.loads((HERE / "protocol.json").read_text())
DATA = json.loads((HERE / "models" / "data.json").read_text())
RHO = DATA["rho"]
CELLS = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "artifacts" / "cells"
P = [0.05, 0.5, 0.95]


def load_tick(cell, tick):
    raw = np.frombuffer((cell / f"tick-{tick:03}.f32").read_bytes(), dtype="<f4").astype(float)
    a = raw.reshape(4, -1, 3)
    mu, ls, hl = a[..., 0], a[..., 1], a[..., 2]
    eps = np.random.default_rng(840000 + tick).normal(size=(4, 20000))[:, : a.shape[1]]
    m = mu + RHO * (hl - mu)
    hn = m + np.exp(ls) * eps
    straddle = float(np.mean(np.exp(m / 2 + np.exp(2 * ls) / 8)))
    q = np.quantile(hn, P)
    mc = np.array([float(az.mcse(hn, method="quantile", prob=p)) for p in P])
    rhat = max(float(az.rhat(x)) for x in (mu, ls, hl, hn))
    return dict(q=q, mcse=mc, rhat=rhat, hn=hn, straddle=straddle)


def records(cell):
    return {r["tick"]: r for r in map(json.loads, (cell / "ticks.jsonl").read_text().splitlines())}


def main():
    refs = {}
    for N in PROTO["stream"]["N"]:
        c = CELLS / f"ref-N{N}"
        recs = records(c)
        refs[N] = {t: load_tick(c, t) for t, r in recs.items() if r["status"] == "ok"}
    rows, ticks_out = [], {}
    for c in PROTO["cells"]:
        if c["arm"] == "ref":
            continue
        cell = CELLS / c["id"]
        if not (cell / "ticks.jsonl").exists():
            rows.append(dict(id=c["id"], status="missing"))
            continue
        recs = records(cell)
        N, per = c["N"], []
        for t in range(1, PROTO["stream"]["ticks"] + 1):
            r = recs.get(t)
            ref = refs[N].get(t)
            if r is None or r["status"] != "ok" or ref is None:
                per.append(dict(tick=t, ok=False, wall=r["wall_seconds"] if r else None, v1=False, v2=False))
                continue
            e = load_tick(cell, t)
            err = np.abs(e["q"] - ref["q"])
            clean = e["rhat"] <= 1.01 and sum(r["divergences"]) == 0
            v1 = bool(clean and np.all(err <= 3 * ref["mcse"]))
            v2 = bool(clean and np.all(err <= 3 * np.sqrt(ref["mcse"] ** 2 + e["mcse"] ** 2)))
            lo, hi = ref["q"][0], ref["q"][2]
            inside = float(np.mean((e["hn"] >= lo) & (e["hn"] <= hi)))
            truth = DATA["h"][N + t]
            ql, qh = np.quantile(e["hn"], [0.05, 0.95])
            per.append(dict(tick=t, ok=True, wall=r["wall_seconds"], v1=v1, v2=v2, rhat=e["rhat"],
                            div=sum(r["divergences"]), err_over_mcse=(err / ref["mcse"]).tolist(), inside_ref90=inside,
                            truth_covered=bool(ql <= truth <= qh),
                            straddle_rel_err=e["straddle"] / ref["straddle"] - 1))
        thr = 0.4 if N == 250 else 2.0
        ref_ok = len(refs[N]) > 0  # A1: a failed reference makes validity n/a, not 0
        w = np.array([p["wall"] if p["wall"] is not None else np.inf for p in per])
        okp = [p for p in per if p["ok"]]
        row = dict(id=c["id"], arm=c["arm"] + str(c.get("K", "")), N=N, seed=c["seed"], ticks_ok=len(okp),
                   median_s=float(np.median(w)), p95_s=float(np.quantile(w, .95)),
                   frac_lt_0p4=float(np.mean(w < 0.4)), frac_lt_2=float(np.mean(w < 2.0)),
                   valid1=float(np.mean([p["v1"] for p in per])), valid2=float(np.mean([p["v2"] for p in per])),
                   valid1_and_fast=float(np.mean([p["v1"] and p["wall"] < thr for p in per])),
                   rhat_pass=float(np.mean([p.get("rhat", 9) <= 1.01 for p in per])),
                   div_free=float(np.mean([p.get("div", 1) == 0 for p in per])),
                   truth_cov90=float(np.mean([p.get("truth_covered", False) for p in per])),
                   ref_available=ref_ok,
                   straddle_abs_rel_err_median=float(np.median([abs(p["straddle_rel_err"]) for p in okp])) if okp else None)
        if c["arm"] == "warm":
            t0 = records(cell).get(0, {})
            row["tick0_wall_s"] = t0.get("wall_seconds")
        if c["arm"] == "warm" and okp:
            ins = np.array([p.get("inside_ref90", np.nan) for p in per])
            row.update(drift_mean=float(np.nanmean(ins)), drift_early=float(np.nanmean(ins[:25])),
                       drift_late=float(np.nanmean(ins[75:])))
            row["drift_ok"] = bool(abs(row["drift_mean"] - .9) <= .03 and abs(row["drift_late"] - row["drift_early"]) <= .03)
            t0 = records(cell).get(0, {})
            row["tick0_wall_s"] = t0.get("wall_seconds")
        rows.append(row)
        ticks_out[c["id"]] = per
    # decision rule
    verdict = {}
    for K in (50, 200):
        ok = True
        for N in (250, 1000):
            rs = [r for r in rows if r.get("arm") == f"warm{K}" and r["N"] == N]
            pooled = np.mean([r["valid1_and_fast"] for r in rs]) if len(rs) == 3 else 0
            drift = len(rs) == 3 and all(r.get("drift_ok") for r in rs)
            verdict[f"K{K}_N{N}"] = dict(valid_and_fast=float(pooled), drift_ok=bool(drift))
            ok &= pooled >= 0.95 and drift
        verdict[f"K{K}_realtime"] = bool(ok)
    verdict["realtime_claim_allowed"] = verdict["K50_realtime"] or verdict["K200_realtime"]
    out = HERE / "artifacts"
    (out / "summary.json").write_text(json.dumps(dict(rows=rows, verdict=verdict), indent=1))
    (out / "per-tick.json").write_text(json.dumps(ticks_out))
    hdr = "| arm | N | median s | p95 s | <0.4 s | <2 s | valid (3 ref-MCSE) | valid (combined MCSE) | R-hat ok | div-free | drift in-ref90 (early/late) |"
    lines = [hdr, "|" + "---|" * 11]
    for arm in ("warm50", "warm200", "refit", "cmdstan", "nutpie"):
        for N in (250, 1000):
            rs = [r for r in rows if r.get("arm") == arm and r["N"] == N]
            if not rs:
                continue
            f = lambda k: float(np.mean([r[k] for r in rs])) if all(r.get("ref_available") and k in r for r in rs) else float("nan")
            d = (f"{f('drift_mean'):.3f} ({f('drift_early'):.3f}/{f('drift_late'):.3f})" if arm.startswith("warm") else "")
            g = lambda k: float(np.mean([r[k] for r in rs]))
            lines.append(f"| {arm} | {N} | {np.median([r['median_s'] for r in rs]):.3f} | {max(r['p95_s'] for r in rs):.3f} | "
                         f"{g('frac_lt_0p4'):.2f} | {g('frac_lt_2'):.2f} | {f('valid1'):.2f} | {f('valid2'):.2f} | "
                         f"{f('rhat_pass'):.2f} | {f('div_free'):.2f} | {d} |")
    (out / "results-table.md").write_text("\n".join(lines) + "\n\n" + json.dumps(verdict, indent=1) + "\n")
    print("\n".join(lines))
    print(json.dumps(verdict, indent=1))


if __name__ == "__main__":
    main()
