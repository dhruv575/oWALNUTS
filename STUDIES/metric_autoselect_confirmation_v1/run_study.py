#!/usr/bin/env python3
"""WP85 driver: default-flip confirmation of WP79's Hessian-fit dense / diagonal auto-selection (22 v7 posteriors x 6 seeds).

    python3 run_study.py prepare        # posteriordb models -> models/*.stan, *.data.json, BridgeStan *_model.so
    python3 run_study.py run P          # posteriordb, 17 house models x 3 seeds x {diag, dense, auto} x 4 x 1,000/1,000
    python3 run_study.py run F          # funnel sanity arm, 10 seeds x {diag, dense, auto} x 4 x 2,000/20,000
    python3 run_study.py analyze        # artifacts/summary.json + artifacts/results-table.md

Arms in one build (target/release/*, owalnuts with the `research` feature): `diag` = Sampler defaults (diagonal);
`dense` = Metric::dense(); `auto` = default (diagonal) metric + Adaptation::Custom(sampler warmup defaults +
with_dense_auto_select(DenseAutoSelectConfig::hessian_fit(2, 5.0, 0.5))). Calibration: calibrate.py (WP75 records).
On the shared box every call is wrapped in `taskset -c 8-11`; children inherit it.
Funnel statistics are WP66's; posteriordb cell metrics are v7's (via WP68's / WP71's driver), reading posteriordb files directly.
Never rerun a cell; an errored or timed-out cell is a failed cell.
"""
from __future__ import annotations

import io
import json
import math
import os
import statistics
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
ART = Path(os.environ.get("WP85_ARTIFACTS", HERE / "artifacts"))  # override only for the non-evidence pipeline check
CELLS = ART / "cells"
DRAWS = Path(os.environ.get("WP85_DRAWS", HERE / "draws"))  # unconstrained draws; not committed (hash manifest is)
MODELS = Path(os.environ.get("WP85_MODELS", HERE / "models"))
PDB = Path(os.environ.get("WP85_POSTERIORDB", Path.home() / "infra" / "posteriordb" / "posterior_database"))
BRIDGESTAN = Path(os.environ.get("BRIDGESTAN", HERE / "bridgestan"))
EXE = ".exe" if os.name == "nt" else ""
BIN = HERE / "target" / "release"
ARMS = ["diag", "auto"]
SEEDS = PROTOCOL["seeds"]
BLOCKS = PROTOCOL["blocks"]
HOUSE = PROTOCOL["models"]
GATES_ONLY = set(PROTOCOL["gates_only_models"])
GATES = PROTOCOL["gates"]
TIMEOUT = PROTOCOL["cell_timeout_seconds"]
THRESHOLD = PROTOCOL["selection"]["threshold"]
EXACT_P5 = 0.0477903522728147


def branch_of(cell: dict) -> str:
    d = cell.get("auto_decision")
    if not d:
        return "-"
    return "dense" if d.get("chose_dense") else "diag"

def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    ART.mkdir(parents=True, exist_ok=True)
    with (ART / "run-log.txt").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


# --------------------------------------------------------------------------- posteriordb (files read directly)


def pdb_json(rel: str):
    p = PDB / rel
    if p.suffix == ".zip":
        with zipfile.ZipFile(p) as z:
            return json.loads(z.read(z.namelist()[0]).decode("utf-8"))
    return json.loads(p.read_text(encoding="utf-8"))


def posterior_info(model: str) -> dict:
    return pdb_json(f"posteriors/{model}.json")


