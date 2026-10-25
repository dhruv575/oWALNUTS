#!/usr/bin/env python3
"""Adaptive-delta study driver (WP49): the posteriordb v5 protocol (harness of refinement_role_v1, WP34)
restricted to oWALNUTS arms that differ only in `delta` (default 1, fixed 2, and two warmup rules that adapt
it from the observed level-0 leaf-error distribution), with the level-0 leaf-error trace kept as an
instrument, CmdStan cited from v5.

    python run_study.py build                 # compile every BridgeStan model (no STAN_THREADS)
    python run_study.py run                   # every model/arm/seed in protocol order (resumable)
    python run_study.py cell <model> <arm>    # one model/arm, all seeds (child process)
    python run_study.py checks                # funnel (12 seeds) then Eight Schools strict track (3 seeds), every arm
    python run_study.py analyze               # artifacts/summary.json + results-table.md

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
FUNNEL_SEEDS = PROTOCOL["funnel_seeds"]
INSTRUMENT_SEED = None
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
        "schema": "adaptive-delta-v1-cell-metrics",
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
        "schema": "adaptive-delta-v1-cell-metrics", "model": model, "arm": arm, "seed": seed,
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
        "adaptive_delta_trajectory": [c["adaptive_delta_updates"] for c in chains],
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
        for seed in FUNNEL_SEEDS:
            out = fdir / f"defaults-{arm}-{seed}.json"
            if out.exists():
                continue
            log(f"funnel defaults {arm} {seed}")
            cp = subprocess.run([str(FUNNEL), "defaults", arm, str(seed), str(out)], capture_output=True, text=True)
            log(f"  {cp.stderr.strip()[-300:]}")
            if cp.returncode != 0 or not out.exists():
                (fdir / f"defaults-{arm}-{seed}.error.json").write_text(json.dumps(
                    {"arm": arm, "seed": seed, "status": "error", "returncode": cp.returncode,
                     "stderr": cp.stderr[-4000:]}, indent=1) + "\n", encoding="utf-8")
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


EXACT_P5 = 0.0477903522728147
EXACT_P6 = 0.0227501319481792


def funnel_gross_safety(p: dict) -> dict:
    """WP37A gate F3 per seed (finite draws and no sampler error are implied by a result file)."""
    checks = {
        "zero_retained_divergences": p["divergences"] == 0,
        "rank_rhat_le_1.05": p["omega_rhat"] <= 1.05,
        "p5_abs_error_le_0.025": abs(p["estimate"] - EXACT_P5) <= 0.025,
        "p6_abs_error_le_0.015": abs(p["estimate_6"] - EXACT_P6) <= 0.015,
        "omega_variance_in_5_13": 5.0 <= p["omega_variance"] <= 13.0,
    }
    return {"checks": checks, "passed": all(checks.values())}


def funnel_healthy(p: dict) -> bool:
    """WP37A F4 health predicate."""
    return bool(p["omega_rhat"] <= 1.01 and p["omega_bulk_ess"] >= 400 and p["omega_tail_ess"] >= 400
                and p["divergences"] == 0 and p["invalid_stops"] == 0 and p["refinement_exhaustions"] == 0)


def analyze_funnel() -> dict:
    out = {}
    for arm in ARMS:
        entry = {"per_seed": {}, "errors": {}}
        for seed in FUNNEL_SEEDS:
            path = ART / "funnel" / f"defaults-{arm}-{seed}.json"
            err = ART / "funnel" / f"defaults-{arm}-{seed}.error.json"
            if err.exists():
                entry["errors"][str(seed)] = json.loads(err.read_text(encoding="utf-8"))
            if not path.exists():
                continue
            c = json.loads(path.read_text(encoding="utf-8"))
            t = c["tail_mass"]
            entry["per_seed"][str(seed)] = {
                "estimate_6": c["tail_mass_6"]["estimate"], "z_6": c["tail_mass_6"]["z"],
                "omega_variance": c["omega"]["variance"],
                "invalid_stops": sum(ch["invalid_stops"] for ch in c["chains_data"]),
                "warmup_divergences": sum(ch["warmup_divergences"] for ch in c["chains_data"]),
                "reverse_coarser_stops": sum(ch["reverse_coarser_stops"] for ch in c["chains_data"]),
                "refinement_level_built": [sum(x) for x in zip(*(ch["refinement_level_built"] for ch in c["chains_data"]))],
                "delta_trajectory": [ch["adaptive_delta_updates"] for ch in c["chains_data"]],
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
        for p in entry["per_seed"].values():
            p["gross_safety"] = funnel_gross_safety(p)
            p["healthy"] = funnel_healthy(p)
        study = [entry["per_seed"].get(str(s)) for s in SEEDS]
        entry["study_seeds_complete"] = all(p is not None for p in study)
        entry["study_seed_z"] = [p["z"] if p else None for p in study]
        # Decisive (C4, C5): the three study seeds; a missing or errored seed fails both.
        entry["all_study_seeds_abs_z_le_2"] = bool(entry["study_seeds_complete"] and all(abs(p["z"]) <= 2.0 for p in study))
        entry["all_study_seeds_gross_safe"] = bool(entry["study_seeds_complete"] and all(p["gross_safety"]["passed"] for p in study))
        allp = list(entry["per_seed"].values())
        entry["complete"] = len(allp) == len(FUNNEL_SEEDS)
        entry["seeds_abs_z_le_2_all12"] = sum(1 for p in allp if abs(p["z"]) <= 2.0)
        entry["seeds_gross_safe_all12"] = sum(1 for p in allp if p["gross_safety"]["passed"])
        entry["seeds_divergence_free_all12"] = sum(1 for p in allp if p["divergences"] == 0)
        entry["seeds_healthy_all12"] = sum(1 for p in allp if p["healthy"])
        entry["total_divergences_all12"] = sum(p["divergences"] for p in allp)
        entry["total_refinement_exhaustions_all12"] = sum(p["refinement_exhaustions"] for p in allp)
        entry["total_target_calls_all12"] = sum(p["target_calls_total"] for p in allp)
        if allp:
            entry["pooled_p5_all12"] = sum(p["estimate"] for p in allp) / len(allp)
            entry["pooled_p6_all12"] = sum(p["estimate_6"] for p in allp) / len(allp)
            entry["pooled_omega_variance_all12_mean_of_seeds"] = sum(p["omega_variance"] for p in allp) / len(allp)
        entry["max_abs_z"] = max((abs(p["z"]) for p in allp), default=None)
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
                "tail_ess_per_call_min": min(tail.values()) / calls,
                "sample_sha256": c["sample_sha256"],
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


def delta_landing(cells: dict, model: str, arm: str) -> dict:
    """Final delta per chain over the ok cells of (model, arm), and the final-window quantile."""
    finals, quantiles, fractions = [], [], []
    for c in cells.get(model, {}).get(arm, {}).values():
        if c.get("status") != "ok":
            continue
        finals += [x for x in c.get("final_max_error", []) if x is not None]
        for traj in c.get("adaptive_delta_trajectory", []) or []:
            if traj:
                last = traj[-1]
                if last.get("quantile") is not None:
                    quantiles.append(last["quantile"])
                if last.get("fraction_above_before") is not None:
                    fractions.append(last["fraction_above_before"])
    return {"final_delta_median": med(finals), "final_delta_min": min(finals) if finals else None,
            "final_delta_max": max(finals) if finals else None, "n_chains": len(finals),
            "final_window_quantile_median": med(quantiles),
            "final_window_fraction_above_prior_delta_median": med(fractions)}


def analyze() -> None:
    models = PROTOCOL["models"]
    cells = load_cells(CELLS)
    per_model = per_model_summary(models, ARMS, cells, SEEDS)
    v5 = v5_cells()
    v5_per_model = per_model_summary(models, ["owalnuts-da", "cmdstan", "nutpie"], v5, PROTOCOL["v5_seeds"])

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
                "delta_landing": delta_landing(cells, model, arm),
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
            "geomean_h_ratio_vs_da": geomean([per[m]["h_ratio_vs_da"] for m in models if per[m]["h_ratio_vs_da"]]),
            "geomean_gradients_ratio_vs_da": geomean([per[m]["gradients_ratio_vs_da"] for m in models if per[m]["gradients_ratio_vs_da"]]),
            "median_refined_leaf_fraction": med(per[m]["refined_leaf_fraction"] for m in models),
            "median_reverse_coarser_stop_fraction": med(per[m]["reverse_coarser_stop_fraction"] for m in models),
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
        complete = d["models_with_ratio"] == len(models)
        crit = {
            "C1_geomean_ge": {"value": d["geomean_ratio_vs_da"], "threshold": dr["geomean_min"],
                              "held": bool(complete and d["geomean_ratio_vs_da"] >= dr["geomean_min"])},
            "C2_no_model_below": {"value": d["min_ratio_vs_da"], "argmin": d["argmin_ratio_vs_da"], "threshold": dr["per_model_min"],
                                  "held": bool(complete and d["min_ratio_vs_da"] >= dr["per_model_min"])},
            "C3_gates_ge_da": {"value": d["cells_passed"], "da": da_cells, "held": bool(d["cells_passed"] >= da_cells)},
            "C4_funnel_abs_z_le_2": {"value": fz.get("study_seed_z"), "held": bool(fz.get("all_study_seeds_abs_z_le_2"))},
            "C5_funnel_gross_safety": {"value": [fz.get("per_seed", {}).get(str(s), {}).get("gross_safety", {}).get("passed") for s in SEEDS],
                                       "held": bool(fz.get("all_study_seeds_gross_safe"))},
        }
        crit["all_held"] = all(c["held"] is True for c in crit.values())
        crit["secondary_eight_schools_ratio"] = {"value": es_ratio, "reference_threshold": dr["eight_schools_reference_ratio"],
                                                 "at_or_above": bool(es_ratio >= dr["eight_schools_reference_ratio"]) if es_ratio else None}
        rule[arm] = crit
    recommend = [arm for arm in PROTOCOL["candidate_arms"] if rule[arm]["all_held"]]
    recommend.sort(key=lambda a: -decision[a]["geomean_ratio_vs_da"])
    predictions = evaluate_predictions(models, decision, funnel, rule)
    summary = {
        "schema": "adaptive-delta-v1-summary",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "protocol_sha256": __import__("hashlib").sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
        "decision": decision,
        "decision_rule": rule,
        "candidate_arms_meeting_rule": recommend,
        "verdict": (f"RECOMMEND_{recommend[0].upper()}_AS_DEFAULT" if recommend else "NO_ADAPTIVE_DELTA_RULE_QUALIFIES"),
        "predictions": predictions,
        "funnel": funnel,
        "eight_schools": eight,
        "per_model": per_model,
        "v5_per_model": {m: {arm: {k: v for k, v in e.items() if k in ("n_passed", "n_ok", "min_bulk_ess_per_gradient", "min_bulk_ess", "gradients_total", "final_step_size", "wall_per_gradient_us")}
                             for arm, e in row.items()} for m, row in v5_per_model.items()},
        "cells": cells,
    }
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=float) + "\n", encoding="utf-8")
    write_table(models, per_model, decision, rule, funnel, eight, recommend, predictions, summary["verdict"])


def evaluate_predictions(models, decision, funnel, rule) -> dict:
    """The frozen numerical predictions of protocol.json, scored mechanically."""
    out = {}
    pr = PROTOCOL["predictions_numeric"]
    for arm, spec in pr["delta_landing"].items():
        rows = {}
        for cls, cls_spec in spec.items():
            ms = PROTOCOL["model_classes"][cls]
            vals = [decision[arm]["per_model"][m]["delta_landing"]["final_delta_median"] for m in ms]
            vals = [v for v in vals if v is not None]
            m_ = med(vals)
            rows[cls] = {"predicted": cls_spec, "observed_median_over_models": m_,
                         "per_model": {m: decision[arm]["per_model"][m]["delta_landing"]["final_delta_median"] for m in ms},
                         "held": (m_ is not None and cls_spec[0] <= m_ <= cls_spec[1])}
        out[f"delta_landing_{arm}"] = rows
    for arm, (lo, hi) in pr["geomean_vs_da"].items():
        g = decision[arm]["geomean_ratio_vs_da"]
        out[f"geomean_{arm}"] = {"predicted": [lo, hi], "observed": g, "held": bool(lo <= g <= hi)}
    for arm, (lo, hi) in pr["accel_gp_ratio"].items():
        r = decision[arm]["per_model"]["mcycle_gp-accel_gp"]["ratio_vs_da"]
        out[f"accel_gp_{arm}"] = {"predicted": [lo, hi], "observed": r, "held": bool(r is not None and lo <= r <= hi)}
    for arm, expected in pr["meets_rule"].items():
        out[f"meets_rule_{arm}"] = {"predicted": expected, "observed": rule[arm]["all_held"], "held": rule[arm]["all_held"] == expected}
    for arm, (lo, hi) in pr["funnel_final_delta"].items():
        ds = [d for p in funnel.get(arm, {}).get("per_seed", {}).values() for d in p["final_max_error"]]
        m_ = med(ds)
        out[f"funnel_final_delta_{arm}"] = {"predicted": [lo, hi], "observed_median": m_, "held": bool(m_ is not None and lo <= m_ <= hi)}
    return out


def f(x, fmt):
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)


def write_table(models, per_model, decision, rule, funnel, eight, recommend, predictions, verdict) -> None:
    L = ["# adaptive_delta_v1 — results", "",
         f"Verdict: **{verdict}**.", "",
         f"Seed medians over 3 seeds ({', '.join(map(str, SEEDS))}) of the per-cell minimum over reference parameters; `gates` = cells passing "
         "R-hat <= 1.01, bulk/tail ESS >= 400, zero divergences; CmdStan from `posteriordb_bench_v5` (seeds 87101–87103).", "",
         "## Arms against `da` (min bulk ESS per gradient, warmup included; seed medians; ratio arm / da)", "",
         "| arm | cells passed | geomean vs da (17) | geomean vs da (healthy 14) | min ratio (model) | models < 0.85 | vs CmdStan v5 (healthy) | h vs da | grads vs da | refined | rc stop |",
         "|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|"]
    for arm in ARMS:
        d = decision[arm]
        L.append(f"| {arm} | {d['cells_passed']}/{d['cells_ok']} | {f(d['geomean_ratio_vs_da'], '.3f')} | {f(d['geomean_ratio_vs_da_healthy'], '.3f')} | "
                 f"{f(d['min_ratio_vs_da'], '.2f')} ({d['argmin_ratio_vs_da']}) | {', '.join(f'{m} {r:.2f}' for m, r in d['models_below_0.85'].items()) or 'none'} | "
                 f"{f(d['geomean_ratio_vs_cmdstan_v5_healthy'], '.3f')} | {f(d['geomean_h_ratio_vs_da'], '.3f')} | "
                 f"{f(d['geomean_gradients_ratio_vs_da'], '.3f')} | {f(d['median_refined_leaf_fraction'], '.4f')} | {f(d['median_reverse_coarser_stop_fraction'], '.3f')} |")
    L += ["", "## Per model: ratio vs da (gates/3; final delta median over 12 chains [min–max]; refined-leaf fraction; rc-stop fraction)", "",
          "| model | " + " | ".join(ARMS) + " |", "|---|" + "---|" * len(ARMS)]
    for m in models:
        row = []
        for arm in ARMS:
            p = decision[arm]["per_model"][m]
            dl = p["delta_landing"]
            row.append(f"{f(p['ratio_vs_da'], '.2f')} ({p['gates']}/3; d {f(dl['final_delta_median'], '.2f')} [{f(dl['final_delta_min'], '.2f')}–{f(dl['final_delta_max'], '.2f')}]; "
                       f"r {f(p['refined_leaf_fraction'], '.4f')}; rc {f(p['reverse_coarser_stop_fraction'], '.3f')})")
        L.append(f"| {m} | " + " | ".join(row) + " |")
    L += ["", "## Where delta landed: final-window level-0 quantile (r1: q0.99, r2: q0.985) and the final window's fraction of leaves above the prior delta (chain medians)", "",
          "| model | r1 q0.99 | r1 delta | r1 frac>delta | r2 q0.985 | r2 delta | r2 frac>delta | trace q99 at h (da) | trace P(\\|dH\\|>1) at h (da) |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for m in models:
        r1 = decision["r1"]["per_model"][m]["delta_landing"]
        r2 = decision["r2"]["per_model"][m]["delta_landing"]
        tr = per_model[m][BASELINE].get("trace", {}).get("h_x1")
        q99 = tr["levels"][0]["abs_q99"] if tr else None
        p1 = tr["levels"][0]["frac_abs_gt_1"] if tr else None
        L.append(f"| {m} | {f(r1['final_window_quantile_median'], '.3g')} | {f(r1['final_delta_median'], '.2f')} | {f(r1['final_window_fraction_above_prior_delta_median'], '.4f')} | "
                 f"{f(r2['final_window_quantile_median'], '.3g')} | {f(r2['final_delta_median'], '.2f')} | {f(r2['final_window_fraction_above_prior_delta_median'], '.4f')} | {f(q99, '.3g')} | {f(p1, '.4f')} |")
    L += ["", "## Per model absolute (seed medians)", ""]
    for arm in ARMS:
        L += [f"### {arm}", "", "| model | gates | ESS/grad x1e3 | min bulk ESS | grads | leaves/orbit | grads/leaf | final h (seed 1 / 2 / 3) | final delta (seed 1 / 2 / 3) | depth caps | div | max R-hat | max abs z |", "|---|---|---:|---:|---:|---:|---:|---|---|---|---|---:|---:|"]
        for m in models:
            e = per_model[m][arm]
            steps = " / ".join("[" + ", ".join(f"{x:.3g}" for x in st) + "]" for st in e["final_step_size"] if st)
            deltas = " / ".join("[" + ", ".join(f"{x:.3g}" for x in st) + "]" for st in e["final_max_error"] if st)
            L.append(f"| {m} | {e['n_passed']}/{e['n_cells']} | {f((e['min_bulk_ess_per_gradient']['median'] or float('nan')) * 1e3, '.3f')} | {f(e['min_bulk_ess']['median'], ',.0f')} | "
                     f"{f(e['gradients_total']['median'], ',.0f')} | {f(e['leaves_per_transition']['median'], '.1f')} | {f(e['gradients_per_leaf']['median'], '.3f')} | {steps} | {deltas} | "
                     f"{','.join(str(d) for d in e['max_depth_stops']['values'])} | {','.join(str(d) for d in e['divergences'])} | {f(e['max_rank_rhat']['median'], '.4f')} | {f(e['max_abs_z']['median'], '.2f')} |")
        L.append("")
    L += ["## Funnel at the sampler defaults (4 x 2,000 / 20,000; exact P(omega<-5) 0.0478, P(omega<-6) 0.0228, Var 9)", "",
          f"Decisive (C4, C5): study seeds {', '.join(map(str, SEEDS))}; the other nine seeds are descriptive.", "",
          "| arm | seed | P(<-5) | z (MCSE) | P(<-6) | Var omega | R-hat | bulk ESS | div | exhaust | gross-safe | healthy | final delta per chain | calls |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---:|"]
    for arm in ARMS:
        fz = funnel.get(arm, {})
        for seed, p in fz.get("per_seed", {}).items():
            L.append(f"| {arm} | {seed}{' *' if int(seed) in SEEDS else ''} | {p['estimate']:.4f} | {p['z']:+.2f} | {p['estimate_6']:.4f} | {p['omega_variance']:.2f} | {p['omega_rhat']:.3f} | {p['omega_bulk_ess']:.0f} | "
                     f"{p['divergences']} | {p['refinement_exhaustions']} | {p['gross_safety']['passed']} | {p['healthy']} | {', '.join(f'{x:.2f}' for x in p['final_max_error'])} | {p['target_calls_total']:,} |")
        for seed, e in fz.get("errors", {}).items():
            L.append(f"| {arm} | {seed} | error: {e.get('stderr', '')[-120:]!r} |")
    L += ["", "| arm | z ok (3 study) | gross-safe (3 study) | |z|<=2 (12) | gross-safe (12) | divergence-free (12) | healthy (12) | divergences (12) | exhaustions (12) | pooled P(<-5) | pooled P(<-6) | calls (12) |",
          "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for arm in ARMS:
        fz = funnel.get(arm, {})
        L.append(f"| {arm} | {fz.get('all_study_seeds_abs_z_le_2')} | {fz.get('all_study_seeds_gross_safe')} | {fz.get('seeds_abs_z_le_2_all12')} | {fz.get('seeds_gross_safe_all12')} | "
                 f"{fz.get('seeds_divergence_free_all12')} | {fz.get('seeds_healthy_all12')} | {fz.get('total_divergences_all12')} | {fz.get('total_refinement_exhaustions_all12')} | "
                 f"{f(fz.get('pooled_p5_all12'), '.4f')} | {f(fz.get('pooled_p6_all12'), '.4f')} | {f(fz.get('total_target_calls_all12'), ',')} |")
    L += ["", "## Eight Schools strict track (secondary; WP37A amended track: h0 0.3, depth 8, eight levels, DA 0.95, 4 x 1,000/1,000, threads 1, three bit-identical repetitions)", "",
          "| arm | calls per seed | min bulk ESS | max R-hat | div / exhaust | geomean min bulk ESS/call | ratio to da | all healthy | final delta (seed 1) |", "|---|---|---|---|---|---:|---:|---|---|"]
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
        d_s = ", ".join(f"{x:.3g}" for x in first["final_max_error"])
        L.append(f"| {arm} | {calls_s} | {ess_s} | {rhat_s} | {div_s} | {f(g, '.5f')} | {f((g / es_da) if (g and es_da) else None, '.3f')} | {e.get('all_healthy')} | {d_s} |")
    L += ["", "## Decision rule (recommend an adaptive rule as default iff C1 geomean >= 1.10x da over 17, C2 no model < 0.85x, C3 gates >= da, C4 funnel |z| <= 2 on every study seed, C5 funnel gross safety on every study seed)", "",
          "| arm | C1 | C2 | C3 | C4 | C5 | all held | Eight Schools ratio (secondary) |", "|---|---|---|---|---|---|---|---|"]
    for arm, c in rule.items():
        L.append(f"| {arm} | {f(c['C1_geomean_ge']['value'], '.3f')} ({c['C1_geomean_ge']['held']}) | {f(c['C2_no_model_below']['value'], '.2f')} {c['C2_no_model_below']['argmin']} ({c['C2_no_model_below']['held']}) | "
                 f"{c['C3_gates_ge_da']['value']} vs {c['C3_gates_ge_da']['da']} ({c['C3_gates_ge_da']['held']}) | {c['C4_funnel_abs_z_le_2']['value']} ({c['C4_funnel_abs_z_le_2']['held']}) | "
                 f"{c['C5_funnel_gross_safety']['value']} ({c['C5_funnel_gross_safety']['held']}) | **{c['all_held']}** | {f(c['secondary_eight_schools_ratio']['value'], '.3f')} |")
    L += ["", f"Candidate arms meeting the rule: {', '.join(recommend) or 'none'} (`d2` is a control and cannot be recommended).", "",
          "## Predictions (frozen in protocol.json, scored mechanically)", "", "| prediction | predicted | observed | held |", "|---|---|---|---|"]
    for k, v in predictions.items():
        if k.startswith("delta_landing_"):
            for cls, r in v.items():
                L.append(f"| {k} / {cls} | {r['predicted']} | {f(r['observed_median_over_models'], '.2f')} | {r['held']} |")
        else:
            obs = v.get("observed", v.get("observed_median"))
            L.append(f"| {k} | {v['predicted']} | {obs if isinstance(obs, bool) else f(obs, '.3f')} | {v['held']} |")
    (ART / "results-table.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] == "run":
        instrument = False
        models, arms = PROTOCOL["models"], ARMS
        for a in args[1:]:
            if a.startswith("--models="):
                models = a.split("=", 1)[1].split(",")
            elif a.startswith("--arms="):
                arms = a.split("=", 1)[1].split(",")
        run_all(models, arms, instrument)
    elif args[0] == "build":
        build_all(PROTOCOL["models"])
    elif args[0] == "cell":
        run_model_arm(args[1], args[2], False)
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
