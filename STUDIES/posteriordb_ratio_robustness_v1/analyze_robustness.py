#!/usr/bin/env python3
"""WP72 analysis: the fixed-16 oWALNUTS / CmdStan ESS-per-gradient headline under four frozen statistics.

    python analyze_robustness.py      # writes artifacts/summary.json and artifacts/results-table.md

Pool (Linux, 18 seeds): WP64's v7-seed cells (560561-560563) and extension-seed cells (620601-620603),
read unchanged from ../posteriordb_bench_v7_linux_v1/artifacts/{v7,ext}/cells, plus this study's twelve
seeds (artifacts/cells). Every rule here is fixed in protocol.json before the first cell.
Reported only: the same statistics on the six Windows seeds (WP56 + WP62 cells).
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
STUDY = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
EXTP = json.loads((HERE.parent / "posteriordb_bench_v7_seed_extension" / "protocol.json").read_text(encoding="utf-8"))
MODELS = EXTP["fixed_non_arma_models"]
ARMS = ("owalnuts", "cmdstan")
A = STUDY["analysis"]
EXCLUDED_D = A["statistics"]["d"]["excluded_model"]
WP64 = HERE.parent / "posteriordb_bench_v7_linux_v1" / "artifacts"
WIN_V7 = HERE.parent / "posteriordb_bench_v7" / "artifacts"
WIN_EXT = HERE.parent / "posteriordb_bench_v7_seed_extension" / "artifacts"
OWN = HERE / "artifacts"
SOURCES_LINUX = [(WP64 / "v7", STUDY["seeds"]["wp64_v7"]), (WP64 / "ext", STUDY["seeds"]["wp64_ext"]), (OWN, STUDY["seeds"]["new"])]
SOURCES_WINDOWS = [(WIN_V7, STUDY["seeds"]["wp64_v7"]), (WIN_EXT, STUDY["seeds"]["wp64_ext"])]


def short(m: str) -> str:
    return m.replace("-", "__")


def load(sources) -> dict:
    """data[model][arm][seed] = cell dict (with 'parameters') or None if missing."""
    data: dict = {m: {a: {} for a in ARMS} for m in MODELS}
    for d, seeds in sources:
        for m in MODELS:
            for a in ARMS:
                for s in seeds:
                    p = d / "cells" / f"{short(m)}-{a}-{s}.json"
                    data[m][a][s] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    return data


def ok(c) -> bool:
    return bool(c) and c.get("status") == "ok" and c.get("min_bulk_ess_per_gradient") is not None


def passed(c) -> bool:
    return bool(c) and bool(c.get("passed"))


def geomean(xs) -> float:
    xs = [x for x in xs if x is not None and math.isfinite(x) and x > 0]
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs))) if xs else float("nan")


def min_ok(n: int) -> int:
    return math.ceil(A["min_ok_fraction"] * n)


def ratios_a(data, seeds, models) -> dict:
    out = {}
    for m in models:
        v = {a: [data[m][a][s]["min_bulk_ess_per_gradient"] for s in seeds if ok(data[m][a].get(s))] for a in ARMS}
        if all(len(v[a]) >= min_ok(len(seeds)) for a in ARMS):
            out[m] = statistics.median(v["owalnuts"]) / statistics.median(v["cmdstan"])
    return out


def ratios_b(data, seeds, models) -> dict:
    out = {}
    for m in models:
        j = [s for s in seeds if passed(data[m]["owalnuts"].get(s)) and passed(data[m]["cmdstan"].get(s))]
        if len(j) >= A["statistics"]["b"]["min_joint_passing_seeds"]:
            o = statistics.median(data[m]["owalnuts"][s]["min_bulk_ess_per_gradient"] for s in j)
            c = statistics.median(data[m]["cmdstan"][s]["min_bulk_ess_per_gradient"] for s in j)
            out[m] = o / c
    return out


def ratios_c(data, seeds, models) -> dict:
    out = {}
    for m in models:
        r = [data[m]["owalnuts"][s]["min_bulk_ess_per_gradient"] / data[m]["cmdstan"][s]["min_bulk_ess_per_gradient"]
             for s in seeds if ok(data[m]["owalnuts"].get(s)) and ok(data[m]["cmdstan"].get(s))]
        if len(r) >= min_ok(len(seeds)):
            out[m] = statistics.median(r)
    return out


STATS = {
    "a": lambda d, s, ms: ratios_a(d, s, ms),
    "b": lambda d, s, ms: ratios_b(d, s, ms),
    "c": lambda d, s, ms: ratios_c(d, s, ms),
    "d": lambda d, s, ms: ratios_a(d, s, [m for m in ms if m != EXCLUDED_D]),
}


def evaluate(data, seeds: list[int], label: str, bootstrap: bool = True) -> dict:
    res = {}
    rng = np.random.default_rng(A["bootstrap"]["rng_seed"])
    B = A["bootstrap"]["resamples"]
    idx = rng.integers(0, len(seeds), size=(B, len(seeds))) if bootstrap else None
    for k, f in STATS.items():
        r = f(data, seeds, MODELS)
        g = geomean(r.values())
        lomo = {m: abs(math.log(g) - math.log(geomean(v for mm, v in r.items() if mm != m))) for m in r} if len(r) > 1 else {}
        worst = max(lomo, key=lomo.get) if lomo else None
        entry = {"value": g, "models": len(r), "per_model": r,
                 "lomo_max_abs_log_influence": lomo[worst] if worst else None, "lomo_most_influential_model": worst,
                 "lomo_value_without_most_influential": geomean(v for mm, v in r.items() if mm != worst) if worst else None}
        if bootstrap:
            vals, nm = [], []
            for row in idx:
                bs = [seeds[i] for i in row]
                rr = f(data, bs, MODELS)
                vals.append(geomean(rr.values()))
                nm.append(len(rr))
            vals = np.asarray(vals)
            fin = vals[np.isfinite(vals)]
            lo, hi = A["bootstrap"]["percentiles"]
            entry["bootstrap"] = {"interval": [float(np.percentile(fin, lo)), float(np.percentile(fin, hi))],
                                  "median": float(np.median(fin)), "finite_resamples": int(fin.size), "resamples": B,
                                  "models_included_median": float(np.median(nm)), "models_included_range": [int(min(nm)), int(max(nm))]}
        res[k] = entry
    return {"label": label, "seeds": seeds, "statistics": res}


def stuck_chains(cell, draws_path: Path) -> int | None:
    """Chains whose mean is displaced: max over gate parameters |chain mean - reference mean| / reference sd > threshold."""
    if not ok(cell) or not draws_path.exists():
        return None
    z = np.load(draws_path)
    x, names = z["draws"], [str(n) for n in z["names"]]
    P = cell["parameters"]
    ref_m = np.array([P[n]["ref_mean"] for n in names])
    ref_sd = np.array([P[n]["ref_sd"] for n in names])
    dev = np.abs(x.mean(1) - ref_m) / ref_sd
    return int((np.nanmax(dev, axis=1) > A["stuck_chain"]["threshold_ref_sd"]).sum())


def main() -> None:
    lin = load(SOURCES_LINUX)
    win = load(SOURCES_WINDOWS)
    all18 = STUDY["seeds"]["wp64_v7"] + STUDY["seeds"]["wp64_ext"] + STUDY["seeds"]["new"]
    six = STUDY["seeds"]["wp64_v7"] + STUDY["seeds"]["wp64_ext"]
    primary = evaluate(lin, all18, "linux_18_seeds")
    reported = {"linux_new_12": evaluate(lin, STUDY["seeds"]["new"], "linux_new_12"),
                "linux_wp64_6": evaluate(lin, six, "linux_wp64_6"),
                "windows_6": evaluate(win, six, "windows_6")}
    # headline selection rule (frozen)
    elig = A["headline_rule"]["eligible"]
    infl = {k: primary["statistics"][k]["lomo_max_abs_log_influence"] for k in elig}
    best = min(elig, key=lambda k: (infl[k] if infl[k] is not None else math.inf, 0 if k == A["headline_rule"]["tie_break"] else 1))
    # predictions
    pr = STUDY["predictions"]
    S = primary["statistics"]
    preds = {
        "Q1_b_in_interval": {"value": S["b"]["value"], "interval": pr["Q1"]["interval"], "held": pr["Q1"]["interval"][0] <= S["b"]["value"] <= pr["Q1"]["interval"][1]},
        "Q2_c_in_interval": {"value": S["c"]["value"], "interval": pr["Q2"]["interval"], "held": pr["Q2"]["interval"][0] <= S["c"]["value"] <= pr["Q2"]["interval"][1]},
        "Q3_a_above_1_only_because_of_hmm_drive_0": {"value": {"a": S["a"]["value"], "d": S["d"]["value"]}, "held": S["a"]["value"] > 1.0 and S["d"]["value"] <= 1.0},
        "Q4_rule_selects_c": {"value": best, "influence": infl, "held": best == "c"},
    }
    # gates and stuck chains
    passes = {a: {"new_12": [sum(passed(lin[m][a].get(s)) for m in MODELS for s in STUDY["seeds"]["new"]), 16 * len(STUDY["seeds"]["new"])],
                  "all_18": [sum(passed(lin[m][a].get(s)) for m in MODELS for s in all18), 16 * len(all18)]} for a in ARMS}
    stuck = {}
    for d, seeds in SOURCES_LINUX:
        for m in MODELS:
            for a in ARMS:
                for s in seeds:
                    stuck.setdefault(m, {}).setdefault(a, {})[str(s)] = stuck_chains(lin[m][a].get(s), d / "draws" / f"{short(m)}-{a}-{s}.npz")
    hmm = "bball_drive_event_0-hmm_drive_0"
    hmm_table = {a: {"chains_per_seed": stuck[hmm][a],
                     "cells_with_a_stuck_chain": sum(1 for v in stuck[hmm][a].values() if v),
                     "cells_counted": sum(1 for v in stuck[hmm][a].values() if v is not None)} for a in ARMS}
    stuck_totals = {m: {a: {"cells_with_stuck": sum(1 for v in stuck[m][a].values() if v),
                            "chains": sum(v for v in stuck[m][a].values() if v), "counted": sum(1 for v in stuck[m][a].values() if v is not None)}
                        for a in ARMS} for m in MODELS}
    summary = {"schema": "posteriordb-ratio-robustness-v1-summary", "ledger_id": STUDY["ledger_id"],
               "primary_linux_18": primary, "reported": reported, "headline_rule": {"selected": best, "influence": infl,
               "proposed_in_advance": A["headline_rule"]["proposed"]}, "predictions": preds, "passes": passes,
               "stuck_chains_hmm_drive_0": hmm_table, "stuck_chains_all_models": stuck_totals, "stuck_chains_per_cell": stuck,
               "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
               "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    OWN.mkdir(parents=True, exist_ok=True)
    (OWN / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    def f(x, fmt=".3f"):
        return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)

    names = {k: v["name"] for k, v in A["statistics"].items()}
    L = ["# WP72 posteriordb ratio robustness — results", "",
         "oWALNUTS / CmdStan min-bulk-ESS per gradient, fixed 16, Linux. Bootstrap: seeds resampled with replacement, "
         f"{A['bootstrap']['resamples']} resamples, percentile interval.", "",
         "| statistic | pool | value | 95% bootstrap interval | models | most influential model (value without it) |",
         "|---|---|---:|---|---:|---|"]
    for ev in [primary] + list(reported.values()):
        for k, e in ev["statistics"].items():
            b = e.get("bootstrap", {})
            L.append(f"| ({k}) {names[k]} | {ev['label']} | {f(e['value'])} | [{f(b.get('interval', [None])[0])}, {f(b.get('interval', [None, None])[1])}] | "
                     f"{e['models']} | {e['lomo_most_influential_model']} ({f(e['lomo_value_without_most_influential'])}) |")
    L += ["", f"Headline rule (frozen): eligible {elig}; smaller leave-one-model-out max |log| influence wins. "
          f"Influence: {', '.join(f'{k} {f(v)}' for k, v in infl.items())}. Selected: **({best})**; proposed in advance: ({A['headline_rule']['proposed']}).", "",
          "## Per-model ratios, Linux 18 seeds", "", "| model | (a) | (b) | (c) | stuck-chain cells oWALNUTS / CmdStan |", "|---|---:|---:|---:|---|"]
    for m in MODELS:
        L.append(f"| {m} | {f(S['a']['per_model'].get(m))} | {f(S['b']['per_model'].get(m))} | {f(S['c']['per_model'].get(m))} | "
                 f"{stuck_totals[m]['owalnuts']['cells_with_stuck']}/{stuck_totals[m]['owalnuts']['counted']} / "
                 f"{stuck_totals[m]['cmdstan']['cells_with_stuck']}/{stuck_totals[m]['cmdstan']['counted']} |")
    L += ["", "## hmm_drive_0: stuck chains per seed (|chain mean - reference mean| > "
          f"{A['stuck_chain']['threshold_ref_sd']} reference sd)", "", "| seed | oWALNUTS | CmdStan |", "|---|---:|---:|"]
    for s in all18:
        L.append(f"| {s} | {hmm_table['owalnuts']['chains_per_seed'].get(str(s))} | {hmm_table['cmdstan']['chains_per_seed'].get(str(s))} |")
    L.append(f"| cells with a stuck chain | {hmm_table['owalnuts']['cells_with_a_stuck_chain']}/{hmm_table['owalnuts']['cells_counted']} | "
             f"{hmm_table['cmdstan']['cells_with_a_stuck_chain']}/{hmm_table['cmdstan']['cells_counted']} |")
    L += ["", "## Gates", "", "| arm | new 12 seeds | all 18 seeds |", "|---|---:|---:|"]
    for a in ARMS:
        L.append(f"| {a} | {passes[a]['new_12'][0]}/{passes[a]['new_12'][1]} | {passes[a]['all_18'][0]}/{passes[a]['all_18'][1]} |")
    L += ["", "## Predictions", "", "| prediction | value | held |", "|---|---|---|"]
    for k, v in preds.items():
        L.append(f"| {k} | {v['value']} | {v['held']} |")
    (OWN / "results-table.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
