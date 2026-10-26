#!/usr/bin/env python3
"""WP69 trapped-chain restart confirmation driver (`STUDIES/trapped_chain_restart_confirmation_v1`).

    python run_study.py manifest   # the frozen cell order (from protocol.json)
    python run_study.py smoke      # non-evidence smoke on seed 6909901
    python run_study.py run        # every evidence cell in manifest order (resumable; never reruns a written cell)
    python run_study.py analyze    # artifacts/summary.json + artifacts/results-table.md

Run on the Linux box, inside lane 4, as `taskset -c 12-15 ~/venv/bin/python run_study.py run`.

Copied from the WP67 driver (`STUDIES/trapped_chain_restart_v1/run_study.py`, itself WP57 + v7
code) and parametrised; every change is listed in PREREGISTRATION.md ("Harness changes").
Cell kinds: `lotka` (trap-cell, efficacy arm A), `pdb` (pdb-cell: breadth arm B and the
hmm_drive_0 part of arm C), `two_mode` (two-mode, arm C synthetic target), `sync` (sync-cost, arm D).
"""
from __future__ import annotations

import functools
import gzip
import json
import os
import platform
import statistics
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
ART = Path(os.environ["WP69_ART"]) if os.environ.get("WP69_ART") else HERE / "artifacts"
CELLS = ART / "cells"
TELEM = ART / "telemetry"
DRAWS = ART / "draws"
RAW = ART / "raw-tmp"
MODELS = HERE / "models"
PDB = Path(os.path.expanduser(PROTOCOL["posteriordb"]["path"]))
EXE = ".exe" if os.name == "nt" else ""
TRAP = HERE / "target" / "release" / f"trap-cell{EXE}"
PDBH = HERE / "target" / "release" / f"pdb-cell{EXE}"
TWO = HERE / "target" / "release" / f"two-mode{EXE}"
SYNC = HERE / "target" / "release" / f"sync-cost{EXE}"
LOTKA = PROTOCOL["lotka_model"]
HOUSE = PROTOCOL["house_models"]
HMM = "bball_drive_event_0-hmm_drive_0"
ARMS = ["defaults", "restart"]
T = PROTOCOL["timeouts"]
CAP = T["lotka_cooperative_seconds"]
BACKSTOP = T["lotka_process_backstop_seconds"]
PDB_TIMEOUT = T["pdb_process_seconds"]
OTHER_TIMEOUT = T["other_process_seconds"]
G = PROTOCOL["gates"]
# Stan's default schedule for 1,000 warmup transitions (verified against the observed stage field).
WINDOWS = [("init", 0, 75), ("S1", 75, 100), ("S2", 100, 150), ("S3", 150, 250), ("S4", 250, 450),
           ("S5", 450, 950), ("term", 950, 1000), ("sampling", 1000, 2000)]
CHECK_T = 99
STEP_RATIO = 0.1
SHIFT = 3.0


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def short(model: str) -> str:
    return model.replace("-", "__")


def manifest() -> list[dict]:
    cells = []
    for block in PROTOCOL["blocks"]:
        b, kind = block["name"], block["kind"]
        if kind == "sync":
            for chains in block["chains"]:
                for rep_ in range(block["repeats"]):
                    seed = block["seeds"][rep_]
                    cells.append({"block": b, "kind": kind, "model": "gaussian100", "arm": "paired", "seed": seed,
                                  "chains": chains, "repeat": rep_, "targeted": False,
                                  "id": f"{b}--sync--c{chains}--r{rep_}--{seed}"})
            continue
        models = block.get("models", [None])
        if isinstance(models, str):
            models = PROTOCOL[models]
        for model in models:
            for seed in block["seeds"]:
                for arm in ARMS:
                    name = {"lotka": "lotka", "two_mode": "two_mode"}.get(kind) or short(model)
                    cells.append({"block": b, "kind": kind, "model": model or kind, "arm": arm, "seed": seed,
                                  "targeted": seed in block.get("targeted_seeds", []),
                                  "id": f"{b}--{name}--{arm}--{seed}"})
    return cells


# --------------------------------------------------------------------------- posteriordb (read directly)


def _zip_json(path: Path):
    with zipfile.ZipFile(path) as z:
        inner = [n for n in z.namelist() if n.endswith(".json")][0]
        return json.loads(z.read(inner).decode("utf-8"))


