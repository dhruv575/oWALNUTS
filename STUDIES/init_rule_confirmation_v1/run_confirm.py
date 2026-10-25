#!/usr/bin/env python3
"""WP52 init_rule_confirmation_v1 driver: Init::best_of(16) vs Init::uniform() as the default.

Copied from the WP43 driver (STUDIES/init_rule_v1/run_init.py). Changes: arms
`uniform` / `best_of_16`; run order two-mode target, start-only tally, funnel,
then the 17-model screen; `Summary::chain_warnings` recorded; the WP52
decision rule and predictions in `analyze`.

    python run_confirm.py run        # every evidence cell in protocol order
    python run_confirm.py analyze    # artifacts/summary.json + results-table.md

Each posteriordb cell is one fresh child process of the Rust harness
(target/release/init-rule-confirmation-v1.exe) and writes
`artifacts/cells/<model>-<arm>-<seed>.json` (metrics, no draws). Raw draws go
to the ignored `artifacts/draws/`. A cell whose JSON exists is never rerun;
failures are recorded as cells with status != "ok". The metrics and gates are
the posteriordb_bench_v6 ones (ArviZ 0.23.4 rank R-hat, bulk ESS, tail ESS at
0.05/0.95, mean MCSE against the posteriordb reference draws), reused verbatim.
"""
from __future__ import annotations

import json
import math
import os
import platform
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
FUNNEL_DIR = ART / "funnel"
MODELS = HERE / "models"
PDB_PATH = Path(PROTOCOL["posteriordb"]["path"])
HARNESS = HERE / "target" / "release" / "init-rule-confirmation-v1.exe"
FUNNEL = HERE / "target" / "release" / "funnel.exe"
TWO_MODE = HERE / "target" / "release" / "two_mode.exe"
TWO_MODE_DIR = ART / "two_mode"
ARMS = PROTOCOL["arms_order"]
REF = "uniform"
RULE = "best_of_16"
RULE_ARMS = [RULE]
SEEDS = PROTOCOL["seeds"]
TIMEOUT = PROTOCOL["cell_timeout_seconds"]
HIDDEN_SD = PROTOCOL["hidden_mode"]["reference_sd_threshold"]
CHAIN_MODE_SD = PROTOCOL["chain_mode"]["reference_sd_threshold"]
os.environ.setdefault("RUSTUP_TOOLCHAIN", "1.88.0-x86_64-pc-windows-gnu")


def short(model: str) -> str:
    return model.replace("-", "__")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------- posteriordb (v6 verbatim)


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


def rank_rhat_max(arr: np.ndarray) -> float:
    import arviz as az

    ds = az.convert_to_dataset({"p": arr})
    return float(np.nanmax(np.asarray(az.rhat(ds, method="rank").p.values, dtype=float)))


# --------------------------------------------------------------------------- metrics


