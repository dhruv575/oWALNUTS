#!/usr/bin/env python3
"""WP57 lotka_volterra stall diagnostic driver (`STUDIES/lotka_volterra_stall_v1`).

    python run_study.py manifest   # print the frozen cell order (from protocol.json)
    python run_study.py run        # every evidence cell in manifest order (resumable; never reruns a written cell)
    python run_study.py analyze    # artifacts/summary.json + artifacts/results-table.md

Harness reuse: the reference statistics and gates are the WP54
(`STUDIES/nonfinite_policy_requalification_v1/run_study.py`) code, itself the
WP48 / posteriordb_bench_v6 harness, reused verbatim. Each cell writes
`artifacts/cells/<id>.json` (metrics, per-window per-chain profile, no draws),
`artifacts/telemetry/<id>.json.gz` (every transition row the observer saw) and
`artifacts/draws/<id>.npz` (unconstrained draws; uncommitted).
"""
from __future__ import annotations

import gzip
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
TELEM = ART / "telemetry"
DRAWS = ART / "draws"
RAW = ART / "raw-tmp"
MODELS = HERE / "models"
PDB_PATH = Path(PROTOCOL["posteriordb"]["path"])
HARNESS = HERE / "target" / "release" / "stall-cell.exe"
MODEL = PROTOCOL["model"]
SO = MODELS / "hudson_lynx_hare__lotka_volterra_model.so"
DATA = MODELS / "hudson_lynx_hare__lotka_volterra.data.json"
CAP = PROTOCOL["wall_cap_seconds"]
STALL = PROTOCOL["stall_threshold_seconds"]
BACKSTOP = PROTOCOL["process_backstop_seconds"]
# Stan's default schedule for 1,000 warmup transitions (verified against the observed stage field).
WINDOWS = [("init", 0, 75), ("S1", 75, 100), ("S2", 100, 150), ("S3", 150, 250), ("S4", 250, 450),
           ("S5", 450, 950), ("term", 950, 1000), ("sampling", 1000, 2000)]
F = None  # telemetry field index, set from the first cell
os.environ.setdefault("RUSTUP_TOOLCHAIN", "1.88.0-x86_64-pc-windows-gnu")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def manifest() -> list[dict]:
    cells = []
    for block in PROTOCOL["blocks"]:
        for seed in block["seeds"]:
            cells.append({"block": block["name"], "arm": block["arm"], "seed": seed,
                          "targeted": block.get("targeted", False),
                          "id": f"{block['name']}--{block['arm']}--{seed}"})
    return cells


# --------------------------------------------------------------------------- posteriordb reference (WP54/WP48 code)


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


def stan_model():
    import bridgestan as bs

    key = str(SO)
    if key not in _SM:
        bs.compile.windows_dll_path_setup()
        _SM[key] = bs.StanModel(str(SO), data=DATA.read_text(encoding="utf-8"), seed=1)
    return _SM[key]


# --------------------------------------------------------------------------- telemetry profile


def window_of(t: int) -> str:
    for name, a, b in WINDOWS:
        if a <= t < b:
            return name
    return "?"


