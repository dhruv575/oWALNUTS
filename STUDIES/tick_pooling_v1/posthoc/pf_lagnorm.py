#!/usr/bin/env python3
"""WP93 post hoc (NOT preregistered, exploratory, does not change the frozen verdict): the `pf` variant with the
likelihood weights self-normalised WITHIN EACH LAG GROUP before the time weights mix the groups.

The frozen `pf` normalised the likelihood weights across the whole pool, so a lag-j group's total weight was set by
the product of j return densities (about 70 per return in these units) instead of by its time weight: the lag-0 exact
draws were swamped by the oldest group, and the pool's weight ESS fell below the H = 1 pool's size. This script
reports the corrected estimator (`pf-lagnorm`): per lag j, importance weights w ∝ likelihood of the j new returns,
normalised to sum to the time weight w_j (uniform or exponential); the lag-0 group is the exact current draws with
weight 1. Same quantities, same reference, same rule and the same scored ticks; the pass rule is applied for
information only.

  python posthoc/pf_lagnorm.py [cells-dir] [--out artifacts-dir]
"""
import json, sys, warnings
from pathlib import Path
import numpy as np
warnings.filterwarnings("ignore")
from math import lgamma, log, pi

HERE = Path(__file__).resolve().parent.parent
PROTO = json.loads((HERE / "protocol.json").read_text())
args = [a for a in sys.argv[1:] if not a.startswith("--")]
CELLS = Path(args[0]) if args else HERE / "artifacts" / "cells"
OUT = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else HERE / "artifacts"
DATA = json.loads((HERE / "models" / "data.json").read_text())
Y = np.asarray(DATA["y"])
RHO, NU = PROTO["model"]["rho"], PROTO["model"]["nu"]
EPS_BASE, PROP_BASE = PROTO["quantities"]["eps_seed_base"], PROTO["pooling"]["prop_seed_base"]
TOL50, TOL95, THR = PROTO["accuracy"]["tolerance_p50"], PROTO["accuracy"]["tolerance_p95"], PROTO["latency"]["threshold_s"]
K_GRID, H_GRID, SEEDS = PROTO["arms"]["K"], PROTO["pooling"]["H"], PROTO["arms"]["seeds"]
BIG_N, HMAX = PROTO["stream"]["N"], max(PROTO["pooling"]["H"])
T_CONST = lgamma((NU + 1) / 2) - lgamma(NU / 2) - 0.5 * log(NU * pi)


def records(cell):
    return {r["tick"]: r for r in map(json.loads, (cell / "ticks.jsonl").read_text().splitlines()) if r.get("tick", -1) >= 0}


def load_draws(path, chains, draws):
    return np.frombuffer(Path(path).read_bytes(), dtype="<f4").astype(float).reshape(chains, draws, 4)


def h_next(a, tick, chain_idx):
    mu, ls, hl = a[..., 0], a[..., 1], a[..., 3]
    eps = np.random.default_rng(EPS_BASE + tick).normal(size=(4, 20000))[np.asarray(chain_idx), : a.shape[1]]
    return mu + RHO * (hl - mu) + np.exp(ls) * eps


def wquantile(x, w, ps):
    o = np.argsort(x, kind="stable")
    xs, ws = x[o], w[o]
    ws = ws / ws.sum()
    c = np.cumsum(ws) - ws / 2
    return np.interp(ps, c, xs)


def t_loglik(r, h):
    s = np.exp(h / 2)
    u = r / s
    return T_CONST - np.log(s) - 0.5 * (NU + 1) * np.log1p(u * u / NU)


def propagate(block, s, t, rng):
    mu, sig, beta, h = block[:, 0], np.exp(block[:, 1]), block[:, 2], block[:, 3].copy()
    j = t - s
    logw = np.zeros(len(h))
    eps = rng.normal(size=(len(h), j + 1))
    for i in range(j):
        h = mu + RHO * (h - mu) + sig * eps[:, i]
        logw += t_loglik(Y[BIG_N + s + i] - beta, h)
    return mu + RHO * (h - mu) + sig * eps[:, j], logw


def time_weight(j, H, weighting):
    return 1.0 if weighting == "uniform" or H == 1 else 2.0 ** (-j / (H / 2))


def reference():
    refs = {}
    for c in PROTO["cells"]:
        if c["arm"] != "ref":
            continue
        cell = CELLS / c["id"]
        for t, r in records(cell).items():
            if r["status"] != "ok":
                continue
            a = load_draws(cell / r["file"], r["chains"], r["draws"])[r["kept"]]
            hn = h_next(a, t, r["kept"])
            sig = np.exp(hn / 2).ravel()
            q = wquantile(sig, np.ones_like(sig), [0.5, 0.95])
            refs[t] = dict(p50=float(q[0]), p95=float(q[1]), med_ls=float(np.median(a[..., 1])), med_hl=float(np.median(a[..., 3])))
    return refs


