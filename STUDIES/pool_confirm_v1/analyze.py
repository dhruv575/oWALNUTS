#!/usr/bin/env python3
"""WP97 analysis: gated reference per dataset, the as-is H = 1 control and the lag-normalised likelihood-reweighted pool
(pf-lagnorm, WP93 posthoc/pf_lagnorm.py reproduced) at H in {10, 20} with exponential (primary) and uniform (secondary) lag
weights, the WP88 quote rule, latency (library call + pooling arithmetic), drift, weight ESS per lag group, the chain-split
own MCSE of the pooled P50, the largest tolerance met per dataset, and the decision rule (protocol.json).

  python analyze.py [cells-dir] [--out artifacts-dir]

Reads <cells>/*/ticks.jsonl and tick-XXX.f32; writes <out>/summary.json, <out>/per-config.json and <out>/results-table.md.
Reads only.
"""
import json, sys, time, warnings
from math import lgamma, log, pi
from pathlib import Path
import numpy as np
warnings.filterwarnings("ignore")
import arviz as az

HERE = Path(__file__).resolve().parent
PROTO = json.loads((HERE / "protocol.json").read_text())
args = [a for a in sys.argv[1:] if not a.startswith("--")]
CELLS = Path(args[0]) if args else HERE / "artifacts" / "cells"
OUT = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else HERE / "artifacts"
DATASETS = list(PROTO["datasets"])
Y = {d: np.asarray(json.loads((HERE / PROTO["datasets"][d]["file"]).read_text())["y"]) for d in DATASETS}
RHO, NU = PROTO["model"]["rho"], PROTO["model"]["nu"]
EPS_BASE = PROTO["quantities"]["eps_seed_base"]
PROP_BASE = PROTO["pooling"]["prop_seed_base"]
TOL50, TOL95 = PROTO["accuracy"]["tolerance_p50"], PROTO["accuracy"]["tolerance_p95"]
THR = PROTO["latency"]["threshold_s"]
EXTRA_THR = PROTO["latency"]["also_reported_s"]
DRIFT_BOUND = PROTO["drift"]["bound"]
K_GRID, H_GRID = PROTO["arms"]["K"], PROTO["pooling"]["H"]
SEEDS = PROTO["arms"]["seeds"]
BIG_N, TICKS = PROTO["stream"]["N"], PROTO["stream"]["ticks"]
HMAX = max(H_GRID)
CONFIGS = [("asis", 1, "uniform")] + [("pf-lagnorm", H, w) for H in H_GRID if H > 1 for w in ("exp", "uniform")]
TOL_GRID = [(a, b) for a in (0.01, 0.02, 0.05, 0.10) for b in (0.02, 0.05, 0.10, 0.20)]
T_CONST = lgamma((NU + 1) / 2) - lgamma(NU / 2) - 0.5 * log(NU * pi)


def records(cell):
    p = cell / "ticks.jsonl"
    if not p.exists():
        return {}
    return {r["tick"]: r for r in map(json.loads, p.read_text().splitlines()) if r.get("tick", -1) >= 0}


def load_draws(path, chains, draws):
    raw = np.frombuffer(Path(path).read_bytes(), dtype="<f4").astype(float)
    return raw.reshape(chains, draws, 4)


def eps_rows(tick, chain_idx, draws):
    return np.random.default_rng(EPS_BASE + tick).normal(size=(4, 20000))[np.asarray(chain_idx), :draws]


def h_next(a, tick, chain_idx):
    mu, ls, hl = a[..., 0], a[..., 1], a[..., 3]
    return mu + RHO * (hl - mu) + np.exp(ls) * eps_rows(tick, chain_idx, a.shape[1])


def wquantile(x, w, ps):
    """Weighted quantile: linear interpolation of the midpoint CDF (uniform weights = Hyndman-Fan type 5)."""
    o = np.argsort(x, kind="stable")
    xs, ws = x[o], w[o]
    ws = ws / ws.sum()
    c = np.cumsum(ws) - ws / 2
    return np.interp(ps, c, xs)


def quantities(hn, w=None, full=False):
    """P5/P50/P95/mean of sigma_next = exp(h_next/2) from draws hn (any shape) with optional weights (same size)."""
    x = np.exp(hn / 2).ravel()
    ww = np.ones_like(x) if w is None else np.asarray(w).ravel()
    q = wquantile(x, ww, [0.05, 0.5, 0.95])
    out = dict(p5=float(q[0]), p50=float(q[1]), p95=float(q[2]), mean=float(np.sum(x * ww) / ww.sum()),
               hn_q=[float(v) for v in wquantile(hn.ravel(), ww, [0.05, 0.95])])
    if full:
        sig2 = np.exp(hn / 2)
        out["ess"] = float(az.ess(hn))
        out["rhat"] = float(az.rhat(hn)) if hn.shape[0] > 1 else float("nan")
        out["mcse_rel_p50"] = float(az.mcse(sig2, method="quantile", prob=0.5)) / out["p50"]
        out["mcse_rel_p95"] = float(az.mcse(sig2, method="quantile", prob=0.95)) / out["p95"]
    return out


