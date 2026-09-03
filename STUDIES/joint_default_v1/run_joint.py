#!/usr/bin/env python3
"""Joint default study driver: the posteriordb v3 harness restricted to four oWALNUTS arms
(owalnuts-da = current defaults, owalnuts-rhosum = UTurnRule::MomentumSum, owalnuts-stanreg =
DiagonalMetricRegularization::Stan, owalnuts-joint = both), fresh seeds, CmdStan and nutpie cited
from posteriordb_bench_v3.

    python run_joint.py build            # compile every model with BridgeStan (no sampling)
    python run_joint.py run              # every model/arm/seed in protocol order (resumable)
    python run_joint.py run --models=a,b --arms=owalnuts-da,owalnuts-joint
    python run_joint.py cell <model> <arm>   # one model/arm, all seeds (used as a child process)
    python run_joint.py checks           # funnel tail mass (both tunings) and Eight Schools strict track, all arms
    python run_joint.py analyze          # artifacts/summary.json + results-table.md (posteriordb, funnel, Eight Schools, decision)

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
PDB_PATH = HERE / PROTOCOL["posteriordb"]["path"]
HARNESS = HERE / "target" / "release" / "posteriordb-cell.exe"
FUNNEL = HERE / "target" / "release" / "funnel.exe"
EIGHT_SCHOOLS = HERE / "target" / "release" / "eight-schools.exe"
ARMS = ["owalnuts-da", "owalnuts-rhosum", "owalnuts-stanreg", "owalnuts-joint"]
BASE = "owalnuts-da"
CANDIDATES = ["owalnuts-rhosum", "owalnuts-stanreg", "owalnuts-joint"]
DECIDED = "owalnuts-joint"
SHORT = {a: a.removeprefix("owalnuts-") for a in ARMS}   # the binaries' arm names: da, rhosum, stanreg, joint
OWALNUTS_MODE = SHORT
V3_SUMMARY = HERE.parent / "posteriordb_bench_v3" / "artifacts" / "summary.json"
FUNNEL_TUNINGS = ["paper", "defaults"]
EIGHT_SCHOOLS_FUNCTIONALS = ["mu", "tau", "mean_theta", "sd_theta", "theta_1", "theta_8"]
SEEDS = PROTOCOL["seeds"]
TIMEOUT = PROTOCOL["cell_timeout_seconds"]
os.environ.setdefault("MAKE", "mingw32-make")
# BridgeStan make arguments: no STAN_THREADS (v1 wall-gap finding: on mingw-w64
# GCC it costs 9-16x per gradient). The harness loads one library copy per chain
# thread (ReplicatedStanTarget). Every model is compiled fresh for this study
# (the earlier studies' libraries were not kept; same BridgeStan 2.9.0 / Stan 2.39.0 / flags).
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
        "schema": "joint-default-v1-cell-metrics",
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
        "schema": "joint-default-v1-cell-metrics", "model": model, "arm": arm, "seed": seed,
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
        "u_turn": out["tuning"].get("u_turn"),
        "metric_regularization": out["tuning"].get("metric_regularization"),
        "min_mass_diagonal": min(min(c["mass_diagonal"]) for c in chains),
        "max_mass_diagonal": max(max(c["mass_diagonal"]) for c in chains),
        "warmup_divergences": sum(c["warmup_divergences"] for c in chains),
        "retained_depth_histogram": [sum(x) for x in zip(*(c["retained_depth_histogram"] for c in chains))],
        "retained_refinement_level_histogram": [sum(x) for x in zip(*(c["retained_refinement_level_histogram"] for c in chains))],
        "algorithm_revision": out["algorithm_revision"],
        "paper_adaptation_revision": out["paper_adaptation_revision"],
        "unconstrained_dimension": out["dimension"],
    }
    cell = metrics(model, arm, seed, draws, ref["names"], ref, out["wall_seconds"], grads_total, grads_sampling,
                   sum(c["divergences"] for c in chains), sum(c["maximum_depth_stops"] for c in chains), extra)
    save_draws(model, arm, seed, draws, ref["names"], unconstrained=unc)
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


# --------------------------------------------------------------------------- side checks


def run_checks() -> None:
    """Funnel tail mass at both tunings and the Eight Schools strict track, every arm, every seed (resumable)."""
    fdir = ART / "funnel"
    edir = ART / "eight_schools"
    fdir.mkdir(parents=True, exist_ok=True)
    edir.mkdir(parents=True, exist_ok=True)
    for tuning in FUNNEL_TUNINGS:
        for arm in ARMS:
            short_arm = SHORT[arm]
            for seed in SEEDS:
                out = fdir / f"{tuning}-{short_arm}-{seed}.json"
                if out.exists():
                    continue
                log(f"funnel {tuning} {short_arm} {seed}")
                cp = subprocess.run([str(FUNNEL), tuning, short_arm, str(seed), str(out)], capture_output=True, text=True)
                log(f"  {cp.stderr.strip()[-300:]}")
    for arm in ARMS:
        short_arm = SHORT[arm]
        for seed in SEEDS:
            out = edir / f"{short_arm}-{seed}.json"
            if out.exists():
                continue
            log(f"eight schools {short_arm} {seed}")
            cp = subprocess.run([str(EIGHT_SCHOOLS), short_arm, str(seed), str(PROTOCOL["eight_schools"]["repetitions"]), str(out)],
                                capture_output=True, text=True)
            if cp.returncode != 0:
                log(f"  failed: {cp.stderr.strip()[-300:]}")


# --------------------------------------------------------------------------- analysis


def geomean(xs: list[float]) -> float:
    xs = [x for x in xs if x and math.isfinite(x) and x > 0]
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs))) if xs else float("nan")


def fmt(x, spec):
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, spec)


def analyze_funnel() -> dict:
    """Per (tuning, arm): per-seed tail mass with the MCSE z (the gate) and the batch-means z; seed-pooled estimate."""
    out = {}
    for tuning in FUNNEL_TUNINGS:
        for arm in ARMS:
            short_arm = SHORT[arm]
            cells = []
            for seed in SEEDS:
                path = ART / "funnel" / f"{tuning}-{short_arm}-{seed}.json"
                if path.exists():
                    cells.append(json.loads(path.read_text(encoding="utf-8")))
            entry = {"n_cells": len(cells), "per_seed": {}}
            means = []
            for c in cells:
                t = c["tail_mass"]
                entry["per_seed"][str(c["seed"])] = {
                    "estimate": t["estimate"], "mcse": t["mcse"], "z": t["z"],
                    "batch_means_se": t["batch_means_se"], "z_batch_means": t["z_batch_means"],
                    "per_chain": t["per_chain"],
                    "target_calls_total": c["target_calls_total"], "retained_target_calls": c["retained_target_calls"],
                    "omega_bulk_ess": c["omega"]["bulk_ess"], "omega_tail_ess": c["omega"]["tail_ess"],
                    "omega_rhat": c["omega"]["rhat"], "omega_variance": c["omega"]["variance"],
                    "wall_seconds": c["wall_seconds"],
                    "depth_caps": sum(ch["depth_caps"] for ch in c["chains_data"]),
                    "divergences": sum(ch["divergences"] for ch in c["chains_data"]),
                    "refinement_exhaustions": sum(ch["refinement_exhaustions"] for ch in c["chains_data"]),
                    "final_max_error": [ch["final_max_error"] for ch in c["chains_data"]],
                    "final_step_size": [ch["final_step_size"] for ch in c["chains_data"]],
                }
                means.extend(c["batch_means"])
            zs = [p["z"] for p in entry["per_seed"].values()]
            entry["all_seeds_abs_z_le_2"] = bool(len(zs) == len(SEEDS) and all(abs(z) <= 2.0 for z in zs))
            entry["max_abs_z"] = max((abs(z) for z in zs), default=None)
            if means:
                arr = np.asarray(means)
                est = float(arr.mean())
                se = float(arr.std(ddof=1) / math.sqrt(len(arr)))
                exact = cells[0]["tail_mass"]["exact"]
                entry["pooled"] = {"estimate": est, "batch_means_se": se, "z_batch_means": (est - exact) / se, "batches": int(len(arr)),
                                   "exact": exact, "target_calls_total": sum(c["target_calls_total"] for c in cells),
                                   "ess_bulk_omega_total": sum(c["omega"]["bulk_ess"] for c in cells)}
                entry["pooled"]["ess_per_call"] = entry["pooled"]["ess_bulk_omega_total"] / entry["pooled"]["target_calls_total"]
            out[f"{tuning}/{short_arm}"] = entry
    return out


def eight_schools_functionals(samples: np.ndarray) -> dict[str, np.ndarray]:
    """samples: (chains, draws, 10) unconstrained (mu, log tau, z_1..z_8) -> the six v38 functionals."""
    mu = samples[..., 0]
    tau = np.exp(samples[..., 1])
    theta = mu[..., None] + tau[..., None] * samples[..., 2:]
    return {"mu": mu, "tau": tau, "mean_theta": theta.mean(-1), "sd_theta": theta.std(-1, ddof=1),
            "theta_1": theta[..., 0], "theta_8": theta[..., 7]}


def analyze_eight_schools() -> dict:
    import arviz as az

    out = {}
    for arm in ARMS:
        short_arm = SHORT[arm]
        entry = {"per_seed": {}}
        for seed in SEEDS:
            path = ART / "eight_schools" / f"{short_arm}-{seed}.json"
            if not path.exists():
                continue
            c = json.loads(path.read_text(encoding="utf-8"))
            samples = np.asarray([ch["samples"] for ch in c["chains_data"]], dtype=np.float64)
            fs = eight_schools_functionals(samples)
            ds = az.convert_to_dataset({k: v for k, v in fs.items()})
            bulk = {k: float(az.ess(ds, var_names=[k], method="bulk")[k].values) for k in fs}
            tail = {k: float(az.ess(ds, var_names=[k], method="tail", prob=(0.05, 0.95))[k].values) for k in fs}
            rh = {k: float(az.rhat(ds, var_names=[k], method="rank")[k].values) for k in fs}
            calls = c["callbacks_started"][0]
            wall = statistics.median(c["wall_seconds"])
            entry["per_seed"][str(seed)] = {
                "callbacks_started": calls, "wall_median": wall, "wall_all": c["wall_seconds"],
                "bit_identical_repetitions": len(set([c["sample_sha256"]])) == 1,
                "bulk_ess": bulk, "tail_ess": tail, "rhat": rh,
                "min_bulk_ess": min(bulk.values()), "min_tail_ess": min(tail.values()), "max_rhat": max(rh.values()),
                "min_bulk_ess_per_call": min(bulk.values()) / calls, "min_tail_ess_per_call": min(tail.values()) / calls,
                "min_bulk_ess_per_second": min(bulk.values()) / wall,
                "divergences": sum(ch["divergences"] for ch in c["chains_data"]),
                "max_depth_stops": sum(ch["maximum_depth_stops"] for ch in c["chains_data"]),
                "refinement_exhaustions": sum(ch["refinement_exhaustions"] for ch in c["chains_data"]),
                "final_step_size": [ch["final_step_size"] for ch in c["chains_data"]],
            }
        ps = entry["per_seed"].values()
        if ps:
            entry["median_min_bulk_ess_per_call"] = statistics.median(p["min_bulk_ess_per_call"] for p in ps)
            entry["median_min_tail_ess_per_call"] = statistics.median(p["min_tail_ess_per_call"] for p in ps)
            entry["geomean_min_bulk_ess_per_call"] = geomean([p["min_bulk_ess_per_call"] for p in ps])
            entry["all_healthy"] = all(p["min_bulk_ess"] >= 400 and p["min_tail_ess"] >= 400 and p["max_rhat"] <= 1.01
                                       and p["divergences"] == 0 and p["refinement_exhaustions"] == 0 for p in ps)
        out[short_arm] = entry
    return out


def analyze() -> None:
    models = PROTOCOL["models"]
    cells = {}
    for path in sorted(CELLS.glob("*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        c.pop("parameters", None)
        if c.get("status") == "ok" and c.get("gradients_total"):
            c["wall_per_gradient_us"] = 1e6 * c["wall_seconds"] / c["gradients_total"]
        cells.setdefault(c["model"], {}).setdefault(c["arm"], {})[str(c["seed"])] = c
    keys = ["min_bulk_ess_per_second", "min_tail_ess_per_second", "min_bulk_ess_per_gradient", "min_tail_ess_per_gradient",
            "min_bulk_ess_per_gradient_sampling", "wall_seconds", "gradients_total", "gradients_sampling", "min_bulk_ess",
            "min_tail_ess", "max_rank_rhat", "max_abs_z", "wall_per_gradient_us"]
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
                     "agreement_flags": sum(1 for c in ok if c["agreement_flag"]),
                     "failing_gates": {s: [g for g, v in c["gates"].items() if not v] for s, c in seeds.items() if c.get("status") == "ok" and not c["passed"]},
                     "final_step_size": {s: c.get("final_step_size") for s, c in seeds.items() if c.get("status") == "ok"},
                     "u_turn": sorted(set(c.get("u_turn", "?") for c in ok)),
                     "metric_regularization": sorted(set(c.get("metric_regularization", "?") for c in ok))}
            for k in keys:
                vals = [c[k] for c in ok if k in c and c[k] is not None and math.isfinite(c[k])]
                entry[k] = {"median": statistics.median(vals) if vals else None,
                            "min": min(vals) if vals else None, "max": max(vals) if vals else None, "values": vals}
            row[arm] = entry
        per_model[model] = row

    # The decision statistic: seed-median min bulk ESS/gradient, candidate over the default arm, per model.
    v3 = json.loads(V3_SUMMARY.read_text(encoding="utf-8"))["per_model"] if V3_SUMMARY.exists() else {}
    ratios = {}
    for model in models:
        base = per_model[model][BASE]
        row = {}
        for arm in CANDIDATES:
            cand = per_model[model][arm]

            def r(k, cand=cand, base=base):
                x, y = cand[k]["median"], base[k]["median"]
                return (x / y) if (x and y) else None

            def per_seed(k, arm=arm):
                out = []
                for s in SEEDS:
                    a = cells.get(model, {}).get(arm, {}).get(str(s), {})
                    b = cells.get(model, {}).get(BASE, {}).get(str(s), {})
                    out.append((a[k] / b[k]) if a.get("status") == "ok" and b.get("status") == "ok" and b.get(k) else None)
                return out

            row[arm] = {"r_bulk_ess_per_gradient": r("min_bulk_ess_per_gradient"),
                        "r_bulk_ess_per_gradient_sampling": r("min_bulk_ess_per_gradient_sampling"),
                        "r_bulk_ess_per_second": r("min_bulk_ess_per_second"),
                        "r_tail_ess_per_gradient": r("min_tail_ess_per_gradient"),
                        "r_gradients": r("gradients_total"),
                        "r_min_bulk_ess": r("min_bulk_ess"),
                        "per_seed_r_bulk_ess_per_gradient": per_seed("min_bulk_ess_per_gradient"),
                        "gates_candidate": cand["n_passed"], "gates_base": base["n_passed"]}
        ref = v3.get(model, {})
        cm = (ref.get("cmdstan", {}).get("min_bulk_ess_per_gradient") or {}).get("median")
        nt = (ref.get("nutpie", {}).get("min_bulk_ess_per_gradient") or {}).get("median")
        v3da = (ref.get("owalnuts-da", {}).get("min_bulk_ess_per_gradient") or {}).get("median")
        for arm in ARMS:
            x = per_model[model][arm]["min_bulk_ess_per_gradient"]["median"]
            row.setdefault(arm, {})["vs_cmdstan_v3"] = (x / cm) if (x and cm) else None
            row[arm]["vs_nutpie_v3"] = (x / nt) if (x and nt) else None
            row[arm]["vs_v3_da"] = (x / v3da) if (x and v3da) else None
            row[arm]["cmdstan_v3_gates"] = ref.get("cmdstan", {}).get("n_passed")
            row[arm]["nutpie_v3_gates"] = ref.get("nutpie", {}).get("n_passed")
            row[arm]["v3_da_gates"] = ref.get("owalnuts-da", {}).get("n_passed")
        ratios[model] = row

    def overall(arm):
        rs = {m: ratios[m][arm]["r_bulk_ess_per_gradient"] for m in models}
        have = {m: r for m, r in rs.items() if r}
        return {"models_with_ratio": len(have), "geomean_r_bulk_ess_per_gradient": geomean(list(have.values())),
                "min_r_bulk_ess_per_gradient": min(have.values()) if have else None,
                "argmin": min(have, key=have.get) if have else None,
                "models_below_0.85": {m: r for m, r in have.items() if r < 0.85},
                "models_above_1.15": {m: r for m, r in have.items() if r > 1.15},
                "geomean_r_bulk_ess_per_gradient_sampling": geomean([ratios[m][arm]["r_bulk_ess_per_gradient_sampling"] for m in models if ratios[m][arm]["r_bulk_ess_per_gradient_sampling"]]),
                "geomean_r_bulk_ess_per_second": geomean([ratios[m][arm]["r_bulk_ess_per_second"] for m in models if ratios[m][arm]["r_bulk_ess_per_second"]]),
                "geomean_r_gradients": geomean([ratios[m][arm]["r_gradients"] for m in models if ratios[m][arm]["r_gradients"]]),
                "cells_passed": sum(per_model[m][arm]["n_passed"] for m in models),
                "cells_passed_base": sum(per_model[m][BASE]["n_passed"] for m in models),
                "n_frozen_cells": sum(per_model[m][arm]["n_frozen_cells"] for m in models),
                "geomean_vs_cmdstan_v3": geomean([ratios[m][arm]["vs_cmdstan_v3"] for m in models if ratios[m][arm]["vs_cmdstan_v3"]]),
                "geomean_vs_nutpie_v3": geomean([ratios[m][arm]["vs_nutpie_v3"] for m in models if ratios[m][arm]["vs_nutpie_v3"]]),
                "geomean_vs_v3_da": geomean([ratios[m][arm]["vs_v3_da"] for m in models if ratios[m][arm]["vs_v3_da"]])}
    overall_arms = {arm: overall(arm) for arm in CANDIDATES}
    overall_arms[BASE] = {
        "cells_passed": sum(per_model[m][BASE]["n_passed"] for m in models),
        "n_frozen_cells": sum(per_model[m][BASE]["n_frozen_cells"] for m in models),
        "geomean_vs_cmdstan_v3": geomean([ratios[m][BASE]["vs_cmdstan_v3"] for m in models if ratios[m][BASE]["vs_cmdstan_v3"]]),
        "geomean_vs_nutpie_v3": geomean([ratios[m][BASE]["vs_nutpie_v3"] for m in models if ratios[m][BASE]["vs_nutpie_v3"]]),
        "geomean_vs_v3_da": geomean([ratios[m][BASE]["vs_v3_da"] for m in models if ratios[m][BASE]["vs_v3_da"]])}

    funnel = analyze_funnel()
    eight = analyze_eight_schools()
    dr = PROTOCOL["decision_rule"]
    jo = overall_arms[DECIDED]
    js = SHORT[DECIDED]
    bs = SHORT[BASE]

    def es_ratio(short_arm):
        a = eight.get(short_arm, {}).get("geomean_min_bulk_ess_per_call")
        b = eight.get(bs, {}).get("geomean_min_bulk_ess_per_call")
        return (a / b) if (a and b) else None

    funnel_joint = {t: funnel.get(f"{t}/{js}", {}) for t in FUNNEL_TUNINGS}
    funnel_z = {t: [p["z"] for p in e.get("per_seed", {}).values()] for t, e in funnel_joint.items()}
    funnel_complete = all(len(z) == len(SEEDS) for z in funnel_z.values())
    criteria = {
        "C1_geomean_ratio_ge_1.15": {"value": jo["geomean_r_bulk_ess_per_gradient"], "threshold": dr["geomean_min_ratio"],
                                     "held": bool(jo["geomean_r_bulk_ess_per_gradient"] >= dr["geomean_min_ratio"]) if jo["models_with_ratio"] else None,
                                     "models": jo["models_with_ratio"]},
        "C2_no_model_below_0.85": {"value": jo["min_r_bulk_ess_per_gradient"], "argmin": jo["argmin"], "threshold": dr["per_model_min_ratio"],
                                   "held": bool(jo["min_r_bulk_ess_per_gradient"] >= dr["per_model_min_ratio"]) if jo["min_r_bulk_ess_per_gradient"] else None,
                                   "models_below": jo["models_below_0.85"]},
        "C3_gates_ge_da": {"value": jo["cells_passed"], "threshold": jo["cells_passed_base"],
                           "held": bool(jo["cells_passed"] >= jo["cells_passed_base"]) if jo["models_with_ratio"] else None},
        "C4_funnel_abs_z_le_2_every_seed_both_tunings": {
            "value": funnel_z, "threshold": dr["funnel_max_abs_z"],
            "controls": {f"{t}/{SHORT[a]}": [p["z"] for p in funnel.get(f"{t}/{SHORT[a]}", {}).get("per_seed", {}).values()]
                         for t in FUNNEL_TUNINGS for a in ARMS if a != DECIDED},
            "held": all(abs(z) <= dr["funnel_max_abs_z"] for zs in funnel_z.values() for z in zs) if funnel_complete else None},
        "C5_eight_schools_ess_per_call_ge_0.9": {"value": es_ratio(js), "threshold": dr["eight_schools_min_ratio"],
                                                 "held": bool(es_ratio(js) >= dr["eight_schools_min_ratio"]) if es_ratio(js) else None,
                                                 "other_arms": {SHORT[a]: es_ratio(SHORT[a]) for a in CANDIDATES if a != DECIDED}},
    }
    decision = all(c["held"] is True for c in criteria.values())

    healthy = PROTOCOL["expectations"]["healthy_regressions"]
    earn = "earnings-logearn_interaction"
    sbl = "sblrc-blr"
    jr = {m: ratios[m][DECIDED]["r_bulk_ess_per_gradient"] for m in models}
    predictions = {
        "P1_joint_ge_1.2_on_healthy_regressions": {"value": {m: jr[m] for m in healthy},
                                                   "held": all(jr[m] is not None and jr[m] >= 1.2 for m in healthy) if all(jr[m] for m in healthy) else None},
        "P2_earnings_gate_recovered": {"value": {SHORT[a]: per_model[earn][a]["n_passed"] for a in ARMS},
                                       "held": bool(per_model[earn][DECIDED]["n_passed"] >= per_model[earn][BASE]["n_passed"]
                                                    and per_model[earn][DECIDED]["n_passed"] > per_model[earn]["owalnuts-stanreg"]["n_passed"]) if per_model[earn][DECIDED]["n_ok"] else None,
                                       "reading": "joint passes at least as many earnings seeds as da and more than stanreg alone"},
        "P3_sblrc_ge_5x": {"value": jr[sbl], "held": bool(jr[sbl] >= 5.0) if jr[sbl] else None},
    }

    summary = {
        "schema": "joint-default-v1-summary",
        "decision": {"flip_to_joint_default": decision, "criteria": criteria, "rule": dr, "predictions": predictions},
        "overall": overall_arms,
        "ratios": ratios,
        "funnel": funnel,
        "eight_schools": eight,
        "protocol_sha256": __import__("hashlib").sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "per_model": per_model,
        "cells": cells,
    }
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    f = fmt
    seeds_txt = f"{SEEDS[0]}–{SEEDS[-1]}"
    lines = ["# Joint default study — results", "",
             f"Seed medians over 3 seeds ({seeds_txt}) of the per-cell minimum over reference parameters; `gates` = cells passing "
             "R-hat <= 1.01, bulk/tail ESS >= 400, zero divergences; `div` = sampling divergences per seed; "
             "`max|z|` = worst posterior-mean z against the posteriordb reference. Arms: `owalnuts-da` = the current `sampler` defaults "
             "(`UTurnRule::Endpoints`, `DiagonalMetricRegularization::TowardUnit`), `owalnuts-rhosum` = `MomentumSum`, "
             "`owalnuts-stanreg` = `Stan` regularisation, `owalnuts-joint` = both; everything else `Sampler` defaults "
             "(`h0 0.5`, depth 10, eight levels, `delta 1`, dual averaging 0.8, WP24 warmup rule, adapted diagonal, cache).", "",
             "## Per-model cells", "",
             "| model | arm | gates | wall s | grads | min bulk ESS | min tail ESS | bulk ESS/s | bulk ESS/grad x1e3 | max R-hat | div | depth caps | max abs z | final h (seed 1, per chain) |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---|"]
    for model in models:
        for arm in ARMS:
            e = per_model[model][arm]
            status = f"{e['n_passed']}/{e['n_cells']}" if e["n_ok"] else "/".join(sorted(set(e["statuses"].values()))) or "not run"
            h = e["final_step_size"].get(str(SEEDS[0]))
            h_txt = ", ".join(f"{x:.3g}" for x in h) if h else "—"
            lines.append(
                f"| {model} | {SHORT[arm]} | {status} | {f(e['wall_seconds']['median'], '.2f')} | {f(e['gradients_total']['median'], ',.0f')} | "
                f"{f(e['min_bulk_ess']['median'], ',.0f')} | {f(e['min_tail_ess']['median'], ',.0f')} | "
                f"{f(e['min_bulk_ess_per_second']['median'], ',.1f')} | "
                f"{f((e['min_bulk_ess_per_gradient']['median'] or float('nan')) * 1e3, '.3f')} | {f(e['max_rank_rhat']['median'], '.4f')} | "
                f"{','.join(str(d) for d in e['divergences'])} | {','.join(str(d) for d in e['max_depth_stops'])} | {f(e['max_abs_z']['median'], '.2f')} | {h_txt} |")
    lines += ["", "## The decision statistic: seed-median min bulk ESS/gradient, candidate / da, per model", "",
              "`vs CmdStan` / `vs nutpie` = this study's seed median over the v3 seed median (cited, seeds 79101–79103); `da vs v3 da` = reproduction of the v3 default arm on fresh seeds.", "",
              "| model | gates da / rhosum / stanreg / joint | da ESS/grad x1e3 | rhosum / da | stanreg / da | **joint / da** | joint per seed | grads joint/da | da vs CmdStan | joint vs CmdStan | da vs nutpie | joint vs nutpie | da vs v3 da |",
              "|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|"]
    for model in models:
        r = ratios[model]
        pm = per_model[model]
        lines.append(f"| {model} | {' / '.join(str(pm[a]['n_passed']) for a in ARMS)} | "
                     f"{f((pm[BASE]['min_bulk_ess_per_gradient']['median'] or float('nan')) * 1e3, '.3f')} | "
                     f"{f(r['owalnuts-rhosum']['r_bulk_ess_per_gradient'], '.2f')} | {f(r['owalnuts-stanreg']['r_bulk_ess_per_gradient'], '.2f')} | "
                     f"**{f(r[DECIDED]['r_bulk_ess_per_gradient'], '.2f')}** | "
                     f"{', '.join(f(x, '.2f') for x in r[DECIDED]['per_seed_r_bulk_ess_per_gradient'])} | {f(r[DECIDED]['r_gradients'], '.2f')} | "
                     f"{f(r[BASE]['vs_cmdstan_v3'], '.2f')} | {f(r[DECIDED]['vs_cmdstan_v3'], '.2f')} | "
                     f"{f(r[BASE]['vs_nutpie_v3'], '.2f')} | {f(r[DECIDED]['vs_nutpie_v3'], '.2f')} | {f(r[BASE]['vs_v3_da'], '.2f')} |")
    lines += ["", "| arm | cells passed | geomean ratio to da (ESS/grad) | min model ratio | models < 0.85 | models > 1.15 | geomean grads ratio | geomean ESS/s ratio | sampling-only ESS/grad ratio | geomean vs CmdStan v3 | geomean vs nutpie v3 | geomean vs v3 da | frozen cells |",
              "|---|---:|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for arm in ARMS:
        o = overall_arms[arm]
        if arm == BASE:
            lines.append(f"| {SHORT[arm]} | {o['cells_passed']} | 1 | — | — | — | 1 | 1 | 1 | {f(o['geomean_vs_cmdstan_v3'], '.3f')} | {f(o['geomean_vs_nutpie_v3'], '.3f')} | {f(o['geomean_vs_v3_da'], '.3f')} | {o['n_frozen_cells']} |")
        else:
            lines.append(f"| {SHORT[arm]} | {o['cells_passed']} | **{f(o['geomean_r_bulk_ess_per_gradient'], '.3f')}** | {f(o['min_r_bulk_ess_per_gradient'], '.2f')} ({o['argmin']}) | "
                         f"{', '.join(f'{m} {v:.2f}' for m, v in o['models_below_0.85'].items()) or 'none'} | {', '.join(f'{m} {v:.2f}' for m, v in o['models_above_1.15'].items()) or 'none'} | "
                         f"{f(o['geomean_r_gradients'], '.3f')} | {f(o['geomean_r_bulk_ess_per_second'], '.3f')} | {f(o['geomean_r_bulk_ess_per_gradient_sampling'], '.3f')} | "
                         f"{f(o['geomean_vs_cmdstan_v3'], '.3f')} | {f(o['geomean_vs_nutpie_v3'], '.3f')} | {f(o['geomean_vs_v3_da'], '.3f')} | {o['n_frozen_cells']} |")
    lines += ["", "## Funnel tail mass `P(omega < -5)` (exact 0.0478), 4 x 2,000 / 20,000 per seed", "",
              "`z` = (estimate − exact) / MCSE of the indicator (`diagnostics::mcse_mean`, the WP28 statistic; the gate is |z| <= 2 on every seed); "
              "`z_bm` = the WP26 batch-means statistic per seed; pooled = three seeds pooled with batch-means s.e. At the paper tuning the metric is the identity, so the regularisation is inert (`stanreg` = `da`, `joint` = `rhosum`).", "",
              "| tuning | arm | per-seed estimate (z) | all abs(z) <= 2 | per-seed z_bm | pooled estimate (z_bm) | omega bulk ESS / R-hat per seed | target calls (3 seeds) | omega bulk ESS / call x1e3 | depth caps | divergences | retained exhaustions | final h (seed 1) |",
              "|---|---|---|---|---|---|---|---:|---:|---|---|---|---|"]
    for key, e in funnel.items():
        if not e.get("per_seed"):
            lines.append(f"| {key.split('/')[0]} | {key.split('/')[1]} | not run |")
            continue
        ps = list(e["per_seed"].values())
        p = e.get("pooled", {})
        h = ps[0]["final_step_size"]
        est_txt = ", ".join(f"{x['estimate']:.4f} ({x['z']:+.2f})" for x in ps)
        ess_txt = ", ".join(f"{x['omega_bulk_ess']:.0f} / {x['omega_rhat']:.3f}" for x in ps)
        lines.append(f"| {key.split('/')[0]} | {key.split('/')[1]} | {est_txt} | "
                     f"{'**yes**' if e['all_seeds_abs_z_le_2'] else 'no'} | {', '.join(format(x['z_batch_means'], '+.2f') for x in ps)} | "
                     f"{f(p.get('estimate'), '.4f')} ({f(p.get('z_batch_means'), '+.2f')}) | "
                     f"{ess_txt} | {f(p.get('target_calls_total'), ',')} | {f(1e3 * p['ess_per_call'] if p else None, '.3f')} | "
                     f"{','.join(str(x['depth_caps']) for x in ps)} | {','.join(str(x['divergences']) for x in ps)} | {','.join(str(x['refinement_exhaustions']) for x in ps)} | "
                     f"{', '.join(f'{x:.3g}' for x in h)} |")
    lines += ["", "## Eight Schools strict track (v38/v9 settings: h 0.3, depth 8, eight levels, delta 1, accept 0.95, 4 x 1,000/1,000, threads 1, `walnutpie` facade)", "",
              "| arm | seed | calls | min bulk ESS | min tail ESS | max R-hat | bulk ESS/call | tail ESS/call | wall s (median) | div | exhaustions |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    for short_arm, e in eight.items():
        for seed, p in e["per_seed"].items():
            lines.append(f"| {short_arm} | {seed} | {p['callbacks_started']:,} | {p['min_bulk_ess']:,.0f} | {p['min_tail_ess']:,.0f} | {p['max_rhat']:.4f} | "
                         f"{p['min_bulk_ess_per_call']:.5f} | {p['min_tail_ess_per_call']:.5f} | {p['wall_median']:.4f} | {p['divergences']} | {p['refinement_exhaustions']} |")
    lines += ["", "| arm | geomean min bulk ESS/call | median | ratio to da | all seeds healthy |", "|---|---:|---:|---:|---|"]
    for short_arm, e in eight.items():
        if "geomean_min_bulk_ess_per_call" in e:
            lines.append(f"| {short_arm} | {e['geomean_min_bulk_ess_per_call']:.5f} | {e['median_min_bulk_ess_per_call']:.5f} | {f(es_ratio(short_arm), '.3f')} | {e['all_healthy']} |")
    lines += ["", "## Preregistered decision rule (on `joint`)", "", "| criterion | value | threshold | held |", "|---|---|---|---|"]
    for k, c in criteria.items():
        v = c["value"]
        if isinstance(v, dict):
            v = "; ".join(f"{a} " + ", ".join(f"{z:+.2f}" for z in b) for a, b in v.items())
        elif isinstance(v, float):
            v = f"{v:.3f}" + (f" ({c['argmin']})" if c.get("argmin") else "")
        lines.append(f"| {k} | {v} | {c['threshold']} | {c['held']} |")
    lines += ["", "## Preregistered predictions (not gated)", "", "| prediction | value | held |", "|---|---|---|"]
    for k, c in predictions.items():
        v = c["value"]
        if isinstance(v, dict):
            v = ", ".join(f"{a.split('-')[0]} {f(b, '.2f') if isinstance(b, float) else b}" for a, b in v.items())
        elif isinstance(v, float):
            v = f"{v:.2f}"
        lines.append(f"| {k} | {v} | {c['held']} |")
    lines += ["", f"**Decision: {'flip `Tuning::default()` / `Adaptation::default()` to `UTurnRule::MomentumSum` + `DiagonalMetricRegularization::Stan`' if decision else 'keep the current defaults'}** (all five criteria must hold)."]
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
    elif args[0] == "build":
        for model in PROTOCOL["models"]:
            log(f"build {model}")
            prepare_bridgestan(model)
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
