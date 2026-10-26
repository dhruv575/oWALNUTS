#!/usr/bin/env python3
"""WP62 posteriordb v7 seed extension: fixed-16, oWALNUTS defaults vs CmdStan 2.39.0, three new seeds.

Made portable for the WP64 Linux reproduction; changes listed in AMENDMENTS.md. The pooled analysis
reads this study's own Linux v7 cells (artifacts/v7/cells), not the Windows ones. Artifacts go to
artifacts/ext/.

    python run_extension.py run       # every model / arm / seed in protocol order (resumable; no reruns)
    python run_extension.py analyze   # new-seed and pooled (v7 + new) statistics, leave-one-seed-out interval

The cell code (metrics, oWALNUTS and CmdStan arms) is the v7 driver's, unchanged; the v7
cells for the pooled analysis are read from ../posteriordb_bench_v7/artifacts/cells.
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
# WP64: the measurement constants are WP62's frozen protocol, read unchanged from its study directory.
PROTOCOL = json.loads((HERE.parent / "posteriordb_bench_v7_seed_extension" / "protocol.json").read_text(encoding="utf-8"))
STUDY = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
IS_WINDOWS = os.name == "nt"
EXE = ".exe" if IS_WINDOWS else ""
# Smoke tests (non-evidence seeds, before the freeze) redirect output with V7X_SMOKE_ART / V7X_SMOKE_SEEDS.
ART = Path(os.environ["V7X_SMOKE_ART"]) if os.environ.get("V7X_SMOKE_ART") else HERE / "artifacts" / "ext"
CELLS = ART / "cells"
DRAWS = ART / "draws"
MODELS = Path(os.environ.get("BENCH_MODELS", str(HERE / "models")))
CMDSTAN_MODELS = MODELS / "cmdstan"
PDB_PATH = Path(os.environ.get("POSTERIORDB_PATH", str(Path.home() / "infra" / "posteriordb" / "posterior_database")))
CMDSTAN_HOME = Path(os.environ.get("CMDSTAN_HOME", str(Path.home() / "infra" / "cmdstan" / "cmdstan-2.39.0")))
HARNESS = Path(os.environ.get("OWALNUTS_HARNESS", str(HERE / "target" / "release" / f"posteriordb-bench-v7{EXE}")))
SOURCE_TREE = Path(os.environ.get("OWALNUTS_SOURCE_TREE", str(REPO)))
COMMIT = STUDY["commits"]["ext"]["full"]
ARMS = PROTOCOL["arms_order"]
OWALNUTS_MODE = {"owalnuts": "defaults"}
HOUSE = PROTOCOL["models"]
NEW: list[str] = []
ALL_MODELS = HOUSE
V7_CELLS = HERE / "artifacts" / "v7" / "cells"
V7_SEEDS = PROTOCOL["v7_seeds"]
FIXED16 = PROTOCOL["fixed_non_arma_models"]
SEEDS = [int(x) for x in os.environ["V7X_SMOKE_SEEDS"].split(",")] if os.environ.get("V7X_SMOKE_SEEDS") else PROTOCOL["seeds"]
TIMEOUT = PROTOCOL["cell_timeout_seconds"]
if IS_WINDOWS:
    os.environ.setdefault("MAKE", "mingw32-make")


def short(model: str) -> str:
    return model.replace("-", "__")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------- Phase-2 guard


def amendment_commit() -> str:
    """The commit under test; refuses to run unless the library source equals it and the preregistration is committed."""
    if os.environ.get("V7X_SMOKE_ART"):
        return "smoke-test-not-evidence"
    head = subprocess.run(["git", "-C", str(SOURCE_TREE), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(SOURCE_TREE), "diff", "--quiet", "HEAD", "--",
                            "src", "integrations", "Cargo.toml", "tests"], capture_output=True)
    if head != COMMIT or dirty.returncode != 0:
        raise SystemExit(f"source tree {SOURCE_TREE} is not a clean checkout of the commit under test {COMMIT}")
    if not HARNESS.exists():
        raise SystemExit(f"harness {HARNESS} missing")
    for f in ("PREREGISTRATION.md", "protocol.json"):
        tracked = subprocess.run(["git", "-C", str(REPO), "ls-files", "--error-unmatch", str(HERE / f)], capture_output=True)
        changed = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "HEAD", "--", str(HERE / f)], capture_output=True)
        if tracked.returncode != 0 or changed.returncode != 0:
            raise SystemExit(f"{f} must be committed (and unmodified) before the first cell")
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
        "schema": "posteriordb-bench-v7-seed-extension-cell-metrics",
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
        "schema": "posteriordb-bench-v7-seed-extension-cell-metrics", "model": model, "arm": arm, "seed": seed,
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
    ref = reference(model)
    names = gate_names(model, ref)
    todo = [s for s in SEEDS if not cell_path(model, arm, s).exists()]
    if arm == "owalnuts":
        amendment_commit()
        for seed in todo:
            try:
                cell = run_owalnuts(model, arm, seed, ref, names)
            except Exception as e:  # noqa: BLE001
                cell = failure(model, arm, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
            write_cell(cell)
        return
    try:
        m = prepare_cmdstan(model)
    except Exception as e:  # noqa: BLE001
        for seed in todo:
            write_cell(failure(model, arm, seed, "compile_error", str(e)[-2000:]))
        return
    for seed in todo:
        try:
            cell = run_cmdstan(model, seed, ref, names, m)
        except Exception as e:  # noqa: BLE001
            cell = failure(model, arm, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
        write_cell(cell)


def run_all() -> None:
    log(f"commit under test: {amendment_commit()}")
    ART.mkdir(parents=True, exist_ok=True)
    machine = ART / "measured_on.json"
    if not machine.exists():
        machine.write_text(json.dumps({"platform": platform.platform(), "processor": platform.processor(),
                                       "cpu_count": os.cpu_count(), "python": sys.version.split()[0],
                                       "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
                                       "uname": " ".join(platform.uname()),
                                       "harness_sha256": hashlib.sha256(HARNESS.read_bytes()).hexdigest(),
                                       "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                       "note": STUDY["platform"]["wall_label_note"]},
                                      indent=2) + "\n", encoding="utf-8")
    for model in ALL_MODELS:
        log(f"== {model}")
        for arm in ARMS:
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
    xs = [x for x in xs if x is not None and math.isfinite(x) and x > 0]
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs))) if xs else float("nan")


def load(cdir: Path, seeds: list[int]) -> dict:
    out: dict = {}
    for m in ALL_MODELS:
        for arm in ARMS:
            for s in seeds:
                p = cdir / f"{short(m)}-{arm}-{s}.json"
                if p.exists():
                    c = json.loads(p.read_text(encoding="utf-8"))
                    c.pop("parameters", None)
                    out.setdefault(m, {}).setdefault(arm, {})[s] = c
    return out


def pooled_geomean(cells: dict, seeds: list[int], min_ok: int) -> tuple[float, list[str], dict]:
    """Per model and arm: median over status-ok cells among `seeds` of min bulk ESS per gradient.
    A model is included if both arms have at least `min_ok` ok cells; geomean of owalnuts / cmdstan."""
    ratios, used = {}, []
    for m in ALL_MODELS:
        med = {}
        for arm in ARMS:
            vals = [cells.get(m, {}).get(arm, {}).get(s) for s in seeds]
            vals = [c["min_bulk_ess_per_gradient"] for c in vals if c and c.get("status") == "ok"]
            med[arm] = statistics.median(vals) if len(vals) >= min_ok else None
        if med["owalnuts"] and med["cmdstan"]:
            ratios[m] = med["owalnuts"] / med["cmdstan"]
            used.append(m)
    return geomean(list(ratios.values())), used, ratios


def analyze() -> None:
    new = load(CELLS, SEEDS)
    old = load(V7_CELLS, V7_SEEDS)
    allc: dict = {}
    for source in (old, new):
        for m, arms in source.items():
            for arm, cs in arms.items():
                allc.setdefault(m, {}).setdefault(arm, {}).update(cs)
    all_seeds = V7_SEEDS + SEEDS
    rule = PROTOCOL["inclusion_rule"]
    g_new, m_new, r_new = pooled_geomean(new, SEEDS, rule["three_seed_min_ok"])
    g_v7, m_v7, r_v7 = pooled_geomean(old, V7_SEEDS, rule["three_seed_min_ok"])
    g_pool, m_pool, r_pool = pooled_geomean(allc, all_seeds, rule["pooled_six_min_ok"])
    loso = {}
    for drop in all_seeds:
        keep = [s for s in all_seeds if s != drop]
        g, ms, _ = pooled_geomean(allc, keep, rule["loso_five_min_ok"])
        loso[str(drop)] = {"geomean": g, "models": len(ms)}
    lv = [v["geomean"] for v in loso.values()]
    interval = [min(lv), max(lv)]
    per_seed = {}
    for s in all_seeds:
        g, ms, _ = pooled_geomean(allc, [s], 1)
        per_seed[str(s)] = {"geomean": g, "models": len(ms)}
    logs = [math.log(v["geomean"]) for v in per_seed.values() if math.isfinite(v["geomean"])]
    sd_log = statistics.stdev(logs) if len(logs) > 1 else float("nan")
    tol = PROTOCOL["seed_count_recommendation"]["half_width_log"]
    n_rec_single = math.ceil((2 * sd_log / tol) ** 2) if math.isfinite(sd_log) else None
    k = len(lv)
    lv_ok = [x for x in lv if math.isfinite(x)]
    jk_mean = statistics.mean(lv_ok) if lv_ok else float("nan")
    jk_se = math.sqrt((k - 1) / k * sum((x - jk_mean) ** 2 for x in lv_ok)) if len(lv_ok) == k else float("nan")
    hw = PROTOCOL["seed_count_recommendation"]["half_width_abs"]
    n_rec = math.ceil(k * (2 * jk_se / hw) ** 2) if math.isfinite(jk_se) else None

    def passes(cells: dict, arm: str) -> tuple[int, int]:
        cs = [c for m in ALL_MODELS for c in cells.get(m, {}).get(arm, {}).values()]
        return sum(1 for c in cs if c.get("passed")), len(cs)

    pc = {arm: {"new": passes(new, arm), "v7": passes(old, arm), "pooled": passes(allc, arm)} for arm in ARMS}

    def zviol(cells: dict) -> list[str]:
        return [f"{c['model']}/{c['seed']}={c['max_abs_z']:.3f}" for m in ALL_MODELS
                for c in cells.get(m, {}).get("owalnuts", {}).values()
                if c.get("passed") and c.get("max_abs_z") is not None and c["max_abs_z"] > 4]

    zmax_new = max((c["max_abs_z"] for m in ALL_MODELS for c in new.get(m, {}).get("owalnuts", {}).values()
                    if c.get("passed") and c.get("max_abs_z") is not None), default=None)
    pr = PROTOCOL["predictions"]
    preds = {
        "Q1_new_three_geomean_in_[0.65,0.95]": {"value": g_new, "models": len(m_new), "held": pr["Q1"]["low"] <= g_new <= pr["Q1"]["high"]},
        "Q2_pooled_six_geomean_in_[0.72,0.85]": {"value": g_pool, "models": len(m_pool), "held": pr["Q2"]["low"] <= g_pool <= pr["Q2"]["high"]},
        "Q3_loso_range_wider_than_0.08": {"value": interval[1] - interval[0], "interval": interval,
                                          "held": (interval[1] - interval[0]) > pr["Q3"]["width"]},
        "Q4_owalnuts_new_passes_ge_40_of_48": {"value": pc["owalnuts"]["new"][0], "held": pc["owalnuts"]["new"][0] >= pr["Q4"]["min"]},
        "reported_pooled_six_clears_0.75": {"value": g_pool >= 0.75},
        "reported_passing_owalnuts_abs_z_gt_4_new": {"value": zviol(new)},
        "reported_passing_owalnuts_abs_z_gt_4_pooled": {"value": zviol(allc)},
    }
    summary = {"schema": "posteriordb-bench-v7-seed-extension-summary", "commit": COMMIT[:8],
               "new_three": {"geomean": g_new, "models": m_new, "ratios": r_new},
               "v7_three_recomputed": {"geomean": g_v7, "models": m_v7, "ratios": r_v7},
               "pooled_six": {"geomean": g_pool, "models": m_pool, "ratios": r_pool},
               "leave_one_seed_out": loso, "seed_interval": interval, "per_seed_single_geomean": per_seed,
               "per_seed_log_sd": sd_log, "jackknife_se_pooled_geomean": jk_se,
               "recommended_seeds": {"primary_jackknife": {"half_width_abs": hw, "n": n_rec},
                                     "reported_single_seed_log_sd": {"half_width_log": tol, "n": n_rec_single}},
               "passes": pc, "max_abs_z_passing_owalnuts_new": zmax_new, "predictions": preds,
               "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
               "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    def f(x, fmt):
        return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)

    lines = ["# posteriordb v7 seed extension (WP62) — results", "",
             f"Commit `{summary['commit']}`. Ratio = oWALNUTS / CmdStan seed-median min-bulk-ESS per gradient. "
             f"New seeds {SEEDS}; v7 seeds {V7_SEEDS}.", "",
             "| model | new 3: passes oWALNUTS / CmdStan | new 3 ratio | v7 3 ratio | pooled 6 ratio |", "|---|---|---:|---:|---:|"]
    for m in ALL_MODELS:
        po = sum(1 for c in new.get(m, {}).get("owalnuts", {}).values() if c.get("passed"))
        pcm = sum(1 for c in new.get(m, {}).get("cmdstan", {}).values() if c.get("passed"))
        st = sorted({c.get("status") for a in ARMS for c in new.get(m, {}).get(a, {}).values()} - {"ok"})
        note = f" ({','.join(st)})" if st else ""
        lines.append(f"| {m} | {po}/3 / {pcm}/3{note} | {f(r_new.get(m), '.3f')} | {f(r_v7.get(m), '.3f')} | {f(r_pool.get(m), '.3f')} |")
    seeds_txt = ", ".join(f"{k}: {v['geomean']:.3f}" for k, v in per_seed.items())
    lines += ["", "| statistic | value | models |", "|---|---:|---:|",
              f"| geomean, new 3 seeds | **{f(g_new, '.3f')}** | {len(m_new)} |",
              f"| geomean, v7 3 seeds (recomputed) | {f(g_v7, '.3f')} | {len(m_v7)} |",
              f"| geomean, pooled 6 seeds | **{f(g_pool, '.3f')}** | {len(m_pool)} |",
              f"| leave-one-seed-out interval | **[{interval[0]:.3f}, {interval[1]:.3f}]** (width {interval[1] - interval[0]:.3f}) | — |",
              f"| single-seed geomeans | {seeds_txt} | — |",
              f"| log-scale SD of single-seed geomeans | {f(sd_log, '.3f')} | — |",
              f"| jackknife SE of the pooled 6-seed geomean | {f(jk_se, '.3f')} | — |",
              f"| **recommended seeds** for a +/-{hw} half-width (primary: k (2 SE_jk / {hw})^2) | **{n_rec}** | — |",
              f"| seeds for a +/-{tol} log half-width from single-seed SD (reported) | {n_rec_single} | — |", "",
              "| arm | passes new /48 | passes v7 /48 | passes pooled /96 |", "|---|---:|---:|---:|"]
    for arm in ARMS:
        lines.append(f"| {arm} | {pc[arm]['new'][0]}/{pc[arm]['new'][1]} | {pc[arm]['v7'][0]}/{pc[arm]['v7'][1]} | "
                     f"{pc[arm]['pooled'][0]}/{pc[arm]['pooled'][1]} |")
    lines += ["", "| prediction | value | held |", "|---|---|---|"]
    for k, v in preds.items():
        val = v["value"]
        lines.append(f"| {k} | {f(val, '.3f') if isinstance(val, float) else val} | {v.get('held', 'reported')} |")
    (ART / "results-table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] == "run":
        run_all()
    elif args[0] == "cell":
        run_model_arm(args[1], args[2])
    elif args[0] == "analyze":
        analyze()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
