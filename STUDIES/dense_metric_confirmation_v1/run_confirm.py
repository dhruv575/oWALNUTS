#!/usr/bin/env python3
"""WP51 dense-default confirmation driver (the WP48 harness `dense_metric_posteriordb_v1/run_dense.py`, trimmed).

    python run_confirm.py run      # phase 1 (diag, dense-candidate) then the funnel, then phase 2 (dense-legacy)
    python run_confirm.py cell <model> <arm>   # one model/arm, all seeds (child process)
    python run_confirm.py funnel   # funnel side check (diag, dense-candidate)
    python run_confirm.py analyze  # artifacts/summary.json + artifacts/results-table.md + decision

Each cell writes `artifacts/cells/<model>-<arm>-<seed>.json` (metrics, no draws) and
`artifacts/draws/<model>-<arm>-<seed>.npz` (constrained reference-parameter draws and
unconstrained draws; uncommitted). Failures (error, timeout) are cells with status != "ok".
"""
from __future__ import annotations

import hashlib
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
HARNESS = HERE / "target" / "release" / "dense-cell.exe"
FUNNEL = HERE / "target" / "release" / "funnel.exe"
ARMS = list(PROTOCOL["arms"].keys())  # owalnuts-diag, owalnuts-dense-legacy, owalnuts-dense-candidate
MODE = {"owalnuts-diag": "diag", "owalnuts-dense-legacy": "dense-legacy", "owalnuts-dense-candidate": "dense-candidate"}
SEEDS = PROTOCOL["seeds"]
TIMEOUT = PROTOCOL["cell_timeout_seconds"]
DIAG, LEGACY, CAND = "owalnuts-diag", "owalnuts-dense-legacy", "owalnuts-dense-candidate"
os.environ.setdefault("RUSTUP_TOOLCHAIN", "1.88.0-x86_64-pc-windows-gnu")


def short(model: str) -> str:
    return model.replace("-", "__")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------- posteriordb


def posterior(model: str):
    from posteriordb import PosteriorDatabase

    return PosteriorDatabase(str(PDB_PATH)).posterior(model)


def bridgestan_name(name: str) -> str:
    parts = name.split(".")
    if len(parts) == 1 or not all(p.isdigit() for p in parts[1:]):
        return name
    return f"{parts[0]}[{','.join(parts[1:])}]"


def reference(model: str) -> dict:
    p = posterior(model)
    ref = p.reference_draws()
    names = list(ref[0].keys())
    arr = np.asarray([[c[n] for n in names] for c in ref], dtype=np.float64)
    arr = np.transpose(arr, (0, 2, 1))
    return {"names": names, "draws": arr, **arviz_stats(arr)}


def arviz_stats(arr: np.ndarray) -> dict:
    import arviz as az

    ds = az.convert_to_dataset({"p": arr})
    return {
        "mean": arr.reshape(-1, arr.shape[-1]).mean(0),
        "sd": arr.reshape(-1, arr.shape[-1]).std(0, ddof=1),
        "bulk_ess": np.asarray(az.ess(ds, method="bulk").p.values, dtype=float),
        "tail_ess": np.asarray(az.ess(ds, method="tail", prob=(0.05, 0.95)).p.values, dtype=float),
        "rhat": np.asarray(az.rhat(ds, method="rank").p.values, dtype=float),
        "mcse": np.asarray(az.mcse(ds, method="mean").p.values, dtype=float),
    }


def model_files(model: str) -> tuple[Path, Path]:
    so = MODELS / f"{short(model)}_model.so"
    data = MODELS / f"{short(model)}.data.json"
    if not so.exists() or not data.exists():
        raise FileNotFoundError(f"missing copied library or data for {model}")
    return so, data


def stan_model(model: str):
    import bridgestan as bs

    so, data = model_files(model)
    bs.compile.windows_dll_path_setup()
    return bs.StanModel(str(so), data=data.read_text(encoding="utf-8"), seed=1)


# --------------------------------------------------------------------------- metric geometry


