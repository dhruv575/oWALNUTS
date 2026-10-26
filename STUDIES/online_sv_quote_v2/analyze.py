#!/usr/bin/env python3
"""WP88 analysis: gated reference, quote-error accuracy rule, latency, drift, decision rule (protocol.json).

  python analyze.py [cells-dir] [--out artifacts-dir]

Reads artifacts/cells/*/ticks.jsonl and tick-XXX.f32; writes artifacts/summary.json, artifacts/per-tick.json
and artifacts/results-table.md. Reads only.
"""
import json, sys, warnings
from pathlib import Path
import numpy as np
warnings.filterwarnings("ignore")
import arviz as az

HERE = Path(__file__).resolve().parent
PROTO = json.loads((HERE / "protocol.json").read_text())
args = [a for a in sys.argv[1:] if not a.startswith("--")]
CELLS = Path(args[0]) if args else HERE / "artifacts" / "cells"
OUT = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else HERE / "artifacts"
RHO = PROTO["model"]["rho"]
EPS_BASE = PROTO["quantities"]["eps_seed_base"]
TOL50, TOL95 = PROTO["accuracy"]["tolerance_p50"], PROTO["accuracy"]["tolerance_p95"]
THR = {int(k): v for k, v in PROTO["latency"]["threshold_s"].items()}
EXTRA_THR = PROTO["latency"]["also_reported_s"]
DRIFT_BOUND = PROTO["drift"]["bound"]
GRID = [(a, b) for a in (0.01, 0.02, 0.05, 0.10) for b in (0.02, 0.05, 0.10, 0.20)]
SEEDS = PROTO["seeds"]["arms"]
KEYS = ["sim-N250", "sim-N1000", "real-N250"]
_DATA = {}


def data(ds):
    if ds not in _DATA:
        _DATA[ds] = json.loads((HERE / "models" / f"data-{ds}.json").read_text())
    return _DATA[ds]


def records(cell):
    p = cell / "ticks.jsonl"
    if not p.exists():
        return {}
    return {r["tick"]: r for r in map(json.loads, p.read_text().splitlines()) if r.get("tick", -1) >= 0}


def load_draws(path, chains, draws):
    raw = np.frombuffer(Path(path).read_bytes(), dtype="<f4").astype(float)
    return raw.reshape(chains, draws, 3)


def h_next(a, tick, chain_idx):
    mu, ls, hl = a[..., 0], a[..., 1], a[..., 2]
    eps = np.random.default_rng(EPS_BASE + tick).normal(size=(4, 20000))[np.asarray(chain_idx), : a.shape[1]]
    return mu + RHO * (hl - mu) + np.exp(ls) * eps


def quantities(a, tick, chain_idx, full=True):
    """Quote quantities of sigma_next = exp(h_next/2) from draws a (chains, draws, 3) with eps rows chain_idx."""
    hn = h_next(a, tick, chain_idx)
    sig = np.exp(hn / 2)
    q = np.quantile(sig, [0.05, 0.5, 0.95])
    mu, ls = a[..., 0], a[..., 1]
    m = mu + RHO * (a[..., 2] - mu)
    out = dict(p5=float(q[0]), p50=float(q[1]), p95=float(q[2]), mean=float(sig.mean()),
               straddle=float(np.mean(np.exp(m / 2 + np.exp(2 * ls) / 8))),
               med_ls=np.median(ls, axis=1).tolist(), med_hl=np.median(a[..., 2], axis=1).tolist(),
               med_ls_all=float(np.median(ls)), med_hl_all=float(np.median(a[..., 2])),
               hn_p5=float(np.quantile(hn, 0.05)), hn_p95=float(np.quantile(hn, 0.95)))
    if full:
        out["ess"] = float(az.ess(hn))
        out["rhat"] = float(az.rhat(hn)) if hn.shape[0] > 1 else float("nan")
        out["mcse_rel_p50"] = float(az.mcse(sig, method="quantile", prob=0.5)) / out["p50"]
        out["mcse_rel_p95"] = float(az.mcse(sig, method="quantile", prob=0.95)) / out["p95"]
    return out


def ref_key(c):
    return f"{c['ds']}-N{c['N']}"


