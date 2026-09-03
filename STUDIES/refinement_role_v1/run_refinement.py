#!/usr/bin/env python3
"""Refinement-role study driver (WP34): the posteriordb v3/v5 protocol restricted to oWALNUTS arms that
change the step-adaptation rule and `delta`, with a level-0 leaf-error trace, CmdStan cited from v5.

    python run_refinement.py build                 # compile every BridgeStan model (no STAN_THREADS)
    python run_refinement.py instrument            # phase 1: arm `da` on the v5 seed 87101, every model (trace + v5 reproduction)
    python run_refinement.py run                   # phase 2: every model/arm/seed in protocol order (resumable)
    python run_refinement.py run --models=a,b --arms=da,da06
    python run_refinement.py cell <model> <arm> [instrument]   # one model/arm, all seeds (child process)
    python run_refinement.py checks                # funnel (defaults) and Eight Schools strict track, every arm, three seeds
    python run_refinement.py analyze               # artifacts/summary.json + results-table.md

Each cell writes `artifacts/cells/<model>-<arm>-<seed>.json` (metrics, no draws) and
`artifacts/draws/<model>-<arm>-<seed>.npz` (constrained draws on the reference parameter set).
Failures are recorded as cells with status != "ok".
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
INSTR = ART / "instrumentation"
MODELS = HERE / "models"
PDB_PATH = HERE / PROTOCOL["posteriordb"]["path"]
HARNESS = HERE / "target" / "release" / "posteriordb-cell.exe"
FUNNEL = HERE / "target" / "release" / "funnel.exe"
EIGHT_SCHOOLS = HERE / "target" / "release" / "eight-schools.exe"
ARMS = PROTOCOL["arms_order"]
BASELINE = "da"
V5 = HERE.parent / "posteriordb_bench_v5" / "artifacts"
V5_SUMMARY = V5 / "summary.json"
SEEDS = PROTOCOL["seeds"]
INSTRUMENT_SEED = PROTOCOL["instrumentation"]["seed"]
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


# --------------------------------------------------------------------------- v5 CmdStan reference


def v5_cells() -> dict:
    """The v5 per-cell metrics (CmdStan and the DA arm), keyed model -> arm -> seed."""
    out: dict = {}
    for path in sorted((V5 / "cells").glob("*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        c.pop("parameters", None)
        out.setdefault(c["model"], {}).setdefault(c["arm"], {})[str(c["seed"])] = c
    return out


def cmdstan_reference_step(model: str, cells: dict | None = None) -> float | None:
    """Median over the twelve v5 CmdStan chains (three seeds x four chains) of the adapted step."""
    cells = cells or v5_cells()
    steps = [s for c in cells.get(model, {}).get("cmdstan", {}).values() if c.get("status") == "ok"
             for s in c.get("step_size", [])]
    return float(statistics.median(steps)) if steps else None


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
        "schema": "refinement-role-v1-cell-metrics",
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
        "schema": "refinement-role-v1-cell-metrics", "model": model, "arm": arm, "seed": seed,
        "status": status, "error": message, "passed": False,
        "gates": {"no_sampler_error": False}, **extra,
    }


def cell_dir(instrument: bool) -> Path:
    return (INSTR / "cells") if instrument else CELLS


def cell_path(model: str, arm: str, seed: int, instrument: bool = False) -> Path:
    return cell_dir(instrument) / f"{short(model)}-{arm}-{seed}.json"


def write_cell(cell: dict, instrument: bool = False) -> None:
    d = cell_dir(instrument)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{short(cell['model'])}-{cell['arm']}-{cell['seed']}.json"
    path.write_text(json.dumps(cell, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    s = cell["status"]
    if s == "ok":
        log(f"  {cell['arm']} {cell['seed']}: wall {cell['wall_seconds']:.2f}s grads {cell['gradients_total']} "
            f"minbulk {cell['min_bulk_ess']:.0f} mintail {cell['min_tail_ess']:.0f} rhat {cell['max_rank_rhat']:.4f} "
            f"div {cell['divergences']} max|z| {cell['max_abs_z']:.2f} passed {cell['passed']} "
            f"h {cell['median_step']:.4g} (ref {cell['reference_step']}) refined {cell['refined_leaf_fraction']:.4f}")
    else:
        log(f"  {cell['arm']} {cell['seed']}: {s}: {cell.get('error', '')[:200]}")


def save_draws(model: str, arm: str, seed: int, draws: np.ndarray, names: list[str], instrument: bool, **more) -> None:
    d = (INSTR / "draws") if instrument else DRAWS
    d.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(d / f"{short(model)}-{arm}-{seed}.npz", draws=draws, names=np.asarray(names), **more)


# --------------------------------------------------------------------------- the arm


def mean_or_none(values) -> float | None:
    vals = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    return float(sum(vals) / len(vals)) if vals else None


def trace_summary(chains: list[dict]) -> dict:
    """Pool the per-chain leaf-error trace summaries (draw-weighted means of fractions and statistics)."""
    out: dict = {}
    labels = list(chains[0]["leaf_error_trace"]["steps"].keys())
    for label in labels:
        levels = []
        for level in range(chains[0]["leaf_error_trace"]["levels"]):
            rows = [c["leaf_error_trace"]["steps"][label]["levels"][level] for c in chains
                    if label in c["leaf_error_trace"]["steps"]]
            n = sum(r["n"] for r in rows)
            agg = {"n": n, "nonfinite": sum(r["nonfinite"] for r in rows)}
            for k in ("frac_abs_gt_0.25", "frac_abs_gt_0.5", "frac_abs_gt_1", "frac_abs_gt_2", "frac_abs_gt_1000",
                      "mean_exp_neg_abs", "mean_stan_accept"):
                agg[k] = sum(r[k] * r["n"] for r in rows) / n if n else float("nan")
            for k in ("abs_q50", "abs_q90", "abs_q95", "abs_q99"):
                # serde writes NaN quantiles (a chain whose traced leaves were all nonfinite) as null
                finite = [r[k] for r in rows if isinstance(r[k], (int, float)) and math.isfinite(r[k])]
                agg[k] = float(statistics.median(finite)) if finite else float("nan")
            levels.append(agg)
        steps = [c["leaf_error_trace"]["steps"][label]["step"] for c in chains if label in c["leaf_error_trace"]["steps"]]
        out[label] = {"step_median": float(statistics.median(steps)), "step_per_chain": steps, "levels": levels}
    return out


def run_owalnuts(model: str, arm: str, seed: int, ref: dict, instrument: bool, h_ref: float | None) -> dict:
    import bridgestan as bs

    so, data = prepare_bridgestan(model)
    raw_dir = (INSTR / "draws") if instrument else DRAWS
    raw = raw_dir / f"{short(model)}-{arm}-{seed}.raw.json"
    raw_dir.mkdir(parents=True, exist_ok=True)
    if raw.exists():
        raw.unlink()
    cmd = [str(HARNESS), str(so), str(data), arm, str(seed), str(raw), "4"] + ([str(h_ref)] if h_ref else [])
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
    level_built = [sum(x) for x in zip(*(c["retained_work"]["refinement_level_built"] for c in chains))]
    built = sum(level_built)
    stops: dict[str, int] = {}
    for c in chains:
        for k, v in c["retained_stop_histogram"].items():
            stops[k] = stops.get(k, 0) + v
    steps = [c["final_step_size"] for c in chains]
    median_step = float(statistics.median(steps))
    retained_transitions = out["retained"] * out["chains"]
    extra = {
        "final_step_size": steps,
        "median_step": median_step,
        "reference_step": h_ref,
        "step_ratio_vs_cmdstan": (median_step / h_ref) if h_ref else None,
        "final_max_error": [c["final_max_error"] for c in chains],
        "invalid_stops": sum(c["invalid_stops"] for c in chains),
        "refinement_exhaustions": sum(c["refinement_exhaustions"] for c in chains),
        "recoverable_failures_total": out["recoverable_failures_total"],
        "refinement_exhaustions_per_chain": [c["refinement_exhaustions"] for c in chains],
        "frozen_chains": sum(1 for c in chains if c["refinement_exhaustions"] > out["retained"] // 2),
        "start_search_calls": out["init"]["start_search_calls"],
        "tuning": out["tuning"],
        "warmup_config": out["warmup_config"],
        "max_refinement_levels": out["tuning"]["max_refinement_levels"],
        "mass_diagonal_max": [max(c["mass_diagonal"]) for c in chains],
        "mass_diagonal_min": [min(c["mass_diagonal"]) for c in chains],
        "warmup_divergences": sum(c["warmup_divergences"] for c in chains),
        "retained_depth_histogram": [sum(x) for x in zip(*(c["retained_depth_histogram"] for c in chains))],
        "retained_refinement_level_histogram": [sum(x) for x in zip(*(c["retained_refinement_level_histogram"] for c in chains))],
        "retained_refinement_level_built": level_built,
        "retained_leaves_built": built,
        "refined_leaf_fraction": (built - level_built[0]) / built if built else float("nan"),
        "refined_leaf_fraction_by_level": [x / built for x in level_built] if built else None,
        "leaves_per_transition": built / retained_transitions,
        "gradients_per_leaf": grads_sampling / built if built else float("nan"),
        "retained_stop_histogram": stops,
        "reverse_coarser_stop_fraction": stops.get("reverse_coarser_accepted", 0) / retained_transitions,
        "retained_reverse_coarser_stops": sum(c["retained_work"]["reverse_coarser_stops"] for c in chains),
        "retained_reverse_coarser_rejections": sum(c["retained_work"]["reverse_coarser_rejections"] for c in chains),
        "retained_forward_refinement_attempts": sum(c["retained_work"]["forward_refinement_attempts"] for c in chains),
        "retained_target_calls_reverse": sum(c["retained_work"]["target_calls_reverse"] for c in chains),
        "retained_mean_acceptance_statistic": mean_or_none([c["retained_mean_acceptance_statistic"] for c in chains]),
        "retained_max_energy_error_histogram": {
            "bins_upper": chains[0]["retained_max_energy_error_histogram"]["bins_upper"],
            "counts": [sum(x) for x in zip(*(c["retained_max_energy_error_histogram"]["counts"] for c in chains))]},
        "paper_adaptation_updates": [len(c["paper_adaptation_updates"]) for c in chains],
        "paper_final_max_error": [c["final_max_error"] for c in chains],
        "trace": trace_summary(chains),
        "trace_target_calls": out["trace_target_calls"],
        "algorithm_revision": out["algorithm_revision"],
        "paper_adaptation_revision": out["paper_adaptation_revision"],
        "unconstrained_dimension": out["dimension"],
    }
    cell = metrics(model, arm, seed, draws, ref["names"], ref, out["wall_seconds"], grads_total, grads_sampling,
                   sum(c["divergences"] for c in chains), sum(c["maximum_depth_stops"] for c in chains), extra)
    save_draws(model, arm, seed, draws, ref["names"], instrument, unconstrained=unc)
    return cell


# --------------------------------------------------------------------------- orchestration


def run_model_arm(model: str, arm: str, instrument: bool) -> None:
    """All seeds of one (model, arm) in this process."""
    ref = reference(model)
    h_ref = cmdstan_reference_step(model)
    seeds = [INSTRUMENT_SEED] if instrument else SEEDS
    for seed in seeds:
        if cell_path(model, arm, seed, instrument).exists():
            continue
        try:
            cell = run_owalnuts(model, arm, seed, ref, instrument, h_ref)
        except Exception as e:  # noqa: BLE001
            cell = failure(model, arm, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
        write_cell(cell, instrument)


def build_all(models: list[str]) -> None:
    for model in models:
        log(f"== build {model}")
        try:
            prepare_bridgestan(model)
        except Exception as e:  # noqa: BLE001
            log(f"bridgestan compile failed for {model}: {str(e)[-500:]}")


def run_all(models: list[str], arms: list[str], instrument: bool) -> None:
    ART.mkdir(exist_ok=True)
    machine = ART / "measured_on.json"
    if not machine.exists():
        machine.write_text(json.dumps({
            "platform": platform.platform(), "processor": platform.processor(),
            "cpu_count": os.cpu_count(), "python": sys.version.split()[0],
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "note": "shared machine; other agents may run concurrently; walls are upper bounds",
        }, indent=2) + "\n", encoding="utf-8")
    seeds = [INSTRUMENT_SEED] if instrument else SEEDS
    for model in models:
        log(f"== {model}")
        try:
            prepare_bridgestan(model)
        except Exception as e:  # noqa: BLE001
            log(f"bridgestan compile failed for {model}: {str(e)[-500:]}")
            for arm in arms:
                for seed in seeds:
                    if not cell_path(model, arm, seed, instrument).exists():
                        write_cell(failure(model, arm, seed, "compile_error", str(e)[-2000:]), instrument)
        for arm in arms:
            if all(cell_path(model, arm, s, instrument).exists() for s in seeds):
                continue
            if not (MODELS / f"{short(model)}_model.so").exists():
                for seed in seeds:
                    if not cell_path(model, arm, seed, instrument).exists():
                        write_cell(failure(model, arm, seed, "compile_error", "bridgestan library missing"), instrument)
                continue
            cmd = [sys.executable, str(Path(__file__)), "cell", model, arm] + (["instrument"] if instrument else [])
            try:
                cp = subprocess.run(cmd, timeout=TIMEOUT * len(seeds) + 600, text=True)
                if cp.returncode != 0:
                    log(f"child for {model}/{arm} exited {cp.returncode}")
            except subprocess.TimeoutExpired:
                log(f"child for {model}/{arm} timed out")
            for seed in seeds:
                if not cell_path(model, arm, seed, instrument).exists():
                    write_cell(failure(model, arm, seed, "timeout_or_crash", "child process ended without writing the cell"), instrument)


# --------------------------------------------------------------------------- side checks


def run_checks(arms: list[str]) -> None:
    """The funnel tail-mass row at the sampler defaults and the Eight Schools strict track, every arm, every seed (resumable)."""
    fdir = ART / "funnel"
    edir = ART / "eight_schools"
    fdir.mkdir(parents=True, exist_ok=True)
    edir.mkdir(parents=True, exist_ok=True)
    for arm in arms:
        for seed in SEEDS:
            out = fdir / f"defaults-{arm}-{seed}.json"
            if out.exists():
                continue
            log(f"funnel defaults {arm} {seed}")
            cp = subprocess.run([str(FUNNEL), "defaults", arm, str(seed), str(out)], capture_output=True, text=True)
            log(f"  {cp.stderr.strip()[-300:]}")
    for arm in arms:
        for seed in SEEDS:
            out = edir / f"{arm}-{seed}.json"
            if out.exists():
                continue
            log(f"eight schools {arm} {seed}")
            cp = subprocess.run([str(EIGHT_SCHOOLS), arm, str(seed), str(PROTOCOL["eight_schools"]["repetitions"]), str(out)],
                                capture_output=True, text=True)
            if cp.returncode != 0:
                log(f"  failed: {cp.stderr.strip()[-300:]}")


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
                "final_max_error": [ch["final_max_error"] for ch in c["chains_data"]],
            }
        zs = [p["z"] for p in entry["per_seed"].values()]
        entry["complete"] = len(zs) == len(SEEDS)
        entry["all_seeds_abs_z_le_2"] = bool(entry["complete"] and all(abs(z) <= 2.0 for z in zs))
        entry["max_abs_z"] = max((abs(z) for z in zs), default=None)
        out[arm] = entry
    return out


def eight_schools_functionals(samples: np.ndarray) -> dict[str, np.ndarray]:
    mu = samples[..., 0]
    tau = np.exp(samples[..., 1])
    theta = mu[..., None] + tau[..., None] * samples[..., 2:]
    return {"mu": mu, "tau": tau, "mean_theta": theta.mean(-1), "sd_theta": theta.std(-1, ddof=1),
            "theta_1": theta[..., 0], "theta_8": theta[..., 7]}


def analyze_eight_schools() -> dict:
    import arviz as az

    out = {}
    for arm in ARMS:
        entry = {"per_seed": {}}
        for seed in SEEDS:
            path = ART / "eight_schools" / f"{arm}-{seed}.json"
            if not path.exists():
                continue
            c = json.loads(path.read_text(encoding="utf-8"))
            samples = np.asarray([ch["samples"] for ch in c["chains_data"]], dtype=np.float64)
            fs = eight_schools_functionals(samples)
            ds = az.convert_to_dataset(dict(fs.items()))
            bulk = {k: float(az.ess(ds, var_names=[k], method="bulk")[k].values) for k in fs}
            tail = {k: float(az.ess(ds, var_names=[k], method="tail", prob=(0.05, 0.95))[k].values) for k in fs}
            rh = {k: float(az.rhat(ds, var_names=[k], method="rank")[k].values) for k in fs}
            calls = c["callbacks_started"][0]
            wall = statistics.median(c["wall_seconds"])
            entry["per_seed"][str(seed)] = {
                "callbacks_started": calls, "wall_median": wall,
                "bulk_ess": bulk, "tail_ess": tail, "rhat": rh,
                "min_bulk_ess": min(bulk.values()), "min_tail_ess": min(tail.values()), "max_rhat": max(rh.values()),
                "min_bulk_ess_per_call": min(bulk.values()) / calls,
                "divergences": sum(ch["divergences"] for ch in c["chains_data"]),
                "max_depth_stops": sum(ch["maximum_depth_stops"] for ch in c["chains_data"]),
                "refinement_exhaustions": sum(ch["refinement_exhaustions"] for ch in c["chains_data"]),
                "final_step_size": [ch["final_step_size"] for ch in c["chains_data"]],
                "final_max_error": [ch["final_max_error"] for ch in c["chains_data"]],
            }
        ps = list(entry["per_seed"].values())
        if ps:
            entry["complete"] = len(ps) == len(SEEDS)
            entry["geomean_min_bulk_ess_per_call"] = geomean([p["min_bulk_ess_per_call"] for p in ps])
            entry["all_healthy"] = all(p["min_bulk_ess"] >= 400 and p["min_tail_ess"] >= 400 and p["max_rhat"] <= 1.01
                                       and p["divergences"] == 0 and p["refinement_exhaustions"] == 0 for p in ps)
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


KEYS = ["min_bulk_ess_per_second", "min_bulk_ess_per_gradient", "min_tail_ess_per_gradient",
        "min_bulk_ess_per_gradient_sampling", "wall_seconds", "gradients_total", "gradients_sampling",
        "min_bulk_ess", "min_tail_ess", "max_rank_rhat", "max_abs_z", "wall_per_gradient_us", "max_depth_stops",
        "median_step", "step_ratio_vs_cmdstan", "refined_leaf_fraction", "leaves_per_transition",
        "gradients_per_leaf", "reverse_coarser_stop_fraction", "retained_mean_acceptance_statistic"]


def per_model_summary(models: list[str], arms: list[str], cells: dict, seeds: list[int]) -> dict:
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
                     "max_depth_stops": [c["max_depth_stops"] for c in ok],
                     "frozen_chains": [c.get("frozen_chains", 0) for c in ok],
                     "final_step_size": [c.get("final_step_size") for c in ok],
                     "final_max_error": [c.get("final_max_error") for c in ok],
                     "refined_leaf_fraction_by_level": [c.get("refined_leaf_fraction_by_level") for c in ok],
                     "reference_step": next((c.get("reference_step") for c in ok), None),
                     "agreement_flags": sum(1 for c in ok if c["agreement_flag"])}
            for k in KEYS:
                vals = [c[k] for c in ok if k in c and c[k] is not None and math.isfinite(c[k])]
                entry[k] = {"median": statistics.median(vals) if vals else None,
                            "min": min(vals) if vals else None, "max": max(vals) if vals else None, "values": vals}
            # trace at the adapted step and at CmdStan's step (level 0), seed medians
            tr = {}
            for label in ("h_x0.5", "h_x1", "h_x1.5", "h_x2", "h_x3", "h_ref"):
                rows = [c["trace"][label] for c in ok if "trace" in c and label in c["trace"]]
                if not rows:
                    continue
                tr[label] = {"step_median": med(r["step_median"] for r in rows),
                             "levels": [{k: med(r["levels"][lv][k] for r in rows)
                                         for k in ("frac_abs_gt_0.5", "frac_abs_gt_1", "frac_abs_gt_2", "mean_exp_neg_abs",
                                                   "mean_stan_accept", "abs_q50", "abs_q90", "abs_q99", "nonfinite")}
                                        for lv in range(len(rows[0]["levels"]))]}
            entry["trace"] = tr
            row[arm] = entry
        per_model[model] = row
    return per_model


def analyze() -> None:
    models = PROTOCOL["models"]
    cells = load_cells(CELLS)
    per_model = per_model_summary(models, ARMS, cells, SEEDS)
    v5 = v5_cells()
    v5_per_model = per_model_summary(models, ["owalnuts-da", "cmdstan", "nutpie"], v5, PROTOCOL["v5_seeds"])
    instr_cells = load_cells(INSTR / "cells") if (INSTR / "cells").exists() else {}
    instr = per_model_summary(models, [BASELINE], instr_cells, [INSTRUMENT_SEED])

    # ---- instrumentation table: v5 DA vs this study's `da` at the v5 seed, CmdStan step, trace
    instrumentation = {}
    for model in models:
        e = instr[model][BASELINE]
        v = v5_per_model[model]
        c5 = v["cmdstan"]
        d5 = v["owalnuts-da"]
        v5_seed_cell = v5.get(model, {}).get("owalnuts-da", {}).get(str(INSTRUMENT_SEED), {})
        tr = e.get("trace", {})
        instrumentation[model] = {
            "n_ok": e["n_ok"], "passed": e["n_passed"],
            "v5_da_seed_min_bulk_ess": v5_seed_cell.get("min_bulk_ess"),
            "this_min_bulk_ess": e["min_bulk_ess"]["median"],
            "v5_da_seed_gradients": v5_seed_cell.get("gradients_total"),
            "this_gradients": e["gradients_total"]["median"],
            "reproduces_v5_seed": (v5_seed_cell.get("gradients_total") == e["gradients_total"]["median"]
                                   and v5_seed_cell.get("min_bulk_ess") is not None and e["min_bulk_ess"]["median"] is not None
                                   and abs(v5_seed_cell["min_bulk_ess"] - e["min_bulk_ess"]["median"]) < 1e-6),
            "h_walnuts_median": e["median_step"]["median"],
            "h_cmdstan_median": e["reference_step"],
            "h_ratio": e["step_ratio_vs_cmdstan"]["median"],
            "refined_leaf_fraction": e["refined_leaf_fraction"]["median"],
            "refined_by_level": e["refined_leaf_fraction_by_level"][0] if e["refined_leaf_fraction_by_level"] else None,
            "reverse_coarser_stop_fraction": e["reverse_coarser_stop_fraction"]["median"],
            "leaves_per_transition": e["leaves_per_transition"]["median"],
            "gradients_per_leaf": e["gradients_per_leaf"]["median"],
            "mean_acceptance_statistic": e["retained_mean_acceptance_statistic"]["median"],
            "ess_per_gradient_x1e3": (e["min_bulk_ess_per_gradient"]["median"] or float("nan")) * 1e3,
            "v5_da_ess_per_gradient_x1e3": (d5["min_bulk_ess_per_gradient"]["median"] or float("nan")) * 1e3,
            "cmdstan_ess_per_gradient_x1e3": (c5["min_bulk_ess_per_gradient"]["median"] or float("nan")) * 1e3,
            "trace_at_h": tr.get("h_x1"), "trace_at_h_ref": tr.get("h_ref"),
            "trace_at_2h": tr.get("h_x2"), "trace_at_3h": tr.get("h_x3"), "trace_at_1.5h": tr.get("h_x1.5"),
        }
    inst_models = [m for m in models if instrumentation[m]["h_ratio"] is not None]
    instrumentation_overall = {
        "models": inst_models,
        "geomean_h_ratio": geomean([instrumentation[m]["h_ratio"] for m in inst_models]),
        "h_ratio_range": [min(instrumentation[m]["h_ratio"] for m in inst_models), max(instrumentation[m]["h_ratio"] for m in inst_models)] if inst_models else None,
        "median_refined_leaf_fraction": med(instrumentation[m]["refined_leaf_fraction"] for m in inst_models),
        "refined_leaf_fraction_range": [min(instrumentation[m]["refined_leaf_fraction"] for m in inst_models), max(instrumentation[m]["refined_leaf_fraction"] for m in inst_models)] if inst_models else None,
        "reproduced_v5_cells": sum(1 for m in models if instrumentation[m]["reproduces_v5_seed"]),
    }

    # ---- decision table: every arm against `da` (seed medians), gates, refined fraction, h ratio
    decision = {}
    healthy = PROTOCOL["cmdstan_healthy_models"]
    for arm in ARMS:
        per = {}
        for model in models:
            a, b = per_model[model][arm], per_model[model][BASELINE]
            ra = a["min_bulk_ess_per_gradient"]["median"]
            rb = b["min_bulk_ess_per_gradient"]["median"]
            cs = v5_per_model[model]["cmdstan"]["min_bulk_ess_per_gradient"]["median"]
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
                "h_ratio_vs_cmdstan": a["step_ratio_vs_cmdstan"]["median"],
                "h_ratio_vs_da": (a["median_step"]["median"] / b["median_step"]["median"]) if (a["median_step"]["median"] and b["median_step"]["median"]) else None,
                "refined_leaf_fraction": a["refined_leaf_fraction"]["median"],
                "reverse_coarser_stop_fraction": a["reverse_coarser_stop_fraction"]["median"],
                "leaves_per_transition": a["leaves_per_transition"]["median"],
                "gradients_per_leaf": a["gradients_per_leaf"]["median"],
                "final_max_error": a["final_max_error"],
                "divergences": a["divergences"], "max_depth_stops": a["max_depth_stops"],
                "frozen_chains": a["frozen_chains"],
                "max_rank_rhat": a["max_rank_rhat"]["median"],
            }
        ratios = {m: per[m]["ratio_vs_da"] for m in models if per[m]["ratio_vs_da"]}
        decision[arm] = {
            "per_model": per,
            "cells_passed": sum(per_model[m][arm]["n_passed"] for m in models),
            "cells_ok": sum(per_model[m][arm]["n_ok"] for m in models),
            "models_with_ratio": len(ratios),
            "geomean_ratio_vs_da": geomean(list(ratios.values())),
            "geomean_ratio_vs_da_healthy": geomean([per[m]["ratio_vs_da"] for m in healthy if per[m]["ratio_vs_da"]]),
            "min_ratio_vs_da": min(ratios.values()) if ratios else None,
            "argmin_ratio_vs_da": min(ratios, key=ratios.get) if ratios else None,
            "models_below_0.85": {m: r for m, r in ratios.items() if r < 0.85},
            "geomean_ratio_vs_cmdstan_v5_healthy": geomean([per[m]["ratio_vs_cmdstan_v5"] for m in healthy if per[m]["ratio_vs_cmdstan_v5"]]),
            "geomean_ratio_vs_cmdstan_v5_all": geomean([per[m]["ratio_vs_cmdstan_v5"] for m in models if per[m]["ratio_vs_cmdstan_v5"]]),
            "geomean_h_ratio_vs_cmdstan": geomean([per[m]["h_ratio_vs_cmdstan"] for m in models if per[m]["h_ratio_vs_cmdstan"]]),
            "geomean_h_ratio_vs_cmdstan_healthy": geomean([per[m]["h_ratio_vs_cmdstan"] for m in healthy if per[m]["h_ratio_vs_cmdstan"]]),
            "geomean_h_ratio_vs_da": geomean([per[m]["h_ratio_vs_da"] for m in models if per[m]["h_ratio_vs_da"]]),
            "geomean_gradients_ratio_vs_da": geomean([per[m]["gradients_ratio_vs_da"] for m in models if per[m]["gradients_ratio_vs_da"]]),
            "median_refined_leaf_fraction": med(per[m]["refined_leaf_fraction"] for m in models),
            "median_reverse_coarser_stop_fraction": med(per[m]["reverse_coarser_stop_fraction"] for m in models),
            "geomean_wall_per_gradient_vs_cmdstan_v5": geomean([per_model[m][arm]["wall_per_gradient_us"]["median"] / v5_per_model[m]["cmdstan"]["wall_per_gradient_us"]["median"]
                                                             for m in models if per_model[m][arm]["wall_per_gradient_us"]["median"] and v5_per_model[m]["cmdstan"]["wall_per_gradient_us"]["median"]]),
        }
    funnel = analyze_funnel()
    eight = analyze_eight_schools()
    da_cells = decision[BASELINE]["cells_passed"]
    dr = PROTOCOL["decision_rule"]
    rule = {}
    for arm in ARMS:
        if arm == BASELINE:
            continue
        d = decision[arm]
        es = eight.get(arm, {}).get("geomean_min_bulk_ess_per_call")
        es_da = eight.get(BASELINE, {}).get("geomean_min_bulk_ess_per_call")
        es_ratio = (es / es_da) if (es and es_da) else None
        fz = funnel.get(arm, {})
        crit = {
            "C1_geomean_ge": {"value": d["geomean_ratio_vs_da"], "threshold": dr["geomean_min"],
                              "held": bool(d["geomean_ratio_vs_da"] >= dr["geomean_min"]) if d["models_with_ratio"] == len(models) else None},
            "C2_no_model_below": {"value": d["min_ratio_vs_da"], "argmin": d["argmin_ratio_vs_da"], "threshold": dr["per_model_min"],
                                  "held": bool(d["min_ratio_vs_da"] >= dr["per_model_min"]) if d["models_with_ratio"] == len(models) else None},
            "C3_gates_ge_da": {"value": d["cells_passed"], "da": da_cells, "held": bool(d["cells_passed"] >= da_cells) if d["cells_ok"] else None},
            "C4_funnel_abs_z_le_2": {"value": [p["z"] for p in fz.get("per_seed", {}).values()],
                                     "held": fz.get("all_seeds_abs_z_le_2") if fz.get("complete") else None},
            "C5_eight_schools_ge": {"value": es_ratio, "threshold": dr["eight_schools_min_ratio"],
                                    "held": bool(es_ratio >= dr["eight_schools_min_ratio"]) if es_ratio and eight.get(arm, {}).get("complete") else None},
        }
        crit["all_held"] = all(c.get("held") is True for c in crit.values() if isinstance(c, dict))
        crit["beats_da_geomean"] = bool(d["geomean_ratio_vs_da"] > 1.0) if d["models_with_ratio"] else None
        rule[arm] = crit
    flip = [arm for arm, c in rule.items() if c["all_held"]]
    if flip:
        flip.sort(key=lambda a: -decision[a]["geomean_ratio_vs_da"])
    summary = {
        "schema": "refinement-role-v1-summary",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "protocol_sha256": __import__("hashlib").sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
        "instrumentation": instrumentation,
        "instrumentation_overall": instrumentation_overall,
        "decision": decision,
        "decision_rule": rule,
        "arms_meeting_rule": flip,
        "funnel": funnel,
        "eight_schools": eight,
        "per_model": per_model,
        "v5_per_model": {m: {arm: {k: v for k, v in e.items() if k in ("n_passed", "n_ok", "min_bulk_ess_per_gradient", "min_bulk_ess", "gradients_total", "final_step_size", "wall_per_gradient_us")}
                             for arm, e in row.items()} for m, row in v5_per_model.items()},
        "cells": cells,
        "instrumentation_cells": instr_cells,
    }
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=float) + "\n", encoding="utf-8")
    write_table(models, per_model, instrumentation, instrumentation_overall, decision, rule, funnel, eight, v5_per_model, flip)


def f(x, fmt):
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)


def write_table(models, per_model, instrumentation, io, decision, rule, funnel, eight, v5pm, flip) -> None:
    L = ["# refinement_role_v1 — results", "",
         "Seed medians over 3 seeds (89101–89103) of the per-cell minimum over reference parameters; `gates` = cells passing "
         "R-hat <= 1.01, bulk/tail ESS >= 400, zero divergences; CmdStan from `posteriordb_bench_v5` (seeds 87101–87103).", "",
         "## Instrumentation (arm `da` = the shipped defaults, v5 seed 87101, one cell per model)", "",
         "`h ratio` = median adapted `h` over the four chains / median of the twelve v5 CmdStan chain steps; `refined` = fraction of "
         "retained built leaves accepted above level 0; `rc stop` = fraction of retained transitions ending in a reverse-coarser stop; "
         "`P(|dH|>1)` at level 0 from the trace at the adapted `h`, at CmdStan's `h` and at 2`h`; `E exp(-|dH|)` is the statistic dual "
         "averaging drives to 0.8; `Stan acc` the mean of `min(1, exp(-dH))` at the same step.", "",
         "| model | v5 repro | h_walnuts | h_cmdstan | h ratio | refined | rc stop | leaves/orbit | grads/leaf | acc stat | P(\\|dH\\|>1) @h | @h_stan | @2h | @3h | E exp(-\\|dH\\|) @h | Stan acc @h | Stan acc @h_stan | ESS/grad x1e3 (v5 DA / CmdStan) |",
         "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for m in models:
        i = instrumentation[m]
        th, tr, t2, t3 = i["trace_at_h"], i["trace_at_h_ref"], i["trace_at_2h"], i["trace_at_3h"]
        g = lambda t, k: (t["levels"][0][k] if t else None)  # noqa: E731
        L.append(f"| {m} | {'yes' if i['reproduces_v5_seed'] else 'no'} | {f(i['h_walnuts_median'], '.4g')} | {f(i['h_cmdstan_median'], '.4g')} | {f(i['h_ratio'], '.2f')} | "
                 f"{f(i['refined_leaf_fraction'], '.4f')} | {f(i['reverse_coarser_stop_fraction'], '.3f')} | {f(i['leaves_per_transition'], '.1f')} | {f(i['gradients_per_leaf'], '.3f')} | "
                 f"{f(i['mean_acceptance_statistic'], '.3f')} | {f(g(th, 'frac_abs_gt_1'), '.4f')} | {f(g(tr, 'frac_abs_gt_1'), '.4f')} | {f(g(t2, 'frac_abs_gt_1'), '.4f')} | {f(g(t3, 'frac_abs_gt_1'), '.4f')} | "
                 f"{f(g(th, 'mean_exp_neg_abs'), '.3f')} | {f(g(th, 'mean_stan_accept'), '.3f')} | {f(g(tr, 'mean_stan_accept'), '.3f')} | "
                 f"{f(i['ess_per_gradient_x1e3'], '.3f')} ({f(i['v5_da_ess_per_gradient_x1e3'], '.3f')} / {f(i['cmdstan_ess_per_gradient_x1e3'], '.3f')}) |")
    L += ["", f"Geomean h ratio {f(io['geomean_h_ratio'], '.3f')} (range {f((io['h_ratio_range'] or [None])[0], '.2f')}–{f((io['h_ratio_range'] or [None, None])[1], '.2f')}); "
          f"median refined fraction {f(io['median_refined_leaf_fraction'], '.4f')} (range {f((io['refined_leaf_fraction_range'] or [None])[0], '.4f')}–{f((io['refined_leaf_fraction_range'] or [None, None])[1], '.4f')}); "
          f"v5 cells reproduced bit-for-bit (same gradients and min ESS): {io['reproduced_v5_cells']} of {len(models)}.", ""]
    L += ["## Trace: what refinement would cost at a larger step (arm `da`, seed 87101; level-0 leaf statistic from posterior draws with fresh momenta)", "",
          "| model | step | P(\\|dH\\|>0.5) L0 | P(\\|dH\\|>1) L0 | P(\\|dH\\|>2) L0 | P(\\|dH\\|>1) L1 | P(\\|dH\\|>1) L2 | q50 \\|dH\\| | q90 | q99 | E exp(-\\|dH\\|) | Stan acc | nonfinite |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for m in models:
        i = instrumentation[m]
        for label, t in (("0.5h", i["trace_at_h"] and per_model_trace(instrumentation, m, "h_x0.5")), ("h", i["trace_at_h"]), ("h_stan", i["trace_at_h_ref"]), ("1.5h", i["trace_at_1.5h"]), ("2h", i["trace_at_2h"]), ("3h", i["trace_at_3h"])):
            if not t:
                continue
            l0, l1, l2 = t["levels"][0], t["levels"][1], t["levels"][2]
            L.append(f"| {m} | {label} = {f(t['step_median'], '.4g')} | {f(l0['frac_abs_gt_0.5'], '.4f')} | {f(l0['frac_abs_gt_1'], '.4f')} | {f(l0['frac_abs_gt_2'], '.4f')} | "
                     f"{f(l1['frac_abs_gt_1'], '.4f')} | {f(l2['frac_abs_gt_1'], '.4f')} | {f(l0['abs_q50'], '.3g')} | {f(l0['abs_q90'], '.3g')} | {f(l0['abs_q99'], '.3g')} | "
                     f"{f(l0['mean_exp_neg_abs'], '.3f')} | {f(l0['mean_stan_accept'], '.3f')} | {f(l0['nonfinite'], '.0f')} |")
    L += ["", "## Arms against `da` (min bulk ESS per gradient; seed medians; ratio arm / da)", "",
          "| arm | cells passed | geomean vs da (17) | geomean vs da (healthy 14) | min ratio (model) | models < 0.85 | vs CmdStan v5 (healthy) | vs CmdStan v5 (17) | h vs CmdStan | h vs da | grads vs da | refined | rc stop | wall/grad vs CmdStan |",
          "|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for arm in ARMS:
        d = decision[arm]
        L.append(f"| {arm} | {d['cells_passed']}/{d['cells_ok']} | {f(d['geomean_ratio_vs_da'], '.3f')} | {f(d['geomean_ratio_vs_da_healthy'], '.3f')} | "
                 f"{f(d['min_ratio_vs_da'], '.2f')} ({d['argmin_ratio_vs_da']}) | {', '.join(f'{m} {r:.2f}' for m, r in d['models_below_0.85'].items()) or 'none'} | "
                 f"{f(d['geomean_ratio_vs_cmdstan_v5_healthy'], '.3f')} | {f(d['geomean_ratio_vs_cmdstan_v5_all'], '.3f')} | {f(d['geomean_h_ratio_vs_cmdstan'], '.3f')} | {f(d['geomean_h_ratio_vs_da'], '.3f')} | "
                 f"{f(d['geomean_gradients_ratio_vs_da'], '.3f')} | {f(d['median_refined_leaf_fraction'], '.4f')} | {f(d['median_reverse_coarser_stop_fraction'], '.3f')} | {f(d['geomean_wall_per_gradient_vs_cmdstan_v5'], '.3f')} |")
    L += ["", "## Per model (ratio arm / da of seed-median min bulk ESS per gradient; gates arm/da; h ratio vs CmdStan; refined fraction)", "",
          "| model | " + " | ".join(ARMS) + " |", "|---|" + "---|" * len(ARMS)]
    for m in models:
        cells_row = []
        for arm in ARMS:
            p = decision[arm]["per_model"][m]
            cells_row.append(f"{f(p['ratio_vs_da'], '.2f')} ({p['gates']}/3; h {f(p['h_ratio_vs_cmdstan'], '.2f')}; r {f(p['refined_leaf_fraction'], '.3f')})")
        L.append(f"| {m} | " + " | ".join(cells_row) + " |")
    L += ["", "## Per model absolute (seed medians): ESS/grad x1e3, min bulk ESS, gradients, final steps per seed, final delta per seed", ""]
    for arm in ARMS:
        L += [f"### {arm}", "", "| model | gates | ESS/grad x1e3 | min bulk ESS | grads | leaves/orbit | grads/leaf | acc stat | final h per chain (seed 1 / 2 / 3) | final delta (seed 1 / 2 / 3) | depth caps | div | max R-hat | max abs z |", "|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---:|---:|"]
        for m in models:
            e = per_model[m][arm]
            steps = " / ".join("[" + ", ".join(f"{x:.3g}" for x in st) + "]" for st in e["final_step_size"] if st)
            deltas = " / ".join("[" + ", ".join(f"{x:.3g}" for x in st) + "]" for st in e["final_max_error"] if st)
            L.append(f"| {m} | {e['n_passed']}/{e['n_cells']} | {f((e['min_bulk_ess_per_gradient']['median'] or float('nan')) * 1e3, '.3f')} | {f(e['min_bulk_ess']['median'], ',.0f')} | "
                     f"{f(e['gradients_total']['median'], ',.0f')} | {f(e['leaves_per_transition']['median'], '.1f')} | {f(e['gradients_per_leaf']['median'], '.3f')} | {f(e['retained_mean_acceptance_statistic']['median'], '.3f')} | {steps} | {deltas} | "
                     f"{','.join(str(d) for d in e['max_depth_stops']['values'])} | {','.join(str(d) for d in e['divergences'])} | {f(e['max_rank_rhat']['median'], '.4f')} | {f(e['max_abs_z']['median'], '.2f')} |")
        L.append("")
    L += ["## Funnel tail mass P(omega < -5) at the sampler defaults (exact 0.0478), 4 x 2,000 / 20,000 per seed", "",
          "| arm | seed | estimate | MCSE z (gate) | batch-means z | omega bulk ESS / R-hat | omega ESS/call x1e3 | target calls | divergences | retained exhaustions | final h | final delta |", "|---|---|---:|---:|---:|---|---:|---:|---:|---:|---|---|"]
    for arm in ARMS:
        for seed, p in funnel.get(arm, {}).get("per_seed", {}).items():
            L.append(f"| {arm} | {seed} | {p['estimate']:.4f} | {p['z']:+.2f} | {p['z_batch_means']:+.2f} | {p['omega_bulk_ess']:.0f} / {p['omega_rhat']:.3f} | {p['omega_bulk_ess_per_call'] * 1e3:.3f} | {p['target_calls_total']:,} | {p['divergences']} | {p['refinement_exhaustions']} | {', '.join(f'{x:.3g}' for x in p['final_step_size'])} | {', '.join(f'{x:.3g}' for x in p['final_max_error'])} |")
    L += ["", "## Eight Schools strict track (v9 settings: h 0.3, depth 8, eight levels, 4 x 1,000/1,000, threads 1, `walnutpie` facade; the arm's rule replaces `WarmupConfig::new(0.95)` and `delta = 1` where it changes them)", "",
          "| arm | calls per seed | min bulk ESS | max R-hat | div / exhaust | geomean min bulk ESS/call | ratio to da | all healthy | final h (seed 1) | final delta (seed 1) |", "|---|---|---|---|---|---:|---:|---|---|---|"]
    es_da = eight.get(BASELINE, {}).get("geomean_min_bulk_ess_per_call")
    for arm in ARMS:
        e = eight.get(arm, {})
        ps = e.get("per_seed", {})
        if not ps:
            continue
        g = e.get("geomean_min_bulk_ess_per_call")
        first = next(iter(ps.values()))
        calls_s = " / ".join(f"{p['callbacks_started']:,}" for p in ps.values())
        ess_s = " / ".join(f"{p['min_bulk_ess']:,.0f}" for p in ps.values())
        rhat_s = f"{max(p['max_rhat'] for p in ps.values()):.4f}"
        div_s = f"{sum(p['divergences'] for p in ps.values())} / {sum(p['refinement_exhaustions'] for p in ps.values())}"
        h_s = ", ".join(f"{x:.3g}" for x in first["final_step_size"])
        d_s = ", ".join(f"{x:.3g}" for x in first["final_max_error"])
        L.append(f"| {arm} | {calls_s} | {ess_s} | {rhat_s} | {div_s} | {f(g, '.5f')} | {f((g / es_da) if (g and es_da) else None, '.3f')} | {e.get('all_healthy')} | {h_s} | {d_s} |")
    L += ["", "## Decision rule (flip the sampler default to an arm with geomean >= 1.15x da over 17 models, no model < 0.85x, gates >= da, funnel |z| <= 2 on every seed, Eight Schools >= 0.9x)", "",
          "| arm | C1 geomean >= 1.15 | C2 min >= 0.85 | C3 gates >= da | C4 funnel | C5 Eight Schools >= 0.9 | all held |", "|---|---|---|---|---|---|---|"]
    for arm, c in rule.items():
        L.append(f"| {arm} | {f(c['C1_geomean_ge']['value'], '.3f')} ({c['C1_geomean_ge']['held']}) | {f(c['C2_no_model_below']['value'], '.2f')} {c['C2_no_model_below']['argmin']} ({c['C2_no_model_below']['held']}) | "
                 f"{c['C3_gates_ge_da']['value']} vs {c['C3_gates_ge_da']['da']} ({c['C3_gates_ge_da']['held']}) | {', '.join(f'{z:+.2f}' for z in c['C4_funnel_abs_z_le_2']['value'])} ({c['C4_funnel_abs_z_le_2']['held']}) | "
                 f"{f(c['C5_eight_schools_ge']['value'], '.3f')} ({c['C5_eight_schools_ge']['held']}) | **{c['all_held']}** |")
    L += ["", f"Arms meeting the rule: {', '.join(flip) or 'none'}."]
    (ART / "results-table.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


def per_model_trace(instrumentation, model, label):
    # the 0.5h trace is kept in the summary under per_model; fetch through the instrumentation cell summary
    path = INSTR / "cells"
    for p in path.glob(f"{short(model)}-da-*.json"):
        c = json.loads(p.read_text(encoding="utf-8"))
        t = c.get("trace", {}).get(label)
        if t:
            return {"step_median": t["step_median"], "levels": t["levels"]}
    return None


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("run", "instrument"):
        instrument = args[0] == "instrument" if args else False
        models, arms = PROTOCOL["models"], ([BASELINE] if instrument else ARMS)
        for a in args[1:]:
            if a.startswith("--models="):
                models = a.split("=", 1)[1].split(",")
            elif a.startswith("--arms="):
                arms = a.split("=", 1)[1].split(",")
        run_all(models, arms, instrument)
    elif args[0] == "build":
        build_all(PROTOCOL["models"])
    elif args[0] == "cell":
        run_model_arm(args[1], args[2], len(args) > 3 and args[3] == "instrument")
    elif args[0] == "checks":
        arms = ARMS
        for a in args[1:]:
            if a.startswith("--arms="):
                arms = a.split("=", 1)[1].split(",")
        run_checks(arms)
    elif args[0] == "analyze":
        analyze()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