def bridgestan_name(name: str) -> str:
    """'theta.1.2' -> 'theta[1,2]' (WP57/v7 code)."""
    parts = name.split(".")
    if len(parts) == 1 or not all(p.isdigit() for p in parts[1:]):
        return name
    return f"{parts[0]}[{','.join(parts[1:])}]"


def arviz_stats(arr: np.ndarray) -> dict:
    """v7 / WP57 estimators (ArviZ 0.23.4), verbatim."""
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
        "bulk_ess": bulk, "tail_ess": tail, "rhat": rhat, "mcse": mcse,
    }


@functools.lru_cache(maxsize=None)
def reference(model: str) -> dict:
    info = json.loads((PDB / "posteriors" / f"{model}.json").read_text(encoding="utf-8"))
    ref = _zip_json(PDB / "reference_posteriors" / "draws" / "draws" / f"{info['reference_posterior_name']}.json.zip")
    names = list(ref[0].keys())
    arr = np.asarray([[c[n] for n in names] for c in ref], dtype=np.float64)  # (chains, P, draws)
    arr = np.transpose(arr, (0, 2, 1))
    return {"names": names, **arviz_stats(arr)}


@functools.lru_cache(maxsize=None)
def stan_model(model: str):
    import bridgestan as bs

    so, data = MODELS / f"{short(model)}_model.so", MODELS / f"{short(model)}.data.json"
    if os.name == "nt":
        bs.compile.windows_dll_path_setup()
    return bs.StanModel(str(so), data=data.read_text(encoding="utf-8"), seed=1)


def constrain(model: str, unc: np.ndarray, names: list[str]) -> np.ndarray:
    sm = stan_model(model)
    cnames = [bridgestan_name(n) for n in sm.param_names(include_tp=True, include_gq=False)]
    index = {n: i for i, n in enumerate(cnames)}
    missing = [n for n in names if n not in index]
    if missing:
        raise RuntimeError(f"reference parameters not produced by param_constrain: {missing[:5]}")
    con = np.empty(unc.shape[:2] + (len(cnames),))
    for c in range(unc.shape[0]):
        for d in range(unc.shape[1]):
            con[c, d] = sm.param_constrain(unc[c, d], include_tp=True, include_gq=False)
    return con[:, :, [index[n] for n in names]]


def score(model: str, draws: np.ndarray, grads_total: int, divergences: int, z_gate: bool = False) -> dict:
    """Gates (protocol), z against the reference, per-chain shift and trapped chains."""
    ref = reference(model)
    st = arviz_stats(draws)
    z = (st["mean"] - ref["mean"]) / np.sqrt(st["mcse"] ** 2 + ref["mcse"] ** 2)
    min_bulk = float(np.nanmin(st["bulk_ess"]))
    min_tail = float(np.nanmin(st["tail_ess"]))
    max_rhat = float(np.nanmax(st["rhat"]))
    max_abs_z = float(np.nanmax(np.abs(z)))
    shifts = [float(np.nanmax(np.abs((draws[i].mean(0) - ref["mean"]) / ref["sd"]))) for i in range(draws.shape[0])]
    gates = {
        "completed": True,
        "max_rank_rhat": max_rhat <= G["max_rank_rhat"],
        "min_bulk_ess": min_bulk >= G["min_bulk_ess"],
        "min_tail_ess": min_tail >= G["min_tail_ess"],
        "sampling_divergences": divergences == 0,
        "finite_draws": bool(np.isfinite(draws).all()),
    }
    if z_gate:
        gates["max_abs_z"] = max_abs_z <= 4.0
    return {
        "min_bulk_ess": min_bulk, "min_tail_ess": min_tail, "max_rank_rhat": max_rhat,
        "argmin_bulk_ess": ref["names"][int(np.nanargmin(st["bulk_ess"]))],
        "argmax_rank_rhat": ref["names"][int(np.nanargmax(st["rhat"]))],
        "max_abs_z": max_abs_z, "argmax_abs_z": ref["names"][int(np.nanargmax(np.abs(z)))],
        "min_bulk_ess_per_gradient": min_bulk / grads_total,
        "min_tail_ess_per_gradient": min_tail / grads_total,
        "per_chain_shift_ref_sd": shifts,
        "trapped_chains": [i for i, s in enumerate(shifts) if s > SHIFT],
        "wrong_chain_cell": any(s > SHIFT for s in shifts),
        "divergences": divergences, "gradients_total": grads_total,
        "gates": gates, "passed": all(gates.values()),
        "parameters": {n: {"mean": float(st["mean"][i]), "bulk_ess": float(st["bulk_ess"][i]),
                           "tail_ess": float(st["tail_ess"][i]), "rhat": float(st["rhat"][i]), "z": float(z[i])}
                       for i, n in enumerate(ref["names"])},
    }


