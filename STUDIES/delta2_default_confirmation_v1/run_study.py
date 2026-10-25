#!/usr/bin/env python3
"""WP63 delta2_default_confirmation_v1 driver: `default` (delta 1) vs `delta2`, paired by seed.

    python run_study.py run       # blocks A, B, C in protocol order (resumable; never reruns a cell)
    python run_study.py analyze   # artifacts/summary.json + artifacts/results-table.md

Block A/B cells write artifacts/cells/<block>-<model>-<arm>-<seed>.json (metrics, no draws);
constrained draws go to artifacts/draws/ (uncommitted). Block C writes artifacts/funnel/<arm>-<seed>.json.
A failure is a cell with status != "ok"; it is never rerun.
"""
from __future__ import annotations

import functools
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
REPO = HERE.parent.parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
SMOKE = bool(os.environ.get("WP63_SMOKE_ART"))
ART = Path(os.environ["WP63_SMOKE_ART"]) if SMOKE else HERE / "artifacts"
CELLS = ART / "cells"
DRAWS = ART / "draws"
FUNNEL = ART / "funnel"
MODELS = HERE / "models"
PDB_PATH = (HERE / PROTOCOL["posteriordb"]["path"]).resolve()
HARNESS = HERE / "target" / "release" / "delta2-confirmation.exe"
FUNNEL_BIN = HERE / "target" / "release" / "funnel.exe"
ARMS = PROTOCOL["arms_order"]
TIMEOUT = PROTOCOL["cell_timeout_seconds"]
BLOCKS = PROTOCOL["blocks"]
if SMOKE:  # smoke: one model, one non-evidence seed, short funnel; never evidence
    BLOCKS = {"A": {"models": ["eight_schools-eight_schools_noncentered"], "seeds": [630691]},
              "B": {"models": ["eight_schools-eight_schools_noncentered"], "seeds": [630692]},
              "C": {"seeds": [630693], "warmup": 2000, "draws": 20000}}
A_MODELS, A_SEEDS = BLOCKS["A"]["models"], BLOCKS["A"]["seeds"]
B_MODELS, B_SEEDS = BLOCKS["B"]["models"], BLOCKS["B"]["seeds"]
C_SEEDS = BLOCKS["C"]["seeds"]
EXACT_TAIL = 0.0477903522728147


def short(model: str) -> str:
    return model.replace("-", "__")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def check_commit() -> str:
    if SMOKE:
        return "smoke-test-not-evidence"
    commit = PROTOCOL["source_commit_under_test"]
    diff = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", commit, "HEAD", "--",
                           "src", "integrations", "Cargo.toml", "tests"], capture_output=True)
    dirty = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "HEAD", "--", "src", "integrations", "Cargo.toml", "tests"],
                           capture_output=True)
    if diff.returncode != 0 or dirty.returncode != 0:
        raise SystemExit(f"library source differs from the commit under test {commit}")
    for f in ("PREREGISTRATION.md", "protocol.json", "run_study.py", "src/main.rs", "src/bin/funnel.rs"):
        tracked = subprocess.run(["git", "-C", str(REPO), "ls-files", "--error-unmatch", str(HERE / f)], capture_output=True)
        changed = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "HEAD", "--", str(HERE / f)], capture_output=True)
        if tracked.returncode != 0 or changed.returncode != 0:
            raise SystemExit(f"{f} must be committed (and unchanged) before the first evidence cell")
    return commit


def bridgestan_name(name: str) -> str:
    parts = name.split(".")
    if len(parts) == 1 or not all(p.isdigit() for p in parts[1:]):
        return name
    return f"{parts[0]}[{','.join(parts[1:])}]"


def arviz_stats(arr: np.ndarray) -> dict:
    import arviz as az

    ds = az.convert_to_dataset({"p": arr})
    with np.errstate(all="ignore"):
        bulk = np.asarray(az.ess(ds, method="bulk").p.values, dtype=float)
        tail = np.asarray(az.ess(ds, method="tail", prob=(0.05, 0.95)).p.values, dtype=float)
        rhat = np.asarray(az.rhat(ds, method="rank").p.values, dtype=float)
        mcse = np.asarray(az.mcse(ds, method="mean").p.values, dtype=float)
    flat = arr.reshape(-1, arr.shape[-1])
    return {"mean": flat.mean(0), "sd": flat.std(0, ddof=1), "bulk_ess": bulk, "tail_ess": tail, "rhat": rhat, "mcse": mcse}


