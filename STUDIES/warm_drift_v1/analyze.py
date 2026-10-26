#!/usr/bin/env python3
"""WP96 analysis: gated reference, quote-error rule per half, drift, latency (median/P99), trigger firings, cost
statistic, decision rule (protocol.json).

  python analyze.py [cells-dir] [--out artifacts-dir]

Reads <cells>/*/ticks.jsonl and tick-XXXX*.f32; writes summary.json, per-tick.json and results-table.md. Reads only.
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
HALVES = {"half1": PROTO["accuracy"]["scored_ticks"]["half1"], "half2": PROTO["accuracy"]["scored_ticks"]["half2"]}
DRIFT_BOUND = PROTO["drift"]["bound"]
SHIFT_TICK = PROTO["data"]["shift_tick"]
STREAMS = ["shift", "control"]
POLICIES = ["frozen", "m100", "m500", "trig"]
SEEDS = PROTO["seeds"]["arms"]
_DATA = {}


def data(stream):
    if stream not in _DATA:
        _DATA[stream] = json.loads((HERE / "models" / f"data-{stream}.json").read_text())
    return _DATA[stream]


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


def quantities(a, tick, chain_idx):
    hn = h_next(a, tick, chain_idx)
    sig = np.exp(hn / 2)
    q = np.quantile(sig, [0.05, 0.5, 0.95])
    ls = a[..., 1]
    out = dict(p5=float(q[0]), p50=float(q[1]), p95=float(q[2]), mean=float(sig.mean()),
               med_ls=np.median(ls, axis=1).tolist(), med_hl=np.median(a[..., 2], axis=1).tolist(),
               med_ls_all=float(np.median(ls)), med_hl_all=float(np.median(a[..., 2])),
               hn_p5=float(np.quantile(hn, 0.05)), hn_p95=float(np.quantile(hn, 0.95)),
               ess=float(az.ess(hn)), rhat=float(az.rhat(hn)) if hn.shape[0] > 1 else float("nan"),
               mcse_rel_p50=float(az.mcse(sig, method="quantile", prob=0.5)) / float(q[1]),
               mcse_rel_p95=float(az.mcse(sig, method="quantile", prob=0.95)) / float(q[2]))
    return out


# ── references ──────────────────────────────────────────────────────────────────────────────

def load_references():
    refs, stats = {}, {}
    for stream in STREAMS:
        cell = CELLS / f"ref-{stream}"
        recs = records(cell)
        refs[stream] = {}
        st = dict(ticks_planned=len(PROTO["reference"]["ticks"]), ticks_recorded=len(recs), ticks_ok=0, gate_failed=0,
                  second_seed=0, flagged_chain_ticks=0, kept_min=4, rhat_max=0.0, wall_median=None, ess_min=None,
                  mcse_rel_p50={"half1": [], "half2": []}, mcse_rel_p95={"half1": [], "half2": []})
        walls = []
        for t, r in sorted(recs.items()):
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
            refs[stream][t] = q
            half = "half1" if t <= SHIFT_TICK else "half2"
            st["mcse_rel_p50"][half].append(q["mcse_rel_p50"])
            st["mcse_rel_p95"][half].append(q["mcse_rel_p95"])
            st["ess_min"] = q["ess"] if st["ess_min"] is None else min(st["ess_min"], q["ess"])
        for k in ("mcse_rel_p50", "mcse_rel_p95"):
            st[k] = {h: (dict(median=float(np.median(v)), max=float(np.max(v))) if v else None) for h, v in st[k].items()}
        st["wall_median"] = float(np.median(walls)) if walls else None
        st["wall_total_min"] = float(np.sum(walls) / 60) if walls else None
        stats[stream] = st
    return refs, stats


# ── arms ────────────────────────────────────────────────────────────────────────────────────

def stuck_chains(q, ref):
    return [c for c in range(len(q["med_ls"]))
            if abs(q["med_ls"][c] - ref["med_ls_all"]) > 1.0 or abs(q["med_hl"][c] - ref["med_hl_all"]) > 2.0]


def score_tick(cell, rec, t, ref, stream):
    idx = list(range(rec["chains"]))
    a = load_draws(cell / f"tick-{t:04}.f32", rec["chains"], rec["draws"])
    q = quantities(a, t, rec.get("kept", idx))
    e50, e95 = q["p50"] / ref["p50"] - 1, q["p95"] / ref["p95"] - 1
    stuck = stuck_chains(q, ref)
    hn = h_next(a, t, rec.get("kept", idx))
    truth = data(stream)["h"][PROTO["stream"]["N"] + t]
    ql, qh = np.quantile(hn, [0.05, 0.95])
    return dict(tick=t, ok=True, wall=rec["wall_seconds"], e50=e50, e95=e95, e5=q["p5"] / ref["p5"] - 1,
                emean=q["mean"] / ref["mean"] - 1, stuck=stuck, accurate=bool(abs(e50) <= TOL50 and abs(e95) <= TOL95 and not stuck),
                ess=q["ess"], rhat=q["rhat"], mcse_rel_p50=q["mcse_rel_p50"], mcse_rel_p95=q["mcse_rel_p95"],
                div=int(sum(rec.get("divergences", []))), readapt=bool(rec.get("readapt")),
                inside_ref90=float(np.mean((hn >= ref["hn_p5"]) & (hn <= ref["hn_p95"]))), truth_cov90=bool(ql <= truth <= qh))


def failed_tick(t, reason, wall=None):
    return dict(tick=t, ok=False, reason=reason, wall=wall, accurate=False, stuck=[])


def _med(v):
    return float(np.median(v)) if len(v) else None


def _mean(v):
    return float(np.mean(v)) if len(v) else None


def _q(v, p):
    return float(np.quantile(v, p)) if len(v) else None


def analyze_cell(c, refs):
    cell = CELLS / c["id"]
    recs = records(cell)
    stream = c["stream"]
    row = dict(id=c["id"], arm="warm", policy=c["policy_name"], stream=stream, seed=c["seed"], ticks=c["ticks"])
    t0 = recs.get(0, {})
    row.update(tick0_wall_s=t0.get("wall_seconds"), tick0_flagged=t0.get("flagged", []), kept=t0.get("kept", list(range(4))),
               tick0_status=t0.get("status"))
    per = {}
    for half, ticks in HALVES.items():
        scored = []
        for t in ticks:
            r, ref = recs.get(t), refs[stream].get(t)
            if r is None or r.get("status") != "ok" or not (cell / f"tick-{t:04}.f32").exists():
                scored.append(failed_tick(t, "arm_error_or_missing", r.get("wall_seconds") if r else None))
            elif ref is None:
                scored.append(failed_tick(t, "no_reference", r["wall_seconds"]))
            else:
                scored.append(score_tick(cell, r, t, ref, stream))
        ok = [s for s in scored if s["ok"]]
        early, late = [s["e50"] for s in ok if s["tick"] <= ticks[9]], [s["e50"] for s in ok if s["tick"] >= ticks[-10]]
        drift = float(np.mean(late) - np.mean(early)) if early and late else None
        row[half] = dict(scored=len(scored), accurate=int(sum(s["accurate"] for s in scored)),
                         stuck_ticks=int(sum(1 for s in scored if s["stuck"])), unscored=int(sum(1 for s in scored if not s["ok"])),
                         e50_abs_median=_med([abs(s["e50"]) for s in ok]), e95_abs_median=_med([abs(s["e95"]) for s in ok]),
                         e50_abs_p95=_q([abs(s["e50"]) for s in ok], .95), e95_abs_p95=_q([abs(s["e95"]) for s in ok], .95),
                         e50_signed_mean=_mean([s["e50"] for s in ok]), e95_signed_mean=_mean([s["e95"] for s in ok]),
                         own_mcse_rel_p50_median=_med([s["mcse_rel_p50"] for s in ok]), ess_median=_med([s["ess"] for s in ok]),
                         rhat_ok=_mean([s["rhat"] <= 1.01 for s in ok if np.isfinite(s["rhat"])]),
                         div_ticks=int(sum(1 for s in ok if s["div"] > 0)), inside_ref90=_mean([s["inside_ref90"] for s in ok]),
                         truth_cov90=_mean([s["truth_cov90"] for s in ok]),
                         drift=drift, drift_ok=bool(drift is not None and abs(drift) <= DRIFT_BOUND), drift_n=[len(early), len(late)])
        per[f"{c['id']}:{half}"] = scored
    ref0 = refs[stream].get(0)
    if t0.get("status") == "ok" and ref0 is not None and (cell / "tick-0000.f32").exists():
        s0 = score_tick(cell, dict(t0, kept=list(range(t0["chains"]))), 0, ref0, stream)
        row.update(tick0_e50=s0["e50"], tick0_e95=s0["e95"], tick0_stuck=s0["stuck"], tick0_accurate=s0["accurate"])
    # latency over every tick >= 1 the arm ran (missing/error ticks count as infinite)
    walls = np.array([recs[t]["wall_seconds"] if recs.get(t, {}).get("status") == "ok" else np.inf for t in range(1, c["ticks"] + 1)])
    n_ok = int(np.isfinite(walls).sum())
    ra = [t for t in range(1, c["ticks"] + 1) if recs.get(t, {}).get("readapt")]
    ra_walls = np.array([recs[t]["wall_seconds"] for t in ra if recs[t].get("status") == "ok"])
    ra_flag = [t for t in ra if (recs[t].get("readapt_info") or {}).get("flagged")]
    ra_err = [t for t in ra if (recs[t].get("readapt_info") or {}).get("status") == "error"]
    w1 = walls[: SHIFT_TICK] if len(walls) >= SHIFT_TICK else walls
    w2 = walls[SHIFT_TICK:]
    row.update(ticks_ok=n_ok, median_s=_med(walls) if n_ok else None, p99_s=_q(walls, .99) if n_ok else None,
               max_s=float(walls[np.isfinite(walls)].max()) if n_ok else None, frac_lt_04=float(np.mean(walls < 0.4)),
               median_half1_s=_med(w1[np.isfinite(w1)]), median_half2_s=_med(w2[np.isfinite(w2)]),
               readapt_ticks=ra, readapt_count=len(ra), readapt_median_s=_med(ra_walls), readapt_max_s=float(ra_walls.max()) if len(ra_walls) else None,
               readapt_flagged_ticks=ra_flag, readapt_error_ticks=ra_err,
               first_readapt_after_shift=next((t for t in ra if t > SHIFT_TICK), None),
               readapts_after_shift=[t for t in ra if t > SHIFT_TICK])
    # cost statistic C_t (evals per transition) per 250-tick block, relative to ticks 1-20
    ev = np.array([recs.get(t, {}).get("evals_per_transition", np.nan) for t in range(1, c["ticks"] + 1)])
    base = np.nanmean(ev[:20]) if len(ev) >= 20 else np.nan
    row["cost_baseline"] = float(base) if np.isfinite(base) else None
    row["cost_ratio_by_block"] = [float(np.nanmean(ev[i:i + 250]) / base) if np.isfinite(base) and np.isfinite(np.nanmean(ev[i:i + 250])) else None
                                  for i in range(0, c["ticks"], 250)]
    row["step_ratio_by_block"] = [float(np.nanmean([recs.get(t, {}).get("step_ratio", np.nan) for t in range(i + 1, i + 251)]))
                                  for i in range(0, c["ticks"], 250)]
    row["unchanged_frac_max"] = float(np.nanmax([recs.get(t, {}).get("unchanged_frac", np.nan) for t in range(1, c["ticks"] + 1)])) if n_ok else None
    if c["policy_name"] == "trig":
        trig = [(t, recs[t]["trigger"]) for t in range(1, c["ticks"] + 1) if recs.get(t, {}).get("trigger") and recs[t]["trigger"].get("armed")]
        row["trigger_fired_ticks"] = [t for t, g in trig if g.get("fired")]
        row["trigger_ratio_max"] = max((g["ratio"] for _, g in trig), default=None)
        row["trigger_ratio_at_fire"] = [(t, g["ratio"], g["stuck"]) for t, g in trig if g.get("fired")]
    return row, per


# ── groups and verdict ──────────────────────────────────────────────────────────────────────

def group(rows, policy, stream):
    rs = [r for r in rows if r["policy"] == policy and r["stream"] == stream]
    if not rs:
        return None
    g = dict(cells=[r["id"] for r in rs], n_cells=len(rs), halves={})
    for half in HALVES:
        hs = [r[half] for r in rs if half in r]
        scored, acc = sum(h["scored"] for h in hs), sum(h["accurate"] for h in hs)
        per_seed = [h["accurate"] / h["scored"] if h["scored"] else 0.0 for h in hs]
        g["halves"][half] = dict(scored=scored, accurate=acc, pass_share=acc / scored if scored else None, per_seed=per_seed,
                                 stuck_ticks=sum(h["stuck_ticks"] for h in hs), unscored=sum(h["unscored"] for h in hs),
                                 e50_abs_median=_med([h["e50_abs_median"] for h in hs if h["e50_abs_median"] is not None]),
                                 e95_abs_median=_med([h["e95_abs_median"] for h in hs if h["e95_abs_median"] is not None]),
                                 e50_abs_p95=max((h["e50_abs_p95"] for h in hs if h["e50_abs_p95"] is not None), default=None),
                                 e95_abs_p95=max((h["e95_abs_p95"] for h in hs if h["e95_abs_p95"] is not None), default=None),
                                 e95_signed_mean=_mean([h["e95_signed_mean"] for h in hs if h["e95_signed_mean"] is not None]),
                                 own_mcse_rel_p50_median=_med([h["own_mcse_rel_p50_median"] for h in hs if h["own_mcse_rel_p50_median"] is not None]),
                                 ess_median=_med([h["ess_median"] for h in hs if h["ess_median"] is not None]),
                                 inside_ref90=_mean([h["inside_ref90"] for h in hs if h["inside_ref90"] is not None]),
                                 truth_cov90=_mean([h["truth_cov90"] for h in hs if h["truth_cov90"] is not None]),
                                 drift=[h["drift"] for h in hs], drift_ok_all=all(h["drift_ok"] for h in hs),
                                 rule_pass=bool(scored and acc / scored >= 0.95 and all(p >= 0.90 for p in per_seed) and len(hs) == len(SEEDS)))
    g["arm_pass"] = all(g["halves"][h]["rule_pass"] for h in HALVES)
    g.update(median_s=_med([r["median_s"] for r in rs if r["median_s"] is not None]),
             p99_s=max((r["p99_s"] for r in rs if r["p99_s"] is not None), default=None),
             max_s=max((r["max_s"] for r in rs if r["max_s"] is not None), default=None),
             frac_lt_04=_mean([r["frac_lt_04"] for r in rs]),
             median_half1_s=_med([r["median_half1_s"] for r in rs if r["median_half1_s"] is not None]),
             median_half2_s=_med([r["median_half2_s"] for r in rs if r["median_half2_s"] is not None]),
             readapt_count=[r["readapt_count"] for r in rs], readapt_median_s=_med([r["readapt_median_s"] for r in rs if r["readapt_median_s"] is not None]),
             readapt_max_s=max((r["readapt_max_s"] for r in rs if r["readapt_max_s"] is not None), default=None),
             readapt_flagged=sum(len(r["readapt_flagged_ticks"]) for r in rs), readapt_errors=sum(len(r["readapt_error_ticks"]) for r in rs),
             first_readapt_after_shift=[r["first_readapt_after_shift"] for r in rs],
             cost_ratio_by_block=[r["cost_ratio_by_block"] for r in rs], tick0_flagged=[r["tick0_flagged"] for r in rs],
             tick0_wall_s=[r["tick0_wall_s"] for r in rs], tick0_accurate=[r.get("tick0_accurate") for r in rs])
    if policy == "trig":
        g["trigger_fired_ticks"] = [r.get("trigger_fired_ticks") for r in rs]
        g["trigger_ratio_max"] = [r.get("trigger_ratio_max") for r in rs]
    return g


def main():
    refs, ref_stats = load_references()
    rows, per = [], {}
    for c in PROTO["cells"]:
        if c["arm"] != "warm":
            continue
        if not (CELLS / c["id"] / "ticks.jsonl").exists():
            continue
        r, p = analyze_cell(c, refs)
        rows.append(r)
        per.update(p)
    groups = {f"{pol}:{s}": group(rows, pol, s) for pol in POLICIES for s in STREAMS}
    frozen_ok = all(groups[f"frozen:{s}"] is not None and groups[f"frozen:{s}"]["arm_pass"] for s in STREAMS)
    passing = [pol for pol in POLICIES if all(groups[f"{pol}:{s}"] is not None and groups[f"{pol}:{s}"]["arm_pass"] for s in STREAMS)]
    verdict = dict(frozen_holds=frozen_ok, policies_passing_both_streams=passing,
                   per_policy={pol: {s: (groups[f"{pol}:{s}"] or {}).get("arm_pass") for s in STREAMS} for pol in POLICIES},
                   per_half={pol: {s: {h: (groups[f"{pol}:{s}"] or {"halves": {}})["halves"].get(h, {}).get("rule_pass") for h in HALVES}
                                   for s in STREAMS} for pol in POLICIES})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(dict(rows=rows, groups=groups, verdict=verdict, references=ref_stats), indent=1, default=_json_default))
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


def fmt_list(v, f):
    return ", ".join("n/a" if x is None else f(x) for x in v) if v else "n/a"


def tables(groups, verdict, ref_stats, rows):
    L = ["## Accuracy per arm, stream and half (frozen rule)", "",
         "A scored tick passes iff |P50 err| <= 2 % and |P95 err| <= 5 % against the gated reference and no chain is stuck; "
         "a half passes iff >= 95 % of its 80 scored ticks (2 seeds x 40) pass and every seed >= 90 %. Half 1 = ticks 25..1000, "
         "half 2 = ticks 1025..2000 (the regime-2 returns enter from tick 1001 on the shift stream). Drift = mean signed P50 "
         "error over the half's last 10 scored ticks minus its first 10 (pp, per seed; bound 0.5 pp reported, not gated).", "",
         "| policy | stream | half | scored | pass pooled | per seed | |P50 err| med / p95 | |P95 err| med / p95 | P95 signed mean | "
         "own MCSE P50 | ESS med | stuck | in ref 90 % | drift pp per seed | half |", "|" + "---|" * 15]
    for pol in POLICIES:
        for s in STREAMS:
            g = groups.get(f"{pol}:{s}")
            if not g:
                L.append(f"| {pol} | {s} | missing |" + " |" * 12)
                continue
            for half, h in g["halves"].items():
                L.append(f"| {pol} | {s} | {half} | {h['scored']} | {pct(h['pass_share'])} | {' / '.join(pct(p, 0) for p in h['per_seed'])} | "
                         f"{pct(h['e50_abs_median'], 2)} / {pct(h['e50_abs_p95'], 2)} | {pct(h['e95_abs_median'], 2)} / {pct(h['e95_abs_p95'], 2)} | "
                         f"{pct(h['e95_signed_mean'], 2)} | {pct(h['own_mcse_rel_p50_median'], 2)} | {h['ess_median']:.0f} | {h['stuck_ticks']} | "
                         f"{pct(h['inside_ref90'])} | {fmt_list(h['drift'], lambda d: f'{100 * d:+.2f}')} | {'PASS' if h['rule_pass'] else 'FAIL'} |"
                         if h["ess_median"] is not None else
                         f"| {pol} | {s} | {half} | {h['scored']} | {pct(h['pass_share'])} | {' / '.join(pct(p, 0) for p in h['per_seed'])} | n/a | n/a | n/a | n/a | n/a | {h['stuck_ticks']} | n/a | n/a | {'PASS' if h['rule_pass'] else 'FAIL'} |")
    L += ["", "Verdict: " + json.dumps(verdict), ""]
    L += ["## Latency and re-adaptation per arm and stream (all 2,000 ticks; tick 0 excluded)", "",
          "| policy | stream | median s | P99 s | max s | < 0.4 s | median half 1 | median half 2 | re-adaptations per seed | "
          "re-adapt tick median s | re-adapt tick max s | first re-adapt after the shift | re-adapt chain fallbacks | re-adapt errors | "
          "cost ratio by 250-tick block (seed 1) |", "|" + "---|" * 15]
    for pol in POLICIES:
        for s in STREAMS:
            g = groups.get(f"{pol}:{s}")
            if not g:
                continue
            cb = g["cost_ratio_by_block"][0] if g["cost_ratio_by_block"] else []
            L.append(f"| {pol} | {s} | {sec(g['median_s'])} | {sec(g['p99_s'])} | {sec(g['max_s'])} | {pct(g['frac_lt_04'])} | "
                     f"{sec(g['median_half1_s'])} | {sec(g['median_half2_s'])} | {g['readapt_count']} | {sec(g['readapt_median_s'])} | "
                     f"{sec(g['readapt_max_s'])} | {g['first_readapt_after_shift']} | {g['readapt_flagged']} | {g['readapt_errors']} | "
                     f"{fmt_list(cb, lambda x: f'{x:.2f}')} |")
    L += ["", "## Trigger arm: firing ticks (trailing cost > 1.5 x post-adaptation baseline, or > 5 % unchanged positions)", "",
          "| stream | seed | fired at ticks | max trailing/baseline ratio | re-adaptations |", "|---|---|---|---|---|"]
    for r in rows:
        if r["policy"] == "trig":
            L.append(f"| {r['stream']} | {r['seed']} | {r.get('trigger_fired_ticks')} | "
                     f"{r.get('trigger_ratio_max'):.3f} | {r['readapt_count']} |" if r.get("trigger_ratio_max") is not None else
                     f"| {r['stream']} | {r['seed']} | {r.get('trigger_fired_ticks')} | n/a | {r['readapt_count']} |")
    L += ["", "## Gated reference (4 x 2,000/20,000 on the tick's 250-return window)", "",
          "| stream | ticks planned | ok | gate failed (both seeds) | second seed used | ticks with a flagged chain dropped | min chains kept | "
          "max R-hat(h_next) | rel. MCSE P50 med / max (half 1) | (half 2) | rel. MCSE P95 med / max (half 1) | (half 2) | min ESS | median wall s | total min |",
          "|" + "---|" * 15]
    for s in STREAMS:
        st = ref_stats[s]
        if not st["ticks_ok"]:
            L.append(f"| {s} | {st['ticks_planned']} | 0 | {st['gate_failed']} |" + " |" * 11)
            continue
        m = lambda d: "n/a" if d is None else f"{pct(d['median'], 2)} / {pct(d['max'], 2)}"
        L.append(f"| {s} | {st['ticks_planned']} | {st['ticks_ok']} | {st['gate_failed']} | {st['second_seed']} | {st['flagged_chain_ticks']} | "
                 f"{st['kept_min']} | {st['rhat_max']:.4f} | {m(st['mcse_rel_p50']['half1'])} | {m(st['mcse_rel_p50']['half2'])} | "
                 f"{m(st['mcse_rel_p95']['half1'])} | {m(st['mcse_rel_p95']['half2'])} | {st['ess_min']:.0f} | {sec(st['wall_median'])} | {st['wall_total_min']:.1f} |")
    L += ["", "## Tick-0 fits (4 x 1,000/1,000 at defaults; outside the latency statistics)", "",
          "| cell | wall s | flagged chains | kept | tick-0 P50 err | tick-0 P95 err | accurate |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['id']} | {sec(r['tick0_wall_s'])} | {r['tick0_flagged']} | {r['kept']} | "
                 f"{pct(r.get('tick0_e50'), 2) if r.get('tick0_e50') is not None else 'n/a'} | "
                 f"{pct(r.get('tick0_e95'), 2) if r.get('tick0_e95') is not None else 'n/a'} | {r.get('tick0_accurate')} |")
    L += ["", "## Per-cell step ratio (mean 2^-level) and cost ratio by 250-tick block", "",
          "| cell | cost ratio per block (vs ticks 1-20) | step ratio per block | max unchanged fraction |", "|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['id']} | {fmt_list(r['cost_ratio_by_block'], lambda x: f'{x:.2f}')} | "
                 f"{fmt_list(r['step_ratio_by_block'], lambda x: f'{x:.3f}')} | "
                 f"{r['unchanged_frac_max'] if r['unchanged_frac_max'] is None else f'{r['unchanged_frac_max']:.4f}'} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