# ── references ──────────────────────────────────────────────────────────────────────────────

def load_references():
    refs, stats = {}, {}
    for key in KEYS:
        cell = CELLS / f"ref-{key}"
        recs = records(cell)
        refs[key] = {}
        st = dict(ticks_planned=len(PROTO["reference"]["ticks"][key]), ticks_recorded=len(recs), ticks_ok=0,
                  gate_failed=0, second_seed=0, flagged_chain_ticks=0, kept_min=4, rhat_max=0.0,
                  attempt_gates=[], wall_median=None, mcse_rel_p50=[], mcse_rel_p95=[], ess_min=None)
        walls = []
        for t, r in sorted(recs.items()):
            st["attempt_gates"].append([a.get("gate") for a in r.get("attempts", [])])
            if r["status"] != "ok":
                st["gate_failed"] += 1
                continue
            st["ticks_ok"] += 1
            st["second_seed"] += int(r["attempt"] > 0)
            st["flagged_chain_ticks"] += int(len(r["flagged"]) > 0)
            st["kept_min"] = min(st["kept_min"], len(r["kept"]))
            st["rhat_max"] = max(st["rhat_max"], r["rhat_h_next"])
            walls.append(sum(a.get("wall_seconds") or 0 for a in r["attempts"]))
            a = load_draws(cell / r["file"], r["chains"], r["draws"])[r["kept"]]
            q = quantities(a, t, r["kept"])
            q.update(kept=r["kept"], flagged=r["flagged"], attempt=r["attempt"], wall=r["wall_seconds"])
            refs[key][t] = q
            st["mcse_rel_p50"].append(q["mcse_rel_p50"])
            st["mcse_rel_p95"].append(q["mcse_rel_p95"])
            st["ess_min"] = q["ess"] if st["ess_min"] is None else min(st["ess_min"], q["ess"])
        for k in ("mcse_rel_p50", "mcse_rel_p95"):
            v = np.array(st[k])
            st[k] = dict(median=float(np.median(v)), p95=float(np.quantile(v, .95)), max=float(v.max())) if len(v) else None
        st["wall_median"] = float(np.median(walls)) if walls else None
        st["wall_total_min"] = float(np.sum(walls) / 60) if walls else None
        stats[key] = st
    return refs, stats


# ── arms ────────────────────────────────────────────────────────────────────────────────────

def stuck_chains(q, ref):
    return [c for c in range(len(q["med_ls"]))
            if abs(q["med_ls"][c] - ref["med_ls_all"]) > 1.0 or abs(q["med_hl"][c] - ref["med_hl_all"]) > 2.0]


def score_tick(cell, rec, t, ref, chain_idx, thr):
    """One scored tick for one variant (chain subset). Returns the per-tick dict."""
    a = load_draws(cell / f"tick-{t:03}.f32", rec["chains"], rec["draws"])[chain_idx]
    q = quantities(a, t, chain_idx)
    e50, e95 = q["p50"] / ref["p50"] - 1, q["p95"] / ref["p95"] - 1
    e5, emean = q["p5"] / ref["p5"] - 1, q["mean"] / ref["mean"] - 1
    stuck = stuck_chains(q, ref)
    accurate = abs(e50) <= TOL50 and abs(e95) <= TOL95 and not stuck
    wall = rec["wall_seconds"]
    out = dict(tick=t, ok=True, wall=wall, e50=e50, e95=e95, e5=e5, emean=emean, stuck=stuck,
               accurate=bool(accurate), fast=bool(wall < thr), passed=bool(accurate and wall < thr),
               ess=q["ess"], rhat=q["rhat"], mcse_rel_p50=q["mcse_rel_p50"], mcse_rel_p95=q["mcse_rel_p95"],
               div=int(sum(rec.get("divergences", []))), straddle_err=q["straddle"] / ref["straddle"] - 1,
               grid=[bool(abs(e50) <= g50 and abs(e95) <= g95 and not stuck) for g50, g95 in GRID],
               fast_extra={str(x): bool(wall < x) for x in EXTRA_THR},
               inside_ref90=float(np.mean((h_next(a, t, chain_idx) >= ref["hn_p5"]) & (h_next(a, t, chain_idx) <= ref["hn_p95"]))))
    return out


