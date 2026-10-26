#!/usr/bin/env python3
"""WP70 driver: why oWALNUTS's ESS per gradient on mcycle_gp-accel_gp is ~0.35x CmdStan's.

A copy of `STUDIES/bridgestan_linux_dispatch_v1/run_bench.py` (WP65), itself a copy of the v7
driver `STUDIES/posteriordb_bench_v7/run_posteriordb.py`; every change is listed in
PREREGISTRATION.md. The metric, gate and posteriordb functions are verbatim; `run_cmdstan` and
`run_owalnuts` additionally record the preregistered diagnostics.

    python run_gap.py run --phase=1     # accel_gp x {cmdstan, owalnuts}, controls x {owalnuts}; 3 seeds
    python run_gap.py diagnose          # artifacts/diagnosis.json + diagnosis.md (hypotheses H1-H3)
    python run_gap.py run --phase=2     # the three candidates on accel_gp + controls; 3 seeds
    python run_gap.py analyze           # artifacts/summary.json + results-table.md (candidate rules)
    python run_gap.py cell <model> <arm>

Run under `taskset -c 4-7`; children inherit it.
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
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
# Smoke tests (non-evidence model and seed, before the freeze) redirect with WP70_SMOKE_ART / _MODELS / _SEEDS.
ART = Path(os.environ["WP70_SMOKE_ART"]) if os.environ.get("WP70_SMOKE_ART") else HERE / "artifacts"
CELLS = ART / "cells"
DRAWS = ART / "draws"
MODELS = Path(os.environ["WP70_SMOKE_MODELS"]) if os.environ.get("WP70_SMOKE_MODELS") else HERE / "models"
CMDSTAN_MODELS = MODELS / "cmdstan"
LANE = Path(os.environ.get("WP70_LANE", "~/lanes/accel_gp_gap_v1")).expanduser()
PDB_PATH = Path(os.environ.get("WP70_POSTERIORDB", "~/infra/posteriordb")).expanduser() / PROTOCOL["posteriordb"]["path"]
CMDSTAN_HOME = LANE / "cmdstan-2.39.0"
HARNESS = HERE / "target" / "release" / "harness"
# arm -> (harness mode, dispatch, library build); every oWALNUTS arm uses the WP65-qualified replicated dispatch
OWALNUTS_ARMS = {arm: (spec["mode"], "replicated", "nothreads") for arm, spec in PROTOCOL["owalnuts_arms"].items()}
CANDIDATES = [a for a in OWALNUTS_ARMS if a != "owalnuts"]
ARMS = ["cmdstan"] + list(OWALNUTS_ARMS)
TARGET = PROTOCOL["target_model"]
CONTROLS = PROTOCOL["control_models"]
FIXED16 = [TARGET] + CONTROLS
ALL_MODELS = FIXED16
HOUSE = FIXED16
GATES_ONLY = []
SEEDS = [int(x) for x in os.environ["WP70_SMOKE_SEEDS"].split(",")] if os.environ.get("WP70_SMOKE_SEEDS") else PROTOCOL["seeds"]
TIMEOUT = PROTOCOL["cell_timeout_seconds"]
PHASES = {"1": [(TARGET, "cmdstan"), (TARGET, "owalnuts")] + [(m, "owalnuts") for m in CONTROLS],
          "2": [(m, c) for c in CANDIDATES for m in [TARGET] + CONTROLS]}


def short(model: str) -> str:
    return model.replace("-", "__")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------- source guard


def source_commit() -> str:
    """Refuses oWALNUTS cells unless the library source equals the preregistered base commit."""
    base = PROTOCOL["source_commit_under_test"]
    diff = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", base, "HEAD", "--",
                           "src", "integrations", "Cargo.toml", "tests"], capture_output=True, text=True)
    if diff.returncode != 0:
        raise SystemExit(f"library source at HEAD differs from the commit under test {base}")
    dirty = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "HEAD", "--", "src", "integrations", "Cargo.toml"],
                           capture_output=True, text=True)
    if dirty.returncode != 0:
        raise SystemExit("uncommitted library changes in the clone")
    return subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


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

    so, data = MODELS / "nothreads" / f"{short(model)}_model.so", MODELS / f"{short(model)}.data.json"
    if os.name == "nt":
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
        "schema": "accel-gp-gap-v1-cell-metrics",
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
        "schema": "accel-gp-gap-v1-cell-metrics", "model": model, "arm": arm, "seed": seed,
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
    mode, dispatch, build = OWALNUTS_ARMS[arm]
    so, data = MODELS / build / f"{short(model)}_model.so", MODELS / f"{short(model)}.data.json"
    raw = DRAWS / f"{short(model)}-{arm}-{seed}.raw.json"
    DRAWS.mkdir(parents=True, exist_ok=True)
    if raw.exists():
        raw.unlink()
    cmd = [str(HARNESS), str(so), str(data), mode, dispatch, str(seed), str(raw), "4"]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return failure(model, arm, seed, "timeout", f"exceeded {TIMEOUT}s")
    if cp.returncode != 0 or not raw.exists():
        return failure(model, arm, seed, "error", cp.stderr.strip()[-2000:] or f"exit {cp.returncode} with no stderr",
                       returncode=cp.returncode)
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
        "dispatch": out.get("dispatch"),
        "library_build": build,
        "compiled_threading": out.get("compiled_threading"),
        "threading": out.get("threading"),
        "cpus_allowed_list": out.get("cpus_allowed_list"),
        "model_info": out.get("model_info"),
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
        "unconstrained_draws_sha256": hashlib.sha256(np.ascontiguousarray(unc).tobytes()).hexdigest(),
        "warmup_target_calls_per_chain": [c["warmup_target_calls"] for c in chains],
        "retained_target_calls_per_chain": [c["retained_target_calls"] for c in chains],
        "per_chain_bulk_ess_min": [float(np.nanmin(arviz_stats(draws[i:i + 1])["bulk_ess"])) for i in range(draws.shape[0])],
    }
    wp70, arrays = owalnuts_diagnostics(out, model, grads_total, grads_sampling)
    extra.update(wp70)
    extra["warmup"] = out.get("warmup")
    extra["mass_diagonal_per_chain"] = [c["mass_diagonal"] for c in chains]
    cell = metrics(model, arm, seed, draws, names, ref, out["wall_seconds"], grads_total, grads_sampling,
                   sum(c["divergences"] for c in chains), sum(c["maximum_depth_stops"] for c in chains), extra)
    save_draws(model, arm, seed, draws, names, unconstrained=unc, **arrays)
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
    extra.update(cmdstan_diagnostics(fit, all_draws, col, n_warm, model, grads_total, grads_sampling))
    extra["inv_metric_per_chain"] = np.asarray(fit.metric).tolist()
    cell = metrics(model, "cmdstan", seed, draws, names, ref, wall, grads_total, grads_sampling, div, depth, extra)
    save_draws(model, "cmdstan", seed, draws, names)
    return cell

# --------------------------------------------------------------------------- WP70 diagnostics


@functools.lru_cache(maxsize=None)
def reference_unconstrained_variance(model: str) -> tuple[tuple[float, ...] | None, str | None]:
    """Per-coordinate variance of the posteriordb reference draws mapped to Stan's unconstrained space."""
    try:
        ref = posterior(model).reference_draws()
        sm = bridgestan_model(model)
        pnames = [bridgestan_name(n) for n in sm.param_names(include_tp=False, include_gq=False)]
        missing = [n for n in pnames if n not in ref[0]]
        if missing:
            return None, f"reference draws lack parameters {missing[:5]}"
        rows = []
        for chain in ref:
            arr = np.column_stack([np.asarray(chain[n], dtype=float) for n in pnames])
            rows.extend(sm.param_unconstrain(theta) for theta in arr)
        return tuple(float(v) for v in np.asarray(rows).var(0, ddof=1)), None
    except Exception as e:  # noqa: BLE001
        return None, f"{e}"


