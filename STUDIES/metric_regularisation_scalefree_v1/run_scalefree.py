#!/usr/bin/env python3
"""Scale-free diagonal-metric regularisation study driver (WP41): the posteriordb v5 protocol (17 models, 4 chains x
1,000/1,000, uniform(-2, 2) starts, four threads) restricted to three oWALNUTS arms that differ only in the
`DiagonalMetricRegularization` applied at slow-window boundaries; Neal's funnel as the side check.

    python run_scalefree.py build      # compile every BridgeStan model (no STAN_THREADS)
    python run_scalefree.py run        # every model/arm/seed in protocol order (resumable, strictly sequential)
    python run_scalefree.py cell <model> <arm>   # one model/arm, all seeds (child process)
    python run_scalefree.py checks     # funnel at the sampler defaults with each arm, three seeds
    python run_scalefree.py analyze    # artifacts/summary.json + results-table.md

Each cell writes `artifacts/cells/<model>-<arm>-<seed>.json` (metrics, installed metric per chain and per window, no
draws) and `artifacts/draws/<model>-<arm>-<seed>.npz` (constrained draws on the reference parameter set and the
unconstrained draws; uncommitted). Failures are recorded as cells with status != "ok".
Derived from `STUDIES/refinement_role_v1/run_refinement.py`.
"""
from __future__ import annotations

import json
import math
import os
import platform
import shutil
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
MODELS = HERE / "models"
PDB_PATH = HERE / PROTOCOL["posteriordb"]["path"]
HARNESS = HERE / "target" / "release" / "posteriordb-cell.exe"
FUNNEL = HERE / "target" / "release" / "funnel.exe"
ARMS = PROTOCOL["arms_order"]
BASELINE = "da"
V5 = HERE.parent / "posteriordb_bench_v5" / "artifacts"
SEEDS = PROTOCOL["seeds"]
TIMEOUT = PROTOCOL["cell_timeout_seconds"]
os.environ.setdefault("MAKE", "mingw32-make")
# BridgeStan make arguments: no STAN_THREADS (v1 wall-gap finding). The harness loads one library
# copy per chain thread (ReplicatedStanTarget).
BRIDGESTAN_MAKE_ARGS: list[str] = []


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
    """Reference draws as (chains, draws, P) with column names and ArviZ summaries."""
    p = posterior(model)
    ref = p.reference_draws()
    names = list(ref[0].keys())
    arr = np.asarray([[c[n] for n in names] for c in ref], dtype=np.float64)  # (chains, P, draws)
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
        "bulk_ess": bulk,
        "tail_ess": tail,
        "rhat": rhat,
        "mcse": mcse,
    }


# --------------------------------------------------------------------------- compilation


def prepare_bridgestan(model: str) -> tuple[Path, Path]:
    """Copy the Stan program + data into models/ and compile with BridgeStan once."""
    import bridgestan as bs

    p = posterior(model)
    MODELS.mkdir(exist_ok=True)
    stan = MODELS / f"{short(model)}.stan"
    data = MODELS / f"{short(model)}.data.json"
    if not stan.exists():
        shutil.copyfile(p.model.code_file_path("stan"), stan)
    if not data.exists():
        data.write_text(json.dumps(p.data.values()), encoding="utf-8")
    so = stan.with_name(f"{stan.stem}_model.so")
    if not so.exists():
        t = time.perf_counter()
        bs.compile_model(stan, make_args=BRIDGESTAN_MAKE_ARGS)
        log(f"bridgestan compiled {model} in {time.perf_counter() - t:.1f}s")
    return so, data


# --------------------------------------------------------------------------- v5 CmdStan reference (cited, not rerun)