# ── references ──────────────────────────────────────────────────────────────────────────────

def load_references(dataset):
    refs, st = {}, dict(dataset=dataset, ticks_planned=0, ticks_recorded=0, ticks_ok=0, gate_failed=0, second_seed=0,
                        flagged_chain_ticks=0, flagged_ticks=[], kept_min=4, rhat_max=0.0, mcse_rel_p50=[], mcse_rel_p95=[],
                        ess_min=None, walls=[], driver_walls=[], cells=[])
    for c in PROTO["cells"]:
        if c["arm"] != "ref" or c["dataset"] != dataset:
            continue
        cell = CELLS / c["id"]
        recs = records(cell)
        st["ticks_planned"] += len(c["ticks"])
        st["ticks_recorded"] += len(recs)
        st["cells"].append(c["id"])
        for t, r in sorted(recs.items()):
            if r["status"] != "ok":
                st["gate_failed"] += 1
                continue
            st["ticks_ok"] += 1
            st["second_seed"] += int(r["attempt"] > 0)
            if len(r["flagged"]) > 0 or any(a.get("flagged") for a in r["attempts"]):
                st["flagged_chain_ticks"] += 1
                st["flagged_ticks"].append(t)
            st["kept_min"] = min(st["kept_min"], len(r["kept"]))
            st["rhat_max"] = max(st["rhat_max"], r["rhat_h_next"])
            st["walls"].append(sum(a.get("wall_seconds") or 0 for a in r["attempts"]))
            st["driver_walls"].append(sum(a.get("driver_wall") or 0 for a in r["attempts"]))
            a = load_draws(cell / r["file"], r["chains"], r["draws"])[r["kept"]]
            hn = h_next(a, t, r["kept"])
            q = quantities(hn, full=True)
            q.update(kept=r["kept"], flagged=r["flagged"], attempt=r["attempt"], wall=r["wall_seconds"],
                     med_ls=float(np.median(a[..., 1])), med_hl=float(np.median(a[..., 3])))
            refs[t] = q
            st["mcse_rel_p50"].append(q["mcse_rel_p50"])
            st["mcse_rel_p95"].append(q["mcse_rel_p95"])
            st["ess_min"] = q["ess"] if st["ess_min"] is None else min(st["ess_min"], q["ess"])
    for k in ("mcse_rel_p50", "mcse_rel_p95"):
        v = np.array(st[k])
        st[k] = dict(median=float(np.median(v)), p95=float(np.quantile(v, .95)), max=float(v.max())) if len(v) else None
    w, dw = st.pop("walls"), st.pop("driver_walls")
    st["wall_median"] = float(np.median(w)) if w else None
    st["wall_max"] = float(np.max(w)) if w else None
    st["wall_total_min"] = float(np.sum(w) / 60) if w else None
    st["driver_wall_median"] = float(np.median(dw)) if dw else None
    st["driver_wall_total_min"] = float(np.sum(dw) / 60) if dw else None
    return refs, st


def reference_lag_curve(refs):
    """Staleness with no Monte Carlo noise: the reference's own P50/P95 at tick t-j against tick t."""
    out = {}
    ts = sorted(t for t in refs if t >= 1)
    for j in range(1, HMAX + 1):
        e50 = np.array([refs[t - j]["p50"] / refs[t]["p50"] - 1 for t in ts if t - j in refs])
        e95 = np.array([refs[t - j]["p95"] / refs[t]["p95"] - 1 for t in ts if t - j in refs])
        if len(e50) == 0:
            continue
        out[j] = dict(n=int(len(e50)), p50_abs_median=float(np.median(np.abs(e50))), p50_within=float(np.mean(np.abs(e50) <= TOL50)),
                      p50_signed_mean=float(e50.mean()), p95_abs_median=float(np.median(np.abs(e95))),
                      p95_within=float(np.mean(np.abs(e95) <= TOL95)), p95_signed_mean=float(e95.mean()),
                      both_within=float(np.mean((np.abs(e50) <= TOL50) & (np.abs(e95) <= TOL95))))
    return out


# ── pooling ─────────────────────────────────────────────────────────────────────────────────

def t_loglik(r, h):
    """log t_nu(r; 0, exp(h/2)) elementwise."""
    s = np.exp(h / 2)
    u = r / s
    return T_CONST - np.log(s) - 0.5 * (NU + 1) * np.log1p(u * u / NU)


