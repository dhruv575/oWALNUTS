#!/usr/bin/env python3
"""WP43 init_rule_v1 driver: start rules on the 17-model posteriordb screen.

    python run_init.py run        # every (model, seed, arm) cell in protocol order, then the funnel row
    python run_init.py funnel     # the funnel row only
    python run_init.py analyze    # artifacts/summary.json + results-table.md

Each cell is one fresh child process of the Rust harness
(target/release/init-rule-v1.exe) and writes
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
PDB_PATH = HERE / PROTOCOL["posteriordb"]["path"]
HARNESS = HERE / "target" / "release" / "init-rule-v1.exe"
FUNNEL = HERE / "target" / "release" / "funnel.exe"
ARMS = PROTOCOL["arms_order"]
RULE_ARMS = [a for a in ARMS if a != "default"]
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
        "schema": "init-rule-v1-cell-metrics",
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
        "schema": "init-rule-v1-cell-metrics", "model": model, "arm": arm, "seed": seed,
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
            f"disagree {cell['disagreeing_chains']} off {cell['chains_off_reference']} "
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
            "note": "shared 16-core machine with nine sibling agents running concurrently; walls are contended upper bounds and are not evidence",
        }, indent=2) + "\n", encoding="utf-8")
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
    run_funnel()


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
                "final_step_size": [ch["final_step_size"] for ch in c["chains_data"]],
            }
        zs = [p["z"] for p in per.values() if p]
        out[arm] = {
            "per_seed": per,
            "complete": all(p is not None for p in per.values()),
            "all_abs_z_le_2": bool(len(zs) == len(per) and all(abs(z) <= 2 for z in zs)),
            "max_abs_z": max((abs(z) for z in zs), default=None),
        }
    return out


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
                "outcome_ranks": {s: c["outcome_rank"] for s, c in cs.items()},
                "max_rank_rhat": {s: c["max_rank_rhat"] for s, c in ok.items()},
                "max_abs_dmean_over_ref_sd": {s: c["max_abs_dmean_over_ref_sd"] for s, c in ok.items()},
                "disagreeing_chains": {s: c["disagreeing_chains"] for s, c in ok.items()},
                "chains_off_reference": {s: c["chains_off_reference"] for s, c in ok.items()},
                "start_log_densities": {s: c["start_log_densities"] for s, c in ok.items()},
                "start_log_density_median": statistics.median([x for c in ok.values() for x in c["start_log_densities"]]) if ok else None,
                "init_evaluations": {s: c.get("init_evaluations") for s, c in cs.items()},
                "min_bulk_ess_per_gradient": {s: c["min_bulk_ess_per_gradient"] for s, c in ok.items()},
                "gradients_total": {s: c["gradients_total"] for s, c in ok.items()},
                "frozen_chains": {s: c["frozen_chains"] for s, c in ok.items()},
            }
        # Paired efficiency ratio (seeds where both arms are ok).
        for a in RULE_ARMS:
            both = [s for s in SEEDS if s in row["default"]["min_bulk_ess_per_gradient"] and s in row[a]["min_bulk_ess_per_gradient"]]
            g_rule = geomean([row[a]["min_bulk_ess_per_gradient"][s] for s in both])
            g_def = geomean([row["default"]["min_bulk_ess_per_gradient"][s] for s in both])
            row[a]["paired_seeds"] = both
            row[a]["ess_per_gradient_ratio_vs_default"] = g_rule / g_def if both else None
        per_model[m] = row
    funnel = analyze_funnel()
    decisions = {}
    for a in RULE_ARMS:
        ratios = [per_model[m][a]["ess_per_gradient_ratio_vs_default"] for m in models]
        g = geomean(ratios)
        d1 = arms[a]["credited_passes"] >= arms["default"]["credited_passes"]
        d2 = len(arms[a]["hidden_mode_cells"]) == 0
        d3 = bool(math.isfinite(g) and g >= PROTOCOL["decision_rule"]["geomean_min"])
        d4 = funnel[a]["all_abs_z_le_2"] and funnel[a]["complete"]
        decisions[a] = {
            "D1_credited_gates_ge_default": d1, "credited_passes": arms[a]["credited_passes"],
            "default_credited_passes": arms["default"]["credited_passes"],
            "D2_zero_hidden_mode": d2, "hidden_mode_cells": arms[a]["hidden_mode_cells"],
            "D3_geomean_ratio_ge_0_97": d3, "geomean_ess_per_gradient_ratio": g,
            "per_model_ratio_min": min((r for r in ratios if r), default=None),
            "D4_funnel_abs_z_le_2_every_seed": d4, "funnel_max_abs_z": funnel[a]["max_abs_z"],
            "qualifies": bool(d1 and d2 and d3 and d4),
        }
    qualifying = [a for a in RULE_ARMS if decisions[a]["qualifies"]]
    qualifying.sort(key=lambda a: (-decisions[a]["credited_passes"], -decisions[a]["geomean_ess_per_gradient_ratio"]))
    recommendation = qualifying[0] if qualifying else "keep Init::uniform() default"
    hmm = "bball_drive_event_0-hmm_drive_0"
    lv = "hudson_lynx_hare-lotka_volterra"

    def lottery(model, a):
        r = per_model[model][a]
        return {
            "credited_passes": r["credited_passes"], "hidden": r["hidden"],
            "seeds_with_chain_off_reference": [s for s, v in r["chains_off_reference"].items() if v],
            "seeds_with_disagreeing_chain": [s for s, v in r["disagreeing_chains"].items() if v],
            "frozen": [s for s, v in r["frozen_chains"].items() if v],
            "rhat_fail_seeds": [s for s, v in r["max_rank_rhat"].items() if v > 1.01],
        }
    lotteries = {model: {a: lottery(model, a) for a in ARMS} for model in (hmm, lv)}
    # Predictions (frozen in protocol.json; evaluated mechanically here).
    P = {}
    dc = arms["default"]["credited_passes"]
    P["P1"] = {"value": dc, "held": 70 <= dc <= 74}
    b = "best16"
    hmm_off = {a: len(lotteries[hmm][a]["seeds_with_chain_off_reference"]) for a in ARMS}
    lv_bad = {a: 5 - lotteries[lv][a]["credited_passes"] for a in ARMS}
    P["P2"] = {"value": {"hmm_default_seeds_off": hmm_off["default"], "hmm_best16_seeds_off": hmm_off[b],
                         "lv_default_fail": lv_bad["default"], "lv_best16_fail": lv_bad[b]},
               "held": hmm_off[b] == 0 and lv_bad[b] == 0 and 1 <= hmm_off["default"] <= 2}
    P["P1"]["value"] = {"credited": dc,
                        "centered_eight_schools_fail": 5 - per_model["eight_schools-eight_schools_centered"]["default"]["credited_passes"],
                        "accel_gp_fail": 5 - per_model["mcycle_gp-accel_gp"]["default"]["credited_passes"]}
    P["P1"]["held"] = (70 <= dc <= 74 and P["P1"]["value"]["centered_eight_schools_fail"] == 5
                       and 2 <= P["P1"]["value"]["accel_gp_fail"] <= 3)
    P["P3"] = {"value": arms[b]["credited_passes"] - dc, "held": 1 <= arms[b]["credited_passes"] - dc <= 3}
    P["P4"] = {"value": arms[b]["hidden_mode_cells"], "held": len(arms[b]["hidden_mode_cells"]) == 0}
    gb = decisions[b]["geomean_ess_per_gradient_ratio"]
    P["P5"] = {"value": gb, "held": 1.00 <= gb <= 1.15}
    gm = decisions["median16"]["geomean_ess_per_gradient_ratio"]
    mc = arms["median16"]["credited_passes"]
    P["P6"] = {"value": {"credited_delta": mc - dc, "geomean": gm, "hmm_seeds_off": hmm_off["median16"]},
               "held": abs(mc - dc) <= 1 and 0.97 <= gm <= 1.03 and hmm_off["median16"] >= 1}
    P["P7"] = {"value": {a: funnel[a]["max_abs_z"] for a in ARMS},
               "held": all(funnel[a]["all_abs_z_le_2"] for a in ARMS)}
    higher = [m for m in models if per_model[m][b]["start_log_density_median"] is not None
              and per_model[m]["default"]["start_log_density_median"] is not None
              and per_model[m][b]["start_log_density_median"] > per_model[m]["default"]["start_log_density_median"]]
    P["P8"] = {"value": f"{len(higher)}/{len(models)} models", "held": len(higher) == len(models)}
    P["P9"] = {"value": {a: decisions[a]["qualifies"] for a in RULE_ARMS},
               "held": decisions[b]["qualifies"] and not decisions["median16"]["qualifies"]}
    summary = {
        "schema": "init-rule-v1-summary", "arms": arms, "decisions": decisions,
        "recommendation": recommendation, "lotteries": lotteries, "funnel": funnel,
        "predictions": P, "per_model": per_model,
    }
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    write_table(summary, cells, models)


def write_table(summary: dict, cells: dict, models: list[str]) -> None:
    L = ["# init_rule_v1 results", "", "Generated by `run_init.py analyze`. Gradients include every init evaluation. "
         "Walls are contended and not reported here.", "", "## Arms", "",
         "| arm | ok | raw passes | credited passes | hidden-mode | R-hat failures | init evals | geomean ESS/grad vs default | qualifies |",
         "|---|---|---|---|---|---|---|---|---|"]
    for a in ARMS:
        x = summary["arms"][a]
        d = summary["decisions"].get(a, {})
        g = d.get("geomean_ess_per_gradient_ratio")
        L.append(f"| {a} | {x['ok']}/{x['cells_expected']} | {x['raw_passes']} | {x['credited_passes']} | "
                 f"{len(x['hidden_mode_cells'])} | {x['rhat_failures']} | {x['init_evaluations_total']} | "
                 f"{'1 (reference)' if a == 'default' else f'{g:.4f}'} | {d.get('qualifies', '-')} |")
    L += ["", f"**Recommendation (mechanical):** {summary['recommendation']}", "", "## Decision clauses", ""]
    for a, d in summary["decisions"].items():
        L.append(f"- `{a}`: D1 {d['D1_credited_gates_ge_default']} ({d['credited_passes']} vs {d['default_credited_passes']}), "
                 f"D2 {d['D2_zero_hidden_mode']} ({d['hidden_mode_cells']}), D3 {d['D3_geomean_ratio_ge_0_97']} "
                 f"({d['geomean_ess_per_gradient_ratio']:.4f}), D4 {d['D4_funnel_abs_z_le_2_every_seed']} (max |z| {d['funnel_max_abs_z']})")
    L += ["", "## Every cell", "",
          "| model | seed | arm | status | R-hat | min bulk | min tail | div | max abs dmean/sd | disagreeing (Rust LOO) | chains off ref | start logp (per chain) | init evals | bulk ESS/grad | pass | hidden |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in models:
        for s in SEEDS:
            for a in ARMS:
                c = cells.get(m, {}).get(a, {}).get(s)
                if not c:
                    L.append(f"| {m} | {s} | {a} | missing | | | | | | | | | | | | |")
                    continue
                if c["status"] != "ok":
                    L.append(f"| {m} | {s} | {a} | {c['status']} | | | | | | | | | {c.get('init_evaluations')} | | False | |")
                    continue
                sl = ", ".join(f"{x:.4g}" for x in c["start_log_densities"])
                L.append(f"| {m} | {s} | {a} | ok | {c['max_rank_rhat']:.4f} | {c['min_bulk_ess']:.0f} | {c['min_tail_ess']:.0f} | "
                         f"{c['divergences']} | {c['max_abs_dmean_over_ref_sd']:.2f} | {c['disagreeing_chains']} | {c['chains_off_reference']} | "
                         f"{sl} | {c['init_evaluations']} | {c['min_bulk_ess_per_gradient']:.3e} | {c['passed']} | {c['hidden_mode']} |")
    L += ["", "## Per-model ESS/gradient ratio vs default (paired seeds, geomean)", "", "| model | " + " | ".join(RULE_ARMS) + " |", "|---|" + "---|" * len(RULE_ARMS)]
    for m in models:
        L.append(f"| {m} | " + " | ".join(f"{summary['per_model'][m][a]['ess_per_gradient_ratio_vs_default']:.3f}"
                                         if summary['per_model'][m][a]['ess_per_gradient_ratio_vs_default'] else "-" for a in RULE_ARMS) + " |")
    L += ["", "## Funnel (P(omega < -5), exact 0.0478)", "", "| arm | seed | estimate | MCSE z | batch z | omega bulk ESS | omega R-hat | div | start omegas |", "|---|---|---|---|---|---|---|---|---|"]
    for a, f in summary["funnel"].items():
        for s, p in f["per_seed"].items():
            if p is None:
                L.append(f"| {a} | {s} | missing | | | | | | |")
                continue
            L.append(f"| {a} | {s} | {p['estimate']:.4f} | {p['z']:+.2f} | {p['z_batch_means']:+.2f} | {p['omega_bulk_ess']:.0f} | "
                     f"{p['omega_rhat']:.3f} | {p['divergences']} | {', '.join(f'{w:.2f}' for w in p['start_omegas'])} |")
    L += ["", "## Predictions", "", "| prediction | value | held |", "|---|---|---|"]
    for k, v in summary["predictions"].items():
        L.append(f"| {k} | {v['value']} | {v['held']} |")
    (ART / "results-table.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:20]))


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] == "run":
        run_all()
    elif args[0] == "model":
        run_model(args[1])
    elif args[0] == "funnel":
        run_funnel()
    elif args[0] == "analyze":
        analyze()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