@functools.lru_cache(maxsize=None)
def reference(model: str) -> dict:
    from posteriordb import PosteriorDatabase

    ref = PosteriorDatabase(str(PDB_PATH)).posterior(model).reference_draws()
    names = list(ref[0].keys())
    arr = np.transpose(np.asarray([[c[n] for n in names] for c in ref], dtype=np.float64), (0, 2, 1))
    return {"names": names, **arviz_stats(arr)}


@functools.lru_cache(maxsize=None)
def bridgestan_model(model: str):
    import bridgestan as bs

    bs.compile.windows_dll_path_setup()
    return bs.StanModel(str(MODELS / f"{short(model)}_model.so"),
                        data=(MODELS / f"{short(model)}.data.json").read_text(encoding="utf-8"), seed=1)


def failure(block: str, model: str, arm: str, seed: int, status: str, message: str) -> dict:
    return {"schema": "delta2-confirmation-v1-cell-metrics", "block": block, "model": model, "arm": arm, "seed": seed,
            "status": status, "error": message, "passed": False, "gates": {"no_sampler_error": False}}


def run_cell(block: str, model: str, arm: str, seed: int) -> dict:
    ref = reference(model)
    so, data = MODELS / f"{short(model)}_model.so", MODELS / f"{short(model)}.data.json"
    DRAWS.mkdir(parents=True, exist_ok=True)
    raw = DRAWS / f"{block}-{short(model)}-{arm}-{seed}.raw.json"
    if raw.exists():
        raw.unlink()
    try:
        cp = subprocess.run([str(HARNESS), str(so), str(data), arm, str(seed), str(raw), str(PROTOCOL["threads"])],
                            capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return failure(block, model, arm, seed, "timeout", f"exceeded {TIMEOUT}s")
    if cp.returncode != 0 or not raw.exists():
        return failure(block, model, arm, seed, "error", cp.stderr.strip()[-2000:] or f"exit {cp.returncode}")
    out = json.loads(raw.read_text(encoding="utf-8"))
    if out.get("status") != "ok":
        return failure(block, model, arm, seed, "error", out.get("error", "unknown"))
    sm = bridgestan_model(model)
    cnames = [bridgestan_name(n) for n in sm.param_names(include_tp=True, include_gq=False)]
    unc = np.asarray([c["samples"] for c in out["chains_data"]], dtype=np.float64)
    con = np.empty(unc.shape[:2] + (len(cnames),))
    for c in range(unc.shape[0]):
        for d in range(unc.shape[1]):
            con[c, d] = sm.param_constrain(unc[c, d], include_tp=True, include_gq=False)
    index = {n: i for i, n in enumerate(cnames)}
    names = ref["names"]
    draws = con[:, :, [index[n] for n in names]]
    st = arviz_stats(draws)
    chains = out["chains_data"]
    grads_total = out["target_calls_total"]
    div = sum(c["divergences"] for c in chains)
    min_bulk, min_tail, max_rhat = float(np.nanmin(st["bulk_ess"])), float(np.nanmin(st["tail_ess"])), float(np.nanmax(st["rhat"]))
    z = (st["mean"] - ref["mean"]) / np.sqrt(st["mcse"] ** 2 + ref["mcse"] ** 2)
    g = PROTOCOL["gates"]
    gates = {"max_rank_rhat": max_rhat <= g["max_rank_rhat"], "min_bulk_ess": min_bulk >= g["min_bulk_ess"],
             "min_tail_ess": min_tail >= g["min_tail_ess"], "sampling_divergences": div == 0,
             "finite_draws": bool(np.isfinite(draws).all()), "no_sampler_error": True}
    steps = [c["final_step_size"] for c in chains]
    med_step = statistics.median(steps)
    cell = {
        "schema": "delta2-confirmation-v1-cell-metrics", "block": block, "model": model, "arm": arm, "seed": seed, "status": "ok",
        "wall_seconds": out["wall_seconds"], "gradients_total": grads_total,
        "gradients_warmup": sum(c["warmup_target_calls"] for c in chains),
        "gradients_sampling": sum(c["retained_target_calls"] for c in chains),
        "start_search_calls": out["init"]["start_search_calls"],
        "min_bulk_ess": min_bulk, "min_tail_ess": min_tail, "max_rank_rhat": max_rhat, "divergences": div,
        "warmup_divergences": sum(c["warmup_divergences"] for c in chains),
        "argmin_bulk_ess": names[int(np.nanargmin(st["bulk_ess"]))],
        "min_bulk_ess_per_gradient": min_bulk / grads_total,
        "max_abs_z": float(np.nanmax(np.abs(z))), "argmax_abs_z": names[int(np.nanargmax(np.abs(z)))],
        "gates": gates, "passed": all(gates.values()),
        "final_max_error": [c["final_max_error"] for c in chains],
        "end_of_warmup_step": steps,
        "end_of_warmup_step_min_over_median": min(steps) / med_step if med_step else None,
        "max_depth_stops": sum(c["maximum_depth_stops"] for c in chains),
        "refinement_exhaustions": sum(c["refinement_exhaustions"] for c in chains),
        "retained_refinement_level_histogram": [sum(x) for x in zip(*[c["retained_refinement_level_histogram"] for c in chains])],
        "retained_depth_histogram": [sum(x) for x in zip(*[c["retained_depth_histogram"] for c in chains])],
        "nonfinite_position_rejections": sum(c["retained_work"]["nonfinite_position_rejections"] + c["warmup_work"]["nonfinite_position_rejections"] for c in chains),
        "chain_warnings": out.get("chain_warnings", []),
        "warmup_config_used": out.get("warmup_config_used"),
        "tuning": out["tuning"], "init": out["init"]["detail"], "defaults": out["defaults"], "execution": out.get("execution"),
        "algorithm_revision": out["algorithm_revision"],
    }
    np.savez_compressed(DRAWS / f"{block}-{short(model)}-{arm}-{seed}.npz", draws=draws, names=np.asarray(names), unconstrained=unc)
    raw.unlink()
    return cell


def cell_path(block: str, model: str, arm: str, seed: int) -> Path:
    return CELLS / f"{block}-{short(model)}-{arm}-{seed}.json"


def funnel_path(arm: str, seed: int) -> Path:
    return FUNNEL / f"{arm}-{seed}.json"


def run_block(block: str, models: list[str], seeds: list[int]) -> None:
    for model in models:
        log(f"== {block} {model}")
        for seed in seeds:
            for arm in ARMS:
                p = cell_path(block, model, arm, seed)
                if p.exists():
                    continue
                try:
                    cell = run_cell(block, model, arm, seed)
                except Exception as e:  # noqa: BLE001
                    cell = failure(block, model, arm, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
                p.write_text(json.dumps(cell, indent=1, sort_keys=True) + "\n", encoding="utf-8")
                if cell["status"] == "ok":
                    log(f"  {arm} {seed}: grads {cell['gradients_total']} minbulk {cell['min_bulk_ess']:.0f} mintail {cell['min_tail_ess']:.0f} "
                        f"rhat {cell['max_rank_rhat']:.4f} div {cell['divergences']} max|z| {cell['max_abs_z']:.2f} "
                        f"ess/grad {cell['min_bulk_ess_per_gradient']:.3e} passed {cell['passed']} wall {cell['wall_seconds']:.1f}s")
                else:
                    log(f"  {arm} {seed}: {cell['status']}: {cell['error'][:200]}")


def run_funnel() -> None:
    FUNNEL.mkdir(parents=True, exist_ok=True)
    c = BLOCKS["C"]
    log("== C funnel")
    for seed in C_SEEDS:
        for arm in ARMS:
            p = funnel_path(arm, seed)
            if p.exists() or p.with_suffix(".error.json").exists():
                continue
            try:
                cp = subprocess.run([str(FUNNEL_BIN), arm, str(c["warmup"]), str(c["draws"]), str(seed), str(p)],
                                    capture_output=True, text=True, timeout=TIMEOUT)
                ok = cp.returncode == 0 and p.exists()
                msg = cp.stderr.strip()[-2000:]
            except subprocess.TimeoutExpired:
                ok, msg = False, f"timeout {TIMEOUT}s"
            if not ok:
                p.with_suffix(".error.json").write_text(json.dumps({"arm": arm, "seed": seed, "status": "error", "error": msg}, indent=1) + "\n", encoding="utf-8")
                log(f"  {arm} {seed}: ERROR {msg[:200]}")
            else:
                log(f"  {msg.splitlines()[-1] if msg else arm}")


def run_all() -> None:
    log(f"commit under test: {check_commit()}")
    CELLS.mkdir(parents=True, exist_ok=True)
    machine = ART / "measured_on.json"
    if not machine.exists():
        machine.write_text(json.dumps({"platform": platform.platform(), "processor": platform.processor(),
                                       "cpu_count": os.cpu_count(), "python": sys.version.split()[0],
                                       "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                       "concurrency": "strictly sequential, one sampling process at a time",
                                       "note": "shared machine; walls contended"}, indent=2) + "\n", encoding="utf-8")
    run_block("A", A_MODELS, A_SEEDS)
    run_block("B", B_MODELS, B_SEEDS)
    run_funnel()
    log("done")


def geomean(xs) -> float:
    xs = [x for x in xs if x is not None and math.isfinite(x) and x > 0]
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs))) if xs else float("nan")