def propagate(block, s, t, rng, y):
    """From tick-s draws (n, 4) propagate h_{N+s} -> h_{N+t+1} (j+1 = t-s+1 steps) with fresh noise; return h_next and the
    log-likelihood weight of the j new returns y[N+s .. N+t-1] along the path (WP93 pf_lagnorm.propagate unchanged)."""
    mu, sig, beta, h = block[:, 0], np.exp(block[:, 1]), block[:, 2], block[:, 3].copy()
    j = t - s
    logw = np.zeros(len(h))
    eps = rng.normal(size=(len(h), j + 1))
    for i in range(j):
        h = mu + RHO * (h - mu) + sig * eps[:, i]
        logw += t_loglik(y[BIG_N + s + i] - beta, h)
    hn = mu + RHO * (h - mu) + sig * eps[:, j]
    return hn, logw


def time_weight(j, H, weighting):
    return 1.0 if weighting == "uniform" or H == 1 else 2.0 ** (-j / (H / 2))


def lag_normalised(logw):
    v = np.exp(logw - logw.max())
    return v / v.sum()


def score_cell(c, refs):
    """Score every configuration of one warm cell on ticks 1..TICKS."""
    cell = CELLS / c["id"]
    recs = records(cell)
    K, y = c["K"], Y[c["dataset"]]
    draws, hn_asis = {}, {}
    for t in range(1, c["ticks"] + 1):
        r = recs.get(t)
        if r is None or r.get("status") != "ok":
            continue
        a = load_draws(cell / f"tick-{t:03}.f32", r["chains"], r["draws"])
        draws[t] = a
        hn_asis[t] = h_next(a, t, r.get("kept", list(range(r["chains"]))))
    scored = {cfg: [] for cfg in CONFIGS}
    lag_eff = {j: [] for j in range(HMAX)}
    own = []  # per tick H = 1 diagnostics (ESS, R-hat, arviz own MCSE)
    for t in range(1, c["ticks"] + 1):
        r, ref = recs.get(t), refs.get(t)
        base_fail = None
        if r is None or r.get("status") != "ok":
            base_fail = "arm_error_or_missing"
        elif ref is None:
            base_fail = "no_reference"
        if base_fail:
            for cfg in CONFIGS:
                scored[cfg].append(dict(tick=t, ok=False, reason=base_fail, passed=False, accurate=False, wall=(r or {}).get("wall_seconds")))
            continue
        a = draws[t]
        C, wall = a.shape[0], r["wall_seconds"]
        stuck = [ci for ci in range(C)
                 if abs(np.median(a[ci, :, 1]) - ref["med_ls"]) > 1.0 or abs(np.median(a[ci, :, 3]) - ref["med_hl"]) > 2.0]
        q1 = quantities(hn_asis[t], full=True)
        own.append(dict(tick=t, ess=q1["ess"], rhat=q1["rhat"], mcse_rel_p50=q1["mcse_rel_p50"], mcse_rel_p95=q1["mcse_rel_p95"],
                        div=int(sum(r.get("divergences", [])))))
        # per lag: values and likelihood log-weights (lag 0 = the exact current draws), the re-propagation timed per lag
        rng = np.random.default_rng(PROP_BASE[c["dataset"]] + t)
        vals, logw, prop_s = {}, {}, {}
        for j in range(min(HMAX, t)):
            s = t - j
            if j == 0:
                vals[j], logw[j], prop_s[j] = hn_asis[t].ravel(), np.zeros(hn_asis[t].size), 0.0
            else:
                t0 = time.perf_counter()
                vals[j], logw[j] = propagate(draws[s].reshape(-1, 4), s, t, rng, y)
                prop_s[j] = time.perf_counter() - t0
            v = lag_normalised(logw[j])
            lag_eff[j].append(1.0 / np.sum(v ** 2) / v.size)
        for est, H, w in CONFIGS:
            lags = list(range(min(H, t)))
            t0 = time.perf_counter()
            xs, ws = [], []
            for j in lags:
                xs.append(vals[j])
                ws.append(lag_normalised(logw[j]) * time_weight(j, H, w) if est == "pf-lagnorm" else np.ones(vals[j].size))
            x, ww = np.concatenate(xs), np.concatenate(ws)
            q = quantities(x, ww)
            pool_s = (time.perf_counter() - t0) + sum(prop_s[j] for j in lags)
            e50, e95 = q["p50"] / ref["p50"] - 1, q["p95"] / ref["p95"] - 1
            accurate = abs(e50) <= TOL50 and abs(e95) <= TOL95 and not stuck
            wn = ww / ww.sum()
            inside = float(np.sum(wn * ((x >= ref["hn_q"][0]) & (x <= ref["hn_q"][1]))))
            # chain-split own MCSE of the pooled P50: the same pool from each chain's draws alone (chain-major flattening)
            p50c = []
            for ci in range(C):
                xc, wc = [], []
                for j in lags:
                    xj = vals[j].reshape(C, -1)[ci]
                    lj = logw[j].reshape(C, -1)[ci]
                    xc.append(xj)
                    wc.append(lag_normalised(lj) * time_weight(j, H, w) if est == "pf-lagnorm" else np.ones(xj.size))
                p50c.append(wquantile(np.exp(np.concatenate(xc) / 2), np.concatenate(wc), [0.5])[0])
            own_mcse = float(np.std(p50c, ddof=1) / np.sqrt(C) / q["p50"]) if C > 1 else None
            scored[(est, H, w)].append(dict(
                tick=t, ok=True, wall=wall, pool_s=pool_s, total_s=wall + pool_s, e50=e50, e95=e95, e5=q["p5"] / ref["p5"] - 1,
                emean=q["mean"] / ref["mean"] - 1, stuck=stuck, accurate=bool(accurate), fast=bool(wall + pool_s < THR),
                passed=bool(accurate and wall + pool_s < THR), pool_n=int(x.size), wess=float(1.0 / np.sum(wn ** 2)),
                inside_ref90=inside, own_mcse=own_mcse))
    walls = np.array([recs[t]["wall_seconds"] if recs.get(t, {}).get("status") == "ok" else np.inf for t in range(1, c["ticks"] + 1)])
    n_ok = int(np.isfinite(walls).sum())
    t0 = recs.get(0, {})
    cellinfo = dict(id=c["id"], dataset=c["dataset"], K=K, seed=c["seed"], ticks=c["ticks"], ticks_ok=n_ok,
                    median_s=float(np.median(walls)) if n_ok else None, p95_s=float(np.quantile(walls, .95)) if n_ok else None,
                    max_s=float(walls.max()) if n_ok else None, frac_lt_thr=float(np.mean(walls < THR)),
                    frac_lt={str(x): float(np.mean(walls < x)) for x in EXTRA_THR},
                    tick0_status=t0.get("status"), tick0_wall_s=t0.get("wall_seconds"), tick0_attempts=len(t0.get("attempts", [])),
                    tick0_flagged=t0.get("flagged"), kept=t0.get("kept"), tick0_seed=t0.get("tick0_seed"),
                    own_mcse_rel_p50_median=_med([o["mcse_rel_p50"] for o in own]), own_mcse_rel_p95_median=_med([o["mcse_rel_p95"] for o in own]),
                    ess_median=_med([o["ess"] for o in own]), rhat_ok=_mean([o["rhat"] <= 1.01 for o in own if np.isfinite(o["rhat"])]),
                    div_ticks=int(sum(1 for o in own if o["div"] > 0)),
                    lag_eff_median={str(j): _med(v) for j, v in lag_eff.items() if v})
    ref0 = refs.get(0)
    if t0.get("status") == "ok" and ref0 is not None and (cell / "tick-000.f32").exists():
        a0 = load_draws(cell / "tick-000.f32", t0["chains"], t0["draws"])
        q0 = quantities(h_next(a0, 0, list(range(t0["chains"]))))
        cellinfo["tick0_e50"], cellinfo["tick0_e95"] = q0["p50"] / ref0["p50"] - 1, q0["p95"] / ref0["p95"] - 1
    rows = {}
    for cfg, sc in scored.items():
        okk = [s for s in sc if s["ok"]]
        early = [s["e50"] for s in okk if s["tick"] <= 30]
        late = [s["e50"] for s in okk if s["tick"] >= 70]
        drift = float(np.mean(late) - np.mean(early)) if early and late else None
        rows[cfg] = dict(
            scored=len(sc), passed=int(sum(s["passed"] for s in sc)), accurate=int(sum(s["accurate"] for s in sc)),
            passed_ge20=int(sum(s["passed"] for s in sc if s["tick"] >= 20)), scored_ge20=int(sum(1 for s in sc if s["tick"] >= 20)),
            p50_ok=int(sum(abs(s["e50"]) <= TOL50 for s in okk)), p95_ok=int(sum(abs(s["e95"]) <= TOL95 for s in okk)),
            stuck_ticks=int(sum(1 for s in okk if s["stuck"])), unscored=int(sum(1 for s in sc if not s["ok"])),
            slow_ticks=int(sum(1 for s in okk if not s["fast"])),
            e50_abs_median=_med([abs(s["e50"]) for s in okk]), e50_abs_p95=_q95([abs(s["e50"]) for s in okk]),
            e95_abs_median=_med([abs(s["e95"]) for s in okk]), e95_abs_p95=_q95([abs(s["e95"]) for s in okk]),
            e50_signed_mean=_mean([s["e50"] for s in okk]), e95_signed_mean=_mean([s["e95"] for s in okk]),
            e5_signed_mean=_mean([s["e5"] for s in okk]), emean_signed_mean=_mean([s["emean"] for s in okk]),
            drift=drift, drift_ok=bool(drift is not None and abs(drift) <= DRIFT_BOUND), drift_n=[len(early), len(late)],
            pool_n_median=_med([s["pool_n"] for s in okk]), wess_median=_med([s["wess"] for s in okk]), wess_min=_min([s["wess"] for s in okk]),
            inside_ref90=_mean([s["inside_ref90"] for s in okk]), own_mcse_median=_med([s["own_mcse"] for s in okk if s["own_mcse"] is not None]),
            pool_s_median=_med([s["pool_s"] for s in okk]), pool_s_p95=_q95([s["pool_s"] for s in okk]),
            total_s_median=_med([s["total_s"] for s in okk]), total_s_p95=_q95([s["total_s"] for s in okk]),
            tol_grid={f"{int(100 * a)}/{int(100 * b)}": int(sum(1 for s in okk if abs(s["e50"]) <= a and abs(s["e95"]) <= b and not s["stuck"]))
                      for a, b in TOL_GRID})
    return cellinfo, rows, scored