def metrics(model: str, arm: str, seed: int, draws: np.ndarray, names: list[str], ref: dict,
            out: dict) -> dict:
    """draws: (chains, draws, P) on the reference parameter set (same order as ref)."""
    st = arviz_stats(draws)
    chains = out["chains_data"]
    divergences = sum(c["divergences"] for c in chains)
    grads_total = out["gradients_total"]
    grads_sampling = sum(c["retained_target_calls"] for c in chains)
    finite = bool(np.isfinite(draws).all())
    z = (st["mean"] - ref["mean"]) / np.sqrt(st["mcse"] ** 2 + ref["mcse"] ** 2)
    dsd = np.abs(st["mean"] - ref["mean"]) / ref["sd"]
    min_bulk = float(np.nanmin(st["bulk_ess"]))
    min_tail = float(np.nanmin(st["tail_ess"]))
    max_rhat = float(np.nanmax(st["rhat"]))
    gates = {
        "max_rank_rhat": max_rhat <= PROTOCOL["gates"]["max_rank_rhat"],
        "min_bulk_ess": min_bulk >= PROTOCOL["gates"]["min_bulk_ess"],
        "min_tail_ess": min_tail >= PROTOCOL["gates"]["min_tail_ess"],
        "sampling_divergences": divergences == 0,
        "finite_draws": finite,
        "no_sampler_error": True,
    }
    passed = all(gates.values())
    max_dsd = float(np.nanmax(dsd))
    hidden = bool(gates["max_rank_rhat"] and max_dsd > HIDDEN_SD)
    # Per-chain distance from the reference: max over reference parameters of
    # |chain mean - reference mean| / reference sd.
    chain_dist = [float(np.nanmax(np.abs(draws[i].mean(0) - ref["mean"]) / ref["sd"]))
                  for i in range(draws.shape[0])]
    # Leave-one-chain-out rank R-hat on the reference set (the ArviZ analogue
    # of ChainDisagreement, reported beside the Rust diagnostic).
    loo = [rank_rhat_max(np.delete(draws, i, axis=0)) for i in range(draws.shape[0])] if max_rhat > 1.01 else None
    per_param = {
        n: {
            "mean": float(st["mean"][i]), "sd": float(st["sd"][i]), "mcse": float(st["mcse"][i]),
            "bulk_ess": float(st["bulk_ess"][i]), "tail_ess": float(st["tail_ess"][i]),
            "rhat": float(st["rhat"][i]), "ref_mean": float(ref["mean"][i]), "ref_sd": float(ref["sd"][i]),
            "z": float(z[i]), "abs_dmean_over_ref_sd": float(dsd[i]),
        }
        for i, n in enumerate(names)
    }
    disagreement = out.get("chain_disagreement")
    return {
        "schema": "init-rule-confirmation-v1-cell-metrics",
        "model": model, "arm": arm, "seed": seed, "status": "ok",
        "dimension_reference_params": len(names),
        "unconstrained_dimension": out["dimension"],
        "wall_seconds": out["wall_seconds"],
        "gradients_total": grads_total,
        "gradients_sampling": grads_sampling,
        "init_evaluations": out["init_evaluations"],
        "init_fraction_of_gradients": out["init_evaluations"] / grads_total,
        "init": out["init"],
        "start_log_densities": out["start_log_densities"],
        "candidate_log_densities": out["candidate_log_densities"],
        "chosen_candidate": out["chosen_candidate"],
        "divergences": divergences,
        "max_depth_stops": sum(c["maximum_depth_stops"] for c in chains),
        "refinement_exhaustions_per_chain": [c["refinement_exhaustions"] for c in chains],
        "frozen_chains": sum(1 for c in chains if c["refinement_exhaustions"] > out["retained"] // 2),
        "final_step_size": [c["final_step_size"] for c in chains],
        "warmup_divergences": sum(c["warmup_divergences"] for c in chains),
        "chain_rescue_records": sum(c["chain_rescues"] for c in chains),
        "min_bulk_ess": min_bulk, "min_tail_ess": min_tail, "max_rank_rhat": max_rhat,
        "argmin_bulk_ess": names[int(np.nanargmin(st["bulk_ess"]))],
        "min_bulk_ess_per_gradient": min_bulk / grads_total,
        "min_tail_ess_per_gradient": min_tail / grads_total,
        "max_abs_z": float(np.nanmax(np.abs(z))),
        "argmax_abs_z": names[int(np.nanargmax(np.abs(z)))],
        "max_abs_dmean_over_ref_sd": max_dsd,
        "gates": gates,
        "passed": passed,
        "hidden_mode": hidden,
        "credited_pass": bool(passed and not hidden),
        "outcome_rank": outcome_rank(passed, hidden, gates),
        "chain_disagreement": disagreement,
        "chain_warnings": out.get("chain_warnings", []),
        "chain_warning_chains": out.get("chain_warning_chains", []),
        "chain_warnings_fired": bool(out.get("chain_warnings")),
        "disagreeing_chains": (disagreement or {}).get("chains", []),
        "max_unconstrained_rhat": out.get("max_unconstrained_rhat"),
        "chain_reference_distance": chain_dist,
        "chains_off_reference": [i for i, d in enumerate(chain_dist) if d > CHAIN_MODE_SD],
        "loo_rank_rhat_reference_set": loo,
        "parameters": per_param,
        "algorithm_revision": out["algorithm_revision"],
    }


def outcome_rank(passed: bool, hidden: bool, gates: dict) -> int:
    """3 = credited pass, 2 = visible non-R-hat failure, 1 = visible R-hat failure, 0 = hidden-mode or error."""
    if hidden or not gates.get("no_sampler_error", False):
        return 0
    if passed:
        return 3
    return 1 if not gates["max_rank_rhat"] else 2


def failure(model: str, arm: str, seed: int, status: str, message: str, **extra) -> dict:
    return {
        "schema": "init-rule-confirmation-v1-cell-metrics", "model": model, "arm": arm, "seed": seed,
        "status": status, "error": message, "passed": False, "hidden_mode": False,
        "credited_pass": False, "outcome_rank": 0,
        "gates": {"no_sampler_error": False}, **extra,
    }


def cell_path(model: str, arm: str, seed: int) -> Path:
    return CELLS / f"{short(model)}-{arm}-{seed}.json"


def write_cell(cell: dict) -> None:
    CELLS.mkdir(parents=True, exist_ok=True)
    path = cell_path(cell["model"], cell["arm"], cell["seed"])
    path.write_text(json.dumps(cell, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if cell["status"] == "ok":
        log(f"  {cell['arm']:>8} {cell['seed']}: grads {cell['gradients_total']} init {cell['init_evaluations']} "
            f"minbulk {cell['min_bulk_ess']:.0f} mintail {cell['min_tail_ess']:.0f} rhat {cell['max_rank_rhat']:.4f} "
            f"div {cell['divergences']} max|d|/sd {cell['max_abs_dmean_over_ref_sd']:.2f} "
            f"disagree {cell['disagreeing_chains']} off {cell['chains_off_reference']} warn {cell['chain_warning_chains']} "
            f"passed {cell['passed']} hidden {cell['hidden_mode']}")
    else:
        log(f"  {cell['arm']:>8} {cell['seed']}: {cell['status']}: {cell.get('error', '')[:200]}")


def run_cell(model: str, arm: str, seed: int, ref: dict, sm) -> dict:
    so = MODELS / f"{short(model)}_model.so"
    data = MODELS / f"{short(model)}.data.json"
    raw = DRAWS / f"{short(model)}-{arm}-{seed}.raw.json"
    DRAWS.mkdir(parents=True, exist_ok=True)
    if raw.exists():
        raw.unlink()
    cmd = [str(HARNESS), str(so), str(data), arm, str(seed), str(raw), str(PROTOCOL["threads"])]
    started = time.perf_counter()
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return failure(model, arm, seed, "timeout", f"exceeded {TIMEOUT}s")
    elapsed = time.perf_counter() - started
    stderr_tail = cp.stderr.strip()[-2000:]
    if not raw.exists():
        return failure(model, arm, seed, "error", f"exit {cp.returncode}: {stderr_tail}")
    out = json.loads(raw.read_text(encoding="utf-8"))
    if out.get("status") != "ok":
        return failure(model, arm, seed, "error", out.get("error", "unknown"),
                       stage=out.get("stage"), exit_code=cp.returncode,
                       start_log_densities=out.get("start_log_densities"),
                       init_evaluations=out.get("init_evaluations"))
    cnames = [bridgestan_name(n) for n in sm.param_names(include_tp=True, include_gq=False)]
    unc = np.asarray([c["samples"] for c in out["chains_data"]], dtype=np.float64)
    con = np.empty(unc.shape[:2] + (len(cnames),))
    for c in range(unc.shape[0]):
        for d in range(unc.shape[1]):
            con[c, d] = sm.param_constrain(unc[c, d], include_tp=True, include_gq=False)
    index = {n: i for i, n in enumerate(cnames)}
    missing = [n for n in ref["names"] if n not in index]
    if missing:
        return failure(model, arm, seed, "error", f"reference parameters not produced: {missing[:5]}")
    draws = con[:, :, [index[n] for n in ref["names"]]]
    cell = metrics(model, arm, seed, draws, ref["names"], ref, out)
    cell["process_exit_code"] = cp.returncode
    cell["process_seconds"] = elapsed
    cell["harness_stderr_tail"] = stderr_tail[-400:]
    np.savez_compressed(DRAWS / f"{short(model)}-{arm}-{seed}.npz", draws=draws,
                        names=np.asarray(ref["names"]), unconstrained=unc)
    raw.unlink()
    return cell


def run_model(model: str) -> None:
    """All seeds and arms of one model in this process (child of `run`)."""
    import bridgestan as bs

    ref = reference(model)
    bs.compile.windows_dll_path_setup()
    data = MODELS / f"{short(model)}.data.json"
    sm = bs.StanModel(str(MODELS / f"{short(model)}_model.so"), data=data.read_text(encoding="utf-8"), seed=1)
    for seed in SEEDS:
        for arm in ARMS:
            if cell_path(model, arm, seed).exists():
                continue
            try:
                cell = run_cell(model, arm, seed, ref, sm)
            except Exception as e:  # noqa: BLE001
                cell = failure(model, arm, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
            write_cell(cell)


def run_all() -> None:
    ART.mkdir(exist_ok=True)
    machine = ART / "measured_on.json"
    if not machine.exists():
        machine.write_text(json.dumps({
            "platform": platform.platform(), "processor": platform.processor(),
            "cpu_count": os.cpu_count(), "python": sys.version.split()[0],
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "note": "shared 16-core machine with up to six sibling agents running concurrently; walls are contended upper bounds and are not evidence",
        }, indent=2) + "\n", encoding="utf-8")
    run_two_mode()
    run_funnel()
    for model in PROTOCOL["models"]:
        log(f"== {model}")
        if all(cell_path(model, a, s).exists() for s in SEEDS for a in ARMS):
            continue
        if not (MODELS / f"{short(model)}_model.so").exists():
            for seed in SEEDS:
                for arm in ARMS:
                    if not cell_path(model, arm, seed).exists():
                        write_cell(failure(model, arm, seed, "compile_error", "bridgestan library missing"))
            continue
        cmd = [sys.executable, str(Path(__file__)), "model", model]
        try:
            cp = subprocess.run(cmd, timeout=TIMEOUT * len(SEEDS) * len(ARMS) + 600, text=True)
            if cp.returncode != 0:
                log(f"child for {model} exited {cp.returncode}")
        except subprocess.TimeoutExpired:
            log(f"child for {model} timed out")
        for seed in SEEDS:
            for arm in ARMS:
                if not cell_path(model, arm, seed).exists():
                    write_cell(failure(model, arm, seed, "timeout_or_crash", "child process ended without writing the cell"))


def run_two_mode() -> None:
    TWO_MODE_DIR.mkdir(parents=True, exist_ok=True)
    tm = PROTOCOL["two_mode"]
    for seed in tm["seeds"]:
        for arm in ARMS:
            out = TWO_MODE_DIR / f"two-mode-{arm}-{seed}.json"
            if out.exists():
                continue
            log(f"two-mode {arm} {seed}")
            cp = subprocess.run([str(TWO_MODE), "run", arm, str(seed), str(out)], capture_output=True, text=True,
                                timeout=TIMEOUT)
            log(f"  {cp.stderr.strip()[-300:]}")
            if not out.exists():
                (TWO_MODE_DIR / f"two-mode-{arm}-{seed}.error.txt").write_text(
                    f"exit {cp.returncode}\n{cp.stderr}", encoding="utf-8")
    so = tm["start_only"]
    for arm in ARMS:
        out = TWO_MODE_DIR / f"starts-{arm}.json"
        if out.exists():
            continue
        log(f"two-mode start-only tally {arm}")
        cp = subprocess.run([str(TWO_MODE), "starts", arm, str(so["first_seed"]), str(so["count"]), str(out)],
                            capture_output=True, text=True, timeout=TIMEOUT)
        log(f"  {cp.stderr.strip()[-300:]}")


def run_funnel() -> None:
    FUNNEL_DIR.mkdir(parents=True, exist_ok=True)
    for seed in PROTOCOL["funnel"]["seeds"]:
        for arm in ARMS:
            out = FUNNEL_DIR / f"funnel-{arm}-{seed}.json"
            if out.exists():
                continue
            log(f"funnel {arm} {seed}")
            cp = subprocess.run([str(FUNNEL), arm, str(seed), str(out)], capture_output=True, text=True)
            log(f"  {cp.stderr.strip()[-300:]}")
            if not out.exists():
                (FUNNEL_DIR / f"funnel-{arm}-{seed}.error.txt").write_text(
                    f"exit {cp.returncode}\n{cp.stderr}", encoding="utf-8")




# --------------------------------------------------------------------------- analysis


def geomean(xs: list[float]) -> float:
    xs = [x for x in xs if x is not None and math.isfinite(x) and x > 0]
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs))) if xs else float("nan")


def analyze_funnel() -> dict:
    out = {}
    for arm in ARMS:
        per = {}
        for seed in PROTOCOL["funnel"]["seeds"]:
            path = FUNNEL_DIR / f"funnel-{arm}-{seed}.json"
            if not path.exists():
                per[str(seed)] = None
                continue
            c = json.loads(path.read_text(encoding="utf-8"))
            t = c["tail_mass"]
            per[str(seed)] = {
                "estimate": t["estimate"], "mcse": t["mcse"], "z": t["z"], "z_batch_means": t["z_batch_means"],
                "omega_bulk_ess": c["omega"]["bulk_ess"], "omega_rhat": c["omega"]["rhat"],
                "divergences": sum(ch["divergences"] for ch in c["chains_data"]),
                "target_calls_total": c["target_calls_total"],
                "start_omegas": [s[0] for s in c["starts"]],
            }
        zs = [p["z"] for p in per.values() if p]
        out[arm] = {
            "per_seed": per,
            "complete": all(p is not None for p in per.values()),
            "all_abs_z_le_2": bool(len(zs) == len(per) and all(abs(z) <= PROTOCOL["funnel"]["abs_z_max"] for z in zs)),
            "max_abs_z": max((abs(z) for z in zs), default=None),
        }
    return out


def analyze_two_mode() -> dict:
    tm = PROTOCOL["two_mode"]
    thr = tm["rhat_threshold"]
    per = {}
    for seed in tm["seeds"]:
        row = {}
        for arm in ARMS:
            path = TWO_MODE_DIR / f"two-mode-{arm}-{seed}.json"
            if not path.exists():
                row[arm] = None
                continue
            c = json.loads(path.read_text(encoding="utf-8"))
            row[arm] = {
                "chains_starting_minor": c["chains_starting_minor"],
                "chains_ending_minor": c["chains_ending_minor"],
                "start_modes": [ch["start_mode"] for ch in c["chains_data"]],
                "end_modes": [ch["end_mode"] for ch in c["chains_data"]],
                "retained_fraction_major": [ch["retained_fraction_major"] for ch in c["chains_data"]],
                "retained_boundary_crossings": [ch["retained_boundary_crossings"] for ch in c["chains_data"]],
                "start_log_densities": c["start_log_densities"],
                "max_split_rhat": c["max_split_rhat"], "x1_split_rhat": c["x1_split_rhat"],
                "rhat_gt_threshold": c["max_split_rhat"] > thr,
                "chain_warnings_fired": c["chain_warnings_fired"], "chain_warnings": c["chain_warnings"],
                "chain_disagreement": c["chain_disagreement"],
                "pooled_fraction_major": c["pooled_fraction_major"],
                "divergences": sum(ch["divergences"] for ch in c["chains_data"]),
                "gradients_total": c["gradients_total"], "init_evaluations": c["init_evaluations"],
                "detected": bool(c["max_split_rhat"] > thr and c["chains_ending_minor"] >= 1),
                "single_mode_hidden": bool(c["max_split_rhat"] <= thr and c["chains_ending_minor"] in (0, c["chains"])),
            }
        u, b = row.get(REF), row.get(RULE)
        row["hide_event"] = bool(u and b and u["detected"] and b["max_split_rhat"] <= thr and b["chains_ending_minor"] == 0)
        per[str(seed)] = row
    starts = {}
    for arm in ARMS:
        path = TWO_MODE_DIR / f"starts-{arm}.json"
        if path.exists():
            c = json.loads(path.read_text(encoding="utf-8"))
            c.pop("per_seed_chains_starting_minor", None)
            starts[arm] = c
    complete = all(per[str(s)][a] is not None for s in tm["seeds"] for a in ARMS)
    return {"per_seed": per, "complete": complete,
            "hide_events": [s for s, r in per.items() if r["hide_event"]],
            "start_only": starts}


def analyze() -> None:
    models = PROTOCOL["models"]
    cells: dict = {}
    for m in models:
        for a in ARMS:
            for s in SEEDS:
                p = cell_path(m, a, s)
                if p.exists():
                    c = json.loads(p.read_text(encoding="utf-8"))
                    c.pop("parameters", None)
                    cells.setdefault(m, {}).setdefault(a, {})[s] = c
    n_expected = len(models) * len(SEEDS)
    arms = {}
    for a in ARMS:
        cs = [cells.get(m, {}).get(a, {}).get(s) for m in models for s in SEEDS]
        present = [c for c in cs if c]
        arms[a] = {
            "cells_present": len(present), "cells_expected": n_expected,
            "ok": sum(1 for c in present if c["status"] == "ok"),
            "raw_passes": sum(1 for c in present if c["passed"]),
            "credited_passes": sum(1 for c in present if c["credited_pass"]),
            "hidden_mode_cells": [f"{c['model']}/{c['seed']}" for c in present if c["hidden_mode"]],
            "rhat_failures": sum(1 for c in present if c["status"] == "ok" and not c["gates"]["max_rank_rhat"]),
            "errors": [f"{c['model']}/{c['seed']}: {c['status']}: {c.get('error', '')[:160]}" for c in present if c["status"] != "ok"],
            "failing_cells": [f"{c['model']}/{c['seed']}" for c in present if not c["credited_pass"]],
            "cells_with_disagreeing_chain": [f"{c['model']}/{c['seed']}:{c.get('disagreeing_chains')}" for c in present
                                             if c["status"] == "ok" and c.get("disagreeing_chains")],
            "cells_with_chain_warnings": [f"{c['model']}/{c['seed']}:{c.get('chain_warning_chains')}" for c in present
                                          if c["status"] == "ok" and c.get("chain_warnings_fired")],
            "cells_with_chain_off_reference": [f"{c['model']}/{c['seed']}:{c.get('chains_off_reference')}" for c in present
                                               if c["status"] == "ok" and c.get("chains_off_reference")],
            "frozen_chain_cells": [f"{c['model']}/{c['seed']}" for c in present if c.get("frozen_chains", 0) > 0],
            "init_evaluations_total": sum(c.get("init_evaluations") or 0 for c in present),
            "init_fraction_median": statistics.median([c["init_fraction_of_gradients"] for c in present if c["status"] == "ok"]) if present else None,
        }
    per_model = {}
    for m in models:
        row = {}
        for a in ARMS:
            cs = cells.get(m, {}).get(a, {})
            ok = {s: c for s, c in cs.items() if c["status"] == "ok"}
            row[a] = {
                "credited_passes": sum(1 for c in cs.values() if c["credited_pass"]),
                "raw_passes": sum(1 for c in cs.values() if c["passed"]),
                "hidden": [s for s, c in cs.items() if c["hidden_mode"]],
                "max_rank_rhat": {s: c["max_rank_rhat"] for s, c in ok.items()},
                "disagreeing_chains": {s: c["disagreeing_chains"] for s, c in ok.items()},
                "chain_warning_chains": {s: c.get("chain_warning_chains") for s, c in ok.items()},
                "chains_off_reference": {s: c["chains_off_reference"] for s, c in ok.items()},
                "start_log_density_median": statistics.median([x for c in ok.values() for x in c["start_log_densities"]]) if ok else None,
                "min_bulk_ess_per_gradient": {s: c["min_bulk_ess_per_gradient"] for s, c in ok.items()},
                "frozen_chains": {s: c["frozen_chains"] for s, c in ok.items()},
            }
        both = [s for s in SEEDS if s in row[REF]["min_bulk_ess_per_gradient"] and s in row[RULE]["min_bulk_ess_per_gradient"]]
        g_rule = geomean([row[RULE]["min_bulk_ess_per_gradient"][s] for s in both])
        g_ref = geomean([row[REF]["min_bulk_ess_per_gradient"][s] for s in both])
        row[RULE]["paired_seeds"] = both
        row[RULE]["ess_per_gradient_ratio_vs_uniform"] = g_rule / g_ref if both else None
        per_model[m] = row
    funnel = analyze_funnel()
    two = analyze_two_mode()
    ratios = [per_model[m][RULE]["ess_per_gradient_ratio_vs_uniform"] for m in models]
    g = geomean(ratios)
    lottery = PROTOCOL["lottery_models"]
    g_nonlottery = geomean([per_model[m][RULE]["ess_per_gradient_ratio_vs_uniform"] for m in models if m not in lottery])
    g_lottery = geomean([per_model[m][RULE]["ess_per_gradient_ratio_vs_uniform"] for m in lottery])
    dr = PROTOCOL["decision_rule"]
    cu, cb = arms[REF]["credited_passes"], arms[RULE]["credited_passes"]
    complete = (arms[REF]["cells_present"] == n_expected and arms[RULE]["cells_present"] == n_expected
                and funnel[RULE]["complete"] and two["complete"])
    f1 = bool(math.isfinite(g) and g >= dr["geomean_min"])
    f2 = cb >= cu - dr["gate_slack"]
    f3 = bool(funnel[RULE]["complete"] and funnel[RULE]["all_abs_z_le_2"])
    f4 = bool(two["complete"] and not two["hide_events"])
    decision = {
        "complete": complete,
        "F1_geomean_ge_1_10": f1, "geomean_ess_per_gradient_ratio": g,
        "geomean_nonlottery_14": g_nonlottery, "geomean_lottery_3": g_lottery,
        "F2_gates_ge_uniform_minus_1": f2, "credited_passes": {REF: cu, RULE: cb},
        "F3_funnel_best_of_16_abs_z_le_2_every_seed": f3, "funnel_max_abs_z": {a: funnel[a]["max_abs_z"] for a in ARMS},
        "F4_no_hide_event": f4, "hide_events": two["hide_events"],
        "flip": bool(complete and f1 and f2 and f3 and f4),
    }
    decision["recommendation"] = ("flip the default to Init::best_of(16)" if decision["flip"]
                                  else "keep Init::uniform() as the default; best_of(16) stays opt-in")
    ts = PROTOCOL["two_mode"]["seeds"]
    thr = PROTOCOL["two_mode"]["rhat_threshold"]
    P = {}
    P["P1"] = {"text": "best_of_16/uniform geomean >= 1.10", "value": g, "held": f1}
    P["P2"] = {"text": "best_of_16 credited passes >= uniform's", "value": {REF: cu, RULE: cb}, "held": cb >= cu}
    P["P3"] = {"text": "funnel |z| <= 2 every seed, both arms", "value": {a: funnel[a]["max_abs_z"] for a in ARMS},
               "held": all(funnel[a]["all_abs_z_le_2"] and funnel[a]["complete"] for a in ARMS)}
    u_det = [s for s in ts if (two["per_seed"][str(s)][REF] or {}).get("detected")]
    b_hid = []
    for s in ts:
        r = two["per_seed"][str(s)][RULE]
        if r and r["chains_ending_minor"] == 0 and r["max_split_rhat"] <= thr:
            b_hid.append(s)
    P["P4"] = {"text": "uniform: >= 1 minor-mode chain and R-hat > 1.01 on >= 2 of 3 seeds",
               "value": {"seeds": u_det, "count": len(u_det)}, "held": len(u_det) >= 2}
    P["P5"] = {"text": "best_of_16: all 4 chains in the major mode and R-hat <= 1.01 on >= 2 of 3 seeds",
               "value": {"seeds": b_hid, "count": len(b_hid)}, "held": len(b_hid) >= 2}
    summary = {
        "schema": "init-rule-confirmation-v1-summary", "arms": arms, "decision": decision,
        "funnel": funnel, "two_mode": two, "predictions": P, "per_model": per_model,
    }
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    write_table(summary, cells, models)


def write_table(summary: dict, cells: dict, models: list[str]) -> None:
    d = summary["decision"]
    L = ["# init_rule_confirmation_v1 results", "", "Generated by `run_confirm.py analyze`. Gradients include every init "
         "evaluation. Walls are contended and not reported.", "", "## Decision (frozen rule)", "",
         f"- F1 geomean ESS/grad best_of_16/uniform >= 1.10: **{d['F1_geomean_ge_1_10']}** ({d['geomean_ess_per_gradient_ratio']:.4f}; "
         f"lottery 3 {d['geomean_lottery_3']:.4f}, other 14 {d['geomean_nonlottery_14']:.4f})",
         f"- F2 credited passes >= uniform - 1: **{d['F2_gates_ge_uniform_minus_1']}** ({d['credited_passes']})",
         f"- F3 funnel best_of_16 |z| <= 2 every seed: **{d['F3_funnel_best_of_16_abs_z_le_2_every_seed']}** (max |z| {d['funnel_max_abs_z']})",
         f"- F4 no two-mode hide event: **{d['F4_no_hide_event']}** (hide events on seeds {d['hide_events']})",
         f"- complete: {d['complete']}; flip: **{d['flip']}**; {d['recommendation']}", "", "## Arms", "",
         "| arm | ok | raw passes | credited passes | hidden-mode | R-hat failures | cells with chain_warnings | init evals |",
         "|---|---|---|---|---|---|---|---|"]
    for a in ARMS:
        x = summary["arms"][a]
        L.append(f"| {a} | {x['ok']}/{x['cells_expected']} | {x['raw_passes']} | {x['credited_passes']} | "
                 f"{len(x['hidden_mode_cells'])} | {x['rhat_failures']} | {len(x['cells_with_chain_warnings'])} | {x['init_evaluations_total']} |")
    L += ["", "## Two-mode target (0.7 N(+4e1, I) + 0.3 N(-4e1, I), d = 10)", "",
          "| seed | arm | start modes | end modes | retained frac major | crossings | max split R-hat | x1 R-hat | chain_warnings | pooled major (exact 0.7) | div | hide event |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s, r in summary["two_mode"]["per_seed"].items():
        for a in ARMS:
            c = r[a]
            if c is None:
                L.append(f"| {s} | {a} | missing | | | | | | | | | |")
                continue
            sm = "".join("A" if m == "major" else "i" for m in c["start_modes"])
            em = "".join("A" if m == "major" else "i" for m in c["end_modes"])
            fr = ", ".join(f"{x:.3f}" for x in c["retained_fraction_major"])
            L.append(f"| {s} | {a} | {sm} | {em} | {fr} | {c['retained_boundary_crossings']} | "
                     f"{c['max_split_rhat']:.4f} | {c['x1_split_rhat']:.4f} | {c['chain_warnings_fired']} {c['chain_warnings'][:2]} | "
                     f"{c['pooled_fraction_major']:.3f} | {c['divergences']} | {r['hide_event']} |")
    L += ["", "(per chain: A = major mode, i = minor mode; start = side of the boundary x1 = b at the start, "
          "end = majority of retained draws)", "", "Start-only tally (1,000 seeds, no sampling):", ""]
    for a, c in summary["two_mode"]["start_only"].items():
        L.append(f"- {a}: chains starting minor {c['fraction_chains_starting_minor']:.3f}; histogram of minor starts per "
                 f"4-chain seed {c['histogram_chains_starting_minor']}; all-major {c['fraction_seeds_all_major']:.3f}, "
                 f"single-mode {c['fraction_seeds_single_mode']:.3f}")
    L += ["", "## Every posteriordb cell", "",
          "| model | seed | arm | status | R-hat | min bulk | min tail | div | max abs dmean/sd | disagreeing (Rust LOO) | chain_warnings chains | chains off ref | start logp (per chain) | init evals | bulk ESS/grad | pass | hidden |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in models:
        for s in SEEDS:
            for a in ARMS:
                c = cells.get(m, {}).get(a, {}).get(s)
                if not c:
                    L.append(f"| {m} | {s} | {a} | missing | | | | | | | | | | | | | |")
                    continue
                if c["status"] != "ok":
                    L.append(f"| {m} | {s} | {a} | {c['status']} | | | | | | | | | | {c.get('init_evaluations')} | | False | |")
                    continue
                sl = ", ".join(f"{x:.4g}" for x in c["start_log_densities"])
                L.append(f"| {m} | {s} | {a} | ok | {c['max_rank_rhat']:.4f} | {c['min_bulk_ess']:.0f} | {c['min_tail_ess']:.0f} | "
                         f"{c['divergences']} | {c['max_abs_dmean_over_ref_sd']:.2f} | {c['disagreeing_chains']} | {c.get('chain_warning_chains')} | "
                         f"{c['chains_off_reference']} | {sl} | {c['init_evaluations']} | {c['min_bulk_ess_per_gradient']:.3e} | {c['passed']} | {c['hidden_mode']} |")
    L += ["", "## Per-model ESS/gradient ratio best_of_16 / uniform (paired seeds, geomean)", "",
          "| model | ratio | credited uniform | credited best_of_16 |", "|---|---|---|---|"]
    for m in models:
        r = summary["per_model"][m]
        x = r[RULE]["ess_per_gradient_ratio_vs_uniform"]
        xs = f"{x:.3f}" if x else "-"
        L.append(f"| {m} | {xs} | {r[REF]['credited_passes']} | {r[RULE]['credited_passes']} |")
    L += ["", "## Funnel (P(omega < -5), exact 0.0478)", "",
          "| arm | seed | estimate | MCSE z | batch z | omega bulk ESS | omega R-hat | div | start omegas |", "|---|---|---|---|---|---|---|---|---|"]
    for a, f in summary["funnel"].items():
        for s, p in f["per_seed"].items():
            if p is None:
                L.append(f"| {a} | {s} | missing | | | | | | |")
                continue
            om = ", ".join(f"{w:.2f}" for w in p["start_omegas"])
            L.append(f"| {a} | {s} | {p['estimate']:.4f} | {p['z']:+.2f} | {p['z_batch_means']:+.2f} | {p['omega_bulk_ess']:.0f} | "
                     f"{p['omega_rhat']:.3f} | {p['divergences']} | {om} |")
    L += ["", "## Predictions", "", "| prediction | value | held |", "|---|---|---|"]
    for k, v in summary["predictions"].items():
        L.append(f"| {k}: {v['text']} | {v['value']} | {v['held']} |")
    (ART / "results-table.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:14]))


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] == "run":
        run_all()
    elif args[0] == "model":
        run_model(args[1])
    elif args[0] == "analyze":
        analyze()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
