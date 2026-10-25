#!/usr/bin/env python3
"""posteriordb breadth study v1 (WP46) driver: the shipped oWALNUTS defaults on posteriors never used before.

    python run_breadth.py prepare            # compile every protocol model with BridgeStan (no sampling)
    python run_breadth.py run                # every model/seed in protocol order (resumable)
    python run_breadth.py cell <model>       # one model, all seeds (used as a child process)
    python run_breadth.py analyze            # artifacts/summary.json + results-table.md

Derived from STUDIES/posteriordb_bench_v6/run_posteriordb.py (same estimators, gates,
z statistic, constraint path and cell layout); CmdStan, nutpie and the funnel row are
removed, a gates-only tier for posteriors without reference draws is added, and the
per-cell telemetry needed for the failure taxonomy is recorded.

Each cell writes `artifacts/cells/<model>-owalnuts-da-<seed>.json` (metrics, no draws)
and `artifacts/draws/<model>-owalnuts-da-<seed>.npz` (ignored by git). Failures are
recorded as cells with status != "ok".
"""
from __future__ import annotations

import hashlib
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
HARNESS = HERE / "target" / "release" / "posteriordb-breadth-v1.exe"
ARM = "owalnuts-da"
SEEDS = PROTOCOL["seeds"]
TIMEOUT = PROTOCOL["cell_timeout_seconds"]
REFERENCE_TIER = PROTOCOL["tiers"]["reference"]["models"]
GATES_ONLY_TIER = PROTOCOL["tiers"]["gates_only"]["models"]
ALL_MODELS = REFERENCE_TIER + GATES_ONLY_TIER
CLASSIFIER = PROTOCOL["taxonomy"]["mechanical_classifier"]
os.environ.setdefault("MAKE", "mingw32-make")
# No STAN_THREADS (v1 wall-gap finding); identical to v6.
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


def reference(model: str) -> dict | None:
    """Reference draws as (chains, draws, P) with column names and ArviZ summaries; None for the gates-only tier."""
    if model not in REFERENCE_TIER:
        return None
    p = posterior(model)
    ref = p.reference_draws()
    names = list(ref[0].keys())
    arr = np.asarray([[c[n] for n in names] for c in ref], dtype=np.float64)  # (chains, P, draws)
    arr = np.transpose(arr, (0, 2, 1))
    return {"names": names, "draws": arr, **arviz_stats(arr)}


# --------------------------------------------------------------------------- compilation


def prepare_bridgestan(model: str) -> tuple[Path, Path]:
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


def chain_disagreement(draws: np.ndarray) -> dict:
    """max over parameters and chains of |chain mean - mean of the other chains| / pooled sd."""
    chains = draws.shape[0]
    pooled_sd = draws.reshape(-1, draws.shape[-1]).std(0, ddof=1)
    cm = draws.mean(1)  # (chains, P)
    worst, worst_chain, worst_param = 0.0, None, None
    per_chain = []
    for c in range(chains):
        others = np.delete(cm, c, axis=0).mean(0)
        with np.errstate(divide="ignore", invalid="ignore"):
            d = np.abs(cm[c] - others) / pooled_sd
        d = np.where(np.isfinite(d), d, 0.0)
        per_chain.append(float(d.max()) if d.size else 0.0)
        if d.size and d.max() > worst:
            worst, worst_chain, worst_param = float(d.max()), c, int(d.argmax())
    return {"max": worst, "chain": worst_chain, "param_index": worst_param, "per_chain": per_chain}