def load_cells() -> dict:
    cells: dict = {}
    for p in sorted(CELLS.glob("*.json")):
        c = json.loads(p.read_text(encoding="utf-8"))
        cells[(c["block"], c["model"], c["arm"], int(c["seed"]))] = c
    return cells


def primary(cells: dict, seeds: list[int]) -> tuple[float, dict]:
    """Geomean over the A models of each model's geomean of paired per-seed ratios delta2 / default."""
    per_model = {}
    for m in A_MODELS:
        ratios = {}
        for s in seeds:
            d, t = cells.get(("A", m, "default", s)), cells.get(("A", m, "delta2", s))
            if d and t and d["status"] == "ok" and t["status"] == "ok":
                ratios[s] = t["min_bulk_ess_per_gradient"] / d["min_bulk_ess_per_gradient"]
        per_model[m] = ratios
    return geomean([geomean(r.values()) for r in per_model.values() if r]), per_model


def funnel_summary() -> dict:
    out = {}
    for arm in ARMS:
        est, div, err, zs, caps, grads, ess_per_grad, tail6 = {}, {}, [], [], 0, [], [], []
        for s in C_SEEDS:
            p = funnel_path(arm, s)
            if not p.exists():
                err.append(s)
                continue
            f = json.loads(p.read_text(encoding="utf-8"))
            est[s] = f["tail_mass"]["estimate"]
            div[s] = sum(c["divergences"] for c in f["chains_data"])
            caps += sum(c.get("depth_caps", 0) for c in f["chains_data"])
            zs.append(f["tail_mass"]["z"])
            grads.append(f["target_calls_total"])
            ess_per_grad.append(f["min_bulk_ess_per_gradient"])
            tail6.append(f["tail_mass_6"]["estimate"])
        v = list(est.values())
        mean = statistics.fmean(v) if v else float("nan")
        se = statistics.stdev(v) / math.sqrt(len(v)) if len(v) > 1 else float("nan")
        out[arm] = {"n": len(v), "missing_or_error_seeds": err, "pooled_tail_mass": mean, "between_seed_se": se,
                    "per_seed": {str(k): x for k, x in est.items()}, "divergences_total": sum(div.values()),
                    "divergences_per_seed": {str(k): x for k, x in div.items()}, "div_free_seeds": sum(1 for x in div.values() if x == 0),
                    "seeds_abs_z_gt_2": sum(1 for z in zs if abs(z) > 2), "z_per_seed": zs, "depth_caps_total": caps,
                    "median_gradients": statistics.median(grads) if grads else None,
                    "geomean_min_ess_per_gradient": geomean(ess_per_grad),
                    "pooled_tail_mass_6": statistics.fmean(tail6) if tail6 else None,
                    "exact": EXACT_TAIL}
    return out


