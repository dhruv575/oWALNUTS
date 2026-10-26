#!/usr/bin/env python3
"""WP73 driver: where oWALNUTS spends its warmup gradients, and three research warmup schedules.

A copy of `STUDIES/accel_gp_gap_v1/run_gap.py` (WP70), itself the WP65 / v7 driver; every change is
listed in PREREGISTRATION.md. The posteriordb, metric and gate functions are verbatim; `run_nutpie`
is v7's / WP64's; `run_owalnuts`, `run_cmdstan` and `run_nutpie` additionally record the warmup spend.

    python run_spend.py tests           # phase T: kernel fingerprint + stable-metric-stop tests (rule clause R4)
    python run_spend.py run --phase=A   # descriptive arm: 17 models x {owalnuts, cmdstan, nutpie} x 3 seeds
    python run_spend.py run --phase=B   # candidates: {init25, half, stablestop} x 17 models x 3 seeds
    python run_spend.py run --phase=F   # funnel sanity: {default, init25, half, stablestop} x 10 seeds, 4 x 2,000/20,000
    python run_spend.py analyze         # artifacts/summary.json + results-table.md
    python run_spend.py cell <model> <arm> <seed>

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
# Smoke tests (non-evidence model and seed, before the freeze) redirect with WP73_SMOKE_ART / _MODELS / _SEEDS / _HOUSE.
SMOKE = bool(os.environ.get("WP73_SMOKE_ART"))
ART = Path(os.environ["WP73_SMOKE_ART"]) if SMOKE else HERE / "artifacts"
CELLS = ART / "cells"
DRAWS = ART / "draws"
FUNNEL_CELLS = ART / "funnel"
MODELS = Path(os.environ["WP73_SMOKE_MODELS"]) if os.environ.get("WP73_SMOKE_MODELS") else HERE / "models"
CMDSTAN_MODELS = MODELS / "cmdstan"
NUTPIE_MODELS = MODELS / "nutpie"
LANE = Path(os.environ.get("WP73_LANE", "~/lanes/warmup_spend_v1")).expanduser()
PDB_PATH = Path(os.environ.get("WP73_POSTERIORDB", "~/infra/posteriordb")).expanduser() / PROTOCOL["posteriordb"]["path"]
CMDSTAN_HOME = LANE / "cmdstan-2.39.0"
HARNESS = HERE / "target" / "release" / "harness"
FUNNEL = HERE / "target" / "release" / "funnel"
# arm -> harness arm; every oWALNUTS arm uses the WP65-qualified replicated dispatch and the nothreads build
OWALNUTS_ARMS = {arm: spec["harness_arm"] for arm, spec in PROTOCOL["owalnuts_arms"].items()}
CANDIDATES = [a for a in OWALNUTS_ARMS if a != "owalnuts"]
ARMS = ["owalnuts", "cmdstan", "nutpie"] + CANDIDATES
HOUSE = os.environ["WP73_SMOKE_HOUSE"].split(",") if os.environ.get("WP73_SMOKE_HOUSE") else PROTOCOL["house_models"]
ALL_MODELS = HOUSE
GATES_ONLY: list[str] = []
SEEDS = [int(x) for x in os.environ["WP73_SMOKE_SEEDS"].split(",")] if os.environ.get("WP73_SMOKE_SEEDS") else PROTOCOL["seeds"]
FUNNEL_SPEC = PROTOCOL["funnel_sanity"]
FUNNEL_SEEDS = [int(x) for x in os.environ["WP73_SMOKE_FUNNEL_SEEDS"].split(",")] if os.environ.get("WP73_SMOKE_FUNNEL_SEEDS") else FUNNEL_SPEC["seeds"]
TIMEOUT = PROTOCOL["cell_timeout_seconds"]
PHASES = {"A": [(m, a) for m in HOUSE for a in ("owalnuts", "cmdstan", "nutpie")],
          "B": [(m, c) for c in CANDIDATES for m in HOUSE]}
WARMUP = PROTOCOL["warmup"]
RETAINED = PROTOCOL["retained"]


def short(model: str) -> str:
    return model.replace("-", "__")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------- source guard


def source_commit() -> str:
    """Refuses oWALNUTS cells unless the library source equals the preregistered commit."""
    if SMOKE:
        return "smoke-test-not-evidence"
    base = PROTOCOL["source_commit_under_test"]
    diff = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", base, "HEAD", "--",
                           "src", "integrations", "Cargo.toml", "tests"], capture_output=True, text=True)
    if diff.returncode != 0:
        raise SystemExit(f"library source at HEAD differs from the commit under test {base}")
    dirty = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "HEAD", "--", "src", "integrations", "Cargo.toml", "tests"],
                           capture_output=True, text=True)
    if dirty.returncode != 0:
        raise SystemExit("uncommitted library changes in the clone")
    return subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


# --------------------------------------------------------------------------- posteriordb (verbatim)


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


# --------------------------------------------------------------------------- metrics (verbatim except the schema string)


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
        "schema": "warmup-spend-v1-cell-metrics",
        "model": model, "arm": arm, "seed": seed, "status": "ok",
        "tier": "reference" if ref is not None else "gates_only",
        "block": "house",
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
        "schema": "warmup-spend-v1-cell-metrics", "model": model, "arm": arm, "seed": seed,
        "block": "house",
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
            f"warm {cell.get('warmup_share', float('nan')):.3f} minbulk {cell['min_bulk_ess']:.0f} mintail {cell['min_tail_ess']:.0f} "
            f"rhat {cell['max_rank_rhat']:.4f} div {cell['divergences']} max|z| {'-' if z is None else f'{z:.2f}'} passed {cell['passed']}")
    else:
        log(f"  {cell['arm']} {cell['seed']}: {s}: {cell.get('error', '')[:200]}")


def save_draws(model: str, arm: str, seed: int, draws: np.ndarray, names: list[str], **more) -> None:
    DRAWS.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(DRAWS / f"{short(model)}-{arm}-{seed}.npz", draws=draws, names=np.asarray(names), **more)


# --------------------------------------------------------------------------- WP73 warmup-spend bookkeeping


def stan_schedule(warmup: int = WARMUP) -> dict:
    """Stan's (and oWALNUTS's default) window rule: 75 / 25, 50, ... / 50, last window extended."""
    initial, base, terminal = 75, 25, 50
    slow_end = warmup - terminal
    windows, start, size = [], initial, base
    while start < slow_end:
        remaining = slow_end - start
        length = min(size, remaining)
        if remaining > length and remaining - length < 2 * size:
            length = remaining
        windows.append([start, start + length])
        start += length
        size *= 2
    return {"initial_fast_end": initial, "terminal_fast_start": slow_end, "windows": windows}


def phase_bins(schedule: dict, warmup: int) -> list[tuple[str, int, int]]:
    bins = [("initial_fast", 0, schedule["initial_fast_end"])]
    bins += [(f"window_{i}", a, b) for i, (a, b) in enumerate(schedule["windows"])]
    bins.append(("terminal_fast", schedule["terminal_fast_start"], warmup))
    return [b for b in bins if b[2] > b[1]]


def per_phase(evals_per_chain: list[list[float]], schedules: list[dict], warmups: list[int]) -> dict:
    """Gradients per transition by warmup phase, pooled over chains (each chain by its own schedule)."""
    out: dict = {}
    for ev, sch, w in zip(evals_per_chain, schedules, warmups):
        for name, a, b in phase_bins(sch, w):
            o = out.setdefault(name, {"transitions": 0, "gradients": 0})
            o["transitions"] += b - a
            o["gradients"] += float(sum(ev[a:b]))
    for o in out.values():
        o["per_transition"] = o["gradients"] / o["transitions"] if o["transitions"] else None
    return out


def fixed_bins(evals_per_chain: list[list[float]], edges: list[int]) -> list[float | None]:
    """Gradients per transition in fixed index bins [edges[i], edges[i+1]), pooled over chains."""
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        g = [float(sum(ev[a:min(b, len(ev))])) for ev in evals_per_chain]
        n = sum(max(0, min(b, len(ev)) - a) for ev in evals_per_chain)
        out.append(sum(g) / n if n else None)
    return out


FIXED_EDGES = [0, 75, 100, 150, 250, 450, 950, 1000]


# --------------------------------------------------------------------------- arms


def run_owalnuts(model: str, arm: str, seed: int, ref: dict | None, names: list[str]) -> dict:
    harness_arm = OWALNUTS_ARMS[arm]
    so, data = MODELS / "nothreads" / f"{short(model)}_model.so", MODELS / f"{short(model)}.data.json"
    raw = DRAWS / f"{short(model)}-{arm}-{seed}.raw.json"
    DRAWS.mkdir(parents=True, exist_ok=True)
    if raw.exists():
        raw.unlink()
    cmd = [str(HARNESS), str(so), str(data), harness_arm, "replicated", str(seed), str(raw), "4"]
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
        "library_build": "nothreads",
        "compiled_threading": out.get("compiled_threading"),
        "threading": out.get("threading"),
        "cpus_allowed_list": out.get("cpus_allowed_list"),
        "model_info": out.get("model_info"),
        "warmup_divergences": sum(c["warmup_divergences"] for c in chains),
        "retained_reverse_coarser_stops": sum(c["retained_work"]["reverse_coarser_stops"] for c in chains),
        "retained_nonfinite_position_rejections": sum(c["retained_work"]["nonfinite_position_rejections"] for c in chains),
        "warmup_nonfinite_position_rejections": sum(c["warmup_work"]["nonfinite_position_rejections"] for c in chains),
        "retained_depth_histogram": [sum(x) for x in zip(*(c["retained_depth_histogram"] for c in chains))],
        "retained_stop_histogram": [c["retained_stop_histogram"] for c in chains],
        "chain_warnings": out.get("chain_warnings", []),
        "rescued_chains": len(restarted),
        "algorithm_revision": out["algorithm_revision"],
        "unconstrained_dimension": out["dimension"],
        "unconstrained_draws_sha256": hashlib.sha256(np.ascontiguousarray(unc).tobytes()).hexdigest(),
        "warmup_target_calls_per_chain": [c["warmup_target_calls"] for c in chains],
        "retained_target_calls_per_chain": [c["retained_target_calls"] for c in chains],
        "per_chain_bulk_ess_min": [float(np.nanmin(arviz_stats(draws[i:i + 1])["bulk_ess"])) for i in range(draws.shape[0])],
        "mass_diagonal_per_chain": [c["mass_diagonal"] for c in chains],
    }
    extra.update(owalnuts_spend(out, grads_total, grads_sampling))
    cell = metrics(model, arm, seed, draws, names, ref, out["wall_seconds"], grads_total, grads_sampling,
                   sum(c["divergences"] for c in chains), sum(c["maximum_depth_stops"] for c in chains), extra)
    arrays = {"warmup_evaluations": np.asarray([np.pad(np.asarray(c["warmup_per_transition"]["target_evaluations"], float),
                                                       (0, out["warmup"] - c["warmup_transitions"]), constant_values=np.nan) for c in chains]),
              "warmup_step": np.asarray([np.pad(np.asarray(c["warmup_per_transition"]["step_size"], float),
                                                (0, out["warmup"] - c["warmup_transitions"]), constant_values=np.nan) for c in chains]),
              "retained_evaluations": np.asarray([c["retained_per_transition"]["target_evaluations"] for c in chains], float)}
    save_draws(model, arm, seed, draws, names, unconstrained=unc, **arrays)
    raw.unlink()  # unconstrained draws and the per-transition arrays are kept in the .npz
    return cell


def owalnuts_spend(out: dict, grads_total: int, grads_sampling: int) -> dict:
    chains = out["chains_data"]
    ev = [c["warmup_per_transition"]["target_evaluations"] for c in chains]
    sch = [c["warmup_schedule"] for c in chains]
    warm = [c["warmup_transitions"] for c in chains]
    warm_grads = sum(c["warmup_target_calls"] for c in chains)
    start = out["init"]["start_search_calls"]
    return {
        "warmup_share": 1 - grads_sampling / grads_total,
        "warmup_share_excluding_start_search": warm_grads / (grads_total - start) if grads_total > start else None,
        "warmup_gradients": warm_grads,
        "start_search_gradients": start,
        "warmup_transitions_per_chain": warm,
        "warmup_schedule_per_chain": sch,
        "warmup_gradients_per_phase": per_phase(ev, sch, warm),
        "warmup_gradients_per_transition_fixed_bins": fixed_bins(ev, FIXED_EDGES),
        "sampling_gradients_per_transition": grads_sampling / (len(chains) * out["retained"]),
        "phase_work": [c["phase_work"] for c in chains],
        "metric_updates": [c["metric_updates"] for c in chains],
        "stable_metric_checks": [c["stable_metric_checks"] for c in chains],
        "warmup_step_trace_every_50": [c["warmup_per_transition"]["step_size"][::50] for c in chains],
        "adaptation_target_calls": sum(c["adaptation_target_calls"] for c in chains),
    }


def prepare_cmdstan(model: str):
    import cmdstanpy

    cmdstanpy.set_cmdstan_path(str(CMDSTAN_HOME))
    stan = CMDSTAN_MODELS / f"{short(model)}.stan"
    if not stan.exists():
        raise RuntimeError(f"{stan} missing; run build_models.py first")
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
    warm_leap = [list(map(float, leap[:n_warm, c])) for c in range(leap.shape[1])]
    sch = stan_schedule(n_warm)
    extra = {"cmdstan_elapsed_per_chain": elapsed,
             "step_size": [float(x) for x in np.asarray(fit.step_size).ravel()],
             "warmup_share": 1 - grads_sampling / grads_total,
             "warmup_gradients": grads_total - grads_sampling,
             "warmup_schedule": sch,
             "warmup_gradients_per_phase": per_phase(warm_leap, [sch] * len(warm_leap), [n_warm] * len(warm_leap)),
             "warmup_gradients_per_transition_fixed_bins": fixed_bins(warm_leap, FIXED_EDGES),
             "sampling_gradients_per_transition": grads_sampling / leap[n_warm:].size,
             "warmup_step_trace_every_50": [list(map(float, all_draws[:n_warm:50, c, col["stepsize__"]])) for c in range(leap.shape[1])],
             "warmup_divergences": int(all_draws[:n_warm, :, col["divergent__"]].sum())}
    cell = metrics(model, "cmdstan", seed, draws, names, ref, wall, grads_total, grads_sampling, div, depth, extra)
    save_draws(model, "cmdstan", seed, draws, names, warmup_evaluations=leap[:n_warm].T,
               warmup_step=all_draws[:n_warm, :, col["stepsize__"]].T)
    return cell


def nutpie_model(model: str):
    """The object `nutpie.compile_stan_model(filename=...)` returns, from the library that
    build_models.py built with the make call `bridgestan.compile_model(.., make_args=["STAN_THREADS=true"])` makes (v7 / WP64)."""
    import bridgestan
    from nutpie import _lib
    from nutpie.compile_stan import CompiledStanModel

    stan = NUTPIE_MODELS / f"{short(model)}.stan"
    so = NUTPIE_MODELS / f"{short(model)}_model.so"
    if not so.exists():
        raise RuntimeError(f"{so} missing; run build_models.py first")
    if os.name == "nt":
        bridgestan.compile.windows_dll_path_setup()
    library = _lib.StanLibrary(str(so))
    return CompiledStanModel(code=stan.read_text(), library=library, dims={}, _coords={},
                             model_name="model", model=None, data=None).with_data(**posterior(model).data.values())


def run_nutpie(model: str, seed: int, ref: dict | None, names: list[str], compiled) -> dict:
    import nutpie

    t = time.perf_counter()
    idata = nutpie.sample(compiled, draws=1000, tune=1000, chains=4, seed=seed, progress_bar=False, save_warmup=True,
                          store_mass_matrix=True)
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
    extra.update(nutpie_spend(ss, wss, grads_total, grads_sampling))
    cell = metrics(model, "nutpie", seed, draws, names, ref, wall, grads_total, grads_sampling, div, depth, extra)
    save_draws(model, "nutpie", seed, draws, names, warmup_evaluations=np.asarray(wss.n_steps, float),
               warmup_step=np.asarray(wss.step_size, float))
    return cell


def nutpie_spend(ss, wss, grads_total: int, grads_sampling: int) -> dict:
    """Warmup spend from nutpie's exposed per-draw stats: n_steps and step_size of every warmup draw,
    and, with store_mass_matrix, the draw after which the mass matrix stops changing."""
    n_steps = np.asarray(wss.n_steps, dtype=float)  # (chain, tune)
    ev = [list(row) for row in n_steps]
    tune = n_steps.shape[1]
    last_change, switches = [], []
    key = next((k for k in ("mass_matrix_inv", "mass_matrix") if k in wss), None)
    if key is not None:
        mm = np.asarray(wss[key], dtype=float)
        mm = mm.reshape(mm.shape[0], mm.shape[1], -1)
        for c in range(mm.shape[0]):
            changed = np.where(np.any(mm[c, 1:] != mm[c, :-1], axis=-1))[0] + 1
            last_change.append(int(changed.max()) if changed.size else 0)
            switches.append(changed.tolist()[:200])
    # nutpie's own phases from the exposed diagnostics: before vs after the last mass-matrix change
    own = {}
    if last_change:
        before = sum(float(sum(e[:lc])) for e, lc in zip(ev, last_change))
        after = sum(float(sum(e[lc:])) for e, lc in zip(ev, last_change))
        nb = sum(last_change)
        na = sum(tune - lc for lc in last_change)
        own = {"metric_adapting": {"transitions": nb, "gradients": before, "per_transition": before / nb if nb else None},
               "step_only_final": {"transitions": na, "gradients": after, "per_transition": after / na if na else None}}
    return {
        "warmup_share": 1 - grads_sampling / grads_total,
        "warmup_gradients": grads_total - grads_sampling,
        "warmup_gradients_per_transition_fixed_bins": fixed_bins(ev, FIXED_EDGES),
        "warmup_gradients_per_phase_nutpie_own": own,
        "mass_matrix_stat": key,
        "mass_matrix_last_change_per_chain": last_change,
        "mass_matrix_change_draws_per_chain": switches,
        "sampling_gradients_per_transition": grads_sampling / np.asarray(ss.n_steps).size,
        "warmup_step_trace_every_50": [list(map(float, row[::50])) for row in np.asarray(wss.step_size, float)],
        "warmup_sample_stats_variables": sorted(str(v) for v in wss.data_vars),
        "warmup_divergences": int(np.asarray(wss.diverging).sum()) if "diverging" in wss else None,
    }


# --------------------------------------------------------------------------- orchestration


def cell_path(model: str, arm: str, seed: int) -> Path:
    return CELLS / f"{short(model)}-{arm}-{seed}.json"


def run_cell(model: str, arm: str, seed: int) -> None:
    """One (model, arm, seed) in this process (a child of run_phase)."""
    if cell_path(model, arm, seed).exists():
        return
    ref = reference(model)
    names = gate_names(model, ref)
    if arm in OWALNUTS_ARMS:
        source_commit()
        try:
            cell = run_owalnuts(model, arm, seed, ref, names)
        except Exception as e:  # noqa: BLE001
            cell = failure(model, arm, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
        write_cell(cell)
        return
    try:
        handle = prepare_cmdstan(model) if arm == "cmdstan" else nutpie_model(model)
    except Exception as e:  # noqa: BLE001
        write_cell(failure(model, arm, seed, "compile_error", str(e)[-2000:]))
        return
    try:
        cell = run_cmdstan(model, seed, ref, names, handle) if arm == "cmdstan" else run_nutpie(model, seed, ref, names, handle)
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


def record_run(phase: str) -> None:
    ART.mkdir(parents=True, exist_ok=True)
    machine = ART / "measured_on.json"
    record = json.loads(machine.read_text(encoding="utf-8")) if machine.exists() else {**machine_record(), "runs": []}
    record["runs"].append({"phase": phase, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    machine.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def run_phase(phase: str) -> None:
    log(f"oWALNUTS library source: {source_commit()}")
    if not SMOKE and not (ART / "tests.json").exists():
        raise SystemExit("phase T (`tests`) must run first")
    record_run(phase)
    if phase == "F":
        run_funnel()
        return
    for model, arm in PHASES[phase]:
        for seed in SEEDS:
            if cell_path(model, arm, seed).exists():
                continue
            log(f"== {model} / {arm} / {seed}")
            cmd = [sys.executable, "-I", str(Path(__file__)), "cell", model, arm, str(seed)]
            try:
                cp = subprocess.run(cmd, timeout=TIMEOUT + 600, text=True)
                if cp.returncode != 0:
                    log(f"child for {model}/{arm}/{seed} exited {cp.returncode}")
            except subprocess.TimeoutExpired:
                log(f"child for {model}/{arm}/{seed} timed out")
            if not cell_path(model, arm, seed).exists():
                write_cell(failure(model, arm, seed, "timeout_or_crash", "child process ended without writing the cell"))


def run_funnel() -> None:
    FUNNEL_CELLS.mkdir(parents=True, exist_ok=True)
    for seed in FUNNEL_SEEDS:
        for arm in FUNNEL_SPEC["arms"]:
            out = FUNNEL_CELLS / f"{arm}-{seed}.json"
            if out.exists() or out.with_suffix(".error.json").exists():
                continue
            cmd = [str(FUNNEL), arm, str(FUNNEL_SPEC["warmup"]), str(FUNNEL_SPEC["draws"]), str(seed), str(out)]
            t = time.perf_counter()
            try:
                cp = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
                rc, err = cp.returncode, cp.stderr
            except subprocess.TimeoutExpired:
                rc, err = -1, "timeout"
            if rc != 0 or not out.exists():
                out.with_suffix(".error.json").write_text(json.dumps({"arm": arm, "seed": seed, "returncode": rc, "stderr": err[-3000:]}) + "\n")
                log(f"funnel {arm} {seed}: ERROR {err[-200:]}")
            else:
                log(f"funnel {arm} {seed}: {err.strip().splitlines()[-1][:200] if err.strip() else ''} ({time.perf_counter() - t:.1f}s)")


def run_tests() -> None:
    """Phase T (rule clause R4): the kernel fingerprint test with every flag off, and the new option's tests."""
    ART.mkdir(parents=True, exist_ok=True)
    commit = source_commit()
    results = {}
    for name in PROTOCOL["tests"]["targets"]:
        t = time.perf_counter()
        cp = subprocess.run(["cargo", "test", "--release", "-j4", "--test", name], cwd=str(REPO), capture_output=True, text=True)
        (ART / f"test-{name}.log").write_text(cp.stdout + "\n--- stderr ---\n" + cp.stderr, encoding="utf-8")
        results[name] = {"exit": cp.returncode, "passed": cp.returncode == 0, "seconds": round(time.perf_counter() - t, 1),
                         "summary": [l for l in cp.stdout.splitlines() if l.startswith("test ")]}
        log(f"cargo test --test {name}: exit {cp.returncode}")
    record = {"commit": commit, "rustc": subprocess.run(["rustc", "--version"], capture_output=True, text=True).stdout.strip(),
              "uname": platform.platform(), "results": results, "all_passed": all(r["passed"] for r in results.values()),
              "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (ART / "tests.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")


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
        c.pop("mass_matrix_change_draws_per_chain", None)
        c.pop("mass_diagonal_per_chain", None)
        if c.get("status") == "ok" and c.get("gradients_total"):
            c["wall_per_gradient_us"] = 1e6 * c["wall_seconds"] / c["gradients_total"]
        cells.setdefault(c["model"], {}).setdefault(c["arm"], {})[str(c["seed"])] = c
    return cells


def med(xs: list) -> float | None:
    xs = [x for x in xs if x is not None and isinstance(x, (int, float)) and math.isfinite(x)]
    return statistics.median(xs) if xs else None


def seed_median(cells: dict, model: str, arm: str, key, require_all: bool = True) -> float | None:
    cs = cells.get(model, {}).get(arm, {})
    getter = key if callable(key) else (lambda c: c.get(key))
    vals = [getter(cs[str(s)]) for s in SEEDS if cs.get(str(s), {}).get("status") == "ok"]
    vals = [v for v in vals if v is not None]
    if require_all and len(vals) != len(SEEDS):
        return None
    return med(vals)


def ratio_of_medians(cells: dict, model: str, a: str, b: str, key: str = "min_bulk_ess_per_gradient") -> float | None:
    """v7 convention: seed-median of arm a over seed-median of arm b; None unless every seed is ok on both."""
    va, vb = seed_median(cells, model, a, key), seed_median(cells, model, b, key)
    return va / vb if va is not None and vb else None


def passes(cells: dict, model: str, arm: str) -> int:
    return sum(1 for s in SEEDS if cells.get(model, {}).get(arm, {}).get(str(s), {}).get("passed"))


def phase_per_transition(c: dict, phase: str) -> float | None:
    p = (c.get("warmup_gradients_per_phase") or {}).get(phase)
    return p.get("per_transition") if p else None


def funnel_summary() -> dict:
    out = {}
    exact = FUNNEL_SPEC["exact_p5"]
    for arm in FUNNEL_SPEC["arms"]:
        est, errors, wcalls, rcalls, warm, stops = [], [], [], [], [], 0
        for seed in FUNNEL_SEEDS:
            f = FUNNEL_CELLS / f"{arm}-{seed}.json"
            if not f.exists():
                errors.append(seed)
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            est.append(d["tail_mass"]["estimate"])
            wcalls.append(sum(c["warmup_target_calls"] for c in d["chains_data"]))
            rcalls.append(sum(c["retained_target_calls"] for c in d["chains_data"]))
            warm.extend(c["warmup_transitions"] for c in d["chains_data"])
            stops += sum(1 for c in d["chains_data"] for k in c["stable_metric_checks"] if k["stopped"])
        n = len(est)
        mean = float(np.mean(est)) if n else None
        se = float(np.std(est, ddof=1) / math.sqrt(n)) if n > 1 else None
        held = (n == len(FUNNEL_SEEDS) and se is not None and abs(mean - exact) <= se)
        out[arm] = {"seeds": n, "errors": errors, "pooled_p5": mean, "between_seed_se": se, "exact": exact,
                    "t": (mean - exact) / se if se else None, "held": held, "per_seed": est,
                    "warmup_gradient_share_median": med([w / (w + r) for w, r in zip(wcalls, rcalls)]),
                    "warmup_transitions": sorted(set(warm)), "chains_stopped_early": stops}
    return out


def analyze() -> None:
    cells = load_cells()
    rule = PROTOCOL["decision_rule"]
    tests = json.loads((ART / "tests.json").read_text(encoding="utf-8")) if (ART / "tests.json").exists() else {}
    # ---- descriptive arm
    desc = {}
    for m in HOUSE:
        row = {}
        for arm in ("owalnuts", "cmdstan", "nutpie"):
            row[arm] = {"warmup_share": seed_median(cells, m, arm, "warmup_share", require_all=False),
                        "passes": passes(cells, m, arm),
                        "ok": sum(1 for c in cells.get(m, {}).get(arm, {}).values() if c.get("status") == "ok"),
                        "sampling_gradients_per_transition": seed_median(cells, m, arm, "sampling_gradients_per_transition", require_all=False),
                        "fixed_bins": [med([c.get("warmup_gradients_per_transition_fixed_bins", [None] * 7)[i]
                                            for c in cells.get(m, {}).get(arm, {}).values() if c.get("status") == "ok"]) for i in range(len(FIXED_EDGES) - 1)]}
            if arm != "nutpie":
                row[arm]["per_phase"] = {ph: seed_median(cells, m, arm, functools.partial(phase_per_transition, phase=ph), require_all=False)
                                         for ph in ("initial_fast", "window_0", "window_1", "window_2", "window_3", "window_4", "terminal_fast")}
            else:
                row[arm]["own_phases"] = {ph: seed_median(cells, m, arm, lambda c, ph=ph: ((c.get("warmup_gradients_per_phase_nutpie_own") or {}).get(ph) or {}).get("per_transition"), require_all=False)
                                          for ph in ("metric_adapting", "step_only_final")}
                row[arm]["mass_matrix_last_change_median"] = med([x for c in cells.get(m, {}).get(arm, {}).values() if c.get("status") == "ok"
                                                                  for x in c.get("mass_matrix_last_change_per_chain", [])])
        o, cm, nu = row["owalnuts"]["warmup_share"], row["cmdstan"]["warmup_share"], row["nutpie"]["warmup_share"]
        row["share_diff_vs_cmdstan"] = o - cm if o is not None and cm is not None else None
        row["share_diff_vs_nutpie"] = o - nu if o is not None and nu is not None else None
        row["ess_per_gradient_vs_cmdstan"] = ratio_of_medians(cells, m, "owalnuts", "cmdstan")
        row["ess_per_gradient_vs_nutpie"] = ratio_of_medians(cells, m, "owalnuts", "nutpie")
        row["phase_ratio_vs_cmdstan"] = {ph: (row["owalnuts"]["per_phase"][ph] / row["cmdstan"]["per_phase"][ph])
                                         if row["owalnuts"]["per_phase"][ph] and row["cmdstan"]["per_phase"][ph] else None
                                         for ph in row["owalnuts"]["per_phase"]}
        so, sc = row["owalnuts"]["sampling_gradients_per_transition"], row["cmdstan"]["sampling_gradients_per_transition"]
        row["phase_ratio_vs_cmdstan"]["sampling"] = so / sc if so and sc else None
        desc[m] = row
    diffs = [r["share_diff_vs_cmdstan"] for r in desc.values() if r["share_diff_vs_cmdstan"] is not None]
    pr = PROTOCOL["predictions"]
    p1v = med(diffs)
    wp58 = pr["P2"]["models"]
    p2 = {m: {"vs_cmdstan": desc[m]["share_diff_vs_cmdstan"], "vs_nutpie": desc[m]["share_diff_vs_nutpie"]} for m in wp58}
    p2_held = all(v["vs_cmdstan"] is not None and pr["P2"]["vs_cmdstan_interval"][0] <= v["vs_cmdstan"] <= pr["P2"]["vs_cmdstan_interval"][1]
                  for v in p2.values())
    phase_med = {}
    for ph in ("initial_fast", "window_0", "window_1", "window_2", "window_3", "window_4", "terminal_fast", "sampling"):
        phase_med[ph] = med([r["phase_ratio_vs_cmdstan"][ph] for r in desc.values()])
    slow = med([v for r in desc.values() for ph in ("window_0", "window_1", "window_2", "window_3", "window_4")
                for v in [r["phase_ratio_vs_cmdstan"][ph]] if v is not None])
    predictions = {
        "P1_median_share_diff_vs_cmdstan": {"value": p1v, "interval": pr["P1"]["interval"], "models": len(diffs),
                                            "held": p1v is not None and pr["P1"]["interval"][0] <= p1v <= pr["P1"]["interval"][1]},
        "P2_wp58_overlap_share_diff_vs_cmdstan": {"value": p2, "interval": pr["P2"]["vs_cmdstan_interval"], "held": p2_held},
        "P3_initial_fast_per_transition_ratio": {"value": phase_med["initial_fast"], "threshold": pr["P3"]["initial_fast_min"],
                                                 "held": phase_med["initial_fast"] is not None and phase_med["initial_fast"] >= pr["P3"]["initial_fast_min"]},
        "P4_slow_window_per_transition_ratio": {"value": slow, "interval": pr["P4"]["interval"],
                                                "held": slow is not None and pr["P4"]["interval"][0] <= slow <= pr["P4"]["interval"][1]},
        "phase_ratio_medians": phase_med,
    }
    # ---- candidates
    funnel = funnel_summary()
    base_passes = sum(passes(cells, m, "owalnuts") for m in HOUSE)
    results = {}
    for cand in CANDIDATES:
        per_model = {m: ratio_of_medians(cells, m, cand, "owalnuts") for m in HOUSE}
        vals = [v for v in per_model.values() if v]
        g = geomean(vals)
        cp = sum(passes(cells, m, cand) for m in HOUSE)
        errors = [f"{m}/{s}: {c.get('status')}" for m in HOUSE for s, c in cells.get(m, {}).get(cand, {}).items() if c.get("status") != "ok"]
        hi_z = [f"{m}/{s}={c['max_abs_z']:.2f}" for m in HOUSE for s, c in cells.get(m, {}).get(cand, {}).items()
                if c.get("passed") and c.get("max_abs_z") is not None and c["max_abs_z"] > 4]
        fa = funnel.get(PROTOCOL["owalnuts_arms"][cand]["harness_arm"], {})
        clauses = {
            "R1_gates_not_lower": {"value": {"candidate": cp, "default": base_passes}, "held": cp >= base_passes},
            "R2_geomean_ess_per_total_gradient_ge": {"value": g, "threshold": rule["geomean_threshold"], "models": len(vals),
                                                     "excluded_models": [m for m, v in per_model.items() if not v],
                                                     "per_model": per_model,
                                                     "held": len(vals) > 0 and math.isfinite(g) and g >= rule["geomean_threshold"]},
            "R3_funnel_p5_within_1_se": {"value": {k: fa.get(k) for k in ("pooled_p5", "between_seed_se", "t", "seeds")}, "held": bool(fa.get("held"))},
            "R4_kernel_fingerprint_flags_off": {"value": tests.get("results", {}).get("kernel_fingerprint", {}).get("exit"),
                                                "held": bool(tests.get("results", {}).get("kernel_fingerprint", {}).get("passed"))},
        }
        spend = {
            "warmup_share_median_over_models": med([seed_median(cells, m, cand, "warmup_share", require_all=False) for m in HOUSE]),
            "warmup_gradients_ratio_vs_default_median": med([ratio_of_medians(cells, m, cand, "owalnuts", "warmup_gradients") for m in HOUSE]),
            "total_gradients_ratio_vs_default_median": med([ratio_of_medians(cells, m, cand, "owalnuts", "gradients_total") for m in HOUSE]),
            "min_bulk_ess_ratio_vs_default_median": med([ratio_of_medians(cells, m, cand, "owalnuts", "min_bulk_ess") for m in HOUSE]),
            "sampling_only_ratio_vs_default_geomean": geomean([ratio_of_medians(cells, m, cand, "owalnuts", "min_bulk_ess_per_gradient_sampling") or 0 for m in HOUSE]),
            "chains_stopped_early": sum(1 for m in HOUSE for c in cells.get(m, {}).get(cand, {}).values()
                                        for ch in (c.get("stable_metric_checks") or []) for k in ch if k.get("stopped")),
            "passes_per_model": {m: passes(cells, m, cand) for m in HOUSE},
            "passing_cells_above_abs_z_4": hi_z,
        }
        results[cand] = {"clauses": clauses, "passes_rule": all(v["held"] for v in clauses.values()), "errors": errors, "spend": spend}
    summary = {"schema": "warmup-spend-v1-summary", "descriptive": desc, "predictions": predictions,
               "default_passes": base_passes, "default_passes_per_model": {m: passes(cells, m, "owalnuts") for m in HOUSE},
               "competitor_passes": {a: sum(passes(cells, m, a) for m in HOUSE) for a in ("cmdstan", "nutpie")},
               "candidates": results, "funnel": funnel, "tests": tests,
               "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
               "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    write_table(summary, cells)


def write_table(s: dict, cells: dict) -> None:
    def f(x, fmt=".3f"):
        return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)

    lines = ["# WP73 results", "", f"Seeds {SEEDS}; 4 chains x 1,000/1,000 (`half`: 500/1,000); funnel {FUNNEL_SPEC['warmup']}/{FUNNEL_SPEC['draws']} x {len(FUNNEL_SEEDS)} seeds; pinned to cores 4-7, co-tenanted.", "",
             "## Descriptive arm: warmup share of all gradients (seed medians)", "",
             "| model | oWALNUTS | CmdStan | nutpie | oW - Cmd | oW - nutpie | oW passes | Cmd passes | nutpie passes | ESS/grad oW/Cmd | oW/nutpie |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for m, r in s["descriptive"].items():
        lines.append(f"| {m} | {f(r['owalnuts']['warmup_share'])} | {f(r['cmdstan']['warmup_share'])} | {f(r['nutpie']['warmup_share'])} | "
                     f"{f(r['share_diff_vs_cmdstan'], '+.3f')} | {f(r['share_diff_vs_nutpie'], '+.3f')} | {r['owalnuts']['passes']}/3 | {r['cmdstan']['passes']}/3 | {r['nutpie']['passes']}/3 | "
                     f"{f(r['ess_per_gradient_vs_cmdstan'])} | {f(r['ess_per_gradient_vs_nutpie'])} |")
    lines += ["", "## Gradients per transition by warmup phase (seed medians), oWALNUTS / CmdStan", "",
              "| model | initial fast | w0 | w1 | w2 | w3 | w4 | terminal | sampling | oW initial | Cmd initial | nutpie metric-adapting | nutpie step-only | nutpie last metric change |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for m, r in s["descriptive"].items():
        pr = r["phase_ratio_vs_cmdstan"]
        lines.append(f"| {m} | " + " | ".join(f(pr[k], ".2f") for k in ("initial_fast", "window_0", "window_1", "window_2", "window_3", "window_4", "terminal_fast", "sampling")) +
                     f" | {f(r['owalnuts']['per_phase']['initial_fast'], '.0f')} | {f(r['cmdstan']['per_phase']['initial_fast'], '.0f')} | "
                     f"{f(r['nutpie']['own_phases']['metric_adapting'], '.1f')} | {f(r['nutpie']['own_phases']['step_only_final'], '.1f')} | {f(r['nutpie']['mass_matrix_last_change_median'], '.0f')} |")
    lines += ["", "## Predictions", "", "```", json.dumps(s["predictions"], indent=1, default=str), "```", "",
              "## Candidates against the frozen rule", "",
              f"Default passes {s['default_passes']}/51 (CmdStan {s['competitor_passes']['cmdstan']}, nutpie {s['competitor_passes']['nutpie']}).", "",
              "| candidate | R1 passes vs default | R2 geomean ESS / total gradient vs default | R3 funnel P5 ± s.e. | R4 fingerprint | rule | warmup grads vs default | total grads vs default | min ESS vs default | early-stopped chains |",
              "|---|---|---|---|---|---|---:|---:|---:|---:|"]
    for cand, r in s["candidates"].items():
        cl, sp = r["clauses"], r["spend"]
        fv = cl["R3_funnel_p5_within_1_se"]["value"]
        lines.append(f"| {cand} | {cl['R1_gates_not_lower']['value']['candidate']} vs {cl['R1_gates_not_lower']['value']['default']} ({cl['R1_gates_not_lower']['held']}) | "
                     f"{f(cl['R2_geomean_ess_per_total_gradient_ge']['value'])} over {cl['R2_geomean_ess_per_total_gradient_ge']['models']} ({cl['R2_geomean_ess_per_total_gradient_ge']['held']}) | "
                     f"{f(fv.get('pooled_p5'), '.4f')} ± {f(fv.get('between_seed_se'), '.4f')} ({cl['R3_funnel_p5_within_1_se']['held']}) | {cl['R4_kernel_fingerprint_flags_off']['held']} | **{r['passes_rule']}** | "
                     f"{f(sp['warmup_gradients_ratio_vs_default_median'])} | {f(sp['total_gradients_ratio_vs_default_median'])} | {f(sp['min_bulk_ess_ratio_vs_default_median'])} | {sp['chains_stopped_early']} |")
    lines += ["", "## Per-model ESS per total gradient vs default (seed medians) and passes", "",
              "| model | default passes | " + " | ".join(f"{c} ratio | {c} passes" for c in s["candidates"]) + " |",
              "|---|---:|" + "---:|---:|" * len(s["candidates"])]
    for m in HOUSE:
        lines.append(f"| {m} | {s['default_passes_per_model'][m]}/3 | " + " | ".join(
            f"{f(r['clauses']['R2_geomean_ess_per_total_gradient_ge']['per_model'][m])} | {r['spend']['passes_per_model'][m]}/3" for r in s["candidates"].values()) + " |")
    lines += ["", "## Funnel sanity (P(omega < -5), exact 0.0478)", "", "| arm | seeds | pooled P5 | s.e. | t | within 1 s.e. | warmup share | warmup lengths | early-stopped chains |", "|---|---:|---:|---:|---:|---|---:|---|---:|"]
    for arm, r in s["funnel"].items():
        lines.append(f"| {arm} | {r['seeds']} | {f(r['pooled_p5'], '.4f')} | {f(r['between_seed_se'], '.4f')} | {f(r['t'], '+.2f')} | {r['held']} | {f(r['warmup_gradient_share_median'])} | {r['warmup_transitions']} | {r['chains_stopped_early']} |")
    (ART / "results-table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "run":
        phase = next((a.split("=", 1)[1] for a in args[1:] if a.startswith("--phase=")), None)
        if phase not in ("A", "B", "F"):
            raise SystemExit("run needs --phase=A, B or F")
        run_phase(phase)
    elif args and args[0] == "cell":
        run_cell(args[1], args[2], int(args[3]))
    elif args and args[0] == "tests":
        run_tests()
    elif args and args[0] == "analyze":
        analyze()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