def preconditioned_condition(sigma: np.ndarray, mass: np.ndarray) -> float:
    """Condition number of the posterior covariance in the installed metric's whitened coordinates."""
    if mass.ndim == 1:
        s = np.sqrt(mass)
        a = sigma * s[:, None] * s[None, :]
    else:
        lower = np.linalg.cholesky(0.5 * (mass + mass.T))
        a = lower.T @ sigma @ lower
    ev = np.linalg.eigvalsh(0.5 * (a + a.T))
    return float(ev[-1] / max(ev[0], 1e-300))


# --------------------------------------------------------------------------- cells


def metrics(model, arm, seed, draws, names, ref, wall, grads_total, grads_sampling, divergences,
            max_depth_stops, extra) -> dict:
    st = arviz_stats(draws)
    finite = bool(np.isfinite(draws).all())
    z = (st["mean"] - ref["mean"]) / np.sqrt(st["mcse"] ** 2 + ref["mcse"] ** 2)
    min_bulk = float(np.nanmin(st["bulk_ess"]))
    min_tail = float(np.nanmin(st["tail_ess"]))
    max_rhat = float(np.nanmax(st["rhat"]))
    g = PROTOCOL["gates"]
    gates = {
        "max_rank_rhat": max_rhat <= g["max_rank_rhat"],
        "min_bulk_ess": min_bulk >= g["min_bulk_ess"],
        "min_tail_ess": min_tail >= g["min_tail_ess"],
        "sampling_divergences": divergences == 0,
        "finite_draws": finite,
        "no_sampler_error": True,
    }
    n_draws = draws.shape[0] * draws.shape[1]
    return {
        "schema": "dense-metric-confirmation-v1-cell-metrics",
        "model": model, "arm": arm, "seed": seed, "status": "ok",
        "dimension_reference_params": len(names),
        "wall_seconds_contended": wall,
        "gradients_total": grads_total,
        "gradients_sampling": grads_sampling,
        "divergences": divergences,
        "max_depth_stops": max_depth_stops,
        "depth_cap_fraction": max_depth_stops / n_draws,
        "min_bulk_ess": min_bulk, "min_tail_ess": min_tail, "max_rank_rhat": max_rhat,
        "argmin_bulk_ess": names[int(np.nanargmin(st["bulk_ess"]))],
        "min_bulk_ess_per_gradient": min_bulk / grads_total,
        "min_tail_ess_per_gradient": min_tail / grads_total,
        "max_abs_z": float(np.nanmax(np.abs(z))),
        "argmax_abs_z": names[int(np.nanargmax(np.abs(z)))],
        "gates": gates,
        "passed": all(gates.values()),
        "parameters": {
            n: {"mean": float(st["mean"][i]), "bulk_ess": float(st["bulk_ess"][i]),
                "tail_ess": float(st["tail_ess"][i]), "rhat": float(st["rhat"][i]), "z": float(z[i])}
            for i, n in enumerate(names)
        },
        **extra,
    }


def failure(model, arm, seed, status, message, **extra) -> dict:
    return {"schema": "dense-metric-confirmation-v1-cell-metrics", "model": model, "arm": arm, "seed": seed,
            "status": status, "error": message, "passed": False, "gates": {"no_sampler_error": False}, **extra}


def cell_path(model, arm, seed) -> Path:
    return CELLS / f"{short(model)}-{arm}-{seed}.json"


