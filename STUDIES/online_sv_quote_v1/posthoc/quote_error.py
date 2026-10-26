#!/usr/bin/env python3
"""Post hoc, not preregistered; exploratory; informs the next study's rule.

WP84 re-analysis: how far is the QUOTE a warm refresh produces from the quote the slow
reference produces, in relative terms, and does that stay put over 100 ticks?

N = 250 only (the N = 1000 reference failed at admission; only latency is reported there).
Every tick 1-100 of every arm cell is compared with the reference cell ref-N250 on the
next-period volatility sigma_next = exp(h_next / 2), with h_next built exactly as in
analyze.py (same eps stream per tick, so every arm estimates the same functional).

Reference cleaning (post hoc): at four ticks one reference chain is frozen at a point far
outside the posterior (adapted step ~1e-6, log density thousands below the others). The
sampler flagged each one in ticks.jsonl (`WarmupStep { chain: c }` / `SampledLogDensity
{ chain: c }`); this script drops exactly the flagged chains, so the reference is 3 x 20,000
at those ticks and 4 x 20,000 elsewhere. Nothing else is changed.

Stuck-chain census for the arms: a chain is "stuck" when the median of its log_sigma draws
is more than 1.0 from the cleaned reference's median log_sigma, or its median h_last more
than 2.0 away (posterior sds are about 0.3 and 0.45; healthy chain-to-chain spread is ~0.01;
every stuck chain seen sits 3-4 units away in log_sigma). Arms are reported as sampled (what
a quote engine would have used) and with stuck ticks removed (what a chain gate would pass).

Per tick and cell:
  sigma P5 / P50 / P95 / mean, relative error (arm - ref) / ref, absolute and signed;
  the quote: half-spread = c * P50(sigma), risk quote = c * P95(sigma), so the relative error
  of P50 (P95) is the spread error in basis points per unit of spread (1 % = 100 bp);
  pooled-across-chains bulk ESS of h_next (arviz.ess: split chains, rank-normalised) and the
  arm's own MCSE of P50(sigma) (arviz.mcse method="quantile": Vehtari et al. 2021 quantile
  MCSE from the ESS of the indicator I(sigma <= q), reported relative to P50);
  the reference's own MCSE of the same quantities (the floor), and an empirical floor: the
  relative gap between two half-references (chains split in two).

Usage: python quote_error.py [cells_dir] [--json out.json]
cells_dir defaults to ../artifacts/cells (raw draws are not committed; point at the checkout
that holds them). Prints markdown tables; --json writes the per-tick numbers.
"""
import json, re, sys, warnings
from pathlib import Path
import numpy as np
warnings.filterwarnings("ignore")
import arviz as az

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
PROTO = json.loads((STUDY / "protocol.json").read_text())
DATA = json.loads((STUDY / "models" / "data.json").read_text())
RHO = DATA["rho"]
P = [0.05, 0.5, 0.95]
QN = ["p5", "p50", "p95", "mean"]
TOL = [0.01, 0.02, 0.05, 0.10]
ARMS = ["warm50", "warm200", "refit", "cmdstan", "nutpie"]
DRAWS = {"warm50": 200, "warm200": 800, "refit": 4000, "cmdstan": 4000, "nutpie": 4000}
TICKS = PROTO["stream"]["ticks"]
N_MAIN = 250
STUCK_LS, STUCK_HL = 1.0, 2.0


def arm_name(c):
    return c["arm"] + str(c.get("K", ""))


def records(cell):
    return {r["tick"]: r for r in map(json.loads, (cell / "ticks.jsonl").read_text().splitlines())}


def flagged_chains(rec):
    """Chains the oWALNUTS rescue diagnostics flagged as stuck: step collapsed in warmup or the
    sampled log density far below the other chains. (The RHat/RHatCluster warnings also name the
    healthy partner chain of a pair, so they are not used to pick the chain.)"""
    out = set()
    for w in rec.get("chain_warnings") or []:
        m = re.match(r"(SampledLogDensity|WarmupStep) \{ chain: (\d+)", w)
        if m:
            out.add(int(m.group(2)))
    return sorted(out)


def raw(cell, tick):
    a = np.frombuffer((cell / f"tick-{tick:03}.f32").read_bytes(), dtype="<f4").astype(float)
    return a.reshape(4, -1, 3)        # (chain, draw, [mu, log_sigma, h_last])


def h_next(a, tick, chains):
    a = a[chains]
    mu, ls, hl = a[..., 0], a[..., 1], a[..., 2]
    eps = np.random.default_rng(840000 + tick).normal(size=(4, 20000))[chains][:, : a.shape[1]]
    return mu + RHO * (hl - mu) + np.exp(ls) * eps