def prepare() -> None:
    MODELS.mkdir(parents=True, exist_ok=True)
    targets = []
    for model in HOUSE:
        info = posterior_info(model)
        stan = (PDB / "models" / "stan" / f"{info['model_name']}.stan").read_text(encoding="utf-8")
        data = pdb_json(f"data/data/{info['data_name']}.json.zip")
        (MODELS / f"{model}.stan").write_text(stan, encoding="utf-8")
        (MODELS / f"{model}.data.json").write_text(json.dumps(data), encoding="utf-8")
        if not (MODELS / f"{model}_model.so").exists():
            targets.append(str((MODELS / f"{model}_model.so").resolve()))
    log(f"prepare: {len(HOUSE)} models written, {len(targets)} to compile with BridgeStan at {BRIDGESTAN}")
    for t in targets:  # one model at a time, make -j2 inside: stays under the lane's 6 GB
        t0 = time.time()
        cp = subprocess.run(["make", "-j2", "-C", str(BRIDGESTAN), t], capture_output=True, text=True)
        log(f"compile {Path(t).name}: exit {cp.returncode} in {time.time() - t0:.0f}s {cp.stderr.strip()[-300:] if cp.returncode else ''}")


def reference(model: str) -> dict:
    ref = pdb_json(f"reference_posteriors/draws/draws/{posterior_info(model)['reference_posterior_name']}.json.zip")
    import numpy as np

    names = list(ref[0].keys())
    arr = np.asarray([[c[n] for n in names] for c in ref], dtype=np.float64)  # (chains, P, draws)
    arr = np.transpose(arr, (0, 2, 1))
    return {"names": names, **arviz_stats(arr)}


def arviz_stats(arr) -> dict:
    import arviz as az
    import numpy as np

    ds = az.convert_to_dataset({"p": arr})
    with np.errstate(all="ignore"):
        bulk = np.asarray(az.ess(ds, method="bulk").p.values, dtype=float)
        tail = np.asarray(az.ess(ds, method="tail", prob=(0.05, 0.95)).p.values, dtype=float)
        rhat = np.asarray(az.rhat(ds, method="rank").p.values, dtype=float)
        mcse = np.asarray(az.mcse(ds, method="mean").p.values, dtype=float)
    flat = arr.reshape(-1, arr.shape[-1])
    return {"mean": flat.mean(0), "sd": flat.std(0, ddof=1), "bulk_ess": bulk, "tail_ess": tail, "rhat": rhat, "mcse": mcse}


def bridgestan_name(name: str) -> str:
    parts = name.split(".")
    if len(parts) == 1 or not all(p.isdigit() for p in parts[1:]):
        return name
    return f"{parts[0]}[{','.join(parts[1:])}]"


_SM: dict = {}


def stan_model(model: str):
    if model not in _SM:
        import bridgestan as bs

        _SM[model] = bs.StanModel(str(MODELS / f"{model}_model.so"),
                                  data=(MODELS / f"{model}.data.json").read_text(encoding="utf-8"), seed=1)
    return _SM[model]


# --------------------------------------------------------------------------- cells


def cell_path(block: str, arm: str, seed: int, model: str | None = None) -> Path:
    mid = f"{model}-{arm}" if model else arm
    return CELLS / f"{block}-{mid}-{seed}.json"


def run_funnel_cell(block: str, arm: str, seed: int) -> None:
    spec = BLOCKS[block]
    out = cell_path(block, arm, seed)
    err = out.with_suffix(".error.json")
    if out.exists() or err.exists():
        return
    CELLS.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    cmd = [str(BIN / f"funnel{EXE}"), arm, str(spec["warmup"]), str(spec["draws"]), str(seed), str(out)]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
        rc, stderr = cp.returncode, cp.stderr
    except subprocess.TimeoutExpired:
        rc, stderr = "timeout", f"exceeded {TIMEOUT}s"
    log(f"{block} [{time.time() - t0:.1f}s] {stderr.strip()[-400:]}")
    if rc != 0 or not out.exists():
        err.write_text(json.dumps({"block": block, "arm": arm, "seed": seed, "status": "error", "returncode": rc,
                                   "stderr": stderr[-4000:]}, indent=1) + "\n", encoding="utf-8")


def failure(model, arm, seed, status, message, **extra) -> dict:
    return {"model": model, "arm": arm, "seed": seed, "status": status, "error": message, "passed": False,
            "gates": {"no_sampler_error": False}, **extra}


