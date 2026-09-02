#!/usr/bin/env python3
"""Adaptation-parity ablation driver.

    python run_parity.py run                       # every model x config x seed (resumable)
    python run_parity.py run --configs base,all --models mesquite-logmesquite_logvash
    python run_parity.py analyze                   # artifacts/summary.json + results-table.md

Reuses the posteriordb benchmark v1 driver (reference draws, BridgeStan
constraining, ArviZ estimators, gates) so that the numbers are directly
comparable with the v1 CmdStan cells. Each cell writes
`artifacts/cells/<model>-<config>-<seed>.json`; raw draws stay in
`artifacts/draws/` (not committed).
"""
from __future__ import annotations

import json
import math
import statistics
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
V1 = Path(PROTOCOL["v1_study_dir"])
sys.path.insert(0, str(V1))
import run_posteriordb as v1  # noqa: E402

ART = HERE / "artifacts"
CELLS = ART / "cells"
DRAWS = ART / "draws"
HARNESS = Path(PROTOCOL["harness"])
MODELS = PROTOCOL["models"]
CONFIGS = PROTOCOL["configs"]
SEEDS = PROTOCOL["seeds"]
TIMEOUT = PROTOCOL["cell_timeout_seconds"]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def cell_path(model: str, config: str, seed: int) -> Path:
    return CELLS / f"{v1.short(model)}-{config}-{seed}.json"


def run_cell(model: str, config: str, seed: int, ref: dict) -> dict:
    import bridgestan as bs

    so = V1 / "models" / f"{v1.short(model)}_model.so"
    data = V1 / "models" / f"{v1.short(model)}.data.json"
    DRAWS.mkdir(parents=True, exist_ok=True)
    raw = DRAWS / f"{v1.short(model)}-{config}-{seed}.raw.json"
    if raw.exists():
        raw.unlink()
    cmd = [str(HARNESS), str(so), str(data), config, str(seed), str(raw), "4"]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return v1.failure(model, config, seed, "timeout", f"exceeded {TIMEOUT}s")
    if cp.returncode != 0 or not raw.exists():
        return v1.failure(model, config, seed, "error", cp.stderr.strip()[-2000:])
    out = json.loads(raw.read_text(encoding="utf-8"))
    if out.get("status") != "ok":
        return v1.failure(model, config, seed, "error", out.get("error", "unknown"), wall_seconds=out.get("wall_seconds"))
    bs.compile.windows_dll_path_setup()
    sm = bs.StanModel(str(so), data=data.read_text(encoding="utf-8"), seed=1)
    cnames = [v1.bridgestan_name(n) for n in sm.param_names(include_tp=True, include_gq=False)]
    unc = np.asarray([c["samples"] for c in out["chains_data"]], dtype=np.float64)
    con = np.empty(unc.shape[:2] + (len(cnames),))
    for c in range(unc.shape[0]):
        for d in range(unc.shape[1]):
            con[c, d] = sm.param_constrain(unc[c, d], include_tp=True, include_gq=False)
    index = {n: i for i, n in enumerate(cnames)}
    missing = [n for n in ref["names"] if n not in index]
    if missing:
        return v1.failure(model, config, seed, "error", f"reference parameters not produced: {missing[:5]}")
    draws = con[:, :, [index[n] for n in ref["names"]]]
    chains = out["chains_data"]
    grads_sampling = sum(c["retained_target_calls"] for c in chains)
    grads_total = out["target_calls_total"]
    n_ret = out["chains"] * out["retained"]
    depth_stops = sum(c["maximum_depth_stops"] for c in chains)
    extra = {
        "final_step_size": [c["final_step_size"] for c in chains],
        "invalid_stops": sum(c["invalid_stops"] for c in chains),
        "refinement_exhaustions": sum(c["refinement_exhaustions"] for c in chains),
        "recoverable_failures_total": out["recoverable_failures_total"],
        "warmup_divergences": sum(c["warmup_divergences"] for c in chains),
        "warmup_maximum_depth_stops": sum(c["warmup_maximum_depth_stops"] for c in chains),
        "depth_cap_rate": depth_stops / n_ret,
        "retained_depth_histogram": [sum(x) for x in zip(*(c["retained_depth_histogram"] for c in chains))],
        "retained_refinement_level_histogram": [sum(x) for x in zip(*(c["retained_refinement_level_histogram"] for c in chains))],
        "warmup_refinement_level_histogram": [sum(x) for x in zip(*(c["warmup_refinement_level_histogram"] for c in chains))],
        "step_searches": [c["step_searches"] for c in chains],
        "metric_updates": [c["metric_updates"] for c in chains],
        "rust_min_bulk_ess_unconstrained": out["rust_min_bulk_ess"],
        "rust_max_rhat_unconstrained": out["rust_max_rhat"],
        "rust_min_bulk_ess_per_gradient_unconstrained": out["rust_min_bulk_ess_per_gradient"],
        "tuning": out["tuning"],
        "warmup_config": out["warmup_config"],
        "algorithm_revision": out["algorithm_revision"],
        "unconstrained_dimension": out["dimension"],
    }
    cell = v1.metrics(model, config, seed, draws, ref["names"], ref, out["wall_seconds"], grads_total, grads_sampling,
                      sum(c["divergences"] for c in chains), depth_stops, extra)
    cell["schema"] = "adaptation-parity-v1-cell-metrics"
    return cell