def emulated_flags(steps: list) -> dict:
    """The detector on a list of per-chain steps at transition 99 (None = chain did not reach it)."""
    if len(steps) < 3 or any(s is None for s in steps) or not all(np.isfinite(s) and s > 0 for s in steps):
        return {"scored": False, "steps": steps, "flagged": []}
    med = statistics.median(steps)
    return {"scored": True, "steps": steps, "median": med, "threshold": STEP_RATIO * med,
            "ratios": [s / med for s in steps], "flagged": [i for i, s in enumerate(steps) if s < STEP_RATIO * med]}


# --------------------------------------------------------------------------- lotka telemetry profile (WP57 code + epochs)


def window_of(t: int) -> str:
    for name, a, b in WINDOWS:
        if a <= t < b:
            return name
    return "?"


def profile(out: dict) -> dict:
    """Per chain per window over the chain's final epoch (the run that produced its draws), plus the
    abandoned epoch-0 run of a restarted chain. WP57 profile() otherwise unchanged."""
    fields = out["telemetry_fields"]
    ix = {f: i for i, f in enumerate(fields)}
    stops = out["stop_reasons"]
    cap_code = stops.index("MaximumDepth")
    pending, unattributed = {}, []
    for p in out.get("pending_unfinished_transition_work", []):
        (unattributed if p["chain"] is None else pending.setdefault(p["chain"], [])).append(p)
    chains, stage_mismatch = [], 0
    for c, all_rows in enumerate(out["telemetry"]):
        all_rows = np.asarray(all_rows, dtype=float).reshape(-1, len(fields))
        epochs = sorted({int(e) for e in all_rows[:, ix["epoch"]]}) if len(all_rows) else [0]
        last = epochs[-1]
        rows = all_rows[all_rows[:, ix["epoch"]] == last] if len(all_rows) else all_rows
        abandoned = None
        if last > 0:
            a = all_rows[all_rows[:, ix["epoch"]] == 0]
            abandoned = {"transitions": len(a), "gradients": float(a[:, ix["target_evaluations"]].sum()),
                         "step_at_99": float(a[a[:, ix["t"]] == CHECK_T][0, ix["step"]]) if (a[:, ix["t"]] == CHECK_T).any() else None,
                         "log_density_median_S1": float(np.median(a[(a[:, ix["t"]] >= 75), ix["log_density"]])) if (a[:, ix["t"]] >= 75).any() else None,
                         "t_end_seconds": float(a[-1, ix["t_end_ms"]] / 1e3) if len(a) else None}
        per = {}
        for name, a, b in WINDOWS:
            r = rows[(rows[:, ix["t"]] >= a) & (rows[:, ix["t"]] < b)] if len(rows) else rows
            n = len(r)
            if n == 0:
                per[name] = {"transitions": 0, "gradients": 0}
                continue
            grads = float(r[:, ix["target_evaluations"]].sum())
            calls = float(r[:, ix["eval_calls"]].sum())
            ev = float(r[:, ix["eval_us"]].sum())
            leaves = float(r[:, ix["leaves_built"]].sum())
            lv = r[:, ix["selected_level"]]
            per[name] = {
                "transitions": n, "complete": n == b - a, "gradients": grads, "observed_calls": calls,
                "step_median": float(np.median(r[:, ix["step"]])), "step_min": float(r[:, ix["step"]].min()),
                "step_end": float(r[-1, ix["step"]]), "depth_median": float(np.median(r[:, ix["depth"]])),
                "depth_cap_stops": int((r[:, ix["stop"]] == cap_code).sum()),
                "depth_cap_fraction": float((r[:, ix["stop"]] == cap_code).mean()),
                "stop_counts": {stops[int(k)] if k >= 0 else "?": int((r[:, ix["stop"]] == k).sum())
                                for k in np.unique(r[:, ix["stop"]])},
                "gradients_per_transition": grads / n,
                "refinement_attempts_per_leaf": float(r[:, ix["refinement_attempts"]].sum() / leaves) if leaves else None,
                "selected_level_mean": float(lv[lv >= 0].mean()) if (lv >= 0).any() else None,
                "divergent": int(r[:, ix["divergent"]].sum()), "zero_density": int(r[:, ix["zero_density"]].sum()),
                "log_density_median": float(np.median(r[:, ix["log_density"]])),
                "log_density_iqr": float(np.subtract(*np.percentile(r[:, ix["log_density"]], [75, 25]))),
                "wall_seconds": float(r[:, ix["wall_us"]].sum() / 1e6), "eval_seconds": ev / 1e6,
                "eval_us_per_gradient": ev / calls if calls else None,
                "t_end_seconds": float(r[-1, ix["t_end_ms"]] / 1e3),
            }
            expect = {"init": 0, "term": 2, "sampling": 3}.get(name, 1)
            stage_mismatch += int((r[:, ix["stage"]] != expect).sum())
        done = len(rows)
        pend = pending.get(c, [])
        grads = float(all_rows[:, ix["target_evaluations"]].sum()) if len(all_rows) else 0.0
        step99 = rows[rows[:, ix["t"]] == CHECK_T][0, ix["step"]] if done and (rows[:, ix["t"]] == CHECK_T).any() else None
        chains.append({
            "chain": c, "epochs": epochs, "transitions_done": done, "finished": done == 2000,
            "next_window": window_of(done) if done < 2000 else None,
            "gradients_recorded_all_epochs": grads, "pending_calls": sum(p["calls"] for p in pend),
            "gradients_total": grads + sum(p["calls"] for p in pend),
            "epoch0_step_at_99": (abandoned or {}).get("step_at_99") if last > 0 else (float(step99) if step99 is not None else None),
            "abandoned_epoch0": abandoned, "start_log_density": out["start_log_densities"][c], "windows": per,
        })
    if unattributed:
        empty = [ch for ch in chains if ch["transitions_done"] == 0]
        if len(empty) == 1:
            empty[0]["pending_calls"] += sum(p["calls"] for p in unattributed)
            empty[0]["gradients_total"] = empty[0]["gradients_recorded_all_epochs"] + empty[0]["pending_calls"]
            empty[0]["pending_attributed_by_elimination"] = True
    return {"chains": chains, "stage_mismatch_rows": stage_mismatch, "unattributed_pending": unattributed}