def run_pdb_cell(model: str, arm: str, seed: int) -> None:
    import numpy as np

    out = cell_path("P", arm, seed, model)
    if out.exists():
        return
    DRAWS.mkdir(parents=True, exist_ok=True)
    raw = DRAWS / f"{model}-{arm}-{seed}.raw.json"
    if raw.exists():
        raw.unlink()
    so, data = MODELS / f"{model}_model.so", MODELS / f"{model}.data.json"
    cmd = [str(BIN / f"pdb{EXE}"), str(so), str(data), arm, str(seed), str(raw), "4"]
    t0 = time.time()
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        cell = failure(model, arm, seed, "timeout", f"exceeded {TIMEOUT}s")
        return write_cell(out, cell, time.time() - t0)
    if cp.returncode != 0 or not raw.exists():
        cell = failure(model, arm, seed, "error", cp.stderr.strip()[-2000:] or f"exit {cp.returncode}")
        return write_cell(out, cell, time.time() - t0)
    o = json.loads(raw.read_text(encoding="utf-8"))
    if o.get("status") != "ok":
        return write_cell(out, failure(model, arm, seed, "error", o.get("error", "unknown")), time.time() - t0)
    sm = stan_model(model)
    if model in GATES_ONLY:  # v7 / WP46 rule: parameter-block coordinates, no reference, no z
        ref = None
        names = [bridgestan_name(n) for n in sm.param_names(include_tp=False, include_gq=False)]
    else:
        ref = reference(model)
        names = ref["names"]
    cnames = [bridgestan_name(n) for n in sm.param_names(include_tp=True, include_gq=False)]
    unc = np.asarray([c["samples"] for c in o["chains_data"]], dtype=np.float64)
    con = np.empty(unc.shape[:2] + (len(cnames),))
    for c in range(unc.shape[0]):
        for d in range(unc.shape[1]):
            con[c, d] = sm.param_constrain(unc[c, d], include_tp=True, include_gq=False)
    index = {n: i for i, n in enumerate(cnames)}
    missing = [n for n in names if n not in index]
    if missing:
        return write_cell(out, failure(model, arm, seed, "error", f"gate parameters missing: {missing[:5]}"), time.time() - t0)
    draws = con[:, :, [index[n] for n in names]]
    st = arviz_stats(draws)
    chains = o["chains_data"]
    divergences = sum(c["divergences"] for c in chains)
    grads = o["target_calls_total"]
    min_bulk, min_tail, max_rhat = float(np.nanmin(st["bulk_ess"])), float(np.nanmin(st["tail_ess"])), float(np.nanmax(st["rhat"]))
    gates = {"max_rank_rhat": max_rhat <= GATES["max_rank_rhat"], "min_bulk_ess": min_bulk >= GATES["min_bulk_ess"],
             "min_tail_ess": min_tail >= GATES["min_tail_ess"], "sampling_divergences": divergences == 0,
             "finite_draws": bool(np.isfinite(draws).all()), "no_sampler_error": True}
    z = ((st["mean"] - ref["mean"]) / np.sqrt(st["mcse"] ** 2 + ref["mcse"] ** 2)) if ref is not None else np.full(len(names), np.nan)
    cell = {
        "schema": "metric-autoselect-confirmation-v1-pdb-metrics", "model": model, "arm": arm, "seed": seed, "status": "ok",
        "wall_seconds_pinned_cotenanted": o["wall_seconds"], "gradients_total": grads,
        "gradients_sampling": sum(c["retained_target_calls"] for c in chains),
        "divergences": divergences, "max_depth_stops": sum(c["maximum_depth_stops"] for c in chains),
        "min_bulk_ess": min_bulk, "min_tail_ess": min_tail, "max_rank_rhat": max_rhat,
        "argmin_bulk_ess": names[int(np.nanargmin(st["bulk_ess"]))],
        "min_bulk_ess_per_gradient": min_bulk / grads, "min_tail_ess_per_gradient": min_tail / grads,
        "max_abs_z": float(np.nanmax(np.abs(z))) if ref is not None else None,
        "argmax_abs_z": names[int(np.nanargmax(np.abs(z)))] if ref is not None else None, "tier": "reference" if ref is not None else "gates_only",
        "gates": gates, "passed": all(gates.values()),
        "draws_fnv": [c["draws_fnv"] for c in chains],
        "gradients_warmup": sum(c["warmup_target_calls"] for c in chains),
        "gradients_start_search": o["init"]["start_search_calls"],
        "warmup_gradient_share": sum(c["warmup_target_calls"] for c in chains) / grads,
        "metric_updates": [[{k: u.get(k) for k in ("window_index", "sample_count", "outcome", "step_before", "step_after_restart",
                                                    "dense_offdiag_max")} for u in c["metric_updates"]] for c in chains],
        "auto_decision": chains[0].get("dense_auto_select"),
        "auto_decision_identical_across_chains": len({json.dumps(c.get("dense_auto_select"), sort_keys=True) for c in chains}) == 1,
        "final_metric_dense": [bool((c["metric_updates"][-1].get("dense_offdiag_max") or 0) > 0) if c["metric_updates"] else None for c in chains],
        "arm_adaptation": o["defaults"].get("arm_adaptation"),
        "exhaustion_stops_all_transitions": sum(c["all_transitions_exhaustion_stops"] for c in chains),
        "retained_exhaustions": sum(c["refinement_exhaustions"] for c in chains),
        "warmup_divergences": sum(c["warmup_divergences"] for c in chains),
        "final_step_size": [c["final_step_size"] for c in chains],
        "retained_refinement_level_histogram": [sum(x) for x in zip(*(c["retained_refinement_level_histogram"] for c in chains))],
        "tuning": o["tuning"], "defaults": o["defaults"], "init": o["init"]["detail"].get("rule"),
        "chain_warnings": o.get("chain_warnings", []), "algorithm_revision": o["algorithm_revision"],
        "dimension": o["dimension"], "execution": o.get("execution"), "replicas": o.get("replicas"),
        "parameters": {n: {"mean": float(st["mean"][i]), "bulk_ess": float(st["bulk_ess"][i]), "tail_ess": float(st["tail_ess"][i]),
                           "rhat": float(st["rhat"][i]), "z": float(z[i])} for i, n in enumerate(names)},
    }
    np.savez_compressed(DRAWS / f"{model}-{arm}-{seed}.npz", unconstrained=unc, constrained=draws, names=np.asarray(names))
    raw.unlink()
    write_cell(out, cell, time.time() - t0)


