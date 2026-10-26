#!/usr/bin/env python3
"""WP74 chain-disagreement split-rule driver (`STUDIES/chain_disagreement_splits_v1`).

    python run_study.py manifest   # the frozen cell order (from protocol.json)
    python run_study.py smoke      # non-evidence smoke on seed 7409901
    python run_study.py run        # every evidence cell in manifest order (resumable; never reruns a written cell)
    python run_study.py analyze    # artifacts/summary.json + artifacts/results-table.md

Run on the Linux box, inside lane 4, as `taskset -c 12-15 ~/venv/bin/python run_study.py run`.

The posteriordb plumbing (reference(), constrain(), arviz_stats(), score()) is the WP69 driver's
(`STUDIES/trapped_chain_restart_confirmation_v1/run_study.py`, itself WP67/WP57 + v7 code), copied
verbatim except that the lotka z gate is dropped. Cell kinds: `pdb` (pdb-cell, defaults arm),
`two_mode` (two-mode, defaults arm), `replay` (replay-cell = the WP55/WP44 cell). Every cell runs once,
in manifest order; failures are results.
"""
from __future__ import annotations

import functools
import json
import os
import platform
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
ART = Path(os.environ["WP74_ART"]) if os.environ.get("WP74_ART") else HERE / "artifacts"
CELLS = ART / "cells"
DRAWS = ART / "draws"
RAW = ART / "raw-tmp"
MODELS = HERE / "models"
PDB = Path(os.path.expanduser(PROTOCOL["posteriordb"]["path"]))
EXE = ".exe" if os.name == "nt" else ""
PDBH = HERE / "target" / "release" / f"pdb-cell{EXE}"
TWO = HERE / "target" / "release" / f"two-mode{EXE}"
REPLAY = HERE / "target" / "release" / f"replay-cell{EXE}"
T = PROTOCOL["timeouts"]
G = PROTOCOL["gates"]
SHIFT = 3.0


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def short(model: str) -> str:
    return model.replace("-", "__")


def manifest() -> list[dict]:
    cells = []
    for block in PROTOCOL["blocks"]:
        b, kind = block["name"], block["kind"]
        models = block.get("models", [block.get("model")])
        if isinstance(models, str):
            models = PROTOCOL[models]
        for model in models:
            seeds = block.get("only", {}).get(model, block["seeds"])
            for seed in seeds:
                name = "two_mode" if kind == "two_mode" else short(model)
                cells.append({"block": b, "arm": block["arm"], "kind": kind, "model": model, "seed": seed,
                              "role": block["role"], "id": f"{b}--{name}--{seed}"})
    ids = [c["id"] for c in cells]
    assert len(ids) == len(set(ids)), "duplicate cell ids"
    return cells


# --------------------------------------------------------------------------- posteriordb (WP69 code)


def _zip_json(path: Path):
    with zipfile.ZipFile(path) as z:
        inner = [n for n in z.namelist() if n.endswith(".json")][0]
        return json.loads(z.read(inner).decode("utf-8"))


def bridgestan_name(name: str) -> str:
    """'theta.1.2' -> 'theta[1,2]' (WP57/v7 code)."""
    parts = name.split(".")
    if len(parts) == 1 or not all(p.isdigit() for p in parts[1:]):
        return name
    return f"{parts[0]}[{','.join(parts[1:])}]"


def arviz_stats(arr: np.ndarray) -> dict:
    """v7 / WP57 estimators (ArviZ 0.23.4), verbatim."""
    import arviz as az

    ds = az.convert_to_dataset({"p": arr})
    with np.errstate(all="ignore"):
        bulk = np.asarray(az.ess(ds, method="bulk").p.values, dtype=float)
        tail = np.asarray(az.ess(ds, method="tail", prob=(0.05, 0.95)).p.values, dtype=float)
        rhat = np.asarray(az.rhat(ds, method="rank").p.values, dtype=float)
        mcse = np.asarray(az.mcse(ds, method="mean").p.values, dtype=float)
    return {
        "mean": arr.reshape(-1, arr.shape[-1]).mean(0),
        "sd": arr.reshape(-1, arr.shape[-1]).std(0, ddof=1),
        "bulk_ess": bulk, "tail_ess": tail, "rhat": rhat, "mcse": mcse,
    }


def has_reference(model: str) -> bool:
    p = PDB / "posteriors" / f"{model}.json"
    return p.exists() and bool(json.loads(p.read_text(encoding="utf-8")).get("reference_posterior_name"))


