#!/usr/bin/env python3
"""posteriordb benchmark v5 driver (the v3 protocol on the post-WP31 sampler defaults, fresh seeds, three arms).

    python run_posteriordb.py run              # every model/arm/seed in protocol order (resumable)
    python run_posteriordb.py run --models=a,b --arms=owalnuts-da,nutpie
    python run_posteriordb.py cell <model> <arm>   # one model/arm, all seeds (used as a child process)
    python run_posteriordb.py checks           # the funnel tail-mass row at the sampler defaults, three seeds
    python run_posteriordb.py analyze          # artifacts/summary.json + results-table.md

Each cell writes `artifacts/cells/<model>-<arm>-<seed>.json` (metrics, no draws)
and `artifacts/draws/<model>-<arm>-<seed>.npz` (constrained draws on the
reference parameter set). Failures are recorded as cells with status != "ok".
"""
from __future__ import annotations

import json
import math
import os
import platform
import re
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
CMDSTAN_MODELS = MODELS / "cmdstan"
PDB_PATH = HERE / PROTOCOL["posteriordb"]["path"]
CMDSTAN_HOME = Path(r"C:\dev\polyscope\STUDIES\matched_competitor_eight_schools_v38\cmdstan\cmdstan-2.39.0")
HARNESS = HERE / "target" / "release" / "posteriordb-bench-v5.exe"
FUNNEL = HERE / "target" / "release" / "funnel.exe"
ARMS = ["owalnuts-da", "cmdstan", "nutpie"]
OWALNUTS_MODE = {"owalnuts-da": "da"}
V3_SUMMARY = HERE.parent / "posteriordb_bench_v3" / "artifacts" / "summary.json"
V3_ARMS = {"owalnuts-da": "owalnuts-da", "cmdstan": "cmdstan", "nutpie": "nutpie"}
FUNNEL_SEEDS = PROTOCOL["funnel"]["seeds"]
SEEDS = PROTOCOL["seeds"]
TIMEOUT = PROTOCOL["cell_timeout_seconds"]
os.environ.setdefault("MAKE", "mingw32-make")
# BridgeStan make arguments: no STAN_THREADS (v1 wall-gap finding: on mingw-w64
# GCC it costs 9-16x per gradient). The harness loads one library copy per chain
# thread (ReplicatedStanTarget). The compiled libraries are the v4 worktree's
# (copied; same BridgeStan 2.9.0 / Stan 2.39.0 / flags, no STAN_THREADS); a missing one is compiled here.
BRIDGESTAN_MAKE_ARGS: list[str] = []


def short(model: str) -> str:
    return model.replace("-", "__")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------- posteriordb


def posterior(model: str):
    from posteriordb import PosteriorDatabase

    return PosteriorDatabase(str(PDB_PATH)).posterior(model)


def stan_name(var: str, idx: tuple[int, ...]) -> str:
    return var if not idx else f"{var}[{','.join(str(i + 1) for i in idx)}]"


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


def prepare_cmdstan(model: str):
    import cmdstanpy

    cmdstanpy.set_cmdstan_path(str(CMDSTAN_HOME))
    CMDSTAN_MODELS.mkdir(parents=True, exist_ok=True)
    stan = CMDSTAN_MODELS / f"{short(model)}.stan"
    if not stan.exists():
        shutil.copyfile(posterior(model).model.code_file_path("stan"), stan)
    t = time.perf_counter()
    m = cmdstanpy.CmdStanModel(stan_file=str(stan))
    log(f"cmdstan model ready {model} in {time.perf_counter() - t:.1f}s")
    return m


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
        "schema": "posteriordb-bench-v5-cell-metrics",
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
        "min_bulk_ess_per_second_sampling": min_bulk / wall_sampling,
        "min_tail_ess_per_second_sampling": min_tail / wall_sampling,
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
        "schema": "posteriordb-bench-v5-cell-metrics", "model": model, "arm": arm, "seed": seed,
        "status": status, "error": message, "passed": False,
        "gates": {"no_sampler_error": False}, **extra,
    }