def v5_cells() -> dict:
    """The v5 per-cell metrics, keyed model -> arm -> seed."""
    out: dict = {}
    for path in sorted((V5 / "cells").glob("*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        c.pop("parameters", None)
        out.setdefault(c["model"], {}).setdefault(c["arm"], {})[str(c["seed"])] = c
    return out


# --------------------------------------------------------------------------- metrics


def metrics(model: str, arm: str, seed: int, draws: np.ndarray, names: list[str], ref: dict,
            wall: float, grads_total: int, grads_sampling: int, divergences: int,
            max_depth_stops: int, extra: dict) -> dict:
    """draws: (chains, draws, P) on the reference parameter set (same order as ref)."""
    st = arviz_stats(draws)
    finite = bool(np.isfinite(draws).all())
    z = (st["mean"] - ref["mean"]) / np.sqrt(st["mcse"] ** 2 + ref["mcse"] ** 2)
    dsd = np.abs(st["mean"] - ref["mean"]) / ref["sd"]
    min_bulk = float(np.nanmin(st["bulk_ess"]))
    min_tail = float(np.nanmin(st["tail_ess"]))
    max_rhat = float(np.nanmax(st["rhat"]))
    wall_sampling = wall * grads_sampling / grads_total if grads_total else float("nan")
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
        "schema": "metric-regularisation-scalefree-v1-cell-metrics",
        "model": model, "arm": arm, "seed": seed, "status": "ok",
        "dimension_reference_params": len(names),
        "wall_seconds": wall,
        "wall_seconds_sampling_estimated": wall_sampling,
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
        "schema": "metric-regularisation-scalefree-v1-cell-metrics", "model": model, "arm": arm, "seed": seed,
        "status": status, "error": message, "passed": False,
        "gates": {"no_sampler_error": False}, **extra,
    }


def cell_path(model: str, arm: str, seed: int) -> Path:
    return CELLS / f"{short(model)}-{arm}-{seed}.json"


def write_cell(cell: dict) -> None:
    CELLS.mkdir(parents=True, exist_ok=True)
    cell_path(cell["model"], cell["arm"], cell["seed"]).write_text(json.dumps(cell, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    s = cell["status"]
    if s == "ok":
        log(f"  {cell['arm']} {cell['seed']}: wall {cell['wall_seconds']:.2f}s grads {cell['gradients_total']} "
            f"minbulk {cell['min_bulk_ess']:.0f} mintail {cell['min_tail_ess']:.0f} rhat {cell['max_rank_rhat']:.4f} "
            f"div {cell['divergences']} max|z| {cell['max_abs_z']:.2f} passed {cell['passed']} "
            f"h {cell['median_step']:.4g} installed/posterior var (median chain) min {cell['installed_over_posterior_variance']['min_median_chain']:.3g} "
            f"max {cell['installed_over_posterior_variance']['max_median_chain']:.3g}")
    else:
        log(f"  {cell['arm']} {cell['seed']}: {s}: {cell.get('error', '')[:200]}")


def save_draws(model: str, arm: str, seed: int, draws: np.ndarray, names: list[str], **more) -> None:
    DRAWS.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(DRAWS / f"{short(model)}-{arm}-{seed}.npz", draws=draws, names=np.asarray(names), **more)




# --------------------------------------------------------------------------- the arm


def mean_or_none(values) -> float | None:
    vals = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    return float(sum(vals) / len(vals)) if vals else None


def installed_metric_summary(chains: list[dict], unc: np.ndarray) -> dict:
    """Installed diagonal against the posterior variance in unconstrained space.

    `installed variance` = 1 / mass entry (the API's mass is the inverse variance). The posterior variance per
    unconstrained coordinate is the variance of this cell's retained draws pooled over its four chains. The ratio
    installed / posterior per coordinate and chain says where a regularisation over- (ratio >> 1) or under-
    (ratio << 1) states the scale of a coordinate.
    """
    posterior_var = unc.reshape(-1, unc.shape[-1]).var(0, ddof=1)
    installed = np.asarray([[1.0 / m for m in c["mass_diagonal"]] for c in chains], dtype=np.float64)  # (chains, dim)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = installed / posterior_var[None, :]
    log_ratio = np.log10(ratio)
    per_chain_min = np.nanmin(ratio, axis=1)
    per_chain_max = np.nanmax(ratio, axis=1)
    per_chain_med = np.nanmedian(ratio, axis=1)
    # per-window: the median window variance anchor implied is not observable from the mass alone, so record
    # the installed variance spread of every window (log10 max/min) per chain.
    windows = [[{"window_index": u["window_index"], "transition": u["transition"], "sample_count": u["sample_count"],
                 "outcome": u["outcome"],
                 "installed_variance_min": (min(1.0 / m for m in u["mass_diagonal"]) if u["mass_diagonal"] else None),
                 "installed_variance_max": (max(1.0 / m for m in u["mass_diagonal"]) if u["mass_diagonal"] else None),
                 "step_before": u["step_before"]}
                for u in c["metric_updates"]] for c in chains]
    return {
        "posterior_variance_unconstrained": posterior_var.tolist(),
        "installed_variance_per_chain": installed.tolist(),
        "installed_over_posterior_per_chain": ratio.tolist(),
        "min_per_chain": per_chain_min.tolist(),
        "max_per_chain": per_chain_max.tolist(),
        "median_per_chain": per_chain_med.tolist(),
        "min_median_chain": float(np.median(per_chain_min)),
        "max_median_chain": float(np.median(per_chain_max)),
        "max_abs_log10_ratio": float(np.nanmax(np.abs(log_ratio))),
        "coords_ratio_gt_2": int(np.sum(ratio > 2.0)),
        "coords_ratio_lt_0.5": int(np.sum(ratio < 0.5)),
        "installed_variance_log10_spread_per_chain": (np.log10(installed.max(1)) - np.log10(installed.min(1))).tolist(),
        "windows": windows,
    }


def run_owalnuts(model: str, arm: str, seed: int, ref: dict) -> dict:
    import bridgestan as bs

    so, data = prepare_bridgestan(model)
    DRAWS.mkdir(parents=True, exist_ok=True)
    raw = DRAWS / f"{short(model)}-{arm}-{seed}.raw.json"
    if raw.exists():
        raw.unlink()
    cmd = [str(HARNESS), str(so), str(data), arm, str(seed), str(raw), str(PROTOCOL["threads"])]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return failure(model, arm, seed, "timeout", f"exceeded {TIMEOUT}s")
    if cp.returncode != 0 or not raw.exists():
        return failure(model, arm, seed, "error", f"exit {cp.returncode}: " + cp.stderr.strip()[-2000:])
    out = json.loads(raw.read_text(encoding="utf-8"))
    if out.get("status") != "ok":
        return failure(model, arm, seed, "error", out.get("error", "unknown"), wall_seconds=out.get("wall_seconds"))
    bs.compile.windows_dll_path_setup()
    sm = bs.StanModel(str(so), data=data.read_text(encoding="utf-8"), seed=1)
    cnames = [bridgestan_name(n) for n in sm.param_names(include_tp=True, include_gq=False)]
    unc = np.asarray([c["samples"] for c in out["chains_data"]], dtype=np.float64)  # (chains, draws, dim)
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
    extra = {
        "final_step_size": steps,
        "median_step": float(statistics.median(steps)),
        "invalid_stops": sum(c["invalid_stops"] for c in chains),
        "refinement_exhaustions": sum(c["refinement_exhaustions"] for c in chains),
        "refinement_exhaustions_per_chain": [c["refinement_exhaustions"] for c in chains],
        "frozen_chains": sum(1 for c in chains if c["refinement_exhaustions"] > out["retained"] // 2),
        "recoverable_failures_total": out["recoverable_failures_total"],
        "start_search_calls": out["init"]["start_search_calls"],
        "tuning": out["tuning"],
        "warmup_config": out["warmup_config"],
        "mass_diagonal_per_chain": [c["mass_diagonal"] for c in chains],
        "mass_diagonal_max": [max(c["mass_diagonal"]) for c in chains],
        "mass_diagonal_min": [min(c["mass_diagonal"]) for c in chains],
        "installed_over_posterior_variance": installed_metric_summary(chains, unc),
        "metric_updates_per_chain": [c["metric_updates"] for c in chains],
        "warmup_divergences": sum(c["warmup_divergences"] for c in chains),
        "retained_depth_histogram": [sum(x) for x in zip(*(c["retained_depth_histogram"] for c in chains))],
        "retained_refinement_level_built": level_built,
        "refined_leaf_fraction": (built - level_built[0]) / built if built else float("nan"),
        "leaves_per_transition": built / retained_transitions,
        "retained_stop_histogram": stops,
        "retained_mean_acceptance_statistic": mean_or_none([c["retained_mean_acceptance_statistic"] for c in chains]),
        "algorithm_revision": out["algorithm_revision"],
        "unconstrained_dimension": out["dimension"],
    }
    cell = metrics(model, arm, seed, draws, ref["names"], ref, out["wall_seconds"], grads_total, grads_sampling,
                   sum(c["divergences"] for c in chains), sum(c["maximum_depth_stops"] for c in chains), extra)
    save_draws(model, arm, seed, draws, ref["names"], unconstrained=unc)
    raw.unlink()  # the npz keeps the unconstrained and constrained draws
    return cell


# --------------------------------------------------------------------------- orchestration


def run_model_arm(model: str, arm: str) -> None:
    """All seeds of one (model, arm) in this process, ascending."""
    ref = reference(model)
    for seed in SEEDS:
        if cell_path(model, arm, seed).exists():
            continue
        try:
            cell = run_owalnuts(model, arm, seed, ref)
        except Exception as e:  # noqa: BLE001
            cell = failure(model, arm, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
        write_cell(cell)


def build_all(models: list[str]) -> None:
    for model in models:
        log(f"== build {model}")
        try:
            prepare_bridgestan(model)
        except Exception as e:  # noqa: BLE001
            log(f"bridgestan compile failed for {model}: {str(e)[-500:]}")


def run_all(models: list[str], arms: list[str]) -> None:
    ART.mkdir(exist_ok=True)
    machine = ART / "measured_on.json"
    if not machine.exists():
        machine.write_text(json.dumps({
            "platform": platform.platform(), "processor": platform.processor(),
            "cpu_count": os.cpu_count(), "python": sys.version.split()[0],
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "note": "shared machine; nine other agents run concurrently (WP41-WP50); walls are contended upper bounds",
        }, indent=2) + "\n", encoding="utf-8")
    for model in models:
        log(f"== {model}")
        try:
            prepare_bridgestan(model)
        except Exception as e:  # noqa: BLE001
            log(f"bridgestan compile failed for {model}: {str(e)[-500:]}")
        for arm in arms:
            if all(cell_path(model, arm, s).exists() for s in SEEDS):
                continue
            if not (MODELS / f"{short(model)}_model.so").exists():
                for seed in SEEDS:
                    if not cell_path(model, arm, seed).exists():
                        write_cell(failure(model, arm, seed, "compile_error", "bridgestan library missing"))
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


# --------------------------------------------------------------------------- funnel side check


def run_checks(arms: list[str]) -> None:
    """Neal's funnel at the sampler defaults with each arm, every seed, in arm order then seed order (resumable)."""
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
                "batch_means_se": t["batch_means_se"], "z_batch_means": t["z_batch_means"], "per_chain": t["per_chain"],
                "target_calls_total": c["target_calls_total"], "retained_target_calls": c["retained_target_calls"],
                "omega_bulk_ess": c["omega"]["bulk_ess"], "omega_tail_ess": c["omega"]["tail_ess"], "omega_rhat": c["omega"]["rhat"],
                "omega_bulk_ess_per_call": c["omega"]["bulk_ess"] / c["target_calls_total"],
                "wall_seconds": c["wall_seconds"],
                "depth_caps": sum(ch["depth_caps"] for ch in c["chains_data"]),
                "divergences": sum(ch["divergences"] for ch in c["chains_data"]),
                "refinement_exhaustions": sum(ch["refinement_exhaustions"] for ch in c["chains_data"]),
                "final_step_size": [ch["final_step_size"] for ch in c["chains_data"]],
                "mass_diagonal": [ch["mass_diagonal"] for ch in c["chains_data"]],
            }
        zs = [p["z"] for p in entry["per_seed"].values()]
        entry["complete"] = len(zs) == len(SEEDS)
        entry["all_seeds_abs_z_le_2"] = bool(entry["complete"] and all(abs(z) <= 2.0 for z in zs))
        entry["max_abs_z"] = max((abs(z) for z in zs), default=None)
        out[arm] = entry
    return out


# --------------------------------------------------------------------------- analysis


def geomean(xs: list[float]) -> float:
    xs = [x for x in xs if x is not None and math.isfinite(x) and x > 0]
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs))) if xs else float("nan")


def med(vals):
    vals = [v for v in vals if v is not None and isinstance(v, (int, float)) and math.isfinite(v)]
    return statistics.median(vals) if vals else None


def load_cells(directory: Path) -> dict:
    cells: dict = {}
    for path in sorted(directory.glob("*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        c.pop("parameters", None)
        if c.get("status") == "ok" and c.get("gradients_total"):
            c["wall_per_gradient_us"] = 1e6 * c["wall_seconds"] / c["gradients_total"]
        cells.setdefault(c["model"], {}).setdefault(c["arm"], {})[str(c["seed"])] = c
    return cells


KEYS = ["min_bulk_ess_per_second", "min_bulk_ess_per_gradient", "min_tail_ess_per_gradient", "wall_seconds",
        "gradients_total", "gradients_sampling", "min_bulk_ess", "min_tail_ess", "max_rank_rhat", "max_abs_z",
        "wall_per_gradient_us", "max_depth_stops", "median_step", "refined_leaf_fraction", "leaves_per_transition",
        "retained_mean_acceptance_statistic"]


def per_model_summary(models: list[str], arms: list[str], cells: dict) -> dict:
    per_model = {}
    for model in models:
        row = {}
        for arm in arms:
            sc = cells.get(model, {}).get(arm, {})
            ok = [c for c in sc.values() if c.get("status") == "ok"]
            entry = {"n_cells": len(sc), "n_ok": len(ok), "n_passed": sum(1 for c in ok if c["passed"]),
                     "statuses": {s: c.get("status") for s, c in sc.items()},
                     "errors": {s: c.get("error", "")[:300] for s, c in sc.items() if c.get("status") != "ok"},
                     "divergences": [c["divergences"] for c in ok],
                     "frozen_chains": [c.get("frozen_chains", 0) for c in ok],
                     "final_step_size": [c.get("final_step_size") for c in ok],
                     "mass_diagonal_max": [c.get("mass_diagonal_max") for c in ok],
                     "mass_diagonal_min": [c.get("mass_diagonal_min") for c in ok],
                     "installed_over_posterior_min": [c["installed_over_posterior_variance"]["min_per_chain"] for c in ok],
                     "installed_over_posterior_max": [c["installed_over_posterior_variance"]["max_per_chain"] for c in ok],
                     "agreement_flags": sum(1 for c in ok if c["agreement_flag"])}
            for k in KEYS:
                vals = [c[k] for c in ok if k in c and c[k] is not None and math.isfinite(c[k])]
                entry[k] = {"median": statistics.median(vals) if vals else None,
                            "min": min(vals) if vals else None, "max": max(vals) if vals else None, "values": vals}
            row[arm] = entry
        per_model[model] = row
    return per_model


def mechanism(models: list[str], cells: dict) -> dict:
    """Per model and arm: per-coordinate median over the 12 chains of the installed variance, of the
    installed / posterior variance ratio, and the arm / da ratio of the installed variance."""
    out = {}
    for model in models:
        row = {}
        for arm in ARMS:
            ok = [c for c in cells.get(model, {}).get(arm, {}).values() if c.get("status") == "ok"]
            if not ok:
                continue
            inst = np.asarray([ch for c in ok for ch in c["installed_over_posterior_variance"]["installed_variance_per_chain"]])
            ratio = np.asarray([ch for c in ok for ch in c["installed_over_posterior_variance"]["installed_over_posterior_per_chain"]])
            post = np.asarray([c["installed_over_posterior_variance"]["posterior_variance_unconstrained"] for c in ok])
            row[arm] = {"installed_variance_median": np.median(inst, 0).tolist(),
                        "installed_variance_min_chain": inst.min(0).tolist(),
                        "installed_variance_max_chain": inst.max(0).tolist(),
                        "installed_over_posterior_median": np.median(ratio, 0).tolist(),
                        "posterior_variance_median": np.median(post, 0).tolist(),
                        "chains": int(inst.shape[0])}
        if BASELINE in row:
            for arm in ARMS:
                if arm != BASELINE and arm in row:
                    a = np.asarray(row[arm]["installed_variance_median"])
                    b = np.asarray(row[BASELINE]["installed_variance_median"])
                    row[arm]["installed_variance_vs_da"] = (a / b).tolist()
        out[model] = row
    return out


def analyze() -> None:
    models = PROTOCOL["models"]
    cells = load_cells(CELLS)
    per_model = per_model_summary(models, ARMS, cells)
    v5 = v5_cells()
    v5_per_model = per_model_summary_v5(models, v5)
    decision = {}
    for arm in ARMS:
        per = {}
        for model in models:
            a, b = per_model[model][arm], per_model[model][BASELINE]
            ra = a["min_bulk_ess_per_gradient"]["median"]
            rb = b["min_bulk_ess_per_gradient"]["median"]
            cs = v5_per_model.get(model, {}).get("cmdstan")
            per[model] = {
                "ratio_vs_da": (ra / rb) if (ra and rb) else None,
                "ratio_vs_cmdstan_v5": (ra / cs) if (ra and cs) else None,
                "per_seed_ratio_vs_da": {s: (a_c["min_bulk_ess_per_gradient"] / b_c["min_bulk_ess_per_gradient"])
                                         for s, a_c in cells.get(model, {}).get(arm, {}).items()
                                         if a_c.get("status") == "ok" and (b_c := cells.get(model, {}).get(BASELINE, {}).get(s, {})).get("status") == "ok"
                                         and b_c["min_bulk_ess_per_gradient"]},
                "gates": a["n_passed"], "gates_da": b["n_passed"],
                "ess_per_gradient_x1e3": (ra or float("nan")) * 1e3,
                "gradients_ratio_vs_da": (a["gradients_total"]["median"] / b["gradients_total"]["median"]) if (a["gradients_total"]["median"] and b["gradients_total"]["median"]) else None,
                "ess_ratio_vs_da": (a["min_bulk_ess"]["median"] / b["min_bulk_ess"]["median"]) if (a["min_bulk_ess"]["median"] and b["min_bulk_ess"]["median"]) else None,
                "h_ratio_vs_da": (a["median_step"]["median"] / b["median_step"]["median"]) if (a["median_step"]["median"] and b["median_step"]["median"]) else None,
                "median_step": a["median_step"]["median"],
                "divergences": a["divergences"], "frozen_chains": a["frozen_chains"],
                "max_rank_rhat": a["max_rank_rhat"]["median"],
            }
        ratios = {m: per[m]["ratio_vs_da"] for m in models if per[m]["ratio_vs_da"]}
        decision[arm] = {
            "per_model": per,
            "cells_passed": sum(per_model[m][arm]["n_passed"] for m in models),
            "cells_ok": sum(per_model[m][arm]["n_ok"] for m in models),
            "models_with_ratio": len(ratios),
            "geomean_ratio_vs_da": geomean(list(ratios.values())),
            "min_ratio_vs_da": min(ratios.values()) if ratios else None,
            "argmin_ratio_vs_da": min(ratios, key=ratios.get) if ratios else None,
            "models_below_0.85": {m: r for m, r in ratios.items() if r < 0.85},
            "models_above_1.15": {m: r for m, r in ratios.items() if r > 1.15},
            "geomean_ratio_vs_cmdstan_v5": geomean([per[m]["ratio_vs_cmdstan_v5"] for m in models if per[m]["ratio_vs_cmdstan_v5"]]),
            "geomean_h_ratio_vs_da": geomean([per[m]["h_ratio_vs_da"] for m in models if per[m]["h_ratio_vs_da"]]),
            "geomean_gradients_ratio_vs_da": geomean([per[m]["gradients_ratio_vs_da"] for m in models if per[m]["gradients_ratio_vs_da"]]),
        }
    funnel = analyze_funnel()
    da_cells = decision[BASELINE]["cells_passed"]
    dr = PROTOCOL["decision_rule"]
    rule = {}
    for arm in ARMS:
        if arm == BASELINE:
            continue
        d = decision[arm]
        complete = d["models_with_ratio"] == len(models)
        fz = funnel.get(arm, {})
        crit = {
            "C1_geomean_ge": {"value": d["geomean_ratio_vs_da"], "threshold": dr["geomean_min"],
                              "held": bool(d["geomean_ratio_vs_da"] >= dr["geomean_min"]) if complete else False},
            "C2_no_model_below": {"value": d["min_ratio_vs_da"], "argmin": d["argmin_ratio_vs_da"], "threshold": dr["per_model_min"],
                                  "held": bool(d["min_ratio_vs_da"] >= dr["per_model_min"]) if complete else False},
            "C3_gates_ge_da": {"value": d["cells_passed"], "da": da_cells, "held": bool(d["cells_passed"] >= da_cells)},
            "C4_funnel_abs_z_le_2": {"value": [p["z"] for p in fz.get("per_seed", {}).values()],
                                     "held": bool(fz.get("all_seeds_abs_z_le_2")) if fz.get("complete") else False},
        }
        crit["all_held"] = all(c["held"] is True for c in crit.values())
        rule[arm] = crit
    flip = sorted([a for a, c in rule.items() if c["all_held"]], key=lambda a: -decision[a]["geomean_ratio_vs_da"])
    mech = mechanism(models, cells)
    summary = {
        "schema": "metric-regularisation-scalefree-v1-summary",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "protocol_sha256": __import__("hashlib").sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
        "decision": decision,
        "decision_rule": rule,
        "arms_meeting_rule": flip,
        "recommendation": (f"flip the default to {flip[0]}" if flip else "keep DiagonalMetricRegularization::Stan"),
        "funnel": funnel,
        "per_model": per_model,
        "mechanism": mech,
        "v5_cmdstan_min_bulk_ess_per_gradient": {m: v5_per_model.get(m, {}).get("cmdstan") for m in models},
        "cells": cells,
    }
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=float) + "\n", encoding="utf-8")
    write_table(models, per_model, decision, rule, funnel, mech, flip)


def per_model_summary_v5(models: list[str], v5: dict) -> dict:
    """Seed median of CmdStan's min bulk ESS per gradient in posteriordb_bench_v5 (cited)."""
    out = {}
    for m in models:
        vals = [c["min_bulk_ess_per_gradient"] for c in v5.get(m, {}).get("cmdstan", {}).values() if c.get("status") == "ok"]
        out[m] = {"cmdstan": statistics.median(vals) if vals else None}
    return out


def f(x, fmt):
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)