# --------------------------------------------------------------------------- cells


def base(cell: dict) -> dict:
    return {"schema": "trapped-chain-restart-v1-cell-metrics", "id": cell["id"], "block": cell["block"],
            "kind": cell["kind"], "model": cell["model"], "arm": cell["arm"], "seed": cell["seed"],
            "targeted": cell["targeted"]}


def failure(cell, status, message, **extra) -> dict:
    return {**base(cell), "status": status, "error": message, "completed": False, "passed": False,
            "gates": {"completed": False}, **extra}


def checks_of(chains_data: list) -> dict:
    checks = [c.get("trapped_chain_checks", []) for c in chains_data]
    return {"records": checks, "restarted": [i for i, cs in enumerate(checks) if any(x["restarted"] for x in cs)]}


def run_lotka(cell: dict) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    raw = RAW / f"{cell['id']}.json"
    if raw.exists():
        raw.unlink()
    so, data = MODELS / f"{short(LOTKA)}_model.so", MODELS / f"{short(LOTKA)}.data.json"
    cmd = [str(TRAP), str(so), str(data), cell["arm"], str(cell["seed"]), str(raw), str(CAP), "4"]
    t0 = time.perf_counter()
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=BACKSTOP)
    except subprocess.TimeoutExpired:
        return failure(cell, "backstop_timeout", f"process exceeded {BACKSTOP}s", process_seconds=time.perf_counter() - t0)
    process_seconds = time.perf_counter() - t0
    if cp.returncode != 0 or not raw.exists():
        return failure(cell, "harness_error", f"exit {cp.returncode}: {cp.stderr.strip()[-2000:]}")
    out = json.loads(raw.read_text(encoding="utf-8"))
    TELEM.mkdir(parents=True, exist_ok=True)
    with gzip.open(TELEM / f"{cell['id']}.json.gz", "wt", encoding="utf-8") as fh:
        json.dump({k: out[k] for k in ("telemetry_fields", "stop_reasons", "telemetry",
                                       "pending_unfinished_transition_work", "start_log_densities")}, fh)
    prof = profile(out)
    common = {
        "wall_seconds_pinned_cotenanted": out["wall_seconds"], "process_seconds": process_seconds,
        "start_log_densities": out["start_log_densities"], "starts_hash": out["starts_hash"],
        "start_search_calls": out["start_search_calls"], "sampling_calls": out["sampling_calls"],
        "target_calls_total": out["target_calls_total"], "adaptation": out["adaptation"],
        "algorithm_revision_const": out["algorithm_revision_const"], "profile": prof,
        "telemetry_epochs": [ch["epochs"] for ch in prof["chains"]],
        "detector_emulated_epoch0": emulated_flags([ch["epoch0_step_at_99"] for ch in prof["chains"]]),
    }
    if out["status"] != "ok":
        raw.unlink()
        status = "timeout" if out.get("error_kind") == "DeadlineExceeded" else "error"
        unfinished = [ch["chain"] for ch in prof["chains"] if not ch["finished"]]
        restarted = [ch["chain"] for ch in prof["chains"] if len(ch["epochs"]) > 1]
        return {**failure(cell, status, out.get("error"), error_kind=out.get("error_kind")), **common,
                "trapped_chains": unfinished, "restarted_chains": restarted}
    chains = out["chains_data"]
    unc = np.asarray([c["samples"] for c in chains], dtype=np.float64)
    ref = reference(LOTKA)
    draws = constrain(LOTKA, unc, ref["names"])
    sc = score(LOTKA, draws, out["target_calls_total"], sum(c["divergences"] for c in chains), z_gate=True)
    ck = checks_of(chains)
    res = {
        **base(cell), **common, **sc, "status": "ok", "completed": True,
        "draw_hash": out["draw_hash"], "per_chain_draw_hash": [c["draw_hash"] for c in chains],
        "per_chain_target_calls": [c["total_target_calls"] for c in chains],
        "per_chain_step_at_99": [c["step_at_transition_99"] for c in chains],
        "per_chain_effective_seed": [c["effective_seed"] for c in chains],
        "trapped_chain_checks": ck["records"], "restarted_chains": ck["restarted"],
        "detector_emulated_from_draw_run": emulated_flags([c["step_at_transition_99"] for c in chains]),
        "warmup_divergences": sum(c["warmup_divergences"] for c in chains),
        "max_depth_stops": sum(c["maximum_depth_stops"] for c in chains),
        "final_step_size": [c["final_step_size"] for c in chains],
        "chain_warnings": out["chain_warnings"], "chain_warning_chains": out["chain_warning_chains"],
        "algorithm_revision": out["algorithm_revision"],
    }
    DRAWS.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(DRAWS / f"{cell['id']}.npz", unconstrained=unc, draws=draws, names=np.asarray(ref["names"]))
    raw.unlink()
    return res


