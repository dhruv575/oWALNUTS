#!/usr/bin/env python3
"""WP80 telemetry arm: oWALNUTS (telemetry harness) and nutpie (stored mass matrix and unconstrained draws)
on the four telemetry models x three seeds, with per-draw / per-transition diagnostics.

Derived from WP76's run_nutpie18.py (WP64's portable v7 driver); the cell code is v7's, plus the saving of
telemetry listed in AMENDMENTS.md. The analysis is analyze_gap.py.

    python run_telemetry.py run                        # models in order, owalnuts then nutpie, seeds ascending
    python run_telemetry.py cell <model> <arm> <seed>
"""
from __future__ import annotations

import functools
import hashlib
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
REPO = HERE.parent.parent
# WP64/WP76: the measurement constants (gates, timeout, reference rule) are v7's frozen protocol, read unchanged;
# the models (fixed 16), seeds (18) and platform note come from this study's protocol.json.
PROTOCOL = json.loads((HERE.parent / "posteriordb_bench_v7" / "protocol.json").read_text(encoding="utf-8"))
STUDY = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
IS_WINDOWS = os.name == "nt"
EXE = ".exe" if IS_WINDOWS else ""
# Smoke tests (non-evidence seeds, before the freeze) redirect output with V7_SMOKE_ART / V7_SMOKE_SEEDS.
ART = Path(os.environ["V7_SMOKE_ART"]) if os.environ.get("V7_SMOKE_ART") else HERE / "artifacts"
CELLS = ART / "cells"
DRAWS = ART / "draws"
MODELS = Path(os.environ.get("BENCH_MODELS", str(HERE / "models")))
CMDSTAN_MODELS = MODELS / "cmdstan"
NUTPIE_MODELS = MODELS / "nutpie"
PDB_PATH = Path(os.environ.get("POSTERIORDB_PATH", str(Path.home() / "infra" / "posteriordb" / "posterior_database")))
CMDSTAN_HOME = Path(os.environ.get("CMDSTAN_HOME", str(Path.home() / "infra" / "cmdstan" / "cmdstan-2.39.0")))
HARNESS = Path(os.environ.get("OWALNUTS_HARNESS", str(HERE / "target" / "release" / f"posteriordb-bench-v7{EXE}")))
FUNNEL = Path(os.environ.get("OWALNUTS_FUNNEL", str(HERE / "target" / "release" / f"funnel{EXE}")))
# The clean source tree (git worktree at the commit under test) that HARNESS and FUNNEL were built from.
SOURCE_TREE = Path(os.environ.get("OWALNUTS_SOURCE_TREE", str(REPO)))
COMMIT = STUDY["commit"]["full"]
ARMS = ["owalnuts", "cmdstan", "nutpie"]
DESCRIPTIVE_ARMS = ["owalnuts-dense"]
OWALNUTS_MODE = {"owalnuts": "defaults", "owalnuts-dense": "dense"}
DENSE_MODELS = PROTOCOL["descriptive_dense_arm"]["models"]
HOUSE = PROTOCOL["house_models"]
NEW = PROTOCOL["new_models"]
ALL_MODELS = HOUSE + NEW
FIXED16 = PROTOCOL["fixed_non_arma_models"]
FUNNEL_SEEDS = PROTOCOL["funnel"]["seeds"]
SEEDS = [int(x) for x in os.environ["V7_SMOKE_SEEDS"].split(",")] if os.environ.get("V7_SMOKE_SEEDS") else STUDY["telemetry"]["seeds"]
TELEMETRY = ART / "telemetry"
TIMEOUT = PROTOCOL["cell_timeout_seconds"]
PRIOR_SUMMARY = HERE.parent / "posteriordb_bench_v6" / "artifacts" / "summary.json"
PRIOR_ARMS = {"owalnuts": "owalnuts-da", "cmdstan": "cmdstan", "nutpie": "nutpie"}
if IS_WINDOWS:
    os.environ.setdefault("MAKE", "mingw32-make")