def write_cell(path: Path, cell: dict, seconds: float) -> None:
    CELLS.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cell, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if cell["status"] == "ok":
        log(f"P {cell['model']} {cell['arm']} {cell['seed']} [{seconds:.1f}s]: grads {cell['gradients_total']} minbulk {cell['min_bulk_ess']:.0f} "
            f"mintail {cell['min_tail_ess']:.0f} rhat {cell['max_rank_rhat']:.4f} div {cell['divergences']} |z| {cell['max_abs_z'] if cell['max_abs_z'] is None else round(cell['max_abs_z'], 2)} "
            f"passed {cell['passed']} warmup-share {cell['warmup_gradient_share']:.3f} "
            f"branch {branch_of(cell)} G {((cell.get('auto_decision') or {}).get('statistic') or float('nan')):.3g} "
            f"GH {((cell.get('auto_decision') or {}).get('hessian_gain') or float('nan')):.3g} lin {((cell.get('auto_decision') or {}).get('linearity') or float('nan')):.3g} "
            f"exh {cell['exhaustion_stops_all_transitions']} fnv {cell['draws_fnv'][0]}")
    else:
        log(f"P {cell['model']} {cell['arm']} {cell['seed']} [{seconds:.1f}s]: {cell['status']}: {cell.get('error', '')[:300]}")


