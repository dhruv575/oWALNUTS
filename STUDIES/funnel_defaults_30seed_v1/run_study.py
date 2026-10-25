#!/usr/bin/env python3
"""WP53 driver: funnel tail-mass calibration over 30 fresh seeds (stdlib only).

    python run_study.py run A        # block A (2,000/20,000; default, delta2), resumable, sequential
    python run_study.py run B        # block B (1,000/1,000; default, delta2, delta0.5)
    python run_study.py analyze      # artifacts/summary.json + artifacts/results-table.md

Cells: artifacts/cells/<block>-<arm>-<seed>.json; errors as <...>.error.json. Never rerun.
"""
from __future__ import annotations

import json
import math
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
ART = HERE / "artifacts"
CELLS = ART / "cells"
FUNNEL = HERE / "target" / "release" / "funnel.exe"
SEEDS = PROTOCOL["seeds"]
BLOCKS = PROTOCOL["blocks"]
EXACT_P5 = 0.0477903522728147
EXACT_P6 = 0.0227501319481792
P_EXCEED = 2 * (1 - 0.5 * (1 + math.erf(2 / math.sqrt(2))))  # 0.0455


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with (ART / "run-log.txt").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def cell_path(block: str, arm: str, seed: int, error: bool = False) -> Path:
    return CELLS / f"{block}-{arm}-{seed}{'.error' if error else ''}.json"


def run(block: str) -> None:
    CELLS.mkdir(parents=True, exist_ok=True)
    spec = BLOCKS[block]
    for seed in SEEDS:
        for arm in spec["arms"]:
            out = cell_path(block, arm, seed)
            if out.exists() or cell_path(block, arm, seed, True).exists():
                continue
            cp = subprocess.run([str(FUNNEL), arm, str(spec["warmup"]), str(spec["draws"]), str(seed), str(out)],
                                capture_output=True, text=True, timeout=1800)
            log(f"{block} {cp.stderr.strip()[-400:]}")
            if cp.returncode != 0 or not out.exists():
                cell_path(block, arm, seed, True).write_text(json.dumps(
                    {"block": block, "arm": arm, "seed": seed, "status": "error", "returncode": cp.returncode,
                     "stderr": cp.stderr[-4000:]}, indent=1) + "\n", encoding="utf-8")
    log(f"block {block} complete")


# ----------------------------------------------------------------------------- statistics


def norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def binom_upper(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))


def gammainc_lower_reg(a: float, x: float) -> float:
    """Regularized lower incomplete gamma P(a, x) (series / continued fraction)."""
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
    # continued fraction for Q
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
    q = math.exp(-x + a * math.log(x) - math.lgamma(a)) * h
    return 1 - q


def chi2_cdf(x: float, df: int) -> float:
    return gammainc_lower_reg(df / 2, x / 2)


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
    mean_stat = mean * math.sqrt(n)
    p_mean = 2 * (1 - norm_cdf(abs(mean_stat)))
    chi = (n - 1) * sd * sd
    c = chi2_cdf(chi, n - 1)
    p_var = 2 * min(c, 1 - c)
    d, p_ks = ks_normal(z)
    return {"n": n, "exceed_count": k, "exceed_rate": k / n, "binom_p_ge_k": binom_upper(k, n, P_EXCEED),
            "expected_exceed": n * P_EXCEED, "mean": mean, "mean_se_null": 1 / math.sqrt(n), "p_mean": p_mean,
            "sd": sd, "chi2": chi, "p_variance": p_var, "ks_d": d, "p_ks": p_ks,
            "consistent_with_n01": bool(p_mean >= 0.05 and p_var >= 0.05 and p_ks >= 0.05),
            "min": min(z), "max": max(z), "median": statistics.median(z),
            "n_below_minus2": sum(v < -2 for v in z), "n_above_plus2": sum(v > 2 for v in z)}


HIST_EDGES = [-math.inf, -4, -3, -2, -1, 0, 1, 2, 3, 4, math.inf]
HIST_LABELS = ["< -4", "[-4,-3)", "[-3,-2)", "[-2,-1)", "[-1,0)", "[0,1)", "[1,2)", "[2,3)", "[3,4)", ">= 4"]


def histogram(z: list[float]) -> list[int]:
    return [sum(lo <= v < hi for v in z) for lo, hi in zip(HIST_EDGES[:-1], HIST_EDGES[1:])]


# ----------------------------------------------------------------------------- analysis