def failed_tick(t, reason, wall=None):
    return dict(tick=t, ok=False, reason=reason, wall=wall, accurate=False, fast=bool(wall is not None and wall < 1e9),
                passed=False, stuck=[], grid=[False] * len(GRID), fast_extra={str(x): False for x in EXTRA_THR})


def analyze_cell(c, refs):
    cell = CELLS / c["id"]
    recs = records(cell)
    key = ref_key(c)
    thr = THR[c["N"]]
    ref_ticks = [t for t in PROTO["reference"]["ticks"][key] if 1 <= t <= c["ticks"]]
    variants = {"as_sampled": None}
    if c["arm"] == "refit":
        variants["gated"] = "flags"
    rows, per = [], {}
    for vname, vmode in variants.items():
        scored = []
        for t in ref_ticks:
            r, ref = recs.get(t), refs[key].get(t)
            if r is None or r.get("status") != "ok":
                scored.append(failed_tick(t, "arm_error_or_missing", r.get("wall_seconds") if r else None))
                continue
            if ref is None:
                scored.append(failed_tick(t, "no_reference", r["wall_seconds"]))
                continue
            idx = list(range(r["chains"]))
            if vmode == "flags":
                idx = [i for i in idx if i not in r.get("flagged", [])]
                if len(idx) < 2:
                    scored.append(failed_tick(t, "gate_below_2_chains", r["wall_seconds"]))
                    continue
            scored.append(score_tick(cell, r, t, ref, idx, thr))
        # latency over every tick >= 1 the arm ran (error ticks count as infinite)
        walls = np.array([recs[t]["wall_seconds"] if recs.get(t, {}).get("status") == "ok" else np.inf
                          for t in range(1, c["ticks"] + 1)])
        n_ok = int(np.isfinite(walls).sum())
        row = dict(id=c["id"], arm=c["arm"], variant=vname, ds=c["ds"], N=c["N"], K=c.get("K"), seed=c.get("seed"),
                   key=key, ticks=c["ticks"], ticks_ok=n_ok, scored=len(scored),
                   accurate=int(sum(s["accurate"] for s in scored)), passed=int(sum(s["passed"] for s in scored)),
                   stuck_ticks=int(sum(1 for s in scored if s["stuck"])),
                   unscored=int(sum(1 for s in scored if not s["ok"])),
                   median_s=float(np.median(walls)) if n_ok else None,
                   p95_s=float(np.quantile(walls, .95)) if n_ok else None, max_s=float(walls.max()) if n_ok else None,
                   frac_lt_thr=float(np.mean(walls < thr)),
                   frac_lt={str(x): float(np.mean(walls < x)) for x in EXTRA_THR + [0.4, 2.0]},
                   grid=[int(sum(s["grid"][i] for s in scored)) for i in range(len(GRID))],
                   e50_abs_median=_med([abs(s["e50"]) for s in scored if s["ok"]]),
                   e50_abs_p95=_q95([abs(s["e50"]) for s in scored if s["ok"]]),
                   e95_abs_median=_med([abs(s["e95"]) for s in scored if s["ok"]]),
                   e95_abs_p95=_q95([abs(s["e95"]) for s in scored if s["ok"]]),
                   e50_signed_mean=_mean([s["e50"] for s in scored if s["ok"]]),
                   e95_signed_mean=_mean([s["e95"] for s in scored if s["ok"]]),
                   own_mcse_rel_p50_median=_med([s["mcse_rel_p50"] for s in scored if s["ok"]]),
                   ess_median=_med([s["ess"] for s in scored if s["ok"]]),
                   rhat_ok=_mean([s["rhat"] <= 1.01 for s in scored if s["ok"] and np.isfinite(s["rhat"])]),
                   div_ticks=int(sum(1 for s in scored if s.get("div", 0) > 0)),
                   inside_ref90=_mean([s["inside_ref90"] for s in scored if s["ok"]]))
        early = [s["e50"] for s in scored if s["ok"] and s["tick"] <= 30]
        late = [s["e50"] for s in scored if s["ok"] and s["tick"] >= 70]
        if c["arm"] in ("warm", "pyextra"):
            row["drift"] = float(np.mean(late) - np.mean(early)) if early and late else None
            row["drift_ok"] = bool(row["drift"] is not None and abs(row["drift"]) <= DRIFT_BOUND)
            row["drift_n"] = [len(early), len(late)]
            t0 = recs.get(0, {})
            row["tick0_wall_s"] = t0.get("wall_seconds")
            row["tick0_flagged"] = t0.get("flagged", [])
            row["kept"] = t0.get("kept", list(range(4)))
            ref0 = refs[key].get(0)
            if t0.get("status") == "ok" and ref0 is not None and (cell / "tick-000.f32").exists():
                s0 = score_tick(cell, t0, 0, ref0, list(range(t0["chains"])), np.inf)
                row["tick0_e50"], row["tick0_e95"], row["tick0_stuck"] = s0["e50"], s0["e95"], s0["stuck"]
        if c["arm"] == "refit":
            row["flagged_ticks"] = int(sum(1 for t in range(1, c["ticks"] + 1) if recs.get(t, {}).get("flagged")))
        if c["ds"] == "sim":
            cov = []
            for s in scored:
                if not s["ok"]:
                    continue
                r = recs[s["tick"]]
                a = load_draws(cell / f"tick-{s['tick']:03}.f32", r["chains"], r["draws"])
                hn = h_next(a, s["tick"], list(range(r["chains"])))
                truth = data("sim")["h"][c["N"] + s["tick"]]
                ql, qh = np.quantile(hn, [0.05, 0.95])
                cov.append(ql <= truth <= qh)
            row["truth_cov90"] = _mean(cov)
        rows.append(row)
        per[f"{c['id']}:{vname}"] = scored
    return rows, per


