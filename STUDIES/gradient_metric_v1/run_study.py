#!/usr/bin/env python3
"""WP71 driver: does a gradient-informed diagonal metric estimator raise ESS per gradient?

    python3 run_study.py prepare        # posteriordb models -> models/*.stan, *.data.json, BridgeStan *_model.so
    python3 run_study.py run P          # posteriordb, 17 house models x 3 seeds x {default, gradmetric, gradmetric-overlap} x 4 x 1,000/1,000
    python3 run_study.py run F          # funnel sanity arm, 10 seeds x {default, gradmetric, gradmetric-overlap} x 4 x 2,000/20,000
    python3 run_study.py analyze        # artifacts/summary.json + artifacts/results-table.md

Arms are adaptations in one build (target/release/*, owalnuts with the `research` feature):
`default` = Adaptation::default(); `gradmetric` / `gradmetric-overlap` = Adaptation::Custom with the sampler's own
warmup defaults plus DiagonalMetricEstimator::GradientInformed / GradientInformedOverlap.
On the shared box every call is wrapped in `taskset -c 8-11`; children inherit it.
Funnel statistics are WP66's; posteriordb cell metrics are v7's (via WP68's driver), reading posteriordb files directly.
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
ART = Path(os.environ.get("WP71_ARTIFACTS", HERE / "artifacts"))  # override only for the non-evidence pipeline check
CELLS = ART / "cells"
DRAWS = Path(os.environ.get("WP71_DRAWS", HERE / "draws"))  # unconstrained draws; not committed (hash manifest is)
MODELS = Path(os.environ.get("WP71_MODELS", HERE / "models"))
PDB = Path(os.environ.get("WP71_POSTERIORDB", Path.home() / "infra" / "posteriordb" / "posterior_database"))
BRIDGESTAN = Path(os.environ.get("BRIDGESTAN", HERE / "bridgestan"))
EXE = ".exe" if os.name == "nt" else ""
BIN = HERE / "target" / "release"
ARMS = ["default", "gradmetric", "gradmetric-overlap"]
CANDIDATES = ["gradmetric", "gradmetric-overlap"]
PRIMARY = "gradmetric"
SEEDS = PROTOCOL["seeds"]
BLOCKS = PROTOCOL["blocks"]
HOUSE = PROTOCOL["house_models"]
GATES = PROTOCOL["gates"]
TIMEOUT = PROTOCOL["cell_timeout_seconds"]
PREDICTED = PROTOCOL["predicted_gainers"]
EXACT_P5 = 0.0477903522728147

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
        "schema": "gradient-metric-v1-pdb-metrics", "model": model, "arm": arm, "seed": seed, "status": "ok",
        "wall_seconds_pinned_cotenanted": o["wall_seconds"], "gradients_total": grads,
        "gradients_sampling": sum(c["retained_target_calls"] for c in chains),
        "divergences": divergences, "max_depth_stops": sum(c["maximum_depth_stops"] for c in chains),
        "min_bulk_ess": min_bulk, "min_tail_ess": min_tail, "max_rank_rhat": max_rhat,
        "argmin_bulk_ess": names[int(np.nanargmin(st["bulk_ess"]))],
        "min_bulk_ess_per_gradient": min_bulk / grads, "min_tail_ess_per_gradient": min_tail / grads,
        "max_abs_z": float(np.nanmax(np.abs(z))), "argmax_abs_z": names[int(np.nanargmax(np.abs(z)))],
        "gates": gates, "passed": all(gates.values()),
        "draws_fnv": [c["draws_fnv"] for c in chains],
        "gradients_warmup": sum(c["warmup_target_calls"] for c in chains),
        "gradients_start_search": o["init"]["start_search_calls"],
        "warmup_gradient_share": sum(c["warmup_target_calls"] for c in chains) / grads,
        "metric_updates": [[{k: u[k] for k in ("window_index", "sample_count", "outcome", "step_before", "step_after_restart",
                                                "mass_min", "mass_max", "mass_geomean")} for u in c["metric_updates"]] for c in chains],
        "final_mass_geomean": [math.exp(statistics.fmean(math.log(m) for m in c["mass_diagonal"])) for c in chains],
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
            f"mintail {cell['min_tail_ess']:.0f} rhat {cell['max_rank_rhat']:.4f} div {cell['divergences']} |z| {cell['max_abs_z']:.2f} "
            f"passed {cell['passed']} warmup-share {cell['warmup_gradient_share']:.3f} "
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
    return {
        "cells": len(cs), "errors": errors, "pooled_p5": p5, "se_p5": se, "t_p5": (p5 - EXACT_P5) / se,
        "mean_z": statistics.fmean(z), "exceed": sum(abs(v) > 2 for v in z) + len(errors),
        "divergences": sum(ch["divergences"] for c in cs for ch in c["chains_data"]),
        "divergence_free_seeds": sum(sum(ch["divergences"] for ch in c["chains_data"]) == 0 for c in cs),
        "exhaustions": sum(ch["refinement_exhaustions"] for c in cs for ch in c["chains_data"]),
        "warmup_divergences": sum(ch["warmup_divergences"] for c in cs for ch in c["chains_data"]),
        "median_omega_tail_ess": statistics.median(c["omega"]["tail_ess"] for c in cs),
        "median_omega_bulk_ess": statistics.median(c["omega"]["bulk_ess"] for c in cs),
        "geomean_min_bulk_ess_per_gradient": geomean([c["min_bulk_ess_per_gradient"] for c in cs]),
        "median_gradients": statistics.median(c["target_calls_total"] for c in cs),
        "warmup_gradient_share": sum(ch["target_calls"] - ch["retained_target_calls"] for c in cs for ch in c["chains_data"])
                                 / sum(c["target_calls_total"] for c in cs),
        "max_rhat_max": max(c["max_rhat"] for c in cs),
        "chain_warning_cells": sum(bool(c["chain_warnings"]) for c in cs),
        "final_mass_omega_median": statistics.median(ch["mass_diagonal"][0] for c in cs for ch in c["chains_data"]),
        "final_mass_x_median": statistics.median(statistics.median(ch["mass_diagonal"][1:]) for c in cs for ch in c["chains_data"]),
        "per_seed": {str(s): {"p5": c["tail_mass"]["estimate"], "z": c["tail_mass"]["z"],
                              "divergences": sum(ch["divergences"] for ch in c["chains_data"]),
                              "exhaustions": sum(ch["refinement_exhaustions"] for ch in c["chains_data"]),
                              "omega_tail_ess": c["omega"]["tail_ess"], "draws_fnv": c["draws_fnv"]} for s, c in cells.items()},
        "algorithm_revisions": sorted({c["algorithm_revision"] for c in cs if "algorithm_revision" in c}),
    }


def pdb_cells() -> dict:
    cells = {arm: {} for arm in ARMS}
    for model in HOUSE:
        for seed in SEEDS[BLOCKS["P"]["seeds"]]:
            for arm in ARMS:
                c = load(cell_path("P", arm, seed, model))
                if c is not None:
                    cells[arm][(model, seed)] = c
    return cells


def arm_row(cs: list) -> dict:
    ok = [c for c in cs if c and c["status"] == "ok"]
    return {"passed": sum(bool(c and c["passed"]) for c in cs), "ok": len(ok),
            "median_ess_per_gradient": statistics.median(c["min_bulk_ess_per_gradient"] for c in cs) if len(ok) == len(cs) else None,
            "divergences": sum(c.get("divergences", 0) for c in cs if c),
            "max_abs_z": max((c.get("max_abs_z") or 0) for c in ok) if ok else None,
            "max_rhat": max(c["max_rank_rhat"] for c in ok) if ok else None,
            "min_bulk": min(c["min_bulk_ess"] for c in ok) if ok else None,
            "warmup_gradient_share": (sum(c["gradients_warmup"] for c in ok) / sum(c["gradients_total"] for c in ok)) if ok else None,
            "median_gradients": statistics.median(c["gradients_total"] for c in ok) if ok else None,
            "median_final_step": statistics.median(x for c in ok for x in c["final_step_size"]) if ok else None,
            "failed_gates": sorted({g for c in cs if c for g, v in c["gates"].items() if not v})}


def pdb_summary() -> dict:
    cells = pdb_cells()
    seeds = SEEDS[BLOCKS["P"]["seeds"]]
    out = {"cells_per_arm": len(HOUSE) * len(seeds),
           "passes": {arm: sum(c["passed"] for c in cells[arm].values()) for arm in ARMS},
           "ok_cells": {arm: sum(c["status"] == "ok" for c in cells[arm].values()) for arm in ARMS},
           "divergences": {arm: sum(c.get("divergences", 0) for c in cells[arm].values()) for arm in ARMS},
           "warmup_gradient_share_pooled": {arm: (sum(c["gradients_warmup"] for c in cells[arm].values() if c["status"] == "ok")
                                                  / max(1, sum(c["gradients_total"] for c in cells[arm].values() if c["status"] == "ok")))
                                            for arm in ARMS},
           "per_model": {}, "candidates": {}}
    for model in HOUSE:
        out["per_model"][model] = {arm: arm_row([cells[arm].get((model, s)) for s in seeds]) for arm in ARMS}
    for cand in CANDIDATES:
        ratios, new_div, lost = {}, [], []
        for model in HOUSE:
            row = out["per_model"][model]
            a, b = row["default"]["median_ess_per_gradient"], row[cand]["median_ess_per_gradient"]
            ratios[model] = b / a if a and b else None
            if row[cand]["divergences"] > row["default"]["divergences"]:
                new_div.append(model)
            if row[cand]["passed"] < row["default"]["passed"]:
                lost.append(model)
        valid = {m: r for m, r in ratios.items() if r}
        ranked = sorted(valid, key=valid.get, reverse=True)
        pred = [m for m in PREDICTED if m in valid]
        rest = [m for m in valid if m not in PREDICTED]
        out["candidates"][cand] = {
            "ratios": ratios, "geomean_ratio": geomean(list(valid.values())) if valid else None, "models_in_geomean": len(valid),
            "ranked": ranked, "models_up": sum(r > 1 for r in valid.values()), "models_down": sum(r < 1 for r in valid.values()),
            "models_with_more_divergences": new_div, "models_with_fewer_passes": lost,
            "geomean_predicted_gainers": geomean([valid[m] for m in pred]) if pred else None,
            "geomean_other_models": geomean([valid[m] for m in rest]) if rest else None,
            "predicted_in_top6": sum(m in ranked[:6] for m in PREDICTED),
            "geomean_without_hmm_drive_0": geomean([r for m, r in valid.items() if m != "bball_drive_event_0-hmm_drive_0"]) if valid else None,
            "identical_cells_vs_default": sum(bool(cells[cand].get((m, s)) and cells["default"].get((m, s))
                                                   and cells[cand][(m, s)].get("draws_fnv") == cells["default"][(m, s)].get("draws_fnv"))
                                              for m in HOUSE for s in seeds),
        }
    return out


def rules_for(cand: str, P: dict, F: dict, env: dict) -> dict:
    c = P["candidates"][cand]
    g = c["geomean_ratio"]
    r = {"R1_geomean_ess_per_gradient_ge_1.10": {"value": g, "models": c["models_in_geomean"], "held": g is not None and g >= 1.10},
         "R2_pass_count_not_lower": {"default": P["passes"]["default"], cand: P["passes"][cand], "held": P["passes"][cand] >= P["passes"]["default"]},
         "R3_no_new_divergences": {"models_with_more_divergences": c["models_with_more_divergences"],
                                   "total_default": P["divergences"]["default"], f"total_{cand}": P["divergences"][cand],
                                   "held": not c["models_with_more_divergences"]}}
    f = F.get(cand)
    if f:
        r["F_funnel_p5_within_1se"] = {"pooled": f["pooled_p5"], "se": f["se_p5"], "abs_error": abs(f["pooled_p5"] - EXACT_P5),
                                       "held": abs(f["pooled_p5"] - EXACT_P5) <= f["se_p5"]}
    else:
        r["F_funnel_p5_within_1se"] = {"held": False, "note": "no funnel cells"}
    D = bool(env.get("library_diff_scoped") and env.get("kernel_fingerprint_test_passed") and env.get("flag_off_test_passed"))
    r["D_flag_off_integrity"] = {k: env.get(k) for k in ("library_diff_scoped", "kernel_fingerprint_test_passed", "flag_off_test_passed")} | {"held": D}
    failed = [k for k, v in r.items() if not v["held"]]
    r["verdict"] = ("SUPPORTED: the gradient-informed estimator raises ESS per gradient without losing gates (research flag; no default flip)"
                    if not failed else "NOT SUPPORTED (failed: " + ", ".join(k.split("_")[0] for k in failed) + ")")
    return r


def analyze(env: dict) -> None:
    F = {arm: funnel_arm("F", arm) for arm in ARMS}
    P = pdb_summary()
    rules = {cand: rules_for(cand, P, F, env) for cand in CANDIDATES}
    c = P["candidates"][PRIMARY]
    co = P["candidates"]["gradmetric-overlap"]
    ws = P["warmup_gradient_share_pooled"]
    preds = {
        "Pa_predicted_gainers_gain_more": {"observed": [c["geomean_predicted_gainers"], c["geomean_other_models"]],
                                           "held": None not in (c["geomean_predicted_gainers"], c["geomean_other_models"])
                                           and c["geomean_predicted_gainers"] > c["geomean_other_models"]},
        "Pb_at_least_3_predicted_in_top6": {"observed": c["predicted_in_top6"], "top6": c["ranked"][:6], "held": c["predicted_in_top6"] >= 3},
        "Pc_warmup_share_lower_with_gradmetric": {"observed": [ws["default"], ws[PRIMARY]], "held": ws[PRIMARY] < ws["default"]},
        "Pd_warmup_share_change_under_5_points": {"observed": ws[PRIMARY] - ws["default"], "held": abs(ws[PRIMARY] - ws["default"]) < 0.05},
        "Pe_overlap_within_5pct_of_primary": {"observed": [co["geomean_ratio"], c["geomean_ratio"]],
                                              "held": None not in (co["geomean_ratio"], c["geomean_ratio"])
                                              and abs(co["geomean_ratio"] / c["geomean_ratio"] - 1) <= 0.05},
        "Pf_lost_passes_only_on_gp_pois_regr_or_lotka_volterra": {
            "observed": c["models_with_fewer_passes"],
            "held": set(c["models_with_fewer_passes"]) <= {"gp_pois_regr-gp_pois_regr", "hudson_lynx_hare-lotka_volterra"}},
    }
    summary = {"schema": "gradient-metric-v1-summary", "ledger_id": "WP71", "protocol": PROTOCOL["status"],
               "environment": env, "decision_rules": rules, "verdict": rules[PRIMARY]["verdict"], "predictions": preds,
               "funnel": F, "posteriordb": P}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n", encoding="utf-8")
    write_table(summary)
    print(json.dumps({"decision_rules": rules, "predictions": preds}, indent=1, default=str))


def write_table(s: dict) -> None:
    F, P = s["funnel"], s["posteriordb"]
    fmt = lambda x, sp=".3e": "—" if x is None else format(x, sp)  # noqa: E731
    L = ["# WP71 results tables (generated by `run_study.py analyze`)", "",
         "## posteriordb house set (4 x 1,000/1,000, 3 seeds per arm)", "",
         f"Passes /{P['cells_per_arm']}: " + ", ".join(f"{a} {P['passes'][a]}" for a in ARMS) + "; retained divergences: "
         + ", ".join(f"{a} {P['divergences'][a]}" for a in ARMS) + "; pooled warmup gradient share: "
         + ", ".join(f"{a} {P['warmup_gradient_share_pooled'][a]:.3f}" for a in ARMS) + ".", ""]
    for cand in CANDIDATES:
        c = P["candidates"][cand]
        L.append(f"- `{cand}`: geomean ratio {fmt(c['geomean_ratio'], '.3f')} over {c['models_in_geomean']} models "
                 f"({c['models_up']} up, {c['models_down']} down; without hmm_drive_0 {fmt(c['geomean_without_hmm_drive_0'], '.3f')}); "
                 f"predicted gainers {fmt(c['geomean_predicted_gainers'], '.3f')} vs others {fmt(c['geomean_other_models'], '.3f')}; "
                 f"fewer passes on {c['models_with_fewer_passes'] or 'none'}; more divergences on {c['models_with_more_divergences'] or 'none'}.")
    L += ["", "| model | pass d / g / o | ratio g | ratio o | median ESS/grad default | gradmetric | overlap | div d / g / o | max R-hat d / g / o | warmup share d / g / o | median final step d / g / o | failed gates g |",
          "|---|---|---:|---:|---:|---:|---:|---|---|---|---|---|"]
    for m, r in P["per_model"].items():
        d, g, o = r["default"], r["gradmetric"], r["gradmetric-overlap"]
        L.append(f"| {m} | {d['passed']} / {g['passed']} / {o['passed']} | {fmt(P['candidates']['gradmetric']['ratios'][m], '.3f')} | "
                 f"{fmt(P['candidates']['gradmetric-overlap']['ratios'][m], '.3f')} | {fmt(d['median_ess_per_gradient'])} | {fmt(g['median_ess_per_gradient'])} | "
                 f"{fmt(o['median_ess_per_gradient'])} | {d['divergences']} / {g['divergences']} / {o['divergences']} | "
                 f"{fmt(d['max_rhat'], '.4f')} / {fmt(g['max_rhat'], '.4f')} / {fmt(o['max_rhat'], '.4f')} | "
                 f"{fmt(d['warmup_gradient_share'], '.3f')} / {fmt(g['warmup_gradient_share'], '.3f')} / {fmt(o['warmup_gradient_share'], '.3f')} | "
                 f"{fmt(d['median_final_step'], '.3g')} / {fmt(g['median_final_step'], '.3g')} / {fmt(o['median_final_step'], '.3g')} | "
                 f"{', '.join(g['failed_gates']) or '—'} |")
    L += ["", "## Funnel sanity arm (4 x 2,000/20,000, 10 seeds per arm)", "",
          "| arm | cells | err | pooled P5 ± s.e. | t | divergences | div-free seeds | exhaustions | median omega tail ESS | geomean minESS/grad | median gradients | warmup share | final mass omega / x (median) |",
          "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for arm in ARMS:
        a = F.get(arm)
        if a:
            L.append(f"| `{arm}` | {a['cells']} | {len(a['errors'])} | {a['pooled_p5']:.4f} ± {a['se_p5']:.4f} | {a['t_p5']:+.2f} | {a['divergences']} | "
                     f"{a['divergence_free_seeds']} | {a['exhaustions']} | {a['median_omega_tail_ess']:.0f} | {a['geomean_min_bulk_ess_per_gradient']:.3e} | "
                     f"{a['median_gradients']:.3g} | {a['warmup_gradient_share']:.3f} | {a['final_mass_omega_median']:.3g} / {a['final_mass_x_median']:.3g} |")
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