def run_pdb(cell: dict) -> dict:
    model = cell["model"]
    so, data = MODELS / f"{short(model)}_model.so", MODELS / f"{short(model)}.data.json"
    RAW.mkdir(parents=True, exist_ok=True)
    raw = RAW / f"{cell['id']}.json"
    if raw.exists():
        raw.unlink()
    cmd = [str(PDBH), str(so), str(data), cell["arm"], str(cell["seed"]), str(raw), "4"]
    t0 = time.perf_counter()
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=PDB_TIMEOUT)
    except subprocess.TimeoutExpired:
        return failure(cell, "timeout", f"exceeded {PDB_TIMEOUT}s", process_seconds=time.perf_counter() - t0)
    if not raw.exists():
        return failure(cell, "harness_error", f"exit {cp.returncode}: {cp.stderr.strip()[-2000:]}")
    out = json.loads(raw.read_text(encoding="utf-8"))
    if out.get("status") != "ok":
        raw.unlink()
        return failure(cell, "error", out.get("error", "unknown"), wall_seconds=out.get("wall_seconds"),
                       target_calls=out.get("target_calls"))
    chains = out["chains_data"]
    unc = np.asarray([c["samples"] for c in chains], dtype=np.float64)
    ref = reference(model)
    draws = constrain(model, unc, ref["names"])
    sc = score(model, draws, out["target_calls_total"], sum(c["divergences"] for c in chains))
    ck = checks_of(chains)
    res = {
        **base(cell), **sc, "status": "ok", "completed": True,
        "wall_seconds_pinned_cotenanted": out["wall_seconds"], "process_seconds": time.perf_counter() - t0,
        "target_calls_total": out["target_calls_total"], "start_search_calls": out["init"]["start_search_calls"],
        "draw_hash": out["draw_hash"], "per_chain_draw_hash": [c["draw_hash"] for c in chains],
        "per_chain_target_calls": [c["total_target_calls"] for c in chains],
        "per_chain_step_at_99": [c["step_at_transition_99"] for c in chains],
        "per_chain_effective_seed": [c["effective_seed"] for c in chains],
        "trapped_chain_checks": ck["records"], "restarted_chains": ck["restarted"],
        "detector_emulated_from_draw_run": emulated_flags([c["step_at_transition_99"] for c in chains]),
        "warmup_divergences": sum(c["warmup_divergences"] for c in chains),
        "max_depth_stops": sum(c["maximum_depth_stops"] for c in chains),
        "refinement_exhaustions_per_chain": [c["refinement_exhaustions"] for c in chains],
        "final_step_size": [c["final_step_size"] for c in chains],
        "chain_warnings": out.get("chain_warnings", []),
        "defaults_debug": out["defaults"], "warmup_config_used": out.get("warmup_config_used"),
        "execution": out.get("execution"), "replicas": out.get("replicas"),
        "algorithm_revision": out["algorithm_revision"], "unconstrained_dimension": out["dimension"],
    }
    DRAWS.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(DRAWS / f"{cell['id']}.npz", unconstrained=unc, draws=draws, names=np.asarray(ref["names"]))
    raw.unlink()
    return res