def _med(v):
    return float(np.median(v)) if len(v) else None


def _q95(v):
    return float(np.quantile(v, .95)) if len(v) else None


def _mean(v):
    return float(np.mean(v)) if len(v) else None


def _min(v):
    return float(np.min(v)) if len(v) else None


def cfg_key(dataset, K, cfg):
    est, H, w = cfg
    return f"{dataset}:K{K}:H{H}:{w}:{est}"


def group(dataset, K, cfg, cell_rows, cells):
    rs = [(ci, cell_rows[ci["id"]][cfg]) for ci in cells if ci.get("K") == K and ci.get("dataset") == dataset and ci["id"] in cell_rows]
    if not rs:
        return None
    scored = sum(r["scored"] for _, r in rs)
    passed = sum(r["passed"] for _, r in rs)
    per_seed = [r["passed"] / r["scored"] if r["scored"] else None for _, r in rs]
    largest = None
    for a, b in TOL_GRID:
        key = f"{int(100 * a)}/{int(100 * b)}"
        pooled = sum(r["tol_grid"][key] for _, r in rs) / scored if scored else 0
        if pooled >= 0.95 and all(r["tol_grid"][key] / r["scored"] >= 0.90 for _, r in rs if r["scored"]):
            largest = key
            break
    g = dict(dataset=dataset, K=K, estimator=cfg[0], H=cfg[1], weighting=cfg[2], cells=[ci["id"] for ci, _ in rs], scored=scored,
             passed=passed, pass_share=passed / scored if scored else None, per_seed_pass=per_seed,
             accurate_share=sum(r["accurate"] for _, r in rs) / scored if scored else None,
             pass_share_ge20=(sum(r["passed_ge20"] for _, r in rs) / sum(r["scored_ge20"] for _, r in rs)) if sum(r["scored_ge20"] for _, r in rs) else None,
             p50_ok_share=sum(r["p50_ok"] for _, r in rs) / scored if scored else None,
             p95_ok_share=sum(r["p95_ok"] for _, r in rs) / scored if scored else None,
             stuck_ticks=sum(r["stuck_ticks"] for _, r in rs), unscored=sum(r["unscored"] for _, r in rs),
             slow_ticks=sum(r["slow_ticks"] for _, r in rs),
             lib_s_median=_med([ci["median_s"] for ci, _ in rs if ci["median_s"] is not None]),
             lib_s_p95=max((ci["p95_s"] for ci, _ in rs if ci["p95_s"] is not None), default=None),
             pool_s_median=_med([r["pool_s_median"] for _, r in rs if r["pool_s_median"] is not None]),
             pool_s_p95=max((r["pool_s_p95"] for _, r in rs if r["pool_s_p95"] is not None), default=None),
             total_s_median=_med([r["total_s_median"] for _, r in rs if r["total_s_median"] is not None]),
             total_s_p95=max((r["total_s_p95"] for _, r in rs if r["total_s_p95"] is not None), default=None),
             e50_abs_median=_med([r["e50_abs_median"] for _, r in rs if r["e50_abs_median"] is not None]),
             e95_abs_median=_med([r["e95_abs_median"] for _, r in rs if r["e95_abs_median"] is not None]),
             e50_signed_mean=_mean([r["e50_signed_mean"] for _, r in rs if r["e50_signed_mean"] is not None]),
             e95_signed_mean=_mean([r["e95_signed_mean"] for _, r in rs if r["e95_signed_mean"] is not None]),
             drift=[r["drift"] for _, r in rs], drift_ok_all=all(r["drift_ok"] for _, r in rs),
             pool_n_median=_med([r["pool_n_median"] for _, r in rs if r["pool_n_median"] is not None]),
             wess_median=_med([r["wess_median"] for _, r in rs if r["wess_median"] is not None]),
             wess_min=_min([r["wess_min"] for _, r in rs if r["wess_min"] is not None]),
             inside_ref90=_mean([r["inside_ref90"] for _, r in rs if r["inside_ref90"] is not None]),
             own_mcse_median=_med([r["own_mcse_median"] for _, r in rs if r["own_mcse_median"] is not None]),
             largest_tolerance=largest, n_seeds=len(rs))
    g["rule_pass"] = bool(g["pass_share"] is not None and g["pass_share"] >= 0.95 and
                          all(p is not None and p >= 0.90 for p in per_seed) and g["drift_ok_all"] and len(rs) == len(SEEDS[dataset]))
    return g