def metrics(model: str, seed: int, draws: np.ndarray, names: list[str], ref: dict | None,
            wall: float, grads_total: int, grads_sampling: int, divergences: int,
            max_depth_stops: int, extra: dict) -> dict:
    """draws: (chains, draws, P) on the parameter set (reference columns, or all constrained parameters)."""
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
    dis = chain_disagreement(draws)
    out = {
        "schema": "posteriordb-breadth-v1-cell-metrics",
        "model": model, "arm": ARM, "seed": seed, "status": "ok",
        "tier": "reference" if ref is not None else "gates_only",
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
        "argmin_tail_ess": names[int(np.nanargmin(st["tail_ess"]))],
        "argmax_rank_rhat": names[int(np.nanargmax(st["rhat"]))],
        "min_bulk_ess_per_gradient": min_bulk / grads_total,
        "min_tail_ess_per_gradient": min_tail / grads_total,
        "min_bulk_ess_per_second": min_bulk / wall,
        "chain_disagreement_max": dis["max"],
        "chain_disagreement_chain": dis["chain"],
        "chain_disagreement_param": names[dis["param_index"]] if dis["param_index"] is not None else None,
        "chain_disagreement_per_chain": dis["per_chain"],
        "gates": gates,
        "passed": all(gates.values()),
        **extra,
    }
    per_param = {}
    if ref is not None:
        z = (st["mean"] - ref["mean"]) / np.sqrt(st["mcse"] ** 2 + ref["mcse"] ** 2)
        dsd = np.abs(st["mean"] - ref["mean"]) / ref["sd"]
        # per-chain displacement from the reference mean, in reference sd
        with np.errstate(divide="ignore", invalid="ignore"):
            chain_disp = np.abs(draws.mean(1) - ref["mean"][None, :]) / ref["sd"][None, :]
        chain_disp = np.where(np.isfinite(chain_disp), chain_disp, 0.0)
        out.update({
            "max_abs_z": float(np.nanmax(np.abs(z))),
            "argmax_abs_z": names[int(np.nanargmax(np.abs(z)))],
            "n_params_abs_z_gt_4": int(np.sum(np.abs(z) > 4)),
            "n_params_abs_z_gt_3": int(np.sum(np.abs(z) > 3)),
            "max_abs_dmean_over_ref_sd": float(np.nanmax(dsd)),
            "agreement_flag": bool(np.nanmax(np.abs(z)) > 4),
            "per_chain_max_displacement_ref_sd": [float(x) for x in chain_disp.max(1)],
            "reference_min_bulk_ess": float(np.nanmin(ref["bulk_ess"])),
            "reference_max_rank_rhat": float(np.nanmax(ref["rhat"])),
            "reference_chains_draws": list(ref["draws"].shape[:2]),
        })
        for i, n in enumerate(names):
            per_param[n] = {
                "mean": float(st["mean"][i]), "sd": float(st["sd"][i]), "mcse": float(st["mcse"][i]),
                "bulk_ess": float(st["bulk_ess"][i]), "tail_ess": float(st["tail_ess"][i]),
                "rhat": float(st["rhat"][i]), "ref_mean": float(ref["mean"][i]), "ref_sd": float(ref["sd"][i]),
                "ref_mcse": float(ref["mcse"][i]), "z": float(z[i]), "abs_dmean_over_ref_sd": float(dsd[i]),
            }
    else:
        out.update({"max_abs_z": None, "agreement_flag": None})
        for i, n in enumerate(names):
            per_param[n] = {
                "mean": float(st["mean"][i]), "sd": float(st["sd"][i]), "mcse": float(st["mcse"][i]),
                "bulk_ess": float(st["bulk_ess"][i]), "tail_ess": float(st["tail_ess"][i]),
                "rhat": float(st["rhat"][i]),
            }
    out["parameters"] = per_param
    return out


def failure(model: str, seed: int, status: str, message: str, **extra) -> dict:
    return {
        "schema": "posteriordb-breadth-v1-cell-metrics", "model": model, "arm": ARM, "seed": seed,
        "tier": "reference" if model in REFERENCE_TIER else "gates_only",
        "status": status, "error": message, "passed": False,
        "gates": {"no_sampler_error": False}, **extra,
    }


def cell_path(model: str, seed: int) -> Path:
    return CELLS / f"{short(model)}-{ARM}-{seed}.json"