def write_cell(cell: dict) -> None:
    CELLS.mkdir(parents=True, exist_ok=True)
    cell_path(cell["model"], cell["arm"], cell["seed"]).write_text(
        json.dumps(cell, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if cell["status"] == "ok":
        log(f"  {cell['arm']} {cell['seed']}: wall {cell['wall_seconds_contended']:.2f}s grads {cell['gradients_total']} "
            f"minbulk {cell['min_bulk_ess']:.0f} mintail {cell['min_tail_ess']:.0f} rhat {cell['max_rank_rhat']:.4f} "
            f"div {cell['divergences']} caps {cell['max_depth_stops']} max|z| {cell['max_abs_z']:.2f} passed {cell['passed']}")
    else:
        log(f"  {cell['arm']} {cell['seed']}: {cell['status']}: {cell.get('error', '')[:300]}")


def run_owalnuts(model: str, arm: str, seed: int, ref: dict) -> dict:
    so, data = model_files(model)
    raw = DRAWS / f"{short(model)}-{arm}-{seed}.raw.json"
    DRAWS.mkdir(parents=True, exist_ok=True)
    if raw.exists():
        raw.unlink()
    cmd = [str(HARNESS), str(so), str(data), MODE[arm], str(seed), str(raw), "4"]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        if raw.exists():
            raw.unlink()
        return failure(model, arm, seed, "timeout", f"exceeded {TIMEOUT}s")
    if cp.returncode != 0 or not raw.exists():
        return failure(model, arm, seed, "error", cp.stderr.strip()[-2000:])
    out = json.loads(raw.read_text(encoding="utf-8"))
    if out.get("status") != "ok":
        return failure(model, arm, seed, "error", out.get("error", "unknown"), wall_seconds_contended=out.get("wall_seconds"))
    sm = stan_model(model)
    cnames = [bridgestan_name(n) for n in sm.param_names(include_tp=True, include_gq=False)]
    unc = np.asarray([c["samples"] for c in out["chains_data"]], dtype=np.float64)  # (chains, draws, d)
    con = np.empty(unc.shape[:2] + (len(cnames),))
    for c in range(unc.shape[0]):
        for d in range(unc.shape[1]):
            con[c, d] = sm.param_constrain(unc[c, d], include_tp=True, include_gq=False)
    index = {n: i for i, n in enumerate(cnames)}
    missing = [n for n in ref["names"] if n not in index]
    if missing:
        return failure(model, arm, seed, "error", f"reference parameters not produced: {missing[:5]}")
    draws = con[:, :, [index[n] for n in ref["names"]]]
    chains = out["chains_data"]
    dim = out["dimension"]
    pooled = unc.reshape(-1, dim)
    sigma = np.cov(pooled, rowvar=False).reshape(dim, dim)
    installed = []
    for c in chains:
        if MODE[arm] == "diag":
            installed.append(np.asarray(c["mass_diagonal"], dtype=float))
        elif c.get("final_mass_dense") is not None:
            installed.append(np.asarray(c["final_mass_dense"], dtype=float).reshape(dim, dim))
        else:
            installed.append(np.eye(dim))
    kappa_pre = []
    for m in installed:
        try:
            kappa_pre.append(preconditioned_condition(sigma, m))
        except np.linalg.LinAlgError:
            kappa_pre.append(float("nan"))
    last_ridges = [(c["metric_updates"][-1]["ridge"] if c["metric_updates"] else None) for c in chains]
    extra = {
        "unconstrained_dimension": dim,
        "final_step_size": [c["final_step_size"] for c in chains],
        "per_chain_target_calls": [c["total_target_calls"] for c in chains],
        "per_chain_depth_caps": [c["maximum_depth_stops"] for c in chains],
        "invalid_stops": sum(c["invalid_stops"] for c in chains),
        "refinement_exhaustions": sum(c["refinement_exhaustions"] for c in chains),
        "warmup_divergences": sum(c["warmup_divergences"] for c in chains),
        "retained_depth_histogram": [sum(x) for x in zip(*(c["retained_depth_histogram"] for c in chains))],
        "start_search_calls": out["init"]["start_search_calls"],
        "warmup_config": out["warmup_config"],
        "tuning": out["tuning"],
        "algorithm_revision": out["algorithm_revision"],
        "metric_updates": [c["metric_updates"] for c in chains],
        "dense_installed_windows": [sum(1 for u in c["metric_updates"] if u["outcome"] == "Installed") for c in chains],
        "last_window_ridge_per_chain": last_ridges,
        "cholesky_failures_total": sum(u.get("cholesky_failures") or 0 for c in chains for u in c["metric_updates"]),
        "preconditioned_condition_per_chain": kappa_pre,
        "preconditioned_condition_median": float(np.nanmedian(kappa_pre)) if any(math.isfinite(k) for k in kappa_pre) else None,
    }
    cell = metrics(model, arm, seed, draws, ref["names"], ref, out["wall_seconds"], out["target_calls_total"],
                   sum(c["retained_target_calls"] for c in chains), sum(c["divergences"] for c in chains),
                   sum(c["maximum_depth_stops"] for c in chains), extra)
    np.savez_compressed(DRAWS / f"{short(model)}-{arm}-{seed}.npz", draws=draws, names=np.asarray(ref["names"]),
                        unconstrained=unc, installed=np.asarray(installed, dtype=float))
    raw.unlink()
    return cell


def run_model_arm(model: str, arm: str) -> None:
    ref = reference(model)
    for seed in SEEDS:
        if cell_path(model, arm, seed).exists():
            continue
        try:
            cell = run_owalnuts(model, arm, seed, ref)
        except Exception as e:  # noqa: BLE001
            cell = failure(model, arm, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
        write_cell(cell)


def machine_note() -> None:
    ART.mkdir(exist_ok=True)
    machine = ART / "measured_on.json"
    if not machine.exists():
        machine.write_text(json.dumps({
            "platform": platform.platform(), "processor": platform.processor(),
            "cpu_count": os.cpu_count(), "python": sys.version.split()[0],
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "note": "shared 16-core machine; up to seven agents ran concurrently; every wall is contended and an upper bound",
        }, indent=2) + "\n", encoding="utf-8")


def run_phase(arms: list[str]) -> None:
    for model in PROTOCOL["models"]:
        log(f"== {model}")
        for arm in arms:
            if all(cell_path(model, arm, s).exists() for s in SEEDS):
                continue
            cmd = [sys.executable, str(Path(__file__)), "cell", model, arm]
            try:
                cp = subprocess.run(cmd, timeout=TIMEOUT * len(SEEDS) + 900, text=True)
                if cp.returncode != 0:
                    log(f"child for {model}/{arm} exited {cp.returncode}")
            except subprocess.TimeoutExpired:
                log(f"child for {model}/{arm} timed out")
            for seed in SEEDS:
                if not cell_path(model, arm, seed).exists():
                    write_cell(failure(model, arm, seed, "timeout_or_crash", "child process ended without writing the cell"))


def run_funnel() -> None:
    FUNNEL_DIR.mkdir(parents=True, exist_ok=True)
    for arm in PROTOCOL["funnel"]["arms"]:
        for seed in PROTOCOL["funnel"]["seeds"]:
            out = FUNNEL_DIR / f"{arm}-{seed}.json"
            if out.exists() or (FUNNEL_DIR / f"{arm}-{seed}.failed.json").exists():
                continue
            log(f"funnel {arm} {seed}")
            try:
                cp = subprocess.run([str(FUNNEL), arm, str(seed), str(out)], capture_output=True, text=True, timeout=TIMEOUT)
                msg = cp.stderr.strip()[-400:]
                code = cp.returncode
            except subprocess.TimeoutExpired:
                msg, code = f"timeout after {TIMEOUT}s", "timeout"
            log(f"  {msg}")
            if not out.exists():
                (FUNNEL_DIR / f"{arm}-{seed}.failed.json").write_text(
                    json.dumps({"arm": arm, "seed": seed, "status": "error", "returncode": code, "error": msg}, indent=1) + "\n",
                    encoding="utf-8")


def run_all() -> None:
    machine_note()
    log("phase 1: diag and dense-candidate")
    run_phase(PROTOCOL["phases"]["phase_1_arms"])
    log("funnel side check")
    run_funnel()
    log("phase 2: dense-legacy")
    run_phase(PROTOCOL["phases"]["phase_2_arms"])
    log("done")


# --------------------------------------------------------------------------- analysis


def geomean(xs):
    xs = [x for x in xs if x is not None and math.isfinite(x) and x > 0]
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs))) if xs else float("nan")