def analyze() -> None:
    cells = load_cells()
    g, per_model = primary(cells, A_SEEDS)
    loso = {str(s): primary(cells, [x for x in A_SEEDS if x != s])[0] for s in A_SEEDS}
    loso_min = min(loso.values())
    pooled_pairs = geomean([r for rs in per_model.values() for r in rs.values()])
    per_seed_geomean = {str(s): geomean([per_model[m][s] for m in A_MODELS if s in per_model[m]]) for s in A_SEEDS}

    def arm_cells(arm, blocks=("A", "B")):
        return [c for (b, m, a, s), c in cells.items() if a == arm and b in blocks]

    expected = {"A": len(A_MODELS) * len(A_SEEDS), "B": len(B_MODELS) * len(B_SEEDS)}
    passes = {arm: {"A": sum(c["passed"] for c in arm_cells(arm, ("A",))), "B": sum(c["passed"] for c in arm_cells(arm, ("B",))),
                    "AB": sum(c["passed"] for c in arm_cells(arm))} for arm in ARMS}
    errors = {arm: [f"{c['block']} {c['model']} {c['seed']}: {c['status']}" for c in arm_cells(arm) if c["status"] != "ok"] for arm in ARMS}
    z_over_4 = {arm: [f"{c['block']} {c['model']} {c['seed']} {c['argmax_abs_z']} {c['max_abs_z']:.2f}" for c in arm_cells(arm)
                      if c["passed"] and c["max_abs_z"] > 4] for arm in ARMS}
    passing_pairs = geomean([cells[("A", m, "delta2", s)]["min_bulk_ess_per_gradient"] / cells[("A", m, "default", s)]["min_bulk_ess_per_gradient"]
                             for m in A_MODELS for s in A_SEEDS
                             if cells.get(("A", m, "default", s), {}).get("passed") and cells.get(("A", m, "delta2", s), {}).get("passed")])
    fun = funnel_summary()
    fd, f2 = fun["default"], fun["delta2"]
    se_diff = math.sqrt(fd["between_seed_se"] ** 2 + f2["between_seed_se"] ** 2)
    diff = f2["pooled_tail_mass"] - fd["pooled_tail_mass"]
    complete = (all(len([c for c in arm_cells(a, (b,))]) == expected[b] for a in ARMS for b in ("A", "B"))
                and fd["n"] == len(C_SEEDS) and f2["n"] == len(C_SEEDS))
    div_ratio = f2["divergences_total"] / fd["divergences_total"] if fd["divergences_total"] else (0.0 if f2["divergences_total"] == 0 else float("inf"))
    rule = {
        "R1_paired_geomean_ge_1.08": g >= 1.08,
        "R2_loso_min_ge_1.00": loso_min >= 1.00,
        "R3_gates_AB_delta2_ge_default_minus_1": passes["delta2"]["AB"] >= passes["default"]["AB"] - 1,
        "R4_no_delta2_passing_cell_abs_z_gt_4": not z_over_4["delta2"],
        "R5_funnel_tail_not_lower_by_more_than_1_se_diff": diff >= -se_diff and not f2["missing_or_error_seeds"],
        "R6_funnel_divergences_le_1.5x": f2["divergences_total"] <= 1.5 * fd["divergences_total"] and not f2["missing_or_error_seeds"],
    }
    flip = all(rule.values()) and complete
    predictions = {
        "P1_paired_geomean_in_[1.05,1.15]": 1.05 <= g <= 1.15,
        "P2_loso_min_ge_1.0": loso_min >= 1.0,
        "P3_gates_within_1": abs(passes["delta2"]["AB"] - passes["default"]["AB"]) <= 1,
        "P4_funnel_tail_within_1_se_diff": abs(diff) <= se_diff,
        "P5_funnel_divergences_within_1.5x": (fd["divergences_total"] == 0 and f2["divergences_total"] == 0) or (1 / 1.5 <= div_ratio <= 1.5),
    }
    rows = {}
    for m in A_MODELS + [x for x in B_MODELS if x not in A_MODELS]:
        row = {"ratio_geomean_A": geomean(per_model.get(m, {}).values()) if m in per_model else None,
               "per_seed_ratio_A": {str(k): v for k, v in per_model.get(m, {}).items()}}
        for arm in ARMS:
            cs = [c for (b, mm, a, s), c in cells.items() if mm == m and a == arm]
            ok = [c for c in cs if c["status"] == "ok"]
            row[arm] = {"n": len(cs), "passed": sum(c["passed"] for c in cs),
                        "passed_A": sum(c["passed"] for c in cs if c["block"] == "A"),
                        "passed_B": sum(c["passed"] for c in cs if c["block"] == "B"),
                        "errors": [c["seed"] for c in cs if c["status"] != "ok"],
                        "divergent_cells": sum(1 for c in ok if c["divergences"] > 0),
                        "max_abs_z_max": max((c["max_abs_z"] for c in ok), default=None),
                        "gradients_median": statistics.median([c["gradients_total"] for c in ok]) if ok else None,
                        "ess_per_grad_median": statistics.median([c["min_bulk_ess_per_gradient"] for c in ok]) if ok else None,
                        "failed_gates": sorted({k for c in cs for k, v in c["gates"].items() if not v})}
        rows[m] = row
    summary = {"schema": "delta2-confirmation-v1-summary", "commit": PROTOCOL["source_commit_under_test"], "smoke": SMOKE,
               "complete": complete, "paired_geomean_A": g, "loso": loso, "loso_min": loso_min,
               "pooled_geomean_all_pairs_A": pooled_pairs, "passing_pairs_geomean_A": passing_pairs,
               "per_seed_geomean_A": per_seed_geomean,
               "models_below_1": sum(1 for m in A_MODELS if rows[m]["ratio_geomean_A"] is not None and rows[m]["ratio_geomean_A"] < 1),
               "passes": passes, "errors": errors, "passing_cells_abs_z_gt_4": z_over_4,
               "funnel": fun, "funnel_tail_diff_delta2_minus_default": diff, "funnel_se_diff": se_diff,
               "funnel_divergence_ratio": div_ratio,
               "decision_rule": rule, "flip": flip,
               "decision": "FLIP: make delta = 2 the default" if flip else "NO FLIP: document and change nothing",
               "predictions": predictions, "per_model": rows,
               "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
               "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    def f(x, fmt):
        return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)

    lines = ["# delta2_default_confirmation_v1 (WP63) — results", "",
             f"Commit `{summary['commit']}`; ratio = delta2 / default min-bulk-ESS per gradient, paired by seed.", "",
             "| model | ratio geomean (A) | per-seed ratios (A) | passes default / delta2 (A+B) | divergent cells default / delta2 | max abs z default / delta2 | grads median default / delta2 | failed gates default ; delta2 |",
             "|---|---:|---|---|---|---|---|---|"]
    for m, r in rows.items():
        d, t = r["default"], r["delta2"]
        lines.append(f"| {m} | **{f(r['ratio_geomean_A'], '.3f')}** | {', '.join(f'{x:.2f}' for x in r['per_seed_ratio_A'].values())} | "
                     f"{d['passed']}/{d['n']} / {t['passed']}/{t['n']} | {d['divergent_cells']} / {t['divergent_cells']} | "
                     f"{f(d['max_abs_z_max'], '.2f')} / {f(t['max_abs_z_max'], '.2f')} | {f(d['gradients_median'], ',.0f')} / {f(t['gradients_median'], ',.0f')} | "
                     f"{', '.join(d['failed_gates']) or '-'} ; {', '.join(t['failed_gates']) or '-'} |")
    lines += ["", f"**Paired geomean over A (17 models): {f(g, '.3f')}**; LOSO {', '.join(f'{k}: {v:.3f}' for k, v in loso.items())} (min {loso_min:.3f}); "
              f"pooled over all A pairs {f(pooled_pairs, '.3f')}; passing pairs only {f(passing_pairs, '.3f')}; per-seed geomeans {', '.join(f'{k}: {v:.3f}' for k, v in per_seed_geomean.items())}",
              f"Gates: default A {passes['default']['A']}/{expected['A']}, B {passes['default']['B']}/{expected['B']}, A+B {passes['default']['AB']}; "
              f"delta2 A {passes['delta2']['A']}/{expected['A']}, B {passes['delta2']['B']}/{expected['B']}, A+B {passes['delta2']['AB']}",
              f"Errors: {errors}", f"Passing cells with |z| > 4: {z_over_4}", "",
              "| funnel arm | seeds | pooled P(omega<-5) | between-seed SE | seeds abs z > 2 | divergences (div-free seeds) | depth caps | median gradients | geomean min ESS / gradient | pooled P(omega<-6) |",
              "|---|---:|---:|---:|---:|---|---:|---:|---:|---:|"]
    for arm in ARMS:
        x = fun[arm]
        lines.append(f"| {arm} | {x['n']} | {f(x['pooled_tail_mass'], '.4f')} | {f(x['between_seed_se'], '.4f')} | {x['seeds_abs_z_gt_2']} | {x['divergences_total']} ({x['div_free_seeds']}) | "
                     f"{x['depth_caps_total']} | {f(x['median_gradients'], ',.0f')} | {f(x['geomean_min_ess_per_gradient'], '.3e')} | {f(x['pooled_tail_mass_6'], '.4f')} |")
    lines += ["", f"Funnel: delta2 - default = {diff:+.4f}, SE of the difference {se_diff:.4f} (exact 0.0478); divergence ratio {f(div_ratio, '.2f')}", "",
              "Decision rule: " + "; ".join(f"{k} {'PASS' if v else 'FAIL'}" for k, v in rule.items()),
              f"**Decision (frozen rule): {summary['decision']}** (complete: {complete})", "",
              "Predictions: " + "; ".join(f"{k} {'held' if v else 'failed'}" for k, v in predictions.items())]
    (ART / "results-table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "run":
        run_all()
    elif a[0] == "analyze":
        analyze()
    else:
        raise SystemExit(__doc__)
