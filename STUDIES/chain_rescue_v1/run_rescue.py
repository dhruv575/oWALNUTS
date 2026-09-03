#!/usr/bin/env python3
"""chain_rescue_v1 driver (WP33): the v5 posteriordb protocol on eight models, arms da / restart / pool, fresh seeds.

    python run_rescue.py prepare           # copy Stan programs + data from posteriordb and compile with BridgeStan
    python run_rescue.py run               # every model/arm/seed in protocol order (resumable)
    python run_rescue.py run --models=a,b --arms=da,restart
    python run_rescue.py cell <model> <arm>  # one model/arm, all seeds (child process)
    python run_rescue.py checks            # the funnel cells, every arm and seed (resumable)
    python run_rescue.py analyze           # artifacts/summary.json + results-table.md + the decision rule

Each cell writes `artifacts/cells/<model>-<arm>-<seed>.json` (metrics, no draws)
and `artifacts/draws/<model>-<arm>-<seed>.npz`. Failures are cells with status != "ok".
The metrics function is the v5 one (same gates, same ArviZ estimators, same z).
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
MODELS = HERE / "models"
PDB_PATH = HERE / "posteriordb" / "posterior_database"
HARNESS = HERE / "target" / "release" / "chain-rescue-v1.exe"
FUNNEL = HERE / "target" / "release" / "funnel.exe"
ARMS = ["da", "restart", "pool"]
SEEDS = PROTOCOL["seeds"]
FUNNEL_SEEDS = PROTOCOL["funnel"]["seeds"]
TIMEOUT = PROTOCOL["cell_timeout_seconds"]
RULE = PROTOCOL["decision_rule"]
os.environ.setdefault("MAKE", "mingw32-make")
BRIDGESTAN_MAKE_ARGS: list[str] = []  # no STAN_THREADS (v1 wall-gap finding)


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
    bulk = np.asarray(az.ess(ds, method="bulk").p.values, dtype=float)
    tail = np.asarray(az.ess(ds, method="tail", prob=(0.05, 0.95)).p.values, dtype=float)
    rhat = np.asarray(az.rhat(ds, method="rank").p.values, dtype=float)
    mcse = np.asarray(az.mcse(ds, method="mean").p.values, dtype=float)
    return {
        "mean": arr.reshape(-1, arr.shape[-1]).mean(0),
        "sd": arr.reshape(-1, arr.shape[-1]).std(0, ddof=1),
        "bulk_ess": bulk, "tail_ess": tail, "rhat": rhat, "mcse": mcse,
    }


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


# --------------------------------------------------------------------------- metrics (v5)


def metrics(model: str, arm: str, seed: int, draws: np.ndarray, names: list[str], ref: dict,
            wall: float, grads_total: int, grads_sampling: int, divergences: int,
            max_depth_stops: int, extra: dict) -> dict:
    st = arviz_stats(draws)
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
    per_param = {
        n: {"mean": float(st["mean"][i]), "sd": float(st["sd"][i]), "mcse": float(st["mcse"][i]),
            "bulk_ess": float(st["bulk_ess"][i]), "tail_ess": float(st["tail_ess"][i]),
            "rhat": float(st["rhat"][i]), "ref_mean": float(ref["mean"][i]), "ref_sd": float(ref["sd"][i]),
            "ref_mcse": float(ref["mcse"][i]), "z": float(z[i]), "abs_dmean_over_ref_sd": float(dsd[i])}
        for i, n in enumerate(names)
    }
    return {
        "schema": "chain-rescue-v1-cell-metrics",
        "model": model, "arm": arm, "seed": seed, "status": "ok",
        "wall_seconds": wall, "gradients_total": grads_total, "gradients_sampling": grads_sampling,
        "divergences": divergences, "max_depth_stops": max_depth_stops,
        "min_bulk_ess": min_bulk, "min_tail_ess": min_tail, "max_rank_rhat": max_rhat,
        "argmin_bulk_ess": names[int(np.nanargmin(st["bulk_ess"]))],
        "min_bulk_ess_per_second": min_bulk / wall,
        "min_bulk_ess_per_gradient": min_bulk / grads_total,
        "min_tail_ess_per_gradient": min_tail / grads_total,
        "max_abs_z": float(np.nanmax(np.abs(z))),
        "argmax_abs_z": names[int(np.nanargmax(np.abs(z)))],
        "max_abs_dmean_over_ref_sd": float(np.nanmax(dsd)),
        "agreement_flag": bool(np.nanmax(np.abs(z)) > 4),
        "gates": gates, "passed": all(gates.values()), "parameters": per_param, **extra,
    }


def failure(model: str, arm: str, seed: int, status: str, message: str, **extra) -> dict:
    return {"schema": "chain-rescue-v1-cell-metrics", "model": model, "arm": arm, "seed": seed,
            "status": status, "error": message, "passed": False, "gates": {"no_sampler_error": False}, **extra}


def cell_path(model: str, arm: str, seed: int) -> Path:
    return CELLS / f"{short(model)}-{arm}-{seed}.json"


def write_cell(cell: dict) -> None:
    CELLS.mkdir(parents=True, exist_ok=True)
    cell_path(cell["model"], cell["arm"], cell["seed"]).write_text(json.dumps(cell, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if cell["status"] == "ok":
        log(f"  {cell['arm']} {cell['seed']}: wall {cell['wall_seconds']:.2f}s grads {cell['gradients_total']} "
            f"minbulk {cell['min_bulk_ess']:.0f} mintail {cell['min_tail_ess']:.0f} rhat {cell['max_rank_rhat']:.4f} "
            f"div {cell['divergences']} max|z| {cell['max_abs_z']:.2f} rescued {cell['rescued_chains']} passed {cell['passed']}")
    else:
        log(f"  {cell['arm']} {cell['seed']}: {cell['status']}: {cell.get('error', '')[:200]}")


# --------------------------------------------------------------------------- the oWALNUTS cell


def rescue_summary(chains: list[dict]) -> dict:
    """Counts from the per-chain ChainRescueUpdate records."""
    restarted, pooled, by_criterion, events = 0, 0, {"Step": 0, "LogDensity": 0}, []
    for c in chains:
        for u in c["chain_rescues"]:
            o = u["outcome"]
            if o["kind"] == "restarted":
                restarted += 1
                by_criterion[o["criterion"]] = by_criterion.get(o["criterion"], 0) + 1
                events.append({"chain": u["chain"], "window": u["window_index"], "transition": u["transition"],
                               "criterion": o["criterion"], "source": o["source"], "step_before": u["step_before"],
                               "step_after": o["step_after"], "median_log_density": u["median_log_density"]})
            elif o["kind"] == "pooled":
                pooled += 1
    boundaries = max((len(c["chain_rescues"]) for c in chains), default=0)
    return {"rescued_chains": restarted, "rescues_by_criterion": by_criterion, "pooled_boundaries": pooled // max(len(chains), 1),
            "rescue_boundaries": boundaries, "rescue_events": events}


def run_owalnuts(model: str, arm: str, seed: int, ref: dict) -> dict:
    import bridgestan as bs

    so, data = prepare_bridgestan(model)
    raw = DRAWS / f"{short(model)}-{arm}-{seed}.raw.json"
    DRAWS.mkdir(parents=True, exist_ok=True)
    if raw.exists():
        raw.unlink()
    cmd = [str(HARNESS), str(so), str(data), arm, str(seed), str(raw), "4"]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return failure(model, arm, seed, "timeout", f"exceeded {TIMEOUT}s")
    if cp.returncode != 0 or not raw.exists():
        return failure(model, arm, seed, "error", cp.stderr.strip()[-2000:])
    out = json.loads(raw.read_text(encoding="utf-8"))
    if out.get("status") != "ok":
        return failure(model, arm, seed, "error", out.get("error", "unknown"), wall_seconds=out.get("wall_seconds"))
    bs.compile.windows_dll_path_setup()
    sm = bs.StanModel(str(so), data=data.read_text(encoding="utf-8"), seed=1)
    cnames = [bridgestan_name(n) for n in sm.param_names(include_tp=True, include_gq=False)]
    unc = np.asarray([c["samples"] for c in out["chains_data"]], dtype=np.float64)
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
    extra = {
        "final_step_size": [c["final_step_size"] for c in chains],
        "refinement_exhaustions_per_chain": [c["refinement_exhaustions"] for c in chains],
        "frozen_chains": sum(1 for c in chains if c["refinement_exhaustions"] > out["retained"] // 2),
        "start_search_calls": out["init"]["start_search_calls"],
        "warmup_config": out["warmup_config"],
        "mass_diagonal_max": [max(c["mass_diagonal"]) for c in chains],
        "mass_diagonal_min": [min(c["mass_diagonal"]) for c in chains],
        "warmup_divergences": sum(c["warmup_divergences"] for c in chains),
        "algorithm_revision": out["algorithm_revision"],
        "per_chain_bulk_ess_min": [float(np.nanmin(arviz_stats(draws[i:i + 1])["bulk_ess"])) for i in range(draws.shape[0])],
        **rescue_summary(chains),
    }
    cell = metrics(model, arm, seed, draws, ref["names"], ref, out["wall_seconds"], out["target_calls_total"], grads_sampling,
                   sum(c["divergences"] for c in chains), sum(c["maximum_depth_stops"] for c in chains), extra)
    DRAWS.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(DRAWS / f"{short(model)}-{arm}-{seed}.npz", draws=draws, names=np.asarray(ref["names"]), unconstrained=unc)
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


def run_all(models: list[str], arms: list[str]) -> None:
    ART.mkdir(exist_ok=True)
    machine = ART / "measured_on.json"
    if not machine.exists():
        machine.write_text(json.dumps({
            "platform": platform.platform(), "processor": platform.processor(), "cpu_count": os.cpu_count(),
            "python": sys.version.split()[0], "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "note": "shared machine; other worktrees may run concurrently; walls are upper bounds",
        }, indent=2) + "\n", encoding="utf-8")
    for model in models:
        log(f"== {model}")
        for arm in arms:
            if all(cell_path(model, arm, s).exists() for s in SEEDS):
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


# --------------------------------------------------------------------------- funnel


def funnel_path(arm: str, seed: int) -> Path:
    return ART / "funnel" / f"funnel-{arm}-{seed}.json"


def run_checks(arms: list[str]) -> None:
    (ART / "funnel").mkdir(parents=True, exist_ok=True)
    for arm in arms:
        for seed in FUNNEL_SEEDS:
            out = funnel_path(arm, seed)
            if out.exists():
                continue
            log(f"funnel {arm} {seed}")
            cp = subprocess.run([str(FUNNEL), arm, str(seed), str(out)], capture_output=True, text=True)
            log(f"  {cp.stderr.strip()[-300:]}")


def funnel_cell(arm: str, seed: int) -> dict | None:
    path = funnel_path(arm, seed)
    if not path.exists():
        return None
    c = json.loads(path.read_text(encoding="utf-8"))
    t = c["tail_mass"]
    z_ok = abs(t["z"]) <= PROTOCOL["decision_rule"]["funnel_abs_z_max"]
    ess_ok = c["omega"]["bulk_ess"] >= PROTOCOL["gates"]["min_bulk_ess"]
    rhat_ok = c["omega"]["rhat"] <= PROTOCOL["gates"]["max_rank_rhat"]
    steps = [ch["final_step_size"] for ch in c["chains_data"]]
    return {"arm": arm, "seed": seed, "estimate": t["estimate"], "z": t["z"], "z_batch_means": t["z_batch_means"],
            "omega_bulk_ess": c["omega"]["bulk_ess"], "omega_rhat": c["omega"]["rhat"],
            "target_calls_total": c["target_calls_total"], "depth_caps": sum(ch["depth_caps"] for ch in c["chains_data"]),
            "divergences": sum(ch["divergences"] for ch in c["chains_data"]),
            "final_step_size": steps, "step_spread": max(steps) / min(steps),
            "min_bulk_ess_per_gradient": c["omega"]["bulk_ess"] / c["target_calls_total"],
            "rescued_chains": c.get("rescued_chains", 0), "rescue_events": c.get("rescue_events", []),
            "gates": {"abs_z": z_ok, "omega_bulk_ess": ess_ok, "omega_rhat": rhat_ok},
            "passed": z_ok and ess_ok and rhat_ok, "wall_seconds": c["wall_seconds"]}


# --------------------------------------------------------------------------- analysis


def geomean(xs: list[float]) -> float:
    xs = [x for x in xs if x and math.isfinite(x) and x > 0]
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs))) if xs else float("nan")


def med(xs):
    xs = [x for x in xs if x is not None and math.isfinite(x)]
    return statistics.median(xs) if xs else None


def analyze() -> None:
    models = PROTOCOL["models"]
    cells: dict = {}
    for path in sorted(CELLS.glob("*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        c.pop("parameters", None)
        cells.setdefault(c["model"], {}).setdefault(c["arm"], {})[str(c["seed"])] = c
    funnel = {arm: {str(s): funnel_cell(arm, s) for s in FUNNEL_SEEDS} for arm in ARMS}

    per_model = {}
    for model in models:
        row = {}
        for arm in ARMS:
            seeds = cells.get(model, {}).get(arm, {})
            ok = [c for c in seeds.values() if c.get("status") == "ok"]
            row[arm] = {
                "n_cells": len(seeds), "n_ok": len(ok), "n_passed": sum(1 for c in ok if c["passed"]),
                "statuses": {s: c.get("status") for s, c in seeds.items()},
                "passed_by_seed": {s: bool(c.get("passed")) for s, c in seeds.items()},
                "ess_per_gradient_median": med([c["min_bulk_ess_per_gradient"] for c in ok]),
                "ess_per_gradient": {s: c["min_bulk_ess_per_gradient"] for s, c in seeds.items() if c.get("status") == "ok"},
                "min_bulk_ess": [c["min_bulk_ess"] for c in ok],
                "max_rank_rhat": [c["max_rank_rhat"] for c in ok],
                "max_abs_z": {s: c["max_abs_z"] for s, c in seeds.items() if c.get("status") == "ok"},
                "max_abs_z_median": med([c["max_abs_z"] for c in ok]),
                "divergences": [c["divergences"] for c in ok],
                "wall_seconds": [c["wall_seconds"] for c in ok],
                "gradients_total": [c["gradients_total"] for c in ok],
                "rescued_chains": [c.get("rescued_chains", 0) for c in ok],
                "rescues_by_criterion": [c.get("rescues_by_criterion") for c in ok],
                "rescue_events": {s: c.get("rescue_events", []) for s, c in seeds.items() if c.get("status") == "ok"},
                "pooled_boundaries": [c.get("pooled_boundaries", 0) for c in ok],
                "final_step_size": [c.get("final_step_size") for c in ok],
                "per_chain_bulk_ess_min": [c.get("per_chain_bulk_ess_min") for c in ok],
            }
        per_model[model] = row

    # Decision rule per candidate against da on paired cells.
    def gates_of(arm):
        n = sum(per_model[m][arm]["n_passed"] for m in models)
        n += sum(1 for s in FUNNEL_SEEDS if (funnel[arm].get(str(s)) or {}).get("passed"))
        return n

    decision = {}
    for arm in ("restart", "pool"):
        ratios = {m: (per_model[m][arm]["ess_per_gradient_median"] / per_model[m]["da"]["ess_per_gradient_median"])
                  if per_model[m][arm]["ess_per_gradient_median"] and per_model[m]["da"]["ess_per_gradient_median"] else None
                  for m in models}
        fr = {str(s): funnel[arm].get(str(s)) for s in FUNNEL_SEEDS}
        fd = {str(s): funnel["da"].get(str(s)) for s in FUNNEL_SEEDS}
        ratios["funnel"] = (med([c["min_bulk_ess_per_gradient"] for c in fr.values() if c]) / med([c["min_bulk_ess_per_gradient"] for c in fd.values() if c])
                            if all(fr.values()) and all(fd.values()) else None)
        new_bias = [f"{m}/{s}" for m in models for s in per_model[m][arm]["max_abs_z"]
                    if per_model[m][arm]["max_abs_z"][s] > RULE["agreement_abs_z_max_new"]
                    and per_model[m]["da"]["max_abs_z"].get(s, 0) <= RULE["agreement_abs_z_max_new"]]
        fz = [c["z"] for c in fr.values() if c]
        c1 = gates_of(arm) - gates_of("da")
        crit = {
            "C1_gain_cells": {"value": c1, "held": c1 >= RULE["gain_cells"]},
            "C2_min_ess_per_gradient_ratio": {"value": min((r for r in ratios.values() if r is not None), default=None),
                                              "per_model": ratios,
                                              "held": all(r is None or r >= RULE["per_model_ess_per_gradient_floor"] for r in ratios.values())},
            "C3_new_reference_disagreement": {"value": new_bias, "held": not new_bias},
            "C4_funnel_abs_z_le_2": {"value": fz, "held": len(fz) == len(FUNNEL_SEEDS) and all(abs(z) <= RULE["funnel_abs_z_max"] for z in fz)},
        }
        decision[arm] = {"cells_passed": gates_of(arm), "da_cells_passed": gates_of("da"), "criteria": crit,
                         "flip": all(v["held"] for v in crit.values())}

    controls = ["kidiq-kidscore_momhsiq", "mesquite-logmesquite_logvash", "nes2000-nes"]
    control_events = {m: per_model[m]["restart"]["rescue_events"] for m in models if m in controls}
    p1 = all(len(ev) <= 1 and all(e["window"] <= 1 for e in ev) for m in control_events.values() for ev in m.values())
    fr = [funnel["restart"][str(s)] for s in FUNNEL_SEEDS]
    p2 = all(c and c["passed"] and c["step_spread"] <= 10 for c in fr)
    hmm = "bball_drive_event_0-hmm_drive_0"
    hmm_da_bad = [s for s, c in cells.get(hmm, {}).get("da", {}).items() if c.get("status") == "ok" and c["max_rank_rhat"] > 1.01]
    p3_detail = {s: {"restart_rhat": (cells[hmm].get("restart", {}).get(s) or {}).get("max_rank_rhat"),
                     "events": per_model[hmm]["restart"]["rescue_events"].get(s)} for s in hmm_da_bad}
    p3 = all(d["restart_rhat"] is not None and d["restart_rhat"] <= 1.01 and any(e["criterion"] == "LogDensity" and e["window"] <= 2 for e in (d["events"] or []))
             for d in p3_detail.values()) if hmm_da_bad else None
    p4 = all(abs((per_model[m][arm]["max_abs_z_median"] or 0) - (per_model[m]["da"]["max_abs_z_median"] or 0)) <= 1 for m in models for arm in ("restart", "pool"))
    pool_ratios = decision["pool"]["criteria"]["C2_min_ess_per_gradient_ratio"]["per_model"]
    p5 = all(r is None or 0.9 <= r <= 1.2 for r in pool_ratios.values()) and decision["pool"]["criteria"]["C1_gain_cells"]["value"] <= 0
    p6 = not any(d["flip"] for d in decision.values())
    predictions = {"P1_restart_quiet_on_controls": {"held": p1, "events": control_events},
                   "P2_restart_funnel_gate_and_step_spread": {"held": p2, "cells": fr},
                   "P3_restart_fixes_second_mode_hmm": {"held": p3, "da_failing_seeds": hmm_da_bad, "detail": p3_detail},
                   "P4_no_bias_shift": {"held": p4},
                   "P5_pool_within_band_no_gate": {"held": p5, "ratios": pool_ratios},
                   "P6_rule_not_met": {"held": p6}}
    summary = {"schema": "chain-rescue-v1-summary", "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "protocol_sha256": __import__("hashlib").sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
               "cells_passed": {arm: gates_of(arm) for arm in ARMS}, "decision": decision, "predictions": predictions,
               "per_model": per_model, "funnel": funnel, "cells": cells}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    def f(x, fmt):
        return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)

    lines = ["# chain_rescue_v1 — results", "",
             "Seed medians over 3 seeds; `gates` = cells passing R-hat <= 1.01, bulk/tail ESS >= 400, zero divergences; "
             "`rescued` = chains re-seeded per seed (restart) or boundaries pooled per seed (pool); `max|z|` = worst "
             "posterior-mean z against the posteriordb reference per seed.", "",
             "| model | arm | gates | ESS/grad x1e3 | vs da | min bulk ESS per seed | max R-hat per seed | max abs z per seed | rescued per seed | final steps (seed 1) |",
             "|---|---|---|---:|---:|---|---|---|---|---|"]
    for model in models:
        for arm in ARMS:
            e = per_model[model][arm]
            r = decision.get(arm, {}).get("criteria", {}).get("C2_min_ess_per_gradient_ratio", {}).get("per_model", {}).get(model) if arm != "da" else 1.0
            steps = e["final_step_size"][0] if e["final_step_size"] else None
            resc = e["rescued_chains"] if arm == "restart" else e["pooled_boundaries"] if arm == "pool" else [0] * len(e["rescued_chains"])
            lines.append(f"| {model} | {arm} | {e['n_passed']}/{e['n_cells']} | {f((e['ess_per_gradient_median'] or float('nan')) * 1e3, '.3f')} | {f(r, '.2f')} | "
                         f"{', '.join(f'{x:.0f}' for x in e['min_bulk_ess'])} | {', '.join(f'{x:.3f}' for x in e['max_rank_rhat'])} | "
                         f"{', '.join(f'{x:.2f}' for x in e['max_abs_z'].values())} | {', '.join(str(x) for x in resc)} | "
                         f"{'[' + ', '.join(f'{x:.3g}' for x in steps) + ']' if steps else '—'} |")
    lines += ["", "## Funnel tail mass P(omega < -5) (exact 0.0478), 4 x 2,000 / 20,000; gate = |z| <= 2 and omega bulk ESS >= 400 and R-hat <= 1.01", "",
              "| arm | seed | estimate | z | omega bulk ESS | omega R-hat | target calls | depth caps | final steps | step spread | rescued | gate |", "|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|---|"]
    for arm in ARMS:
        for s in FUNNEL_SEEDS:
            c = funnel[arm].get(str(s))
            if not c:
                lines.append(f"| {arm} | {s} | not run | | | | | | | | | |")
                continue
            lines.append(f"| {arm} | {s} | {c['estimate']:.4f} | {c['z']:+.2f} | {c['omega_bulk_ess']:.0f} | {c['omega_rhat']:.3f} | {c['target_calls_total']:,} | {c['depth_caps']} | "
                         f"{', '.join(f'{x:.3g}' for x in c['final_step_size'])} | {c['step_spread']:.1f} | {c['rescued_chains']} | {'pass' if c['passed'] else 'fail'} |")
    lines += ["", "## Rescue events (restart arm)", "", "| model | seed | chain | window | transition | criterion | source | step before -> after | median log density |", "|---|---|---|---|---|---|---|---|---|"]
    for model in models:
        for s, ev in per_model[model]["restart"]["rescue_events"].items():
            for e in ev:
                lines.append(f"| {model} | {s} | {e['chain']} | {e['window']} | {e['transition']} | {e['criterion']} | {e['source']} | {e['step_before']:.3g} -> {e['step_after']:.3g} | {f(e['median_log_density'], '.1f')} |")
    for arm in ARMS:
        for s in FUNNEL_SEEDS:
            c = funnel[arm].get(str(s))
            for e in (c or {}).get("rescue_events", []):
                lines.append(f"| funnel ({arm}) | {s} | {e['chain']} | {e['window']} | {e['transition']} | {e['criterion']} | {e['source']} | {e['step_before']:.3g} -> {e['step_after']:.3g} | {f(e['median_log_density'], '.1f')} |")
    lines += ["", "## Decision rule", "", "| candidate | cells passed (of 27) | da | C1 gain >= 3 | C2 min ESS/grad ratio >= 0.9 | C3 new |z| > 3.5 | C4 funnel |z| <= 2 | flip |", "|---|---:|---:|---|---|---|---|---|"]
    for arm, d in decision.items():
        c = d["criteria"]
        lines.append(f"| {arm} | {d['cells_passed']} | {d['da_cells_passed']} | {c['C1_gain_cells']['value']} ({c['C1_gain_cells']['held']}) | "
                     f"{f(c['C2_min_ess_per_gradient_ratio']['value'], '.3f')} ({c['C2_min_ess_per_gradient_ratio']['held']}) | "
                     f"{c['C3_new_reference_disagreement']['value'] or 'none'} ({c['C3_new_reference_disagreement']['held']}) | "
                     f"{', '.join(f'{z:+.2f}' for z in c['C4_funnel_abs_z_le_2']['value'])} ({c['C4_funnel_abs_z_le_2']['held']}) | **{d['flip']}** |")
    lines += ["", "## Predictions", "", "| prediction | held |", "|---|---|"]
    for k, v in predictions.items():
        lines.append(f"| {k} | {v['held']} |")
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
    elif args[0] == "prepare":
        for model in PROTOCOL["models"]:
            prepare_bridgestan(model)
    elif args[0] == "cell":
        run_model_arm(args[1], args[2])
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