def profile(out: dict) -> dict:
    """Per chain per window: gradients, transitions, steps, depth caps, refinement, per-gradient wall."""
    fields = out["telemetry_fields"]
    ix = {f: i for i, f in enumerate(fields)}
    stops = out["stop_reasons"]
    cap_code = stops.index("MaximumDepth")
    max_depth = out["kernel_max_depth"]
    pending = {}
    unattributed = []
    for p in out.get("pending_unfinished_transition_work", []):
        if p["chain"] is None:
            unattributed.append(p)
        else:
            pending.setdefault(p["chain"], []).append(p)
    chains = []
    stage_mismatch = 0
    for c, rows in enumerate(out["telemetry"]):
        rows = np.asarray(rows, dtype=float).reshape(-1, len(fields))
        per = {}
        for name, a, b in WINDOWS:
            r = rows[(rows[:, ix["t"]] >= a) & (rows[:, ix["t"]] < b)] if len(rows) else rows
            n = len(r)
            if n == 0:
                per[name] = {"transitions": 0, "gradients": 0}
                continue
            grads = float(r[:, ix["target_evaluations"]].sum())
            calls = float(r[:, ix["eval_calls"]].sum())
            ev = float(r[:, ix["eval_us"]].sum())
            leaves = float(r[:, ix["leaves_built"]].sum())
            lv = r[:, ix["selected_level"]]
            per[name] = {
                "transitions": n, "complete": n == b - a,
                "gradients": grads, "observed_calls": calls,
                "step_median": float(np.median(r[:, ix["step"]])),
                "step_min": float(r[:, ix["step"]].min()),
                "step_end": float(r[-1, ix["step"]]),
                "depth_median": float(np.median(r[:, ix["depth"]])),
                "depth_cap_stops": int((r[:, ix["stop"]] == cap_code).sum()),
                "depth_cap_fraction": float((r[:, ix["stop"]] == cap_code).mean()),
                "stop_counts": {stops[int(k)] if k >= 0 else "?": int((r[:, ix["stop"]] == k).sum())
                                for k in np.unique(r[:, ix["stop"]])},
                "gradients_per_transition": grads / n,
                "refinement_attempts_per_leaf": float(r[:, ix["refinement_attempts"]].sum() / leaves) if leaves else None,
                "gradients_per_leaf": grads / leaves if leaves else None,
                "selected_level_mean": float(lv[lv >= 0].mean()) if (lv >= 0).any() else None,
                "selected_level_none_fraction": float((lv < 0).mean()),
                "divergent": int(r[:, ix["divergent"]].sum()),
                "zero_density": int(r[:, ix["zero_density"]].sum()),
                "log_density_median": float(np.median(r[:, ix["log_density"]])),
                "log_density_iqr": float(np.subtract(*np.percentile(r[:, ix["log_density"]], [75, 25]))),
                "wall_seconds": float(r[:, ix["wall_us"]].sum() / 1e6),
                "eval_seconds": ev / 1e6,
                "eval_us_per_gradient": ev / calls if calls else None,
                "wall_us_per_gradient": float(r[:, ix["wall_us"]].sum()) / grads if grads else None,
                "t_end_seconds": float(r[-1, ix["t_end_ms"]] / 1e3),
            }
            expect = {"init": 0, "term": 2, "sampling": 3}.get(name, 1)
            stage_mismatch += int((r[:, ix["stage"]] != expect).sum())
        done = len(rows)
        pend = pending.get(c, [])
        pend_calls = sum(p["calls"] for p in pend)
        pend_eval = sum(p["eval_seconds"] for p in pend)
        next_window = window_of(done) if done < 2000 else None
        grads = float(rows[:, ix["target_evaluations"]].sum()) if done else 0.0
        calls = float(rows[:, ix["eval_calls"]].sum()) if done else 0.0
        ev = float(rows[:, ix["eval_us"]].sum()) if done else 0.0
        chains.append({
            "chain": c, "transitions_done": done, "finished": done == 2000,
            "next_window": next_window,
            "gradients_recorded": grads, "pending_calls": pend_calls, "pending_eval_seconds": pend_eval,
            "gradients_total": grads + pend_calls,
            "eval_us_per_gradient": (ev + pend_eval * 1e6) / (calls + pend_calls) if (calls + pend_calls) else None,
            "start_log_density": out["start_log_densities"][c],
            "windows": per,
        })
    # attribute unattributed pending work (a chain stuck inside its first transition) to the unique chain with 0 rows
    if unattributed:
        empty = [ch for ch in chains if ch["transitions_done"] == 0]
        if len(empty) == 1:
            ch = empty[0]
            ch["pending_calls"] += sum(p["calls"] for p in unattributed)
            ch["pending_eval_seconds"] += sum(p["eval_seconds"] for p in unattributed)
            ch["gradients_total"] = ch["gradients_recorded"] + ch["pending_calls"]
            ch["pending_attributed_by_elimination"] = True
    for ch in chains:  # window-share of gradients, pending work counted in its window
        tot = ch["gradients_total"]
        share = {}
        for name, _, _ in WINDOWS:
            g = ch["windows"][name].get("gradients", 0) + (ch["pending_calls"] if ch["next_window"] == name else 0)
            share[name] = g / tot if tot else 0.0
        ch["gradient_share"] = share
    return {"chains": chains, "stage_mismatch_rows": stage_mismatch,
            "unattributed_pending": unattributed, "max_depth": max_depth}


