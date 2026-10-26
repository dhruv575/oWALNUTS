#!/usr/bin/env python3
"""WP76 analysis: oWALNUTS vs nutpie (and CmdStan) on the fixed 16 x 18 Linux seeds, statistic (c).

    python analyze_nutpie18.py      # writes artifacts/summary.json and artifacts/results-table.md

oWALNUTS and CmdStan cells are read unchanged from WP64 (../posteriordb_bench_v7_linux_v1/artifacts/{v7,ext})
and WP72 (../posteriordb_ratio_robustness_v1/artifacts); nutpie cells are this study's. Statistic (c) is
WP72's: per model, the median over seeds of the paired per-seed ratio (both cells status ok), a model
entering with at least ceil(5n/6) paired seeds; geomean over models; seed bootstrap. Fixed in protocol.json.
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
A = STUDY["analysis"]
MODELS = STUDY["models"]
SEEDS = STUDY["seeds"]
ALL = SEEDS["all"]
WP64 = HERE.parent / "posteriordb_bench_v7_linux_v1" / "artifacts"
WP72 = HERE.parent / "posteriordb_ratio_robustness_v1" / "artifacts"
OWN = HERE / "artifacts"
SOURCES = {
    "owalnuts": [(WP64 / "v7", SEEDS["wp64_v7"]), (WP64 / "ext", SEEDS["wp64_ext"]), (WP72, SEEDS["wp72"])],
    "cmdstan": [(WP64 / "v7", SEEDS["wp64_v7"]), (WP64 / "ext", SEEDS["wp64_ext"]), (WP72, SEEDS["wp72"])],
    "nutpie": [(OWN, ALL)],
}
ARMS = list(SOURCES)


def short(m: str) -> str:
    return m.replace("-", "__")


def load() -> tuple[dict, dict]:
    data: dict = {m: {a: {} for a in ARMS} for m in MODELS}
    where: dict = {m: {a: {} for a in ARMS} for m in MODELS}
    for a, srcs in SOURCES.items():
        for d, seeds in srcs:
            for m in MODELS:
                for s in seeds:
                    p = d / "cells" / f"{short(m)}-{a}-{s}.json"
                    data[m][a][s] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
                    where[m][a][s] = d
    return data, where


def ok(c, key) -> bool:
    return bool(c) and c.get("status") == "ok" and c.get(key) is not None and math.isfinite(c[key]) and c[key] > 0


def geomean(xs) -> float:
    xs = [x for x in xs if x is not None and math.isfinite(x) and x > 0]
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs))) if xs else float("nan")


def ratios_c(data, seeds, ours, theirs, key) -> dict:
    out = {}
    need = math.ceil(A["min_ok_fraction"] * len(seeds))
    for m in MODELS:
        r = [data[m][ours][s][key] / data[m][theirs][s][key] for s in seeds
             if ok(data[m][ours].get(s), key) and ok(data[m][theirs].get(s), key)]
        if len(r) >= need:
            out[m] = statistics.median(r)
    return out


def evaluate(data, ours, theirs, key) -> dict:
    r = ratios_c(data, ALL, ours, theirs, key)
    g = geomean(r.values())
    lomo = {m: abs(math.log(g) - math.log(geomean(v for mm, v in r.items() if mm != m))) for m in r} if len(r) > 1 else {}
    worst = max(lomo, key=lomo.get) if lomo else None
    rng = np.random.default_rng(A["bootstrap"]["rng_seed"])
    idx = rng.integers(0, len(ALL), size=(A["bootstrap"]["resamples"], len(ALL)))
    vals = np.asarray([geomean(ratios_c(data, [ALL[i] for i in row], ours, theirs, key).values()) for row in idx])
    fin = vals[np.isfinite(vals)]
    lo, hi = A["bootstrap"]["percentiles"]
    return {"value": g, "models": len(r), "per_model": r, "interval": [float(np.percentile(fin, lo)), float(np.percentile(fin, hi))],
            "lomo_max_abs_log_influence": lomo.get(worst), "lomo_most_influential_model": worst,
            "lomo_value_without_most_influential": geomean(v for mm, v in r.items() if mm != worst) if worst else None}


def stuck_chains(cell, draws_path: Path):
    if not (cell and cell.get("status") == "ok") or not draws_path.exists():
        return None
    z = np.load(draws_path)
    x, names = z["draws"], [str(n) for n in z["names"]]
    P = cell["parameters"]
    ref_m = np.array([P[n]["ref_mean"] for n in names])
    ref_sd = np.array([P[n]["ref_sd"] for n in names])
    dev = np.abs(x.mean(1) - ref_m) / ref_sd
    return int((np.nanmax(dev, axis=1) > A["stuck_chain"]["threshold_ref_sd"]).sum())


def main() -> None:
    data, where = load()
    stats = {}
    for name, (ours, theirs, key) in {
        "owalnuts_vs_nutpie_per_gradient": ("owalnuts", "nutpie", "min_bulk_ess_per_gradient"),
        "owalnuts_vs_nutpie_per_second": ("owalnuts", "nutpie", "min_bulk_ess_per_second"),
        "owalnuts_vs_cmdstan_per_gradient": ("owalnuts", "cmdstan", "min_bulk_ess_per_gradient"),
        "owalnuts_vs_cmdstan_per_second": ("owalnuts", "cmdstan", "min_bulk_ess_per_second"),
        "nutpie_vs_cmdstan_per_gradient": ("nutpie", "cmdstan", "min_bulk_ess_per_gradient"),
        "nutpie_vs_cmdstan_per_second": ("nutpie", "cmdstan", "min_bulk_ess_per_second"),
    }.items():
        stats[name] = evaluate(data, ours, theirs, key)
    gates = {a: sum(bool(data[m][a].get(s) and data[m][a][s].get("passed")) for m in MODELS for s in ALL) for a in ARMS}
    recorded = {a: sum(data[m][a].get(s) is not None for m in MODELS for s in ALL) for a in ARMS}
    statuses = {a: {} for a in ARMS}
    for a in ARMS:
        for m in MODELS:
            for s in ALL:
                c = data[m][a].get(s)
                st = c.get("status") if c else "missing"
                if st != "ok":
                    statuses[a].setdefault(st, []).append(f"{m}/{s}")
    per_model_gates = {m: {a: sum(bool(data[m][a].get(s) and data[m][a][s].get("passed")) for s in ALL) for a in ARMS} for m in MODELS}
    stuck = {m: {a: {str(s): stuck_chains(data[m][a].get(s), where[m][a][s] / "draws" / f"{short(m)}-{a}-{s}.npz") for s in ALL}
                 for a in ARMS} for m in MODELS}
    hmm = "bball_drive_event_0-hmm_drive_0"
    stuck_hmm = {a: {"per_seed": stuck[hmm][a], "cells_with_stuck": sum(1 for v in stuck[hmm][a].values() if v),
                     "counted": sum(1 for v in stuck[hmm][a].values() if v is not None)} for a in ARMS}
    stuck_tot = {m: {a: sum(1 for v in stuck[m][a].values() if v) for a in ARMS} for m in MODELS}
    # same-seed nutpie repeat against WP64's Linux nutpie cells (reported)
    repeat = {}
    for m in MODELS:
        for s in SEEDS["wp64_v7"]:
            p = WP64 / "v7" / "cells" / f"{short(m)}-nutpie-{s}.json"
            old, new = (json.loads(p.read_text(encoding="utf-8")) if p.exists() else None), data[m]["nutpie"].get(s)
            if old and new:
                same = (old.get("status") == new.get("status") == "ok" and old.get("gradients_total") == new.get("gradients_total")
                        and all(abs(old["parameters"][n]["mean"] - new["parameters"][n]["mean"]) <= 1e-12 * max(1.0, abs(old["parameters"][n]["mean"]))
                                for n in old.get("parameters", {})))
                repeat[f"{m}/{s}"] = {"identical": bool(same), "old_status": old.get("status"), "new_status": new.get("status"),
                                      "old_passed": old.get("passed"), "new_passed": new.get("passed")}
    pr = STUDY["predictions"]
    g, sec = stats["owalnuts_vs_nutpie_per_gradient"]["value"], stats["owalnuts_vs_nutpie_per_second"]["value"]
    preds = {
        "N1_per_gradient_c_vs_nutpie_in_[1.0,1.4]": {"value": g, "held": pr["N1"]["interval"][0] <= g <= pr["N1"]["interval"][1]},
        "N1b_per_gradient_c_vs_nutpie_in_[0.55,0.95]": {"value": g, "held": pr["N1b"]["interval"][0] <= g <= pr["N1b"]["interval"][1]},
        "N2_per_second_c_vs_nutpie_in_[1.2,1.8]": {"value": sec, "held": pr["N2"]["interval"][0] <= sec <= pr["N2"]["interval"][1]},
        "N3_nutpie_gates_below_owalnuts": {"value": {"nutpie": gates["nutpie"], "owalnuts": gates["owalnuts"]}, "held": gates["nutpie"] < gates["owalnuts"]},
    }
    summary = {"schema": "nutpie-18seed-v1-summary", "ledger_id": STUDY["ledger_id"], "statistics": stats, "gates": gates,
               "recorded": recorded, "non_ok": statuses, "per_model_gates": per_model_gates, "stuck_hmm_drive_0": stuck_hmm,
               "stuck_cells_per_model": stuck_tot, "nutpie_same_seed_repeat_vs_wp64": repeat, "predictions": preds,
               "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
               "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    OWN.mkdir(parents=True, exist_ok=True)
    (OWN / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    def f(x, fmt=".3f"):
        return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)

    L = ["# WP76 nutpie 18-seed — results", "", "Statistic (c), fixed 16, 18 Linux seeds; 95 % seed-bootstrap interval "
         f"({A['bootstrap']['resamples']} resamples). Per-second walls are pinned, co-tenanted (lane 1).", "",
         "| ratio | value | interval | models | most influential model (value without) |", "|---|---:|---|---:|---|"]
    for k, e in stats.items():
        L.append(f"| {k} | {f(e['value'])} | [{f(e['interval'][0])}, {f(e['interval'][1])}] | {e['models']} | "
                 f"{e['lomo_most_influential_model']} ({f(e['lomo_value_without_most_influential'])}) |")
    L += ["", "| arm | gates /288 | recorded | non-ok cells |", "|---|---:|---:|---|"]
    for a in ARMS:
        L.append(f"| {a} | {gates[a]} | {recorded[a]} | {', '.join(f'{k} {len(v)}' for k, v in statuses[a].items()) or '—'} |")
    L += ["", "| model | oWALNUTS | CmdStan | nutpie | per-grad (c) vs nutpie | per-sec (c) vs nutpie | stuck cells o/c/n |", "|---|---:|---:|---:|---:|---:|---|"]
    for m in MODELS:
        pg = per_model_gates[m]
        L.append(f"| {m} | {pg['owalnuts']}/18 | {pg['cmdstan']}/18 | {pg['nutpie']}/18 | "
                 f"{f(stats['owalnuts_vs_nutpie_per_gradient']['per_model'].get(m))} | {f(stats['owalnuts_vs_nutpie_per_second']['per_model'].get(m))} | "
                 f"{stuck_tot[m]['owalnuts']}/{stuck_tot[m]['cmdstan']}/{stuck_tot[m]['nutpie']} |")
    L += ["", "## hmm_drive_0 stuck chains per seed", "", "| seed | oWALNUTS | CmdStan | nutpie |", "|---|---:|---:|---:|"]
    for s in ALL:
        L.append(f"| {s} | {stuck_hmm['owalnuts']['per_seed'][str(s)]} | {stuck_hmm['cmdstan']['per_seed'][str(s)]} | {stuck_hmm['nutpie']['per_seed'][str(s)]} |")
    L.append(f"| cells with a stuck chain | {stuck_hmm['owalnuts']['cells_with_stuck']}/{stuck_hmm['owalnuts']['counted']} | "
             f"{stuck_hmm['cmdstan']['cells_with_stuck']}/{stuck_hmm['cmdstan']['counted']} | {stuck_hmm['nutpie']['cells_with_stuck']}/{stuck_hmm['nutpie']['counted']} |")
    L += ["", f"nutpie same-seed repeat vs WP64 (560561-560563): {sum(v['identical'] for v in repeat.values())}/{len(repeat)} identical; "
          f"pass agreement {sum(v['old_passed'] == v['new_passed'] for v in repeat.values())}/{len(repeat)}", "",
          "## Predictions", "", "| prediction | value | held |", "|---|---|---|"]
    for k, v in preds.items():
        L.append(f"| {k} | {v['value']} | {v['held']} |")
    (OWN / "results-table.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