def med(xs):
    xs = [x for x in xs if x is not None and math.isfinite(x)]
    return statistics.median(xs) if xs else None


def analyze() -> None:
    models = PROTOCOL["models"]
    cells = {}
    for path in sorted(CELLS.glob("*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        c.pop("parameters", None)
        c.pop("metric_updates", None)
        cells.setdefault(c["model"], {}).setdefault(c["arm"], {})[str(c["seed"])] = c
    per_model = {}
    for model in models:
        row = {}
        for arm in ARMS:
            seeds = cells.get(model, {}).get(arm, {})
            if not seeds:
                continue
            ok = [c for c in seeds.values() if c.get("status") == "ok"]
            e = {"n_cells": len(seeds), "n_ok": len(ok), "n_passed": sum(1 for c in ok if c["passed"]),
                 "statuses": {s: c.get("status") for s, c in seeds.items()},
                 "errors": {s: c.get("error", "")[:300] for s, c in seeds.items() if c.get("status") != "ok"},
                 "failed_gates": {s: [k for k, v in c["gates"].items() if not v] for s, c in seeds.items() if c.get("status") == "ok"}}
            for k in ["min_bulk_ess_per_gradient", "min_tail_ess_per_gradient", "min_bulk_ess", "min_tail_ess",
                      "max_rank_rhat", "max_abs_z", "gradients_total", "wall_seconds_contended", "depth_cap_fraction",
                      "divergences", "preconditioned_condition_median", "cholesky_failures_total"]:
                vals = [c.get(k) for c in ok]
                vals = [v for v in vals if v is not None and math.isfinite(v)]
                e[k] = {"median": med(vals), "values": vals}
            e["step_median"] = med([x for c in ok for x in (c.get("final_step_size") or [])])
            e["max_last_window_ridge"] = max((r for c in ok for r in (c.get("last_window_ridge_per_chain") or []) if r is not None), default=None)
            e["unconstrained_dimension"] = next((c.get("unconstrained_dimension") for c in ok), None)
            row[arm] = e
        per_model[model] = row

    def ratio(model, arm, base=DIAG, key="min_bulk_ess_per_gradient"):
        a = per_model[model].get(arm, {}).get(key, {}).get("median")
        b = per_model[model].get(base, {}).get(key, {}).get("median")
        return (a / b) if (a and b) else None

    comparisons = {}
    for arm in (CAND, LEGACY):
        rows = {}
        for model in models:
            if arm not in per_model[model] or DIAG not in per_model[model]:
                continue
            rows[model] = {"ratio_bulk_ess_per_gradient": ratio(model, arm),
                           "ratio_bulk_ess_per_second_contended": None,
                           "gates": per_model[model][arm]["n_passed"], "gates_diag": per_model[model][DIAG]["n_passed"]}
            wa = per_model[model][arm]["wall_seconds_contended"]["median"]
            wb = per_model[model][DIAG]["wall_seconds_contended"]["median"]
            ea = per_model[model][arm]["min_bulk_ess"]["median"]
            eb = per_model[model][DIAG]["min_bulk_ess"]["median"]
            if wa and wb and ea and eb:
                rows[model]["ratio_bulk_ess_per_second_contended"] = (ea / wa) / (eb / wb)
        complete = [m for m in rows if rows[m]["ratio_bulk_ess_per_gradient"]]
        comparisons[arm] = {
            "per_model": rows,
            "models_in_geomean": len(complete),
            "models_excluded_from_geomean": [m for m in models if m not in complete],
            "geomean_ratio_bulk_ess_per_gradient": geomean([rows[m]["ratio_bulk_ess_per_gradient"] for m in complete]),
            "geomean_ratio_bulk_ess_per_second_contended": geomean([rows[m]["ratio_bulk_ess_per_second_contended"] for m in complete]),
            "gates_total": sum(rows[m]["gates"] for m in rows),
            "gates_total_diag": sum(rows[m]["gates_diag"] for m in rows),
            "models_3_to_0": [m for m in rows if rows[m]["gates_diag"] == 3 and rows[m]["gates"] == 0],
        }
    # funnel
    funnel = {}
    for arm in PROTOCOL["funnel"]["arms"]:
        for seed in PROTOCOL["funnel"]["seeds"]:
            f = FUNNEL_DIR / f"{arm}-{seed}.json"
            if f.exists():
                c = json.loads(f.read_text())
                t = c["tail_mass"]
                funnel[f"{arm}-{seed}"] = {"arm": arm, "seed": seed, "status": "ok", "estimate": t["estimate"], "z": t["z"],
                                           "z_batch_means": t["z_batch_means"], "omega_bulk_ess": c["omega"]["bulk_ess"],
                                           "omega_rhat": c["omega"]["rhat"], "target_calls_total": c["target_calls_total"],
                                           "divergences": sum(ch["divergences"] for ch in c["chains_data"]),
                                           "final_step_size": [ch["final_step_size"] for ch in c["chains_data"]],
                                           "wall_seconds_contended": c["wall_seconds"]}
            elif (FUNNEL_DIR / f"{arm}-{seed}.failed.json").exists():
                funnel[f"{arm}-{seed}"] = {"arm": arm, "seed": seed, "status": "error", "z": None, "divergences": None}
    fz = {k: v for k, v in funnel.items() if v["arm"] == "dense-candidate"}
    fd = {k: v for k, v in funnel.items() if v["arm"] == "diag"}
    funnel_ok = len(fz) == 3 and all(v["status"] == "ok" and abs(v["z"]) <= 2 for v in fz.values())
    div_c = sum(v["divergences"] or 0 for v in fz.values())
    div_d = sum(v["divergences"] or 0 for v in fd.values())

    c = comparisons[CAND]
    rule = PROTOCOL["decision_rule"]
    conditions = {
        "geomean_ge_1_5": bool(c["geomean_ratio_bulk_ess_per_gradient"] >= rule["min_geomean_ratio"]),
        "gates_ge_diag_minus_1": bool(c["gates_total"] >= c["gates_total_diag"] - rule["max_gate_deficit"]),
        "funnel_abs_z_le_2_every_seed": bool(funnel_ok),
        "no_model_3_of_3_to_0_of_3": not c["models_3_to_0"],
    }
    decision = {"conditions": conditions, "flip": all(conditions.values()),
                "geomean": c["geomean_ratio_bulk_ess_per_gradient"], "gates": c["gates_total"],
                "gates_diag": c["gates_total_diag"], "funnel_z": {k: v["z"] for k, v in fz.items()},
                "models_3_to_0": c["models_3_to_0"]}

    dm, ag = "diamonds-diamonds", "mcycle_gp-accel_gp"
    lg = comparisons[LEGACY]
    predictions = {
        "P1_candidate_geomean_ge_2": {"value": c["geomean_ratio_bulk_ess_per_gradient"],
                                      "held": bool(c["geomean_ratio_bulk_ess_per_gradient"] >= 2.0)},
        "P2_diamonds_ratio_ge_20": {"value": c["per_model"].get(dm, {}).get("ratio_bulk_ess_per_gradient"),
                                    "held": bool((c["per_model"].get(dm, {}).get("ratio_bulk_ess_per_gradient") or 0) >= 20)},
        "P3_accel_gp_0_of_3_every_arm": {"value": {a: per_model[ag].get(a, {}).get("n_passed") for a in ARMS},
                                         "held": all(per_model[ag].get(a, {}).get("n_passed") == 0 for a in ARMS)},
        "P4_candidate_gates_ge_diag": {"value": [c["gates_total"], c["gates_total_diag"]],
                                       "held": bool(c["gates_total"] >= c["gates_total_diag"])},
        "P5_funnel_candidate_abs_z_le_2_and_div_le_2x_diag": {
            "value": {"z": {k: v["z"] for k, v in fz.items()}, "divergences_candidate": div_c, "divergences_diag": div_d},
            "held": bool(funnel_ok and div_c <= 2 * div_d)},
        "P6_legacy_geomean_le_0_5_and_gates_lt_diag": {"value": [lg["geomean_ratio_bulk_ess_per_gradient"], lg["gates_total"], lg["gates_total_diag"]],
                                                       "held": bool(lg["geomean_ratio_bulk_ess_per_gradient"] <= 0.5 and lg["gates_total"] < lg["gates_total_diag"])},
    }
    summary = {
        "schema": "dense-metric-confirmation-v1-summary",
        "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "decision": decision, "predictions": predictions,
        "per_model": per_model, "comparisons": comparisons, "funnel": funnel,
        "funnel_divergences": {"dense-candidate": div_c, "diag": div_d},
        "cells": cells,
    }
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")

    def f(x, fmt):
        return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)

    L = ["# WP51 dense-default confirmation — results", "",
         "Seed medians over ok cells (3 seeds per arm). `gates` = cells passing rank R-hat <= 1.01, bulk/tail ESS >= 400, "
         "zero retained divergences, no sampler error (timeouts and errors count as failures). `kappa` = condition number of "
         "the pooled retained unconstrained covariance in the installed metric's whitened coordinates (median over chains). "
         "Walls are CONTENDED (up to seven agents on 16 cores) and decide nothing.", "",
         "| model | d | arm | gates | grads | min bulk ESS | bulk ESS/grad x1e3 | ratio vs diag | step | cap frac | kappa | last ridge max | max R-hat | div | max abs z | wall s (contended) |",
         "|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|"]
    for model in models:
        for arm in ARMS:
            e = per_model[model].get(arm)
            if not e:
                continue
            bad = [s for s in e["statuses"].values() if s != "ok"]
            status = f"{e['n_passed']}/{e['n_cells']}" + (f" ({len(bad)} {'/'.join(sorted(set(bad)))})" if bad else "")
            r = ratio(model, arm) if arm != DIAG else 1.0
            L.append(f"| {model} | {e['unconstrained_dimension']} | {arm} | {status} | {f(e['gradients_total']['median'], ',.0f')} | "
                     f"{f(e['min_bulk_ess']['median'], ',.0f')} | {f((e['min_bulk_ess_per_gradient']['median'] or float('nan')) * 1e3, '.3f')} | "
                     f"{f(r, '.2f')} | {f(e['step_median'], '.3g')} | {f(e['depth_cap_fraction']['median'], '.3f')} | "
                     f"{f(e['preconditioned_condition_median']['median'], '.3g')} | {f(e['max_last_window_ridge'], '.2g')} | "
                     f"{f(e['max_rank_rhat']['median'], '.4f')} | "
                     f"{','.join(str(int(x)) for x in e['divergences']['values'])} | {f(e['max_abs_z']['median'], '.2f')} | "
                     f"{f(e['wall_seconds_contended']['median'], '.1f')} |")
    for arm, comp in comparisons.items():
        L += ["", f"## {arm} versus owalnuts-diag", "",
              f"- geomean min-bulk-ESS/gradient ratio over {comp['models_in_geomean']} models: "
              f"{f(comp['geomean_ratio_bulk_ess_per_gradient'], '.3f')} (excluded: {comp['models_excluded_from_geomean'] or 'none'}); "
              f"contended ESS/s geomean {f(comp['geomean_ratio_bulk_ess_per_second_contended'], '.3f')}",
              f"- gates {comp['gates_total']}/51 versus diag {comp['gates_total_diag']}/51; models 3/3 -> 0/3: {comp['models_3_to_0'] or 'none'}", "",
              "| model | ESS/grad ratio | contended ESS/s ratio | gates | diag gates |", "|---|---:|---:|---|---|"]
        for m, r in comp["per_model"].items():
            L.append(f"| {m} | {f(r['ratio_bulk_ess_per_gradient'], '.2f')} | {f(r['ratio_bulk_ess_per_second_contended'], '.2f')} | "
                     f"{r['gates']}/3 | {r['gates_diag']}/3 |")
    L += ["", "## Funnel side check (P(omega < -5), exact 0.0478; gate |z| <= 2 per seed)", "",
          "| cell | status | estimate | MCSE z | batch-means z | omega bulk ESS | omega R-hat | divergences | final steps |",
          "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for k, v in funnel.items():
        if v["status"] != "ok":
            L.append(f"| {k} | {v['status']} | — | — | — | — | — | — | — |")
            continue
        L.append(f"| {k} | ok | {v['estimate']:.4f} | {v['z']:+.2f} | {v['z_batch_means']:+.2f} | {v['omega_bulk_ess']:.0f} | "
                 f"{v['omega_rhat']:.4f} | {v['divergences']} | {', '.join(f'{x:.3g}' for x in v['final_step_size'])} |")
    L += ["", "## Frozen decision rule", ""]
    for k, v in conditions.items():
        L.append(f"- {k}: {v}")
    L.append(f"- **flip: {decision['flip']}**")
    L += ["", "## Preregistered predictions", "", "| prediction | held | value |", "|---|---|---|"]
    for k, v in predictions.items():
        L.append(f"| {k} | {v['held']} | `{json.dumps(v['value'], default=str)[:400]}` |")
    (ART / "results-table.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] == "run":
        run_all()
    elif args[0] == "cell":
        run_model_arm(args[1], args[2])
    elif args[0] == "funnel":
        run_funnel()
    elif args[0] == "analyze":
        analyze()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