def emulate_wp44(prof: dict) -> dict:
    """WP44 step and log-density rules evaluated at the end of each warmup window, on chains that reached it."""
    out = {}
    for name, a, b in WINDOWS[:-1]:
        wins = [ch["windows"][name] for ch in prof["chains"]]
        reached = [i for i, w in enumerate(wins) if w.get("complete")]
        if len(reached) < 3 or b - a < 10:
            out[name] = {"scored": False, "reached": reached}
            continue
        steps = [wins[i]["step_end"] for i in reached]
        med_step = statistics.median(steps)
        meds = [wins[i]["log_density_median"] for i in reached]
        iqrs = [wins[i]["log_density_iqr"] for i in reached]
        ref = statistics.median(meds)
        thr = 3.0 * statistics.median(iqrs)
        flags = {}
        for i in reached:
            why = []
            if wins[i]["step_end"] < 0.1 * med_step:
                why.append("step")
            if ref - wins[i]["log_density_median"] > thr:
                why.append("log_density")
            if why:
                flags[i] = why
        known_at = max(wins[i]["t_end_seconds"] for i in reached)
        out[name] = {"scored": True, "reached": reached, "flags": {str(k): v for k, v in flags.items()},
                     "median_step_end": med_step, "known_at_seconds": known_at,
                     "not_reached": [i for i in range(len(wins)) if i not in reached]}
    return out


# --------------------------------------------------------------------------- cells


def failure(cell, status, message, **extra) -> dict:
    return {**base(cell), "status": status, "error": message, "completed": False, "passed": False,
            "gates": {"completed": False}, **extra}


def base(cell: dict) -> dict:
    return {"schema": "lotka-volterra-stall-v1-cell-metrics", "id": cell["id"], "block": cell["block"],
            "model": MODEL, "arm": cell["arm"], "seed": cell["seed"], "targeted": cell["targeted"]}


def run_cell_inner(cell: dict) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    raw = RAW / f"{cell['id']}.json"
    if raw.exists():
        raw.unlink()
    cmd = [str(HARNESS), str(SO), str(DATA), cell["arm"], str(cell["seed"]), str(raw), str(CAP), "4"]
    t0 = time.perf_counter()
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=BACKSTOP)
    except subprocess.TimeoutExpired:
        return failure(cell, "backstop_timeout", f"process exceeded {BACKSTOP}s", process_seconds=time.perf_counter() - t0)
    process_seconds = time.perf_counter() - t0
    if cp.returncode != 0 or not raw.exists():
        return failure(cell, "harness_error", f"exit {cp.returncode}: {cp.stderr.strip()[-2000:]}")
    out = json.loads(raw.read_text(encoding="utf-8"))
    TELEM.mkdir(parents=True, exist_ok=True)
    with gzip.open(TELEM / f"{cell['id']}.json.gz", "wt", encoding="utf-8") as fh:
        json.dump({k: out[k] for k in ("telemetry_fields", "stop_reasons", "telemetry",
                                       "pending_unfinished_transition_work", "start_log_densities")}, fh)
    prof = profile(out)
    common = {
        "wall_seconds_contended": out["wall_seconds"], "process_seconds": process_seconds,
        "stalled": (out["status"] != "ok") or out["wall_seconds"] > STALL,
        "start_log_densities": out["start_log_densities"], "starts_hash": out["starts_hash"],
        "chosen_candidate": out["chosen_candidate"], "start_search_calls": out["start_search_calls"],
        "sampling_calls": out["sampling_calls"], "algorithm_revision_const": out["algorithm_revision_const"],
        "adaptation": out["adaptation"], "init": out["init"],
        "profile": prof, "wp44_emulated_by_window": emulate_wp44(prof),
    }
    if out["status"] != "ok":
        raw.unlink()
        status = "timeout" if out.get("error_kind") == "DeadlineExceeded" else "error"
        return {**failure(cell, status, out.get("error"), error_kind=out.get("error_kind")), **common}
    ref = reference(MODEL)
    sm = stan_model()
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
        return failure(cell, "harness_error", f"reference parameters not produced: {missing[:5]}")
    draws = con[:, :, [index[n] for n in ref["names"]]]
    st = arviz_stats(draws)
    z = (st["mean"] - ref["mean"]) / np.sqrt(st["mcse"] ** 2 + ref["mcse"] ** 2)
    g = PROTOCOL["gates"]
    min_bulk = float(np.nanmin(st["bulk_ess"]))
    min_tail = float(np.nanmin(st["tail_ess"]))
    max_rhat = float(np.nanmax(st["rhat"]))
    max_abs_z = float(np.nanmax(np.abs(z)))
    divergences = sum(c["divergences"] for c in chains)
    gates = {
        "completed": True,
        "max_rank_rhat": max_rhat <= g["max_rank_rhat"],
        "min_bulk_ess": min_bulk >= g["min_bulk_ess"],
        "min_tail_ess": min_tail >= g["min_tail_ess"],
        "sampling_divergences": divergences == 0,
        "finite_draws": bool(np.isfinite(draws).all()),
        "max_abs_z": max_abs_z <= g["max_abs_z"],
    }
    grads = out["target_calls_total"]
    res = {
        **base(cell), **common, "status": "ok", "completed": True,
        "draw_hash": out["draw_hash"],
        "per_chain_draw_hash": [c["draw_hash"] for c in chains],
        "per_chain_target_calls": [c["total_target_calls"] for c in chains],
        "gradients_total": grads,
        "nonfinite_position_rejections": sum(c["nonfinite_position_rejections_total"] for c in chains),
        "divergences": divergences,
        "warmup_divergences": sum(c["warmup_divergences"] for c in chains),
        "warmup_max_depth_stops": [c["warmup_maximum_depth_stops"] for c in chains],
        "max_depth_stops": sum(c["maximum_depth_stops"] for c in chains),
        "final_step_size": [c["final_step_size"] for c in chains],
        "final_max_depth": [c["final_max_depth"] for c in chains],
        "min_bulk_ess": min_bulk, "min_tail_ess": min_tail, "max_rank_rhat": max_rhat,
        "min_bulk_ess_per_gradient": min_bulk / grads,
        "max_abs_z": max_abs_z, "argmax_abs_z": ref["names"][int(np.nanargmax(np.abs(z)))],
        "per_chain_max_abs_mean_shift_ref_sd": [float(np.nanmax(np.abs((draws[i].mean(0) - ref["mean"]) / ref["sd"])))
                                                for i in range(draws.shape[0])],
        "chain_warnings": out["chain_warnings"], "chain_warning_chains": out["chain_warning_chains"],
        "gates": gates, "passed": all(gates.values()),
        "algorithm_revision": out["algorithm_revision"],
        "parameters": {n: {"mean": float(st["mean"][i]), "bulk_ess": float(st["bulk_ess"][i]),
                           "tail_ess": float(st["tail_ess"][i]), "rhat": float(st["rhat"][i]), "z": float(z[i])}
                       for i, n in enumerate(ref["names"])},
    }
    DRAWS.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(DRAWS / f"{cell['id']}.npz", unconstrained=unc, draws=draws, names=np.asarray(ref["names"]))
    raw.unlink()
    return res