@functools.lru_cache(maxsize=None)
def reference(model: str) -> dict:
    info = json.loads((PDB / "posteriors" / f"{model}.json").read_text(encoding="utf-8"))
    ref = _zip_json(PDB / "reference_posteriors" / "draws" / "draws" / f"{info['reference_posterior_name']}.json.zip")
    names = list(ref[0].keys())
    arr = np.asarray([[c[n] for n in names] for c in ref], dtype=np.float64)  # (chains, P, draws)
    arr = np.transpose(arr, (0, 2, 1))
    return {"names": names, **arviz_stats(arr)}


@functools.lru_cache(maxsize=None)
def stan_model(model: str):
    import bridgestan as bs

    so, data = MODELS / f"{short(model)}_model.so", MODELS / f"{short(model)}.data.json"
    if os.name == "nt":
        bs.compile.windows_dll_path_setup()
    return bs.StanModel(str(so), data=data.read_text(encoding="utf-8"), seed=1)


def constrain(model: str, unc: np.ndarray, names: list[str]) -> np.ndarray:
    sm = stan_model(model)
    cnames = [bridgestan_name(n) for n in sm.param_names(include_tp=True, include_gq=False)]
    index = {n: i for i, n in enumerate(cnames)}
    missing = [n for n in names if n not in index]
    if missing:
        raise RuntimeError(f"reference parameters not produced by param_constrain: {missing[:5]}")
    con = np.empty(unc.shape[:2] + (len(cnames),))
    for c in range(unc.shape[0]):
        for d in range(unc.shape[1]):
            con[c, d] = sm.param_constrain(unc[c, d], include_tp=True, include_gq=False)
    return con[:, :, [index[n] for n in names]]


def score(model: str, draws: np.ndarray, grads_total, divergences: int) -> dict:
    """v7 gates, z against the reference, per-chain shift and off chains (WP69 score() without the z gate)."""
    ref = reference(model)
    st = arviz_stats(draws)
    z = (st["mean"] - ref["mean"]) / np.sqrt(st["mcse"] ** 2 + ref["mcse"] ** 2)
    min_bulk = float(np.nanmin(st["bulk_ess"]))
    min_tail = float(np.nanmin(st["tail_ess"]))
    max_rhat = float(np.nanmax(st["rhat"]))
    shifts = [float(np.nanmax(np.abs((draws[i].mean(0) - ref["mean"]) / ref["sd"]))) for i in range(draws.shape[0])]
    gates = {
        "completed": True,
        "max_rank_rhat": max_rhat <= G["max_rank_rhat"],
        "min_bulk_ess": min_bulk >= G["min_bulk_ess"],
        "min_tail_ess": min_tail >= G["min_tail_ess"],
        "sampling_divergences": divergences == 0,
        "finite_draws": bool(np.isfinite(draws).all()),
    }
    return {
        "scored": True,
        "min_bulk_ess": min_bulk, "min_tail_ess": min_tail, "max_rank_rhat": max_rhat,
        "argmin_bulk_ess": ref["names"][int(np.nanargmin(st["bulk_ess"]))],
        "argmax_rank_rhat": ref["names"][int(np.nanargmax(st["rhat"]))],
        "max_abs_z": float(np.nanmax(np.abs(z))), "argmax_abs_z": ref["names"][int(np.nanargmax(np.abs(z)))],
        "per_chain_shift_ref_sd": shifts,
        "off_chains": [i for i, s in enumerate(shifts) if s > SHIFT],
        "divergences": divergences, "gradients_total": grads_total,
        "gates": gates, "passed": all(gates.values()),
    }


# --------------------------------------------------------------------------- cells


def base(cell: dict) -> dict:
    return {"schema": "chain-disagreement-splits-v1-cell", **{k: cell[k] for k in
                                                              ("id", "block", "arm", "kind", "model", "seed", "role")}}


def failure(cell, status, message, **extra) -> dict:
    return {**base(cell), "status": status, "error": message, "completed": False, "passed": False,
            "gates": {"completed": False}, **extra}


