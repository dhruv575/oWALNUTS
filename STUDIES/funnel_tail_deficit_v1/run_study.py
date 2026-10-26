#!/usr/bin/env python3
"""WP66 driver: funnel tail deficit, three single-setting candidates (stdlib only).

    python3 run_study.py run A        # block A (2,000/20,000; four arms x 30 seeds), sequential, resumable
    python3 run_study.py run S        # sanity arm (default, 2,000/80,000, 10 seeds)
    python3 run_study.py run C        # side check (eight, gauss100; four arms x 10 seeds; 1,000/1,000)
    python3 run_study.py analyze      # artifacts/summary.json + artifacts/results-table.md

Cells: artifacts/cells/<block>-<arm>[-<target>]-<seed>.json; errors as <...>.error.json. Never rerun.
On the shared box every call is wrapped by the caller in `taskset -c 8-11`; children inherit it.
Copied from STUDIES/funnel_defaults_30seed_v1/run_study.py and parametrised (see protocol.json
"changes_from_WP53_harness").
"""
from __future__ import annotations

import json
import math
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
ART = HERE / "artifacts"
CELLS = ART / "cells"
EXE = ".exe" if os.name == "nt" else ""
FUNNEL = HERE / "target" / "release" / f"funnel{EXE}"
SIDE = HERE / "target" / "release" / f"side{EXE}"
SEEDS = PROTOCOL["seeds"]
BLOCKS = PROTOCOL["blocks"]
ARMS = BLOCKS["A"]["arms"]
CANDIDATES = [a for a in ARMS if a != "default"]
EXACT_P5 = 0.0477903522728147
EXACT_P6 = 0.0227501319481792
P_EXCEED = 2 * (1 - 0.5 * (1 + math.erf(2 / math.sqrt(2))))  # 0.0455
HYP = {"accept0.9": "H1_step_adaptation", "levels10": "H2_refinement_ceiling", "endpoint": "H3_u_turn_rule"}


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with (ART / "run-log.txt").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def cell_path(block: str, arm: str, seed: int, target: str | None = None, error: bool = False) -> Path:
    mid = f"{arm}-{target}" if target else arm
    return CELLS / f"{block}-{mid}-{seed}{'.error' if error else ''}.json"


def run_one(block: str, cmd: list[str], out: Path, err: Path, meta: dict) -> None:
    t0 = time.time()
    cp = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    log(f"{block} [{time.time() - t0:.1f}s] {cp.stderr.strip()[-500:]}")
    if cp.returncode != 0 or not out.exists():
        err.write_text(json.dumps({**meta, "status": "error", "returncode": cp.returncode,
                                   "stderr": cp.stderr[-4000:]}, indent=1) + "\n", encoding="utf-8")


def run(block: str) -> None:
    CELLS.mkdir(parents=True, exist_ok=True)
    spec = BLOCKS[block]
    log(f"block {block} start (pid {os.getpid()}, affinity {sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else 'n/a'})")
    for seed in SEEDS[spec["seeds"]]:
        if spec["kind"] == "funnel":
            for arm in spec["arms"]:
                out, err = cell_path(block, arm, seed), cell_path(block, arm, seed, error=True)
                if out.exists() or err.exists():
                    continue
                run_one(block, [str(FUNNEL), arm, str(spec["warmup"]), str(spec["draws"]), str(seed), str(out)],
                        out, err, {"block": block, "arm": arm, "seed": seed})
        else:
            for target in spec["targets"]:
                for arm in spec["arms"]:
                    out, err = cell_path(block, arm, seed, target), cell_path(block, arm, seed, target, True)
                    if out.exists() or err.exists():
                        continue
                    run_one(block, [str(SIDE), target, arm, str(seed), str(out)], out, err,
                            {"block": block, "arm": arm, "target": target, "seed": seed})
    log(f"block {block} complete")


# ----------------------------------------------------------------------------- statistics (WP53)


def norm_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2))


def binom_upper(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))