def metric_mismatch(variance_estimates: list[list[float]], model: str) -> dict:
    """q90 and max over unconstrained coordinates of |ln(adapted variance / reference variance)|, per chain."""
    ref, why = reference_unconstrained_variance(model)
    if ref is None:
        return {"metric_mismatch_q90_median_over_chains": None, "metric_mismatch_error": why}
    ref = np.asarray(ref)
    q90, mx = [], []
    for v in variance_estimates:
        r = np.abs(np.log(np.asarray(v, dtype=float) / ref))
        q90.append(float(np.quantile(r, 0.9)))
        mx.append(float(r.max()))
    return {"metric_mismatch_q90_per_chain": q90, "metric_mismatch_max_per_chain": mx,
            "metric_mismatch_q90_median_over_chains": float(np.median(q90))}


def owalnuts_diagnostics(out: dict, model: str, grads_total: int, grads_sampling: int) -> tuple[dict, dict]:
    chains = out["chains_data"]
    pt = [c["retained_per_transition"] for c in chains]
    stops = [s for p in pt for s in p["stop"]]
    n = len(stops)
    hist: dict = {}
    for s in stops:
        hist[s] = hist.get(s, 0) + 1
    # integration time per transition = leaves built x h (the kernel's trajectory_macro_length), comparable to
    # CmdStan's n_leapfrog x eps; merged orbit states x h is reported too (it excludes built-but-unmerged subtrees)
    integ = [n_leaves * h for p in pt for n_leaves, h in zip(p["leaves_built"], p["step_size"])]
    merged = [o * h for p in pt for o, h in zip(p["orbit_states"], p["step_size"])]
    acc = [a for p in pt for a in p["acceptance_statistic"] if a is not None]
    lv = [lvl for p in pt for lvl in p["selected_level"] if lvl is not None]
    steps = [c["final_step_size"] for c in chains]
    diag = {
        "retained_stop_counts": hist,
        "reverse_coarser_stop_fraction": hist.get("reverse_coarser_accepted", 0) / n,
        "maximum_depth_stop_fraction": hist.get("maximum_depth", 0) / n,
        "u_turn_stop_fraction": (hist.get("outer_u_turn", 0) + hist.get("recursive_u_turn", 0)) / n,
        "integration_time_median": float(np.median(integ)),
        "integration_time_mean": float(np.mean(integ)),
        "merged_orbit_time_median": float(np.median(merged)),
        "integration_time_median_by_stop": {s: float(np.median([n_leaves * h for p in pt for n_leaves, h, t in zip(p["leaves_built"], p["step_size"], p["stop"]) if t == s]))
                                            for s in hist},
        "gradients_per_retained_transition": grads_sampling / n,
        "refined_selected_fraction": (sum(1 for lvl in lv if lvl > 0) / len(lv)) if lv else None,
        "mean_acceptance_statistic": float(np.mean(acc)) if acc else None,
        "warmup_gradient_share": 1 - grads_sampling / grads_total,
        "step_size_per_chain": steps,
        "step_size_median": float(np.median(steps)),
        "step_size_max_over_min": max(steps) / min(steps),
        "depth_ge_10_fraction": sum(1 for p in pt for d in p["depth"] if d >= 10) / n,
        **metric_mismatch([[1.0 / m for m in c["mass_diagonal"]] for c in chains], model),
    }
    arrays = {f"pt_{k}": np.asarray([p[k] for p in pt], dtype=object if k in ("stop", "acceptance_statistic", "selected_level") else float)
              for k in pt[0]}
    return diag, arrays


