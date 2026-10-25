#!/usr/bin/env python3
"""WP54 nonfinite-position policy default-flip confirmation driver.

    python run_study.py manifest   # print the frozen cell order (from protocol.json)
    python run_study.py smoke      # non-evidence smoke test (seed in protocol "smoke_seed"; writes artifacts/smoke/)
    python run_study.py run        # every evidence cell in manifest order (resumable; never reruns a written cell)
    python run_study.py analyze    # artifacts/summary.json + artifacts/results-table.md

Harness reuse: the cell metrics, reference statistics and gates are those of
`STUDIES/dense_metric_posteriordb_v1/run_dense.py` (WP48), itself the
posteriordb_bench_v6 harness. Each cell writes `artifacts/cells/<id>.json`
(metrics, draw hash, counters, no draws) and `artifacts/draws/<id>.npz`
(unconstrained draws; uncommitted). Failures are cells with status != "ok".
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
RAW = ART / "raw-tmp"
MODELS = HERE / "models"
PDB_PATH = Path(PROTOCOL["posteriordb"]["path"])
HARNESS = HERE / "target" / "release" / "policy-cell.exe"
FUNNEL = HERE / "target" / "release" / "funnel.exe"
ARMS = PROTOCOL["arms"]  # ["abort", "reject_leaf"]
os.environ.setdefault("RUSTUP_TOOLCHAIN", "1.88.0-x86_64-pc-windows-gnu")


def short(model: str) -> str:
    return model.replace("-", "__")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------- manifest


def manifest() -> list[dict]:
    """The frozen cell order. Each block lists (model, seed) pairs; both arms run back to back, abort first."""
    cells = []
    for block in PROTOCOL["blocks"]:
        if block.get("kind") == "funnel":
            for seed in block["seeds"]:
                for arm in ARMS:
                    cells.append({"block": block["name"], "kind": "funnel", "model": "funnel", "seed": seed, "arm": arm,
                                  "id": f"{block['name']}--funnel--{arm}--{seed}"})
            continue
        models = block["models"] if "models" in block else PROTOCOL["models"]
        for model in models:
            for seed in block["seeds"]:
                for arm in ARMS:
                    cells.append({"block": block["name"], "kind": "posterior", "model": model, "seed": seed, "arm": arm,
                                  "assets": block.get("assets", "house"),
                                  "timeout": block["cell_timeout_seconds"],
                                  "id": f"{block['name']}--{short(model)}--{arm}--{seed}"})
    return cells


# --------------------------------------------------------------------------- posteriordb reference (WP48 code)


def posterior(model: str):
    from posteriordb import PosteriorDatabase

    return PosteriorDatabase(str(PDB_PATH)).posterior(model)


def bridgestan_name(name: str) -> str:
    parts = name.split(".")
    if len(parts) == 1 or not all(p.isdigit() for p in parts[1:]):
        return name
    return f"{parts[0]}[{','.join(parts[1:])}]"


_REF = {}


def reference(model: str) -> dict:
    if model not in _REF:
        p = posterior(model)
        ref = p.reference_draws()
        names = list(ref[0].keys())
        arr = np.asarray([[c[n] for n in names] for c in ref], dtype=np.float64)
        arr = np.transpose(arr, (0, 2, 1))
        _REF[model] = {"names": names, **arviz_stats(arr)}
    return _REF[model]


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


_SM = {}


def stan_model(so: Path, data: Path):
    import bridgestan as bs

    key = str(so)
    if key not in _SM:
        bs.compile.windows_dll_path_setup()
        _SM[key] = bs.StanModel(str(so), data=data.read_text(encoding="utf-8"), seed=1)
    return _SM[key]


def assets(cell: dict) -> tuple[Path, Path, list[str]]:
    """(model.so, data.json, extra harness args [threads, construct_seed, preload])."""
    model = cell["model"]
    data = MODELS / f"{short(model)}.data.json"
    if cell["assets"] == "wp50":
        a = PROTOCOL["wp50_assets"]
        return HERE / a["model"], data, ["4", str(a["construct_seed"]), str(HERE / a["preload"])]
    return MODELS / f"{short(model)}_model.so", data, ["4"]


# --------------------------------------------------------------------------- cells


def base(cell: dict) -> dict:
    return {"schema": "nonfinite-policy-requalification-v1-cell-metrics", "id": cell["id"], "block": cell["block"],
            "model": cell["model"], "arm": cell["arm"], "seed": cell["seed"]}


def failure(cell, status, message, **extra) -> dict:
    return {**base(cell), "status": status, "error": message, "completed": False, "passed": False,
            "gates": {"completed": False}, **extra}


def run_posterior_cell(cell: dict, out_dir: Path) -> dict:
    so, data, extra_args = assets(cell)
    RAW.mkdir(parents=True, exist_ok=True)
    raw = RAW / f"{cell['id']}.json"
    if raw.exists():
        raw.unlink()
    cmd = [str(HARNESS), str(so), str(data), cell["arm"], str(cell["seed"]), str(raw), *extra_args]
    t0 = time.perf_counter()
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=cell["timeout"])
    except subprocess.TimeoutExpired:
        if raw.exists():
            raw.unlink()
        return failure(cell, "timeout", f"exceeded {cell['timeout']}s", process_seconds=time.perf_counter() - t0)
    if cp.returncode != 0 or not raw.exists():
        return failure(cell, "harness_error", f"exit {cp.returncode}: {cp.stderr.strip()[-2000:]}")
    out = json.loads(raw.read_text(encoding="utf-8"))
    if out.get("status") != "ok":
        raw.unlink()
        msg = out.get("error", "unknown")
        return failure(cell, "aborted" if out.get("error_kind") == "Numerical" and "nonfinite target position" in msg
                       else "error", msg, error_kind=out.get("error_kind"), stage=out.get("stage"),
                       wall_seconds_contended=out.get("wall_seconds"), target_calls=out.get("target_calls"),
                       nonfinite_event_class=("kernel_nonfinite_position" if "nonfinite target position" in msg else "other"))
    ref = reference(cell["model"])
    sm = stan_model(so, data)
    cnames = [bridgestan_name(n) for n in sm.param_names(include_tp=True, include_gq=False)]
    chains = out["chains_data"]
    unc = np.asarray([c["samples"] for c in chains], dtype=np.float64)  # (chains, draws, d)
    con = np.empty(unc.shape[:2] + (len(cnames),))
    for c in range(unc.shape[0]):
        for d in range(unc.shape[1]):
            con[c, d] = sm.param_constrain(unc[c, d], include_tp=True, include_gq=False)
    index = {n: i for i, n in enumerate(cnames)}
    missing = [n for n in ref["names"] if n not in index]
    if missing:
        return failure(cell, "harness_error", f"reference parameters not produced: {missing[:5]}")
    draws = con[:, :, [index[n] for n in ref["names"]]]
    st = arviz_stats(draws)
    z = (st["mean"] - ref["mean"]) / np.sqrt(st["mcse"] ** 2 + ref["mcse"] ** 2)
    g = PROTOCOL["gates"]
    min_bulk = float(np.nanmin(st["bulk_ess"]))
    min_tail = float(np.nanmin(st["tail_ess"]))
    max_rhat = float(np.nanmax(st["rhat"]))
    divergences = sum(c["divergences"] for c in chains)
    gates = {
        "completed": True,
        "max_rank_rhat": max_rhat <= g["max_rank_rhat"],
        "min_bulk_ess": min_bulk >= g["min_bulk_ess"],
        "min_tail_ess": min_tail >= g["min_tail_ess"],
        "sampling_divergences": divergences == 0,
        "finite_draws": bool(np.isfinite(draws).all()),
    }
    grads = out["target_calls_total"]
    res = {
        **base(cell), "status": "ok", "completed": True,
        "draw_hash": out["draw_hash"],
        "per_chain_draw_hash": [c["draw_hash"] for c in chains],
        "per_chain_target_calls": [c["total_target_calls"] for c in chains],
        "gradients_total": grads,
        "start_search_calls": out["start_search_calls"],
        "nonfinite_position_rejections": sum(c["nonfinite_position_rejections_total"] for c in chains),
        "nonfinite_position_rejections_per_chain": [c["nonfinite_position_rejections_total"] for c in chains],
        "nonfinite_position_rejections_retained": sum(c["nonfinite_position_rejections_retained"] for c in chains),
        "divergences": divergences,
        "warmup_divergences": sum(c["warmup_divergences"] for c in chains),
        "per_chain_divergences": [c["divergences"] for c in chains],
        "max_depth_stops": sum(c["maximum_depth_stops"] for c in chains),
        "refinement_exhaustions": sum(c["refinement_exhaustions"] for c in chains),
        "final_step_size": [c["final_step_size"] for c in chains],
        "min_bulk_ess": min_bulk, "min_tail_ess": min_tail, "max_rank_rhat": max_rhat,
        "argmin_bulk_ess": ref["names"][int(np.nanargmin(st["bulk_ess"]))],
        "min_bulk_ess_per_gradient": min_bulk / grads,
        "max_abs_z": float(np.nanmax(np.abs(z))),
        "argmax_abs_z": ref["names"][int(np.nanargmax(np.abs(z)))],
        "per_chain_bulk_ess_min": [float(np.nanmin(arviz_stats(draws[i:i + 1])["bulk_ess"])) for i in range(draws.shape[0])],
        "gates": gates, "passed": all(gates.values()),
        "wall_seconds_contended": out["wall_seconds"],
        "algorithm_revision": out["algorithm_revision"],
        "kernel_nonfinite_position": out["kernel_nonfinite_position"],
        "model_library": out["model_library"], "construct_seed": out["construct_seed"], "preload": out["preload"],
        "init": out["init"],
        "parameters": {n: {"mean": float(st["mean"][i]), "bulk_ess": float(st["bulk_ess"][i]),
                           "tail_ess": float(st["tail_ess"][i]), "rhat": float(st["rhat"][i]), "z": float(z[i])}
                       for i, n in enumerate(ref["names"])},
    }
    DRAWS.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(DRAWS / f"{cell['id']}.npz", unconstrained=unc, draws=draws, names=np.asarray(ref["names"]))
    raw.unlink()
    return res


def run_funnel_cell(cell: dict) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    raw = RAW / f"{cell['id']}.json"
    if raw.exists():
        raw.unlink()
    cp = subprocess.run([str(FUNNEL), cell["arm"], str(cell["seed"]), str(raw)], capture_output=True, text=True,
                        timeout=PROTOCOL["funnel"]["cell_timeout_seconds"])
    if cp.returncode != 0 or not raw.exists():
        return failure(cell, "harness_error", f"exit {cp.returncode}: {cp.stderr.strip()[-2000:]}")
    out = json.loads(raw.read_text(encoding="utf-8"))
    raw.unlink()
    if out.get("status") != "ok":
        return failure(cell, "aborted" if "nonfinite target position" in out.get("error", "") else "error",
                       out.get("error"), error_kind=out.get("error_kind"))
    t = out["tail_mass"]
    ch = out["chains_data"]
    gate = abs(t["z"]) <= PROTOCOL["funnel"]["max_abs_z"]
    return {**base(cell), "status": "ok", "completed": True, "draw_hash": out["draw_hash"],
            "tail_mass": t, "omega": out["omega"], "target_calls_total": out["target_calls_total"],
            "per_chain_target_calls": [c["target_calls"] for c in ch],
            "divergences": sum(c["divergences"] for c in ch),
            "warmup_divergences": sum(c["warmup_divergences"] for c in ch),
            "nonfinite_position_rejections": sum(c["nonfinite_position_rejections_total"] for c in ch),
            "final_step_size": [c["final_step_size"] for c in ch],
            "gates": {"completed": True, "tail_mass_abs_z": gate}, "passed": gate,
            "wall_seconds_contended": out["wall_seconds"], "algorithm_revision": out["algorithm_revision"]}


def summarize_line(c: dict) -> str:
    if c["status"] != "ok":
        return f"{c['id']}: {c['status']}: {str(c.get('error', ''))[:200]}"
    if c["model"] == "funnel":
        return (f"{c['id']}: ok z {c['tail_mass']['z']:+.2f} est {c['tail_mass']['estimate']:.4f} div {c['divergences']} "
                f"nfr {c['nonfinite_position_rejections']} hash {c['draw_hash']}")
    return (f"{c['id']}: ok grads {c['gradients_total']} minbulk {c['min_bulk_ess']:.0f} mintail {c['min_tail_ess']:.0f} "
            f"rhat {c['max_rank_rhat']:.4f} div {c['divergences']} nfr {c['nonfinite_position_rejections']} "
            f"max|z| {c['max_abs_z']:.2f} passed {c['passed']} hash {c['draw_hash']} wall {c['wall_seconds_contended']:.1f}s")


def run_cell(cell: dict, out_path: Path) -> None:
    try:
        c = run_funnel_cell(cell) if cell["kind"] == "funnel" else run_posterior_cell(cell, out_path.parent)
    except Exception as e:  # noqa: BLE001
        c = failure(cell, "harness_error", f"{e}\n{traceback.format_exc()[-1500:]}")
    c["ordinal"] = cell.get("ordinal")
    c["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(c, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    log(summarize_line(c))


def run_all() -> None:
    ART.mkdir(exist_ok=True)
    m = ART / "measured_on.json"
    if not m.exists():
        m.write_text(json.dumps({
            "platform": platform.platform(), "processor": platform.processor(), "cpu_count": os.cpu_count(),
            "python": sys.version.split()[0], "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "note": "shared 16-core machine; up to six sibling agents ran concurrently; every wall is contended",
        }, indent=2) + "\n", encoding="utf-8")
    cells = manifest()
    for i, cell in enumerate(cells):
        cell["ordinal"] = i
        path = CELLS / f"{cell['id']}.json"
        if path.exists():
            continue
        log(f"[{i + 1}/{len(cells)}] {cell['id']}")
        run_cell(cell, path)


def smoke() -> None:
    seed = PROTOCOL["smoke_seed"]
    for arm in ARMS:
        cell = {"block": "smoke", "kind": "posterior", "model": "sblrc-blr", "seed": seed, "arm": arm,
                "assets": "house", "timeout": 600, "id": f"smoke--sblrc__blr--{arm}--{seed}"}
        run_cell(cell, ART / "smoke" / f"{cell['id']}.json")
    for arm in ARMS:
        cell = {"block": "smoke", "kind": "funnel", "model": "funnel", "seed": seed, "arm": arm,
                "id": f"smoke--funnel--{arm}--{seed}"}
        run_cell(cell, ART / "smoke" / f"{cell['id']}.json")


# --------------------------------------------------------------------------- analysis


def geomean(xs):
    xs = [x for x in xs if x and math.isfinite(x) and x > 0]
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs))) if xs else None


def med(xs):
    xs = [x for x in xs if x is not None and math.isfinite(x)]
    return statistics.median(xs) if xs else None


def analyze() -> None:
    cells = manifest()
    rec = {}
    for cell in cells:
        p = CELLS / f"{cell['id']}.json"
        if p.exists():
            c = json.loads(p.read_text(encoding="utf-8"))
            c.pop("parameters", None)
            rec[cell["id"]] = c
    missing = [c["id"] for c in cells if c["id"] not in rec]
    # pairs
    pairs = {}
    for cell in cells:
        key = (cell["block"], cell["model"], cell["seed"])
        pairs.setdefault(key, {})[cell["arm"]] = rec.get(cell["id"])
    pair_rows = []
    fingerprint_cells = 0
    fingerprint_identical = 0
    fingerprint_diffs = []
    rescued = []
    lost_by_reject_only = []
    for (block, model, seed), arms in pairs.items():
        a, r = arms.get("abort"), arms.get("reject_leaf")
        if a is None or r is None:
            continue
        row = {"block": block, "model": model, "seed": seed,
               "abort": {k: a.get(k) for k in ("status", "error", "passed", "gates", "max_abs_z", "divergences",
                                               "nonfinite_position_rejections", "draw_hash", "min_bulk_ess",
                                               "min_tail_ess", "max_rank_rhat", "tail_mass")},
               "reject_leaf": {k: r.get(k) for k in ("status", "error", "passed", "gates", "max_abs_z", "divergences",
                                                     "nonfinite_position_rejections", "nonfinite_position_rejections_retained",
                                                     "draw_hash", "min_bulk_ess", "min_tail_ess", "max_rank_rhat",
                                                     "tail_mass", "argmax_abs_z", "per_chain_divergences",
                                                     "nonfinite_position_rejections_per_chain")}}
        if a["status"] == "ok":
            fingerprint_cells += 1
            same = (r["status"] == "ok" and r["draw_hash"] == a["draw_hash"]
                    and r.get("per_chain_target_calls") == a.get("per_chain_target_calls")
                    and r.get("nonfinite_position_rejections") == 0)
            row["bit_identical"] = same
            if same:
                fingerprint_identical += 1
            else:
                fingerprint_diffs.append(f"{block}/{model}/{seed}")
        else:
            row["bit_identical"] = None
            if r["status"] == "ok":
                other = {k: v for k, v in r["gates"].items() if k not in ("completed",)}
                rescued.append({"block": block, "model": model, "seed": seed, "abort_status": a["status"],
                                "abort_error": str(a.get("error"))[:300], "max_abs_z": r.get("max_abs_z"),
                                "argmax_abs_z": r.get("argmax_abs_z"),
                                "passed_all_gates": r.get("passed"), "gates": r["gates"],
                                "divergences": r.get("divergences"),
                                "nonfinite_position_rejections": r.get("nonfinite_position_rejections"),
                                "nonfinite_position_rejections_retained": r.get("nonfinite_position_rejections_retained"),
                                "silently_wrong": bool(model != "funnel" and r.get("max_abs_z", 0) > 4 and all(other.values()))})
        if r["status"] != "ok" and a["status"] == "ok":
            lost_by_reject_only.append(f"{block}/{model}/{seed}")
        pair_rows.append(row)

    def completed(arm, blocks=None):
        return sum(1 for c in rec.values() if c["arm"] == arm and c["status"] == "ok" and (blocks is None or c["block"] in blocks))

    def passed(arm, blocks):
        return sum(1 for c in rec.values() if c["arm"] == arm and c.get("passed") and c["block"] in blocks)

    blocks = [b["name"] for b in PROTOCOL["blocks"]]
    stress_blocks = [b["name"] for b in PROTOCOL["blocks"] if b.get("stress")]
    per_block = {b: {arm: {"cells": sum(1 for c in rec.values() if c["arm"] == arm and c["block"] == b),
                           "completed": completed(arm, [b]), "passed_gates": passed(arm, [b]),
                           "statuses": {f"{c['model']}/{c['seed']}": c["status"] for c in rec.values()
                                        if c["arm"] == arm and c["block"] == b}}
                     for arm in ARMS} for b in blocks}
    # house statistic: geomean over models of per-model seed-median min bulk ESS per gradient
    house = PROTOCOL["house_block"]
    house_models = {}
    for model in PROTOCOL["models"]:
        e = {}
        for arm in ARMS:
            ok = [c for c in rec.values() if c["block"] == house and c["model"] == model and c["arm"] == arm and c["status"] == "ok"]
            e[arm] = {"n_ok": len(ok), "n_passed": sum(1 for c in ok if c["passed"]),
                      "min_bulk_ess_per_gradient_median": med([c["min_bulk_ess_per_gradient"] for c in ok]),
                      "max_abs_z_max": max([c["max_abs_z"] for c in ok], default=None),
                      "failed_gates": {str(c["seed"]): [k for k, v in c["gates"].items() if not v] for c in ok}}
        a = e["abort"]["min_bulk_ess_per_gradient_median"]
        r = e["reject_leaf"]["min_bulk_ess_per_gradient_median"]
        e["ratio_reject_over_abort"] = (r / a) if (a and r) else None
        house_models[model] = e
    geo = {arm: geomean([house_models[m][arm]["min_bulk_ess_per_gradient_median"] for m in PROTOCOL["models"]]) for arm in ARMS}
    total_completed = {arm: completed(arm) for arm in ARMS}
    total_cells = {arm: sum(1 for c in cells if c["arm"] == arm) for arm in ARMS}
    funnel_rows = [c for c in rec.values() if c["model"] == "funnel"]
    funnel = {arm: {str(c["seed"]): {"status": c["status"], "z": c.get("tail_mass", {}).get("z"),
                                     "estimate": c.get("tail_mass", {}).get("estimate"),
                                     "divergences": c.get("divergences"),
                                     "nonfinite_position_rejections": c.get("nonfinite_position_rejections"),
                                     "passed": c.get("passed")}
                    for c in funnel_rows if c["arm"] == arm} for arm in ARMS}
    funnel_pass = {arm: bool(funnel[arm]) and all(v["passed"] for v in funnel[arm].values()) for arm in ARMS}
    stress_gates = {arm: passed(arm, stress_blocks) for arm in ARMS}

    # decision rule (frozen)
    d1 = fingerprint_cells > 0 and fingerprint_identical == fingerprint_cells
    d2 = total_completed["reject_leaf"] > total_completed["abort"]
    d3 = not any(x["silently_wrong"] for x in rescued)
    d4 = funnel_pass["reject_leaf"]
    decision = {"D1_bit_identical_all_completed_abort_cells": d1, "D2_reject_completes_strictly_more": d2,
                "D3_no_silently_wrong_rescue": d3, "D4_funnel_passes_under_reject_leaf": d4,
                "flip": bool(d1 and d2 and d3 and d4 and not missing)}
    # predictions
    abort_completed_ids = {(c["block"], c["model"], c["seed"]) for c in rec.values() if c["arm"] == "abort" and c["status"] == "ok"}
    reject_completed_ids = {(c["block"], c["model"], c["seed"]) for c in rec.values() if c["arm"] == "reject_leaf" and c["status"] == "ok"}
    stress_abort_lost = {(c["block"], c["model"], c["seed"]) for c in rec.values()
                         if c["arm"] == "abort" and c["status"] != "ok" and c["block"] in stress_blocks}
    preds = {
        "P1_reject_completes_every_abort_completion": abort_completed_ids <= reject_completed_ids,
        "P1b_reject_completes_every_stress_case_abort_loses": stress_abort_lost <= reject_completed_ids,
        "P1b_detail": {"stress_abort_lost": sorted(map(list, stress_abort_lost)),
                       "of_which_reject_completed": sorted(map(list, stress_abort_lost & reject_completed_ids))},
        "P2_bit_identical_all_completed_abort_cells": d1,
        "P3_stress_gates_reject_ge_abort": stress_gates["reject_leaf"] >= stress_gates["abort"],
        "P3_detail": stress_gates,
        "P4_rescued_max_abs_z_le_3": all((x["max_abs_z"] or 0) <= 3 for x in rescued) if rescued else None,
        "P5_rescued_ge1_retained_divergence": all((x["divergences"] or 0) >= 1 for x in rescued) if rescued else None,
        "P6_funnel_passes_both_arms": funnel_pass["abort"] and funnel_pass["reject_leaf"],
    }
    summary = {
        "schema": "nonfinite-policy-requalification-v1-summary",
        "missing_cells": missing, "n_cells_recorded": len(rec), "n_cells_manifest": len(cells),
        "total_cells": total_cells, "total_completed": total_completed,
        "fingerprint": {"completed_abort_cells": fingerprint_cells, "bit_identical": fingerprint_identical,
                        "differing": fingerprint_diffs, "reject_lost_where_abort_completed": lost_by_reject_only},
        "rescued": rescued, "per_block": per_block,
        "house": {"block": house, "geomean_min_bulk_ess_per_gradient": geo,
                  "geomean_ratio_reject_over_abort": (geo["reject_leaf"] / geo["abort"]) if geo["abort"] and geo["reject_leaf"] else None,
                  "gates_passed": {arm: passed(arm, [house]) for arm in ARMS}, "per_model": house_models},
        "funnel": funnel, "funnel_pass": funnel_pass, "stress_gates_passed": stress_gates,
        "decision": decision, "predictions": preds, "pairs": pair_rows,
    }
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    # table
    lines = ["# WP54 results table", "",
             "Every pair of cells (abort, reject_leaf). `nfr` = nonfinite-position rejections (RejectLeaf leaves); "
             "`div` = retained divergences; `ident` = draws bit-identical (only defined where abort completed).", "",
             "| block | model | seed | abort | reject_leaf | ident | rl nfr | rl div | rl max abs z | rl gates |",
             "|---|---|---:|---|---|---|---:|---:|---:|---|"]
    for row in pair_rows:
        a, r = row["abort"], row["reject_leaf"]

        def st(x):
            if x["status"] != "ok":
                return x["status"]
            if row["model"] == "funnel":
                return f"ok z {x['tail_mass']['z']:+.2f}"
            return f"ok {'pass' if x['passed'] else 'fail'} z {x['max_abs_z']:.2f}"
        fg = "" if r["status"] != "ok" else ",".join(k for k, v in r["gates"].items() if not v) or "all"
        lines.append(f"| {row['block']} | {row['model']} | {row['seed']} | {st(a)} | {st(r)} | {row['bit_identical']} | "
                     f"{r.get('nonfinite_position_rejections')} | {r.get('divergences')} | "
                     f"{'' if r.get('max_abs_z') is None else round(r['max_abs_z'], 2)} | {fg} |")
    lines += ["", f"Completed: abort {total_completed['abort']}/{total_cells['abort']}, "
              f"reject_leaf {total_completed['reject_leaf']}/{total_cells['reject_leaf']}.",
              f"Fingerprint: {fingerprint_identical}/{fingerprint_cells} completed-abort cells bit-identical.",
              f"House geomean min bulk ESS/gradient: abort {geo['abort']}, reject_leaf {geo['reject_leaf']}.",
              f"Decision: {json.dumps(decision)}"]
    (ART / "results-table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("total_completed", "fingerprint", "decision", "predictions", "stress_gates_passed", "funnel_pass")}, indent=1))
    print(json.dumps(summary["house"]["geomean_min_bulk_ess_per_gradient"]), summary["house"]["gates_passed"])
    print(json.dumps(rescued, indent=1))


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "manifest":
        for i, c in enumerate(manifest()):
            print(i, c["id"], c.get("timeout", ""))
    elif cmd == "smoke":
        smoke()
    elif cmd == "run":
        run_all()
    elif cmd == "analyze":
        analyze()
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
