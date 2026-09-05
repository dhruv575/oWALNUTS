#!/usr/bin/env python3
"""Reverse-coarser policy study driver (WP39): the posteriordb v5 protocol restricted to the two
oWALNUTS arms `stop` (the shipped `ReverseCoarserPolicy::StopOrbit`) and `beyond`
(`ReverseCoarserPolicy::ZeroWeightBeyond`), CmdStan cited from v5.

    python run_study.py run                        # every model/arm/seed in protocol order (resumable)
    python run_study.py run --models=a,b --arms=stop
    python run_study.py cell <model> <arm>          # one model/arm, all seeds (child process)
    python run_study.py checks                     # funnel tail mass at the defaults, both arms, three seeds
    python run_study.py analyze                    # artifacts/summary.json + results-table.md

The BridgeStan libraries and the posteriordb checkout are the ones compiled for
`posteriordb_bench_v6` (protocol `external`); nothing is compiled here. Each cell writes
`artifacts/cells/<model>-<arm>-<seed>.json` (metrics, no draws) and
`artifacts/draws/<model>-<arm>-<seed>.npz` (constrained draws on the reference parameter set).
Failures are recorded as cells with status != "ok".
"""
from __future__ import annotations

import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
ART = HERE / "artifacts"
CELLS = ART / "cells"
DRAWS = ART / "draws"
EXTERNAL = (HERE / PROTOCOL["external"]["root"]).resolve()
MODELS = EXTERNAL / "models"
PDB_PATH = EXTERNAL / PROTOCOL["posteriordb"]["path"]
HARNESS = HERE / "target" / "release" / "posteriordb-cell.exe"
FUNNEL = HERE / "target" / "release" / "funnel.exe"
ARMS = PROTOCOL["arms_order"]
BASELINE = "stop"
CANDIDATE = "beyond"
V5 = HERE.parent / "posteriordb_bench_v5" / "artifacts"
SEEDS = PROTOCOL["seeds"]
TIMEOUT = PROTOCOL["cell_timeout_seconds"]
TARGET_MODELS = PROTOCOL["target_models"]


def short(model: str) -> str:
    return model.replace("-", "__")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------- posteriordb


def posterior(model: str):
    from posteriordb import PosteriorDatabase

    return PosteriorDatabase(str(PDB_PATH)).posterior(model)


def bridgestan_name(name: str) -> str:
    """'theta.1.2' -> 'theta[1,2]'."""
    parts = name.split(".")
    if len(parts) == 1 or not all(p.isdigit() for p in parts[1:]):
        return name
    return f"{parts[0]}[{','.join(parts[1:])}]"


def reference(model: str) -> dict:
    p = posterior(model)
    ref = p.reference_draws()
    names = list(ref[0].keys())
    arr = np.asarray([[c[n] for n in names] for c in ref], dtype=np.float64)
    arr = np.transpose(arr, (0, 2, 1))
    return {"names": names, "draws": arr, **arviz_stats(arr)}


def arviz_stats(arr: np.ndarray) -> dict:
    import arviz as az

    ds = az.convert_to_dataset({"p": arr})
    bulk = np.asarray(az.ess(ds, method="bulk").p.values, dtype=float)
    tail = np.asarray(az.ess(ds, method="tail", prob=(0.05, 0.95)).p.values, dtype=float)
    rhat = np.asarray(az.rhat(ds, method="rank").p.values, dtype=float)
    mcse = np.asarray(az.mcse(ds, method="mean").p.values, dtype=float)
    return {
        "mean": arr.reshape(-1, arr.shape[-1]).mean(0),
        "sd": arr.reshape(-1, arr.shape[-1]).std(0, ddof=1),
        "bulk_ess": bulk, "tail_ess": tail, "rhat": rhat, "mcse": mcse,
    }


def model_files(model: str) -> tuple[Path, Path]:
    so = MODELS / f"{short(model)}_model.so"
    data = MODELS / f"{short(model)}.data.json"
    if not so.exists() or not data.exists():
        raise FileNotFoundError(f"missing {so} or {data}")
    return so, data


# --------------------------------------------------------------------------- v5 CmdStan reference