def gammainc_lower_reg(a: float, x: float) -> float:
    if x <= 0:
        return 0.0
    if x < a + 1:
        term = total = 1.0 / a
        n = a
        for _ in range(10000):
            n += 1
            term *= x / n
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
        return total * math.exp(-x + a * math.log(x) - math.lgamma(a))
    b = x + 1 - a
    c = 1e300
    d = 1 / b
    h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return 1 - math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def ks_normal(z: list[float]) -> tuple[float, float]:
    xs = sorted(z)
    n = len(xs)
    d = max(max((i + 1) / n - norm_cdf(x), norm_cdf(x) - i / n) for i, x in enumerate(xs))
    lam = (math.sqrt(n) + 0.12 + 0.11 / math.sqrt(n)) * d
    p = 2 * sum((-1) ** (j - 1) * math.exp(-2 * j * j * lam * lam) for j in range(1, 101))
    return d, min(max(p, 0.0), 1.0)


def calibration(z: list[float]) -> dict:
    n = len(z)
    k = sum(abs(v) > 2 for v in z)
    mean = statistics.fmean(z)
    sd = statistics.stdev(z)
    p_mean = 2 * (1 - norm_cdf(abs(mean * math.sqrt(n))))
    chi = (n - 1) * sd * sd
    c = gammainc_lower_reg((n - 1) / 2, chi / 2)
    d, p_ks = ks_normal(z)
    return {"n": n, "exceed_count": k, "binom_p_ge_k": binom_upper(k, n, P_EXCEED), "mean": mean, "p_mean": p_mean,
            "sd": sd, "p_variance": 2 * min(c, 1 - c), "ks_d": d, "p_ks": p_ks,
            "consistent_with_n01": bool(p_mean >= 0.05 and 2 * min(c, 1 - c) >= 0.05 and p_ks >= 0.05),
            "min": min(z), "max": max(z), "n_below_minus2": sum(v < -2 for v in z), "n_above_plus2": sum(v > 2 for v in z)}


def mean_se(xs: list[float]) -> tuple[float, float]:
    return statistics.fmean(xs), (statistics.stdev(xs) / math.sqrt(len(xs)) if len(xs) > 1 else float("nan"))