def score(c, refs):
    cell = CELLS / c["id"]
    recs = records(cell)
    draws, hn0 = {}, {}
    for t in range(1, c["ticks"] + 1):
        r = recs[t]
        draws[t] = load_draws(cell / f"tick-{t:03}.f32", r["chains"], r["draws"])
        hn0[t] = h_next(draws[t], t, r.get("kept", list(range(r["chains"])))).ravel()
    rows = {(H, w): [] for H in H_GRID for w in ("uniform", "exp")}
    lag_eff = {j: [] for j in range(HMAX)}
    for t in range(1, c["ticks"] + 1):
        r, ref = recs[t], refs[t]
        a = draws[t]
        stuck = [ci for ci in range(a.shape[0])
                 if abs(np.median(a[ci, :, 1]) - ref["med_ls"]) > 1.0 or abs(np.median(a[ci, :, 3]) - ref["med_hl"]) > 2.0]
        rng = np.random.default_rng(PROP_BASE + t)
        vals, lw = {}, {}
        for j in range(min(HMAX, t)):
            s = t - j
            if j == 0:
                vals[j], lw[j] = hn0[t], np.zeros(hn0[t].size)
            else:
                vals[j], lw[j] = propagate(draws[s].reshape(-1, 4), s, t, rng)
            wn = np.exp(lw[j] - lw[j].max())
            wn /= wn.sum()
            lag_eff[j].append(1.0 / np.sum(wn ** 2) / wn.size)
        for H in H_GRID:
            lags = list(range(min(H, t)))
            for w in ("uniform", "exp"):
                xs, ws = [], []
                for j in lags:
                    wn = np.exp(lw[j] - lw[j].max())
                    wn = wn / wn.sum() * time_weight(j, H, w)
                    xs.append(vals[j])
                    ws.append(wn)
                x, ww = np.concatenate(xs), np.concatenate(ws)
                q = wquantile(np.exp(x / 2), ww, [0.5, 0.95])
                e50, e95 = q[0] / ref["p50"] - 1, q[1] / ref["p95"] - 1
                wn = ww / ww.sum()
                rows[(H, w)].append(dict(tick=t, e50=e50, e95=e95, wess=1.0 / np.sum(wn ** 2), stuck=bool(stuck),
                                         passed=bool(abs(e50) <= TOL50 and abs(e95) <= TOL95 and not stuck and r["wall_seconds"] < THR)))
    return rows, {j: float(np.median(v)) for j, v in lag_eff.items() if v}


def main():
    refs = reference()
    per_cell, lag_eff_all = {}, {}
    for c in PROTO["cells"]:
        if c["arm"] != "warm":
            continue
        rows, lag_eff = score(c, refs)
        per_cell[c["id"]] = (c, rows)
        lag_eff_all[c["id"]] = lag_eff
        print("scored", c["id"], flush=True)
    L = ["## Post hoc (not preregistered): `pf-lagnorm`, likelihood weights normalised within each lag group", "",
         "Exploratory; the frozen verdict stands. Same ticks, reference and rule; the pass rule is applied for information only.", "",
         "| K | H | weighting | pass pooled | per seed | \\|P50 err\\| med | \\|P95 err\\| med | signed P50 | signed P95 | drift pp per seed | wESS med | "
         "would pass |", "|" + "---|" * 12]
    summary = {}
    for K in K_GRID:
        for H in H_GRID:
            for w in ("uniform", "exp"):
                if H == 1 and w == "exp":
                    continue
                cells = [(c, rows[(H, w)]) for c, rows in per_cell.values() if c["K"] == K]
                allrows = [x for _, rows in cells for x in rows]
                per_seed = [np.mean([x["passed"] for x in rows]) for _, rows in cells]
                drifts = [np.mean([x["e50"] for x in rows if x["tick"] >= 70]) - np.mean([x["e50"] for x in rows if x["tick"] <= 30]) for _, rows in cells]
                ps = float(np.mean([x["passed"] for x in allrows]))
                ok = ps >= 0.95 and all(p >= 0.9 for p in per_seed) and all(abs(d) <= PROTO["drift"]["bound"] for d in drifts) and len(cells) == len(SEEDS)
                g = dict(K=K, H=H, weighting=w, pass_share=ps, per_seed=per_seed, drift=drifts,
                         e50_abs_median=float(np.median([abs(x["e50"]) for x in allrows])), e95_abs_median=float(np.median([abs(x["e95"]) for x in allrows])),
                         e50_signed_mean=float(np.mean([x["e50"] for x in allrows])), e95_signed_mean=float(np.mean([x["e95"] for x in allrows])),
                         wess_median=float(np.median([x["wess"] for x in allrows])), would_pass=bool(ok))
                summary[f"K{K}:H{H}:{w}:pf-lagnorm"] = g
                L.append(f"| {K} | {H} | {w} | {100 * ps:.1f} % | {' / '.join(f'{100 * p:.0f} %' for p in per_seed)} | "
                         f"{100 * g['e50_abs_median']:.2f} % | {100 * g['e95_abs_median']:.2f} % | {100 * g['e50_signed_mean']:+.2f} % | "
                         f"{100 * g['e95_signed_mean']:+.2f} % | {', '.join(f'{100 * d:+.2f}' for d in drifts)} | {g['wess_median']:.0f} | "
                         f"{'yes' if ok else 'no'} |")
    L += ["", "## Importance-weight efficiency per lag (weight ESS / draws of that lag group, median over ticks; per K, median over seeds)", "",
          "| K | " + " | ".join(f"lag {j}" for j in range(HMAX)) + " |", "|" + "---|" * (HMAX + 1)]
    for K in K_GRID:
        effs = [lag_eff_all[c["id"]] for c, _ in per_cell.values() if c["K"] == K]
        L.append(f"| {K} | " + " | ".join(f"{100 * np.median([e[j] for e in effs]):.0f} %" for j in range(HMAX)) + " |")
    summary["lag_efficiency"] = {str(K): [float(np.median([lag_eff_all[c["id"]][j] for c, _ in per_cell.values() if c["K"] == K])) for j in range(HMAX)] for K in K_GRID}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "posthoc-pf-lagnorm.md").write_text("\n".join(L) + "\n")
    (OUT / "posthoc-pf-lagnorm.json").write_text(json.dumps(summary, indent=1))
    print("\n".join(L))


if __name__ == "__main__":
    main()
