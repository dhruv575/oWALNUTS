"""Post-hoc mechanism probes (not preregistered, not evidence for the claim).

Usage: python posthoc_analyze.py  -> artifacts/posthoc-summary.json + printed tables
"""
import json
import math
from pathlib import Path

import arviz as az
import numpy as np

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
PHI = lambda z: 0.5 * (1 + math.erf(z / math.sqrt(2)))
BINS = [-np.inf, -8, -6, -5, -4, -2, 0, 2, 4, np.inf]


def load(name):
    p = ART / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def gaussian_check(a):
    s = np.asarray(a["samples"])  # chains, draws, dim
    out = {}
    for j in range(s.shape[2]):
        x = s[:, :, j]
        bulk = float(az.ess(x, method="bulk"))
        mean = float(x.mean())
        var = float(x.var(ddof=1))
        out[f"x{j}"] = {"mean": mean, "mean_z": mean / math.sqrt(1.0 / bulk), "var": var,
                        "rhat": float(az.rhat(x)), "bulk_ess": bulk,
                        "p_lt_minus2": float((x < -2).mean()), "exact_p_lt_minus2": PHI(-2)}
    pooled = s.reshape(-1, s.shape[2])
    r2 = (pooled ** 2).sum(axis=1)
    out["radius_sq_mean"] = float(r2.mean())
    out["radius_sq_exact_mean"] = float(s.shape[2])
    ret = [c["retained"] for c in a["chains"]]
    out["health"] = {k: sum(c[k] for c in ret) for k in
                     ("divergences", "refinement_exhaustion_stops", "maximum_depth_stops", "reverse_coarser_stops")}
    out["stop_reasons"] = {}
    for c in ret:
        for k, v in c["stop_reasons"].items():
            out["stop_reasons"][k] = out["stop_reasons"].get(k, 0) + v
    return out


def trace_table(a):
    """Bin retained transitions by the selected omega; report stop mix and work."""
    rows = []
    for c in a["chains"]:
        rows.extend(c["trace"])
    om = np.array([r[0] for r in rows], dtype=float)
    depth = np.array([r[1] for r in rows])
    stop = np.array([r[2] for r in rows])
    level = np.array([r[3] for r in rows])
    calls = np.array([r[4] for r in rows])
    rcr = np.array([r[6] for r in rows])
    table = []
    idx = np.digitize(om, BINS[1:-1])
    for b in range(len(BINS) - 1):
        m = idx == b
        if m.sum() == 0:
            continue
        stops = {k: int((stop[m] == k).sum()) for k in np.unique(stop[m])}
        table.append({
            "omega_bin": f"[{BINS[b]}, {BINS[b+1]})", "n": int(m.sum()), "frac": float(m.mean()),
            "mean_depth": float(depth[m].mean()), "mean_level": float(level[m].mean()),
            "mean_calls": float(calls[m].mean()), "mean_reverse_coarser_rejections": float(rcr[m].mean()),
            "stop_fractions": {k: v / m.sum() for k, v in stops.items()},
        })
    # "stuck" statistic: fraction of transitions where selected omega == previous omega (no move)
    same = 0
    total = 0
    for c in a["chains"]:
        o = np.array([r[0] for r in c["trace"]])
        same += int((o[1:] == o[:-1]).sum())
        total += len(o) - 1
    # neck escape: given omega_t < -5, P(omega_{t+1} >= -5)
    esc_n = esc_k = 0
    ent_n = ent_k = 0
    for c in a["chains"]:
        o = np.array([r[0] for r in c["trace"]])
        neck = o[:-1] < -5
        esc_n += int(neck.sum()); esc_k += int((neck & (o[1:] >= -5)).sum())
        mouth = o[:-1] >= -5
        ent_n += int(mouth.sum()); ent_k += int((mouth & (o[1:] < -5)).sum())
    return {"bins": table, "no_move_fraction": same / max(total, 1),
            "neck_escape_rate": esc_k / max(esc_n, 1), "neck_entry_rate": ent_k / max(ent_n, 1),
            "implied_neck_mass": (ent_k / max(ent_n, 1)) / ((ent_k / max(ent_n, 1)) + (esc_k / max(esc_n, 1))) if esc_n and ent_n else None}


def tail_stats(a):
    s = np.asarray(a["samples"])
    om = s[:, :, 0]
    tail = float(az.ess(om, method="tail", prob=(0.05, 0.95)))
    pooled = om.reshape(-1)
    out = {"rhat": float(az.rhat(om)), "bulk_ess": float(az.ess(om, method="bulk")), "tail_ess": tail,
           "mean": float(pooled.mean()), "var": float(pooled.var(ddof=1))}
    for thr in (-5.0, -6.0):
        exact = PHI(thr / 3)
        p = float((pooled < thr).mean())
        out[f"p_lt_{int(-thr)}"] = {"observed": p, "exact": exact,
                                   "z": (p - exact) / math.sqrt(exact * (1 - exact) / max(tail, 1))}
    ret = [c["retained"] for c in a["chains"]]
    out["health"] = {k: sum(c[k] for c in ret) for k in
                     ("divergences", "refinement_exhaustion_stops", "maximum_depth_stops", "reverse_coarser_stops", "target_calls")}
    out["wall_seconds"] = a["wall_seconds_including_discarded"]
    return out


def main():
    summary = {"schema": "owalnuts-paper-funnel-reproduction-posthoc-summary/v1", "note": "post-hoc, non-evidence"}
    F = load("F")
    FT = load("posthoc-FT")
    if F and FT:
        identical = np.array_equal(np.asarray(F["samples"]), np.asarray(FT["samples"]))
        summary["FT_bit_identical_to_F"] = bool(identical)
        summary["FT_trace"] = trace_table(FT)
    G = load("posthoc-G")
    if G:
        summary["G_gaussian_control"] = gaussian_check(G)
    for name in ("posthoc-S", "posthoc-M8"):
        a = load(name)
        if a:
            summary[name] = tail_stats(a)
            summary[name + "_trace"] = trace_table(a)
    (ART / "posthoc-summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if not k.endswith("_trace")}, indent=1))
    for k, v in summary.items():
        if k.endswith("_trace"):
            print("###", k, "no_move", round(v["no_move_fraction"], 4), "escape", round(v["neck_escape_rate"], 4),
                  "entry", round(v["neck_entry_rate"], 4), "implied neck mass", v["implied_neck_mass"])
            for b in v["bins"]:
                print(f"  {b['omega_bin']:>14} n={b['n']:6d} depth={b['mean_depth']:.2f} level={b['mean_level']:.2f} "
                      f"calls={b['mean_calls']:.0f} rcr={b['mean_reverse_coarser_rejections']:.2f} "
                      + " ".join(f"{s}={f:.2f}" for s, f in sorted(b['stop_fractions'].items())))


if __name__ == "__main__":
    main()