def write_cell(cell: dict) -> None:
    CELLS.mkdir(parents=True, exist_ok=True)
    cell_path(cell["model"], cell["seed"]).write_text(json.dumps(cell, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if cell["status"] == "ok":
        z = cell.get("max_abs_z")
        log(f"  {cell['seed']}: wall {cell['wall_seconds']:.1f}s grads {cell['gradients_total']} "
            f"minbulk {cell['min_bulk_ess']:.0f} mintail {cell['min_tail_ess']:.0f} rhat {cell['max_rank_rhat']:.4f} "
            f"div {cell['divergences']} caps {cell['depth_cap_fraction']:.3f} "
            f"max|z| {'-' if z is None else f'{z:.2f}'} passed {cell['passed']}")
    else:
        log(f"  {cell['seed']}: {cell['status']}: {cell.get('error', '')[:200]}")


# --------------------------------------------------------------------------- the oWALNUTS cell


def sum_lists(lists):
    return [sum(x) for x in zip(*lists)]


def run_owalnuts(model: str, seed: int, ref: dict | None) -> dict:
    import bridgestan as bs

    so, data = prepare_bridgestan(model)
    raw = DRAWS / f"{short(model)}-{ARM}-{seed}.raw.json"
    DRAWS.mkdir(parents=True, exist_ok=True)
    if raw.exists():
        raw.unlink()
    cmd = [str(HARNESS), str(so), str(data), "da", str(seed), str(raw), str(PROTOCOL["threads"])]
    t0 = time.perf_counter()
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return failure(model, seed, "timeout", f"exceeded {TIMEOUT}s", elapsed_seconds=time.perf_counter() - t0)
    if cp.returncode != 0 or not raw.exists():
        msg = (cp.stderr or "").strip()[-2000:]
        extra = {"returncode": cp.returncode}
        if raw.exists():
            try:
                partial = json.loads(raw.read_text(encoding="utf-8"))
                extra["harness_stage"] = partial.get("stage")
                extra["harness_error"] = partial.get("error")
                extra["harness_target_calls"] = partial.get("target_calls")
            except Exception:  # noqa: BLE001
                pass
        return failure(model, seed, "error", msg or f"exit {cp.returncode} with no stderr", **extra)
    out = json.loads(raw.read_text(encoding="utf-8"))
    if out.get("status") != "ok":
        return failure(model, seed, "error", out.get("error", "unknown"), wall_seconds=out.get("wall_seconds"))
    bs.compile.windows_dll_path_setup()
    sm = bs.StanModel(str(so), data=data.read_text(encoding="utf-8"), seed=1)
    include_tp = ref is not None
    cnames = [bridgestan_name(n) for n in sm.param_names(include_tp=include_tp, include_gq=False)]
    unc = np.asarray([c["samples"] for c in out["chains_data"]], dtype=np.float64)  # (chains, draws, dim)
    con = np.empty(unc.shape[:2] + (len(cnames),))
    for c in range(unc.shape[0]):
        for d in range(unc.shape[1]):
            con[c, d] = sm.param_constrain(unc[c, d], include_tp=include_tp, include_gq=False)
    if ref is not None:
        index = {n: i for i, n in enumerate(cnames)}
        missing = [n for n in ref["names"] if n not in index]
        if missing:
            return failure(model, seed, "error", f"reference parameters not produced by param_constrain: {missing[:5]}")
        names = ref["names"]
        draws = con[:, :, [index[n] for n in names]]
    else:
        names = cnames
        draws = con
    chains = out["chains_data"]
    retained_n = out["retained"] * len(chains)
    grads_sampling = sum(c["retained_target_calls"] for c in chains)
    grads_total = out["target_calls_total"]
    rw = [c["retained_work"] for c in chains]
    ww = [c["warmup_work"] for c in chains]
    level_built = sum_lists([w["refinement_level_built"] for w in rw])
    leaves_built = sum(w["leaves_built"] for w in rw)
    stops: dict[str, int] = {}
    for c in chains:
        for k, v in c["retained_stop_histogram"].items():
            stops[k] = stops.get(k, 0) + v
    final_steps = [c["final_step_size"] for c in chains]
    med_step = statistics.median(final_steps)
    # Metric floor check: installed inverse-metric variance (1 / mass) against the retained
    # unconstrained variance of the same chain, per coordinate.
    floor_t = CLASSIFIER["thresholds"]
    metric_ratio_max, metric_floor_coords = [], []
    for ci, c in enumerate(chains):
        installed = 1.0 / np.asarray(c["mass_diagonal"], dtype=float)
        emp = unc[ci].var(0, ddof=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = installed / emp
        ratio = np.where(np.isfinite(ratio), ratio, 0.0)
        metric_ratio_max.append(float(ratio.max()))
        hits = np.where((ratio > floor_t["metric_floor_installed_over_empirical"]) & (emp < floor_t["metric_floor_empirical_variance_below"]))[0]
        metric_floor_coords.append([int(i) for i in hits[:20]])
    # A recoverable target failure is also counted as a zero-density evaluation; take the larger, not the sum.
    def bad(w):
        return max(w["recoverable_target_failures"], w["zero_density_evaluations"]) + w["nonfinite_position_rejections"]
    invalid_like = sum(bad(w) for w in rw)
    invalid_like_warmup = sum(bad(w) for w in ww)
    extra = {
        "final_step_size": final_steps,
        "median_final_step": med_step,
        "min_step_ratio_to_median": min(final_steps) / med_step if med_step > 0 else None,
        "final_max_error": [c["final_max_error"] for c in chains],
        "depth_cap_fraction": sum(c["maximum_depth_stops"] for c in chains) / retained_n,
        "depth_caps_per_chain": [c["maximum_depth_stops"] for c in chains],
        "warmup_depth_caps_per_chain": [c["warmup_maximum_depth_stops"] for c in chains],
        "retained_leaves_built": leaves_built,
        "retained_refinement_level_built": level_built,
        "refined_leaf_fraction": (leaves_built - level_built[0]) / leaves_built if leaves_built else float("nan"),
        "refined_leaf_fraction_per_chain": [
            (w["leaves_built"] - w["refinement_level_built"][0]) / w["leaves_built"] if w["leaves_built"] else None for w in rw
        ],
        "leaves_per_transition": leaves_built / retained_n,
        "retained_stop_histogram": stops,
        "reverse_coarser_stop_fraction": stops.get("reverse_coarser_accepted", 0) / retained_n,
        "invalid_stops": sum(c["invalid_stops"] for c in chains),
        "refinement_exhaustions": sum(c["refinement_exhaustions"] for c in chains),
        "refinement_exhaustions_per_chain": [c["refinement_exhaustions"] for c in chains],
        "frozen_chains": sum(1 for c in chains if c["refinement_exhaustions"] > out["retained"] // 2),
        "retained_invalid_like_evaluations": invalid_like,
        "retained_invalid_like_fraction": invalid_like / grads_sampling if grads_sampling else None,
        "warmup_invalid_like_evaluations": invalid_like_warmup,
        "recoverable_failures_total": out["recoverable_failures_total"],
        "retained_work_per_chain": rw,
        "warmup_work_per_chain": ww,
        "warmup_stop_histogram_per_chain": [c["warmup_stop_histogram"] for c in chains],
        "warmup_step_trace_every_50": [c["warmup_step_trace_every_50"] for c in chains],
        "retained_step_quantiles": [c["retained_step_quantiles"] for c in chains],
        "retained_initial_hamiltonian_quantiles": [c["retained_initial_hamiltonian_quantiles"] for c in chains],
        "retained_max_abs_energy_error_quantiles": [c["retained_max_abs_energy_error_quantiles"] for c in chains],
        "start_search_calls": out["init"]["start_search_calls"],
        "starts": out.get("starts"),
        "tuning": out["tuning"],
        "warmup_config": out["warmup_config"],
        "threading": out.get("threading"), "replicas": out.get("replicas"),
        "requested_replicas": out.get("requested_replicas"), "execution": out.get("execution"),
        "metric_installed_over_empirical_variance_max": metric_ratio_max,
        "metric_floor_coordinates": metric_floor_coords,
        "mass_diagonal_max": [max(c["mass_diagonal"]) for c in chains],
        "mass_diagonal_min": [min(c["mass_diagonal"]) for c in chains],
        "warmup_divergences": sum(c["warmup_divergences"] for c in chains),
        "divergences_per_chain": [c["divergences"] for c in chains],
        "retained_depth_histogram": sum_lists([c["retained_depth_histogram"] for c in chains]),
        "retained_refinement_level_histogram": sum_lists([c["retained_refinement_level_histogram"] for c in chains]),
        "rescue_events": sum(len(c.get("chain_rescues", [])) for c in chains),
        "algorithm_revision": out["algorithm_revision"],
        "unconstrained_dimension": out["dimension"],
        "wall_label": "contended shared-machine wall (ten agents on 16 cores; Windows owned BridgeStan worker serialises gradient calls)",
        "per_chain_bulk_ess_min": [float(np.nanmin(arviz_stats(draws[i:i + 1])["bulk_ess"])) for i in range(draws.shape[0])],
    }
    cell = metrics(model, seed, draws, names, ref, out["wall_seconds"], grads_total, grads_sampling,
                   sum(c["divergences"] for c in chains), sum(c["maximum_depth_stops"] for c in chains), extra)
    cell["mechanism"] = classify(cell)
    np.savez_compressed(DRAWS / f"{short(model)}-{ARM}-{seed}.npz", draws=draws, names=np.asarray(names), unconstrained=unc)
    raw.unlink()  # the npz keeps the unconstrained draws; the raw JSON is large
    return cell


# --------------------------------------------------------------------------- frozen mechanical classifier


def borderline(cell: dict) -> bool:
    b = CLASSIFIER["borderline"]
    if cell.get("status") != "ok" or not cell.get("passed"):
        return False
    z = cell.get("max_abs_z")
    return bool(cell["max_rank_rhat"] > b["rank_rhat_above"]
                or min(cell["min_bulk_ess"], cell["min_tail_ess"]) < b["min_ess_below"]
                or (z is not None and z > b["abs_z_above"]))


def classify(cell: dict) -> dict:
    """Every label whose frozen telemetry rule fires, in protocol order; primary = first."""
    t = CLASSIFIER["thresholds"]
    labels = []
    if cell.get("status") != "ok":
        return {"labels": ["process_error"], "primary": "process_error", "failing": True, "borderline": False}
    h0 = [q["q50"] if q else None for q in cell["retained_initial_hamiltonian_quantiles"]]
    h0_iqr = [(q["q75"] - q["q25"]) if q else None for q in cell["retained_initial_hamiltonian_quantiles"]]
    dis = cell["chain_disagreement_max"]
    if dis > t["chain_disagreement_sd"] and cell["max_rank_rhat"] > PROTOCOL["gates"]["max_rank_rhat"]:
        c = cell["chain_disagreement_chain"]
        others = [h for i, h in enumerate(h0) if i != c and h is not None]
        iqr = statistics.median([x for x in h0_iqr if x is not None]) if any(x is not None for x in h0_iqr) else 0.0
        if h0[c] is not None and others and (h0[c] - statistics.median(others)) > max(t["start_lottery_h0_nats"], t["start_lottery_h0_iqr"] * iqr):
            labels.append("start_lottery")
        else:
            labels.append("multimodality")
    if cell["depth_cap_fraction"] > t["depth_cap_fraction"]:
        labels.append("depth_cap")
    if cell["min_step_ratio_to_median"] is not None and cell["min_step_ratio_to_median"] < t["step_collapse_ratio"]:
        labels.append("step_collapse")
    if any(cell["metric_floor_coordinates"]):
        labels.append("metric_floor")
    if (cell["retained_invalid_like_fraction"] or 0) > t["invalid_fraction"] or cell["invalid_stops"] > 0:
        labels.append("constraint_boundary")
    if cell["divergences"] > 0:
        labels.append("divergence")
    z = cell.get("max_abs_z")
    if z is not None and z > t["reference_z"] and dis <= t["chain_disagreement_sd"]:
        labels.append("reference_draw_disagreement")
    failing = not cell["passed"]
    border = borderline(cell)
    if (failing or border) and not labels:
        labels.append("unclassified_slow_mixing")
    return {"labels": labels, "primary": labels[0] if labels else None, "failing": failing, "borderline": border}


# --------------------------------------------------------------------------- orchestration


def run_model(model: str) -> None:
    ref = reference(model)
    for seed in SEEDS:
        if cell_path(model, seed).exists():
            continue
        try:
            cell = run_owalnuts(model, seed, ref)
        except Exception as e:  # noqa: BLE001
            cell = failure(model, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
        if cell.get("status") != "ok":
            cell["mechanism"] = classify(cell)
        write_cell(cell)


def machine_record() -> None:
    ART.mkdir(exist_ok=True)
    machine = ART / "measured_on.json"
    if not machine.exists():
        machine.write_text(json.dumps({
            "platform": platform.platform(), "processor": platform.processor(),
            "cpu_count": os.cpu_count(), "python": sys.version.split()[0],
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "note": "shared machine; ten agents run concurrently; walls are contended upper bounds",
        }, indent=2) + "\n", encoding="utf-8")


def prepare_all() -> None:
    status = {}
    for model in ALL_MODELS:
        try:
            t = time.perf_counter()
            prepare_bridgestan(model)
            status[model] = {"compiled": True, "seconds": time.perf_counter() - t}
        except Exception as e:  # noqa: BLE001
            status[model] = {"compiled": False, "error": str(e)[-1500:]}
        log(f"{model}: {status[model]}")
    ART.mkdir(exist_ok=True)
    (ART / "compile-status.json").write_text(json.dumps(status, indent=1) + "\n", encoding="utf-8")


def run_all(models: list[str]) -> None:
    machine_record()
    for model in models:
        log(f"== {model}")
        if all(cell_path(model, s).exists() for s in SEEDS):
            continue
        try:
            prepare_bridgestan(model)
        except Exception as e:  # noqa: BLE001
            for seed in SEEDS:
                if not cell_path(model, seed).exists():
                    c = failure(model, seed, "compile_error", str(e)[-2000:])
                    c["mechanism"] = classify(c)
                    write_cell(c)
            continue
        cmd = [sys.executable, str(Path(__file__)), "cell", model]
        try:
            cp = subprocess.run(cmd, timeout=TIMEOUT * len(SEEDS) + 900, text=True)
            if cp.returncode != 0:
                log(f"child for {model} exited {cp.returncode}")
        except subprocess.TimeoutExpired:
            log(f"child for {model} timed out")
        for seed in SEEDS:
            if not cell_path(model, seed).exists():
                c = failure(model, seed, "timeout_or_crash", "child process ended without writing the cell")
                c["mechanism"] = classify(c)
                write_cell(c)


# --------------------------------------------------------------------------- analysis


def geomean(xs):
    xs = [x for x in xs if x and math.isfinite(x) and x > 0]
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs))) if xs else float("nan")


def analyze() -> None:
    cells = {}
    for path in sorted(CELLS.glob("*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        c.pop("parameters", None)
        for k in ("retained_work_per_chain", "warmup_work_per_chain", "starts"):
            c.pop(k, None)
        cells.setdefault(c["model"], {})[str(c["seed"])] = c
    per_model = {}
    for model in ALL_MODELS:
        seeds = cells.get(model, {})
        ok = [c for c in seeds.values() if c.get("status") == "ok"]
        per_model[model] = {
            "tier": "reference" if model in REFERENCE_TIER else "gates_only",
            "family": PROTOCOL["families"].get(model),
            "n_cells": len(seeds), "n_ok": len(ok), "n_passed": sum(1 for c in ok if c["passed"]),
            "statuses": {s: c.get("status") for s, c in seeds.items()},
            "mechanisms": {s: c.get("mechanism") for s, c in seeds.items()},
            "median_bulk_ess_per_gradient": statistics.median([c["min_bulk_ess_per_gradient"] for c in ok]) if ok else None,
        }
    ref_cells = [c for m in REFERENCE_TIER for c in cells.get(m, {}).values()]
    go_cells = [c for m in GATES_ONLY_TIER for c in cells.get(m, {}).values()]
    ref_pass = sum(1 for c in ref_cells if c.get("passed"))
    go_pass = sum(1 for c in go_cells if c.get("passed"))
    passing_z = [f"{c['model']}/{c['seed']}={c['max_abs_z']:.3f}" for c in ref_cells
                 if c.get("passed") and c.get("max_abs_z") is not None and c["max_abs_z"] > 4]
    any_z = [f"{c['model']}/{c['seed']}={c['max_abs_z']:.3f}" for c in ref_cells
             if c.get("status") == "ok" and c.get("max_abs_z") is not None and c["max_abs_z"] > 4]
    flagged = [c for m in ALL_MODELS for c in cells.get(m, {}).values()
               if (c.get("mechanism") or {}).get("failing") or (c.get("mechanism") or {}).get("borderline")]
    primary_counts: dict[str, int] = {}
    label_counts: dict[str, int] = {}
    for c in flagged:
        mech = c["mechanism"]
        primary_counts[mech["primary"]] = primary_counts.get(mech["primary"], 0) + 1
        for lab in mech["labels"]:
            label_counts[lab] = label_counts.get(lab, 0) + 1
    ref_fail_primary: dict[str, int] = {}
    for c in ref_cells:
        if not c.get("passed") and c.get("mechanism"):
            ref_fail_primary[c["mechanism"]["primary"]] = ref_fail_primary.get(c["mechanism"]["primary"], 0) + 1
    pred = PROTOCOL["predictions"]
    failing_models = sorted({c["model"] for c in ref_cells + go_cells if not c.get("passed")})
    predicted_failing = pred["P2_failing_families"]["models"]
    summary = {
        "schema": "posteriordb-breadth-v1-summary",
        "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "reference_tier": {"cells": len(ref_cells), "passed": ref_pass,
                           "pass_rate": ref_pass / len(ref_cells) if ref_cells else None},
        "gates_only_tier": {"cells": len(go_cells), "passed": go_pass,
                            "pass_rate": go_pass / len(go_cells) if go_cells else None},
        "passing_cells_max_abs_z_gt_4": passing_z,
        "all_ok_cells_max_abs_z_gt_4": any_z,
        "flagged_cells": [{"model": c["model"], "seed": c["seed"], **c["mechanism"]} for c in flagged],
        "primary_mechanism_counts": primary_counts,
        "label_counts": label_counts,
        "failing_models": failing_models,
        "predictions": {
            "P1_reference_tier_pass_count": {
                "predicted": pred["P1_reference_pass_rate"]["predicted_passes"],
                "interval": pred["P1_reference_pass_rate"]["interval"],
                "value": ref_pass,
                "held": pred["P1_reference_pass_rate"]["interval"][0] <= ref_pass <= pred["P1_reference_pass_rate"]["interval"][1],
                "below_v6_rate": (ref_pass / len(ref_cells)) < 45 / 51 if ref_cells else None,
            },
            "P2_failing_families": {
                "predicted_models": predicted_failing,
                "observed_failing_models": failing_models,
                "predicted_and_failed": sorted(set(predicted_failing) & set(failing_models)),
                "predicted_but_clean": sorted(set(predicted_failing) - set(failing_models)),
                "unpredicted_failures": sorted(set(failing_models) - set(predicted_failing)),
            },
            "P3_gates_only_tier_pass_count": {
                "interval": pred["P3_gates_only_pass_count"]["interval"], "value": go_pass,
                "held": pred["P3_gates_only_pass_count"]["interval"][0] <= go_pass <= pred["P3_gates_only_pass_count"]["interval"][1],
            },
            "P4_passing_reference_cells_max_abs_z_le_4": {"value": passing_z, "held": not passing_z},
            "P6_modal_primary_mechanism_failing_reference_cells": {
                "counts": ref_fail_primary,
                "value": max(ref_fail_primary, key=ref_fail_primary.get) if ref_fail_primary else None,
                "held": (max(ref_fail_primary.values()) == ref_fail_primary.get("depth_cap", -1)) if ref_fail_primary else None,
            },
            "P5_no_process_errors": {
                "value": [f"{c['model']}/{c['seed']}:{c['status']}" for c in ref_cells + go_cells if c.get("status") != "ok"],
                "held": all(c.get("status") == "ok" for c in ref_cells + go_cells),
            },
        },
        "per_model": per_model,
        "cells": cells,
    }
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    def f(x, fmt):
        return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)

    lines = ["# posteriordb breadth v1 (WP46) — results", "",
             "oWALNUTS shipped defaults, 4 x 1,000/1,000, seeds " + ", ".join(map(str, SEEDS)) + ". Gates: rank R-hat <= 1.01, "
             "bulk and tail ESS >= 400 on every gate parameter, zero retained divergences. `caps` = retained depth-10 "
             "fraction; `refined` = retained refined-leaf fraction; `inv` = retained invalid/zero-density/non-finite "
             "evaluations; `exh` = retained refinement exhaustions; walls are contended (ten agents, 16 cores, Windows "
             "owned BridgeStan worker serialises gradients) and are not evidence.", "",
             "| tier | model | seed | pass | min bulk | min tail | max R-hat | div | max abs z | median h | min h/median | caps | refined | inv | exh | chain disagr. (sd) | grads | ESS/grad x1e3 | wall s | mechanism |",
             "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for model in ALL_MODELS:
        for seed in SEEDS:
            c = cells.get(model, {}).get(str(seed))
            tier = "ref" if model in REFERENCE_TIER else "gates"
            if c is None:
                lines.append(f"| {tier} | {model} | {seed} | not run |" + " |" * 17)
                continue
            mech = c.get("mechanism") or {}
            mtxt = ",".join(mech.get("labels") or []) or "—"
            if mech.get("borderline"):
                mtxt = "borderline: " + mtxt
            if c.get("status") != "ok":
                lines.append(f"| {tier} | {model} | {seed} | {c['status']} |" + " |" * 16 + f" {mtxt} |")
                continue
            lines.append(
                f"| {tier} | {model} | {seed} | {'yes' if c['passed'] else 'NO'} | {c['min_bulk_ess']:.0f} | {c['min_tail_ess']:.0f} | "
                f"{c['max_rank_rhat']:.4f} | {c['divergences']} | {f(c.get('max_abs_z'), '.2f')} | {c['median_final_step']:.3g} | "
                f"{f(c['min_step_ratio_to_median'], '.2f')} | {c['depth_cap_fraction']:.3f} | {f(c['refined_leaf_fraction'], '.4f')} | "
                f"{c['retained_invalid_like_evaluations']} | {c['refinement_exhaustions']} | {c['chain_disagreement_max']:.2f} | "
                f"{c['gradients_total']:,} | {c['min_bulk_ess_per_gradient'] * 1e3:.3f} | {c['wall_seconds']:.1f} | {mtxt} |")
    lines += ["", f"Reference tier: **{ref_pass}/{len(ref_cells)}** cells pass. Gates-only tier: **{go_pass}/{len(go_cells)}**.", "",
              "## Mechanism counts over failing and borderline cells", "", "| label | primary | any |", "|---|---:|---:|"]
    for lab in sorted(set(primary_counts) | set(label_counts)):
        lines.append(f"| {lab} | {primary_counts.get(lab, 0)} | {label_counts.get(lab, 0)} |")
    lines += ["", "## Preregistered predictions", "", "| prediction | value | held |", "|---|---|---|"]
    for k, v in summary["predictions"].items():
        lines.append(f"| {k} | {json.dumps({kk: vv for kk, vv in v.items() if kk != 'held'})} | {v.get('held', 'reported')} |")
    (ART / "results-table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] == "run":
        models = ALL_MODELS
        for a in args[1:]:
            if a.startswith("--models="):
                models = a.split("=", 1)[1].split(",")
        run_all(models)
    elif args[0] == "cell":
        run_model(args[1])
    elif args[0] == "prepare":
        prepare_all()
    elif args[0] == "analyze":
        analyze()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