def _med(v):
    return float(np.median(v)) if len(v) else None


def _q95(v):
    return float(np.quantile(v, .95)) if len(v) else None


def _mean(v):
    return float(np.mean(v)) if len(v) else None


# ── groups and verdict ──────────────────────────────────────────────────────────────────────

def group(rows, pred):
    rs = [r for r in rows if pred(r)]
    if not rs:
        return None
    scored, passed, acc = sum(r["scored"] for r in rs), sum(r["passed"] for r in rs), sum(r["accurate"] for r in rs)
    g = dict(cells=[r["id"] for r in rs], n_cells=len(rs), scored=scored, passed=passed, accurate=acc,
             pass_share=passed / scored if scored else None, accurate_share=acc / scored if scored else None,
             per_seed_pass=[r["passed"] / r["scored"] if r["scored"] else None for r in rs],
             per_seed_accurate=[r["accurate"] / r["scored"] if r["scored"] else None for r in rs],
             stuck_ticks=sum(r["stuck_ticks"] for r in rs), unscored=sum(r["unscored"] for r in rs),
             median_s=_med([r["median_s"] for r in rs if r["median_s"] is not None]),
             p95_s=max((r["p95_s"] for r in rs if r["p95_s"] is not None), default=None),
             max_s=max((r["max_s"] for r in rs if r["max_s"] is not None), default=None),
             frac_lt_thr=_mean([r["frac_lt_thr"] for r in rs]),
             frac_lt={k: _mean([r["frac_lt"][k] for r in rs]) for k in rs[0]["frac_lt"]},
             e50_abs_median=_med([r["e50_abs_median"] for r in rs if r["e50_abs_median"] is not None]),
             e95_abs_median=_med([r["e95_abs_median"] for r in rs if r["e95_abs_median"] is not None]),
             e50_signed_mean=_mean([r["e50_signed_mean"] for r in rs if r["e50_signed_mean"] is not None]),
             e95_signed_mean=_mean([r["e95_signed_mean"] for r in rs if r["e95_signed_mean"] is not None]),
             own_mcse_rel_p50_median=_med([r["own_mcse_rel_p50_median"] for r in rs if r["own_mcse_rel_p50_median"] is not None]),
             grid_share=[sum(r["grid"][i] for r in rs) / scored if scored else None for i in range(len(GRID))],
             grid_per_seed_min=[min((r["grid"][i] / r["scored"]) if r["scored"] else 0 for r in rs) for i in range(len(GRID))])
    if all("drift" in r for r in rs):
        g["drift"] = [r["drift"] for r in rs]
        g["drift_ok_all"] = all(r["drift_ok"] for r in rs)
        g["drift_common_sign"] = bool(all(d is not None for d in g["drift"]) and
                                      (all(d > 0 for d in g["drift"]) or all(d < 0 for d in g["drift"])))
        g["tick0_wall_s"] = [r.get("tick0_wall_s") for r in rs]
        g["tick0_flagged"] = [r.get("tick0_flagged") for r in rs]
    if all("flagged_ticks" in r for r in rs):
        g["flagged_ticks"] = sum(r["flagged_ticks"] for r in rs)
    # largest tolerance met: the first grid pair (ordered by P50 then P95) with pooled >= 0.95 and every seed >= 0.90
    met = None
    for i, (a, b) in enumerate(GRID):
        if g["grid_share"][i] is not None and g["grid_share"][i] >= 0.95 and g["grid_per_seed_min"][i] >= 0.90:
            met = (a, b)
            break
    g["largest_tolerance_met"] = met
    g["rule_pass"] = bool(g["pass_share"] is not None and g["pass_share"] >= 0.95 and
                          all(p is not None and p >= 0.90 for p in g["per_seed_pass"]) and
                          (g.get("drift_ok_all", True)))
    return g


