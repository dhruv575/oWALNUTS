#!/usr/bin/env python3
"""WP65 part (c) driver: wall per gradient of oWALNUTS-via-BridgeStan dispatch paths vs CmdStan 2.39.0.

A copy of `STUDIES/posteriordb_bench_v7/run_posteriordb.py` (WP56), parametrised for this study;
every change is listed in PREREGISTRATION.md ("Changes to the v7 code"). The metric, gate,
posteriordb and CmdStan functions are verbatim.

    python run_bench.py run                  # the fixed-16 models x {cmdstan, owalnuts, owalnuts-serialised, owalnuts-threaded}
    python run_bench.py cell <model> <arm>   # one model/arm, all seeds (child process)
    python run_bench.py analyze              # artifacts/bench/summary.json + results-table.md

Each cell writes `artifacts/bench/cells/<model>-<arm>-<seed>.json` (metrics, no draws) and
`artifacts/bench/draws/<model>-<arm>-<seed>.npz` (constrained draws on the gate parameter set;
the oWALNUTS arms also keep their unconstrained draws for the bit-identity check). Failures are
recorded as cells with status != "ok". Run the driver under `taskset -c 4-7`; children inherit it.
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
BENCH = PROTOCOL["part_c_wall_per_gradient"]
# Smoke tests (non-evidence model and seed, before the freeze) redirect with WP65_SMOKE_ART / _MODELS / _SEEDS (as v7's V7_SMOKE_*).
ART = Path(os.environ["WP65_SMOKE_ART"]) if os.environ.get("WP65_SMOKE_ART") else HERE / "artifacts" / "bench"
CELLS = ART / "cells"
DRAWS = ART / "draws"
MODELS = Path(os.environ["WP65_SMOKE_MODELS"]) if os.environ.get("WP65_SMOKE_MODELS") else HERE / "models"
CMDSTAN_MODELS = MODELS / "cmdstan"
LANE = Path(os.environ.get("WP65_LANE", "~/lanes/bridgestan_linux_dispatch_v1")).expanduser()
PDB_PATH = Path(os.environ.get("WP65_POSTERIORDB", "~/infra/posteriordb")).expanduser() / PROTOCOL["posteriordb"]["path"]
CMDSTAN_HOME = LANE / "cmdstan-2.39.0"
HARNESS = HERE / "target" / "release" / "harness"
# arm -> (harness mode, dispatch, library build)
OWALNUTS_ARMS = {arm: (spec["mode"], spec["dispatch"], spec["build"]) for arm, spec in BENCH["owalnuts_arms"].items()}
ARMS = ["cmdstan"] + list(OWALNUTS_ARMS)
FIXED16 = PROTOCOL["fixed_non_arma_models"]
ALL_MODELS = FIXED16
HOUSE = FIXED16
GATES_ONLY = []
SEEDS = [int(x) for x in os.environ["WP65_SMOKE_SEEDS"].split(",")] if os.environ.get("WP65_SMOKE_SEEDS") else BENCH["seeds"]
TIMEOUT = BENCH["cell_timeout_seconds"]


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
        "schema": "bridgestan-linux-dispatch-v1-cell-metrics",
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
        "schema": "bridgestan-linux-dispatch-v1-cell-metrics", "model": model, "arm": arm, "seed": seed,
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
    cell = metrics(model, arm, seed, draws, names, ref, out["wall_seconds"], grads_total, grads_sampling,
                   sum(c["divergences"] for c in chains), sum(c["maximum_depth_stops"] for c in chains), extra)
    save_draws(model, arm, seed, draws, names, unconstrained=unc)
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


def run_all(models: list[str], arms: list[str]) -> None:
    ART.mkdir(parents=True, exist_ok=True)
    log(f"oWALNUTS library source: {source_commit()}")
    machine = ART / "measured_on.json"
    record = json.loads(machine.read_text(encoding="utf-8")) if machine.exists() else {**machine_record(), "runs": []}
    record["runs"].append({"arms": arms, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    machine.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    for model in models:
        log(f"== {model}")
        for arm in arms:
            if all(cell_path(model, arm, s).exists() for s in SEEDS):
                continue
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


KEYS = ["min_bulk_ess_per_second", "min_tail_ess_per_second", "min_bulk_ess_per_gradient", "min_tail_ess_per_gradient",
        "wall_seconds", "gradients_total", "min_bulk_ess", "min_tail_ess", "max_rank_rhat", "max_abs_z",
        "wall_per_gradient_us", "max_depth_stops", "chain_disagreement_max",
        "retained_nonfinite_position_rejections", "warmup_nonfinite_position_rejections"]


def model_arm_entry(seeds: dict) -> dict:
    ok = [c for c in seeds.values() if c.get("status") == "ok"]
    entry = {"n_cells": len(seeds), "n_ok": len(ok), "n_passed": sum(1 for c in ok if c["passed"]),
             "statuses": {s: c.get("status") for s, c in seeds.items()},
             "errors": {s: c.get("error", "")[:300] for s, c in seeds.items() if c.get("status") != "ok"},
             "passed_by_seed": {s: c.get("passed") for s, c in seeds.items()},
             "failed_gates": {s: [g for g, v in c.get("gates", {}).items() if not v] for s, c in seeds.items()},
             "divergences": [c["divergences"] for c in ok],
             "frozen_chains": [c.get("frozen_chains", 0) for c in ok],
             "chain_warnings": {s: c.get("chain_warnings") for s, c in seeds.items() if c.get("chain_warnings")},
             "agreement_flags": sum(1 for c in ok if c.get("agreement_flag")),
             "final_step_size": [c.get("final_step_size") or c.get("step_size") for c in ok]}
    for k in KEYS:
        vals = [c[k] for c in ok if c.get(k) is not None and math.isfinite(c[k])]
        entry[k] = {"median": statistics.median(vals) if vals else None,
                    "min": min(vals) if vals else None, "max": max(vals) if vals else None, "values": vals}
    return entry


def ratio_geomean(per_model: dict, models: list[str], ours: str, theirs: str, key: str) -> tuple[float, list[str]]:
    ms = [m for m in models if per_model[m][ours]["n_ok"] == len(SEEDS) and per_model[m][theirs]["n_ok"] == len(SEEDS)]
    return geomean([per_model[m][ours][key]["median"] / per_model[m][theirs][key]["median"] for m in ms]), ms


def analyze() -> None:
    cells: dict = {}
    for path in sorted(CELLS.glob("*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        c.pop("parameters", None)
        c.pop("warmup_step_trace_every_50", None)
        if c.get("status") == "ok" and c.get("gradients_total"):
            c["wall_per_gradient_us"] = 1e6 * c["wall_seconds"] / c["gradients_total"]
        cells.setdefault(c["model"], {}).setdefault(c["arm"], {})[str(c["seed"])] = c
    per_model = {m: {arm: model_arm_entry(cells.get(m, {}).get(arm, {})) for arm in ARMS} for m in FIXED16}
    pass_counts = {arm: {"passed": sum(per_model[m][arm]["n_passed"] for m in FIXED16),
                         "recorded": sum(per_model[m][arm]["n_cells"] for m in FIXED16),
                         "ok": sum(per_model[m][arm]["n_ok"] for m in FIXED16)} for arm in ARMS}

    def ratio(ours: str, theirs: str, key: str) -> dict:
        value, models = ratio_geomean(per_model, FIXED16, ours, theirs, key)
        per = {m: per_model[m][ours][key]["median"] / per_model[m][theirs][key]["median"] for m in models}
        return {"value": value, "models": models, "n_models": len(models), "per_model": per}

    wall = {f"{a}_over_cmdstan": ratio(a, "cmdstan", "wall_per_gradient_us") for a in OWALNUTS_ARMS}
    wall["owalnuts-serialised_over_owalnuts"] = ratio("owalnuts-serialised", "owalnuts", "wall_per_gradient_us")
    wall["owalnuts-threaded_over_owalnuts"] = ratio("owalnuts-threaded", "owalnuts", "wall_per_gradient_us")
    ess = {f"{a}_over_cmdstan": ratio(a, "cmdstan", "min_bulk_ess_per_gradient") for a in OWALNUTS_ARMS}

    def identity(other: str) -> dict:
        rows = {}
        for m in FIXED16:
            a = cells.get(m, {}).get("owalnuts", {})
            b = cells.get(m, {}).get(other, {})
            for s in map(str, SEEDS):
                ca, cb = a.get(s), b.get(s)
                if not (ca and cb and ca.get("status") == "ok" and cb.get("status") == "ok"):
                    rows[m] = None
                    continue
                rows[m] = {"draws_identical": ca["unconstrained_draws_sha256"] == cb["unconstrained_draws_sha256"],
                           "gradients_identical": ca["gradients_total"] == cb["gradients_total"]}
        both = [r for r in rows.values() if r is not None]
        return {"per_model": rows, "comparable": len(both),
                "identical": sum(1 for r in both if r["draws_identical"] and r["gradients_identical"])}

    ident_serialised = identity("owalnuts-serialised")
    ident_threaded = identity("owalnuts-threaded")
    owal_errors = {arm: [f"{m}/{s}: {c.get('status')}" for m in FIXED16 for s, c in cells.get(m, {}).get(arm, {}).items()
                         if c.get("status") != "ok"] for arm in OWALNUTS_ARMS}
    owal_errors_total = sum(len(v) for v in owal_errors.values())
    complete = {a: wall[f"{a}_over_cmdstan"]["n_models"] == len(FIXED16) for a in OWALNUTS_ARMS}
    c1 = wall["owalnuts_over_cmdstan"]["value"]
    c2 = wall["owalnuts-serialised_over_cmdstan"]["value"]
    c3 = wall["owalnuts-serialised_over_owalnuts"]["value"]
    c6 = wall["owalnuts-threaded_over_owalnuts"]["value"]
    pr = BENCH["predictions"]
    predictions = {
        "C1_replicated_over_cmdstan_wall_per_gradient_le": {"threshold": pr["C1"]["threshold"], "value": c1,
            "n_models": wall["owalnuts_over_cmdstan"]["n_models"],
            "held": (c1 <= pr["C1"]["threshold"]) if complete["owalnuts"] else None},
        "C2_serialised_over_cmdstan_wall_per_gradient_ge": {"threshold": pr["C2"]["threshold"], "value": c2,
            "n_models": wall["owalnuts-serialised_over_cmdstan"]["n_models"],
            "held": (c2 >= pr["C2"]["threshold"]) if complete["owalnuts-serialised"] else None},
        "C3_serialised_over_replicated_in_range": {"range": pr["C3"]["range"], "value": c3,
            "n_models": wall["owalnuts-serialised_over_owalnuts"]["n_models"],
            "held": (pr["C3"]["range"][0] <= c3 <= pr["C3"]["range"][1])
            if wall["owalnuts-serialised_over_owalnuts"]["n_models"] == len(FIXED16) else None},
        "C4_replicated_serialised_bit_identical_every_model": {"value": ident_serialised,
            "held": ident_serialised["comparable"] == len(FIXED16) and ident_serialised["identical"] == len(FIXED16)},
        "C5_no_owalnuts_error_any_arm": {"value": owal_errors, "held": owal_errors_total == 0},
        "C6_threaded_over_replicated_wall_per_gradient_le": {"threshold": pr["C6"]["threshold"], "value": c6,
            "n_models": wall["owalnuts-threaded_over_owalnuts"]["n_models"],
            "held": (c6 <= pr["C6"]["threshold"])
            if wall["owalnuts-threaded_over_owalnuts"]["n_models"] == len(FIXED16) else None},
        "reported_threaded_bit_identical_to_replicated": {"value": ident_threaded},
        "reported_bulk_ess_per_gradient_vs_cmdstan": {"value": {k: v["value"] for k, v in ess.items()}},
        "reported_pass_counts_of_16": {"value": pass_counts},
    }
    summary = {
        "schema": "bridgestan-linux-dispatch-v1-bench-summary",
        "source_commit_under_test": PROTOCOL["source_commit_under_test"],
        "pass_counts": pass_counts, "wall_per_gradient": wall, "bulk_ess_per_gradient": ess,
        "bit_identity_serialised": ident_serialised, "bit_identity_threaded": ident_threaded,
        "predictions": predictions,
        "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "per_model": per_model, "cells": cells,
    }
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")

    def f(x, fmt):
        return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)

    lines = ["# WP65 part (c): wall per gradient on Linux, fixed-16, one seed", "",
             f"Seed {SEEDS[0]}; 4 chains x 1,000/1,000; every process pinned to cores 4-7 on a shared box with "
             "three other lanes active (pinned, co-tenanted walls). `wall/grad` = wall seconds around the sampler call "
             "(oWALNUTS start search excluded, CmdStan process launch and CSV I/O included, as v7) divided by all "
             "gradients including warmup. `gates` = rank R-hat <= 1.01, bulk/tail ESS >= 400, zero retained divergences.", "",
             "| model | arm | execution | gates | wall s | grads | wall/grad us | min bulk ESS | bulk ESS/grad x1e3 | max abs z |",
             "|---|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for m in FIXED16:
        for arm in ARMS:
            e = per_model[m][arm]
            c = next(iter(cells.get(m, {}).get(arm, {}).values()), {})
            status = f"{e['n_passed']}/{e['n_cells']}" if e["n_ok"] else ("/".join(sorted(set(e["statuses"].values()))) or "not run")
            lines.append(
                f"| {m} | {arm} | {c.get('execution') or ('cmdstan' if arm == 'cmdstan' else '—')} | {status} | "
                f"{f(e['wall_seconds']['median'], '.2f')} | {f(e['gradients_total']['median'], ',.0f')} | "
                f"{f(e['wall_per_gradient_us']['median'], '.3f')} | {f(e['min_bulk_ess']['median'], ',.0f')} | "
                f"{f((e['min_bulk_ess_per_gradient']['median'] or float('nan')) * 1e3, '.3f')} | {f(e['max_abs_z']['max'], '.2f')} |")
    lines += ["", "## Wall per gradient, geometric mean over models complete on both sides", "",
              "| ratio | models | geomean |", "|---|---:|---:|"]
    for k, v in wall.items():
        lines.append(f"| {k} | {v['n_models']} | {f(v['value'], '.3f')} |")
    lines += ["", "| per model | " + " | ".join(wall) + " |", "|---|" + "---:|" * len(wall)]
    for m in FIXED16:
        lines.append(f"| {m} | " + " | ".join(f(v["per_model"].get(m), ".3f") for v in wall.values()) + " |")
    lines += ["", "## Preregistered predictions", "", "| prediction | value | held |", "|---|---|---|"]
    for k, v in predictions.items():
        val = v["value"]
        if isinstance(val, dict) and "identical" in val:
            val = f"{val['identical']}/{val['comparable']} identical"
        lines.append(f"| {k} | {f(val, '.3f') if isinstance(val, float) else val} | {v.get('held', 'reported')} |")
    (ART / "results-table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] == "run":
        models, arms = FIXED16, ARMS
        for a in args[1:]:
            if a.startswith("--models="):
                models = a.split("=", 1)[1].split(",")
            elif a.startswith("--arms="):
                arms = a.split("=", 1)[1].split(",")
        run_all(models, arms)
    elif args[0] == "cell":
        run_model_arm(args[1], args[2])
    elif args[0] == "analyze":
        analyze()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