def short(model: str) -> str:
    return model.replace("-", "__")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------- Phase-2 guard


def preregistered() -> None:
    """WP64: no cell of any arm runs before PREREGISTRATION.md and protocol.json are committed."""
    if os.environ.get("V7_SMOKE_ART"):
        return
    for f in ("PREREGISTRATION.md", "protocol.json"):
        tracked = subprocess.run(["git", "-C", str(REPO), "ls-files", "--error-unmatch", str(HERE / f)],
                                 capture_output=True, text=True)
        changed = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "HEAD", "--", str(HERE / f)],
                                 capture_output=True, text=True)
        if tracked.returncode != 0 or changed.returncode != 0:
            raise SystemExit(f"{f} must be committed (and unmodified) before the first cell")


def amendment_commit() -> str:
    """The commit under test (WP64: fixed in protocol.json at the freeze, f097391c as v7's A1).
    Refuses to run unless this study's PREREGISTRATION.md and protocol.json are committed and the
    source tree the harness was built from is a clean checkout of that commit."""
    if os.environ.get("V7_SMOKE_ART"):
        return "smoke-test-not-evidence"
    preregistered()
    head = subprocess.run(["git", "-C", str(SOURCE_TREE), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if head != COMMIT:
        raise SystemExit(f"source tree {SOURCE_TREE} is at {head or '?'}, not the commit under test {COMMIT}")
    dirty = subprocess.run(["git", "-C", str(SOURCE_TREE), "diff", "--quiet", "HEAD", "--",
                            "src", "integrations", "Cargo.toml", "tests"], capture_output=True, text=True)
    if dirty.returncode != 0:
        raise SystemExit("uncommitted library changes in the source tree")
    if not HARNESS.exists():
        raise SystemExit(f"harness {HARNESS} missing")
    return COMMIT[:8]


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


def has_reference(model: str) -> bool:
    return model not in PROTOCOL["gates_only_models"]


def reference(model: str) -> dict | None:
    """Reference draws as (chains, draws, P) with column names and ArviZ summaries; None if gates-only."""
    if not has_reference(model):
        return None
    p = posterior(model)
    ref = p.reference_draws()
    names = list(ref[0].keys())
    arr = np.asarray([[c[n] for n in names] for c in ref], dtype=np.float64)  # (chains, P, draws)
    arr = np.transpose(arr, (0, 2, 1))
    return {"names": names, "draws": arr, **arviz_stats(arr)}


@functools.lru_cache(maxsize=None)
def bridgestan_model(model: str):
    import bridgestan as bs

    so, data = MODELS / f"{short(model)}_model.so", MODELS / f"{short(model)}.data.json"
    if IS_WINDOWS:
        bs.compile.windows_dll_path_setup()
    return bs.StanModel(str(so), data=data.read_text(encoding="utf-8"), seed=1)


def gate_names(model: str, ref: dict | None) -> list[str]:
    if ref is not None:
        return ref["names"]
    sm = bridgestan_model(model)
    return [bridgestan_name(n) for n in sm.param_names(include_tp=False, include_gq=False)]


def arviz_stats(arr: np.ndarray) -> dict:
    import arviz as az

    ds = az.convert_to_dataset({"p": arr})
    with np.errstate(all="ignore"):
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


# --------------------------------------------------------------------------- metrics


def chain_disagreement(draws: np.ndarray) -> dict:
    """max over chains and parameters of |chain mean - mean of other chains| / pooled sd (WP46)."""
    cm = draws.mean(1)
    pooled_sd = draws.reshape(-1, draws.shape[-1]).std(0, ddof=1)
    worst, worst_chain = 0.0, None
    for c in range(draws.shape[0]):
        others = np.delete(cm, c, axis=0).mean(0)
        with np.errstate(divide="ignore", invalid="ignore"):
            d = np.abs(cm[c] - others) / pooled_sd
        d = np.where(np.isfinite(d), d, 0.0)
        if d.size and d.max() > worst:
            worst, worst_chain = float(d.max()), c
    return {"max": worst, "chain": worst_chain}


def metrics(model: str, arm: str, seed: int, draws: np.ndarray, names: list[str], ref: dict | None,
            wall: float, grads_total: int, grads_sampling: int, divergences: int,
            max_depth_stops: int, extra: dict) -> dict:
    """draws: (chains, draws, P) on the gate parameter set (same order as names)."""
    st = arviz_stats(draws)
    finite = bool(np.isfinite(draws).all())
    min_bulk = float(np.nanmin(st["bulk_ess"]))
    min_tail = float(np.nanmin(st["tail_ess"]))
    max_rhat = float(np.nanmax(st["rhat"]))
    nan_stat_params = [names[i] for i in range(len(names))
                       if not (np.isfinite(st["bulk_ess"][i]) and np.isfinite(st["tail_ess"][i]) and np.isfinite(st["rhat"][i]))]
    wall_sampling = wall * grads_sampling / grads_total if grads_total else float("nan")
    gates = {
        "max_rank_rhat": max_rhat <= PROTOCOL["gates"]["max_rank_rhat"],
        "min_bulk_ess": min_bulk >= PROTOCOL["gates"]["min_bulk_ess"],
        "min_tail_ess": min_tail >= PROTOCOL["gates"]["min_tail_ess"],
        "sampling_divergences": divergences == 0,
        "finite_draws": finite,
        "no_sampler_error": True,
    }
    per_param = {}
    for i, n in enumerate(names):
        per_param[n] = {"mean": float(st["mean"][i]), "sd": float(st["sd"][i]), "mcse": float(st["mcse"][i]),
                        "bulk_ess": float(st["bulk_ess"][i]), "tail_ess": float(st["tail_ess"][i]),
                        "rhat": float(st["rhat"][i])}
    zinfo: dict = {"max_abs_z": None, "argmax_abs_z": None, "max_abs_dmean_over_ref_sd": None, "agreement_flag": None}
    if ref is not None:
        z = (st["mean"] - ref["mean"]) / np.sqrt(st["mcse"] ** 2 + ref["mcse"] ** 2)
        dsd = np.abs(st["mean"] - ref["mean"]) / ref["sd"]
        for i, n in enumerate(names):
            per_param[n].update({"ref_mean": float(ref["mean"][i]), "ref_sd": float(ref["sd"][i]),
                                 "ref_mcse": float(ref["mcse"][i]), "z": float(z[i]), "abs_dmean_over_ref_sd": float(dsd[i])})
        zinfo = {"max_abs_z": float(np.nanmax(np.abs(z))), "argmax_abs_z": names[int(np.nanargmax(np.abs(z)))],
                 "max_abs_dmean_over_ref_sd": float(np.nanmax(dsd)), "agreement_flag": bool(np.nanmax(np.abs(z)) > 4)}
    dis = chain_disagreement(draws)
    return {
        "schema": "posteriordb-bench-v7-cell-metrics",
        "model": model, "arm": arm, "seed": seed, "status": "ok",
        "tier": "reference" if ref is not None else "gates_only",
        "block": "house" if model in HOUSE else "new",
        "dimension_gate_params": len(names),
        "nan_statistic_params": nan_stat_params,
        "wall_seconds": wall,
        "wall_seconds_sampling_estimated": wall_sampling,
        "gradients_total": grads_total,
        "gradients_sampling": grads_sampling,
        "divergences": divergences,
        "max_depth_stops": max_depth_stops,
        "min_bulk_ess": min_bulk, "min_tail_ess": min_tail, "max_rank_rhat": max_rhat,
        "argmin_bulk_ess": names[int(np.nanargmin(st["bulk_ess"]))],
        "argmax_rank_rhat": names[int(np.nanargmax(st["rhat"]))],
        "min_bulk_ess_per_second": min_bulk / wall,
        "min_tail_ess_per_second": min_tail / wall,
        "min_bulk_ess_per_gradient": min_bulk / grads_total,
        "min_tail_ess_per_gradient": min_tail / grads_total,
        "min_bulk_ess_per_gradient_sampling": min_bulk / grads_sampling if grads_sampling else float("nan"),
        **zinfo,
        "chain_disagreement_max": dis["max"],
        "chain_disagreement_chain": dis["chain"],
        "gates": gates,
        "passed": all(gates.values()),
        "parameters": per_param,
        **extra,
    }


def failure(model: str, arm: str, seed: int, status: str, message: str, **extra) -> dict:
    return {
        "schema": "posteriordb-bench-v7-cell-metrics", "model": model, "arm": arm, "seed": seed,
        "block": "house" if model in HOUSE else "new",
        "status": status, "error": message, "passed": False,
        "gates": {"no_sampler_error": False}, **extra,
    }


def write_cell(cell: dict) -> None:
    CELLS.mkdir(parents=True, exist_ok=True)
    path = CELLS / f"{short(cell['model'])}-{cell['arm']}-{cell['seed']}.json"
    path.write_text(json.dumps(cell, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    s = cell["status"]
    if s == "ok":
        z = cell["max_abs_z"]
        log(f"  {cell['arm']} {cell['seed']}: wall {cell['wall_seconds']:.2f}s grads {cell['gradients_total']} "
            f"minbulk {cell['min_bulk_ess']:.0f} mintail {cell['min_tail_ess']:.0f} rhat {cell['max_rank_rhat']:.4f} "
            f"div {cell['divergences']} max|z| {'-' if z is None else f'{z:.2f}'} passed {cell['passed']}")
    else:
        log(f"  {cell['arm']} {cell['seed']}: {s}: {cell.get('error', '')[:200]}")


def save_draws(model: str, arm: str, seed: int, draws: np.ndarray, names: list[str], **more) -> None:
    DRAWS.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(DRAWS / f"{short(model)}-{arm}-{seed}.npz", draws=draws, names=np.asarray(names), **more)


# --------------------------------------------------------------------------- arms


def run_owalnuts(model: str, arm: str, seed: int, ref: dict | None, names: list[str]) -> dict:
    so, data = MODELS / f"{short(model)}_model.so", MODELS / f"{short(model)}.data.json"
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
        return failure(model, arm, seed, "error", cp.stderr.strip()[-2000:] or f"exit {cp.returncode} with no stderr")
    out = json.loads(raw.read_text(encoding="utf-8"))
    if out.get("status") != "ok":
        return failure(model, arm, seed, "error", out.get("error", "unknown"), wall_seconds=out.get("wall_seconds"))
    sm = bridgestan_model(model)
    include_tp = ref is not None
    cnames = [bridgestan_name(n) for n in sm.param_names(include_tp=include_tp, include_gq=False)]
    unc = np.asarray([c["samples"] for c in out["chains_data"]], dtype=np.float64)  # (chains, draws, dim)
    con = np.empty(unc.shape[:2] + (len(cnames),))
    for c in range(unc.shape[0]):
        for d in range(unc.shape[1]):
            con[c, d] = sm.param_constrain(unc[c, d], include_tp=include_tp, include_gq=False)
    index = {n: i for i, n in enumerate(cnames)}
    missing = [n for n in names if n not in index]
    if missing:
        return failure(model, arm, seed, "error", f"gate parameters not produced by param_constrain: {missing[:5]}")
    draws = con[:, :, [index[n] for n in names]]
    chains = out["chains_data"]
    grads_sampling = sum(c["retained_target_calls"] for c in chains)
    grads_total = out["target_calls_total"]
    restarted = [u for c in chains for u in c.get("chain_rescues", []) if u["outcome"]["kind"] == "restarted"]
    extra = {
        "final_step_size": [c["final_step_size"] for c in chains],
        "final_max_error": [c["final_max_error"] for c in chains],
        "invalid_stops": sum(c["invalid_stops"] for c in chains),
        "refinement_exhaustions": sum(c["refinement_exhaustions"] for c in chains),
        "refinement_exhaustions_per_chain": [c["refinement_exhaustions"] for c in chains],
        "frozen_chains": sum(1 for c in chains if c["refinement_exhaustions"] > out["retained"] // 2),
        "recoverable_failures_total": out["recoverable_failures_total"],
        "start_search_calls": out["init"]["start_search_calls"],
        "init": out["init"]["detail"],
        "defaults": out["defaults"],
        "warmup_config_used": out.get("warmup_config_used"),
        "tuning": out["tuning"],
        "execution": out.get("execution"),
        "replicas": out.get("replicas"),
        "warmup_divergences": sum(c["warmup_divergences"] for c in chains),
        "retained_reverse_coarser_stops": sum(c["retained_work"]["reverse_coarser_stops"] for c in chains),
        "retained_reverse_coarser_rejections": sum(c["retained_work"]["reverse_coarser_rejections"] for c in chains),
        "retained_nonfinite_position_rejections": sum(c["retained_work"]["nonfinite_position_rejections"] for c in chains),
        "warmup_nonfinite_position_rejections": sum(c["warmup_work"]["nonfinite_position_rejections"] for c in chains),
        "retained_leaves_built": sum(c["retained_work"]["leaves_built"] for c in chains),
        "retained_refined_leaves": sum(sum(c["retained_work"]["refinement_level_built"][1:]) for c in chains),
        "retained_depth_histogram": [sum(x) for x in zip(*(c["retained_depth_histogram"] for c in chains))],
        "retained_refinement_level_histogram": [sum(x) for x in zip(*(c["retained_refinement_level_histogram"] for c in chains))],
        "retained_stop_histogram": [c["retained_stop_histogram"] for c in chains],
        "warmup_step_trace_every_50": [c["warmup_step_trace_every_50"] for c in chains],
        "chain_warnings": out.get("chain_warnings", []),
        "rescued_chains": len(restarted),
        "algorithm_revision": out["algorithm_revision"],
        "unconstrained_dimension": out["dimension"],
        "per_chain_bulk_ess_min": [float(np.nanmin(arviz_stats(draws[i:i + 1])["bulk_ess"])) for i in range(draws.shape[0])],
    }
    cell = metrics(model, arm, seed, draws, names, ref, out["wall_seconds"], grads_total, grads_sampling,
                   sum(c["divergences"] for c in chains), sum(c["maximum_depth_stops"] for c in chains), extra)
    save_draws(model, arm, seed, draws, names, unconstrained=unc)
    # WP80: keep the per-transition telemetry, the final metric and the work totals of every chain.
    import gzip
    TELEMETRY.mkdir(parents=True, exist_ok=True)
    keep = ["telemetry_retained", "telemetry_warmup", "mass_diagonal", "final_step_size", "final_max_error",
            "retained_work", "warmup_work", "retained_target_calls", "warmup_target_calls"]
    tel = {"chains": [{k: c.get(k) for k in keep} for c in chains], "tuning": out["tuning"], "defaults": out["defaults"],
           "dimension": out["dimension"], "target_calls_total": out["target_calls_total"]}
    with gzip.open(TELEMETRY / f"{short(model)}-{arm}-{seed}.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(tel, fh)
    raw.unlink()  # unconstrained draws are kept in the .npz
    return cell


def prepare_cmdstan(model: str):
    import cmdstanpy

    cmdstanpy.set_cmdstan_path(str(CMDSTAN_HOME))
    stan = CMDSTAN_MODELS / f"{short(model)}.stan"
    if not stan.exists():
        raise RuntimeError(f"{stan} missing; run prepare_competitors.py first")
    t = time.perf_counter()
    m = cmdstanpy.CmdStanModel(stan_file=str(stan))
    log(f"cmdstan model ready {model} in {time.perf_counter() - t:.1f}s")
    return m


def run_cmdstan(model: str, seed: int, ref: dict | None, names: list[str], m) -> dict:
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
    missing = [n for n in names if n not in col]
    if missing:
        return failure(model, "cmdstan", seed, "error", f"gate parameters missing from CSV: {missing[:5]}")
    draws = np.transpose(all_draws[n_warm:, :, [col[n] for n in names]], (1, 0, 2))
    elapsed = []
    for f in fit.runset.csv_files:
        text = Path(f).read_text(encoding="utf-8", errors="replace")
        w = re.search(r"Elapsed Time:\s*([0-9.]+) seconds \(Warm-up\)", text)
        s = re.search(r"\s([0-9.]+) seconds \(Sampling\)", text)
        elapsed.append({"warmup": float(w.group(1)) if w else None, "sampling": float(s.group(1)) if s else None})
    extra = {"cmdstan_elapsed_per_chain": elapsed,
             "step_size": [float(x) for x in np.asarray(fit.step_size).ravel()]}
    cell = metrics(model, "cmdstan", seed, draws, names, ref, wall, grads_total, grads_sampling, div, depth, extra)
    save_draws(model, "cmdstan", seed, draws, names)
    return cell


def nutpie_model(model: str):
    """The object `nutpie.compile_stan_model(filename=...)` returns, from the library that
    prepare_competitors.py built with the identical bridgestan.compile_model call."""
    import bridgestan
    from nutpie import _lib
    from nutpie.compile_stan import CompiledStanModel

    stan = NUTPIE_MODELS / f"{short(model)}.stan"
    so = NUTPIE_MODELS / f"{short(model)}_model.so"
    if not so.exists():
        raise RuntimeError(f"{so} missing; run prepare_competitors.py first")
    if IS_WINDOWS:
        bridgestan.compile.windows_dll_path_setup()
    library = _lib.StanLibrary(str(so))
    return CompiledStanModel(code=stan.read_text(), library=library, dims={}, _coords={},
                             model_name="model", model=None, data=None).with_data(**posterior(model).data.values())


def run_nutpie(model: str, seed: int, ref: dict | None, names: list[str], compiled) -> dict:
    import nutpie

    t = time.perf_counter()
    idata = nutpie.sample(compiled, draws=1000, tune=1000, chains=4, seed=seed, progress_bar=False, save_warmup=True,
                          store_mass_matrix=True, store_unconstrained=True)  # WP80: storage only
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
    missing = [n for n in names if n not in flat]
    if missing:
        return failure(model, "nutpie", seed, "error", f"gate parameters missing from nutpie posterior: {missing[:5]}")
    draws = np.stack([flat[n] for n in names], axis=-1)
    ss = idata.sample_stats
    wss = idata.warmup_sample_stats
    grads_sampling = int(np.asarray(ss.n_steps).sum())
    grads_total = grads_sampling + int(np.asarray(wss.n_steps).sum())
    div = int(np.asarray(ss.diverging).sum())
    depth = int(np.asarray(ss.maxdepth_reached).sum()) if "maxdepth_reached" in ss else int((np.asarray(ss.depth) >= 10).sum())
    extra = {"step_size": [float(x) for x in np.asarray(ss.step_size)[:, -1]]}
    cell = metrics(model, "nutpie", seed, draws, names, ref, wall, grads_total, grads_sampling, div, depth, extra)
    save_draws(model, "nutpie", seed, draws, names)
    # WP80: per-draw sampler statistics, the stored inverse mass matrix and the unconstrained draws.
    TELEMETRY.mkdir(parents=True, exist_ok=True)
    tel = {}
    for prefix, ds in (("retained", ss), ("warmup", wss)):
        for var in ds.data_vars:
            arr = np.asarray(ds[var])
            if arr.dtype.kind in "biuf":
                tel[f"{prefix}__{var}"] = arr
    np.savez_compressed(TELEMETRY / f"{short(model)}-nutpie-{seed}.npz", **tel)
    return cell


# --------------------------------------------------------------------------- orchestration


def cell_path(model: str, arm: str, seed: int) -> Path:
    return CELLS / f"{short(model)}-{arm}-{seed}.json"


def run_model_arm(model: str, arm: str, seeds: list[int] | None = None) -> None:
    """The given seeds (WP76: one) of one (model, arm) in this process."""
    ref = reference(model)
    names = gate_names(model, ref)
    todo = [s for s in (seeds or SEEDS) if not cell_path(model, arm, s).exists()]
    if arm.startswith("owalnuts"):
        amendment_commit()
        for seed in todo:
            try:
                cell = run_owalnuts(model, arm, seed, ref, names)
            except Exception as e:  # noqa: BLE001
                cell = failure(model, arm, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
            write_cell(cell)
        return
    try:
        handle = prepare_cmdstan(model) if arm == "cmdstan" else nutpie_model(model)
    except Exception as e:  # noqa: BLE001
        for seed in todo:
            write_cell(failure(model, arm, seed, "compile_error", str(e)[-2000:]))
        return
    for seed in todo:
        try:
            cell = run_cmdstan(model, seed, ref, names, handle) if arm == "cmdstan" else run_nutpie(model, seed, ref, names, handle)
        except Exception as e:  # noqa: BLE001
            cell = failure(model, arm, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
        write_cell(cell)


def run_all(models: list[str], arms: list[str]) -> None:
    preregistered()
    ART.mkdir(parents=True, exist_ok=True)
    if any(a.startswith("owalnuts") for a in arms):
        log(f"oWALNUTS commit under test: {amendment_commit()}")
    machine = ART / "measured_on.json"
    record = json.loads(machine.read_text(encoding="utf-8")) if machine.exists() else {
        "platform": platform.platform(), "processor": platform.processor(),
        "cpu_count": os.cpu_count(), "python": sys.version.split()[0],
        "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "uname": " ".join(platform.uname()),
        "note": STUDY["platform"]["wall_label_note"], "runs": []}
    record["runs"].append({"arms": arms, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                           "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
                           "harness_sha256": hashlib.sha256(HARNESS.read_bytes()).hexdigest() if HARNESS.exists() else None})
    machine.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    for model in models:
        log(f"== {model}")
        for arm in arms:
            if arm == "owalnuts-dense" and model not in DENSE_MODELS:
                continue
            for seed in SEEDS:  # WP76: one child process per seed, so a crash cannot take later seeds with it
                if cell_path(model, arm, seed).exists():
                    continue
                cmd = [sys.executable, "-I", str(Path(__file__)), "cell", model, arm, str(seed)]
                try:
                    cp = subprocess.run(cmd, timeout=TIMEOUT + 600, text=True)
                    if cp.returncode != 0:
                        log(f"child for {model}/{arm}/{seed} exited {cp.returncode}")
                except subprocess.TimeoutExpired:
                    log(f"child for {model}/{arm}/{seed} timed out")
                if not cell_path(model, arm, seed).exists():
                    write_cell(failure(model, arm, seed, "timeout_or_crash", "child process ended without writing the cell"))


# The v7 funnel side check and v7 analysis are removed (WP76 analysis: analyze_nutpie18.py).


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] == "run":
        run_all(STUDY["telemetry"]["models"], ["owalnuts", "nutpie"])
    elif args[0] == "cell":
        run_model_arm(args[1], args[2], [int(args[3])] if len(args) > 3 else None)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
