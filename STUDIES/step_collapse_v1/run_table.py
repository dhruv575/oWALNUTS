"""Run the preregistered remedy table (resumable) and the CmdStan reference.

    python run_table.py run [--arms a,b] [--models m,n] [--seeds s,t]
    python run_table.py analyze      -> artifacts/results-table.md, artifacts/summary.json
"""
from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXE = HERE.parent.parent / "target" / "release" / "step-collapse-v1.exe"
PY = HERE / ".venv" / "Scripts" / "python.exe"
TABLE = HERE / "artifacts" / "table"
CMD = HERE / "artifacts" / "cmdstan"
MODELS = ["sblrc__blr", "earnings__logearn_interaction", "diamonds__diamonds", "arma__arma11",
          "kidiq__kidscore_momhsiq", "mesquite__logmesquite_logvash", "nes2000__nes"]
SHORT = {"sblrc__blr": "sblrc", "earnings__logearn_interaction": "earnings", "diamonds__diamonds": "diamonds",
         "arma__arma11": "arma11", "kidiq__kidscore_momhsiq": "kidiq", "mesquite__logmesquite_logvash": "mesquite",
         "nes2000__nes": "nes2000"}
ARMS = ["baseline", "reg", "reg+ramp", "reg+research", "mean-accept", "ramp", "research",
        "research+floor-rel:0.5", "shrink:10", "stan-style"]
SEEDS = [80101, 80102]
COLLAPSING = ["sblrc", "earnings", "diamonds"]
CONTROLS = ["kidiq", "mesquite", "nes2000"]


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def cell_path(model, arm, seed):
    return TABLE / f"{model}-{arm}-{seed}.json"


def run(arms, models, seeds):
    TABLE.mkdir(parents=True, exist_ok=True)
    for model in models:
        for seed in seeds:
            for arm in arms:
                out = cell_path(model, arm, seed)
                if out.exists():
                    continue
                t = time.perf_counter()
                r = subprocess.run([str(EXE), str(HERE / "models" / f"{model}_model.so"),
                                    str(HERE / "models" / f"{model}.data.json"), str(seed), arm, str(out)],
                                   capture_output=True, text=True)
                if r.returncode != 0:
                    out.write_text(json.dumps({"schema": "step-collapse-v1-cell", "model": model, "variant": arm,
                                               "seed": seed, "status": "error", "error": r.stderr[-2000:]}))
                    log(f"{model} {arm} {seed}: ERROR {r.stderr.strip()[-300:]}")
                else:
                    log(f"{model} {arm} {seed}: {r.stderr.strip().splitlines()[-1][:200]} ({time.perf_counter() - t:.0f}s)")
            cm = CMD / f"{model}-{seed}.json"
            if not cm.exists() and cell_path(model, "baseline", seed).exists():
                r = subprocess.run([str(PY), str(HERE / "cmdstan_trace.py"), str(cell_path(model, "baseline", seed))],
                                   capture_output=True, text=True, env={**__import__("os").environ, "MAKE": "mingw32-make",
                                                                        "PYTHONIOENCODING": "utf-8"})
                log(f"cmdstan {model} {seed}: {(r.stdout.strip().splitlines() or [r.stderr[-300:]])[-1][:200]}")


def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def gates(c):
    if c is None or c.get("status") == "error":
        return False
    divs = sum(ch.get("retained_divergences", 0) for ch in c.get("chains_data", [])) if "chains_data" in c else c.get("retained_divergences", 0)
    return c["max_rhat"] <= 1.01 and c["min_bulk_ess"] >= 400 and c["min_tail_ess"] >= 400 and divs == 0


def frozen(c):
    """Chains with fewer than 500 of 1000 retained transitions moving the position."""
    return sum(1 for ch in c.get("chains_data", []) if ch["retained_moved"] < 500)


def fmt_h(hs):
    return "/".join(f"{h:.2g}" for h in hs)