def write_cell(cell: dict) -> None:
    CELLS.mkdir(parents=True, exist_ok=True)
    cell_path(cell["model"], cell["arm"], cell["seed"]).write_text(
        json.dumps(cell, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    s = cell["status"]
    if s == "ok":
        log(f"  {cell['arm']:>14} {cell['seed']}: wall {cell['wall_seconds']:.2f}s grads {cell['gradients_total']:>9} "
            f"minbulk {cell['min_bulk_ess']:.0f} ESS/grad*1e3 {1e3 * cell['min_bulk_ess_per_gradient']:.3f} "
            f"rhat {cell['max_rank_rhat']:.4f} div {cell['divergences']} capped {cell['depth_cap_rate']:.3f} "
            f"h {np.median(cell['final_step_size']):.4f} passed {cell['passed']}")
    else:
        log(f"  {cell['arm']:>14} {cell['seed']}: {s}: {cell.get('error', '')[:300]}")


def run_all(models: list[str], configs: list[str]) -> None:
    for model in models:
        log(f"== {model}")
        ref = None
        for config in configs:
            for seed in SEEDS:
                if cell_path(model, config, seed).exists():
                    continue
                if ref is None:
                    ref = v1.reference(model)
                try:
                    cell = run_cell(model, config, seed, ref)
                except Exception as e:  # noqa: BLE001
                    cell = v1.failure(model, config, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
                write_cell(cell)


def geomean(xs: list[float]) -> float:
    xs = [x for x in xs if x and math.isfinite(x) and x > 0]
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs))) if xs else float("nan")


def fmt(x, digits=3):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:,.{digits}f}"


