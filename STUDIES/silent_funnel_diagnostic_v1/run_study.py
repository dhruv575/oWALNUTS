#!/usr/bin/env python3
"""WP55 silent-funnel diagnostic study driver (STUDIES/silent_funnel_diagnostic_v1).

    python run_study.py prepare    # check models, load every reference (CmdStan references must exist)
    python run_study.py run        # every planned cell in protocol order, strictly sequential, launched once
    python run_study.py analyze    # artifacts/summary.json + artifacts/results-table.md

Each cell launches the compiled harness once (`silent-funnel-cell`), writes the raw output to
`artifacts/raw/` (ignored; unconstrained draws), constrains the draws through BridgeStan and writes
`artifacts/cells/<model>-<seed>.json` (gates, z, per-chain refinement / step / divergence statistics,
WP44 warnings). A launch marker in `artifacts/launches/` forbids a second launch of the same cell.
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
RAW = ART / "raw"
LAUNCHES = ART / "launches"
MODELS = HERE / "models"
PDB_PATH = Path(PROTOCOL["posteriordb"]["path"])
HARNESS = HERE / "target" / "release" / "silent-funnel-cell.exe"
TIMEOUT = PROTOCOL["cell_timeout_seconds"]
THREADS = PROTOCOL["threads"]
GATES = PROTOCOL["gates"]
SEEDS = PROTOCOL["seeds"]
POS, NEG = PROTOCOL["positives"], PROTOCOL["negatives"]
FUNNEL = "funnel10"
FUNNEL_TAIL = 0.0477903522728147
CMDSTAN_REFS = {spec["cell_model"]: key for key, spec in PROTOCOL["references"]["models"].items()}
Z_LIMIT = 3.0


def short(model: str) -> str:
    return model.replace("-", "__")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def plan() -> list[tuple[str, int, str]]:
    # amendment A1: radon (the last positive) runs after the negatives
    late = ["radon_all-radon_hierarchical_intercept_centered"]
    early = [m for m in POS if m not in late]
    return ([(m, s, "positive") for m in early for s in SEEDS] + [(m, s, "negative") for m in NEG for s in SEEDS]
            + [(m, s, "positive") for m in late for s in SEEDS])


# --------------------------------------------------------------------------- references


def bridgestan_name(name: str) -> str:
    parts = name.split(".")
    if len(parts) == 1 or not all(p.isdigit() for p in parts[1:]):
        return name
    return f"{parts[0]}[{','.join(parts[1:])}]"


def arviz_stats(arr: np.ndarray) -> dict:
    import arviz as az

    ds = az.convert_to_dataset({"p": arr})
    flat = arr.reshape(-1, arr.shape[-1])
    return {
        "mean": flat.mean(0),
        "sd": flat.std(0, ddof=1),
        "bulk_ess": np.asarray(az.ess(ds, method="bulk").p.values, dtype=float),
        "tail_ess": np.asarray(az.ess(ds, method="tail", prob=(0.05, 0.95)).p.values, dtype=float),
        "rhat": np.asarray(az.rhat(ds, method="rank").p.values, dtype=float),
        "mcse": np.asarray(az.mcse(ds, method="mean").p.values, dtype=float),
    }


def reference(model: str) -> dict:
    if model == FUNNEL:
        names = ["omega"] + [f"x[{i}]" for i in range(1, 10)]
        return {"names": names, "mean": np.zeros(10), "sd": np.array([3.0] + [math.exp(2.25)] * 9),
                "mcse": np.zeros(10), "source": "exact", "accepted": True}
    if model in CMDSTAN_REFS:
        path = ART / "reference" / f"{CMDSTAN_REFS[model]}.json"
        r = json.loads(path.read_text(encoding="utf-8"))
        return {"names": r["names"], "mean": np.asarray(r["mean"]), "sd": np.asarray(r["sd"]),
                "mcse": np.asarray(r["mcse"]), "source": f"cmdstan:{path.name}", "accepted": r["accepted"]}
    from posteriordb import PosteriorDatabase

    ref = PosteriorDatabase(str(PDB_PATH)).posterior(model).reference_draws()
    names = list(ref[0].keys())
    arr = np.transpose(np.asarray([[c[n] for n in names] for c in ref], dtype=np.float64), (0, 2, 1))
    return {"names": names, **arviz_stats(arr), "source": "posteriordb", "accepted": True}


def prepare() -> None:
    for model in POS + NEG:
        if model != FUNNEL:
            for suffix in ("_model.so", ".data.json", ".stan"):
                p = MODELS / f"{short(model)}{suffix}"
                if not p.exists():
                    raise SystemExit(f"missing {p}")
        r = reference(model)
        log(f"{model}: reference {r['source']} accepted={r['accepted']} params={len(r['names'])}")
    log("prepared")


# --------------------------------------------------------------------------- per-chain statistics


def median7(values) -> float:
    v = sorted(values)
    n = len(v)
    if n == 0:
        return float("nan")
    r = 0.5 * (n - 1)
    lo, hi = math.floor(r), math.ceil(r)
    return v[lo] + (r - lo) * (v[hi] - v[lo])


def chain_stats(chains: list[dict], warnings: list[dict]) -> list[dict]:
    out = []
    w_steps = [(c["warmup_end"] or {}).get("step_size", float("nan")) for c in chains]
    med_step = median7([s for s in w_steps if s is not None and math.isfinite(s)])
    for k, c in enumerate(chains):
        w = c["retained_work"]
        lb = w["refinement_level_built"]
        built = w["leaves_built"]
        refined = built - (lb[0] if lb else 0)
        depth_sum = sum(l * n for l, n in enumerate(lb))
        step = w_steps[k]
        out.append({
            "chain": k,
            "refined_leaf_rate": refined / built if built else float("nan"),
            "mean_refinement_depth": depth_sum / built if built else float("nan"),
            "mean_refinement_depth_given_refined": depth_sum / refined if refined else 0.0,
            "leaves_built": built, "refined_leaves": refined, "refinement_level_built": lb,
            "end_of_warmup_step": step, "final_step_size": c["final_step_size"],
            "step_collapse_factor": med_step / step if step and math.isfinite(step) and step > 0 else float("nan"),
            "retained_divergences": w["divergences"], "warmup_divergences": c["warmup_work"]["divergences"],
            "retained_depth_caps": w["maximum_depth_stops"],
            "retained_refinement_exhaustions": w["refinement_exhaustion_stops"],
            "retained_reverse_coarser_stops": w["reverse_coarser_stops"],
            "retained_mean_tree_depth": c["retained_mean_tree_depth"],
            "retained_target_calls": w["target_calls_total"], "warmup_target_calls": c["warmup_work"]["target_calls_total"],
            "wp44_warnings": sorted({x["check"] for x in warnings if x["chain"] == k}),
            "warmup_step_trace_every_25": c["warmup_step_trace_every_25"],
        })
    return out


# --------------------------------------------------------------------------- cells


def failure(model: str, seed: int, block: str, status: str, message: str, **extra) -> dict:
    return {"schema": "silent-funnel-diagnostic-v1-cell-metrics", "model": model, "seed": seed,
            "block": block, "status": status, "error": message, "wrong": True, **extra}


def constrained_draws(model: str, out: dict, ref: dict) -> np.ndarray:
    unc = np.asarray([c["samples"] for c in out["chains_data"]], dtype=np.float64)
    if model == FUNNEL:
        return unc
    import bridgestan as bs

    so = MODELS / f"{short(model)}_model.so"
    data = MODELS / f"{short(model)}.data.json"
    bs.compile.windows_dll_path_setup()
    sm = bs.StanModel(str(so), data=data.read_text(encoding="utf-8"), seed=1)
    cnames = [bridgestan_name(n) for n in sm.param_names(include_tp=True, include_gq=False)]
    con = np.empty(unc.shape[:2] + (len(cnames),))
    for c in range(unc.shape[0]):
        for d in range(unc.shape[1]):
            con[c, d] = sm.param_constrain(unc[c, d], include_tp=True, include_gq=False)
    index = {n: i for i, n in enumerate(cnames)}
    missing = [n for n in ref["names"] if n not in index]
    if missing:
        raise ValueError(f"reference parameters missing: {missing[:5]}")
    return con[:, :, [index[n] for n in ref["names"]]]


def analyse_cell(model: str, seed: int, block: str, raw_path: Path, ref: dict, wall_process: float) -> dict:
    import arviz as az

    out = json.loads(raw_path.read_text(encoding="utf-8"))
    if out.get("status") != "ok":
        return failure(model, seed, block, "sampler_error", out.get("error", "unknown"), stage=out.get("stage"))
    chains = out["chains_data"]
    draws = constrained_draws(model, out, ref)
    finite = bool(np.isfinite(draws).all())
    st = arviz_stats(draws)
    z = (st["mean"] - ref["mean"]) / np.sqrt(st["mcse"] ** 2 + ref["mcse"] ** 2)
    extra_z = {}
    if model == FUNNEL:
        ind = (draws[:, :, 0] < -5.0).astype(float)
        mcse = float(az.mcse(az.convert_to_dataset({"t": ind}), method="mean").t.values)
        est = float(ind.mean())
        extra_z["tail_mass"] = {"estimate": est, "mcse": mcse, "exact": FUNNEL_TAIL,
                                "z": (est - FUNNEL_TAIL) / mcse if mcse > 0 else float("inf")}
    abs_z = [float(x) for x in np.abs(z)] + [abs(v["z"]) for v in extra_z.values()]
    max_abs_z = float(np.nanmax(abs_z))
    divergences = sum(c["retained_work"]["divergences"] for c in chains)
    max_rhat = float(np.nanmax(st["rhat"]))
    min_bulk = float(np.nanmin(st["bulk_ess"]))
    min_tail = float(np.nanmin(st["tail_ess"]))
    gates = {
        "max_rank_rhat": max_rhat <= GATES["max_rank_rhat"],
        "min_bulk_ess": min_bulk >= GATES["min_bulk_ess"],
        "min_tail_ess": min_tail >= GATES["min_tail_ess"],
        "sampling_divergences": divergences == 0,
        "finite_draws": finite,
        "no_sampler_error": True,
    }
    z_used = bool(ref["accepted"])
    wrong = (not all(gates.values())) or (z_used and max_abs_z > Z_LIMIT)
    chain_dsd = np.abs(draws.mean(axis=1) - ref["mean"][None, :]) / ref["sd"][None, :]
    stats = chain_stats(chains, out["chain_warnings"])
    names = ref["names"]
    worst = int(np.nanargmax(np.abs(z)))
    return {
        "schema": "silent-funnel-diagnostic-v1-cell-metrics",
        "model": model, "seed": seed, "block": block, "status": "ok",
        "wall_seconds_contended": out["wall_seconds"], "process_seconds_contended": wall_process,
        "gradients_total": out["target_calls_total"],
        "reference_source": ref["source"], "reference_accepted": ref["accepted"],
        "divergences": divergences, "min_bulk_ess": min_bulk, "min_tail_ess": min_tail,
        "max_rank_rhat": max_rhat, "max_abs_z": max_abs_z, "argmax_abs_z": names[worst],
        "argmin_bulk_ess": names[int(np.nanargmin(st["bulk_ess"]))], "extra_z": extra_z,
        "max_chain_dmean_ref_sd": [float(np.nanmax(chain_dsd[c])) for c in range(chain_dsd.shape[0])],
        "gates": gates, "passed": all(gates.values()), "wrong": bool(wrong),
        "chain_stats": stats,
        "wp44_warning_lines": out["warning_lines"], "wp44_warnings": out["chain_warnings"],
        "wp44_fired": len(out["chain_warnings"]) > 0,
        "chain_disagreement": out["chain_disagreement"],
        "algorithm_revision": out["algorithm_revision"],
        "parameters_worst": {names[i]: {"mean": float(st["mean"][i]), "z": float(z[i]), "rhat": float(st["rhat"][i]),
                                        "bulk_ess": float(st["bulk_ess"][i]), "tail_ess": float(st["tail_ess"][i]),
                                        "chain_dmean_ref_sd": [float(x) for x in chain_dsd[:, i]]}
                             for i in sorted(set(np.argsort(-np.nan_to_num(np.abs(z)))[:5].tolist()
                                                 + np.argsort(np.nan_to_num(st["bulk_ess"], nan=1e18))[:5].tolist()))},
    }


def run_cell(model: str, seed: int, block: str, ref: dict) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    raw = RAW / f"{short(model)}-{seed}.json"
    if model == FUNNEL:
        cmd = [str(HARNESS), "funnel", "-", str(seed), str(raw), str(THREADS)]
    else:
        cmd = [str(HARNESS), str(MODELS / f"{short(model)}_model.so"), str(MODELS / f"{short(model)}.data.json"),
               str(seed), str(raw), str(THREADS)]
    t = time.perf_counter()
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return failure(model, seed, block, "timeout", f"exceeded {TIMEOUT}s")
    wall = time.perf_counter() - t
    (ART / "stderr").mkdir(parents=True, exist_ok=True)
    (ART / "stderr" / f"{short(model)}-{seed}.txt").write_text(cp.stderr, encoding="utf-8")
    if not raw.exists():
        return failure(model, seed, block, "process_error", f"exit {cp.returncode}: {cp.stderr.strip()[-1500:]}")
    try:
        cell = analyse_cell(model, seed, block, raw, ref, wall)
    except Exception as e:  # noqa: BLE001
        return failure(model, seed, block, "analysis_error", f"{e}\n{traceback.format_exc()[-1500:]}")
    cell["process_returncode"] = cp.returncode
    return cell


def run_all() -> None:
    if not HARNESS.exists():
        raise SystemExit("build the harness first")
    ART.mkdir(exist_ok=True)
    machine = ART / "measured_on.json"
    if not machine.exists():
        machine.write_text(json.dumps({
            "platform": platform.platform(), "processor": platform.processor(), "cpu_count": os.cpu_count(),
            "python": sys.version.split()[0], "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "note": "shared 16-core machine, up to six concurrent study agents; walls are contended upper bounds",
        }, indent=2) + "\n", encoding="utf-8")
    CELLS.mkdir(parents=True, exist_ok=True)
    LAUNCHES.mkdir(parents=True, exist_ok=True)
    refs: dict[str, dict] = {}
    for model, seed, block in plan():
        marker = LAUNCHES / f"{short(model)}-{seed}.launched"
        if marker.exists():
            continue  # launched once already: never relaunch, whatever the outcome
        if model not in refs:
            refs[model] = reference(model)
        with open(marker, "x", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + "\n")
        log(f"{model} {seed} ({block})")
        cell = run_cell(model, seed, block, refs[model])
        (CELLS / f"{short(model)}-{seed}.json").write_text(json.dumps(cell, indent=1, sort_keys=True) + "\n",
                                                          encoding="utf-8")
        if cell["status"] == "ok":
            r = [round(c["refined_leaf_rate"], 4) for c in cell["chain_stats"]]
            s = [round(c["step_collapse_factor"], 2) for c in cell["chain_stats"]]
            log(f"  passed {cell['passed']} wrong {cell['wrong']} |z| {cell['max_abs_z']:.2f} rhat {cell['max_rank_rhat']:.3f} "
                f"bulk {cell['min_bulk_ess']:.0f} tail {cell['min_tail_ess']:.0f} div {cell['divergences']} "
                f"R {r} S {s} wp44 {[w['check'] + str(w['chain']) for w in cell['wp44_warnings']]} "
                f"wall {cell['wall_seconds_contended']:.0f}s")
        else:
            log(f"  {cell['status']}: {cell.get('error', '')[:300]}")


# --------------------------------------------------------------------------- analysis


def load_cells() -> list[dict]:
    cells = []
    for model, seed, block in plan():
        p = CELLS / f"{short(model)}-{seed}.json"
        if p.exists():
            cells.append(json.loads(p.read_text(encoding="utf-8")))
    return cells


def fires(cell: dict, cand: str, t_r: float, t_s: float) -> list[int]:
    out = set()
    for c in cell["chain_stats"]:
        r, s = c["refined_leaf_rate"], c["step_collapse_factor"]
        if cand in ("C_R", "C_RS") and math.isfinite(r) and r > t_r:
            out.add(c["chain"])
        if cand in ("C_S", "C_RS") and math.isfinite(s) and s > t_s:
            out.add(c["chain"])
    return sorted(out)


def confusion(cells: list[dict], fire) -> dict:
    pos = [c for c in cells if c["status"] == "ok" and c["block"] == "positive" and c["wrong"]]
    neg = [c for c in cells if c["status"] == "ok" and c["block"] == "negative" and not c["wrong"]]
    tp = [f"{c['model']}/{c['seed']}" for c in pos if fire(c)]
    fn = [f"{c['model']}/{c['seed']}" for c in pos if not fire(c)]
    fp = [f"{c['model']}/{c['seed']}" for c in neg if fire(c)]
    tn = len(neg) - len(fp)
    cell_level = {"TP": len(tp), "FN": len(fn), "FP": len(fp), "TN": tn,
                  "sensitivity": len(tp) / len(pos) if pos else float("nan"),
                  "specificity": tn / len(neg) if neg else float("nan"), "false_negatives": fn, "false_positives": fp}
    # model level
    pm_tp = pm_fn = pm_fp = pm_tn = 0
    per_model = {}
    for block, models in (("positive", POS), ("negative", NEG)):
        for m in models:
            mc = [c for c in cells if c["model"] == m and c["status"] == "ok"]
            n_wrong = sum(c["wrong"] for c in mc)
            n_fire = sum(bool(fire(c)) for c in mc)
            fired = n_fire >= 2
            in_den = (n_wrong >= 2) if block == "positive" else (len(mc) - n_wrong >= 2)
            per_model[m] = {"block": block, "cells": len(mc), "wrong": n_wrong, "fired_cells": n_fire,
                            "fired": fired, "in_denominator": in_den}
            if in_den and block == "positive":
                pm_tp += fired
                pm_fn += not fired
            elif in_den:
                pm_fp += fired
                pm_tn += not fired
    model_level = {"TP": pm_tp, "FN": pm_fn, "FP": pm_fp, "TN": pm_tn,
                   "sensitivity": pm_tp / (pm_tp + pm_fn) if pm_tp + pm_fn else float("nan"),
                   "specificity": pm_tn / (pm_tn + pm_fp) if pm_tn + pm_fp else float("nan")}
    return {"cell_level": cell_level, "model_level": model_level, "per_model": per_model}


def meets(conf: dict) -> bool:
    spec_min = 13 / 14
    cl, ml = conf["cell_level"], conf["model_level"]
    ok_c = cl["TP"] + cl["FN"] >= 6 and cl["sensitivity"] >= 0.75 and cl["specificity"] >= spec_min - 1e-12
    ok_m = ml["sensitivity"] >= 0.75 and ml["specificity"] >= spec_min - 1e-12
    return bool(ok_c and ok_m)


def analyze() -> None:
    cells = load_cells()
    ok = [c for c in cells if c["status"] == "ok"]
    neg_chains = [s for c in ok if c["block"] == "negative" for s in c["chain_stats"]]
    pos_chains = [s for c in ok if c["block"] == "positive" for s in c["chain_stats"]]
    med_r = median7([s["refined_leaf_rate"] for s in neg_chains if math.isfinite(s["refined_leaf_rate"])])
    med_s = median7([s["step_collapse_factor"] for s in neg_chains if math.isfinite(s["step_collapse_factor"])])
    t_r, t_s = 3 * med_r, 3 * med_s
    cands = {}
    decision = None
    for cand in ("C_R", "C_S", "C_RS"):
        conf = confusion(cells, lambda c, cand=cand: fires(c, cand, t_r, t_s))
        conf["meets_rule"] = meets(conf)
        cands[cand] = conf
        if decision is None and conf["meets_rule"]:
            decision = cand
    wp44 = confusion(cells, lambda c: c["wp44_fired"])
    pos_r = median7([s["refined_leaf_rate"] for s in pos_chains if math.isfinite(s["refined_leaf_rate"])])
    per_pos_model = {m: median7([s["refined_leaf_rate"] for c in ok if c["model"] == m for s in c["chain_stats"]])
                     for m in POS}
    wp44_pos_models = sum(1 for m in POS if sum(c["wp44_fired"] for c in ok if c["model"] == m) >= 2)
    # descriptive: per-model medians and maxima
    per_model = {}
    for m in POS + NEG:
        mc = [c for c in ok if c["model"] == m]
        rs = [s["refined_leaf_rate"] for c in mc for s in c["chain_stats"]]
        ss = [s["step_collapse_factor"] for c in mc for s in c["chain_stats"]]
        per_model[m] = {
            "cells": len(mc), "wrong": sum(c["wrong"] for c in mc),
            "R_median": median7(rs) if rs else None, "R_max": max(rs) if rs else None,
            "R_cell_max": [max(s["refined_leaf_rate"] for s in c["chain_stats"]) for c in mc],
            "S_max": max(ss) if ss else None,
            "depth_given_refined_median": median7([s["mean_refinement_depth_given_refined"] for c in mc for s in c["chain_stats"]]) if mc else None,
            "divergences": [c["divergences"] for c in mc],
            "wp44_fired_cells": sum(c["wp44_fired"] for c in mc),
            "max_abs_z": [c["max_abs_z"] for c in mc],
        }
    preds = {
        "P1": {"pooled_positive_median_R": pos_r, "T_R": t_r, "held": bool(pos_r >= t_r)},
        "P1b": {"per_positive_model_median_R": per_pos_model, "held": all(v >= t_r for v in per_pos_model.values())},
        "P2": {"held": cands["C_R"]["meets_rule"]},
        "P3": {"wp44_positive_models_fired": wp44_pos_models, "held": wp44_pos_models <= 2},
        "P4_agent_forecast": {"C_R_cell_specificity": cands["C_R"]["cell_level"]["specificity"],
                              "held_part_specificity_below": cands["C_R"]["cell_level"]["specificity"] < 13 / 14},
        "P5_agent_forecast": {"C_S_per_model": {m: cands["C_S"]["per_model"][m] for m in (FUNNEL, "seeds_data-seeds_centered_model")}},
    }
    summary = {
        "schema": "silent-funnel-diagnostic-v1-summary",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cells_planned": len(plan()), "cells_present": len(cells), "cells_ok": len(ok),
        "process_failures": [f"{c['model']}/{c['seed']}: {c['status']}" for c in cells if c["status"] != "ok"],
        "negatives_pooled_median_R": med_r, "negatives_pooled_median_S": med_s, "T_R": t_r, "T_S": t_s,
        "candidates": cands, "decision": decision or "none", "wp44_alone": wp44,
        "predictions": preds, "per_model": per_model,
        "off_diagonal": [f"{c['model']}/{c['seed']} ({c['block']}, wrong={c['wrong']})" for c in ok
                         if (c["block"] == "positive") != c["wrong"]],
        "algorithm_revisions": sorted({c["algorithm_revision"] for c in ok}),
        "gradients_total": sum((c["gradients_total"] or 0) for c in ok),
    }
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=float) + "\n", encoding="utf-8")
    write_table(cells, summary)
    log(f"T_R {t_r:.5f} T_S {t_s:.3f} decision {summary['decision']}")


def write_table(cells: list[dict], summary: dict) -> None:
    t_r, t_s = summary["T_R"], summary["T_S"]
    lines = ["# WP55 results table", "",
             f"T_R = 3 x pooled negative-chain median R = 3 x {summary['negatives_pooled_median_R']:.5f} = **{t_r:.5f}**; "
             f"T_S = 3 x {summary['negatives_pooled_median_S']:.4f} = **{t_s:.4f}**.", "",
             "Per chain: R = retained refined-leaf rate, d = mean refinement level of refined leaves, h = end-of-warmup step, "
             "S = median step / h. `*` marks a chain over the threshold. Walls are contended.", "",
             "| block | model | seed | wrong | gates failed | max abs z | R-hat | min bulk | div (ret/warm) | caps | R per chain | d per chain | h per chain | S per chain | WP44 | C_R | C_S | wall s |",
             "|---|---|---:|---|---|---:|---:|---:|---|---:|---|---|---|---|---|---|---|---:|"]
    for c in cells:
        if c["status"] != "ok":
            lines.append(f"| {c['block']} | {c['model']} | {c['seed']} | {c['status']} | | | | | | | | | | | | | | |")
            continue
        cs = c["chain_stats"]
        rr = " ".join(f"{s['refined_leaf_rate']:.4f}{'*' if s['refined_leaf_rate'] > t_r else ''}" for s in cs)
        dd = " ".join(f"{s['mean_refinement_depth_given_refined']:.2f}" for s in cs)
        hh = " ".join(f"{s['end_of_warmup_step']:.3g}" for s in cs)
        ss = " ".join(f"{s['step_collapse_factor']:.2f}{'*' if s['step_collapse_factor'] > t_s else ''}" for s in cs)
        failed = ",".join(k for k, v in c["gates"].items() if not v) or "-"
        wp = ",".join(f"{w['check']}:{w['chain']}" for w in c["wp44_warnings"]) or "-"
        div_r = sum(s["retained_divergences"] for s in cs)
        div_w = sum(s["warmup_divergences"] for s in cs)
        caps = sum(s["retained_depth_caps"] for s in cs)
        lines.append(f"| {c['block']} | {c['model']} | {c['seed']} | {c['wrong']} | {failed} | {c['max_abs_z']:.2f} | "
                     f"{c['max_rank_rhat']:.3f} | {c['min_bulk_ess']:.0f} | {div_r}/{div_w} | {caps} | {rr} | {dd} | {hh} | {ss} | {wp} | "
                     f"{'fire' if fires(c, 'C_R', t_r, t_s) else '-'} | {'fire' if fires(c, 'C_S', t_r, t_s) else '-'} | "
                     f"{c['wall_seconds_contended']:.0f} |")
    lines += ["", "## Confusion (primary truth: positives-list wrong cells vs negatives-list clean cells)", "",
              "| candidate | level | TP | FN | FP | TN | sensitivity | specificity | meets |", "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for name, conf in list(summary["candidates"].items()) + [("WP44 alone", summary["wp44_alone"])]:
        for lvl in ("cell_level", "model_level"):
            x = conf[lvl]
            lines.append(f"| {name} | {lvl} | {x['TP']} | {x['FN']} | {x['FP']} | {x['TN']} | {x['sensitivity']:.3f} | "
                         f"{x['specificity']:.3f} | {conf.get('meets_rule', '') if lvl == 'cell_level' else ''} |")
    (ART / "results-table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    {"prepare": prepare, "run": run_all, "analyze": analyze}[sys.argv[1]]()