def analyze():
    rows = {}
    summary = {"schema": "step-collapse-v1-summary", "cells": {}, "per_model": {}}
    for model in MODELS:
        short = SHORT[model]
        for arm in ARMS + ["cmdstan"]:
            per_seed = []
            for seed in SEEDS:
                c = load(cell_path(model, arm, seed)) if arm != "cmdstan" else load(CMD / f"{model}-{seed}.json")
                if c is None or c.get("status") == "error":
                    per_seed.append(None)
                    continue
                if arm == "cmdstan":
                    entry = {"epg": c["min_bulk_ess_per_gradient"], "ess": c["min_bulk_ess"], "tail": c["min_tail_ess"],
                             "rhat": c["max_rhat"], "gates": c["max_rhat"] <= 1.01 and c["min_bulk_ess"] >= 400 and c["min_tail_ess"] >= 400 and c["retained_divergences"] == 0,
                             "h": c["final_step_size"], "caps": c["retained_depth_caps"] / 4000, "grads": c["gradients_total"],
                             "frozen": 0}
                else:
                    entry = {"epg": c["min_bulk_ess_per_gradient"], "ess": c["min_bulk_ess"], "tail": c["min_tail_ess"],
                             "rhat": c["max_rhat"], "gates": gates(c),
                             "h": [ch["final_step_size"] for ch in c["chains_data"]],
                             "caps": sum(ch["retained_depth_caps"] for ch in c["chains_data"]) / 4000,
                             "grads": c["gradients_total"], "frozen": frozen(c),
                             "divs": sum(ch["retained_divergences"] for ch in c["chains_data"])}
                per_seed.append(entry)
                summary["cells"][f"{short}-{arm}-{seed}"] = entry
            ok = [e for e in per_seed if e]
            med = statistics.median([e["epg"] for e in ok]) if ok else float("nan")
            rows[(short, arm)] = {"per_seed": per_seed, "median_epg": med, "gates": sum(1 for e in ok if e["gates"]),
                                  "frozen": sum(e["frozen"] for e in ok)}
            summary["per_model"][f"{short}-{arm}"] = {"median_epg": med, "gates": rows[(short, arm)]["gates"],
                                                       "seed_epg": [e["epg"] if e else None for e in per_seed]}
    lines = ["# step_collapse_v1 — remedy table", "",
             "Seed median (80101, 80102) of the minimum bulk ESS per gradient x1e3 (warmup + sampling; "
             "min over unconstrained coordinates, ArviZ over constrained parameters for CmdStan), then `x baseline` "
             "and `x cmdstan`; `gates` = seeds passing / 2; `frozen` = chains with < 500 moving retained transitions; "
             "`h` = per-chain final step (seed 80101) and `caps` = retained depth-cap rate over the 4 chains (seed 80101).", ""]
    lines.append("| model | arm | ESS/grad x1e3 | x baseline | x cmdstan | gates | frozen | h (80101) | caps (80101) |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---|---:|")
    geo = {arm: [] for arm in ARMS}
    geo_controls = {arm: [] for arm in ARMS}
    for model in MODELS:
        short = SHORT[model]
        base = rows[(short, "baseline")]["median_epg"]
        cmd = rows[(short, "cmdstan")]["median_epg"]
        for arm in ARMS + ["cmdstan"]:
            r = rows[(short, arm)]
            e0 = r["per_seed"][0]
            h = (fmt_h(e0["h"]) if e0 else "—")
            caps = (f"{e0['caps']:.3f}" if e0 else "—")
            xb = r["median_epg"] / base if base == base and base > 0 else float("nan")
            xc = r["median_epg"] / cmd if cmd == cmd and cmd > 0 else float("nan")
            if arm in ARMS and xb == xb:
                geo[arm].append(xb)
                if short in CONTROLS:
                    geo_controls[arm].append(xb)
            lines.append(f"| {short} | {arm} | {1e3 * r['median_epg']:.3f} | {xb:.2f} | {xc:.2f} | {r['gates']}/2 | {r['frozen']} | {h} | {caps} |")
    lines += ["", "## Geometric means of `x baseline` (seed medians)", "", "| arm | all 7 models | 3 controls | collapsing (sblrc, earnings, diamonds) |", "|---|---:|---:|---:|"]
    import math

    def gm(v):
        v = [x for x in v if x == x and x > 0]
        return math.exp(sum(map(math.log, v)) / len(v)) if v else float("nan")

    for arm in ARMS:
        coll = [rows[(m, arm)]["median_epg"] / rows[(m, "baseline")]["median_epg"] for m in COLLAPSING]
        lines.append(f"| {arm} | {gm(geo[arm]):.3f} | {gm(geo_controls[arm]):.3f} | {gm(coll):.3f} |")
        summary["per_model"][f"geomean-{arm}"] = {"all": gm(geo[arm]), "controls": gm(geo_controls[arm]), "collapsing": gm(coll)}
    lines += ["", "## Per-seed detail", "", "| model | arm | seed | ESS/grad x1e3 | min bulk | min tail | max R-hat | divs | frozen | h | caps |", "|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|"]
    for model in MODELS:
        short = SHORT[model]
        for arm in ARMS + ["cmdstan"]:
            for seed, e in zip(SEEDS, rows[(short, arm)]["per_seed"]):
                if e is None:
                    lines.append(f"| {short} | {arm} | {seed} | error | | | | | | | |")
                    continue
                lines.append(f"| {short} | {arm} | {seed} | {1e3 * e['epg']:.3f} | {e['ess']:.0f} | {e['tail']:.0f} | {e['rhat']:.3f} | {e.get('divs', 0)} | {e['frozen']} | {fmt_h(e['h'])} | {e['caps']:.3f} |")
    (HERE / "artifacts" / "results-table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (HERE / "artifacts" / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print("\n".join(lines[:60]))


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "analyze":
        analyze()
    else:
        arms, models, seeds = ARMS, MODELS, SEEDS
        for a in args[1:]:
            if a.startswith("--arms"):
                arms = a.split("=", 1)[1].split(",")
            if a.startswith("--models"):
                models = a.split("=", 1)[1].split(",")
            if a.startswith("--seeds"):
                seeds = [int(s) for s in a.split("=", 1)[1].split(",")]
        run(arms, models, seeds)
        log("TABLE_DONE")