def cmdstan_diagnostics(fit, all_draws: np.ndarray, col: dict, n_warm: int, model: str,
                        grads_total: int, grads_sampling: int) -> dict:
    s = all_draws[n_warm:]
    leap = s[:, :, col["n_leapfrog__"]]
    eps = s[:, :, col["stepsize__"]]
    tdepth = s[:, :, col["treedepth__"]]
    acc = s[:, :, col["accept_stat__"]]
    n = leap.size
    steps = [float(x) for x in np.asarray(fit.step_size).ravel()]
    inv_metric = np.asarray(fit.metric)
    return {
        "integration_time_median": float(np.median(leap * eps)),
        "integration_time_mean": float(np.mean(leap * eps)),
        "gradients_per_retained_transition": grads_sampling / n,
        "depth_cap_fraction": float((tdepth >= 10).sum() / n),
        "mean_acceptance_statistic": float(acc.mean()),
        "warmup_gradient_share": 1 - grads_sampling / grads_total,
        "step_size_median": float(np.median(steps)),
        "step_size_max_over_min": max(steps) / min(steps),
        **metric_mismatch([list(row) for row in inv_metric.reshape(inv_metric.shape[0], -1)], model),
    }


# --------------------------------------------------------------------------- orchestration


def cell_path(model: str, arm: str, seed: int) -> Path:
    return CELLS / f"{short(model)}-{arm}-{seed}.json"