def main():
    refs, ref_stats = load_references()
    rows, per = [], {}
    for c in PROTO["cells"]:
        if c["arm"] == "ref":
            continue
        if not (CELLS / c["id"] / "ticks.jsonl").exists():
            rows.append(dict(id=c["id"], arm=c["arm"], variant="as_sampled", ds=c["ds"], N=c["N"], K=c.get("K"),
                             seed=c.get("seed"), key=ref_key(c), status="missing", scored=0, passed=0, accurate=0,
                             stuck_ticks=0, unscored=0, ticks=c["ticks"], ticks_ok=0, median_s=None, p95_s=None, max_s=None,
                             frac_lt_thr=0.0, frac_lt={str(x): 0.0 for x in EXTRA_THR + [0.4, 2.0]}, grid=[0] * len(GRID),
                             e50_abs_median=None, e95_abs_median=None, e50_signed_mean=None, e95_signed_mean=None,
                             own_mcse_rel_p50_median=None, e50_abs_p95=None, e95_abs_p95=None, ess_median=None, rhat_ok=None,
                             div_ticks=0, inside_ref90=None))
            continue
        r, p = analyze_cell(c, refs)
        rows += r
        per.update(p)
    groups, verdict = {}, {}
    for K in PROTO["arms"]["K"]:
        for key in KEYS:
            g = group(rows, lambda r: r["arm"] == "warm" and r["K"] == K and r["key"] == key)
            groups[f"warm{K}:{key}"] = g
        ok = all(groups[f"warm{K}:{key}"] is not None and groups[f"warm{K}:{key}"]["rule_pass"] for key in KEYS)
        verdict[f"K{K}"] = dict(realtime=bool(ok), per_key={key: (groups[f"warm{K}:{key}"] or {}).get("rule_pass") for key in KEYS})
    verdict["realtime_claim_allowed"] = any(verdict[f"K{K}"]["realtime"] for K in PROTO["arms"]["K"])
    verdict["realtime_K"] = [K for K in PROTO["arms"]["K"] if verdict[f"K{K}"]["realtime"]]
    for arm in ("refit", "cmdstan", "nutpie"):
        for variant in (("as_sampled", "gated") if arm == "refit" else ("as_sampled",)):
            for key in KEYS:
                groups[f"{arm}:{variant}:{key}"] = group(rows, lambda r: r["arm"] == arm and r["variant"] == variant and r["key"] == key)
    groups["pyextra:sim-N250"] = group(rows, lambda r: r["arm"] == "pyextra")
    groups["warm200-s880101:sim-N250"] = group(rows, lambda r: r["id"] == "warm200-sim-N250-s880101")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(dict(rows=rows, groups=groups, verdict=verdict, references=ref_stats,
                                                      grid=GRID), indent=1, default=_json_default))
    (OUT / "per-tick.json").write_text(json.dumps(per, default=_json_default))
    (OUT / "results-table.md").write_text(tables(groups, verdict, ref_stats, rows))
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