def sc(v):
    """arviz returns 0-d or length-1 arrays depending on method; take the scalar."""
    return float(np.asarray(v).reshape(-1)[0])


def sigma_stats(sig):
    """sig: (chains, draws) of sigma_next. Pooled quantiles/mean and their MCSEs."""
    q = np.quantile(sig, P)
    mc = [sc(az.mcse(sig, method="quantile", prob=p)) for p in P] + [sc(az.mcse(sig, method="mean"))]
    return dict(val=np.array([*q, float(sig.mean())]), mcse=np.array(mc))


def load(a, tick, chains=(0, 1, 2, 3)):
    hn = h_next(a, tick, list(chains))
    sig = np.exp(hn / 2)
    s = sigma_stats(sig)
    s["ess"] = sc(az.ess(hn))
    s["rhat"] = sc(az.rhat(hn))
    s["sig"] = sig
    return s


def main():
    argv = sys.argv[1:]
    json_out = None
    if "--json" in argv:
        i = argv.index("--json")
        json_out = argv[i + 1]
        del argv[i:i + 2]
    cells = Path(argv[0]) if argv else STUDY / "artifacts" / "cells"

    # ---- reference, cleaned by the sampler's own chain flags ----------------------------
    refc = cells / f"ref-N{N_MAIN}"
    rrec = records(refc)
    ref, ref_dropped = {}, {}
    for t in range(1, TICKS + 1):
        a = raw(refc, t)
        bad = flagged_chains(rrec[t])
        keep = [c for c in range(4) if c not in bad]
        r = load(a, t, keep)
        sig = r.pop("sig")
        h = len(keep) // 2
        x, y = sigma_stats(sig[:h]), sigma_stats(sig[h:])          # half-reference gap
        r["half_gap"] = np.abs(x["val"] - y["val"]) / r["val"]
        r["rel_mcse"] = r["mcse"] / r["val"]
        r["ls_med"] = float(np.median(a[keep, :, 1]))
        r["hl_med"] = float(np.median(a[keep, :, 2]))
        r["chains"] = len(keep)
        # census rule applied to the raw reference, to check it agrees with the flags
        r["census_stuck"] = [c for c in range(4) if abs(np.median(a[c, :, 1]) - r["ls_med"]) > STUCK_LS
                             or abs(np.median(a[c, :, 2]) - r["hl_med"]) > STUCK_HL]
        r["flagged"] = bad
        ref[t] = r
        if bad:
            ref_dropped[t] = bad

    # ---- arms -------------------------------------------------------------------------
    per, meta = {}, {}
    for c in PROTO["cells"]:
        if c["arm"] == "ref" or c["N"] != N_MAIN:
            continue
        cell = cells / c["id"]
        recs = records(cell)
        rows = []
        for t in range(1, TICKS + 1):
            rec = recs.get(t)
            if rec is None or rec["status"] != "ok":
                rows.append(dict(tick=t, ok=False, wall=rec["wall_seconds"] if rec else None))
                continue
            a = raw(cell, t)
            rf = ref[t]
            stuck = [k for k in range(4) if abs(np.median(a[k, :, 1]) - rf["ls_med"]) > STUCK_LS
                     or abs(np.median(a[k, :, 2]) - rf["hl_med"]) > STUCK_HL]
            e = load(a, t)
            e.pop("sig")
            rel = (e["val"] - rf["val"]) / rf["val"]
            rows.append(dict(tick=t, ok=True, wall=rec["wall_seconds"], rel=rel.tolist(), abs_rel=np.abs(rel).tolist(),
                             val=e["val"].tolist(), ess=e["ess"], rhat=e["rhat"],
                             rel_mcse=(e["mcse"] / e["val"]).tolist(), div=int(sum(rec["divergences"])),
                             stuck=stuck, flagged=flagged_chains(rec)))
        per[c["id"]] = rows
        meta[c["id"]] = dict(arm=arm_name(c), seed=c["seed"])

    # ---- latency, N = 250 and N = 1000 (latency only) -----------------------------------
    lat = {}
    for c in PROTO["cells"]:
        if c["arm"] == "ref":
            continue
        recs = records(cells / c["id"])
        w = [recs[t]["wall_seconds"] for t in range(1, TICKS + 1) if t in recs]
        lat.setdefault((arm_name(c), c["N"]), []).extend(w)

    # ---- tables -----------------------------------------------------------------------
    out = []
    pct = lambda x: f"{100 * x:.2f} %"
    bp = lambda x: f"{1e4 * x:.0f}"
    pooled = {arm: [r for i in per if meta[i]["arm"] == arm for r in per[i] if r["ok"]] for arm in ARMS}
    clean = {arm: [r for r in pooled[arm] if not r["stuck"]] for arm in ARMS}

    out.append("### Reference (ref-N250, 4 x 20,000 draws; flagged chain dropped at "
               f"{len(ref_dropped)} ticks: {', '.join(f'tick {t} chain {b[0]}' for t, b in ref_dropped.items())})\n")
    agree = all(set(ref[t]["census_stuck"]) == set(ref[t]["flagged"]) for t in ref)
    out.append("| quantity | rel. MCSE median | rel. MCSE P95 | rel. MCSE max | half-ref gap median | half-ref gap P95 | half-ref gap max |")
    out.append("|---|---|---|---|---|---|---|")
    rm = np.array([ref[t]["rel_mcse"] for t in ref])
    hg = np.array([ref[t]["half_gap"] for t in ref])
    for i, qn in enumerate(QN):
        out.append(f"| sigma {qn} | {pct(np.median(rm[:, i]))} | {pct(np.quantile(rm[:, i], .95))} | {pct(rm[:, i].max())} | "
                   f"{pct(np.median(hg[:, i]))} | {pct(np.quantile(hg[:, i], .95))} | {pct(hg[:, i].max())} |")
    ess_ref = np.array([ref[t]["ess"] for t in ref])
    out.append(f"\nCleaned reference: bulk ESS of h_next median {np.median(ess_ref):.0f}, min {ess_ref.min():.0f}; "
               f"max R-hat {max(ref[t]['rhat'] for t in ref):.4f}. The stuck-chain census rule applied to the raw "
               f"reference {'agrees with' if agree else 'DISAGREES with'} the sampler's flags on all 100 ticks. "
               "Half-ref gap = |half A - half B| / full, two independent halves of the retained chains.\n")

    out.append("### Stuck-chain census per arm (ticks with >= 1 chain frozen off-target, of 100 per seed)\n")
    out.append("| arm | seed 84001 | seed 84002 | seed 84003 | total / 300 | ticks with 2 stuck | sampler flagged the same chains |")
    out.append("|---|---|---|---|---|---|---|")
    for arm in ARMS:
        cnt, two, agree_n, flag_n = [], 0, 0, 0
        for i in per:
            if meta[i]["arm"] != arm:
                continue
            rows = [r for r in per[i] if r["ok"]]
            cnt.append(sum(bool(r["stuck"]) for r in rows))
            two += sum(len(r["stuck"]) >= 2 for r in rows)
            if arm in ("refit",):
                for r in rows:
                    if r["stuck"] or r["flagged"]:
                        flag_n += 1
                        agree_n += set(r["stuck"]) == set(r["flagged"])
        fl = f"{agree_n}/{flag_n}" if arm == "refit" else ("n/a (no flags recorded)" if arm in ("cmdstan", "nutpie") else "none to flag")
        out.append(f"| {arm} | {cnt[0]} | {cnt[1]} | {cnt[2]} | {sum(cnt)} ({100 * sum(cnt) / 300:.1f} %) | {two} | {fl} |")

    def err_table(title, src, note):
        out.append(f"\n### {title}\n")
        out.append(note + "\n")
        out.append("| arm | ticks | P5 median / P95 | P50 median / P95 | P95 median / P95 | mean median / P95 | P50 err bp/unit (median / P95) | P95 err bp/unit (median / P95) |")
        out.append("|---|---|---|---|---|---|---|---|")
        for arm in ARMS:
            A = np.array([r["abs_rel"] for r in src[arm]])
            cols = " | ".join(f"{pct(np.median(A[:, k]))} / {pct(np.quantile(A[:, k], .95))}" for k in range(4))
            out.append(f"| {arm} | {len(A)} | {cols} | {bp(np.median(A[:, 1]))} / {bp(np.quantile(A[:, 1], .95))} | "
                       f"{bp(np.median(A[:, 2]))} / {bp(np.quantile(A[:, 2], .95))} |")

    def share_table(title, src):
        out.append(f"\n### {title}\n")
        out.append("| arm | ticks | P50 <= 1 % | P50 <= 2 % | P50 <= 5 % | P50 <= 10 % | P95 <= 1 % | P95 <= 2 % | P95 <= 5 % | P95 <= 10 % |")
        out.append("|---|---|---|---|---|---|---|---|---|---|")
        res = {}
        for arm in ARMS:
            A = np.array([r["abs_rel"] for r in src[arm]])
            s50 = [float(np.mean(A[:, 1] <= tol)) for tol in TOL]
            s95 = [float(np.mean(A[:, 2] <= tol)) for tol in TOL]
            res[arm] = dict(p50=s50, p95=s95, n=len(A))
            out.append(f"| {arm} | {len(A)} | " + " | ".join(f"{100 * x:.1f} %" for x in s50 + s95) + " |")
        return res

    err_table("Relative error vs reference, as sampled, pooled over 3 seeds", pooled,
              "Relative error = |arm - ref| / ref of the sigma_next statistic, every tick the arm produced. For the quote, "
              "the P50 column is the half-spread error and the P95 column the risk-quote error, in basis points per unit "
              "of spread (1 % = 100 bp).")
    share_as = share_table("Share of ticks within tolerance, as sampled (pooled over seeds)", pooled)
    err_table("Relative error vs reference, stuck ticks removed", clean,
              "Same, after dropping every tick on which the arm had a stuck chain (a chain gate would refuse to quote "
              "there). Identical to the as-sampled table for arms with no stuck chains.")
    share_cl = share_table("Share of ticks within tolerance, stuck ticks removed", clean)

    out.append("\n### Chain quality and the arm's own Monte Carlo error (as sampled, pooled over seeds)\n")
    out.append("| arm | draws / tick | bulk ESS h_next median (min) | ESS per draw | own rel. MCSE of P50 median / P95 | R-hat <= 1.01 | R-hat max | signed P50 rel. err median | signed P95 rel. err median | signed P50 mean (clean) | signed P95 mean (clean) |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for arm in ARMS:
        rows, crows = pooled[arm], clean[arm]
        ess = np.array([r["ess"] for r in rows])
        rmc = np.array([r["rel_mcse"][1] for r in rows])
        rh = np.array([r["rhat"] for r in rows])
        S = np.array([r["rel"] for r in rows])
        C = np.array([r["rel"] for r in crows])
        out.append(f"| {arm} | {DRAWS[arm]} | {np.median(ess):.0f} ({ess.min():.0f}) | {np.median(ess) / DRAWS[arm]:.2f} | "
                   f"{pct(np.median(rmc))} / {pct(np.quantile(rmc, .95))} | {100 * np.mean(rh <= 1.01):.0f} % | {rh.max():.3f} | "
                   f"{100 * np.median(S[:, 1]):+.2f} % | {100 * np.median(S[:, 2]):+.2f} % | "
                   f"{100 * C[:, 1].mean():+.2f} % | {100 * C[:, 2].mean():+.2f} % |")

    out.append("\n### Drift: P50 relative error, ticks 1-25 vs 76-100, per arm and seed (stuck ticks removed)\n")
    out.append("| arm | seed | mean abs rel. err 1-25 | mean abs rel. err 76-100 | late - early | signed mean 1-25 | signed mean 76-100 | ticks used |")
    out.append("|---|---|---|---|---|---|---|---|")
    drift = {}
    for arm in ARMS:
        for i in per:
            if meta[i]["arm"] != arm:
                continue
            rows = [r for r in per[i] if r["ok"] and not r["stuck"]]
            e = np.array([r["rel"][1] for r in rows if r["tick"] <= 25])
            l = np.array([r["rel"][1] for r in rows if r["tick"] >= 76])
            drift[i] = dict(early=float(np.abs(e).mean()), late=float(np.abs(l).mean()),
                            early_signed=float(e.mean()), late_signed=float(l.mean()))
            out.append(f"| {arm} | {meta[i]['seed']} | {pct(np.abs(e).mean())} | {pct(np.abs(l).mean())} | "
                       f"{100 * (np.abs(l).mean() - np.abs(e).mean()):+.2f} pp | {100 * e.mean():+.2f} % | {100 * l.mean():+.2f} % | {len(e)} + {len(l)} |")

    out.append("\n### Latency per tick (wall seconds, pooled over 3 seeds = 300 ticks; tick 0 excluded)\n")
    out.append("| arm | N | median s | P95 s | max s |")
    out.append("|---|---|---|---|---|")
    for N in PROTO["stream"]["N"]:
        for arm in ARMS:
            w = np.array(lat[(arm, N)])
            out.append(f"| {arm} | {N} | {np.median(w):.3f} | {np.quantile(w, .95):.3f} | {w.max():.3f} |")

    text = "\n".join(out)
    print(text)
    if json_out:
        Path(json_out).write_text(json.dumps(dict(
            reference={t: dict(val=ref[t]["val"].tolist(), rel_mcse=ref[t]["rel_mcse"].tolist(),
                               half_gap=ref[t]["half_gap"].tolist(), ess=ref[t]["ess"], rhat=ref[t]["rhat"],
                               chains=ref[t]["chains"], flagged=ref[t]["flagged"]) for t in ref},
            cells={i: dict(meta=meta[i], ticks=per[i]) for i in per},
            share_as_sampled=share_as, share_stuck_removed=share_cl, drift=drift,
            latency={f"{a}-N{N}": dict(median=float(np.median(w)), p95=float(np.quantile(w, .95))) for (a, N), w in lat.items()},
        ), indent=1))


if __name__ == "__main__":
    main()
