#!/usr/bin/env python3
"""WP67 driver: is ten refinement levels a safe sampler default?

    python3 run_study.py prepare        # posteriordb models -> models/*.stan, *.data.json, BridgeStan *_model.so
    python3 run_study.py run F          # funnel, 30 seeds x {default, levels10} x 4 x 2,000/20,000
    python3 run_study.py run P          # posteriordb, 17 house models x 3 seeds x {default, levels10} x 4 x 1,000/1,000
    python3 run_study.py run L          # descriptive: default funnel, 30 seeds x 4 x 2,000/80,000
    python3 run_study.py analyze        # artifacts/summary.json + artifacts/results-table.md

Arms are builds of the same harness source: target/release/* (plain, eight levels) and
target-levels10/release/* (`--features levels10`, the library's study-only `candidate-levels10`).
On the shared box every call is wrapped in `taskset -c 8-11`; children inherit it.
Funnel statistics are WP66's (`STUDIES/funnel_tail_deficit_v1/run_study.py`); posteriordb cell metrics are
v7's (`STUDIES/posteriordb_bench_v7/run_posteriordb.py`, `metrics`), reading posteriordb files directly.
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
ART = HERE / "artifacts"
CELLS = ART / "cells"
DRAWS = Path(os.environ.get("WP67_DRAWS", HERE / "draws"))  # unconstrained draws; not committed (hash manifest is)
MODELS = Path(os.environ.get("WP67_MODELS", HERE / "models"))
PDB = Path(os.environ.get("WP67_POSTERIORDB", Path.home() / "infra" / "posteriordb" / "posterior_database"))
BRIDGESTAN = Path(os.environ.get("BRIDGESTAN", HERE / "bridgestan"))
EXE = ".exe" if os.name == "nt" else ""
BIN = {"default": HERE / "target" / "release", "levels10": HERE / "target-levels10" / "release"}
ARMS = ["default", "levels10"]
SEEDS = PROTOCOL["seeds"]
BLOCKS = PROTOCOL["blocks"]
HOUSE = PROTOCOL["house_models"]
GATES = PROTOCOL["gates"]
TIMEOUT = PROTOCOL["cell_timeout_seconds"]
EXACT_P5 = 0.0477903522728147
P_EXCEED = 2 * (1 - 0.5 * (1 + math.erf(2 / math.sqrt(2))))


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
    t0 = time.time()
    cmd = [str(BIN[arm] / f"funnel{EXE}"), arm, str(spec["warmup"]), str(spec["draws"]), str(seed), str(out)]
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
    cmd = [str(BIN[arm] / f"pdb{EXE}"), str(so), str(data), arm, str(seed), str(raw), "4"]
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
    ref = reference(model)
    names = ref["names"]
    sm = stan_model(model)
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
    z = (st["mean"] - ref["mean"]) / np.sqrt(st["mcse"] ** 2 + ref["mcse"] ** 2)
    cell = {
        "schema": "refinement-levels10-v1-pdb-metrics", "model": model, "arm": arm, "seed": seed, "status": "ok",
        "wall_seconds_pinned_cotenanted": o["wall_seconds"], "gradients_total": grads,
        "gradients_sampling": sum(c["retained_target_calls"] for c in chains),
        "divergences": divergences, "max_depth_stops": sum(c["maximum_depth_stops"] for c in chains),
        "min_bulk_ess": min_bulk, "min_tail_ess": min_tail, "max_rank_rhat": max_rhat,
        "argmin_bulk_ess": names[int(np.nanargmin(st["bulk_ess"]))],
        "min_bulk_ess_per_gradient": min_bulk / grads, "min_tail_ess_per_gradient": min_tail / grads,
        "max_abs_z": float(np.nanmax(np.abs(z))), "argmax_abs_z": names[int(np.nanargmax(np.abs(z)))],
        "gates": gates, "passed": all(gates.values()),
        "draws_fnv": [c["draws_fnv"] for c in chains],
        "level7_selected_all_transitions": sum(c["all_transitions_level7_selected"] for c in chains),
        "level8_plus_selected_all_transitions": sum(c["all_transitions_level8_plus_selected"] for c in chains),
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
            f"mintail {cell['min_tail_ess']:.0f} rhat {cell['max_rank_rhat']:.4f} div {cell['divergences']} |z| {cell['max_abs_z']:.2f} "
            f"passed {cell['passed']} L7 {cell['level7_selected_all_transitions']} L8+ {cell['level8_plus_selected_all_transitions']} "
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


def mean_se(xs):
    return statistics.fmean(xs), (statistics.stdev(xs) / math.sqrt(len(xs)) if len(xs) > 1 else float("nan"))


def geomean(xs):
    return math.exp(statistics.fmean(math.log(x) for x in xs))


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def funnel_arm(block: str, arm: str) -> dict | None:
    cells, errors = {}, []
    for seed in SEEDS[BLOCKS[block]["seeds"]]:
        c = load(cell_path(block, arm, seed))
        if c is not None:
            cells[seed] = c
        elif cell_path(block, arm, seed).with_suffix(".error.json").exists():
            errors.append(seed)
    if not cells:
        return None
    cs = list(cells.values())
    est = [c["tail_mass"]["estimate"] for c in cs]
    z = [c["tail_mass"]["z"] for c in cs]
    p5, se = mean_se(est)
    up, upse = mean_se([c["upper_tail_profile"][4]["estimate"] for c in cs])
    div = sum(ch["divergences"] for c in cs for ch in c["chains_data"])
    deep = [c["retained_classes"]["deep"] for c in cs]
    return {
        "cells": len(cs), "errors": errors, "pooled_p5": p5, "se_p5": se, "t_p5": (p5 - EXACT_P5) / se,
        "pooled_upper_p5": up, "se_upper_p5": upse, "prefix_pooled_p5": statistics.fmean(c["tail_mass"]["prefix_estimate"] for c in cs),
        "mean_z": statistics.fmean(z), "sd_z": statistics.stdev(z) if len(z) > 1 else None, "exceed": sum(abs(v) > 2 for v in z) + len(errors),
        "divergences": div, "divergence_free_seeds": sum(sum(ch["divergences"] for ch in c["chains_data"]) == 0 for c in cs),
        "exhaustions": sum(ch["refinement_exhaustions"] for c in cs for ch in c["chains_data"]),
        "warmup_exhaustion_stops": sum(ch["warmup_exhaustion_stops"] for c in cs for ch in c["chains_data"]),
        "depth_caps": sum(ch["depth_caps"] for c in cs for ch in c["chains_data"]),
        "median_omega_tail_ess": statistics.median(c["omega"]["tail_ess"] for c in cs),
        "median_omega_bulk_ess": statistics.median(c["omega"]["bulk_ess"] for c in cs),
        "geomean_min_bulk_ess_per_gradient": geomean([c["min_bulk_ess_per_gradient"] for c in cs]),
        "median_gradients": statistics.median(c["target_calls_total"] for c in cs),
        "deep_transitions": sum(d["n"] for d in deep), "deep_top_level": sum(d["top_level_selected"] for d in deep),
        "deep_exhaust_stops": sum(d["stops"]["RefinementExhausted"] for d in deep),
        "omega_variance": statistics.fmean(c["omega"]["variance"] for c in cs),
        "max_rhat_max": max(c["max_rhat"] for c in cs),
        "chain_warning_cells": sum(bool(c["chain_warnings"]) for c in cs),
        "per_seed": {str(s): {"p5": c["tail_mass"]["estimate"], "z": c["tail_mass"]["z"], "prefix_p5": c["tail_mass"]["prefix_estimate"],
                              "divergences": sum(ch["divergences"] for ch in c["chains_data"]),
                              "exhaustions": sum(ch["refinement_exhaustions"] for ch in c["chains_data"]),
                              "omega_tail_ess": c["omega"]["tail_ess"], "draws_fnv": c["draws_fnv"],
                              "chain_fnv": [ch["draws_fnv"] for ch in c["chains_data"]],
                              "levels": c["kernel_tuning"]["max_refinement_levels"]} for s, c in cells.items()},
        "algorithm_revisions": sorted({c["algorithm_revision"] for c in cs}),
        "levels": sorted({c["kernel_tuning"]["max_refinement_levels"] for c in cs}),
    }


def paired(a: dict, b: dict, key: str = "p5") -> dict:
    seeds = sorted(set(a["per_seed"]) & set(b["per_seed"]))
    d = [b["per_seed"][s][key] - a["per_seed"][s][key] for s in seeds]
    m, s = mean_se(d)
    return {"n": len(d), "mean_diff": m, "se": s, "t": m / s if s else None}


def pdb_summary() -> dict:
    cells = {arm: {} for arm in ARMS}
    for model in HOUSE:
        for seed in SEEDS[BLOCKS["P"]["seeds"]]:
            for arm in ARMS:
                c = load(cell_path("P", arm, seed, model))
                if c is not None:
                    cells[arm][(model, seed)] = c
    passes = {arm: sum(c["passed"] for c in cells[arm].values()) for arm in ARMS}
    oks = {arm: sum(c["status"] == "ok" for c in cells[arm].values()) for arm in ARMS}
    per_model, ratios, identical, diff_cells = {}, [], 0, []
    for model in HOUSE:
        row = {}
        for arm in ARMS:
            cs = [cells[arm].get((model, s)) for s in SEEDS[BLOCKS["P"]["seeds"]]]
            row[arm] = {"passed": sum(bool(c and c["passed"]) for c in cs), "ok": sum(bool(c and c["status"] == "ok") for c in cs),
                        "median_ess_per_gradient": statistics.median(c["min_bulk_ess_per_gradient"] for c in cs) if all(c and c["status"] == "ok" for c in cs) else None,
                        "divergences": sum(c.get("divergences", 0) for c in cs if c), "max_abs_z": max((c.get("max_abs_z") or 0) for c in cs if c) if any(cs) else None,
                        "level7_all": sum(c.get("level7_selected_all_transitions", 0) for c in cs if c),
                        "level8_plus_all": sum(c.get("level8_plus_selected_all_transitions", 0) for c in cs if c),
                        "exhaustion_stops_all": sum(c.get("exhaustion_stops_all_transitions", 0) for c in cs if c),
                        "median_gradients": statistics.median(c["gradients_total"] for c in cs if c and c["status"] == "ok") if any(c and c["status"] == "ok" for c in cs) else None}
        a, b = row["default"]["median_ess_per_gradient"], row["levels10"]["median_ess_per_gradient"]
        row["ratio"] = b / a if a and b else None
        if row["ratio"]:
            ratios.append(row["ratio"])
        ident = []
        for s in SEEDS[BLOCKS["P"]["seeds"]]:
            x, y = cells["default"].get((model, s)), cells["levels10"].get((model, s))
            same = bool(x and y and x["status"] == "ok" and y["status"] == "ok" and x["draws_fnv"] == y["draws_fnv"])
            ident.append(same)
            identical += same
            if not same:
                diff_cells.append(f"{model}/{s}")
        row["identical_seeds"] = sum(ident)
        per_model[model] = row
    return {"passes": passes, "ok_cells": oks, "cells_per_arm": len(HOUSE) * len(SEEDS[BLOCKS["P"]["seeds"]]),
            "geomean_ratio_levels10_over_default": geomean(ratios) if ratios else None, "models_in_geomean": len(ratios),
            "min_model_ratio": min(ratios) if ratios else None, "identical_cells": identical, "non_identical_cells": diff_cells,
            "per_model": per_model,
            "passing_cells_max_abs_z": {arm: max((c["max_abs_z"] for c in cells[arm].values() if c["passed"]), default=None) for arm in ARMS}}


def analyze(env: dict) -> None:
    F = {arm: funnel_arm("F", arm) for arm in ARMS}
    Lb = funnel_arm("L", "default")
    P = pdb_summary() if any(CELLS.glob("P-*.json")) else None
    rules, preds = {}, {}
    d, t = F["default"], F["levels10"]
    if d and t:
        pr = paired(d, t)
        ident_f = sum(d["per_seed"][s]["draws_fnv"] == t["per_seed"][s]["draws_fnv"] for s in d["per_seed"] if s in t["per_seed"])
        rules["F1_divergences_not_higher"] = {"default": d["divergences"], "levels10": t["divergences"], "held": t["divergences"] <= d["divergences"]}
        rules["F2_p5_within_2se_of_exact"] = {"pooled": t["pooled_p5"], "se": t["se_p5"], "abs_error": abs(t["pooled_p5"] - EXACT_P5),
                                              "held": abs(t["pooled_p5"] - EXACT_P5) <= 2 * t["se_p5"]}
        preds["Fa_divergences_fall_10x"] = {"observed": [d["divergences"], t["divergences"]], "held": t["divergences"] * 10 <= d["divergences"]}
        preds["Fb_p5_unchanged_within_1_paired_se"] = {"observed": pr, "held": abs(pr["mean_diff"]) <= pr["se"]}
        tr = t["median_omega_tail_ess"] / d["median_omega_tail_ess"]
        preds["Fc_tail_ess_ratio_0.9_1.1"] = {"observed": tr, "held": 0.9 <= tr <= 1.1}
        preds["Fd_exhaustions_fall_10x"] = {"observed": [d["exhaustions"], t["exhaustions"]], "held": t["exhaustions"] * 10 <= d["exhaustions"]}
        rules["funnel_paired_p5"] = pr
        rules["funnel_identical_cells"] = ident_f
    if P:
        r1 = P["passes"]["levels10"] >= P["passes"]["default"]
        g = P["geomean_ratio_levels10_over_default"]
        r2 = g is not None and g >= 0.95
        rules["P1_pass_count_not_lower"] = {"default": P["passes"]["default"], "levels10": P["passes"]["levels10"], "held": r1}
        rules["P2_geomean_ess_per_gradient_ge_0.95"] = {"value": g, "models": P["models_in_geomean"], "held": r2}
        preds["Pa_identical_cells_ge_25_of_51"] = {"observed": P["identical_cells"], "held": P["identical_cells"] >= 25}
        preds["Pb_geomean_in_0.97_1.03"] = {"observed": g, "held": g is not None and 0.97 <= g <= 1.03}
    D = bool(env.get("library_default_build_unchanged") and env.get("kernel_fingerprint_test_passed")
             and env.get("feature_test_passed"))
    rules["D_build_integrity"] = {k: env.get(k) for k in ("library_default_build_unchanged", "kernel_fingerprint_test_passed", "feature_test_passed")} | {"held": D}
    safe = all(rules.get(k, {}).get("held") for k in ("F1_divergences_not_higher", "F2_p5_within_2se_of_exact",
                                                        "P1_pass_count_not_lower", "P2_geomean_ess_per_gradient_ge_0.95", "D_build_integrity"))
    rules["verdict"] = "SAFE: ten levels qualify as a default change (flip not applied here)" if safe else "NOT QUALIFIED as a default change"
    if Lb:
        rules["L_descriptive"] = {"pooled_p5": Lb["pooled_p5"], "se": Lb["se_p5"], "t": Lb["t_p5"], "relative": Lb["pooled_p5"] / EXACT_P5 - 1,
                                  "prefix_20k_pooled": Lb["prefix_pooled_p5"]}
    summary = {"schema": "refinement-levels10-v1-summary", "ledger_id": "WP67", "protocol": PROTOCOL["status"],
               "environment": env, "decision_rules": rules, "predictions": preds, "funnel": F, "long_funnel": Lb, "posteriordb": P}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n", encoding="utf-8")
    write_table(summary)
    print(json.dumps({"decision_rules": rules, "predictions": preds}, indent=1, default=str))


def write_table(s: dict) -> None:
    F, Lb, P = s["funnel"], s["long_funnel"], s["posteriordb"]
    L = ["# WP67 results tables (generated by `run_study.py analyze`)", "",
         "## Funnel (F: 4 x 2,000/20,000, 30 seeds; L: default 4 x 2,000/80,000, 30 seeds, descriptive)", "",
         "| arm | cells | err | pooled P5 ± s.e. | t | upper P(>5) | prefix-20k P5 | mean z | \\|z\\|>2 | divergences | div-free seeds | exhaustions | deep top-level / exhaust | depth caps | median omega tail ESS | median omega bulk ESS | geomean minESS/grad | median gradients | omega var | warn cells |",
         "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, a in [("default", F.get("default")), ("levels10", F.get("levels10")), ("L: default 80k", Lb)]:
        if not a:
            continue
        L.append(f"| `{name}` | {a['cells']} | {len(a['errors'])} | {a['pooled_p5']:.4f} ± {a['se_p5']:.4f} | {a['t_p5']:+.2f} | {a['pooled_upper_p5']:.4f} | {a['prefix_pooled_p5']:.4f} | "
                 f"{a['mean_z']:+.3f} | {a['exceed']} | {a['divergences']} | {a['divergence_free_seeds']} | {a['exhaustions']} | {a['deep_top_level']} / {a['deep_exhaust_stops']} | {a['depth_caps']} | "
                 f"{a['median_omega_tail_ess']:.0f} | {a['median_omega_bulk_ess']:.0f} | {a['geomean_min_bulk_ess_per_gradient']:.3e} | {a['median_gradients']:.3g} | {a['omega_variance']:.2f} | {a['chain_warning_cells']} |")
    if P:
        L += ["", "## posteriordb house set (4 x 1,000/1,000, 3 seeds)", "",
              f"Passes: default {P['passes']['default']}/{P['cells_per_arm']}, levels10 {P['passes']['levels10']}/{P['cells_per_arm']}; "
              f"geomean ESS/gradient ratio levels10/default {P['geomean_ratio_levels10_over_default']} over {P['models_in_geomean']} models; "
              f"bit-identical cells {P['identical_cells']}/{P['cells_per_arm']}; largest passing |z| {P['passing_cells_max_abs_z']}.", "",
              "| model | pass default | pass levels10 | identical seeds | ratio | median ESS/grad default | levels10 | div default | div levels10 | L7 sel. (default, all transitions) | L8+ sel. (levels10) | exhaust stops default / levels10 | max \\|z\\| default / levels10 | median gradients default / levels10 |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|"]
        for m, r in P["per_model"].items():
            dd, ll = r["default"], r["levels10"]
            fmt = lambda x, sp=".3e": "—" if x is None else format(x, sp)  # noqa: E731
            L.append(f"| {m} | {dd['passed']}/3 | {ll['passed']}/3 | {r['identical_seeds']}/3 | {fmt(r['ratio'], '.3f')} | {fmt(dd['median_ess_per_gradient'])} | {fmt(ll['median_ess_per_gradient'])} | "
                     f"{dd['divergences']} | {ll['divergences']} | {dd['level7_all']} | {ll['level8_plus_all']} | {dd['exhaustion_stops_all']} / {ll['exhaustion_stops_all']} | "
                     f"{fmt(dd['max_abs_z'], '.2f')} / {fmt(ll['max_abs_z'], '.2f')} | {fmt(dd['median_gradients'], '.3g')} / {fmt(ll['median_gradients'], '.3g')} |")
        L += ["", "Non-identical cells: " + ", ".join(P["non_identical_cells"])]
    L += ["", "## Funnel per seed (P5 / z / divergences / exhaustions; identical draws marked =)", "", "| seed | default | levels10 |", "|---|---|---|"]
    if F.get("default") and F.get("levels10"):
        for seed, r in F["default"]["per_seed"].items():
            q = F["levels10"]["per_seed"].get(seed)
            same = "=" if q and q["draws_fnv"] == r["draws_fnv"] else ""
            L.append(f"| {seed} | {r['p5']:.4f} / {r['z']:+.2f} / {r['divergences']} / {r['exhaustions']} | "
                     + (f"{q['p5']:.4f} / {q['z']:+.2f} / {q['divergences']} / {q['exhaustions']} {same}" if q else "—") + " |")
    L += ["", "## Decision rules", "", "```json", json.dumps(s["decision_rules"], indent=1, default=str), "```", "",
          "## Predictions", "", "```json", json.dumps(s["predictions"], indent=1, default=str), "```", ""]
    (ART / "results-table.md").write_text("\n".join(L), encoding="utf-8")


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