def load_cell(block: str, arm: str, seed: int) -> dict | None:
    p = cell_path(block, arm, seed)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def cell_row(c: dict) -> dict:
    ch = c["chains_data"]
    t = c["tail_mass"]
    div = sum(x["divergences"] for x in ch)
    gross = {
        "zero_retained_divergences": div == 0,
        "rank_rhat_le_1.05": c["omega"]["rhat"] <= 1.05,
        "p5_abs_error_le_0.025": abs(t["estimate"] - EXACT_P5) <= 0.025,
        "p6_abs_error_le_0.015": abs(c["tail_mass_6"]["estimate"] - EXACT_P6) <= 0.015,
        "omega_variance_in_5_13": 5.0 <= c["omega"]["variance"] <= 13.0,
    }
    kinds: dict[str, int] = {}
    for w in c["chain_warnings"]:
        kinds[w["kind"]] = kinds.get(w["kind"], 0) + 1
    steps = [x["warmup_end_step_size"] for x in ch]
    return {
        "seed": c["seed"], "z": t["z"], "estimate": t["estimate"], "mcse": t["mcse"], "z_batch": t["z_batch_means"],
        "z6": c["tail_mass_6"]["z"], "estimate6": c["tail_mass_6"]["estimate"],
        "omega_variance": c["omega"]["variance"], "omega_rhat": c["omega"]["rhat"],
        "omega_bulk_ess": c["omega"]["bulk_ess"], "omega_tail_ess": c["omega"]["tail_ess"],
        "min_bulk_ess": c["min_bulk_ess"], "min_tail_ess": c["min_tail_ess"], "max_rhat": c["max_rhat"],
        "divergences": div, "per_chain_divergences": [x["divergences"] for x in ch],
        "depth_caps": sum(x["depth_caps"] for x in ch),
        "exhaustions": sum(x["refinement_exhaustions"] for x in ch),
        "invalid_stops": sum(x["invalid_stops"] for x in ch),
        "warmup_divergences": sum(x["warmup_divergences"] for x in ch),
        "nonfinite_rejections": sum(x["nonfinite_position_rejections_retained"] + x["nonfinite_position_rejections_warmup"] for x in ch),
        "gradients": c["target_calls_total"], "retained_gradients": c["retained_target_calls"],
        "min_bulk_ess_per_gradient": c["min_bulk_ess_per_gradient"],
        "warmup_end_steps": steps, "step_ratio_max_min": max(steps) / min(steps),
        "chain_warnings": len(c["chain_warnings"]), "chain_warning_kinds": kinds,
        "chain_warning_lines": c["chain_warning_lines"],
        "gross_safety": {"checks": gross, "passed": all(gross.values())},
        "house_health": bool(c["max_rhat"] <= 1.01 and c["min_bulk_ess"] >= 400 and c["min_tail_ess"] >= 400 and div == 0),
        "wall_seconds_contended": c["wall_seconds_contended"],
        "algorithm_revision": c["algorithm_revision"],
    }


def geomean(xs: list[float]) -> float:
    return math.exp(statistics.fmean(math.log(x) for x in xs))


def arm_summary(block: str, arm: str) -> dict | None:
    rows, errors = [], []
    for seed in SEEDS:
        c = load_cell(block, arm, seed)
        if c is not None:
            rows.append(cell_row(c))
        elif cell_path(block, arm, seed, True).exists():
            errors.append(seed)
    if not rows and not errors:
        return None
    draws = BLOCKS[block]["draws"]
    # an errored cell counts as |z| > 2: z = +inf placeholder is excluded from moments
    z = [r["z"] for r in rows]
    cal = calibration(z) if len(z) >= 3 else None
    if cal and errors:
        cal["exceed_count_with_errors"] = cal["exceed_count"] + len(errors)
    total_div = sum(r["divergences"] for r in rows)
    transitions = len(rows) * 4 * draws
    pooled_below = sum(r["estimate"] for r in rows) / len(rows) if rows else None
    out = {
        "cells": len(rows), "errors": errors, "calibration": cal, "histogram": histogram(z),
        "z_by_seed": {str(r["seed"]): r["z"] for r in rows},
        "pooled_p5": pooled_below, "pooled_p5_error": pooled_below - EXACT_P5 if rows else None,
        "pooled_p6": statistics.fmean(r["estimate6"] for r in rows) if rows else None,
        "total_divergences": total_div, "retained_transitions": transitions,
        "divergence_rate": total_div / transitions if transitions else None,
        "divergence_free_seeds": sum(r["divergences"] == 0 for r in rows),
        "max_divergences_cell": max((r["divergences"] for r in rows), default=None),
        "total_depth_caps": sum(r["depth_caps"] for r in rows),
        "total_exhaustions": sum(r["exhaustions"] for r in rows),
        "total_invalid_stops": sum(r["invalid_stops"] for r in rows),
        "total_nonfinite_rejections": sum(r["nonfinite_rejections"] for r in rows),
        "gross_safe_seeds": sum(r["gross_safety"]["passed"] for r in rows),
        "house_healthy_seeds": sum(r["house_health"] for r in rows),
        "median_min_bulk_ess": statistics.median(r["min_bulk_ess"] for r in rows),
        "geomean_min_bulk_ess_per_gradient": geomean([r["min_bulk_ess_per_gradient"] for r in rows]),
        "median_gradients": statistics.median(r["gradients"] for r in rows),
        "total_gradients": sum(r["gradients"] for r in rows),
        "median_warmup_end_step": statistics.median(s for r in rows for s in r["warmup_end_steps"]),
        "median_step_ratio_max_min": statistics.median(r["step_ratio_max_min"] for r in rows),
        "chain_warning_cells": sum(r["chain_warnings"] > 0 for r in rows),
        "chain_warning_kinds": {k: sum(r["chain_warning_kinds"].get(k, 0) for r in rows)
                                for k in sorted({k for r in rows for k in r["chain_warning_kinds"]})},
        "rows": rows,
    }
    return out