def write_cell(cell: dict) -> None:
    CELLS.mkdir(parents=True, exist_ok=True)
    path = CELLS / f"{short(cell['model'])}-{cell['arm']}-{cell['seed']}.json"
    path.write_text(json.dumps(cell, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    s = cell["status"]
    if s == "ok":
        log(f"  {cell['arm']} {cell['seed']}: wall {cell['wall_seconds']:.2f}s grads {cell['gradients_total']} "
            f"minbulk {cell['min_bulk_ess']:.0f} mintail {cell['min_tail_ess']:.0f} rhat {cell['max_rank_rhat']:.4f} "
            f"div {cell['divergences']} max|z| {cell['max_abs_z']:.2f} passed {cell['passed']}")
    else:
        log(f"  {cell['arm']} {cell['seed']}: {s}: {cell.get('error', '')[:200]}")


def save_draws(model: str, arm: str, seed: int, draws: np.ndarray, names: list[str], **more) -> None:
    DRAWS.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(DRAWS / f"{short(model)}-{arm}-{seed}.npz", draws=draws, names=np.asarray(names), **more)


# --------------------------------------------------------------------------- arms


def run_owalnuts(model: str, arm: str, seed: int, ref: dict) -> dict:
    import bridgestan as bs

    so, data = prepare_bridgestan(model)
    mode = OWALNUTS_MODE[arm]
    raw = DRAWS / f"{short(model)}-{arm}-{seed}.raw.json"
    DRAWS.mkdir(parents=True, exist_ok=True)
    if raw.exists():
        raw.unlink()
    cmd = [str(HARNESS), str(so), str(data), mode, str(seed), str(raw), "4"]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return failure(model, arm, seed, "timeout", f"exceeded {TIMEOUT}s")
    if cp.returncode != 0 or not raw.exists():
        msg = cp.stderr.strip()[-2000:]
        return failure(model, arm, seed, "error", msg)
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
    extra = {
        "final_step_size": [c["final_step_size"] for c in chains],
        "final_max_error": [c["final_max_error"] for c in chains],
        "invalid_stops": sum(c["invalid_stops"] for c in chains),
        "refinement_exhaustions": sum(c["refinement_exhaustions"] for c in chains),
        "recoverable_failures_total": out["recoverable_failures_total"],
        "refinement_exhaustions_per_chain": [c["refinement_exhaustions"] for c in chains],
        "frozen_chains": sum(1 for c in chains if c["refinement_exhaustions"] > out["retained"] // 2),
        "start_search_calls": out["init"]["start_search_calls"],
        "tuning": out["tuning"],
        "warmup_config": out["warmup_config"],
        "warmup_exhaustion_rule": out["warmup_config"].get("warmup_exhaustion_rule"),
        "metric_regularization": out["warmup_config"].get("metric_regularization"),
        "u_turn": out["tuning"].get("u_turn"),
        "max_refinement_levels": out["tuning"]["max_refinement_levels"],
        "mass_diagonal_max": [max(c["mass_diagonal"]) for c in chains],
        "mass_diagonal_min": [min(c["mass_diagonal"]) for c in chains],
        "warmup_divergences": sum(c["warmup_divergences"] for c in chains),
        "retained_depth_histogram": [sum(x) for x in zip(*(c["retained_depth_histogram"] for c in chains))],
        "retained_refinement_level_histogram": [sum(x) for x in zip(*(c["retained_refinement_level_histogram"] for c in chains))],
        "paper_adaptation_updates": [len(c["paper_adaptation_updates"]) for c in chains],
        "algorithm_revision": out["algorithm_revision"],
        "paper_adaptation_revision": out["paper_adaptation_revision"],
        "unconstrained_dimension": out["dimension"],
    }
    cell = metrics(model, arm, seed, draws, ref["names"], ref, out["wall_seconds"], grads_total, grads_sampling,
                   sum(c["divergences"] for c in chains), sum(c["maximum_depth_stops"] for c in chains), extra)
    save_draws(model, arm, seed, draws, ref["names"], unconstrained=unc)
    return cell


def run_cmdstan(model: str, seed: int, ref: dict, m) -> dict:
    p = posterior(model)
    outdir = ART / "cmdstan-output" / f"{short(model)}-{seed}"
    if outdir.exists():
        shutil.rmtree(outdir)
    outdir.mkdir(parents=True)
    t = time.perf_counter()
    fit = m.sample(data=p.data.values(), chains=4, seed=seed, iter_warmup=1000, iter_sampling=1000,
                   save_warmup=True, show_progress=False, show_console=False, output_dir=str(outdir))
    wall = time.perf_counter() - t
    cols = list(fit.column_names)
    all_draws = np.asarray(fit.draws(inc_warmup=True))  # (draws, chains, cols)
    col = {n: i for i, n in enumerate(cols)}
    n_warm = all_draws.shape[0] - 1000
    leap = all_draws[:, :, col["n_leapfrog__"]]
    grads_total = int(leap.sum())
    grads_sampling = int(leap[n_warm:].sum())
    div = int(all_draws[n_warm:, :, col["divergent__"]].sum())
    depth = int((all_draws[n_warm:, :, col["treedepth__"]] >= 10).sum())
    missing = [n for n in ref["names"] if n not in col]
    if missing:
        return failure(model, "cmdstan", seed, "error", f"reference parameters missing from CSV: {missing[:5]}")
    draws = np.transpose(all_draws[n_warm:, :, [col[n] for n in ref["names"]]], (1, 0, 2))
    elapsed = []
    for f in fit.runset.csv_files:
        text = Path(f).read_text(encoding="utf-8", errors="replace")
        w = re.search(r"Elapsed Time:\s*([0-9.]+) seconds \(Warm-up\)", text)
        s = re.search(r"\s([0-9.]+) seconds \(Sampling\)", text)
        elapsed.append({"warmup": float(w.group(1)) if w else None, "sampling": float(s.group(1)) if s else None})
    extra = {"cmdstan_elapsed_per_chain": elapsed,
             "step_size": [float(x) for x in np.asarray(fit.step_size).ravel()]}
    cell = metrics(model, "cmdstan", seed, draws, ref["names"], ref, wall, grads_total, grads_sampling, div, depth, extra)
    save_draws(model, "cmdstan", seed, draws, ref["names"])
    return cell


def run_nutpie(model: str, seed: int, ref: dict, compiled) -> dict:
    import nutpie

    t = time.perf_counter()
    idata = nutpie.sample(compiled, draws=1000, tune=1000, chains=4, seed=seed, progress_bar=False, save_warmup=True)
    wall = time.perf_counter() - t
    post = idata.posterior
    flat: dict[str, np.ndarray] = {}
    for var in post.data_vars:
        arr = np.asarray(post[var])  # (chain, draw, ...)
        if arr.ndim == 2:
            flat[var] = arr
        else:
            for idx in np.ndindex(arr.shape[2:]):
                flat[stan_name(var, idx)] = arr[(slice(None), slice(None)) + idx]
    missing = [n for n in ref["names"] if n not in flat]
    if missing:
        return failure(model, "nutpie", seed, "error", f"reference parameters missing from nutpie posterior: {missing[:5]}")
    draws = np.stack([flat[n] for n in ref["names"]], axis=-1)
    ss = idata.sample_stats
    wss = idata.warmup_sample_stats
    grads_sampling = int(np.asarray(ss.n_steps).sum())
    grads_total = grads_sampling + int(np.asarray(wss.n_steps).sum())
    div = int(np.asarray(ss.diverging).sum())
    depth = int(np.asarray(ss.maxdepth_reached).sum()) if "maxdepth_reached" in ss else int((np.asarray(ss.depth) >= 10).sum())
    extra = {"step_size": [float(x) for x in np.asarray(ss.step_size)[:, -1]]}
    cell = metrics(model, "nutpie", seed, draws, ref["names"], ref, wall, grads_total, grads_sampling, div, depth, extra)
    save_draws(model, "nutpie", seed, draws, ref["names"])
    return cell


# --------------------------------------------------------------------------- orchestration


def cell_path(model: str, arm: str, seed: int) -> Path:
    return CELLS / f"{short(model)}-{arm}-{seed}.json"


def run_model_arm(model: str, arm: str) -> None:
    """All seeds of one (model, arm) in this process."""
    ref = reference(model)
    if arm.startswith("owalnuts"):
        for seed in SEEDS:
            if cell_path(model, arm, seed).exists():
                continue
            try:
                cell = run_owalnuts(model, arm, seed, ref)
            except Exception as e:  # noqa: BLE001
                cell = failure(model, arm, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
            write_cell(cell)
    elif arm == "cmdstan":
        try:
            m = prepare_cmdstan(model)
        except Exception as e:  # noqa: BLE001
            for seed in SEEDS:
                if not cell_path(model, arm, seed).exists():
                    write_cell(failure(model, arm, seed, "compile_error", str(e)[-2000:]))
            return
        for seed in SEEDS:
            if cell_path(model, arm, seed).exists():
                continue
            try:
                cell = run_cmdstan(model, seed, ref, m)
            except Exception as e:  # noqa: BLE001
                cell = failure(model, arm, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
            write_cell(cell)
    elif arm == "nutpie":
        import nutpie

        p = posterior(model)
        try:
            t = time.perf_counter()
            compiled = nutpie.compile_stan_model(filename=p.model.code_file_path("stan")).with_data(**p.data.values())
            log(f"nutpie compiled {model} in {time.perf_counter() - t:.1f}s")
        except Exception as e:  # noqa: BLE001
            for seed in SEEDS:
                if not cell_path(model, arm, seed).exists():
                    write_cell(failure(model, arm, seed, "compile_error", str(e)[-2000:]))
            return
        for seed in SEEDS:
            if cell_path(model, arm, seed).exists():
                continue
            try:
                cell = run_nutpie(model, seed, ref, compiled)
            except Exception as e:  # noqa: BLE001
                cell = failure(model, arm, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
            write_cell(cell)
    else:
        raise SystemExit(f"unknown arm {arm}")


def run_all(models: list[str], arms: list[str]) -> None:
    ART.mkdir(exist_ok=True)
    machine = ART / "measured_on.json"
    if not machine.exists():
        machine.write_text(json.dumps({
            "platform": platform.platform(), "processor": platform.processor(),
            "cpu_count": os.cpu_count(), "python": sys.version.split()[0],
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "note": "shared machine; other agents may run concurrently; walls are upper bounds",
        }, indent=2) + "\n", encoding="utf-8")
    for model in models:
        log(f"== {model}")
        try:
            prepare_bridgestan(model)
        except Exception as e:  # noqa: BLE001
            log(f"bridgestan compile failed for {model}: {str(e)[-500:]}")
            for arm in arms:
                if arm.startswith("owalnuts"):
                    for seed in SEEDS:
                        if not cell_path(model, arm, seed).exists():
                            write_cell(failure(model, arm, seed, "compile_error", str(e)[-2000:]))
        for arm in arms:
            if all(cell_path(model, arm, s).exists() for s in SEEDS):
                continue
            if arm.startswith("owalnuts") and not (MODELS / f"{short(model)}_model.so").exists():
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


# --------------------------------------------------------------------------- side check


def run_checks() -> None:
    """The funnel tail-mass row at the sampler defaults, every seed (resumable)."""
    fdir = ART / "funnel"
    fdir.mkdir(parents=True, exist_ok=True)
    for seed in FUNNEL_SEEDS:
        out = fdir / f"defaults-owalnuts-da-{seed}.json"
        if out.exists():
            continue
        log(f"funnel defaults {seed}")
        cp = subprocess.run([str(FUNNEL), str(seed), str(out)], capture_output=True, text=True)
        log(f"  {cp.stderr.strip()[-300:]}")


def analyze_funnel() -> dict:
    """Per seed: tail mass with the MCSE z (the gate) and the batch-means z; pooled batch-means estimate."""
    cells = []
    for seed in FUNNEL_SEEDS:
        path = ART / "funnel" / f"defaults-owalnuts-da-{seed}.json"
        if path.exists():
            cells.append(json.loads(path.read_text(encoding="utf-8")))
    entry = {"n_cells": len(cells), "per_seed": {}}
    means = []
    for c in cells:
        t = c["tail_mass"]
        entry["per_seed"][str(c["seed"])] = {
            "estimate": t["estimate"], "mcse": t["mcse"], "z": t["z"],
            "batch_means_se": t["batch_means_se"], "z_batch_means": t["z_batch_means"], "per_chain": t["per_chain"],
            "target_calls_total": c["target_calls_total"], "retained_target_calls": c["retained_target_calls"],
            "omega_bulk_ess": c["omega"]["bulk_ess"], "omega_tail_ess": c["omega"]["tail_ess"], "omega_rhat": c["omega"]["rhat"],
            "omega_variance": c["omega"]["variance"], "wall_seconds": c["wall_seconds"],
            "depth_caps": sum(ch["depth_caps"] for ch in c["chains_data"]),
            "divergences": sum(ch["divergences"] for ch in c["chains_data"]),
            "refinement_exhaustions": sum(ch["refinement_exhaustions"] for ch in c["chains_data"]),
            "final_step_size": [ch["final_step_size"] for ch in c["chains_data"]],
            "u_turn": c.get("u_turn"), "metric_regularization": c.get("metric_regularization"),
        }
        means.extend(c["batch_means"])
    zs = [p["z"] for p in entry["per_seed"].values()]
    entry["all_seeds_abs_z_le_2"] = bool(len(zs) == len(FUNNEL_SEEDS) and all(abs(z) <= 2.0 for z in zs))
    entry["max_abs_z"] = max((abs(z) for z in zs), default=None)
    if means:
        arr = np.asarray(means)
        est = float(arr.mean())
        se = float(arr.std(ddof=1) / math.sqrt(len(arr)))
        exact = cells[0]["tail_mass"]["exact"]
        entry["pooled"] = {"estimate": est, "batch_means_se": se, "z_batch_means": (est - exact) / se, "batches": int(len(arr)), "exact": exact}
    return entry


# --------------------------------------------------------------------------- analysis


def geomean(xs: list[float]) -> float:
    xs = [x for x in xs if x and math.isfinite(x) and x > 0]
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs))) if xs else float("nan")


def analyze() -> None:
    models = PROTOCOL["models"]
    cells = {}
    for path in sorted(CELLS.glob("*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        c.pop("parameters", None)
        if c.get("status") == "ok" and c.get("gradients_total"):
            c["wall_per_gradient_us"] = 1e6 * c["wall_seconds"] / c["gradients_total"]
        cells.setdefault(c["model"], {}).setdefault(c["arm"], {})[str(c["seed"])] = c
    keys = ["min_bulk_ess_per_second", "min_tail_ess_per_second", "min_bulk_ess_per_second_sampling",
            "min_bulk_ess_per_gradient", "min_tail_ess_per_gradient", "min_bulk_ess_per_gradient_sampling",
            "wall_seconds", "gradients_total", "min_bulk_ess", "min_tail_ess", "max_rank_rhat", "max_abs_z",
            "wall_per_gradient_us", "max_depth_stops"]
    per_model = {}
    for model in models:
        row = {}
        for arm in ARMS:
            seeds = cells.get(model, {}).get(arm, {})
            ok = [c for c in seeds.values() if c.get("status") == "ok"]
            entry = {"n_cells": len(seeds), "n_ok": len(ok), "n_passed": sum(1 for c in ok if c["passed"]),
                     "statuses": {s: c.get("status") for s, c in seeds.items()},
                     "errors": {s: c.get("error", "")[:300] for s, c in seeds.items() if c.get("status") != "ok"},
                     "divergences": [c["divergences"] for c in ok],
                     "max_depth_stops": [c["max_depth_stops"] for c in ok],
                     "frozen_chains": [c.get("frozen_chains", 0) for c in ok],
                     "n_frozen_cells": sum(1 for c in ok if c.get("frozen_chains", 0) > 0),
                     "final_step_size": [c.get("final_step_size") for c in ok],
                     "u_turn": sorted({c.get("u_turn") for c in ok if c.get("u_turn")}),
                     "metric_regularization": sorted({c.get("metric_regularization") for c in ok if c.get("metric_regularization")}),
                     "agreement_flags": sum(1 for c in ok if c["agreement_flag"])}
            for k in keys:
                vals = [c[k] for c in ok if k in c and c[k] is not None and math.isfinite(c[k])]
                entry[k] = {"median": statistics.median(vals) if vals else None,
                            "min": min(vals) if vals else None, "max": max(vals) if vals else None, "values": vals}
            row[arm] = entry
        per_model[model] = row

    # Head-to-head vs competitors on ESS/gradient and ESS/s (seed medians, models where both ok on all seeds).
    head = {}
    for arm in ("cmdstan", "nutpie"):
        for ours in ("owalnuts-da",):
            ms = [m for m in models if per_model[m][arm]["n_ok"] == len(SEEDS) and per_model[m][ours]["n_ok"] == len(SEEDS)]
            head[f"{ours}_over_{arm}"] = {
                "models": ms,
                "geomean_wall_per_gradient": geomean([per_model[m][ours]["wall_per_gradient_us"]["median"] / per_model[m][arm]["wall_per_gradient_us"]["median"] for m in ms]),
                "wins_gates": sum(1 for m in ms if per_model[m][ours]["n_passed"] > per_model[m][arm]["n_passed"]),
                "wins_outright": [m for m in ms if per_model[m][ours]["n_passed"] >= per_model[m][arm]["n_passed"] and per_model[m][ours]["min_bulk_ess_per_gradient"]["median"] > per_model[m][arm]["min_bulk_ess_per_gradient"]["median"] and per_model[m][ours]["min_bulk_ess_per_second"]["median"] > per_model[m][arm]["min_bulk_ess_per_second"]["median"]],
                "geomean_bulk_ess_per_gradient": geomean([per_model[m][ours]["min_bulk_ess_per_gradient"]["median"] / per_model[m][arm]["min_bulk_ess_per_gradient"]["median"] for m in ms]),
                "geomean_bulk_ess_per_second": geomean([per_model[m][ours]["min_bulk_ess_per_second"]["median"] / per_model[m][arm]["min_bulk_ess_per_second"]["median"] for m in ms]),
                "wins_bulk_ess_per_second": sum(1 for m in ms if per_model[m][ours]["min_bulk_ess_per_second"]["median"] > per_model[m][arm]["min_bulk_ess_per_second"]["median"]),
                "wins_bulk_ess_per_gradient": sum(1 for m in ms if per_model[m][ours]["min_bulk_ess_per_gradient"]["median"] > per_model[m][arm]["min_bulk_ess_per_gradient"]["median"]),
            }
    # v3 -> v5 comparison (seed medians; identical protocol and competitor versions; the only sampler change in the
    # DA arm is the post-WP31 default pair; cmdstan and nutpie differ by seed noise only).
    v3 = json.loads(V3_SUMMARY.read_text(encoding="utf-8"))["per_model"] if V3_SUMMARY.exists() else {}
    versus_v3 = {}
    for model in models:
        row = {}
        for arm, v3arm in V3_ARMS.items():
            a, b = per_model[model][arm], v3.get(model, {}).get(v3arm, {})

            def r(k, a=a, b=b):
                x = a[k]["median"]
                y = (b.get(k) or {}).get("median")
                return (x / y) if (x and y) else None
            row[arm] = {"v3_passed": b.get("n_passed"), "v5_passed": a["n_passed"], "v3_ok": b.get("n_ok"), "v5_ok": a["n_ok"],
                        "r_bulk_ess_per_gradient": r("min_bulk_ess_per_gradient"), "r_bulk_ess_per_second": r("min_bulk_ess_per_second"),
                        "r_wall": r("wall_seconds"), "r_gradients": r("gradients_total"),
                        "v3_bulk_ess_per_gradient": (b.get("min_bulk_ess_per_gradient") or {}).get("median"),
                        "v5_bulk_ess_per_gradient": a["min_bulk_ess_per_gradient"]["median"]}
        versus_v3[model] = row
    versus_v3_overall = {arm: {
        "models": [m for m in models if versus_v3[m][arm]["r_bulk_ess_per_gradient"]],
        "geomean_r_bulk_ess_per_gradient": geomean([versus_v3[m][arm]["r_bulk_ess_per_gradient"] for m in models]),
        "geomean_r_bulk_ess_per_second": geomean([versus_v3[m][arm]["r_bulk_ess_per_second"] for m in models]),
        "geomean_r_gradients": geomean([versus_v3[m][arm]["r_gradients"] for m in models]),
        "v3_cells_passed": sum((versus_v3[m][arm]["v3_passed"] or 0) for m in models),
        "v5_cells_passed": sum(versus_v3[m][arm]["v5_passed"] for m in models),
    } for arm in V3_ARMS}
    # v5 DA against the v3 competitors (the reference WP31 cited): orientation only.
    v3_cross = {}
    for arm in ("cmdstan", "nutpie"):
        ms = [m for m in models if per_model[m]["owalnuts-da"]["n_ok"] == len(SEEDS) and (v3.get(m, {}).get(arm, {}).get("n_ok") == len(SEEDS))]
        v3_cross[f"owalnuts-da_over_v3_{arm}"] = {
            "models": ms,
            "geomean_bulk_ess_per_gradient": geomean([per_model[m]["owalnuts-da"]["min_bulk_ess_per_gradient"]["median"] / v3[m][arm]["min_bulk_ess_per_gradient"]["median"] for m in ms]),
            "geomean_bulk_ess_per_second": geomean([per_model[m]["owalnuts-da"]["min_bulk_ess_per_second"]["median"] / v3[m][arm]["min_bulk_ess_per_second"]["median"] for m in ms]),
        }
    funnel = analyze_funnel()
    da_cells = [c for m in models for c in cells.get(m, {}).get("owalnuts-da", {}).values()]
    fatal = [f"{c['model']}/{c['arm']}/{c['seed']}: {c.get('error', '')[:120]}" for m in models for arm in ARMS if arm.startswith("owalnuts")
             for c in cells.get(m, {}).get(arm, {}).values() if c.get("status") != "ok"]
    da_frozen = [f"{m}/{s}" for m in models for s, c in cells.get(m, {}).get("owalnuts-da", {}).items() if c.get("frozen_chains", 0) > 0]
    hc = head["owalnuts-da_over_cmdstan"]
    hn = head["owalnuts-da_over_nutpie"]
    regressed = {m: versus_v3[m]["owalnuts-da"]["r_bulk_ess_per_gradient"] for m in models
                 if versus_v3[m]["owalnuts-da"]["r_bulk_ess_per_gradient"] is not None and versus_v3[m]["owalnuts-da"]["r_bulk_ess_per_gradient"] < 0.8}
    improved = {m: versus_v3[m]["owalnuts-da"]["r_bulk_ess_per_gradient"] for m in models
                if versus_v3[m]["owalnuts-da"]["r_bulk_ess_per_gradient"] is not None and versus_v3[m]["owalnuts-da"]["r_bulk_ess_per_gradient"] > 1.2}
    n_pass = sum(1 for c in da_cells if c.get("passed"))
    fz = [p["z"] for p in funnel["per_seed"].values()]
    funnel_complete = len(fz) == len(FUNNEL_SEEDS)
    gates_by_arm = {arm: sum(per_model[m][arm]["n_passed"] for m in models) for arm in ARMS}
    predictions = {
        "P1_da_gate_passes_ge_39_of_51": {"value": n_pass, "held": n_pass >= 39, "competitors": gates_by_arm},
        "P2_da_geomean_bulk_ess_per_gradient_vs_cmdstan_ge_0.45_over_17": {
            "value": hc["geomean_bulk_ess_per_gradient"], "models": len(hc["models"]),
            "held": bool(hc["geomean_bulk_ess_per_gradient"] >= 0.45) if len(hc["models"]) == len(models) else None},
        "P3_da_geomean_bulk_ess_per_second_vs_nutpie_ge_1.5": {
            "value": hn["geomean_bulk_ess_per_second"], "models": len(hn["models"]),
            "held": bool(hn["geomean_bulk_ess_per_second"] >= 1.5)},
        "P4_da_geomean_wall_per_gradient_le_1.0x_cmdstan": {"value": hc["geomean_wall_per_gradient"], "held": bool(hc["geomean_wall_per_gradient"] <= 1.0)},
        "P5_funnel_defaults_abs_z_le_2_every_seed": {"value": fz, "held": (all(abs(z) <= 2.0 for z in fz) if funnel_complete else None)},
        "reported_da_v5_over_v3_geomean_bulk_ess_per_gradient": {"value": versus_v3_overall["owalnuts-da"]["geomean_r_bulk_ess_per_gradient"]},
        "reported_da_models_below_0.8x_v3": {"value": regressed},
        "reported_da_models_above_1.2x_v3": {"value": improved},
        "reported_competitor_v5_over_v3_geomean_bulk_ess_per_gradient": {"value": {arm: versus_v3_overall[arm]["geomean_r_bulk_ess_per_gradient"] for arm in ("cmdstan", "nutpie")}},
        "reported_da_frozen_cells": {"value": da_frozen},
        "reported_owalnuts_cells_not_ok": {"value": fatal},
    }
    summary = {
        "schema": "posteriordb-bench-v5-summary",
        "versus_v3": versus_v3,
        "versus_v3_overall": versus_v3_overall,
        "da_versus_v3_competitors": v3_cross,
        "funnel": funnel,
        "predictions": predictions,
        "protocol_sha256": __import__("hashlib").sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "per_model": per_model,
        "head_to_head": head,
        "cells": cells,
    }
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    def f(x, fmt):
        return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)

    lines = ["# posteriordb benchmark v5 — results", "",
             "Seed medians over 3 seeds of the per-cell minimum over parameters; `gates` = cells passing "
             "R-hat <= 1.01, bulk/tail ESS >= 400, zero divergences; `div` = sampling divergences summed over "
             "chains per seed; `max|z|` = worst posterior-mean z against the posteriordb reference.", "",
             "| model | arm | gates | wall s | grads | min bulk ESS | min tail ESS | bulk ESS/s | tail ESS/s | bulk ESS/grad x1e3 | max R-hat | div | max abs z |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|"]
    for model in models:
        for arm in ARMS:
            e = per_model[model][arm]
            status = f"{e['n_passed']}/{e['n_cells']}" if e["n_ok"] else "/".join(sorted(set(e["statuses"].values()))) or "not run"
            lines.append(
                f"| {model} | {arm} | {status} | {f(e['wall_seconds']['median'], '.2f')} | {f(e['gradients_total']['median'], ',.0f')} | "
                f"{f(e['min_bulk_ess']['median'], ',.0f')} | {f(e['min_tail_ess']['median'], ',.0f')} | "
                f"{f(e['min_bulk_ess_per_second']['median'], ',.1f')} | {f(e['min_tail_ess_per_second']['median'], ',.1f')} | "
                f"{f((e['min_bulk_ess_per_gradient']['median'] or float('nan')) * 1e3, '.3f')} | {f(e['max_rank_rhat']['median'], '.4f')} | "
                f"{','.join(str(d) for d in e['divergences'])} | {f(e['max_abs_z']['median'], '.2f')} |")
    lines += ["",
              "## Head-to-head (geometric mean of seed-median ratios over models complete on both sides)", "",
              "| comparison | models | bulk ESS/grad ratio | bulk ESS/s ratio | wall/grad ratio | wins ESS/s | wins ESS/grad | wins outright (gates >=, ESS/grad >, ESS/s >) |", "|---|---:|---:|---:|---:|---:|---:|---|"]
    for k, h in head.items():
        lines.append(f"| {k} | {len(h['models'])} | {f(h['geomean_bulk_ess_per_gradient'], '.3f')} | {f(h['geomean_bulk_ess_per_second'], '.3f')} | {f(h['geomean_wall_per_gradient'], '.3f')} | {h['wins_bulk_ess_per_second']} | {h['wins_bulk_ess_per_gradient']} | {', '.join(h['wins_outright']) or 'none'} |")
    lines += ["", "## Per-model final steps and depth caps (owalnuts-da; per seed)", "",
              "| model | final step per chain (seed 1 / 2 / 3) | depth caps per seed | divergences per seed |", "|---|---|---|---|"]
    for model in models:
        e = per_model[model]["owalnuts-da"]
        steps = " / ".join("[" + ", ".join(f"{x:.3g}" for x in st) + "]" for st in e["final_step_size"] if st)
        lines.append(f"| {model} | {steps} | {','.join(str(d) for d in e['max_depth_stops']['values'])} | {','.join(str(d) for d in e['divergences'])} |")
    lines += ["", "## v5 versus v3 (seed medians; ratio v5 / v3; same protocol, competitor versions and settings, seeds 79101-79103 -> 87101-87103; the only sampler change is the post-WP31 default pair in the DA arm; cmdstan and nutpie differ by seed noise)", "",
              "| model | arm | v3 gates | v5 gates | v3 ESS/grad x1e3 | v5 ESS/grad x1e3 | ESS/grad v5/v3 | ESS/s v5/v3 | wall v5/v3 | grads v5/v3 |", "|---|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for model in models:
        for arm in V3_ARMS:
            v = versus_v3[model][arm]
            lines.append(f"| {model} | {arm} | {v['v3_passed']}/3 | {v['v5_passed']}/3 | {f((v['v3_bulk_ess_per_gradient'] or float('nan')) * 1e3, '.3f')} | "
                         f"{f((v['v5_bulk_ess_per_gradient'] or float('nan')) * 1e3, '.3f')} | {f(v['r_bulk_ess_per_gradient'], '.2f')} | {f(v['r_bulk_ess_per_second'], '.2f')} | {f(v['r_wall'], '.2f')} | {f(v['r_gradients'], '.2f')} |")
    lines += ["", "| arm | v3 cells passed | v5 cells passed | geomean ESS/grad v5/v3 | geomean ESS/s v5/v3 | geomean grads v5/v3 |", "|---|---:|---:|---:|---:|---:|"]
    for arm, o in versus_v3_overall.items():
        lines.append(f"| {arm} | {o['v3_cells_passed']} | {o['v5_cells_passed']} | {f(o['geomean_r_bulk_ess_per_gradient'], '.2f')} | {f(o['geomean_r_bulk_ess_per_second'], '.2f')} | {f(o['geomean_r_gradients'], '.2f')} |")
    lines += ["", "| v5 owalnuts-da against the v3 competitor medians (orientation; WP31 cited these) | models | ESS/grad ratio | ESS/s ratio |", "|---|---:|---:|---:|"]
    for k, h in v3_cross.items():
        lines.append(f"| {k} | {len(h['models'])} | {f(h['geomean_bulk_ess_per_gradient'], '.3f')} | {f(h['geomean_bulk_ess_per_second'], '.3f')} |")
    lines += ["", "## Funnel tail mass P(omega < -5) at the sampler defaults (exact 0.0478), 4 x 2,000 / 20,000 per seed", "",
              "| seed | estimate | MCSE z (gate) | batch-means z | omega bulk ESS / R-hat | target calls | divergences | retained exhaustions | final steps |", "|---|---:|---:|---:|---|---:|---:|---:|---|"]
    for seed, p in funnel["per_seed"].items():
        lines.append(f"| {seed} | {p['estimate']:.4f} | {p['z']:+.2f} | {p['z_batch_means']:+.2f} | {p['omega_bulk_ess']:.0f} / {p['omega_rhat']:.3f} | {p['target_calls_total']:,} | {p['divergences']} | {p['refinement_exhaustions']} | {', '.join(f'{x:.3g}' for x in p['final_step_size'])} |")
    if "pooled" in funnel:
        po = funnel["pooled"]
        lines.append(f"| pooled (batch means) | {po['estimate']:.4f} | — | {po['z_batch_means']:+.2f} | — | — | — | — | — |")
    lines += ["", "## Preregistered predictions", "", "| prediction | value | held |", "|---|---|---|"]
    for k, v in predictions.items():
        val = v["value"]
        lines.append(f"| {k} | {f(val, '.3f') if isinstance(val, float) else val} | {v.get('held', 'reported')} |")
    (ART / "results-table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


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
    elif args[0] == "cell":
        run_model_arm(args[1], args[2])
    elif args[0] == "checks":
        run_checks()
    elif args[0] == "analyze":
        analyze()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
