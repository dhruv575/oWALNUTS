#!/usr/bin/env python3
"""WP44 chain-disagreement warning study driver (STUDIES/chain_disagreement_warning_v1).

    python run_study.py prepare    # copy posteriordb programs/data, compile BridgeStan models (no STAN_THREADS)
    python run_study.py run        # every planned cell in protocol order, strictly sequential, launched once
    python run_study.py analyze    # artifacts/summary.json + artifacts/results-table.md

Each cell launches the compiled harness once (`chain-check-cell`), writes the raw output to
`artifacts/raw/` (ignored; unconstrained draws), constrains the draws through BridgeStan and writes
`artifacts/cells/<model>-<seed>.json` (gates, z, per-chain reference distances, detectors, Rust
warnings). A launch marker in `artifacts/launches/` forbids a second launch of the same cell; a cell
whose process fails is a result (status != "ok").
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
RAW = ART / "raw"
LAUNCHES = ART / "launches"
MODELS = HERE / "models"
PDB_PATH = HERE / PROTOCOL["posteriordb"]["path"]
HARNESS = HERE / "target" / "release" / "chain-check-cell.exe"
TIMEOUT = PROTOCOL["cell_timeout_seconds"]
THREADS = PROTOCOL["threads"]
GATES = PROTOCOL["gates"]
DET = PROTOCOL["detectors"]
os.environ.setdefault("MAKE", "mingw32-make")


def short(model: str) -> str:
    return model.replace("-", "__")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def plan() -> list[tuple[str, int, str]]:
    cells = [(m, s, "screen") for m in PROTOCOL["models"] for s in PROTOCOL["screen_seeds"]]
    cells += [(m, s, "extra") for m in PROTOCOL["extra_models"] for s in PROTOCOL["extra_seeds"]]
    return cells


# --------------------------------------------------------------------------- posteriordb


def posterior(model: str):
    from posteriordb import PosteriorDatabase

    return PosteriorDatabase(str(PDB_PATH)).posterior(model)


def bridgestan_name(name: str) -> str:
    parts = name.split(".")
    if len(parts) == 1 or not all(p.isdigit() for p in parts[1:]):
        return name
    return f"{parts[0]}[{','.join(parts[1:])}]"


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


def reference(model: str) -> dict:
    ref = posterior(model).reference_draws()
    names = list(ref[0].keys())
    arr = np.transpose(np.asarray([[c[n] for n in names] for c in ref], dtype=np.float64), (0, 2, 1))
    return {"names": names, **arviz_stats(arr)}


def prepare() -> None:
    import bridgestan as bs

    from concurrent.futures import ThreadPoolExecutor

    MODELS.mkdir(exist_ok=True)
    models = sorted(set(PROTOCOL["models"]) | set(PROTOCOL["extra_models"]))
    pending = []
    for model in models:
        p = posterior(model)
        stan = MODELS / f"{short(model)}.stan"
        data = MODELS / f"{short(model)}.data.json"
        if not stan.exists():
            shutil.copyfile(p.model.code_file_path("stan"), stan)
        if not data.exists():
            data.write_text(json.dumps(p.data.values()), encoding="utf-8")
        if not stan.with_name(f"{stan.stem}_model.so").exists():
            pending.append((model, stan))

    def build(item):
        model, stan = item
        t = time.perf_counter()
        bs.compile_model(stan, make_args=[])
        log(f"compiled {model} in {time.perf_counter() - t:.1f}s (contended)")

    with ThreadPoolExecutor(max_workers=3) as pool:  # compilation only; no evidence runs concurrently
        list(pool.map(build, pending))
    for model in models:
        reference(model)  # the reference draws must load
    log("prepared")


# --------------------------------------------------------------------------- detectors


def median7(values) -> float:
    v = sorted(values)
    n = len(v)
    if n == 0:
        return float("nan")
    r = 0.5 * (n - 1)
    lo, hi = math.floor(r), math.ceil(r)
    return v[lo] + (r - lo) * (v[hi] - v[lo])


def window_scores(windows: list[dict | None]) -> dict | None:
    """Scale-free per-chain scores of one phase (None when the check is skipped)."""
    if len(windows) < DET["min_chains"] or any(w is None for w in windows):
        return None
    if any(w["transitions"] < DET["min_window_transitions"] for w in windows):
        return None
    steps = [w["step_size"] for w in windows]
    medians = [w["median_log_density"] for w in windows]
    iqrs = [w["log_density_iqr"] for w in windows]
    out: dict = {"steps": steps, "medians": medians, "iqrs": iqrs}
    if all(math.isfinite(s) for s in steps):
        ms = median7(steps)
        out["median_step"] = ms
        out["step_ratio"] = [s / ms if ms > 0 else float("nan") for s in steps]
    if all(math.isfinite(x) for x in medians + iqrs):
        ref, spread = median7(medians), median7(iqrs)
        out["density_reference"] = ref
        out["density_spread"] = spread
        out["density_gap"] = [ref - m for m in medians]
        out["density_gap_iqrs"] = [(ref - m) / spread if spread > 0 else (math.inf if ref - m > 0 else 0.0)
                                   for m in medians]
    return out


def fired(scores: dict | None, kind: str, step_ratio: float, iqrs: float) -> list[int]:
    if scores is None:
        return []
    if kind == "step":
        if "step_ratio" not in scores:
            return []
        ms = scores["median_step"]
        return [c for c, s in enumerate(scores["steps"]) if s < step_ratio * ms]
    if "density_gap" not in scores:
        return []
    thr = iqrs * scores["density_spread"]
    return [c for c, g in enumerate(scores["density_gap"]) if g > thr]


# --------------------------------------------------------------------------- cells


def failure(model: str, seed: int, block: str, status: str, message: str, **extra) -> dict:
    return {"schema": "chain-disagreement-warning-v1-cell-metrics", "model": model, "seed": seed,
            "block": block, "status": status, "error": message, **extra}


def analyse_cell(model: str, seed: int, block: str, raw_path: Path, ref: dict, wall_process: float) -> dict:
    import bridgestan as bs

    out = json.loads(raw_path.read_text(encoding="utf-8"))
    if out.get("status") != "ok":
        return failure(model, seed, block, "sampler_error", out.get("error", "unknown"), stage=out.get("stage"))
    so = MODELS / f"{short(model)}_model.so"
    data = MODELS / f"{short(model)}.data.json"
    bs.compile.windows_dll_path_setup()
    sm = bs.StanModel(str(so), data=data.read_text(encoding="utf-8"), seed=1)
    cnames = [bridgestan_name(n) for n in sm.param_names(include_tp=True, include_gq=False)]
    chains = out["chains_data"]
    unc = np.asarray([c["samples"] for c in chains], dtype=np.float64)
    con = np.empty(unc.shape[:2] + (len(cnames),))
    for c in range(unc.shape[0]):
        for d in range(unc.shape[1]):
            con[c, d] = sm.param_constrain(unc[c, d], include_tp=True, include_gq=False)
    index = {n: i for i, n in enumerate(cnames)}
    missing = [n for n in ref["names"] if n not in index]
    if missing:
        return failure(model, seed, block, "analysis_error", f"reference parameters missing: {missing[:5]}")
    draws = con[:, :, [index[n] for n in ref["names"]]]
    finite = bool(np.isfinite(draws).all())
    st = arviz_stats(draws)
    z = (st["mean"] - ref["mean"]) / np.sqrt(st["mcse"] ** 2 + ref["mcse"] ** 2)
    pooled_dsd = np.abs(st["mean"] - ref["mean"]) / ref["sd"]
    chain_means = draws.mean(axis=1)  # (chains, P)
    chain_dsd = np.abs(chain_means - ref["mean"][None, :]) / ref["sd"][None, :]
    divergences = sum(c["divergences"] for c in chains)
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
    thr = PROTOCOL["truth"]["reference_sd_threshold"]
    wrong_chains = [c for c in range(chain_dsd.shape[0]) if float(np.nanmax(chain_dsd[c])) > thr]
    truth = {
        "T_gate": (not all(gates.values())) or bool(np.nanmax(pooled_dsd) > thr),
        "T_wrong": len(wrong_chains) > 0,
        "T_rhat": (max_rhat > GATES["max_rank_rhat"]) or len(wrong_chains) > 0,
    }
    w_scores = window_scores([c["warmup_end"] for c in chains])
    s_scores = window_scores([c["sampling_end"] for c in chains])
    dis = out.get("chain_disagreement")
    detectors = {
        "D1_warmup_step": fired(w_scores, "step", DET["step_ratio"], DET["log_density_iqrs"]),
        "D2_warmup_density": fired(w_scores, "density", DET["step_ratio"], DET["log_density_iqrs"]),
        "D3_sampled_density": fired(s_scores, "density", DET["step_ratio"], DET["log_density_iqrs"]),
        "D4_rhat_loo": list(dis["chains"]) if dis else [],
    }
    rust = {"D1_warmup_step": [], "D2_warmup_density": [], "D3_sampled_density": [], "D4_rhat_loo": []}
    key = {"warmup_step": "D1_warmup_step", "warmup_log_density": "D2_warmup_density",
           "sampled_log_density": "D3_sampled_density", "rhat": "D4_rhat_loo"}
    for w in out["chain_warnings"]:
        rust[key[w["check"]]].append(w["chain"])
    per_param = {
        n: {"mean": float(st["mean"][i]), "rhat": float(st["rhat"][i]), "bulk_ess": float(st["bulk_ess"][i]),
            "tail_ess": float(st["tail_ess"][i]), "z": float(z[i]), "pooled_dmean_ref_sd": float(pooled_dsd[i]),
            "chain_dmean_ref_sd": [float(x) for x in chain_dsd[:, i]]}
        for i, n in enumerate(ref["names"])
    }
    return {
        "schema": "chain-disagreement-warning-v1-cell-metrics",
        "model": model, "seed": seed, "block": block, "status": "ok",
        "wall_seconds_contended": out["wall_seconds"], "process_seconds_contended": wall_process,
        "gradients_total": out["target_calls_total"],
        "divergences": divergences, "min_bulk_ess": min_bulk, "min_tail_ess": min_tail,
        "max_rank_rhat": max_rhat, "max_abs_z": float(np.nanmax(np.abs(z))),
        "max_pooled_dmean_ref_sd": float(np.nanmax(pooled_dsd)),
        "max_chain_dmean_ref_sd": [float(np.nanmax(chain_dsd[c])) for c in range(chain_dsd.shape[0])],
        "wrong_chains": wrong_chains,
        "gates": gates, "passed": all(gates.values()), "truth": truth,
        "warmup_end": [c["warmup_end"] for c in chains], "sampling_end": [c["sampling_end"] for c in chains],
        "warmup_scores": w_scores, "sampled_scores": s_scores,
        "chain_disagreement": dis, "unconstrained_max_rhat": out.get("unconstrained_max_rhat"),
        "detectors": detectors, "rust_detectors": rust, "rust_matches_python": rust == detectors,
        "warning_lines": out["warning_lines"],
        "final_step_size": [c["final_step_size"] for c in chains],
        "refinement_exhaustions_per_chain": [c["refinement_exhaustions"] for c in chains],
        "chain_rescues": sum(c["chain_rescues"] for c in chains),
        "algorithm_revision": out["algorithm_revision"],
        "parameters": per_param,
    }


def run_cell(model: str, seed: int, block: str, ref: dict) -> dict:
    so = MODELS / f"{short(model)}_model.so"
    data = MODELS / f"{short(model)}.data.json"
    RAW.mkdir(parents=True, exist_ok=True)
    raw = RAW / f"{short(model)}-{seed}.json"
    cmd = [str(HARNESS), str(so), str(data), str(seed), str(raw), str(THREADS)]
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
            "note": "shared 16-core machine, ten concurrent study agents; walls are contended upper bounds",
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
            d = {k: v for k, v in cell["detectors"].items() if v}
            log(f"  passed {cell['passed']} rhat {cell['max_rank_rhat']:.3f} minbulk {cell['min_bulk_ess']:.0f} "
                f"mintail {cell['min_tail_ess']:.0f} div {cell['divergences']} wrong {cell['wrong_chains']} "
                f"truth {cell['truth']} fired {d} rust==py {cell['rust_matches_python']}")
        else:
            log(f"  {cell['status']}: {cell.get('error', '')[:300]}")


# --------------------------------------------------------------------------- analysis

DETECTORS = ["D1_warmup_step", "D2_warmup_density", "D3_sampled_density", "D4_rhat_loo"]


def union(cell: dict, names: list[str], source: str = "detectors") -> list[int]:
    return sorted({c for n in names for c in cell[source][n]})


def confusion(cells: list[dict], names: list[str], truth: str, fire=None) -> dict:
    tp = fn = fp = tn = 0
    fps, fns = [], []
    for c in cells:
        f = bool(fire(c)) if fire else bool(union(c, names))
        t = c["truth"][truth]
        if t and f:
            tp += 1
        elif t:
            fn += 1
            fns.append(f"{c['model']}/{c['seed']}")
        elif f:
            fp += 1
            fps.append(f"{c['model']}/{c['seed']}")
        else:
            tn += 1
    sens = tp / (tp + fn) if tp + fn else float("nan")
    spec = tn / (tn + fp) if tn + fp else float("nan")
    return {"tp": tp, "fn": fn, "fp": fp, "tn": tn, "sensitivity": sens, "specificity": spec,
            "false_positives": fps, "false_negatives": fns}


def meets(c: dict) -> bool:
    rule = PROTOCOL["decision"]["thresholds"]
    return (not math.isnan(c["specificity"]) and c["specificity"] >= rule["specificity"]
            and not math.isnan(c["sensitivity"]) and c["sensitivity"] >= rule["sensitivity"])


def sweep_fire(cell: dict, step_ratio: float | None, iqrs: float | None, phases: tuple[str, ...]) -> bool:
    hit = False
    if step_ratio is not None and "warmup" in phases:
        hit |= bool(fired(cell["warmup_scores"], "step", step_ratio, 0.0))
    if iqrs is not None:
        if "warmup" in phases:
            hit |= bool(fired(cell["warmup_scores"], "density", 0.0, iqrs))
        if "sampled" in phases:
            hit |= bool(fired(cell["sampled_scores"], "density", 0.0, iqrs))
    return hit


def fmt(x: float) -> str:
    return "nan" if isinstance(x, float) and math.isnan(x) else f"{x:.3f}"


def analyze() -> None:
    planned = plan()
    cells_all = []
    for model, seed, block in planned:
        p = CELLS / f"{short(model)}-{seed}.json"
        cells_all.append(json.loads(p.read_text(encoding="utf-8")) if p.exists()
                         else failure(model, seed, block, "missing", "no cell file"))
    ok = [c for c in cells_all if c["status"] == "ok"]
    screen = [c for c in ok if c["block"] == "screen"]
    candidates = PROTOCOL["decision"]["candidates"]
    results: dict = {"cells_planned": len(planned), "cells_ok": len(ok),
                     "cells_not_ok": [f"{c['model']}/{c['seed']}: {c['status']}" for c in cells_all if c["status"] != "ok"],
                     "rust_python_mismatch": [f"{c['model']}/{c['seed']}" for c in ok if not c["rust_matches_python"]]}
    tables: dict = {}
    for scope, cells in (("all", ok), ("screen", screen)):
        for truth in ("T_gate", "T_wrong", "T_rhat"):
            for name, dets in [(d, [d]) for d in DETECTORS] + [(k, v) for k, v in candidates.items()]:
                tables[f"{scope}|{truth}|{name}"] = confusion(cells, dets, truth)
    results["confusion"] = tables
    # Phase view: warmup end = D1|D2, sampling end = D1|D3|D4 (the step does not change in sampling).
    for scope, cells in (("all", ok),):
        for truth in ("T_gate", "T_wrong", "T_rhat"):
            tables[f"{scope}|{truth}|phase_warmup_end"] = confusion(cells, ["D1_warmup_step", "D2_warmup_density"], truth)
            tables[f"{scope}|{truth}|phase_sampling_end"] = confusion(
                cells, ["D1_warmup_step", "D3_sampled_density", "D4_rhat_loo"], truth)
    # Decision (frozen order).
    decision = {"rule_A": None, "rule_B": None, "ships": None}
    for name in candidates:
        if decision["rule_A"] is None and meets(tables[f"all|{PROTOCOL['decision']['rule_A_truth']}|{name}"]):
            decision["rule_A"] = name
        if decision["rule_B"] is None and meets(tables[f"all|{PROTOCOL['decision']['rule_B_truth']}|{name}"]):
            decision["rule_B"] = name
    decision["ships"] = decision["rule_A"] or decision["rule_B"]
    decision["ships_under"] = "rule_A" if decision["rule_A"] else ("rule_B" if decision["rule_B"] else None)
    results["decision"] = decision
    # Chain-level agreement on T_wrong cells: flagged chains (full union) vs wrong chains.
    chain_level = []
    for c in ok:
        flagged = union(c, DETECTORS)
        if c["wrong_chains"] or flagged:
            chain_level.append({"cell": f"{c['model']}/{c['seed']}", "wrong": c["wrong_chains"], "flagged": flagged,
                                "by_detector": {k: v for k, v in c["detectors"].items() if v}})
    results["chain_level"] = chain_level
    # Exploratory threshold sweep (reported, cannot ship).
    sweep = []
    for sr in PROTOCOL["exploratory_sweep"]["step_ratio"]:
        for k in PROTOCOL["exploratory_sweep"]["log_density_iqrs"]:
            for phases in (("warmup",), ("sampled",), ("warmup", "sampled")):
                row = {"step_ratio": sr if "warmup" in phases else None, "iqrs": k, "phases": "+".join(phases)}
                for truth in ("T_gate", "T_wrong"):
                    row[truth] = confusion(ok, [], truth, fire=lambda c, sr=sr, k=k, ph=phases: sweep_fire(
                        c, sr if "warmup" in ph else None, k, ph))
                sweep.append(row)
    results["exploratory_sweep"] = sweep
    results["predictions"] = predictions(tables, ok)
    (ART / "summary.json").write_text(json.dumps(results, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    write_table(cells_all, ok, tables, results)
    log(f"analyzed {len(ok)}/{len(planned)} cells; decision {decision}")


def predictions(tables: dict, ok: list[dict]) -> dict:
    out = {}
    for pid, p in PROTOCOL["predictions"].items():
        if "key" not in p:
            continue
        val = tables[p["key"]][p["stat"]]
        lo, hi = p["interval"]
        out[pid] = {"text": p["text"], "observed": val, "predicted": p["point"], "interval": p["interval"],
                    "held": (not math.isnan(val)) and lo <= val <= hi}
    return out


def write_table(cells_all: list[dict], ok: list[dict], tables: dict, results: dict) -> None:
    L = ["# WP44 chain-disagreement warning: results", "",
         "Detectors (frozen WP33 thresholds): D1 end-of-warmup step < 0.1 x median; D2 last-slow-window median log "
         "density > 3 x median IQR below the chains' median; D3 the same on the retained draws; D4 ChainDisagreement "
         "(leave-one-chain-out R-hat on the unconstrained draws). Truths: T_gate = any house gate fails or a pooled "
         "reference-parameter mean is > 3 reference SD off; T_wrong = some chain's mean of some reference parameter "
         "is > 3 reference SD off; T_rhat = R-hat gate fails or T_wrong.", "",
         "## Every cell", "",
         "| model | seed | block | status | gates | max R-hat | min bulk / tail ESS | div | max chain dmean/refSD | wrong chains | T_gate | T_wrong | D1 | D2 | D3 | D4 | Rust = Python |",
         "|---|---|---|---|---|---:|---|---:|---|---|---|---|---|---|---|---|---|"]
    for c in cells_all:
        if c["status"] != "ok":
            L.append(f"| {c['model']} | {c['seed']} | {c['block']} | **{c['status']}** | | | | | | | | | | | | | |")
            continue
        d = c["detectors"]
        L.append(
            f"| {c['model']} | {c['seed']} | {c['block']} | ok | {'pass' if c['passed'] else '**fail**'} | "
            f"{c['max_rank_rhat']:.3f} | {c['min_bulk_ess']:.0f} / {c['min_tail_ess']:.0f} | {c['divergences']} | "
            f"{', '.join(f'{x:.2f}' for x in c['max_chain_dmean_ref_sd'])} | {c['wrong_chains'] or '-'} | "
            f"{'Y' if c['truth']['T_gate'] else '-'} | {'Y' if c['truth']['T_wrong'] else '-'} | "
            f"{d['D1_warmup_step'] or '-'} | {d['D2_warmup_density'] or '-'} | {d['D3_sampled_density'] or '-'} | "
            f"{d['D4_rhat_loo'] or '-'} | {'yes' if c['rust_matches_python'] else '**no**'} |")
    L += ["", "## Confusion (all process-valid cells)", "",
          "| truth | detector set | TP | FN | FP | TN | sensitivity | specificity | false positives |",
          "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    names = DETECTORS + list(PROTOCOL["decision"]["candidates"]) + ["phase_warmup_end", "phase_sampling_end"]
    for truth in ("T_gate", "T_wrong", "T_rhat"):
        for n in names:
            t = tables[f"all|{truth}|{n}"]
            L.append(f"| {truth} | {n} | {t['tp']} | {t['fn']} | {t['fp']} | {t['tn']} | {fmt(t['sensitivity'])} | "
                     f"{fmt(t['specificity'])} | {', '.join(t['false_positives']) or '-'} |")
    L += ["", "## Confusion (17-model screen only)", "",
          "| truth | detector set | TP | FN | FP | TN | sensitivity | specificity |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for truth in ("T_gate", "T_wrong", "T_rhat"):
        for n in DETECTORS + list(PROTOCOL["decision"]["candidates"]):
            t = tables[f"screen|{truth}|{n}"]
            L.append(f"| {truth} | {n} | {t['tp']} | {t['fn']} | {t['fp']} | {t['tn']} | {fmt(t['sensitivity'])} | {fmt(t['specificity'])} |")
    L += ["", "## False negatives (full union C1)", ""]
    for truth in ("T_gate", "T_wrong", "T_rhat"):
        L.append(f"- {truth}: {', '.join(tables[f'all|{truth}|C1'].get('false_negatives', [])) or 'none'}")
    L += ["", "## Chain-level agreement (cells with a wrong or flagged chain)", "",
          "| cell | wrong chains | flagged chains | by detector |", "|---|---|---|---|"]
    for r in results["chain_level"]:
        L.append(f"| {r['cell']} | {r['wrong'] or '-'} | {r['flagged'] or '-'} | {r['by_detector']} |")
    L += ["", "## Warning lines as printed by `Summary`", ""]
    for c in ok:
        for line in c["warning_lines"]:
            L.append(f"- `{c['model']}/{c['seed']}`: `{line}`")
    L += ["", "## Decision", "", f"`{json.dumps(results['decision'])}`", "", "## Predictions", ""]
    for pid, p in results["predictions"].items():
        L.append(f"- {pid}: {p['text']} - predicted {p['predicted']} in {p['interval']}, observed {fmt(p['observed'])}: "
                 f"**{'held' if p['held'] else 'failed'}**")
    L += ["", "## Exploratory threshold sweep (all cells; reported only, cannot ship)", "",
          "| phases | step ratio | IQRs | T_gate sens | T_gate spec | T_wrong sens | T_wrong spec | T_wrong FP |",
          "|---|---:|---:|---:|---:|---:|---:|---|"]
    for r in results["exploratory_sweep"]:
        a, b = r["T_gate"], r["T_wrong"]
        L.append(f"| {r['phases']} | {r['step_ratio'] if r['step_ratio'] is not None else '-'} | {r['iqrs']} | "
                 f"{fmt(a['sensitivity'])} | {fmt(a['specificity'])} | {fmt(b['sensitivity'])} | {fmt(b['specificity'])} | "
                 f"{', '.join(b['false_positives']) or '-'} |")
    L += ["", f"Cells not ok: {results['cells_not_ok'] or 'none'}",
          f"Rust/Python detector mismatches: {results['rust_python_mismatch'] or 'none'}", ""]
    (ART / "results-table.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "prepare":
        prepare()
    elif cmd == "run":
        run_all()
    elif cmd == "analyze":
        analyze()
    else:
        raise SystemExit(__doc__)