def analyze() -> None:
    blocks = {b: {arm: arm_summary(b, arm) for arm in spec["arms"]} for b, spec in BLOCKS.items()}
    A = blocks["A"]
    B = blocks["B"]
    d, t = A["default"], A["delta2"]
    pr = PROTOCOL["predictions"]
    preds, rules = {}, {}
    if d and t and d["calibration"] and t["calibration"]:
        kd = d["calibration"].get("exceed_count_with_errors", d["calibration"]["exceed_count"])
        kt = t["calibration"].get("exceed_count_with_errors", t["calibration"]["exceed_count"])
        preds["P1_default_exceedance"] = {"predicted": pr["P1_default_exceedance_seeds"], "observed": kd,
                                          "held": pr["P1_default_exceedance_seeds"][0] <= kd <= pr["P1_default_exceedance_seeds"][1]}
        m, s = d["calibration"]["mean"], d["calibration"]["sd"]
        preds["P2_default_mean_z"] = {"predicted": pr["P2_default_mean_z"], "observed": m,
                                      "held": pr["P2_default_mean_z"][0] <= m <= pr["P2_default_mean_z"][1]}
        preds["P2_default_sd_z"] = {"predicted": pr["P2_default_sd_z"], "observed": s,
                                    "held": pr["P2_default_sd_z"][0] <= s <= pr["P2_default_sd_z"][1]}
        preds["P3_delta2_exceedance"] = {"predicted": f"<= {kd} + {pr['P3_delta2_exceedance_le_default_plus']}",
                                         "observed": kt, "held": kt <= kd + pr["P3_delta2_exceedance_le_default_plus"]}
        dd, td = d["total_divergences"], t["total_divergences"]
        held4 = (td == 0) if dd == 0 else td <= pr["P4_delta2_divergences_le_x_default"] * dd
        preds["P4_delta2_divergences"] = {"predicted": f"<= 3 x {dd}", "observed": td,
                                          "ratio": td / dd if dd else None, "held": held4}
        r1 = kd / 30 > 0.20 or abs(m) > 0.5
        rules["R1_default_calibration_failure"] = {"exceed_rate": kd / 30, "mean_z": m, "triggered": r1,
                                                    "bias_direction": "estimate too low (tail under-sampled)" if m < 0 else "estimate too high",
                                                    "pooled_p5_error": d["pooled_p5_error"]}
        a = kt <= kd + 2
        b = abs(t["calibration"]["mean"]) <= 0.5
        c = t["divergence_rate"] < 0.001
        rules["R2_recommend_delta2"] = {"a_exceedance_le_default_plus_2": {"value": [kt, kd], "held": a},
                                        "b_abs_mean_z_le_0.5": {"value": t["calibration"]["mean"], "held": b},
                                        "c_divergence_rate_lt_0.001": {"value": t["divergence_rate"], "held": c},
                                        "recommend": bool(a and b and c)}
    if all(B.get(arm) for arm in BLOCKS["B"]["arms"]):
        tot = {arm: B[arm]["total_divergences"] for arm in BLOCKS["B"]["arms"]}
        fewest = tot["delta0.5"] < min(tot["default"], tot["delta2"])
        most = tot["delta2"] > max(tot["default"], tot["delta0.5"])
        preds["P5_block_B_divergence_order"] = {"observed": tot, "held": bool(fewest and most)}
    else:
        preds["P5_block_B_divergence_order"] = {"observed": "block B not run or incomplete", "held": None}
    summary = {"schema": "funnel-defaults-30seed-v1-summary", "protocol": PROTOCOL["status"],
               "predictions": preds, "decision_rules": rules,
               "blocks": {b: {arm: ({k: v for k, v in s.items()} if s else None) for arm, s in arms.items()}
                          for b, arms in blocks.items()}}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    write_table(blocks, preds, rules)
    print(json.dumps({"predictions": preds, "decision_rules": rules}, indent=1))