def run_two_mode(cell: dict) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    raw = RAW / f"{cell['id']}.json"
    if raw.exists():
        raw.unlink()
    t0 = time.perf_counter()
    try:
        cp = subprocess.run([str(TWO), "run", cell["arm"], str(cell["seed"]), str(raw)],
                            capture_output=True, text=True, timeout=OTHER_TIMEOUT)
    except subprocess.TimeoutExpired:
        return failure(cell, "timeout", f"exceeded {OTHER_TIMEOUT}s")
    if cp.returncode != 0 or not raw.exists():
        return failure(cell, "harness_error", f"exit {cp.returncode}: {cp.stderr.strip()[-2000:]}")
    out = json.loads(raw.read_text(encoding="utf-8"))
    raw.unlink()
    chains = out.pop("chains_data")
    ck = checks_of(chains)
    steps = [c["step_at_transition_99"] for c in chains]
    return {**base(cell), "status": "ok", "completed": True, "process_seconds": time.perf_counter() - t0,
            **{k: out[k] for k in ("draw_hash", "max_split_rhat", "x1_split_rhat", "min_bulk_ess", "x1_bulk_ess",
                                   "chain_disagreement", "chain_warnings", "chain_warning_chains",
                                   "chain_warnings_fired", "pooled_fraction_major", "chains_starting_minor",
                                   "chains_ending_minor", "gradients_total", "wall_seconds", "starts",
                                   "start_log_densities", "algorithm_revision")},
            "target_calls_total": out["gradients_total"],
            "per_chain_draw_hash": [c["draw_hash"] for c in chains],
            "per_chain_target_calls": [c["total_target_calls"] for c in chains],
            "per_chain_step_at_99": steps,
            "per_chain": [{k: c[k] for k in ("start_mode", "end_mode", "retained_fraction_major",
                                             "retained_boundary_crossings", "x1_mean", "divergences",
                                             "final_step_size")} for c in chains],
            "trapped_chain_checks": ck["records"], "restarted_chains": ck["restarted"],
            "detector_emulated_from_draw_run": emulated_flags(steps),
            "mixed_end_modes": 0 < out["chains_ending_minor"] < 4}