def main():
    refs, ref_stats, lag = {}, {}, {}
    for d in DATASETS:
        refs[d], ref_stats[d] = load_references(d)
        lag[d] = reference_lag_curve(refs[d])
    cells, cell_rows, per = [], {}, {}
    for c in PROTO["cells"]:
        if c["arm"] != "warm":
            continue
        if not (CELLS / c["id"] / "ticks.jsonl").exists():
            cells.append(dict(id=c["id"], dataset=c["dataset"], K=c["K"], seed=c["seed"], status="missing", median_s=None, p95_s=None,
                              frac_lt_thr=0.0, frac_lt={}, lag_eff_median={}))
            continue
        ci, rows, scored = score_cell(c, refs[c["dataset"]])
        cells.append(ci)
        cell_rows[ci["id"]] = rows
        per[ci["id"]] = {cfg_key(c["dataset"], c["K"], cfg): sc for cfg, sc in scored.items()}
        print(time.strftime("%H:%M:%S"), "scored", ci["id"], flush=True)
    groups = {}
    for d in DATASETS:
        for K in K_GRID:
            for cfg in CONFIGS:
                g = group(d, K, cfg, cell_rows, cells)
                if g:
                    groups[cfg_key(d, K, cfg)] = g
    both = {}
    for K in K_GRID:
        for cfg in CONFIGS:
            gs = [groups.get(cfg_key(d, K, cfg)) for d in DATASETS]
            both[f"K{K}:H{cfg[1]}:{cfg[2]}:{cfg[0]}"] = dict(
                K=K, estimator=cfg[0], H=cfg[1], weighting=cfg[2],
                pass_per_dataset={d: (g["rule_pass"] if g else None) for d, g in zip(DATASETS, gs)},
                pass_both=bool(all(g is not None and g["rule_pass"] for g in gs)),
                latency_ms_per_dataset={d: (1e3 * g["total_s_median"] if g and g["total_s_median"] is not None else None) for d, g in zip(DATASETS, gs)})
    headline = [k for k, b in both.items() if b["pass_both"] and b["weighting"] == "exp" and b["estimator"] == "pf-lagnorm"]
    smallest = min((both[k]["K"] for k in headline), default=None)
    verdict = dict(
        headline_allowed=bool(headline), headline_configs=headline, smallest_passing_K_both=smallest,
        smallest_passing_configs_both=[k for k in headline if both[k]["K"] == smallest],
        passing_per_dataset={d: [k for k, g in groups.items() if g["dataset"] == d and g["rule_pass"]] for d in DATASETS},
        smallest_passing_K_per_dataset={d: min((g["K"] for g in groups.values() if g["dataset"] == d and g["rule_pass"]
                                                and g["weighting"] == "exp" and g["estimator"] == "pf-lagnorm"), default=None) for d in DATASETS},
        smallest_passing_K_asis_per_dataset={d: min((g["K"] for g in groups.values() if g["dataset"] == d and g["rule_pass"] and g["estimator"] == "asis"), default=None) for d in DATASETS},
        secondary_uniform_pass_both=[k for k, b in both.items() if b["pass_both"] and b["weighting"] == "uniform"],
        largest_tolerance={k: g["largest_tolerance"] for k, g in groups.items()})
    lag_eff = {}
    for d in DATASETS:
        for K in K_GRID:
            effs = [ci["lag_eff_median"] for ci in cells if ci.get("dataset") == d and ci.get("K") == K and ci.get("lag_eff_median")]
            if effs:
                lag_eff[f"{d}:K{K}"] = [_med([e[str(j)] for e in effs if str(j) in e]) for j in range(HMAX)]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(dict(cells=cells, groups=groups, both=both, verdict=verdict, reference=ref_stats,
                                                      reference_lag_curve=lag, lag_efficiency=lag_eff), indent=1, default=_json_default))
    (OUT / "per-config.json").write_text(json.dumps(per, default=_json_default))
    (OUT / "results-table.md").write_text(tables(groups, both, verdict, ref_stats, lag, cells, lag_eff))
    print((OUT / "results-table.md").read_text())