def f(x, spec=".3f"):
    return "—" if x is None else format(x, spec)


def write_table(blocks, preds, rules) -> None:
    L = ["# WP53 results tables (generated by `run_study.py analyze`)", ""]
    for b, arms in blocks.items():
        spec = BLOCKS[b]
        L += [f"## Block {b}: 4 x {spec['warmup']:,}/{spec['draws']:,}", ""]
        present = {a: s for a, s in arms.items() if s}
        if not present:
            L += ["Not run.", ""]
            continue
        L += ["| arm | cells | errors | \\|z\\|>2 | binom p | mean z | sd z | p(mean) | p(var) | KS p | consistent N(0,1) | min z | max z | pooled P5 | pooled P6 | divergences | rate | div-free | depth caps | exhaustions | nonfinite rej. | gross-safe | house-healthy | median min bulk ESS | geomean minESS/grad | median gradients | median end-warmup h | warn cells |",
              "|---|" + "---:|" * 27]
        for a, s in present.items():
            c = s["calibration"] or {}
            L.append(f"| `{a}` | {s['cells']} | {len(s['errors'])} | {c.get('exceed_count')} | {f(c.get('binom_p_ge_k'))} | {f(c.get('mean'), '+.3f')} | {f(c.get('sd'))} | "
                     f"{f(c.get('p_mean'))} | {f(c.get('p_variance'))} | {f(c.get('p_ks'))} | {c.get('consistent_with_n01')} | {f(c.get('min'), '+.2f')} | {f(c.get('max'), '+.2f')} | "
                     f"{f(s['pooled_p5'], '.4f')} | {f(s['pooled_p6'], '.4f')} | {s['total_divergences']} | {f(s['divergence_rate'], '.2e')} | {s['divergence_free_seeds']} | {s['total_depth_caps']} | "
                     f"{s['total_exhaustions']} | {s['total_nonfinite_rejections']} | {s['gross_safe_seeds']} | {s['house_healthy_seeds']} | {f(s['median_min_bulk_ess'], '.0f')} | {f(s['geomean_min_bulk_ess_per_gradient'], '.2e')} | "
                     f"{f(s['median_gradients'], '.3g')} | {f(s['median_warmup_end_step'], '.3f')} | {s['chain_warning_cells']} |")
        L += ["", "z histogram (unit bins):", "", "| bin | " + " | ".join(f"`{a}`" for a in present) + " | N(0,1) expected |",
              "|---|" + "---:|" * (len(present) + 1)]
        n = 30
        exp_counts = [n * (norm_cdf(hi) - norm_cdf(lo)) for lo, hi in zip(HIST_EDGES[:-1], HIST_EDGES[1:])]
        for i, lab in enumerate(HIST_LABELS):
            L.append(f"| {lab} | " + " | ".join(str(s["histogram"][i]) for s in present.values()) + f" | {exp_counts[i]:.1f} |")
        L += ["", "Chain-warning kinds: " + "; ".join(f"`{a}` {s['chain_warning_kinds']}" for a, s in present.items()), "",
              "Per seed (z / divergences / depth caps / min bulk ESS / gradients / end-of-warmup h min-max / warnings):", "",
              "| seed | " + " | ".join(f"`{a}`" for a in present) + " |", "|---|" + "---|" * len(present)]
        for seed in SEEDS:
            cells = []
            for a, s in present.items():
                r = next((r for r in s["rows"] if r["seed"] == seed), None)
                if r is None:
                    cells.append("error" if seed in s["errors"] else "—")
                else:
                    cells.append(f"{r['z']:+.2f} / {r['divergences']} / {r['depth_caps']} / {r['min_bulk_ess']:.0f} / {r['gradients'] / 1e6:.2f}M / "
                                 f"{min(r['warmup_end_steps']):.3f}-{max(r['warmup_end_steps']):.3f} / {r['chain_warnings']}")
            L.append(f"| {seed} | " + " | ".join(cells) + " |")
        L.append("")
    L += ["## Predictions", "", "| prediction | predicted | observed | held |", "|---|---|---|---|"]
    for k, v in preds.items():
        L.append(f"| {k} | {v.get('predicted', '')} | {v['observed']} | {v['held']} |")
    L += ["", "## Decision rules", "", "```json", json.dumps(rules, indent=1), "```", ""]
    (ART / "results-table.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    ART.mkdir(parents=True, exist_ok=True)
    cmd = sys.argv[1:]
    if cmd[:1] == ["run"] and len(cmd) == 2 and cmd[1] in BLOCKS:
        run(cmd[1])
    elif cmd == ["analyze"]:
        analyze()
    else:
        sys.exit(__doc__)
