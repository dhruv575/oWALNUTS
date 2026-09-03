"""Run and analyse the kernel-gap table.

    python run_table.py run [arm ...]      # every model x arm x seed cell, resumable
    python run_table.py analyze            # artifacts/summary.json, artifacts/results-table.md

Cells: `artifacts/telemetry/<model>-<arm>-<seed>.json` (per-transition
traces; regenerable, not committed) and `artifacts/cells/` (the same with
the traces replaced by their summaries; committed).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from statistics import median

import numpy as np

HERE = Path(__file__).resolve().parent
BIN = HERE.parent.parent / "target" / "release" / "kernel-gap-v1.exe"
MODELS = ["earnings__logearn_interaction", "kidiq__kidscore_momhsiq", "mesquite__logmesquite_logvash",
          "nes2000__nes", "garch__garch11", "arK__arK"]
ARMS = ["nuts-ref", "walnuts", "walnuts+cross", "walnuts+rhosum", "walnuts+delta1000",
        "walnuts+levels1", "walnuts+levels1+rhosum", "walnuts+accept"]
SEEDS = [84201, 84202]
DRAWS = 2000


def cell_path(model: str, arm: str, seed: int) -> Path:
    return HERE / "artifacts" / "telemetry" / f"{model}-{arm}-{seed}.json"


def summarise_trace(chains_data: list[dict]) -> dict:
    """Orbit statistics pooled over the chains of one cell."""
    keys = ["gradients", "leaves", "depth", "orbit_states", "selected_index", "initial_index"]
    pooled = {k: np.concatenate([np.asarray(c["trace"][k], dtype=float) for c in chains_data]) for k in keys}
    stops = np.concatenate([np.asarray(c["trace"]["stop"]) for c in chains_data])
    n = stops.size
    states = pooled["orbit_states"]
    span = np.maximum(states - 1.0, 1.0)
    displacement = np.abs(pooled["selected_index"] - pooled["initial_index"])
    out = {
        "transitions": int(n),
        "mean_depth": float(pooled["depth"].mean()),
        "mean_leaves": float(pooled["leaves"].mean()),
        "mean_orbit_states": float(states.mean()),
        "stops": {s: float((stops == s).mean()) for s in sorted(set(stops.tolist()))},
        "selected_equals_initial": float((displacement == 0).mean()),
        "mean_relative_displacement": float((displacement / span).mean()),
        "mean_relative_position": float((pooled["selected_index"] / span).mean()),
        "mean_initial_relative_position": float((pooled["initial_index"] / span).mean()),
        "displacement_quantiles": {q: float(np.quantile(displacement / span, q / 100)) for q in (10, 25, 50, 75, 90)},
    }
    if "selected_level" in chains_data[0]["trace"]:
        levels = np.concatenate([np.asarray([(-1 if v is None else v) for v in c["trace"]["selected_level"]]) for c in chains_data])
        out["orbits_with_refined_leaf"] = float((levels > 0).mean())
        out["orbits_with_no_leaf"] = float((levels < 0).mean())
    totals = [c["totals"] for c in chains_data]
    tot = lambda k: sum(t.get(k, 0) for t in totals)
    hist = [0] * max(len(t["refinement_level_built"]) for t in totals)
    for t in totals:
        for i, v in enumerate(t["refinement_level_built"]):
            hist[i] += v
    calls = tot("target_calls_total")
    out["refinement_level_built"] = hist
    out["gradients_per_orbit"] = calls / n
    out["gradients_per_orbit_initial"] = tot("target_calls_initial") / n
    out["gradients_per_orbit_rejected_attempts"] = (tot("forward_micro_steps_executed") - tot("accepted_forward_micro_steps")) / n if "forward_micro_steps_executed" in totals[0] else 0.0
    out["gradients_per_orbit_reverse"] = tot("target_calls_reverse") / n
    out["gradients_per_orbit_leaf"] = tot("accepted_forward_micro_steps") / n
    out["gradients_per_leaf"] = calls / max(tot("leaves_built"), 1)
    out["leaves_per_orbit"] = tot("leaves_built") / n
    out["leaf_fraction_refined"] = (sum(hist[1:]) / max(sum(hist), 1)) if len(hist) > 1 else 0.0
    out["divergences"] = tot("divergences")
    out["depth_caps"] = tot("maximum_depth_stops")
    return out


def run(arms: list[str]) -> None:
    log = HERE / "artifacts" / "table-run.log"
    for seed in SEEDS:
        for model in MODELS:
            for arm in arms:
                out = cell_path(model, arm, seed)
                if out.exists():
                    continue
                cmd = [str(BIN), str(HERE / "models" / f"{model}_model.so"), str(HERE / "models" / f"{model}.data.json"),
                       str(HERE / "artifacts" / "cmdstan" / f"{model}.json"), str(seed), arm, str(out), str(DRAWS)]
                t = time.perf_counter()
                proc = subprocess.run(cmd, capture_output=True, text=True)
                line = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else proc.stdout.strip()
                msg = f"{model} {arm} {seed}: {line} ({time.perf_counter() - t:.0f}s)"
                print(msg, flush=True)
                with log.open("a", encoding="utf-8") as f:
                    f.write(msg + "\n")
                if proc.returncode != 0:
                    print(proc.stderr, flush=True)
                    continue
                strip_cell(out)


def strip_cell(path: Path) -> None:
    cell = json.loads(path.read_text(encoding="utf-8"))
    cell["orbit"] = summarise_trace(cell["chains_data"])
    cell["chains_data"] = [{"totals": c["totals"]} for c in cell["chains_data"]]
    dest = HERE / "artifacts" / "cells" / path.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(cell, indent=1), encoding="utf-8")


def load_cells() -> dict:
    cells = {}
    for p in sorted((HERE / "artifacts" / "cells").glob("*.json")):
        c = json.loads(p.read_text(encoding="utf-8"))
        cells[(c["model"].replace("_model", ""), c["arm"], int(c["seed"]))] = c
    return cells


def fmt(x, digits=3):
    return "—" if x is None else f"{x:.{digits}f}"


def analyze() -> None:
    cells = load_cells()
    arms = [a for a in ARMS if any(k[1] == a for k in cells)]
    extra = sorted({k[1] for k in cells} - set(arms))
    arms += extra
    summary = {}
    lines = ["# kernel_gap_v1 — results", "",
             "Seed medians over seeds " + ", ".join(map(str, SEEDS)) +
             f"; 4 chains x {DRAWS} draws at CmdStan's adapted step, inverse metric and post-warmup starts per chain. "
             "ESS = minimum over unconstrained coordinates of bulk ESS. `x ref` = ratio to `nuts-ref` on the same seed, seed median.", ""]
    hdr = "| model | arm | ESS/grad x1e3 | x ref | ESS/orbit | x ref | leaves/orbit | x ref | grads/leaf | x ref | depth | stop causes | sel=init | rel. displacement | refined leaves | non-leaf grads/orbit (init / rejected / reverse) |"
    lines += [hdr, "|" + "---|" * (hdr.count("|") - 1)]
    cmd_lines = ["", "## CmdStan's own sampling run (the source of step, metric and starts; 4 x 1,000 retained, constrained-parameter ESS)", "",
                 "| model | h (per chain) | leapfrogs/orbit | depth | min bulk ESS | ESS/orbit | ESS/grad x1e3 |", "|---|---|---:|---:|---:|---:|---:|"]
    for model in MODELS:
        ref_stats = json.loads((HERE / "artifacts" / "cmdstan" / f"{model}.json").read_text(encoding="utf-8"))
        s = ref_stats["sampling"]
        steps = ", ".join("%.4f" % c["step_size"] for c in ref_stats["chains"])
        cmd_lines.append(f"| {model} | {steps} | {s['leapfrogs_per_orbit']:.1f} | {s['mean_treedepth']:.2f} | {s['min_bulk_ess']:.0f} | {s['min_bulk_ess_per_orbit']:.3f} | {1e3 * s['min_bulk_ess_per_gradient']:.3f} |")
        summary[model] = {}
        for arm in arms:
            per_seed = []
            for seed in SEEDS:
                c = cells.get((model, arm, seed))
                r = cells.get((model, "nuts-ref", seed))
                if c is None:
                    continue
                o = c["orbit"]
                row = {
                    "seed": seed,
                    "ess_per_gradient": c["min_bulk_ess_per_gradient"],
                    "ess_per_orbit": c["min_bulk_ess_per_orbit"],
                    "mean_ess_per_orbit": c["mean_bulk_ess"] / o["transitions"],
                    "leaves_per_orbit": o["leaves_per_orbit"],
                    "gradients_per_leaf": o["gradients_per_leaf"],
                    "gradients_per_orbit": o["gradients_per_orbit"],
                    "depth": o["mean_depth"],
                    "stops": o["stops"],
                    "selected_equals_initial": o["selected_equals_initial"],
                    "relative_displacement": o["mean_relative_displacement"],
                    "leaf_fraction_refined": o["leaf_fraction_refined"],
                    "non_leaf": [o["gradients_per_orbit_initial"], o["gradients_per_orbit_rejected_attempts"], o["gradients_per_orbit_reverse"]],
                    "max_rhat": c["max_rhat"],
                    "divergences": o["divergences"], "depth_caps": o["depth_caps"],
                }
                if r is not None:
                    ro = r["orbit"]
                    row["ratio"] = {
                        "ess_per_gradient": c["min_bulk_ess_per_gradient"] / r["min_bulk_ess_per_gradient"],
                        "ess_per_orbit": c["min_bulk_ess_per_orbit"] / r["min_bulk_ess_per_orbit"],
                        "leaves_per_orbit": o["leaves_per_orbit"] / ro["leaves_per_orbit"],
                        "gradients_per_leaf": o["gradients_per_leaf"] / ro["gradients_per_leaf"],
                    }
                per_seed.append(row)
            if not per_seed:
                continue
            med = lambda f: median(f(x) for x in per_seed)
            ratio = (lambda k: med(lambda x: x["ratio"][k])) if all("ratio" in x for x in per_seed) else (lambda k: None)
            stops = {}
            for x in per_seed:
                for k, v in x["stops"].items():
                    stops.setdefault(k, []).append(v)
            stops = {k: median(v) for k, v in stops.items()}
            stop_text = ", ".join(f"{k} {100 * v:.0f}%" for k, v in sorted(stops.items(), key=lambda kv: -kv[1]))
            entry = {
                "per_seed": per_seed,
                "ess_per_gradient": med(lambda x: x["ess_per_gradient"]),
                "ess_per_orbit": med(lambda x: x["ess_per_orbit"]),
                "leaves_per_orbit": med(lambda x: x["leaves_per_orbit"]),
                "gradients_per_leaf": med(lambda x: x["gradients_per_leaf"]),
                "ratio": {k: ratio(k) for k in ["ess_per_gradient", "ess_per_orbit", "leaves_per_orbit", "gradients_per_leaf"]},
                "stops": stops,
            }
            summary[model][arm] = entry
            lines.append(
                f"| {model} | {arm} | {1e3 * entry['ess_per_gradient']:.3f} | {fmt(entry['ratio']['ess_per_gradient'], 2)} | "
                f"{entry['ess_per_orbit']:.3f} | {fmt(entry['ratio']['ess_per_orbit'], 2)} | {entry['leaves_per_orbit']:.1f} | {fmt(entry['ratio']['leaves_per_orbit'], 2)} | "
                f"{entry['gradients_per_leaf']:.3f} | {fmt(entry['ratio']['gradients_per_leaf'], 2)} | {med(lambda x: x['depth']):.2f} | {stop_text} | "
                f"{med(lambda x: x['selected_equals_initial']):.3f} | {med(lambda x: x['relative_displacement']):.3f} | "
                f"{100 * med(lambda x: x['leaf_fraction_refined']):.1f}% | "
                f"{med(lambda x: x['non_leaf'][0]):.2f} / {med(lambda x: x['non_leaf'][1]):.2f} / {med(lambda x: x['non_leaf'][2]):.2f} |")
    lines += cmd_lines
    # geometric means over models per arm
    lines += ["", "## Geometric mean over the six models of the seed-median ratios to `nuts-ref`", "",
              "| arm | ESS/grad | ESS/orbit | leaves/orbit | grads/leaf | orbits/grad |", "|---|---:|---:|---:|---:|---:|"]
    geo = {}
    for arm in arms:
        if arm == "nuts-ref":
            continue
        vals = {k: [] for k in ["ess_per_gradient", "ess_per_orbit", "leaves_per_orbit", "gradients_per_leaf"]}
        for model in MODELS:
            e = summary.get(model, {}).get(arm)
            if e is None or e["ratio"]["ess_per_gradient"] is None:
                continue
            for k in vals:
                vals[k].append(e["ratio"][k])
        if not vals["ess_per_gradient"]:
            continue
        g = {k: float(np.exp(np.mean(np.log(v)))) for k, v in vals.items()}
        g["orbits_per_gradient"] = 1.0 / (g["leaves_per_orbit"] * g["gradients_per_leaf"])
        g["models"] = len(vals["ess_per_gradient"])
        geo[arm] = g
        lines.append(f"| {arm} | {g['ess_per_gradient']:.3f} | {g['ess_per_orbit']:.3f} | {g['leaves_per_orbit']:.3f} | {g['gradients_per_leaf']:.3f} | {g['orbits_per_gradient']:.3f} |")
    (HERE / "artifacts" / "summary.json").write_text(json.dumps({"models": summary, "geomean": geo}, indent=1), encoding="utf-8")
    (HERE / "artifacts" / "results-table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(sys.argv[2:] or ARMS)
    elif sys.argv[1] == "analyze":
        analyze()
    elif sys.argv[1] == "strip":
        for p in sorted((HERE / "artifacts" / "telemetry").glob("*.json")):
            strip_cell(p)
    else:
        raise SystemExit(__doc__)