def analyze() -> None:
    cells: dict = {}
    for path in sorted(CELLS.glob("*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        c.pop("parameters", None)
        cells.setdefault(c["model"], {}).setdefault(c["arm"], {})[str(c["seed"])] = c
    cmdstan = PROTOCOL["cmdstan_reference_min_bulk_ess_per_gradient_x1e3"]
    v1da = PROTOCOL["v1_owalnuts_da_min_bulk_ess_per_gradient_x1e3"]
    summary = {"per_model": {}, "per_config": {}}
    lines = ["# Adaptation parity v1 — results", "",
             "Seed medians over the preregistered seeds of the per-cell minimum over reference parameters "
             "(ArviZ bulk ESS on constrained coordinates, as in posteriordb benchmark v1). "
             "`x1e3` columns are min bulk ESS per gradient x 1000; `cap` = retained transitions stopped at the depth cap "
             "(fraction); `h` = median final step over chains; `lvl>0` = fraction of retained transitions whose selected "
             "refinement level exceeds zero; `gates` = cells passing R-hat <= 1.01, bulk/tail ESS >= 400, no divergences.",
             ""]
    # Per config summary rows
    lines.append("## Per configuration (geometric means over models with all cells ok)")
    lines.append("")
    lines.append("| config | models ok | geomean ESS/grad vs base | geomean ESS/grad vs cmdstan | worst model vs base | models < 0.9x base | gates |")
    lines.append("|---|---:|---:|---:|---|---:|---:|")
    per_config_rows = []
    for config in CONFIGS:
        ratios_base, ratios_cmd, worst, losers, gates, ok_models = [], [], None, [], 0, 0
        for model in MODELS:
            mine = cells.get(model, {}).get(config, {})
            base = cells.get(model, {}).get("base", {})
            ok = [c for c in mine.values() if c.get("status") == "ok"]
            ok_base = [c for c in base.values() if c.get("status") == "ok"]
            gates += sum(1 for c in ok if c["passed"])
            if len(ok) == len(SEEDS):
                ok_models += 1
                med = statistics.median(c["min_bulk_ess_per_gradient"] for c in ok) * 1e3
                ratios_cmd.append(med / cmdstan[model])
                if len(ok_base) == len(SEEDS):
                    medb = statistics.median(c["min_bulk_ess_per_gradient"] for c in ok_base) * 1e3
                    r = med / medb
                    ratios_base.append(r)
                    if worst is None or r < worst[1]:
                        worst = (model, r)
                    if r < 0.9:
                        losers.append(model)
        row = {"config": config, "models_ok": ok_models, "geomean_vs_base": geomean(ratios_base),
               "geomean_vs_cmdstan": geomean(ratios_cmd), "worst_vs_base": worst, "losers_vs_base": losers,
               "gates_passed": gates}
        summary["per_config"][config] = row
        per_config_rows.append(row)
        w = f"{worst[0]} ({worst[1]:.2f}x)" if worst else "—"
        lines.append(f"| {config} | {ok_models}/{len(MODELS)} | {fmt(row['geomean_vs_base'])} | {fmt(row['geomean_vs_cmdstan'])} | {w} | {len(losers)} | {gates}/{len(MODELS) * len(SEEDS)} |")
    lines.append("")
    lines.append("## Per model")
    lines.append("")
    lines.append("| model | config | gates | grads | min bulk ESS | ESS/grad x1e3 | vs base | vs cmdstan | cmdstan x1e3 | v1 da x1e3 | max R-hat | div | cap | h | lvl>0 |")
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|")
    for model in MODELS:
        summary["per_model"][model] = {}
        base = cells.get(model, {}).get("base", {})
        ok_base = [c for c in base.values() if c.get("status") == "ok"]
        medb = statistics.median(c["min_bulk_ess_per_gradient"] for c in ok_base) * 1e3 if ok_base else None
        for config in CONFIGS:
            mine = cells.get(model, {}).get(config, {})
            ok = [c for c in mine.values() if c.get("status") == "ok"]
            if not mine:
                continue
            if not ok:
                errs = "; ".join(str(c.get("error", ""))[:80] for c in mine.values())
                lines.append(f"| {model} | {config} | error x{len(mine)} | — | — | — | — | — | {cmdstan[model]} | {v1da[model]} | — | | — | — | — | {errs} |")
                summary["per_model"][model][config] = {"status": "error", "errors": errs}
                continue
            med = statistics.median(c["min_bulk_ess_per_gradient"] for c in ok) * 1e3
            lvl = [c["retained_refinement_level_histogram"] for c in ok]
            lvl_gt0 = statistics.median(sum(h[1:]) / max(1, sum(h)) for h in lvl)
            entry = {
                "n_ok": len(ok), "n_passed": sum(1 for c in ok if c["passed"]),
                "gradients_total": statistics.median(c["gradients_total"] for c in ok),
                "min_bulk_ess": statistics.median(c["min_bulk_ess"] for c in ok),
                "min_tail_ess": statistics.median(c["min_tail_ess"] for c in ok),
                "min_bulk_ess_per_gradient_x1e3": med,
                "vs_base": med / medb if medb else None,
                "vs_cmdstan": med / cmdstan[model],
                "max_rank_rhat": statistics.median(c["max_rank_rhat"] for c in ok),
                "divergences": [c["divergences"] for c in ok],
                "depth_cap_rate": statistics.median(c["depth_cap_rate"] for c in ok),
                "final_step_size": statistics.median(float(np.median(c["final_step_size"])) for c in ok),
                "retained_level_gt0_fraction": lvl_gt0,
                "retained_refinement_level_histogram": [sum(x) for x in zip(*lvl)],
                "warmup_refinement_level_histogram": [sum(x) for x in zip(*(c["warmup_refinement_level_histogram"] for c in ok))],
                "wall_seconds": statistics.median(c["wall_seconds"] for c in ok),
                "max_abs_z": statistics.median(c["max_abs_z"] for c in ok),
            }
            summary["per_model"][model][config] = entry
            lines.append(
                f"| {model} | {config} | {entry['n_passed']}/{len(mine)} | {entry['gradients_total']:,.0f} | {entry['min_bulk_ess']:,.0f} | "
                f"{med:.3f} | {fmt(entry['vs_base'], 2)} | {entry['vs_cmdstan']:.2f} | {cmdstan[model]} | {v1da[model]} | "
                f"{entry['max_rank_rhat']:.4f} | {','.join(str(d) for d in entry['divergences'])} | {entry['depth_cap_rate']:.3f} | "
                f"{entry['final_step_size']:.4f} | {lvl_gt0:.3f} |")
    lines.append("")
    lines.append("## Refinement-level histograms (retained transitions, summed over seeds and chains)")
    lines.append("")
    lines.append("| model | config | level 0 | 1 | 2 | 3 | 4 | warmup level 0 | 1 | 2 | 3 | 4 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for model in MODELS:
        for config in CONFIGS:
            e = summary["per_model"][model].get(config)
            if not e or "retained_refinement_level_histogram" not in e:
                continue
            r = e["retained_refinement_level_histogram"]
            w = e["warmup_refinement_level_histogram"]
            lines.append(f"| {model} | {config} | " + " | ".join(f"{x:,}" for x in r) + " | " + " | ".join(f"{x:,}" for x in w) + " |")
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    (ART / "results-table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:len(CONFIGS) + 8]))


def main(argv: list[str]) -> None:
    if not argv:
        raise SystemExit(__doc__)
    if argv[0] == "run":
        models, configs = MODELS, CONFIGS
        i = 1
        while i < len(argv):
            if argv[i] == "--models":
                models = argv[i + 1].split(",")
                i += 2
            elif argv[i] == "--configs":
                configs = argv[i + 1].split(",")
                i += 2
            else:
                raise SystemExit(f"unknown argument {argv[i]}")
        run_all(models, configs)
    elif argv[0] == "analyze":
        analyze()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