def write_table(models, per_model, decision, rule, funnel, mech, flip) -> None:
    seeds = ", ".join(str(s) for s in SEEDS)
    L = ["# metric_regularisation_scalefree_v1 — results", "",
         f"Seed medians over 3 seeds ({seeds}) of the per-cell minimum over reference parameters; `gates` = cells passing "
         "rank R-hat <= 1.01, bulk/tail ESS >= 400, zero retained divergences; ESS/grad = min bulk ESS per target call "
         "(warmup included). Walls are contended (ten agents on 16 cores).", "",
         "## Arms against `da` (min bulk ESS per gradient; seed medians; ratio arm / da)", "",
         "| arm | cells passed | geomean vs da (17) | min ratio (model) | models < 0.85 | models > 1.15 | vs CmdStan v5 (cited) | h vs da | grads vs da |",
         "|---|---:|---:|---|---|---|---:|---:|---:|"]
    for arm in ARMS:
        d = decision[arm]
        L.append(f"| {arm} | {d['cells_passed']}/{d['cells_ok']} | {f(d['geomean_ratio_vs_da'], '.3f')} | "
                 f"{f(d['min_ratio_vs_da'], '.2f')} ({d['argmin_ratio_vs_da']}) | {', '.join(f'{m} {r:.2f}' for m, r in d['models_below_0.85'].items()) or 'none'} | "
                 f"{', '.join(f'{m} {r:.2f}' for m, r in d['models_above_1.15'].items()) or 'none'} | "
                 f"{f(d['geomean_ratio_vs_cmdstan_v5'], '.3f')} | {f(d['geomean_h_ratio_vs_da'], '.3f')} | {f(d['geomean_gradients_ratio_vs_da'], '.3f')} |")
    L += ["", "## Per model", "",
          "`gates` da/sfmed/sfstan; ratio = arm / da of the seed-median ESS/grad; per-seed ratios cell by cell (same seed, same starts).", "",
          "| model | gates | da ESS/grad x1e3 | sfmed / da | sfmed per seed | sfstan / da | sfstan per seed | h da | h sfmed | h sfstan | max R-hat da / sfmed / sfstan |",
          "|---|---|---:|---:|---|---:|---|---:|---:|---:|---|"]
    for m in models:
        pd, ps, pt = (decision[a]["per_model"][m] for a in ARMS)
        seeds_s = lambda p: ", ".join(f"{v:.2f}" for v in p["per_seed_ratio_vs_da"].values())  # noqa: E731
        L.append(f"| {m} | {pd['gates']}/{ps['gates']}/{pt['gates']} | {f(pd['ess_per_gradient_x1e3'], '.3f')} | {f(ps['ratio_vs_da'], '.2f')} | {seeds_s(ps)} | "
                 f"{f(pt['ratio_vs_da'], '.2f')} | {seeds_s(pt)} | {f(pd['median_step'], '.3g')} | {f(ps['median_step'], '.3g')} | {f(pt['median_step'], '.3g')} | "
                 f"{f(pd['max_rank_rhat'], '.3f')} / {f(ps['max_rank_rhat'], '.3f')} / {f(pt['max_rank_rhat'], '.3f')} |")
    L += ["", "## Installed metric (mechanism)", "",
          "Installed variance = 1 / mass entry at the end of warmup; posterior variance = variance of the cell's retained "
          "unconstrained draws. `inst/post` = median over the 12 chains (3 seeds x 4) per coordinate; the range is the "
          "min..max over coordinates of that median. `vs da` = per-coordinate ratio of the median installed variance to "
          "`da`'s, min..max over coordinates.", "",
          "| model | dim | da inst/post | sfmed inst/post | sfstan inst/post | sfmed vs da | sfstan vs da |", "|---|---:|---|---|---|---|---|"]
    rng = lambda xs: f"{min(xs):.3g}..{max(xs):.3g}" if xs else "—"  # noqa: E731
    for m in models:
        row = mech.get(m, {})
        if BASELINE not in row:
            continue
        dim = len(row[BASELINE]["installed_variance_median"])
        L.append(f"| {m} | {dim} | {rng(row[BASELINE]['installed_over_posterior_median'])} | "
                 f"{rng(row.get('sfmed', {}).get('installed_over_posterior_median', []))} | {rng(row.get('sfstan', {}).get('installed_over_posterior_median', []))} | "
                 f"{rng(row.get('sfmed', {}).get('installed_variance_vs_da', []))} | {rng(row.get('sfstan', {}).get('installed_variance_vs_da', []))} |")
    for m in PROTOCOL["mechanism_models"]:
        row = mech.get(m, {})
        if BASELINE not in row:
            continue
        L += ["", f"### {m}: per coordinate (unconstrained), medians over 12 chains", "",
              "| coord | posterior var | da installed | sfmed installed | sfstan installed | da inst/post | sfmed inst/post | sfstan inst/post | da chain min..max | sfmed chain min..max | sfstan chain min..max |",
              "|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|"]
        for i in range(len(row[BASELINE]["installed_variance_median"])):
            cells_ = []
            for a in ARMS:
                r = row.get(a)
                cells_.append(r)
            L.append(f"| {i} | {row[BASELINE]['posterior_variance_median'][i]:.3g} | "
                     + " | ".join(f"{r['installed_variance_median'][i]:.3g}" if r else "—" for r in cells_) + " | "
                     + " | ".join(f"{r['installed_over_posterior_median'][i]:.3g}" if r else "—" for r in cells_) + " | "
                     + " | ".join(f"{r['installed_variance_min_chain'][i]:.3g}..{r['installed_variance_max_chain'][i]:.3g}" if r else "—" for r in cells_) + " |")
    L += ["", "## Funnel tail mass P(omega < -5) at the sampler defaults with each arm (exact 0.0478), 4 x 2,000 / 20,000 per seed", "",
          "| arm | seed | estimate | MCSE z (gate) | batch-means z | omega bulk ESS / R-hat | omega ESS/call x1e3 | target calls | divergences | retained exhaustions | final h | omega mass per chain |",
          "|---|---|---:|---:|---:|---|---:|---:|---:|---:|---|---|"]
    for arm in ARMS:
        for seed, p in funnel.get(arm, {}).get("per_seed", {}).items():
            L.append(f"| {arm} | {seed} | {p['estimate']:.4f} | {p['z']:+.2f} | {p['z_batch_means']:+.2f} | {p['omega_bulk_ess']:.0f} / {p['omega_rhat']:.3f} | "
                     f"{p['omega_bulk_ess_per_call'] * 1e3:.3f} | {p['target_calls_total']:,} | {p['divergences']} | {p['refinement_exhaustions']} | "
                     f"{', '.join(f'{x:.3g}' for x in p['final_step_size'])} | {', '.join(f'{md[0]:.3g}' for md in p['mass_diagonal'])} |")
    L += ["", "## Decision rule (flip iff geomean >= 1.10x da over 17 models, no model < 0.85x, gates >= da, funnel |z| <= 2 on every seed)", "",
          "| arm | C1 geomean >= 1.10 | C2 min >= 0.85 | C3 gates >= da | C4 funnel | all held |", "|---|---|---|---|---|---|"]
    for arm, c in rule.items():
        L.append(f"| {arm} | {f(c['C1_geomean_ge']['value'], '.3f')} ({c['C1_geomean_ge']['held']}) | {f(c['C2_no_model_below']['value'], '.2f')} {c['C2_no_model_below']['argmin']} ({c['C2_no_model_below']['held']}) | "
                 f"{c['C3_gates_ge_da']['value']} vs {c['C3_gates_ge_da']['da']} ({c['C3_gates_ge_da']['held']}) | {', '.join(f'{z:+.2f}' for z in c['C4_funnel_abs_z_le_2']['value'])} ({c['C4_funnel_abs_z_le_2']['held']}) | **{c['all_held']}** |")
    L += ["", f"Arms meeting the rule: {', '.join(flip) or 'none'}; recommendation: "
          + (f"flip the default to {flip[0]}." if flip else "keep `DiagonalMetricRegularization::Stan`.")]
    (ART / "results-table.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] == "run":
        models, arms = PROTOCOL["models"], ARMS
        for a in args[1:]:
            if a.startswith("--models="):
                models = a.split("=", 1)[1].split(",")
            elif a.startswith("--arms="):
                arms = a.split("=", 1)[1].split(",")
        run_all(models, arms)
    elif args[0] == "build":
        models = PROTOCOL["models"]
        for a in args[1:]:
            if a.startswith("--models="):
                models = a.split("=", 1)[1].split(",")
        build_all(models)
    elif args[0] == "cell":
        run_model_arm(args[1], args[2])
    elif args[0] == "checks":
        run_checks(ARMS)
    elif args[0] == "analyze":
        analyze()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