def run(block: str) -> None:
    log(f"block {block} start (pid {os.getpid()}, affinity {sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else 'n/a'})")
    spec = BLOCKS[block]
    if spec["kind"] == "funnel":
        for seed in SEEDS[spec["seeds"]]:
            for arm in spec["arms"]:
                run_funnel_cell(block, arm, seed)
    else:
        for model in HOUSE:
            for seed in SEEDS[spec["seeds"]]:
                for arm in spec["arms"]:
                    run_pdb_cell(model, arm, seed)
    log(f"block {block} complete")




# --------------------------------------------------------------------------- analysis


def geomean(xs):
    return math.exp(statistics.fmean(math.log(x) for x in xs))


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def abranch(c) -> str:
    """Auto-arm branch; 'diag-cap' when no decision was made (dimension above DenseMass::MAX_DIMENSION)."""
    if not ok(c):
        return "error"
    b = branch_of(c)
    return "diag-cap" if b == "-" else b


def ok(c):
    return bool(c) and c.get("status") == "ok"


def funnel_arm(arm: str) -> dict | None:
    cs = {s: load(cell_path("F", arm, s)) for s in SEEDS["F"]}
    cs = {s: c for s, c in cs.items() if c}
    if not cs:
        return None
    est = [c["tail_mass"]["estimate"] for c in cs.values()]
    p5 = statistics.fmean(est)
    se = statistics.stdev(est) / math.sqrt(len(est)) if len(est) > 1 else float("nan")
    return {"cells": len(cs), "errors": [s for s in SEEDS["F"] if s not in cs], "pooled_p5": p5, "se_p5": se,
            "abs_error": abs(p5 - EXACT_P5), "within_1se": abs(p5 - EXACT_P5) <= se,
            "divergences": sum(ch["divergences"] for c in cs.values() for ch in c["chains_data"]),
            "dense_seeds": sum(bool((c["chains_data"][0].get("dense_auto_select") or {}).get("chose_dense")) for c in cs.values()),
            "median_wall_per_gradient": statistics.median(c["wall_seconds_pinned_cotenanted"] / c["target_calls_total"] for c in cs.values()
                                                          if c.get("wall_seconds_pinned_cotenanted") and c.get("target_calls_total"))}


def pdb_cells() -> dict:
    return {arm: {(m, s): load(cell_path("P", arm, s, m)) for m in HOUSE for s in SEEDS["P"]} for arm in ARMS}


def trapped(c) -> bool:
    """A cell with a trapped chain: max rank R-hat above 1.1 (WP75's lotka_volterra stuck chain was 1.53)."""
    return ok(c) and c["max_rank_rhat"] > 1.1