def launch(cell: dict, cmd: list[str], timeout: int):
    RAW.mkdir(parents=True, exist_ok=True)
    raw = RAW / f"{cell['id']}.json"
    if raw.exists():
        raw.unlink()
    t0 = time.perf_counter()
    try:
        cp = subprocess.run([str(raw) if a == "__OUT__" else a for a in cmd],
                            capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raw.unlink(missing_ok=True)
        return None, failure(cell, "timeout", f"exceeded {timeout}s", process_seconds=time.perf_counter() - t0)
    secs = time.perf_counter() - t0
    if not raw.exists():
        return None, failure(cell, "harness_error", f"exit {cp.returncode}: {cp.stderr.strip()[-2000:]}",
                             process_seconds=secs)
    out = json.loads(raw.read_text(encoding="utf-8"))
    raw.unlink()
    if out.get("status", "ok") != "ok":
        return None, failure(cell, "error", out.get("error", "unknown"), stage=out.get("stage"),
                             process_seconds=secs)
    return {"out": out, "process_seconds": secs, "stderr": cp.stderr[-500:]}, None


def score_posteriordb(cell: dict, model: str, chains: list, grads, divergences: int) -> dict:
    if not has_reference(model):
        return {"scored": False}
    unc = np.asarray([c["samples"] for c in chains], dtype=np.float64)
    ref = reference(model)
    draws = constrain(model, unc, ref["names"])
    DRAWS.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(DRAWS / f"{cell['id']}.npz", unconstrained=unc, draws=draws, names=np.asarray(ref["names"]))
    return score(model, draws, grads, divergences)


def run_pdb(cell: dict) -> dict:
    model = cell["model"]
    so, data = MODELS / f"{short(model)}_model.so", MODELS / f"{short(model)}.data.json"
    r, fail = launch(cell, [str(PDBH), str(so), str(data), "defaults", str(cell["seed"]), "__OUT__"],
                     T["pdb_process_seconds"])
    if fail:
        return fail
    out = r["out"]
    chains = out["chains_data"]
    sc = score_posteriordb(cell, model, chains, out["target_calls_total"], sum(c["divergences"] for c in chains))
    rules = out["split_rules"]
    return {**base(cell), **sc, "status": "ok", "completed": True, "process_seconds": r["process_seconds"],
            "wall_seconds_pinned_cotenanted": out["wall_seconds"], "target_calls_total": out["target_calls_total"],
            "draw_hash": out["draw_hash"], "per_chain_draw_hash": [c["draw_hash"] for c in chains],
            "harness_chain_warnings": out["chain_warnings"],
            "implementation_check": [w["text"] for w in rules["current"]["warnings"]] == out["chain_warnings"],
            "unconstrained_dimension": out["dimension"], "algorithm_revision": out["algorithm_revision"],
            "split_rules": rules}


def run_two_mode(cell: dict) -> dict:
    r, fail = launch(cell, [str(TWO), "run", "defaults", str(cell["seed"]), "__OUT__"], T["two_mode_process_seconds"])
    if fail:
        return fail
    out = r["out"]
    chains = out.pop("chains_data")
    rules = out["split_rules"]
    end_minor = out["chains_ending_minor"]
    split = 0 < end_minor < 4
    minority = min(end_minor, 4 - end_minor)
    groups = {"minor": [i for i, c in enumerate(chains) if c["end_mode"] == "minor"],
              "major": [i for i, c in enumerate(chains) if c["end_mode"] == "major"]}
    return {**base(cell), "status": "ok", "completed": True, "process_seconds": r["process_seconds"],
            **{k: out[k] for k in ("draw_hash", "max_split_rhat", "x1_split_rhat", "rhat_per_coordinate",
                                   "min_bulk_ess", "chain_disagreement", "chain_warnings", "chain_warning_chains",
                                   "pooled_fraction_major", "chains_starting_minor", "chains_ending_minor",
                                   "gradients_total", "wall_seconds", "algorithm_revision")},
            "implementation_check": sorted(set(out["chain_warning_chains"])) ==
                                    sorted({w["chain"] for w in rules["current"]["warnings"]}),
            "per_chain": [{k: c[k] for k in ("start_mode", "end_mode", "retained_fraction_major",
                                             "retained_boundary_crossings", "x1_mean", "draw_hash")} for c in chains],
            "split": split, "split_kind": None if not split else f"{4 - minority}-{minority}",
            "mode_groups": groups, "split_rules": rules}


def run_replay(cell: dict) -> dict:
    model = cell["model"]
    if model == "funnel10":
        args = ["funnel", "-"]
    else:
        args = [str(MODELS / f"{short(model)}_model.so"), str(MODELS / f"{short(model)}.data.json")]
    RAW.mkdir(parents=True, exist_ok=True)
    raw = RAW / f"{cell['id']}.json"
    if raw.exists():
        raw.unlink()
    cmd = [str(REPLAY), *args, str(cell["seed"]), str(raw), "4"]
    t0 = time.perf_counter()
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=T["replay_process_seconds"])
    except subprocess.TimeoutExpired:
        raw.unlink(missing_ok=True)
        return failure(cell, "timeout", f"exceeded {T['replay_process_seconds']}s",
                       process_seconds=time.perf_counter() - t0)
    secs = time.perf_counter() - t0
    if not raw.exists():
        return failure(cell, "harness_error", f"exit {cp.returncode}: {cp.stderr.strip()[-2000:]}", process_seconds=secs)
    out = json.loads(raw.read_text(encoding="utf-8"))
    raw.unlink()
    if out.get("status") != "ok":
        return failure(cell, "error", out.get("error", "unknown"), stage=out.get("stage"), process_seconds=secs)
    chains = out["chains_data"]
    div = sum(c["retained_work"]["divergences"] for c in chains)
    sc = score_posteriordb(cell, model, chains, out["target_calls_total"], div) if model != "funnel10" else {"scored": False}
    rules = out["split_rules"]
    return {**base(cell), **sc, "status": "ok", "completed": True, "process_seconds": secs,
            "wall_seconds_pinned_cotenanted": out["wall_seconds"], "target_calls_total": out["target_calls_total"],
            "draw_hash": out["draw_hash"], "retained_divergences": div,
            "harness_chain_warnings": out["chain_warnings"], "harness_warning_lines": out["warning_lines"],
            "implementation_check": [w["text"] for w in rules["current"]["warnings"]] ==
                                    [w["text"] for w in out["chain_warnings"]]
                                    and rules["current"]["lines"] == out["warning_lines"],
            "chain_disagreement": out["chain_disagreement"], "algorithm_revision": out["algorithm_revision"],
            "split_rules": rules}