def sec(x):
    return "n/a" if x is None else (f"{x:.3f}" if x < 10 else f"{x:.1f}")


def tables(groups, verdict, ref_stats, rows):
    L = ["## Warm arm (library `run_warm`) against the frozen rule", "",
         "Pass = accurate (|P50 err| <= 2 %, |P95 err| <= 5 %, no stuck chain) AND under the latency threshold "
         "(0.4 s at N = 250, 2 s at N = 1,000) on >= 95 % of scored ticks pooled and >= 90 % per seed, drift within 0.5 % "
         "per seed. Latency shares are over all 100 ticks; medians are the median of the seed medians, p95 the worst seed.", "",
         "| K | dataset-N | scored | pass pooled | pass per seed | accurate | median s | p95 s | < thr | < 0.1 s | < 0.5 s | "
         "|P50 err| med | |P95 err| med | own MCSE P50 | stuck | drift per seed (pp) | largest tol. met | rule |",
         "|" + "---|" * 18]
    for K in PROTO["arms"]["K"]:
        for key in KEYS:
            g = groups.get(f"warm{K}:{key}")
            if not g:
                L.append(f"| {K} | {key} | missing |" + " |" * 15)
                continue
            drift = ", ".join("n/a" if d is None else f"{100 * d:+.2f}" for d in g.get("drift", [])) or "n/a"
            tol = "none" if g["largest_tolerance_met"] is None else f"{100 * g['largest_tolerance_met'][0]:.0f} / {100 * g['largest_tolerance_met'][1]:.0f} %"
            L.append(f"| {K} | {key} | {g['scored']} | {pct(g['pass_share'])} | "
                     f"{' / '.join(pct(p, 0) for p in g['per_seed_pass'])} | {pct(g['accurate_share'])} | {sec(g['median_s'])} | "
                     f"{sec(g['p95_s'])} | {pct(g['frac_lt_thr'], 0)} | {pct(g['frac_lt']['0.1'], 0)} | {pct(g['frac_lt']['0.5'], 0)} | "
                     f"{pct(g['e50_abs_median'], 2)} | {pct(g['e95_abs_median'], 2)} | {pct(g['own_mcse_rel_p50_median'], 2)} | "
                     f"{g['stuck_ticks']} | {drift} | {tol} | {'PASS' if g['rule_pass'] else 'FAIL'} |")
    L += ["", "Verdict: " + json.dumps(verdict), ""]
    L += ["## Full-refit baselines (20 ticks per seed; scored at the reference ticks within them)", "",
          "| arm | variant | dataset-N | scored | accurate | pass (acc. and < thr) | stuck ticks / 60 | flagged ticks (oWALNUTS) | "
          "median s | p95 s | max s | < thr | |P50 err| med | |P95 err| med |", "|" + "---|" * 14]
    for arm in ("refit", "cmdstan", "nutpie"):
        for variant in (("as_sampled", "gated") if arm == "refit" else ("as_sampled",)):
            for key in KEYS:
                g = groups.get(f"{arm}:{variant}:{key}")
                if not g:
                    continue
                name = {"refit": "oWALNUTS refit", "cmdstan": "CmdStan 2.39.0", "nutpie": "nutpie 0.16.8"}[arm]
                L.append(f"| {name} | {variant} | {key} | {g['scored']} | {pct(g['accurate_share'])} | {pct(g['pass_share'])} | "
                         f"{g['stuck_ticks']} | {g.get('flagged_ticks', 'n/a')} | {sec(g['median_s'])} | {sec(g['p95_s'])} | "
                         f"{sec(g['max_s'])} | {pct(g['frac_lt_thr'], 0)} | {pct(g['e50_abs_median'], 2)} | {pct(g['e95_abs_median'], 2)} |")
    L += ["", "## Gated reference (4 x 2,000/20,000 per tick)", "",
          "| dataset-N | ticks planned | ok | gate failed (both seeds) | second seed used | ticks with a flagged chain dropped | "
          "min chains kept | max R-hat(h_next) | rel. MCSE P50 med / max | rel. MCSE P95 med / max | min ESS | median wall s | total min |",
          "|" + "---|" * 13]
    for key in KEYS:
        s = ref_stats[key]
        m50, m95 = s["mcse_rel_p50"], s["mcse_rel_p95"]
        L.append(f"| {key} | {s['ticks_planned']} | {s['ticks_ok']} | {s['gate_failed']} | {s['second_seed']} | "
                 f"{s['flagged_chain_ticks']} | {s['kept_min']} | {s['rhat_max']:.4f} | "
                 f"{pct(m50['median'], 2) if m50 else 'n/a'} / {pct(m50['max'], 2) if m50 else 'n/a'} | "
                 f"{pct(m95['median'], 2) if m95 else 'n/a'} / {pct(m95['max'], 2) if m95 else 'n/a'} | "
                 f"{s['ess_min']:.0f} | {sec(s['wall_median'])} | {s['wall_total_min']:.1f} |" if s["ticks_ok"] else
                 f"| {key} | {s['ticks_planned']} | 0 | {s['gate_failed']} | | | | | | | | | |")
    g, w = groups.get("pyextra:sim-N250"), groups.get("warm200-s880101:sim-N250")
    L += ["", "## Python `owalnuts.sample_warm` path (sim N = 250, K = 200, seed 880101) vs the Rust cell", ""]
    if g and w:
        L += ["| path | median s | p95 s | < 0.4 s | < 0.1 s | accurate | pass | |P50 err| med | drift (pp) | tick-0 s |", "|" + "---|" * 10]
        for name, x in (("Python sample_warm (C-ABI target, 4 threads)", g), ("Rust run_warm", w)):
            L.append(f"| {name} | {sec(x['median_s'])} | {sec(x['p95_s'])} | {pct(x['frac_lt']['0.4'], 0)} | {pct(x['frac_lt']['0.1'], 0)} | "
                     f"{pct(x['accurate_share'])} | {pct(x['pass_share'])} | {pct(x['e50_abs_median'], 2)} | "
                     f"{', '.join('n/a' if d is None else f'{100 * d:+.2f}' for d in x.get('drift', [])) or 'n/a'} | "
                     f"{', '.join(sec(t) for t in x.get('tick0_wall_s', [])) or 'n/a'} |")
        if g["median_s"] and w["median_s"]:
            L.append(f"\nPython / Rust median latency ratio: {g['median_s'] / w['median_s']:.2f}.")
    else:
        L.append("missing")
    L += ["", "## Warm tick-0 fits (4 x 1,000/1,000 at defaults; outside the latency statistics)", "",
          "| cell | wall s | flagged chains | kept | tick-0 P50 err | tick-0 P95 err |", "|---|---|---|---|---|---|"]
    for r in rows:
        if r["arm"] == "warm" and r.get("tick0_wall_s") is not None:
            L.append(f"| {r['id']} | {sec(r['tick0_wall_s'])} | {r['tick0_flagged']} | {r['kept']} | "
                     f"{pct(r.get('tick0_e50'), 2) if r.get('tick0_e50') is not None else 'n/a'} | "
                     f"{pct(r.get('tick0_e95'), 2) if r.get('tick0_e95') is not None else 'n/a'} |")
    L += ["", "## Tolerance grid: share of scored ticks within (P50, P95) tolerance, pooled (no latency condition)", "",
          "| arm | dataset-N | " + " | ".join(f"{100 * a:.0f}/{100 * b:.0f}" for a, b in GRID) + " |", "|" + "---|" * (2 + len(GRID))]
    for name in [f"warm{K}" for K in PROTO["arms"]["K"]] + ["refit:as_sampled", "refit:gated", "cmdstan:as_sampled", "nutpie:as_sampled", "pyextra"]:
        for key in KEYS:
            g = groups.get(f"{name}:{key}") if name != "pyextra" else (groups.get("pyextra:sim-N250") if key == "sim-N250" else None)
            if g:
                L.append(f"| {name} | {key} | " + " | ".join(pct(x, 0) for x in g["grid_share"]) + " |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