def summarize_line(c: dict) -> str:
    chains = c.get("profile", {}).get("chains", [])
    g = " ".join(f"{ch['gradients_total']:.0f}" for ch in chains)
    if c["status"] != "ok":
        return f"{c['id']}: {c['status']} wall {c.get('wall_seconds_contended')} grads/chain [{g}] {str(c.get('error', ''))[:120]}"
    return (f"{c['id']}: ok wall {c['wall_seconds_contended']:.1f}s stalled {c['stalled']} grads/chain [{g}] "
            f"minbulk {c['min_bulk_ess']:.0f} mintail {c['min_tail_ess']:.0f} rhat {c['max_rank_rhat']:.4f} "
            f"div {c['divergences']} max|z| {c['max_abs_z']:.2f} passed {c['passed']} hash {c['draw_hash']} "
            f"warn {c['chain_warning_chains']}")


def run_cell(cell: dict, out_path: Path) -> None:
    try:
        c = run_cell_inner(cell)
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
            "note": "shared 16-core machine; sibling agents ran concurrently; every wall is contended",
        }, indent=2) + "\n", encoding="utf-8")
    cells = manifest()
    for i, cell in enumerate(cells):
        cell["ordinal"] = i
        path = CELLS / f"{cell['id']}.json"
        if path.exists():
            continue
        log(f"[{i + 1}/{len(cells)}] {cell['id']}")
        run_cell(cell, path)


# --------------------------------------------------------------------------- analysis (see analyze.py)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "manifest":
        for i, c in enumerate(manifest()):
            print(i, c["id"])
    elif cmd == "run":
        run_all()
    elif cmd == "analyze":
        import analyze

        analyze.main()
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