def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def pct(x, d=1):
    return "n/a" if x is None else f"{100 * x:.{d}f} %"


def ms(x, d=1):
    return "n/a" if x is None else f"{1e3 * x:.{d}f}"


def fms(x):
    return "n/a" if x is None else f"{x:.1f}"


def sec(x):
    return "n/a" if x is None else (f"{x:.4f}" if x < 0.1 else f"{x:.3f}" if x < 10 else f"{x:.1f}")


def tables(groups, both, verdict, ref_stats, lag, cells, lag_eff):
    L = ["## Verdict", "", "Verdict: " + json.dumps(verdict), "",
         "## Pass on both datasets per (K, H, weighting)", "",
         "| K | estimator | H | weighting | sim | real | both | latency ms sim / real (library + pooling, median) |", "|" + "---|" * 8]
    for k, b in both.items():
        L.append(f"| {b['K']} | {b['estimator']} | {b['H']} | {b['weighting']} | "
                 f"{' / '.join('PASS' if b['pass_per_dataset'][d] else ('FAIL' if b['pass_per_dataset'][d] is not None else 'missing') for d in ['sim'])} | "
                 f"{' / '.join('PASS' if b['pass_per_dataset'][d] else ('FAIL' if b['pass_per_dataset'][d] is not None else 'missing') for d in ['real'])} | "
                 f"{'**PASS**' if b['pass_both'] else 'no'} | "
                 f"{' / '.join(fms(b['latency_ms_per_dataset'][d]) for d in DATASETS)} |")
    for d in DATASETS:
        L += ["", f"## {d}: pass share per (K, H, weighting) against the frozen rule", "",
              "Pass = |P50 err| <= 2 % and |P95 err| <= 5 % vs the gated reference, no stuck chain, library call + pooling arithmetic < 0.4 s, "
              "on >= 95 % of the 300 scored ticks pooled and >= 90 % per seed, drift within 0.5 pp per seed. 'ge20' = pass share over ticks >= 20 "
              "(full pools). wESS = weight ESS of the pool (median / min over ticks). own MCSE = chain-split own MCSE of the pooled P50 (median). "
              "Latency medians are medians of the seed medians. 'largest tol.' = first (P50, P95) pair on the WP88 grid met at >= 95 % / >= 90 %.", "",
              "| K | estimator | H | weighting | pass pooled | per seed | ge20 | P50 ok | P95 ok | \\|P50 err\\| med | \\|P95 err\\| med | signed P50 | "
              "signed P95 | drift pp per seed | pool n | wESS med / min | in ref 90 % | own MCSE P50 | lib ms | pool ms | total ms | largest tol. | rule |",
              "|" + "---|" * 23]
        for K in K_GRID:
            for cfg in CONFIGS:
                g = groups.get(cfg_key(d, K, cfg))
                if not g:
                    L.append(f"| {K} | {cfg[0]} | {cfg[1]} | {cfg[2]} | missing |" + " |" * 18)
                    continue
                drift = ", ".join("n/a" if x is None else f"{100 * x:+.2f}" for x in g["drift"])
                L.append(f"| {K} | {g['estimator']} | {g['H']} | {g['weighting']} | {pct(g['pass_share'])} | "
                         f"{' / '.join(pct(p, 0) for p in g['per_seed_pass'])} | {pct(g['pass_share_ge20'])} | {pct(g['p50_ok_share'], 0)} | "
                         f"{pct(g['p95_ok_share'], 0)} | {pct(g['e50_abs_median'], 2)} | {pct(g['e95_abs_median'], 2)} | "
                         f"{pct(g['e50_signed_mean'], 2)} | {pct(g['e95_signed_mean'], 2)} | {drift} | {g['pool_n_median']:.0f} | "
                         f"{g['wess_median']:.0f} / {g['wess_min']:.0f} | {g['inside_ref90']:.3f} | {pct(g['own_mcse_median'], 2)} | "
                         f"{ms(g['lib_s_median'])} | {ms(g['pool_s_median'], 2)} | {ms(g['total_s_median'])} | {g['largest_tolerance']} | "
                         f"{'PASS' if g['rule_pass'] else 'FAIL'} |")
    L += ["", "## Latency per (dataset, K): library call per tick, 100 ticks x 3 seeds (tick 0 excluded); pooling arithmetic at H = 20 exp", "",
          "| dataset | K | lib median ms | lib p95 ms (worst seed) | pool ms H=10 / H=20 (exp, median) | total < 0.4 s (H=20 exp) | lib < 10 ms | "
          "lib < 50 ms | lib < 100 ms | arviz own MCSE P50 (H=1) | ESS h_next (H=1) | R-hat <= 1.01 (H=1) | div ticks | tick-0 s | tick-0 attempts | kept |",
          "|" + "---|" * 16]
    for d in DATASETS:
        for K in K_GRID:
            cs = [c for c in cells if c.get("dataset") == d and c.get("K") == K and c.get("median_s") is not None]
            if not cs:
                L.append(f"| {d} | {K} | missing |" + " |" * 13)
                continue
            g10, g20 = groups.get(cfg_key(d, K, ("pf-lagnorm", 10, "exp"))), groups.get(cfg_key(d, K, ("pf-lagnorm", 20, "exp")))
            L.append(f"| {d} | {K} | {1e3 * np.median([c['median_s'] for c in cs]):.1f} | {1e3 * max(c['p95_s'] for c in cs):.1f} | "
                     f"{ms(g10['pool_s_median'], 2) if g10 else 'n/a'} / {ms(g20['pool_s_median'], 2) if g20 else 'n/a'} | "
                     f"{pct(1 - g20['slow_ticks'] / g20['scored'], 1) if g20 and g20['scored'] else 'n/a'} | "
                     f"{pct(np.mean([c['frac_lt']['0.01'] for c in cs]), 0)} | {pct(np.mean([c['frac_lt']['0.05'] for c in cs]), 0)} | "
                     f"{pct(np.mean([c['frac_lt']['0.1'] for c in cs]), 0)} | {pct(np.median([c['own_mcse_rel_p50_median'] for c in cs]), 2)} | "
                     f"{np.median([c['ess_median'] for c in cs]):.0f} | {pct(np.mean([c['rhat_ok'] for c in cs if c['rhat_ok'] is not None]), 0)} | "
                     f"{sum(c['div_ticks'] for c in cs)} | {', '.join(sec(c['tick0_wall_s']) for c in cs)} | "
                     f"{', '.join(str(c['tick0_attempts']) for c in cs)} | {', '.join(str(c['kept']) for c in cs)} |")
    L += ["", "## Gated reference (4 x 2,000/20,000 per tick, every tick 0..100, per dataset; trapped-chain guard on by default)", "",
          "| dataset | ticks planned | recorded | ok | gate failed (both seeds) | second seed used | ticks with a flagged chain | flagged ticks | min chains kept | "
          "max R-hat(h_next) | rel. MCSE P50 med / max | rel. MCSE P95 med / max | min ESS | sampler wall median / max s | driver wall median s | total sampler min |",
          "|" + "---|" * 16]
    for d in DATASETS:
        s = ref_stats[d]
        m50, m95 = s["mcse_rel_p50"], s["mcse_rel_p95"]
        if s["ticks_ok"]:
            L.append(f"| {d} | {s['ticks_planned']} | {s['ticks_recorded']} | {s['ticks_ok']} | {s['gate_failed']} | {s['second_seed']} | "
                     f"{s['flagged_chain_ticks']} | {s['flagged_ticks']} | {s['kept_min']} | {s['rhat_max']:.4f} | {pct(m50['median'], 2)} / "
                     f"{pct(m50['max'], 2)} | {pct(m95['median'], 2)} / {pct(m95['max'], 2)} | {s['ess_min']:.0f} | {sec(s['wall_median'])} / "
                     f"{sec(s['wall_max'])} | {sec(s['driver_wall_median'])} | {s['wall_total_min']:.1f} |")
        else:
            L.append(f"| {d} | {s['ticks_planned']} | {s['ticks_recorded']} | 0 | {s['gate_failed']} |" + " |" * 11)
    L += ["", "## Reference lag curve per dataset: the gated reference at tick t-j against tick t (staleness with no Monte Carlo noise)", "",
          "| dataset | lag j | pairs | \\|P50 change\\| median | within 2 % | signed mean P50 | \\|P95 change\\| median | within 5 % | signed mean P95 | both within |",
          "|" + "---|" * 10]
    for d in DATASETS:
        for j, x in sorted(lag[d].items()):
            if j in (1, 2, 5, 10, 20):
                L.append(f"| {d} | {j} | {x['n']} | {pct(x['p50_abs_median'], 2)} | {pct(x['p50_within'], 0)} | {pct(x['p50_signed_mean'], 2)} | "
                         f"{pct(x['p95_abs_median'], 2)} | {pct(x['p95_within'], 0)} | {pct(x['p95_signed_mean'], 2)} | {pct(x['both_within'], 0)} |")
    L += ["", "## Importance-weight efficiency per lag group (weight ESS / draws of the group, median over ticks, median over seeds)", "",
          "| dataset | K | " + " | ".join(f"lag {j}" for j in range(HMAX)) + " |", "|" + "---|" * (HMAX + 2)]
    for key, effs in lag_eff.items():
        d, K = key.split(":")
        L.append(f"| {d} | {K[1:]} | " + " | ".join("n/a" if e is None else f"{100 * e:.0f} %" for e in effs) + " |")
    L += ["", "## Warm tick-0 fits (gated; outside the latency statistics)", "",
          "| cell | status | attempts | tick-0 seed | wall s | flagged (last attempt) | kept | tick-0 P50 err | tick-0 P95 err |", "|" + "---|" * 9]
    for c in cells:
        if c.get("status") == "missing":
            L.append(f"| {c['id']} | missing |" + " |" * 7)
            continue
        L.append(f"| {c['id']} | {c['tick0_status']} | {c['tick0_attempts']} | {c['tick0_seed']} | {sec(c['tick0_wall_s'])} | {c['tick0_flagged']} | "
                 f"{c['kept']} | {pct(c.get('tick0_e50'), 2) if c.get('tick0_e50') is not None else 'n/a'} | "
                 f"{pct(c.get('tick0_e95'), 2) if c.get('tick0_e95') is not None else 'n/a'} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