def run_model_arm(model: str, arm: str) -> None:
    """All seeds of one (model, arm) in this process."""
    ref = reference(model)
    names = gate_names(model, ref)
    todo = [s for s in SEEDS if not cell_path(model, arm, s).exists()]
    if arm in OWALNUTS_ARMS:
        source_commit()
        for seed in todo:
            try:
                cell = run_owalnuts(model, arm, seed, ref, names)
            except Exception as e:  # noqa: BLE001
                cell = failure(model, arm, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
            write_cell(cell)
        return
    try:
        handle = prepare_cmdstan(model)
    except Exception as e:  # noqa: BLE001
        for seed in todo:
            write_cell(failure(model, arm, seed, "compile_error", str(e)[-2000:]))
        return
    for seed in todo:
        try:
            cell = run_cmdstan(model, seed, ref, names, handle)
        except Exception as e:  # noqa: BLE001
            cell = failure(model, arm, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
        write_cell(cell)


def machine_record() -> dict:
    def sh(cmd: list[str]) -> str:
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception as e:  # noqa: BLE001
            return f"unavailable: {e}"
    return {"platform": platform.platform(), "processor": platform.processor(), "cpu_count": os.cpu_count(),
            "python": sys.version.split()[0],
            "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "lscpu": sh(["lscpu"]), "gcc": sh(["g++", "--version"]).splitlines()[:1], "uname": sh(["uname", "-a"]),
            "env": {k: os.environ.get(k) for k in ("RAYON_NUM_THREADS", "OMP_NUM_THREADS", "TMPDIR")},
            "note": PROTOCOL["environment"]["timing_label"]}


def run_phase(phase: str) -> None:
    ART.mkdir(parents=True, exist_ok=True)
    log(f"oWALNUTS library source: {source_commit()}")
    if phase == "2" and not (ART / "diagnosis.json").exists() and not os.environ.get("WP70_SMOKE_ART"):
        raise SystemExit("phase 2 runs only after `diagnose` has written artifacts/diagnosis.json")
    machine = ART / "measured_on.json"
    record = json.loads(machine.read_text(encoding="utf-8")) if machine.exists() else {**machine_record(), "runs": []}
    record["runs"].append({"phase": phase, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    machine.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    for model, arm in PHASES[phase]:
        if all(cell_path(model, arm, s).exists() for s in SEEDS):
            continue
        log(f"== {model} / {arm}")
        cmd = [sys.executable, "-I", str(Path(__file__)), "cell", model, arm]
        try:
            cp = subprocess.run(cmd, timeout=TIMEOUT * len(SEEDS) + 600, text=True)
            if cp.returncode != 0:
                log(f"child for {model}/{arm} exited {cp.returncode}")
        except subprocess.TimeoutExpired:
            log(f"child for {model}/{arm} timed out")
        for seed in SEEDS:
            if not cell_path(model, arm, seed).exists():
                write_cell(failure(model, arm, seed, "timeout_or_crash", "child process ended without writing the cell"))


# --------------------------------------------------------------------------- analysis


def geomean(xs: list[float]) -> float:
    xs = [x for x in xs if x and math.isfinite(x) and x > 0]
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs))) if xs else float("nan")




def load_cells() -> dict:
    cells: dict = {}
    for path in sorted(CELLS.glob("*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        c.pop("parameters", None)
        c.pop("warmup_step_trace_every_50", None)
        if c.get("status") == "ok" and c.get("gradients_total"):
            c["wall_per_gradient_us"] = 1e6 * c["wall_seconds"] / c["gradients_total"]
        cells.setdefault(c["model"], {}).setdefault(c["arm"], {})[str(c["seed"])] = c
    return cells


def med(xs: list) -> float | None:
    xs = [x for x in xs if x is not None and isinstance(x, (int, float)) and math.isfinite(x)]
    return statistics.median(xs) if xs else None


def diagnose() -> None:
    """The three preregistered diagnostics on the accel_gp phase-1 cells, evaluated mechanically."""
    cells = load_cells()
    o = cells.get(TARGET, {}).get("owalnuts", {})
    c = cells.get(TARGET, {}).get("cmdstan", {})
    seeds = [str(s) for s in SEEDS]
    ok = [s for s in seeds if o.get(s, {}).get("status") == "ok" and c.get(s, {}).get("status") == "ok"]

    def per_seed(key: str, ratio: bool) -> dict:
        if ratio:
            return {s: (o[s].get(key) / c[s].get(key)) if o[s].get(key) and c[s].get(key) else None for s in ok}
        return {s: o[s].get(key) for s in seeds if o.get(s, {}).get("status") == "ok"}

    th = PROTOCOL["hypotheses"]
    rc = per_seed("reverse_coarser_stop_fraction", False)
    it = per_seed("integration_time_median", True)
    md = per_seed("maximum_depth_stop_fraction", False)
    mm = per_seed("metric_mismatch_q90_median_over_chains", True)
    complete = len(ok) == len(seeds)
    d = {
        "H1": {"reverse_coarser_stop_fraction_mean": float(np.mean(list(rc.values()))) if rc else None,
               "integration_time_ratio_median": med(list(it.values())), "per_seed_rc": rc, "per_seed_integration_ratio": it},
        "H2": {"maximum_depth_stop_fraction_mean": float(np.mean(list(md.values()))) if md else None, "per_seed": md},
        "H3": {"metric_mismatch_ratio_median": med(list(mm.values())), "per_seed": mm},
    }
    d["H1"]["supported"] = (complete and d["H1"]["reverse_coarser_stop_fraction_mean"] >= th["H1"]["rc_fraction_threshold"]
                            and d["H1"]["integration_time_ratio_median"] is not None
                            and d["H1"]["integration_time_ratio_median"] <= th["H1"]["integration_ratio_threshold"])
    d["H2"]["supported"] = complete and d["H2"]["maximum_depth_stop_fraction_mean"] >= th["H2"]["threshold"]
    d["H3"]["supported"] = (complete and d["H3"]["metric_mismatch_ratio_median"] is not None
                            and d["H3"]["metric_mismatch_ratio_median"] >= th["H3"]["threshold"])
    reported = {}
    for key in ("step_size_median", "mean_acceptance_statistic", "warmup_gradient_share", "gradients_per_retained_transition",
                "integration_time_median", "step_size_max_over_min", "metric_mismatch_q90_median_over_chains"):
        reported[key] = {"owalnuts": {s: o[s].get(key) for s in ok}, "cmdstan": {s: c[s].get(key) for s in ok},
                         "ratio_median": med([(o[s].get(key) / c[s].get(key)) if o[s].get(key) and c[s].get(key) else None for s in ok])}
    reported["owalnuts_refined_selected_fraction"] = {s: o[s].get("refined_selected_fraction") for s in ok}
    reported["owalnuts_retained_refinement_level_histogram"] = {s: o[s].get("retained_refinement_level_histogram") for s in ok}
    reported["owalnuts_retained_stop_counts"] = {s: o[s].get("retained_stop_counts") for s in ok}
    reported["owalnuts_integration_time_median_by_stop"] = {s: o[s].get("integration_time_median_by_stop") for s in ok}
    reported["owalnuts_depth_ge_10_fraction"] = {s: o[s].get("depth_ge_10_fraction") for s in ok}
    reported["cmdstan_depth_cap_fraction"] = {s: c[s].get("depth_cap_fraction") for s in ok}
    reported["argmin_bulk_ess"] = {"owalnuts": {s: o[s].get("argmin_bulk_ess") for s in ok}, "cmdstan": {s: c[s].get("argmin_bulk_ess") for s in ok}}
    reported["baseline_bulk_ess_per_gradient_ratio_vs_cmdstan"] = ratio_of_medians(cells, TARGET, "owalnuts", "cmdstan")
    out = {"schema": "accel-gp-gap-v1-diagnosis", "complete": complete, "seeds_ok": ok, "hypotheses": d, "reported": reported,
           "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (ART / "diagnosis.json").write_text(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    lines = ["# WP70 diagnosis (accel_gp, phase 1)", "", "| hypothesis | statistic | value | threshold | supported |", "|---|---|---|---|---|",
             f"| H1 truncation | RC-stop fraction; integration-time ratio oWALNUTS/CmdStan | {d['H1']['reverse_coarser_stop_fraction_mean']}; {d['H1']['integration_time_ratio_median']} | >= {th['H1']['rc_fraction_threshold']}; <= {th['H1']['integration_ratio_threshold']} | {d['H1']['supported']} |",
             f"| H2 depth cap | maximum-depth stop fraction | {d['H2']['maximum_depth_stop_fraction_mean']} | >= {th['H2']['threshold']} | {d['H2']['supported']} |",
             f"| H3 adaptation | metric mismatch ratio oWALNUTS/CmdStan | {d['H3']['metric_mismatch_ratio_median']} | >= {th['H3']['threshold']} | {d['H3']['supported']} |",
             "", "## Reported", "", "```", json.dumps(reported, indent=1, default=str), "```"]
    (ART / "diagnosis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:7]))


def ratio_of_medians(cells: dict, model: str, a: str, b: str, key: str = "min_bulk_ess_per_gradient") -> float | None:
    """v7 convention: seed-median of arm a over seed-median of arm b; None unless every seed is ok on both."""
    ca, cb = cells.get(model, {}).get(a, {}), cells.get(model, {}).get(b, {})
    va = [ca.get(str(s), {}).get(key) for s in SEEDS if ca.get(str(s), {}).get("status") == "ok"]
    vb = [cb.get(str(s), {}).get(key) for s in SEEDS if cb.get(str(s), {}).get("status") == "ok"]
    if len(va) != len(SEEDS) or len(vb) != len(SEEDS):
        return None
    return statistics.median(va) / statistics.median(vb)


def passes(cells: dict, model: str, arm: str) -> int:
    return sum(1 for s in SEEDS if cells.get(model, {}).get(arm, {}).get(str(s), {}).get("passed"))


def analyze() -> None:
    cells = load_cells()
    rule = PROTOCOL["decision_rule"]
    diag = json.loads((ART / "diagnosis.json").read_text(encoding="utf-8")) if (ART / "diagnosis.json").exists() else {}
    base = {"accel_ratio_vs_cmdstan": ratio_of_medians(cells, TARGET, "owalnuts", "cmdstan"),
            "accel_passes": passes(cells, TARGET, "owalnuts"), "cmdstan_accel_passes": passes(cells, TARGET, "cmdstan"),
            "control_passes": sum(passes(cells, m, "owalnuts") for m in CONTROLS)}
    results = {}
    for cand in CANDIDATES:
        r1 = ratio_of_medians(cells, TARGET, cand, "cmdstan")
        hi_z = [f"{m}/{s}={c['max_abs_z']:.2f}" for m in [TARGET] + CONTROLS for s, c in cells.get(m, {}).get(cand, {}).items()
                if c.get("passed") and c.get("max_abs_z") is not None and c["max_abs_z"] > rule["max_abs_z"]]
        ctrl = {m: ratio_of_medians(cells, m, cand, "owalnuts") for m in CONTROLS}
        ctrl_vals = [v for v in ctrl.values() if v]
        g = geomean(ctrl_vals) if len(ctrl_vals) == len(CONTROLS) else None
        cp = sum(passes(cells, m, cand) for m in CONTROLS)
        errors = [f"{m}/{s}: {c.get('status')}" for m in [TARGET] + CONTROLS for s, c in cells.get(m, {}).get(cand, {}).items() if c.get("status") != "ok"]
        clauses = {
            "R1_accel_ess_per_gradient_vs_cmdstan_ge": {"value": r1, "threshold": rule["accel_ratio_threshold"],
                                                        "held": r1 is not None and r1 >= rule["accel_ratio_threshold"]},
            "R2_accel_gates_held": {"value": {"candidate_passes": passes(cells, TARGET, cand), "default_passes": base["accel_passes"],
                                              "passing_cells_above_z": hi_z},
                                    "held": passes(cells, TARGET, cand) >= base["accel_passes"] and not hi_z},
            "R3a_control_pass_count_not_lower": {"value": {"candidate": cp, "default": base["control_passes"]}, "held": cp >= base["control_passes"]},
            "R3b_control_geomean_ess_per_gradient_ge": {"value": g, "per_model": ctrl, "threshold": rule["control_geomean_threshold"],
                                                        "held": g is not None and g >= rule["control_geomean_threshold"]},
        }
        results[cand] = {"clauses": clauses, "passes_rule": all(v["held"] for v in clauses.values()), "errors": errors,
                         "hypothesis": PROTOCOL["owalnuts_arms"][cand]["hypothesis"],
                         "hypothesis_supported_by_diagnostic": diag.get("hypotheses", {}).get(PROTOCOL["owalnuts_arms"][cand]["hypothesis"], {}).get("supported"),
                         "accel_ratio_vs_default": ratio_of_medians(cells, TARGET, cand, "owalnuts"),
                         "accel_candidate_diagnostics": {k: med([c.get(k) for c in cells.get(TARGET, {}).get(cand, {}).values()])
                                                         for k in ("reverse_coarser_stop_fraction", "maximum_depth_stop_fraction", "integration_time_median",
                                                                   "step_size_median", "warmup_gradient_share", "metric_mismatch_q90_median_over_chains",
                                                                   "gradients_per_retained_transition", "min_bulk_ess", "min_tail_ess", "max_rank_rhat")}}
    summary = {"schema": "accel-gp-gap-v1-summary", "baseline": base, "candidates": results, "diagnosis": diag.get("hypotheses"),
               "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
               "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cells": cells}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")

    def f(x, fmt=".3f"):
        return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)

    lines = ["# WP70 results", "", f"Seeds {SEEDS}; 4 chains x 1,000/1,000 (warmup2000: 2,000/1,000); pinned to cores 4-7, co-tenanted.", "",
             "| model | arm | gates | grads | min bulk ESS | min tail ESS | max R-hat | bulk ESS/grad x1e3 (seed median) | div | max abs z |",
             "|---|---|---|---:|---:|---:|---:|---:|---|---:|"]
    for m in [TARGET] + CONTROLS:
        for arm in ARMS:
            cs = cells.get(m, {}).get(arm, {})
            if not cs:
                continue
            ok = [c for c in cs.values() if c.get("status") == "ok"]
            lines.append(f"| {m} | {arm} | {sum(1 for c in ok if c['passed'])}/{len(cs)} | {f(med([c['gradients_total'] for c in ok]), ',.0f')} | "
                         f"{f(med([c['min_bulk_ess'] for c in ok]), ',.0f')} | {f(med([c['min_tail_ess'] for c in ok]), ',.0f')} | "
                         f"{f(med([c['max_rank_rhat'] for c in ok]), '.4f')} | {f((med([c['min_bulk_ess_per_gradient'] for c in ok]) or float('nan')) * 1e3)} | "
                         f"{','.join(str(c['divergences']) for c in ok)} | {f(max([c['max_abs_z'] or 0 for c in ok], default=None), '.2f')} |")
    lines += ["", f"Baseline: oWALNUTS/CmdStan accel_gp ESS per gradient {f(base['accel_ratio_vs_cmdstan'])}; accel passes oWALNUTS {base['accel_passes']}/3, CmdStan {base['cmdstan_accel_passes']}/3.", "",
              "| candidate | hypothesis (supported?) | R1 accel vs CmdStan | R2 accel gates | R3a control passes | R3b control geomean | rule |", "|---|---|---|---|---|---|---|"]
    for cand, r in results.items():
        cl = r["clauses"]
        lines.append(f"| {cand} | {r['hypothesis']} ({r['hypothesis_supported_by_diagnostic']}) | {f(cl['R1_accel_ess_per_gradient_vs_cmdstan_ge']['value'])} ({cl['R1_accel_ess_per_gradient_vs_cmdstan_ge']['held']}) | "
                     f"{cl['R2_accel_gates_held']['value']['candidate_passes']}/3 vs {cl['R2_accel_gates_held']['value']['default_passes']}/3 ({cl['R2_accel_gates_held']['held']}) | "
                     f"{cl['R3a_control_pass_count_not_lower']['value']['candidate']} vs {cl['R3a_control_pass_count_not_lower']['value']['default']} ({cl['R3a_control_pass_count_not_lower']['held']}) | "
                     f"{f(cl['R3b_control_geomean_ess_per_gradient_ge']['value'])} ({cl['R3b_control_geomean_ess_per_gradient_ge']['held']}) | **{r['passes_rule']}** |")
    (ART / "results-table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "run":
        phase = next((a.split("=", 1)[1] for a in args[1:] if a.startswith("--phase=")), None)
        if phase not in PHASES:
            raise SystemExit("run needs --phase=1 or --phase=2")
        run_phase(phase)
    elif args and args[0] == "cell":
        run_model_arm(args[1], args[2])
    elif args and args[0] == "diagnose":
        diagnose()
    elif args and args[0] == "analyze":
        analyze()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