def ranks(x: list[float]) -> list[float]:
    order = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and x[order[j + 1]] == x[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2
        i = j + 1
    return r


def spearman(a: list[float], b: list[float]) -> float:
    ra, rb = ranks(a), ranks(b)
    ma, mb = statistics.fmean(ra), statistics.fmean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else float("nan")


def geomean(xs: list[float]) -> float:
    return math.exp(statistics.fmean(math.log(x) for x in xs))


# ----------------------------------------------------------------------------- analysis


def load(p: Path) -> dict | None:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def merge_classes(cells: list[dict]) -> dict:
    """Pool the per-cell class aggregates (counts summed; means re-weighted by n)."""
    out = {}
    for cls in ("bulk", "neck", "deep"):
        rows = [c["retained_classes"][cls] for c in cells]
        n = sum(r["n"] for r in rows)
        w = lambda key: sum(r[key] * r["n"] for r in rows) / n if n else None  # noqa: E731
        depth = [sum(r["depth_histogram"][i] for r in rows) for i in range(len(rows[0]["depth_histogram"]))]
        levels = [sum(r["selected_level_histogram"][i] for r in rows) for i in range(len(rows[0]["selected_level_histogram"]))]
        stops = {k: sum(r["stops"][k] for r in rows) for k in rows[0]["stops"]}
        top = sum(r["top_level_selected"] for r in rows)
        shallow = sum(r["depth_histogram"][d] for r in rows for d in range(0, min(4, len(r["depth_histogram"]))))
        uturn_shallow = sum(r["uturn_depth_le3"] for r in rows)
        out[cls] = {
            "n": n, "depth_histogram": depth, "mean_depth": w("mean_depth"), "stops": stops,
            "selected_level_histogram": levels, "top_level_selected": top,
            "top_level_fraction": top / n if n else None,
            "exhaustion_stops": stops["RefinementExhausted"],
            "top_plus_exhaustion_fraction": (top + stops["RefinementExhausted"]) / n if n else None,
            "depth_cap_fraction": stops["MaximumDepth"] / n if n else None,
            "uturn_fraction": (stops["OuterUTurn"] + stops["RecursiveUTurn"]) / n if n else None,
            "depth_le3_fraction": shallow / n if n else None,
            "uturn_depth_le3_fraction": uturn_shallow / n if n else None,
            "moved_fraction": w("moved_fraction"), "energy_acceptance_proxy": w("mean_energy_acceptance_proxy"),
            "mean_max_abs_energy_error": w("mean_max_abs_energy_error"), "mean_macro_length": w("mean_macro_length"),
            "mean_orbit_states": w("mean_orbit_states"), "mean_target_evaluations": w("mean_target_evaluations"),
            "mean_refinement_attempts": w("mean_refinement_attempts"), "divergences": sum(r["divergences"] for r in rows),
        }
    return out


def funnel_arm(block: str, arm: str) -> dict | None:
    spec = BLOCKS[block]
    cells, errors = [], []
    for seed in SEEDS[spec["seeds"]]:
        c = load(cell_path(block, arm, seed))
        if c is not None:
            cells.append(c)
        elif cell_path(block, arm, seed, error=True).exists():
            errors.append(seed)
    if not cells and not errors:
        return None
    est = [c["tail_mass"]["estimate"] for c in cells]
    z = [c["tail_mass"]["z"] for c in cells]
    p5, se5 = mean_se(est)
    up5, upse = mean_se([c["upper_tail_profile"][4]["estimate"] for c in cells])
    p6, se6 = mean_se([c["tail_mass_6"]["estimate"] for c in cells])
    var, var_se = mean_se([c["omega"]["variance"] for c in cells])
    om, om_se = mean_se([c["omega"]["mean"] for c in cells])
    cal = calibration(z) if len(z) >= 3 else None
    if cal:
        cal["exceed_count_with_errors"] = cal["exceed_count"] + len(errors)
    div = sum(sum(ch["divergences"] for ch in c["chains_data"]) for c in cells)
    transitions = len(cells) * 4 * spec["draws"]
    profile_low = []
    for k in range(10):
        cc = -(k + 1)
        exact = norm_cdf(cc / 3)
        m, s = mean_se([c["lower_tail_profile"][k]["estimate"] for c in cells])
        profile_low.append({"c": cc, "exact": exact, "estimate": m, "se": s, "relative": m / exact - 1, "t": (m - exact) / s if s else None})
    profile_high = []
    for k in range(10):
        cc = k + 1
        exact = norm_cdf(-cc / 3)
        m, s = mean_se([c["upper_tail_profile"][k]["estimate"] for c in cells])
        profile_high.append({"c": cc, "exact": exact, "estimate": m, "se": s, "relative": m / exact - 1, "t": (m - exact) / s if s else None})
    chains = [(ch, c["seed"], i) for c in cells for i, ch in enumerate(c["chains_data"])]
    per_chain_p5 = [c["tail_mass"]["per_chain"][i] for c in cells for i in range(4)]
    log_h = [math.log(ch["final_step_size"]) for ch, _, _ in chains]
    q = [[ch["tail_by_quarter"][k] for ch, _, _ in chains] for k in range(4)]
    prefix = [c["tail_mass"]["prefix_estimate"] for c in cells]
    classes = merge_classes(cells)
    return {
        "cells": len(cells), "errors": errors, "calibration": cal,
        "pooled_p5": p5, "se_p5": se5, "t_p5": (p5 - EXACT_P5) / se5, "relative_deficit": 1 - p5 / EXACT_P5,
        "pooled_upper_p5": up5, "se_upper_p5": upse, "t_upper_p5": (up5 - EXACT_P5) / upse,
        "pooled_p6": p6, "se_p6": se6, "omega_variance": var, "omega_variance_se": var_se,
        "omega_mean": om, "omega_mean_se": om_se,
        "prefix_pooled_p5": statistics.fmean(prefix),
        "profile_low": profile_low, "profile_high": profile_high,
        "total_divergences": div, "retained_transitions": transitions, "divergence_rate": div / transitions,
        "total_depth_caps": sum(ch["depth_caps"] for ch, _, _ in chains),
        "total_exhaustions": sum(ch["refinement_exhaustions"] for ch, _, _ in chains),
        "total_nonfinite_rejections": sum(ch["nonfinite_position_rejections_retained"] + ch["nonfinite_position_rejections_warmup"] for ch, _, _ in chains),
        "median_final_step": statistics.median(math.exp(v) for v in log_h),
        "step_range": [min(math.exp(v) for v in log_h), max(math.exp(v) for v in log_h)],
        "spearman_chain_p5_log_h": spearman(per_chain_p5, log_h),
        "chain_p5_small_h_half": statistics.fmean(p for p, h in zip(per_chain_p5, log_h) if h < statistics.median(log_h)),
        "chain_p5_large_h_half": statistics.fmean(p for p, h in zip(per_chain_p5, log_h) if h >= statistics.median(log_h)),
        "tail_by_quarter_pooled": [statistics.fmean(v) for v in q],
        "mean_neck_entries_per_chain": statistics.fmean(ch["neck_entries"] for ch, _, _ in chains),
        "mean_excursion_length": statistics.fmean(ch["mean_excursion_length"] for ch, _, _ in chains),
        "median_min_omega": statistics.median(ch["min_omega"] for ch, _, _ in chains),
        "warmup_acceptance_mean": statistics.fmean(ch["warmup_last_slow_window_acceptance_mean"] for ch, _, _ in chains if ch["warmup_last_slow_window_acceptance_mean"] is not None),
        "geomean_min_bulk_ess_per_gradient": geomean([c["min_bulk_ess_per_gradient"] for c in cells]),
        "median_gradients": statistics.median(c["target_calls_total"] for c in cells),
        "median_min_bulk_ess": statistics.median(c["min_bulk_ess"] for c in cells),
        "median_omega_tail_ess": statistics.median(c["omega"]["tail_ess"] for c in cells),
        "max_rhat_max": max(c["max_rhat"] for c in cells),
        "chain_warning_cells": sum(bool(c["chain_warnings"]) for c in cells),
        "classes": classes,
        "per_seed": {str(c["seed"]): {"p5": c["tail_mass"]["estimate"], "z": c["tail_mass"]["z"],
                                      "upper_p5": c["upper_tail_profile"][4]["estimate"],
                                      "divergences": sum(ch["divergences"] for ch in c["chains_data"]),
                                      "steps": [ch["final_step_size"] for ch in c["chains_data"]],
                                      "per_chain_p5": c["tail_mass"]["per_chain"],
                                      "prefix_p5": c["tail_mass"]["prefix_estimate"],
                                      "wall": c["wall_seconds_pinned_cotenanted"]} for c in cells},
        "algorithm_revisions": sorted({c["algorithm_revision"] for c in cells}),
        "kernel_tuning": cells[0]["kernel_tuning"] if cells else None,
        "u_turn": sorted({c["u_turn"] for c in cells}), "adaptation": sorted({c["adaptation"] for c in cells}),
    }


def paired(a: dict, b: dict) -> dict:
    seeds = sorted(set(a["per_seed"]) & set(b["per_seed"]))
    d = [b["per_seed"][s]["p5"] - a["per_seed"][s]["p5"] for s in seeds]
    m, s = mean_se(d)
    return {"n": len(d), "mean_diff": m, "se": s, "t": m / s if s else None}


def side_summary() -> dict:
    spec = BLOCKS["C"]
    out = {}
    for target in spec["targets"]:
        out[target] = {}
        base = {s: load(cell_path("C", "default", s, target)) for s in SEEDS["C"]}
        for arm in spec["arms"]:
            cells = {s: load(cell_path("C", arm, s, target)) for s in SEEDS["C"]}
            errs = [s for s in SEEDS["C"] if cell_path("C", arm, s, target, True).exists()]
            ok = {s: c for s, c in cells.items() if c is not None}
            if not ok:
                out[target][arm] = {"cells": 0, "errors": errs}
                continue
            ratios = [ok[s]["min_bulk_ess_per_gradient"] / base[s]["min_bulk_ess_per_gradient"]
                      for s in ok if base.get(s) is not None]
            out[target][arm] = {
                "cells": len(ok), "errors": errs,
                "geomean_ratio_vs_default": geomean(ratios) if ratios else None,
                "min_ratio": min(ratios) if ratios else None,
                "geomean_min_bulk_ess_per_gradient": geomean([c["min_bulk_ess_per_gradient"] for c in ok.values()]),
                "house_healthy": sum(c["house_health"] for c in ok.values()),
                "divergences": sum(c["retained_divergences"] for c in ok.values()),
                "refined_transitions": sum(c["retained_refined_transitions"] for c in ok.values()),
                "top_level_transitions": sum(c["retained_top_level_transitions"] for c in ok.values()),
                "median_step": statistics.median(h for c in ok.values() for h in c["final_step_sizes"]),
            }
    return out


def analyze(fingerprint_ok: bool | None, library_diff_empty: bool | None) -> None:
    A = {arm: funnel_arm("A", arm) for arm in ARMS}
    S = funnel_arm("S", "default")
    C = side_summary() if any(CELLS.glob("C-*.json")) else None
    d = A["default"]
    rules, hyps, preds = {}, {}, {}
    rep = d["pooled_p5"] < EXACT_P5 - d["se_p5"]
    rules["replication"] = {"default_pooled_p5": d["pooled_p5"], "se": d["se_p5"], "replicates": rep}
    dc = d["classes"]
    sig = {
        "H1_step_adaptation": {
            "neck_minus_bulk_energy_acceptance": dc["neck"]["energy_acceptance_proxy"] - dc["bulk"]["energy_acceptance_proxy"],
            "spearman_chain_p5_log_h": d["spearman_chain_p5_log_h"]},
        "H2_refinement_ceiling": {
            "deep_top_plus_exhaustion_fraction": dc["deep"]["top_plus_exhaustion_fraction"],
            "relative_deficit_c-5": -d["profile_low"][4]["relative"], "relative_deficit_c-8": -d["profile_low"][7]["relative"]},
        "H3_u_turn_rule": {
            "neck_uturn_depth_le3_share": dc["neck"]["uturn_depth_le3_fraction"],
            "bulk_uturn_depth_le3_share": dc["bulk"]["uturn_depth_le3_fraction"],
            "neck_mean_depth_default": dc["neck"]["mean_depth"],
            "neck_mean_depth_endpoint": A["endpoint"]["classes"]["neck"]["mean_depth"] if A.get("endpoint") else None},
    }
    s1 = sig["H1_step_adaptation"]
    sig["H1_step_adaptation"]["holds"] = bool(s1["neck_minus_bulk_energy_acceptance"] <= -0.10 or abs(s1["spearman_chain_p5_log_h"]) >= 0.20)
    s2 = sig["H2_refinement_ceiling"]
    sig["H2_refinement_ceiling"]["holds"] = bool(s2["deep_top_plus_exhaustion_fraction"] >= 0.01 and s2["relative_deficit_c-8"] > s2["relative_deficit_c-5"])
    s3 = sig["H3_u_turn_rule"]
    s3_ratio = s3["neck_uturn_depth_le3_share"] / s3["bulk_uturn_depth_le3_share"] if s3["bulk_uturn_depth_le3_share"] else None
    s3["neck_to_bulk_ratio"] = s3_ratio
    s3["holds"] = bool((s3_ratio is not None and s3_ratio >= 1.5) or
                       (s3["neck_mean_depth_endpoint"] is not None and abs(s3["neck_mean_depth_default"] - s3["neck_mean_depth_endpoint"]) >= 0.5))
    for x in CANDIDATES:
        a = A.get(x)
        if a is None:
            continue
        cal = a["calibration"]
        k = cal["exceed_count_with_errors"]
        D1 = abs(a["pooled_p5"] - EXACT_P5) <= a["se_p5"]
        D2 = -0.2 <= cal["mean"] <= 0.2
        D3 = k <= 4 and a["divergence_rate"] < 1e-3
        D4 = bool(fingerprint_ok and library_diff_empty)
        removes = bool(D1 and D2 and D3 and D4)
        E1 = None
        if C:
            E1 = all(C[t][x]["geomean_ratio_vs_default"] is not None and C[t][x]["geomean_ratio_vs_default"] >= 0.95
                     and C[t][x]["house_healthy"] >= C[t]["default"]["house_healthy"] - 1 for t in C)
        E2 = {"accept0.9": False, "endpoint": False, "levels10": True}[x]
        pr = paired(d, a)
        h = HYP[x]
        causal = bool(pr["t"] is not None and pr["mean_diff"] > 0 and pr["t"] >= 2.0)
        sh = sig[h]["holds"]
        hyps[h] = {"candidate": x, "paired_vs_default": pr, "candidate_raises_estimate": causal, "signature": sig[h],
                   "verdict": "SUPPORTED" if causal and sh else "candidate helps, mechanism not shown" if causal
                   else "signature present, not causal at this budget" if sh else "NOT SUPPORTED"}
        rules[x] = {"D1": {"pooled": a["pooled_p5"], "se": a["se_p5"], "abs_error": abs(a["pooled_p5"] - EXACT_P5), "held": D1},
                    "D2": {"mean_z": cal["mean"], "held": D2},
                    "D3": {"exceedances": k, "divergence_rate": a["divergence_rate"], "held": D3},
                    "D4": {"fingerprint_test_passed": fingerprint_ok, "library_diff_empty": library_diff_empty, "held": D4},
                    "removes_deficit": removes,
                    "E1": E1, "E2_preassessed": E2,
                    "recommend_for_posteriordb": bool(removes and E1 and E2),
                    "label": ("RECOMMENDED for a posteriordb confirmation (candidate default change)" if removes and E1 and E2
                              else "removes the deficit, not a default candidate" if removes else "does not remove the deficit")}
    if S:
        rA = d["relative_deficit"]
        rS = S["relative_deficit"]
        fin = rS < rA / 2 and abs(S["pooled_p5"] - EXACT_P5) <= S["se_p5"]
        per = rS >= rA / 2 and S["pooled_p5"] < EXACT_P5 - 1.5 * S["se_p5"]
        pre = [S["per_seed"][s]["prefix_p5"] for s in S["per_seed"]]
        full = [S["per_seed"][s]["p5"] for s in S["per_seed"]]
        rest = [(4 * f - p) / 3 for f, p in zip(full, pre)]  # last 60,000 = (80k*full - 20k*prefix) / 60k
        rules["sanity_arm_S"] = {"relative_deficit_A_default": rA, "relative_deficit_S": rS, "pooled_S": S["pooled_p5"], "se_S": S["se_p5"],
                                 "reading": "FINITE-RUN" if fin else "PERSISTENT-BIAS" if per else "INCONCLUSIVE",
                                 "prefix_20k_mean": statistics.fmean(pre), "last_60k_mean": statistics.fmean(rest),
                                 "paired_last_minus_prefix": mean_se([r - p for r, p in zip(rest, pre)])}
    # predictions
    cal = d["calibration"]
    preds["P1_default_replicates"] = {"observed": [d["pooled_p5"], cal["mean"]], "held": bool(0.0440 <= d["pooled_p5"] <= 0.0475 and -0.6 <= cal["mean"] <= -0.1)}
    preds["P2_lower_tail_specific"] = {"observed": [d["pooled_upper_p5"], d["se_upper_p5"]], "held": bool(abs(d["pooled_upper_p5"] - EXACT_P5) <= d["se_upper_p5"])}
    if A.get("levels10"):
        pr = paired(d, A["levels10"])
        preds["P3_levels10"] = {"observed": [dc["deep"]["top_plus_exhaustion_fraction"], pr["mean_diff"], pr["se"]],
                                "held": bool(dc["deep"]["top_plus_exhaustion_fraction"] < 0.01 and abs(pr["mean_diff"]) <= pr["se"])}
    if A.get("accept0.9"):
        ratio = A["accept0.9"]["median_final_step"] / d["median_final_step"]
        preds["P4_accept0.9_step"] = {"observed": ratio, "held": bool(0.5 <= ratio <= 0.8)}
    if A.get("endpoint"):
        pr = paired(d, A["endpoint"])
        preds["P5_endpoint"] = {"observed": [pr["mean_diff"], pr["se"]], "held": bool(abs(pr["mean_diff"]) <= pr["se"])}
    preds["P6_no_candidate_removes"] = {"observed": {x: rules[x]["removes_deficit"] for x in CANDIDATES if x in rules},
                                        "held": not any(rules[x]["removes_deficit"] for x in CANDIDATES if x in rules)}
    if S:
        preds["P7_sanity"] = {"observed": rules["sanity_arm_S"]["reading"], "held": rules["sanity_arm_S"]["reading"] in ("INCONCLUSIVE", "FINITE-RUN")}
    summary = {"schema": "funnel-tail-deficit-v1-summary", "ledger_id": "WP66", "protocol": PROTOCOL["status"],
               "decision_rules": rules, "hypotheses": hyps, "predictions": preds,
               "block_A": A, "block_S": S, "block_C": C}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    write_table(summary)
    print(json.dumps({"decision_rules": rules, "hypotheses": {k: v["verdict"] for k, v in hyps.items()}, "predictions": preds}, indent=1))


def f(x, spec=".4f"):
    return "—" if x is None else format(x, spec)


def write_table(s: dict) -> None:
    A, S, C = s["block_A"], s["block_S"], s["block_C"]
    L = ["# WP66 results tables (generated by `run_study.py analyze`)", "",
         f"Exact P(omega < -5) = P(omega > 5) = {EXACT_P5:.4f}; P(omega < -6) = {EXACT_P6:.4f}; omega variance 9.", "",
         "## Block A: 4 x 2,000/20,000, 30 seeds", "",
         "| arm | cells | err | pooled P5 ± s.e. | t | rel. deficit | upper P(>5) ± s.e. | P6 | omega var | \\|z\\|>2 | mean z | sd z | N(0,1)? | div | rate | depth caps | exhaust | median h | h range | geomean minESS/grad | median gradients | warn cells |",
         "|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---:|---:|---:|"]
    rows = [(k, v) for k, v in A.items() if v] + ([("S: default 80k", S)] if S else [])
    for name, a in rows:
        c = a["calibration"]
        L.append(f"| `{name}` | {a['cells']} | {len(a['errors'])} | {a['pooled_p5']:.4f} ± {a['se_p5']:.4f} | {a['t_p5']:+.2f} | {a['relative_deficit']:+.3f} | "
                 f"{a['pooled_upper_p5']:.4f} ± {a['se_upper_p5']:.4f} | {a['pooled_p6']:.4f} | {a['omega_variance']:.2f} | {c['exceed_count_with_errors']} | {c['mean']:+.3f} | {c['sd']:.2f} | "
                 f"{c['consistent_with_n01']} | {a['total_divergences']} | {a['divergence_rate']:.1e} | {a['total_depth_caps']} | {a['total_exhaustions']} | {a['median_final_step']:.3f} | "
                 f"{a['step_range'][0]:.3f}–{a['step_range'][1]:.3f} | {a['geomean_min_bulk_ess_per_gradient']:.2e} | {a['median_gradients']:.3g} | {a['chain_warning_cells']} |")
    L += ["", "### Tail-mass profile (pooled estimate / exact - 1; t against exact)", "",
          "| arm | " + " | ".join(f"<{-k - 1}" for k in range(10)) + " |", "|---|" + "---:|" * 10]
    for name, a in rows:
        L.append(f"| `{name}` lower | " + " | ".join(f"{p['relative']:+.3f} ({p['t']:+.1f})" if p["t"] is not None else "—" for p in a["profile_low"]) + " |")
        L.append(f"| `{name}` upper (>c) | " + " | ".join(f"{p['relative']:+.3f} ({p['t']:+.1f})" if p["t"] is not None else "—" for p in a["profile_high"]) + " |")
    L += ["", "### Retained transitions by starting omega (pooled over seeds and chains)", "",
          "| arm | class | n | mean depth | depth<=3 | U-turn at depth<=3 | depth cap | U-turn stops | exhaust stops | top level | top+exh | moved | energy-acc proxy | mean max\\|dH\\| | macro length | gradients/trans | div |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, a in rows:
        for cls in ("bulk", "neck", "deep"):
            k = a["classes"][cls]
            if not k["n"]:
                L.append(f"| `{name}` | {cls} | 0 |" + " — |" * 13)
                continue
            L.append(f"| `{name}` | {cls} | {k['n']} | {k['mean_depth']:.2f} | {k['depth_le3_fraction']:.3f} | {k['uturn_depth_le3_fraction']:.3f} | {k['depth_cap_fraction']:.4f} | {k['uturn_fraction']:.3f} | "
                     f"{k['exhaustion_stops']} | {k['top_level_selected']} | {k['top_plus_exhaustion_fraction']:.4f} | {k['moved_fraction']:.3f} | {k['energy_acceptance_proxy']:.3f} | "
                     f"{k['mean_max_abs_energy_error']:.3f} | {k['mean_macro_length']:.2f} | {k['mean_target_evaluations']:.1f} | {k['divergences']} |")
    L += ["", "Selected-level histograms (levels 0..L-1):", ""]
    for name, a in rows:
        for cls in ("bulk", "neck", "deep"):
            L.append(f"- `{name}` {cls}: {a['classes'][cls]['selected_level_histogram']}")
    L += ["", "### Chains", "", "| arm | Spearman(chain P5, log h) | P5 small-h half | P5 large-h half | P5 by retained quarter | neck entries / chain | mean excursion | median min omega | warmup last-window acceptance |",
          "|---|---:|---:|---:|---|---:|---:|---:|---:|"]
    for name, a in rows:
        L.append(f"| `{name}` | {a['spearman_chain_p5_log_h']:+.3f} | {a['chain_p5_small_h_half']:.4f} | {a['chain_p5_large_h_half']:.4f} | "
                 f"{', '.join(f'{v:.4f}' for v in a['tail_by_quarter_pooled'])} | {a['mean_neck_entries_per_chain']:.1f} | {a['mean_excursion_length']:.1f} | {a['median_min_omega']:.2f} | {a['warmup_acceptance_mean']:.3f} |")
    if C:
        L += ["", "## Block C: side check (4 x 1,000/1,000, 10 seeds)", "",
              "| target | arm | cells | err | geomean ratio vs default | min ratio | geomean minESS/grad | healthy | div | refined trans | top-level trans | median h |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for t, arms in C.items():
            for arm, v in arms.items():
                if not v.get("cells"):
                    L.append(f"| {t} | `{arm}` | 0 | {len(v['errors'])} |" + " — |" * 8)
                    continue
                L.append(f"| {t} | `{arm}` | {v['cells']} | {len(v['errors'])} | {f(v['geomean_ratio_vs_default'], '.3f')} | {f(v['min_ratio'], '.3f')} | {v['geomean_min_bulk_ess_per_gradient']:.3e} | "
                         f"{v['house_healthy']} | {v['divergences']} | {v['refined_transitions']} | {v['top_level_transitions']} | {v['median_step']:.3f} |")
    L += ["", "## Per seed, block A (P5 / z / divergences)", "", "| seed | " + " | ".join(f"`{k}`" for k, v in A.items() if v) + " |",
          "|---|" + "---|" * sum(1 for v in A.values() if v)]
    for seed in SEEDS["A"]:
        cells = []
        for k, v in A.items():
            if not v:
                continue
            r = v["per_seed"].get(str(seed))
            cells.append("error" if r is None and seed in v["errors"] else "—" if r is None else f"{r['p5']:.4f} / {r['z']:+.2f} / {r['divergences']}")
        L.append(f"| {seed} | " + " | ".join(cells) + " |")
    if S:
        L += ["", "## Per seed, block S (P5 full 80k / prefix 20k / z)", "", "| seed | P5 80k | P5 first 20k | z |", "|---|---:|---:|---:|"]
        for seed, r in S["per_seed"].items():
            L.append(f"| {seed} | {r['p5']:.4f} | {r['prefix_p5']:.4f} | {r['z']:+.2f} |")
    L += ["", "## Decision rules", "", "```json", json.dumps(s["decision_rules"], indent=1), "```", "",
          "## Hypotheses", "", "```json", json.dumps(s["hypotheses"], indent=1), "```", "",
          "## Predictions", "", "```json", json.dumps(s["predictions"], indent=1), "```", ""]
    (ART / "results-table.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    ART.mkdir(parents=True, exist_ok=True)
    cmd = sys.argv[1:]
    if cmd[:1] == ["run"] and len(cmd) == 2 and cmd[1] in BLOCKS:
        run(cmd[1])
    elif cmd[:1] == ["analyze"]:
        env = json.loads((ART / "environment.json").read_text(encoding="utf-8")) if (ART / "environment.json").exists() else {}
        analyze(env.get("kernel_fingerprint_test_passed"), env.get("library_diff_empty"))
    else:
        sys.exit(__doc__)