def analyze(env: dict) -> None:
    import numpy as np  # noqa: F401

    pc = pdb_cells()
    seeds = SEEDS["P"]
    need = math.ceil(5 * len(seeds) / 6)
    per_model, headline, wall_ratios = {}, {}, {}
    new_div, below, overhead = [], [], []
    ident_checked, ident_failed = [], []
    for m in HOUSE:
        d = [pc["diag"][(m, s)] for s in seeds]
        a = [pc["auto"][(m, s)] for s in seeds]
        paired = [x["min_bulk_ess_per_gradient"] and y["min_bulk_ess_per_gradient"] / x["min_bulk_ess_per_gradient"]
                  for x, y in zip(d, a) if ok(x) and ok(y) and x["min_bulk_ess_per_gradient"] > 0]
        branches = [abranch(y) for y in a]
        if len(paired) >= need:
            headline[m] = statistics.median(paired)
        wp = [(y["wall_seconds_pinned_cotenanted"] / y["gradients_total"]) / (x["wall_seconds_pinned_cotenanted"] / x["gradients_total"])
              for x, y in zip(d, a) if ok(x) and ok(y)]
        if wp:
            wall_ratios[m] = statistics.median(wp)
        for s, x, y in zip(seeds, d, a):
            if abranch(y) in ("diag", "diag-cap"):
                ident_checked.append(f"P:{m}:{s}")
                if not (ok(x) and x["draws_fnv"] == y["draws_fnv"] and x["gradients_total"] == y["gradients_total"]):
                    ident_failed.append(f"P:{m}:{s}")
            if ok(x) and ok(y) and abranch(y) == "dense":
                overhead.append({"model": m, "seed": s, "warmup_gradient_ratio": y["gradients_warmup"] / x["gradients_warmup"]})
        dd = sum(x.get("divergences", 0) for x in d if x)
        da = sum(y.get("divergences", 0) for y in a if y)
        if da > dd:
            new_div.append(m)
        if m not in headline or headline[m] < 0.9:
            below.append(m)
        per_model[m] = {"passes_diag": sum(bool(x and x.get("passed")) for x in d), "passes_auto": sum(bool(y and y.get("passed")) for y in a),
                        "branches": branches, "branch_consistent": len(set(branches)) == 1 and branches[0] != "error",
                        "paired_ratios": paired, "headline_ratio": headline.get(m), "divergences_diag": dd, "divergences_auto": da,
                        "trapped_cells_diag": sum(trapped(x) for x in d), "trapped_cells_auto": sum(trapped(y) for y in a),
                        "hessian_gain": [((y or {}).get("auto_decision") or {}).get("hessian_gain") for y in a],
                        "linearity": [((y or {}).get("auto_decision") or {}).get("linearity") for y in a],
                        "max_abs_z_passing_auto": max([y["max_abs_z"] for y in a if ok(y) and y["passed"] and y.get("max_abs_z") is not None], default=None),
                        "max_abs_z_passing_diag": max([x["max_abs_z"] for x in d if ok(x) and x["passed"] and x.get("max_abs_z") is not None], default=None),
                        "wall_per_gradient_ratio": wall_ratios.get(m)}
    for s in SEEDS["F"]:
        a, d = load(cell_path("F", "auto", s)), load(cell_path("F", "diag", s))
        if a and not (a["chains_data"][0].get("dense_auto_select") or {}).get("chose_dense", True):
            ident_checked.append(f"F:{s}")
            if not (d and a.get("draws_fnv") is not None and (a["draws_fnv"], a["target_calls_total"]) == (d["draws_fnv"], d["target_calls_total"])):
                ident_failed.append(f"F:{s}")
    passes = {arm: sum(bool(c and c.get("passed")) for c in pc[arm].values()) for arm in ARMS}
    hz = [v["max_abs_z_passing_auto"] for v in per_model.values() if v["max_abs_z_passing_auto"] is not None]
    consistent = sum(v["branch_consistent"] for v in per_model.values())
    lv = per_model["hudson_lynx_hare-lotka_volterra"]
    F = {arm: funnel_arm(arm) for arm in ARMS}
    fa = F["auto"]
    rules = {
        "R1_passes": {"diag": passes["diag"], "auto": passes["auto"], "cells": len(HOUSE) * len(seeds), "held": passes["auto"] >= passes["diag"]},
        "R2_headline_ge_1.5": {"value": geomean(list(headline.values())) if headline else None, "models": len(headline),
                               "held": bool(headline) and geomean(list(headline.values())) >= 1.5},
        "R3_no_model_below_0.9": {"models_below": below, "held": not below},
        "R4_no_new_divergences": {"models": new_div, "held": not new_div},
        "R5_max_abs_z_passing_reference_le_4": {"max": max(hz) if hz else None, "held": bool(hz) and max(hz) <= 4},
        "R6_diag_branch_bit_identical": {"cells": len(ident_checked), "not_identical": ident_failed, "held": bool(ident_checked) and not ident_failed},
        "R7_branch_consistent_ge_20_of_22": {"consistent": consistent, "inconsistent": [m for m, v in per_model.items() if not v["branch_consistent"]],
                                              "held": consistent >= 20},
        "R8_funnel_p5_within_1se": ({"pooled": fa["pooled_p5"], "se": fa["se_p5"], "dense_seeds": fa["dense_seeds"],
                                     "identical_to_diag_by_construction": True, "held": fa["within_1se"]} if fa else {"held": False}),
        "R9_lotka_trapped_not_higher": {"diag": lv["trapped_cells_diag"], "auto": lv["trapped_cells_auto"], "held": lv["trapped_cells_auto"] <= lv["trapped_cells_diag"]},
    }
    D = bool(env.get("library_diff_scoped") and env.get("kernel_fingerprint_test_passed") and env.get("autoselect_tests_passed"))
    rules["D_integrity"] = {k: env.get(k) for k in ("library_diff_scoped", "kernel_fingerprint_test_passed", "autoselect_tests_passed")} | {"held": D}
    failed = [k.split("_")[0] for k, r in rules.items() if not r["held"]]
    verdict = "FLIP QUALIFIES: every preregistered rule holds" if not failed else "FLIP DOES NOT QUALIFY (failed: " + ", ".join(failed) + ")"
    pred = PROTOCOL["predicted_branch"]
    runs = [(m, b) for m, v in per_model.items() for b in v["branches"]]
    reported = {
        "wall_per_gradient_auto_over_diag_geomean": geomean(list(wall_ratios.values())) if wall_ratios else None,
        "wall_per_gradient_by_branch": {"diag": geomean([wall_ratios[m] for m, v in per_model.items() if m in wall_ratios and set(v["branches"]) <= {"diag", "diag-cap"}] or [1.0]),
                                        "dense": geomean([wall_ratios[m] for m, v in per_model.items() if m in wall_ratios and set(v["branches"]) == {"dense"}] or [1.0])},
        "funnel_wall_per_gradient_auto_over_diag": (F["auto"]["median_wall_per_gradient"] / F["diag"]["median_wall_per_gradient"]) if F["auto"] and F["diag"] else None,
        "dense_branch_warmup_gradient_ratio_median": statistics.median([o["warmup_gradient_ratio"] for o in overhead]) if overhead else None,
        "dense_branch_cells": len(overhead),
        "branch_matches_prediction": sum(b == pred[m] for m, b in runs), "runs": len(runs),
        "passes_by_model": {m: (v["passes_diag"], v["passes_auto"]) for m, v in per_model.items()},
    }
    summary = {"schema": "metric-autoselect-confirmation-v1-summary", "ledger_id": "WP85", "environment": env, "decision_rules": rules,
               "verdict": verdict, "reported": reported, "funnel": F, "per_model": per_model, "dense_branch_overhead": overhead}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n", encoding="utf-8")
    L = [f"# WP85 results (generated by `run_study.py analyze`)", "", f"Verdict: {verdict}", "",
         "| model | branches (6 seeds) | pass diag / auto | headline auto/diag | div diag / auto | trapped diag / auto | max abs z passing auto | wall/grad ratio |",
         "|---|---|---|---:|---|---|---:|---:|"]
    f = lambda x, sp=".3g": "-" if x is None else format(x, sp)  # noqa: E731
    for m, v in per_model.items():
        L.append(f"| {m} | {' '.join(v['branches'])} | {v['passes_diag']} / {v['passes_auto']} | {f(v['headline_ratio'], '.2f')} | "
                 f"{v['divergences_diag']} / {v['divergences_auto']} | {v['trapped_cells_diag']} / {v['trapped_cells_auto']} | "
                 f"{f(v['max_abs_z_passing_auto'], '.2f')} | {f(v['wall_per_gradient_ratio'], '.3f')} |")
    L += ["", "```json", json.dumps({"rules": rules, "reported": reported}, indent=1, default=str), "```", ""]
    (ART / "results-table.md").write_text("\n".join(L), encoding="utf-8")
    print(json.dumps({"verdict": verdict, "rules": rules, "reported": reported}, indent=1, default=str))


if __name__ == "__main__":
    cmd = sys.argv[1:]
    if cmd == ["prepare"]:
        prepare()
    elif cmd[:1] == ["run"] and len(cmd) == 2 and cmd[1] in BLOCKS:
        run(cmd[1])
    elif cmd == ["analyze"]:
        env = load(ART / "environment.json") or {}
        analyze(env)
    else:
        sys.exit(__doc__)