def run_sync(cell: dict) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    raw = RAW / f"{cell['id']}.json"
    if raw.exists():
        raw.unlink()
    try:
        cp = subprocess.run([str(SYNC), str(cell["chains"]), str(cell["repeat"]), str(cell["seed"]), str(raw)],
                            capture_output=True, text=True, timeout=OTHER_TIMEOUT)
    except subprocess.TimeoutExpired:
        return failure(cell, "timeout", f"exceeded {OTHER_TIMEOUT}s")
    if cp.returncode != 0 or not raw.exists():
        return failure(cell, "harness_error", f"exit {cp.returncode}: {cp.stderr.strip()[-2000:]}")
    out = json.loads(raw.read_text(encoding="utf-8"))
    raw.unlink()
    return {**base(cell), "status": "ok", "completed": True, "chains": cell["chains"], "repeat": cell["repeat"],
            **{k: out[k] for k in ("threads", "order", "pairs_per_repeat", "warmup_run", "runs",
                                   "defaults_walls_sorted", "restart_walls_sorted",
                                   "wall_ratio_restart_over_defaults", "identical")},
            "restarted_any": any(r["restarted"] for r in out["runs"]),
            "checks_per_run": sorted({r["checks"] for r in out["runs"] if r["arm"] == "restart"})}


def summarize_line(c: dict) -> str:
    if c["kind"] == "sync":
        if c["status"] != "ok":
            return f"{c['id']}: {c['status']} {str(c.get('error', ''))[:160]}"
        return f"{c['id']}: ok ratio {c['wall_ratio_restart_over_defaults']:.4f} identical {c['identical']} restarted {c['restarted_any']}"
    if c["kind"] == "two_mode":
        if c["status"] != "ok":
            return f"{c['id']}: {c['status']} {str(c.get('error', ''))[:160]}"
        return (f"{c['id']}: ok rhat {c['max_split_rhat']:.3f} start_minor {c['chains_starting_minor']} end_minor "
                f"{c['chains_ending_minor']} warnings {c['chain_warning_chains']} restarted {c['restarted_chains']} hash {c['draw_hash']}")
    if c["status"] != "ok":
        return f"{c['id']}: {c['status']} trapped {c.get('trapped_chains')} restarted {c.get('restarted_chains')} {str(c.get('error', ''))[:160]}"
    return (f"{c['id']}: ok wall {c['wall_seconds_pinned_cotenanted']:.1f}s grads {c['target_calls_total']} "
            f"minbulk {c['min_bulk_ess']:.0f} mintail {c['min_tail_ess']:.0f} rhat {c['max_rank_rhat']:.4f} "
            f"div {c['divergences']} max|z| {c['max_abs_z']:.2f} passed {c['passed']} trapped {c['trapped_chains']} "
            f"restarted {c['restarted_chains']} hash {c['draw_hash']}")