def summarize_line(c: dict) -> str:
    if c["status"] != "ok":
        return f"{c['id']}: {c['status']} {str(c.get('error', ''))[:200]}"
    r = c["split_rules"]
    s, g = r["split_rhat"], r["density_clusters"]
    extra = (f"split {c['split_kind']} end_minor {c['chains_ending_minor']} rhat {c['max_split_rhat']:.3f}"
             if c["kind"] == "two_mode" else
             (f"passed {c['passed']} rhat {c['max_rank_rhat']:.4f} off {c['off_chains']}" if c.get("scored") else "unscored"))
    return (f"{c['id']}: ok {extra} | current {r['current']['disagreement_chains']} S {s['named']} "
            f"(maxR {s.get('max_rhat', float('nan')):.3f}) G {g['named']} impl {c['implementation_check']} hash {c['draw_hash']}")


def run_cell(cell: dict, out_path: Path) -> None:
    try:
        c = {"pdb": run_pdb, "two_mode": run_two_mode, "replay": run_replay}[cell["kind"]](cell)
    except Exception as e:  # noqa: BLE001
        c = failure(cell, "harness_error", f"{e}\n{traceback.format_exc()[-1500:]}")
    c["ordinal"] = cell.get("ordinal")
    c["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(c, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    log(summarize_line(c))


def measured_on() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    m = ART / "measured_on.json"
    if m.exists():
        return
    try:
        affinity = sorted(os.sched_getaffinity(0))
    except AttributeError:
        affinity = None
    m.write_text(json.dumps({
        "platform": platform.platform(), "processor": platform.processor(), "cpu_count": os.cpu_count(),
        "affinity": affinity, "python": sys.version.split()[0],
        "env": {k: os.environ.get(k) for k in ("RAYON_NUM_THREADS", "OMP_NUM_THREADS", "TMPDIR")},
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "lane 4 of a shared 16-core box, core-pinned to 12-15, other lanes active: walls are pinned, co-tenanted",
    }, indent=2) + "\n", encoding="utf-8")


def run_all() -> None:
    measured_on()
    cells = manifest()
    for i, cell in enumerate(cells):
        cell["ordinal"] = i
        path = CELLS / f"{cell['id']}.json"
        if path.exists():
            continue
        log(f"[{i + 1}/{len(cells)}] {cell['id']}")
        run_cell(cell, path)
    log("all cells done")


def smoke() -> None:
    """Non-evidence smoke (seed 7409901): one cell of each kind, written to artifacts/smoke/."""
    global CELLS
    seed = PROTOCOL["smoke_seed"]
    out_dir = ART / "smoke"
    cells = [
        {"block": "smoke", "arm": "-", "kind": "two_mode", "model": "two_mode", "seed": seed, "role": "smoke"},
        {"block": "smoke", "arm": "-", "kind": "pdb", "model": "eight_schools-eight_schools_centered", "seed": seed, "role": "smoke"},
        {"block": "smoke", "arm": "-", "kind": "replay", "model": "funnel10", "seed": seed, "role": "smoke"},
        {"block": "smoke", "arm": "-", "kind": "replay", "model": "radon_all-radon_hierarchical_intercept_centered", "seed": seed, "role": "smoke"},
    ]
    for c in cells:
        c["id"] = f"smoke--{'two_mode' if c['kind'] == 'two_mode' else short(c['model'])}--{c['kind']}--{seed}"
        p = out_dir / f"{c['id']}.json"
        p.unlink(missing_ok=True)
        run_cell(c, p)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "manifest":
        for i, c in enumerate(manifest()):
            print(i, c["id"], c["role"])
    elif cmd == "smoke":
        smoke()
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