def v5_cmdstan() -> dict:
    """Per model: seed-median CmdStan min bulk ESS per gradient (and per second) from the v5 cells."""
    out: dict = {}
    for path in sorted((V5 / "cells").glob("*-cmdstan-*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        if c.get("status") != "ok":
            continue
        out.setdefault(c["model"], []).append(c)
    return {m: {"min_bulk_ess_per_gradient": med([c["min_bulk_ess_per_gradient"] for c in cs]),
                "min_bulk_ess_per_second": med([c["min_bulk_ess_per_second"] for c in cs]),
                "n": len(cs)} for m, cs in out.items()}


# --------------------------------------------------------------------------- metrics


def metrics(model: str, arm: str, seed: int, draws: np.ndarray, names: list[str], ref: dict,
            wall: float, grads_total: int, grads_sampling: int, divergences: int,
            max_depth_stops: int, extra: dict) -> dict:
    st = arviz_stats(draws)
    finite = bool(np.isfinite(draws).all())
    z = (st["mean"] - ref["mean"]) / np.sqrt(st["mcse"] ** 2 + ref["mcse"] ** 2)
    dsd = np.abs(st["mean"] - ref["mean"]) / ref["sd"]
    min_bulk = float(np.nanmin(st["bulk_ess"]))
    min_tail = float(np.nanmin(st["tail_ess"]))
    max_rhat = float(np.nanmax(st["rhat"]))
    gates = {
        "max_rank_rhat": max_rhat <= PROTOCOL["gates"]["max_rank_rhat"],
        "min_bulk_ess": min_bulk >= PROTOCOL["gates"]["min_bulk_ess"],
        "min_tail_ess": min_tail >= PROTOCOL["gates"]["min_tail_ess"],
        "sampling_divergences": divergences == 0,
        "finite_draws": finite,
        "no_sampler_error": True,
    }
    per_param = {
        n: {
            "mean": float(st["mean"][i]), "sd": float(st["sd"][i]), "mcse": float(st["mcse"][i]),
            "bulk_ess": float(st["bulk_ess"][i]), "tail_ess": float(st["tail_ess"][i]),
            "rhat": float(st["rhat"][i]), "ref_mean": float(ref["mean"][i]), "ref_sd": float(ref["sd"][i]),
            "ref_mcse": float(ref["mcse"][i]), "z": float(z[i]), "abs_dmean_over_ref_sd": float(dsd[i]),
        }
        for i, n in enumerate(names)
    }
    return {
        "schema": "reverse-coarser-policy-v1-cell-metrics",
        "model": model, "arm": arm, "seed": seed, "status": "ok",
        "dimension_reference_params": len(names),
        "wall_seconds": wall,
        "gradients_total": grads_total,
        "gradients_sampling": grads_sampling,
        "divergences": divergences,
        "max_depth_stops": max_depth_stops,
        "min_bulk_ess": min_bulk, "min_tail_ess": min_tail, "max_rank_rhat": max_rhat,
        "argmin_bulk_ess": names[int(np.nanargmin(st["bulk_ess"]))],
        "min_bulk_ess_per_second": min_bulk / wall,
        "min_tail_ess_per_second": min_tail / wall,
        "min_bulk_ess_per_gradient": min_bulk / grads_total,
        "min_tail_ess_per_gradient": min_tail / grads_total,
        "min_bulk_ess_per_gradient_sampling": min_bulk / grads_sampling if grads_sampling else float("nan"),
        "min_tail_ess_per_gradient_sampling": min_tail / grads_sampling if grads_sampling else float("nan"),
        "max_abs_z": float(np.nanmax(np.abs(z))),
        "argmax_abs_z": names[int(np.nanargmax(np.abs(z)))],
        "max_abs_dmean_over_ref_sd": float(np.nanmax(dsd)),
        "agreement_flag": bool(np.nanmax(np.abs(z)) > 4),
        "gates": gates,
        "passed": all(gates.values()),
        "parameters": per_param,
        **extra,
    }


def failure(model: str, arm: str, seed: int, status: str, message: str, **extra) -> dict:
    return {
        "schema": "reverse-coarser-policy-v1-cell-metrics", "model": model, "arm": arm, "seed": seed,
        "status": status, "error": message, "passed": False,
        "gates": {"no_sampler_error": False}, **extra,
    }


def cell_path(model: str, arm: str, seed: int) -> Path:
    return CELLS / f"{short(model)}-{arm}-{seed}.json"


def write_cell(cell: dict) -> None:
    CELLS.mkdir(parents=True, exist_ok=True)
    cell_path(cell["model"], cell["arm"], cell["seed"]).write_text(
        json.dumps(cell, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    s = cell["status"]
    if s == "ok":
        log(f"  {cell['arm']} {cell['seed']}: wall {cell['wall_seconds']:.2f}s grads {cell['gradients_total']} "
            f"minbulk {cell['min_bulk_ess']:.0f} mintail {cell['min_tail_ess']:.0f} rhat {cell['max_rank_rhat']:.4f} "
            f"div {cell['divergences']} max|z| {cell['max_abs_z']:.2f} passed {cell['passed']} "
            f"h {cell['median_step']:.4g} rc-stop {cell['reverse_coarser_stop_fraction']:.3f} "
            f"cont {cell['reverse_coarser_continuation_fraction']:.3f} depthcap {cell['max_depth_stop_fraction']:.3f}")
    else:
        log(f"  {cell['arm']} {cell['seed']}: {s}: {cell.get('error', '')[:200]}")


def save_draws(model: str, arm: str, seed: int, draws: np.ndarray, names: list[str], **more) -> None:
    DRAWS.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(DRAWS / f"{short(model)}-{arm}-{seed}.npz", draws=draws, names=np.asarray(names), **more)


# --------------------------------------------------------------------------- the arm


def mean_or_none(values) -> float | None:
    vals = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    return float(sum(vals) / len(vals)) if vals else None


def run_owalnuts(model: str, arm: str, seed: int, ref: dict) -> dict:
    import bridgestan as bs

    so, data = model_files(model)
    raw = DRAWS / f"{short(model)}-{arm}-{seed}.raw.json"
    DRAWS.mkdir(parents=True, exist_ok=True)
    if raw.exists():
        raw.unlink()
    cmd = [str(HARNESS), str(so), str(data), arm, str(seed), str(raw), "4"]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return failure(model, arm, seed, "timeout", f"exceeded {TIMEOUT}s")
    if cp.returncode != 0 or not raw.exists():
        return failure(model, arm, seed, "error", cp.stderr.strip()[-2000:])
    out = json.loads(raw.read_text(encoding="utf-8"))
    if out.get("status") != "ok":
        return failure(model, arm, seed, "error", out.get("error", "unknown"), wall_seconds=out.get("wall_seconds"))
    bs.compile.windows_dll_path_setup()
    sm = bs.StanModel(str(so), data=data.read_text(encoding="utf-8"), seed=1)
    cnames = [bridgestan_name(n) for n in sm.param_names(include_tp=True, include_gq=False)]
    unc = np.asarray([c["samples"] for c in out["chains_data"]], dtype=np.float64)
    con = np.empty(unc.shape[:2] + (len(cnames),))
    for c in range(unc.shape[0]):
        for d in range(unc.shape[1]):
            con[c, d] = sm.param_constrain(unc[c, d], include_tp=True, include_gq=False)
    index = {n: i for i, n in enumerate(cnames)}
    missing = [n for n in ref["names"] if n not in index]
    if missing:
        return failure(model, arm, seed, "error", f"reference parameters not produced by param_constrain: {missing[:5]}")
    draws = con[:, :, [index[n] for n in ref["names"]]]
    chains = out["chains_data"]
    grads_sampling = sum(c["retained_target_calls"] for c in chains)
    grads_total = out["target_calls_total"]
    level_built = [sum(x) for x in zip(*(c["retained_work"]["refinement_level_built"] for c in chains))]
    built = sum(level_built)
    stops: dict[str, int] = {}
    for c in chains:
        for k, v in c["retained_stop_histogram"].items():
            stops[k] = stops.get(k, 0) + v
    steps = [c["final_step_size"] for c in chains]
    retained_transitions = out["retained"] * out["chains"]
    work = lambda key: sum(c["retained_work"][key] for c in chains)  # noqa: E731
    wwork = lambda key: sum(c["warmup_work"][key] for c in chains)  # noqa: E731
    depth_hist = [sum(x) for x in zip(*(c["retained_depth_histogram"] for c in chains))]
    extra = {
        "final_step_size": steps,
        "median_step": float(statistics.median(steps)),
        "invalid_stops": sum(c["invalid_stops"] for c in chains),
        "refinement_exhaustions": sum(c["refinement_exhaustions"] for c in chains),
        "recoverable_failures_total": out["recoverable_failures_total"],
        "start_search_calls": out["init"]["start_search_calls"],
        "tuning": out["tuning"],
        "warmup_config": out["warmup_config"],
        "mass_diagonal_max": [max(c["mass_diagonal"]) for c in chains],
        "mass_diagonal_min": [min(c["mass_diagonal"]) for c in chains],
        "warmup_divergences": sum(c["warmup_divergences"] for c in chains),
        "retained_depth_histogram": depth_hist,
        "mean_depth": sum(i * n for i, n in enumerate(depth_hist)) / retained_transitions,
        "max_depth_stop_fraction": stops.get("maximum_depth", 0) / retained_transitions,
        "retained_refinement_level_histogram": [sum(x) for x in zip(*(c["retained_refinement_level_histogram"] for c in chains))],
        "retained_refinement_level_built": level_built,
        "retained_leaves_built": built,
        "retained_leaves_attempted": work("leaves_attempted"),
        "refined_leaf_fraction": (built - level_built[0]) / built if built else float("nan"),
        "leaves_per_transition": built / retained_transitions,
        "gradients_per_leaf": grads_sampling / built if built else float("nan"),
        "retained_stop_histogram": stops,
        "reverse_coarser_stop_fraction": stops.get("reverse_coarser_accepted", 0) / retained_transitions,
        "retained_reverse_coarser_stops": work("reverse_coarser_stops"),
        "retained_reverse_coarser_rejections": work("reverse_coarser_rejections"),
        "retained_reverse_coarser_continuations": work("reverse_coarser_continuations"),
        "retained_zero_weight_leaves": work("zero_weight_leaves"),
        "reverse_coarser_continuation_fraction": work("reverse_coarser_continuations") / retained_transitions,
        "zero_weight_leaf_fraction": work("zero_weight_leaves") / built if built else float("nan"),
        "retained_forward_refinement_attempts": work("forward_refinement_attempts"),
        "retained_reverse_coarsening_attempts": work("reverse_coarsening_attempts"),
        "retained_target_calls_reverse": work("target_calls_reverse"),
        "warmup_reverse_coarser_stops": wwork("reverse_coarser_stops"),
        "warmup_reverse_coarser_continuations": wwork("reverse_coarser_continuations"),
        "warmup_zero_weight_leaves": wwork("zero_weight_leaves"),
        "warmup_leaves_built": wwork("leaves_built"),
        "retained_mean_acceptance_statistic": mean_or_none([c["retained_mean_acceptance_statistic"] for c in chains]),
        "retained_max_energy_error_histogram": {
            "bins_upper": chains[0]["retained_max_energy_error_histogram"]["bins_upper"],
            "counts": [sum(x) for x in zip(*(c["retained_max_energy_error_histogram"]["counts"] for c in chains))]},
        "algorithm_revision": out["algorithm_revision"],
        "unconstrained_dimension": out["dimension"],
    }
    cell = metrics(model, arm, seed, draws, ref["names"], ref, out["wall_seconds"], grads_total, grads_sampling,
                   sum(c["divergences"] for c in chains), sum(c["maximum_depth_stops"] for c in chains), extra)
    save_draws(model, arm, seed, draws, ref["names"], unconstrained=unc)
    return cell


# --------------------------------------------------------------------------- orchestration


def run_model_arm(model: str, arm: str) -> None:
    ref = reference(model)
    for seed in SEEDS:
        if cell_path(model, arm, seed).exists():
            continue
        try:
            cell = run_owalnuts(model, arm, seed, ref)
        except Exception as e:  # noqa: BLE001
            cell = failure(model, arm, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
        write_cell(cell)


def run_all(models: list[str], arms: list[str]) -> None:
    ART.mkdir(exist_ok=True)
    machine = ART / "measured_on.json"
    if not machine.exists():
        machine.write_text(json.dumps({
            "platform": platform.platform(), "processor": platform.processor(),
            "cpu_count": os.cpu_count(), "python": sys.version.split()[0],
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "models": str(MODELS),
            "note": "shared machine; other processes may run concurrently; walls are upper bounds",
        }, indent=2) + "\n", encoding="utf-8")
    for model in models:
        log(f"== {model}")
        for arm in arms:
            if all(cell_path(model, arm, s).exists() for s in SEEDS):
                continue
            try:
                model_files(model)
            except FileNotFoundError as e:
                for seed in SEEDS:
                    if not cell_path(model, arm, seed).exists():
                        write_cell(failure(model, arm, seed, "compile_error", str(e)))
                continue
            cmd = [sys.executable, str(Path(__file__)), "cell", model, arm]
            try:
                cp = subprocess.run(cmd, timeout=TIMEOUT * len(SEEDS) + 600, text=True)
                if cp.returncode != 0:
                    log(f"child for {model}/{arm} exited {cp.returncode}")
            except subprocess.TimeoutExpired:
                log(f"child for {model}/{arm} timed out")
            for seed in SEEDS:
                if not cell_path(model, arm, seed).exists():
                    write_cell(failure(model, arm, seed, "timeout_or_crash", "child process ended without writing the cell"))


def run_checks(arms: list[str]) -> None:
    fdir = ART / "funnel"
    fdir.mkdir(parents=True, exist_ok=True)
    for arm in arms:
        for seed in SEEDS:
            out = fdir / f"defaults-{arm}-{seed}.json"
            if out.exists():
                continue
            log(f"funnel defaults {arm} {seed}")
            cp = subprocess.run([str(FUNNEL), "defaults", arm, str(seed), str(out)], capture_output=True, text=True)
            log(f"  {cp.stderr.strip()[-300:]}")


# --------------------------------------------------------------------------- analysis


def geomean(xs) -> float:
    xs = [x for x in xs if x is not None and math.isfinite(x) and x > 0]
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs))) if xs else float("nan")


def med(vals):
    vals = [v for v in vals if v is not None and isinstance(v, (int, float)) and math.isfinite(v)]
    return float(statistics.median(vals)) if vals else None


def load_cells() -> dict:
    out: dict = {}
    for path in sorted(CELLS.glob("*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        c.pop("parameters", None)
        out.setdefault(c["model"], {}).setdefault(c["arm"], {})[str(c["seed"])] = c
    return out


KEYS = ["min_bulk_ess_per_gradient", "min_bulk_ess_per_gradient_sampling", "min_tail_ess_per_gradient",
        "min_bulk_ess_per_second", "min_bulk_ess", "min_tail_ess", "max_rank_rhat", "divergences",
        "gradients_total", "gradients_sampling", "wall_seconds", "median_step", "mean_depth",
        "max_depth_stop_fraction", "leaves_per_transition", "gradients_per_leaf", "refined_leaf_fraction",
        "reverse_coarser_stop_fraction", "reverse_coarser_continuation_fraction", "zero_weight_leaf_fraction",
        "retained_reverse_coarser_rejections", "retained_reverse_coarser_continuations",
        "retained_forward_refinement_attempts", "max_abs_z", "retained_mean_acceptance_statistic"]


def per_model_summary(models: list[str], arms: list[str], cells: dict) -> dict:
    out: dict = {}
    for model in models:
        out[model] = {}
        for arm in arms:
            seeds = cells.get(model, {}).get(arm, {})
            ok = [c for c in seeds.values() if c.get("status") == "ok"]
            entry = {
                "cells": len(seeds), "ok": len(ok),
                "gates_passed": sum(1 for c in ok if c.get("passed")),
                "statuses": {s: c.get("status") for s, c in seeds.items()},
                "per_seed": {s: {k: c.get(k) for k in KEYS} | {"passed": c.get("passed")} for s, c in seeds.items()},
            }
            for k in KEYS:
                entry[k] = med([c.get(k) for c in ok])
            out[model][arm] = entry
    return out


def analyze_funnel() -> dict:
    out = {}
    for arm in ARMS:
        entry = {"per_seed": {}}
        for seed in SEEDS:
            path = ART / "funnel" / f"defaults-{arm}-{seed}.json"
            if not path.exists():
                continue
            c = json.loads(path.read_text(encoding="utf-8"))
            t = c["tail_mass"]
            entry["per_seed"][str(seed)] = {
                "estimate": t["estimate"], "mcse": t["mcse"], "z": t["z"],
                "batch_means_se": t["batch_means_se"], "z_batch_means": t["z_batch_means"],
                "target_calls_total": c["target_calls_total"],
                "omega_bulk_ess": c["omega"]["bulk_ess"], "omega_tail_ess": c["omega"]["tail_ess"],
                "omega_rhat": c["omega"]["rhat"], "omega_variance": c["omega"]["variance"],
                "omega_bulk_ess_per_call": c["omega"]["bulk_ess"] / c["target_calls_total"],
                "wall_seconds": c["wall_seconds"],
                "depth_caps": sum(ch["depth_caps"] for ch in c["chains_data"]),
                "divergences": sum(ch["divergences"] for ch in c["chains_data"]),
                "reverse_coarser_stops": sum(ch["reverse_coarser_stops"] for ch in c["chains_data"]),
                "reverse_coarser_continuations": sum(ch["reverse_coarser_continuations"] for ch in c["chains_data"]),
                "zero_weight_leaves": sum(ch["zero_weight_leaves"] for ch in c["chains_data"]),
                "leaves_built": sum(ch["leaves_built"] for ch in c["chains_data"]),
                "final_step_size": [ch["final_step_size"] for ch in c["chains_data"]],
            }
        zs = [p["z"] for p in entry["per_seed"].values()]
        entry["complete"] = len(zs) == len(SEEDS)
        entry["all_seeds_abs_z_le_2"] = bool(entry["complete"] and all(abs(z) <= 2.0 for z in zs))
        entry["max_abs_z"] = max((abs(z) for z in zs), default=None)
        entry["geomean_omega_bulk_ess_per_call"] = geomean([p["omega_bulk_ess_per_call"] for p in entry["per_seed"].values()])
        out[arm] = entry
    return out


def analyze() -> None:
    models = PROTOCOL["models"]
    healthy = PROTOCOL["cmdstan_healthy_models"]
    cells = load_cells()
    per_model = per_model_summary(models, ARMS, cells)
    cmdstan = v5_cmdstan() if (V5 / "cells").exists() else {}
    rule = PROTOCOL["decision_rule"]

    ratios = {}
    for model in models:
        b, s = per_model[model][CANDIDATE], per_model[model][BASELINE]
        ratios[model] = {
            "ratio": (b["min_bulk_ess_per_gradient"] / s["min_bulk_ess_per_gradient"])
            if b["min_bulk_ess_per_gradient"] and s["min_bulk_ess_per_gradient"] else None,
            "ratio_sampling": (b["min_bulk_ess_per_gradient_sampling"] / s["min_bulk_ess_per_gradient_sampling"])
            if b["min_bulk_ess_per_gradient_sampling"] and s["min_bulk_ess_per_gradient_sampling"] else None,
            "ratio_per_second": (b["min_bulk_ess_per_second"] / s["min_bulk_ess_per_second"])
            if b["min_bulk_ess_per_second"] and s["min_bulk_ess_per_second"] else None,
            "step_ratio": (b["median_step"] / s["median_step"]) if b["median_step"] and s["median_step"] else None,
            "vs_cmdstan": {arm: (per_model[model][arm]["min_bulk_ess_per_gradient"] / cmdstan[model]["min_bulk_ess_per_gradient"])
                           if model in cmdstan and per_model[model][arm]["min_bulk_ess_per_gradient"] else None for arm in ARMS},
        }
    all_ratios = [ratios[m]["ratio"] for m in models]
    complete = all(r is not None for r in all_ratios)
    gates = {arm: sum(per_model[m][arm]["gates_passed"] for m in models) for arm in ARMS}
    control = [m for m in models if m not in TARGET_MODELS]
    funnel = analyze_funnel()
    decision = {
        "complete": complete,
        "geomean_all": geomean(all_ratios),
        "geomean_healthy": geomean([ratios[m]["ratio"] for m in healthy]),
        "geomean_targets": geomean([ratios[m]["ratio"] for m in TARGET_MODELS]),
        "geomean_controls": geomean([ratios[m]["ratio"] for m in control]),
        "geomean_sampling_all": geomean([ratios[m]["ratio_sampling"] for m in models]),
        "geomean_per_second_all": geomean([ratios[m]["ratio_per_second"] for m in models]),
        "min_ratio": min((r for r in all_ratios if r is not None), default=None),
        "argmin_ratio": min((m for m in models if ratios[m]["ratio"] is not None), key=lambda m: ratios[m]["ratio"], default=None),
        "gates": gates,
        "vs_cmdstan_healthy": {arm: geomean([ratios[m]["vs_cmdstan"][arm] for m in healthy]) for arm in ARMS},
        "funnel_beyond_all_seeds_abs_z_le_2": funnel[CANDIDATE]["all_seeds_abs_z_le_2"],
        "funnel_stop_all_seeds_abs_z_le_2": funnel[BASELINE]["all_seeds_abs_z_le_2"],
    }
    decision["C1_geomean"] = bool(complete and decision["geomean_all"] >= rule["geomean_min"])
    decision["C2_no_model_below"] = bool(complete and decision["min_ratio"] >= rule["per_model_min"])
    decision["C3_gates"] = gates[CANDIDATE] >= gates[BASELINE]
    decision["C4_funnel"] = bool(decision["funnel_beyond_all_seeds_abs_z_le_2"])
    decision["C5_targets"] = bool(complete and decision["geomean_targets"] >= rule["targets_geomean_min"])
    decision["flip"] = all(decision[k] for k in ("C1_geomean", "C2_no_model_below", "C3_gates", "C4_funnel", "C5_targets"))

    summary = {
        "schema": "reverse-coarser-policy-v1-summary",
        "protocol_sha256": __import__("hashlib").sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
        "analyzed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "per_model": per_model, "ratios": ratios, "cmdstan_v5": cmdstan, "decision": decision, "funnel": funnel,
    }
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=float) + "\n", encoding="utf-8")
    write_table(models, per_model, ratios, decision, funnel, cmdstan)
    log(f"decision: {json.dumps({k: v for k, v in decision.items() if k.startswith('C') or k in ('flip', 'geomean_all', 'geomean_targets', 'min_ratio', 'argmin_ratio', 'gates')})}")


def f(x, fmt):
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)


def write_table(models, per_model, ratios, decision, funnel, cmdstan) -> None:
    L = ["# reverse_coarser_policy_v1 — results", "",
         f"Seed medians over {len(SEEDS)} seeds ({SEEDS[0]}–{SEEDS[-1]}) of the per-cell minimum over reference parameters "
         "of bulk ESS per gradient (all target calls, warmup included); `gates` = cells passing rank R-hat <= 1.01, bulk/tail "
         "ESS >= 400, zero divergences (of 3); CmdStan from `posteriordb_bench_v5` (seeds 87101–87103). `rc stop` = fraction "
         "of retained transitions ending in a reverse-coarser stop (`stop` arm); `cont` = continued leaves per retained "
         "transition (`beyond` arm); "
         "`zero-w` = zero-weight leaves / built leaves; `depth cap` = fraction of retained transitions ending at the depth cap.", "",
         "## Per model", "",
         "| model | ESS/grad x1e3 `stop` | `beyond` | ratio | ratio (sampling grads) | ratio (per s) | gates stop/beyond | h beyond/stop | leaves/orbit stop → beyond | rc stop | cont | zero-w | depth cap stop → beyond | vs CmdStan stop / beyond |",
         "|---|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---:|---|---|"]
    for m in models:
        s, b, r = per_model[m][BASELINE], per_model[m][CANDIDATE], ratios[m]
        tag = " **(target)**" if m in TARGET_MODELS else ""
        L.append(f"| {m}{tag} | {f((s['min_bulk_ess_per_gradient'] or float('nan')) * 1e3, '.3f')} | "
                 f"{f((b['min_bulk_ess_per_gradient'] or float('nan')) * 1e3, '.3f')} | {f(r['ratio'], '.3f')} | "
                 f"{f(r['ratio_sampling'], '.3f')} | {f(r['ratio_per_second'], '.3f')} | {s['gates_passed']}/{b['gates_passed']} | "
                 f"{f(r['step_ratio'], '.3f')} | {f(s['leaves_per_transition'], '.1f')} → {f(b['leaves_per_transition'], '.1f')} | "
                 f"{f(s['reverse_coarser_stop_fraction'], '.3f')} | {f(b['reverse_coarser_continuation_fraction'], '.3f')} | "
                 f"{f(b['zero_weight_leaf_fraction'], '.3f')} | {f(s['max_depth_stop_fraction'], '.3f')} → {f(b['max_depth_stop_fraction'], '.3f')} | "
                 f"{f(r['vs_cmdstan'][BASELINE], '.3f')} / {f(r['vs_cmdstan'][CANDIDATE], '.3f')} |")
    d = decision
    L += ["", "## Decision (protocol.json `decision_rule`)", "",
          "| statistic | value |", "|---|---:|",
          f"| geomean ratio `beyond`/`stop`, 17 models | {f(d['geomean_all'], '.3f')} |",
          f"| geomean ratio, 14 CmdStan-healthy models | {f(d['geomean_healthy'], '.3f')} |",
          f"| geomean ratio, 4 target models | {f(d['geomean_targets'], '.3f')} |",
          f"| geomean ratio, 13 control models | {f(d['geomean_controls'], '.3f')} |",
          f"| geomean ratio on sampling gradients only | {f(d['geomean_sampling_all'], '.3f')} |",
          f"| geomean ratio per second | {f(d['geomean_per_second_all'], '.3f')} |",
          f"| worst model | {f(d['min_ratio'], '.3f')} ({d['argmin_ratio']}) |",
          f"| gates passed (of 51) stop / beyond | {d['gates'][BASELINE]} / {d['gates'][CANDIDATE]} |",
          f"| vs CmdStan (healthy) stop / beyond | {f(d['vs_cmdstan_healthy'][BASELINE], '.3f')} / {f(d['vs_cmdstan_healthy'][CANDIDATE], '.3f')} |",
          f"| C1 geomean >= {PROTOCOL['decision_rule']['geomean_min']} | {d['C1_geomean']} |",
          f"| C2 no model < {PROTOCOL['decision_rule']['per_model_min']} | {d['C2_no_model_below']} |",
          f"| C3 gates >= stop | {d['C3_gates']} |",
          f"| C4 funnel \\|z\\| <= 2 every seed (beyond) | {d['C4_funnel']} |",
          f"| C5 targets geomean >= {PROTOCOL['decision_rule']['targets_geomean_min']} | {d['C5_targets']} |",
          f"| **flip the default** | **{d['flip']}** |",
          "", "## Funnel (Neal's 10-D funnel at the sampler defaults, 4 x 2,000/20,000, P(omega < -5) exact 0.0478)", "",
          "| arm | seed | estimate | MCSE z | batch-means z | omega bulk ESS | ESS/call x1e3 | rc stops | continuations | zero-w leaves / built | depth caps | divergences |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|"]
    for arm in ARMS:
        for seed, p in funnel[arm]["per_seed"].items():
            L.append(f"| {arm} | {seed} | {p['estimate']:.4f} | {p['z']:+.2f} | {p['z_batch_means']:+.2f} | {p['omega_bulk_ess']:.0f} | "
                     f"{p['omega_bulk_ess_per_call'] * 1e3:.3f} | {p['reverse_coarser_stops']} | {p['reverse_coarser_continuations']} | "
                     f"{p['zero_weight_leaves']} / {p['leaves_built']} | {p['depth_caps']} | {p['divergences']} |")
    (ART / "results-table.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd = args[0]
    if cmd == "run":
        models, arms = PROTOCOL["models"], ARMS
        for a in args[1:]:
            if a.startswith("--models="):
                models = a.split("=", 1)[1].split(",")
            if a.startswith("--arms="):
                arms = a.split("=", 1)[1].split(",")
        run_all(models, arms)
    elif cmd == "cell":
        run_model_arm(args[1], args[2])
    elif cmd == "checks":
        run_checks(ARMS)
    elif cmd == "analyze":
        analyze()
    else:
        raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    main()