def run_cell(cell: dict, out_path: Path) -> None:
    try:
        c = {"lotka": run_lotka, "pdb": run_pdb, "two_mode": run_two_mode, "sync": run_sync}[cell["kind"]](cell)
    except Exception as e:  # noqa: BLE001
        c = failure(cell, "harness_error", f"{e}\n{traceback.format_exc()[-1500:]}")
    c["ordinal"] = cell.get("ordinal")
    c["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(c, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    log(summarize_line(c))


def measured_on() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    m = ART / "measured_on.json"
    if m.exists():
        return
    try:
        affinity = sorted(os.sched_getaffinity(0))
    except AttributeError:
        affinity = None
    m.write_text(json.dumps({
        "platform": platform.platform(), "processor": platform.processor(), "cpu_count": os.cpu_count(),
        "affinity": affinity, "python": sys.version.split()[0],
        "env": {k: os.environ.get(k) for k in ("RAYON_NUM_THREADS", "OMP_NUM_THREADS", "TMPDIR")},
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "lane 4 of a shared 16-core box, core-pinned to 12-15, three other lanes active: walls are pinned, co-tenanted",
    }, indent=2) + "\n", encoding="utf-8")


def run_all() -> None:
    measured_on()
    cells = manifest()
    for i, cell in enumerate(cells):
        cell["ordinal"] = i
        path = CELLS / f"{cell['id']}.json"
        if path.exists():
            continue
        log(f"[{i + 1}/{len(cells)}] {cell['id']}")
        run_cell(cell, path)
    log("all cells done")


def smoke() -> None:
    """Non-evidence identity smoke (seed 6709901): lotka defaults / restart / custom_noop / --plain,
    and eight_schools_centered defaults / restart through pdb-cell."""
    out_dir = ART / "smoke"
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = PROTOCOL["smoke_seed"]
    so, data = MODELS / f"{short(LOTKA)}_model.so", MODELS / f"{short(LOTKA)}.data.json"
    res = {"seed": seed, "lotka": {}, "eight_schools_centered": {}}
    for arm, extra in [("defaults", []), ("restart", []), ("custom_noop", []), ("defaults", ["--plain"])]:
        key = arm + ("-plain" if extra else "")
        raw = out_dir / f"lotka-{key}.json"
        if raw.exists():
            raw.unlink()
        cp = subprocess.run([str(TRAP), str(so), str(data), arm, str(seed), str(raw), str(CAP), "4", *extra],
                            capture_output=True, text=True, timeout=BACKSTOP)
        o = json.loads(raw.read_text(encoding="utf-8")) if raw.exists() else {}
        res["lotka"][key] = {"rc": cp.returncode, "status": o.get("status"), "draw_hash": o.get("draw_hash"),
                             "target_calls_total": o.get("target_calls_total"),
                             "restarted": checks_of(o["chains_data"])["restarted"] if o.get("chains_data") else None,
                             "steps_at_99": [c["step_at_transition_99"] for c in o.get("chains_data", [])],
                             "stderr": cp.stderr[-400:]}
        raw.unlink(missing_ok=True)
    for arm in ARMS:
        raw = out_dir / f"two-mode-{arm}.json"
        raw.unlink(missing_ok=True)
        cp = subprocess.run([str(TWO), "run", arm, str(seed), str(raw)], capture_output=True, text=True,
                            timeout=OTHER_TIMEOUT)
        o = json.loads(raw.read_text(encoding="utf-8")) if raw.exists() else {}
        res.setdefault("two_mode", {})[arm] = {"rc": cp.returncode, "draw_hash": o.get("draw_hash"),
                                               "gradients_total": o.get("gradients_total"),
                                               "restarted": checks_of(o["chains_data"])["restarted"] if o.get("chains_data") else None,
                                               "max_split_rhat": o.get("max_split_rhat"),
                                               "chain_warnings": o.get("chain_warnings"), "stderr": cp.stderr[-300:]}
        raw.unlink(missing_ok=True)
    raw = out_dir / "sync-c4.json"
    raw.unlink(missing_ok=True)
    cp = subprocess.run([str(SYNC), "4", "0", str(seed), str(raw)], capture_output=True, text=True, timeout=OTHER_TIMEOUT)
    o = json.loads(raw.read_text(encoding="utf-8")) if raw.exists() else {}
    res["sync_c4"] = {"rc": cp.returncode, "ratio": o.get("wall_ratio_restart_over_defaults"),
                      "identical": o.get("identical"), "defaults_walls": o.get("defaults_walls_sorted"),
                      "restart_walls": o.get("restart_walls_sorted"), "stderr": cp.stderr[-300:]}
    raw.unlink(missing_ok=True)
    m = "eight_schools-eight_schools_centered"
    so, data = MODELS / f"{short(m)}_model.so", MODELS / f"{short(m)}.data.json"
    for arm in ARMS:
        raw = out_dir / f"es-{arm}.json"
        if raw.exists():
            raw.unlink()
        cp = subprocess.run([str(PDBH), str(so), str(data), arm, str(seed), str(raw), "4"],
                            capture_output=True, text=True, timeout=PDB_TIMEOUT)
        o = json.loads(raw.read_text(encoding="utf-8")) if raw.exists() else {}
        res["eight_schools_centered"][arm] = {"rc": cp.returncode, "status": o.get("status"),
                                              "draw_hash": o.get("draw_hash"),
                                              "target_calls_total": o.get("target_calls_total"),
                                              "restarted": checks_of(o["chains_data"])["restarted"] if o.get("chains_data") else None,
                                              "stderr": cp.stderr[-400:]}
        raw.unlink(missing_ok=True)
    (out_dir / "smoke-summary.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(res, indent=1))


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "manifest":
        for i, c in enumerate(manifest()):
            print(i, c["id"])
    elif cmd == "smoke":
        smoke()
    elif cmd == "run":
        run_all()
    elif cmd == "analyze":
        import analyze

        analyze.main()
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
