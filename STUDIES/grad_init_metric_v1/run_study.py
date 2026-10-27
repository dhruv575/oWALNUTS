#!/usr/bin/env python3
"""WP94 driver (`STUDIES/grad_init_metric_v1`): the gradient-scaled initial metric (nutpie's initial mass
matrix, WP89's `nutpie_init`) as a default-flip candidate on top of the shipped defaults (`gradinit`), and
alone without the WP90 trapped-chain guard (`gradinit-noguard`), against the defaults.

    python run_study.py manifest                 # the frozen cell order (from protocol.json)
    python run_study.py smoke                    # non-evidence smoke on the diagnostic seed (disclosed, before the freeze)
    python run_study.py run [S|F|P|all] [lane N of M]   # evidence cells in manifest order; lane N of M takes the
                                                 # positions with index % M == N (resumable; never reruns a written cell)
    python run_study.py analyze                  # artifacts/summary.json + artifacts/results-table.md

Run on the Linux box, lanes 1-2 (cores 0-7), two cells at a time: lane 0 as `taskset -c 0-3 ... run all 0 2`,
lane 1 as `taskset -c 4-7 ... run all 1 2`, with `RAYON_NUM_THREADS=4 OMP_NUM_THREADS=1`. Environment: `WP94_ART`
(artifact root, default `artifacts/`), `WP94_MODELS` (BridgeStan model libraries + data of the 22 v7 posteriors),
`WP94_WORK` (scratch), `WP94_BIN` (release binaries), `WP94_DRAWS` (retained draws, out of git, hashed).

Parts (protocol.json `blocks`, run in the order S, F, P):
- `S` (Part 3): `sv-cell` on the WP84 SV model, 4 x 1,000/1,000, arms `defaults` / `gradinit` /
  `gradinit-noguard`; the retained [mu, log_sigma, h_last] draws go to `WP94_DRAWS` right after the cell is
  written and the WP89 census (frozen anchor) decides trapped chains.
- `F` (Part 2): `funnel`, Neal's 10-D funnel at 4 x 2,000/20,000, `diag` / `gradinit` / `gradinit-noguard`.
- `P` (Part 1): `pdb-cell` on the 22 v7 posteriors at 4 x 1,000/1,000, the three arms, scored by the v7 gates
  with WP85's two tiers (reference draws for 18 posteriors, gates-only parameter-block coordinates for the 4
  without reference draws).

Harness reuse: `pdb_cell.rs`, `sv_cell.rs`, `funnel.rs` are WP90's with the arm table replaced (changes listed in
PREREGISTRATION.md); the Part 1 scoring is WP85's `run_pdb_cell` on WP90's cell output; the SV census is WP89's.
"""
from __future__ import annotations

import functools
import gzip
import json
import math
import os
import statistics
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8")) if (HERE / "protocol.json").exists() else {}
ART = Path(os.environ.get("WP94_ART", HERE / "artifacts"))
CELLS = ART / "cells"
TELEM = ART / "telemetry"
WORK = Path(os.environ.get("WP94_WORK", HERE / "work"))
MODELS = Path(os.environ.get("WP94_MODELS", HERE / "models"))
BIN = Path(os.environ.get("WP94_BIN", HERE / "target" / "release"))
DRAWS = Path(os.environ.get("WP94_DRAWS", ART / "draws"))
DATA = HERE / "models" / "data.json"
PDB = Path(os.environ.get("WP94_POSTERIORDB", Path.home() / "infra" / "posteriordb" / "posterior_database"))
N = 250
CHAINS = 4
CHECKPOINTS = {"init": 74, "S1": 99, "S2": 149, "S3": 249, "S4": 449, "S5": 949, "term": 999}
SHIFT = 3.0
EXACT_P5 = 0.0477903522728147
CANDIDATE = "gradinit"
NOGUARD = "gradinit-noguard"
NOOP = "custom_noop"
LOG_SUFFIX = ""


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    ART.mkdir(parents=True, exist_ok=True)
    with (ART / f"run-log{LOG_SUFFIX}.txt").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


# --------------------------------------------------------------------------- cells

def cell_path(cid: str) -> Path:
    return CELLS / f"{cid}.json"


def write_cell(cid: str, payload: dict) -> None:
    CELLS.mkdir(parents=True, exist_ok=True)
    cell_path(cid).write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def load(cid: str) -> dict | None:
    p = cell_path(cid)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def ok(c) -> bool:
    return bool(c) and c.get("status") == "ok"


def timeout_of(kind: str) -> int:
    return int(PROTOCOL["timeouts"][f"{kind}_process_seconds"])


def run_process(cmd: list[str], kind: str) -> tuple[int | str, str]:
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_of(kind))
        return cp.returncode, cp.stderr
    except subprocess.TimeoutExpired:
        return "timeout", f"exceeded {timeout_of(kind)}s"


def mass_summary(diag: list[float] | None) -> dict | None:
    """Min / median / max of a diagonal mass (the initial metric of a chain)."""
    if not diag:
        return None
    a = np.asarray(diag, dtype=np.float64)
    return {"min": float(a.min()), "median": float(np.median(a)), "max": float(a.max()), "dimension": int(a.size)}


# ---- Part 3: the SV model (WP89 cell, WP89 census)

def h_last(mu, ls, z, rho):
    s = np.exp(ls)
    h = mu + s * z[:, 0] / math.sqrt(1 - rho * rho)
    for i in range(1, z.shape[1]):
        h = mu + rho * (h - mu) + s * z[:, i]
    return h


def chain_summary(mu, ls, hl):
    return [{"median_log_sigma": float(np.median(ls[c])), "median_mu": float(np.median(mu[c])),
             "median_h_last": float(np.median(hl[c])), "sd_log_sigma": float(np.std(ls[c])),
             "mean_log_sigma": float(np.mean(ls[c]))} for c in range(mu.shape[0])]


def rhat_stats(mu, ls, hl):
    import arviz as az
    out = {}
    with np.errstate(all="ignore"):
        for name, arr in (("mu", mu), ("log_sigma", ls), ("h_last", hl)):
            ds = az.convert_to_dataset({"p": arr[:, :, None]})
            out[name] = {"rhat": float(az.rhat(ds, method="rank").p.values[0]),
                         "ess_bulk": float(az.ess(ds, method="bulk").p.values[0])}
    return out


def strip_sv_draws(cid: str, c: dict) -> dict:
    """Move the retained [mu, log_sigma, h_last] draws out of the cell into WP94_DRAWS/<cid>.npz and
    leave the per-chain summaries the census reads (WP89 `strip_draws.py`, applied at write time). The
    initial mass diagonal (253 values per chain) is summarised and its log_sigma / beta entries kept."""
    if c.get("status") != "ok" or "draws_mu_logsigma_hlast" not in c["chains_data"][0]:
        return c
    DRAWS.mkdir(parents=True, exist_ok=True)
    arr = np.asarray([ch.pop("draws_mu_logsigma_hlast") for ch in c["chains_data"]], dtype=np.float64)
    mu, ls, hl = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    for ch, s in zip(c["chains_data"], chain_summary(mu, ls, hl)):
        ch.update(s)
        ch["step_at_checkpoints"] = {k: ch["step_at_transition"].get(str(t)) for k, t in CHECKPOINTS.items()}
        init = ch.pop("initial_mass_diagonal", None)
        ch["initial_mass"] = mass_summary(init)
        if init:
            ch["initial_mass"].update({"mu": init[0], "log_sigma": init[1], "beta": init[2], "z_median": float(np.median(init[3:]))})
    c["rhat"] = rhat_stats(mu, ls, hl)
    np.savez_compressed(DRAWS / f"{cid}.npz", draws=arr.astype(np.float32))
    return c


def gzip_telemetry(cid: str, raw: Path) -> None:
    if raw.exists():
        TELEM.mkdir(parents=True, exist_ok=True)
        with open(raw, "rb") as f, gzip.open(TELEM / f"{cid}.json.gz", "wb", compresslevel=6) as g:
            g.write(f.read())
        raw.unlink()


def run_sv(cid: str, arm: str, seed: int) -> None:
    if cell_path(cid).exists():
        return
    WORK.mkdir(parents=True, exist_ok=True)
    CELLS.mkdir(parents=True, exist_ok=True)
    out, raw = cell_path(cid), WORK / f"{cid}.telemetry.json"
    t0 = time.time()
    rc, stderr = run_process([str(BIN / "sv-cell"), str(DATA), str(N), arm, str(seed), str(out), str(raw), str(CHAINS)], "sv")
    gzip_telemetry(cid, raw)
    if rc != 0 or not out.exists():
        write_cell(cid, {"id": cid, "kind": "sv", "arm": arm, "seed": seed, "status": "error", "returncode": rc,
                         "stderr": stderr[-4000:]})
    else:
        c = json.loads(out.read_text(encoding="utf-8"))
        c.update(id=cid, kind="sv")
        write_cell(cid, strip_sv_draws(cid, c))
    c = load(cid)
    log(f"{cid} [{time.time() - t0:.1f}s] {c.get('status')} hash {c.get('draw_hash')} warned {c.get('chain_warning_chains')} "
        f"fired {fired_chains(c) if ok(c) else None} trapped {sv_trapped(c) if ok(c) else None} {stderr.strip()[-200:] if rc != 0 else ''}")


def sv_trapped(cell: dict) -> list[int]:
    """WP89's frozen census with WP89's anchor (protocol.json `sv_trapped_rule`)."""
    T = PROTOCOL["sv_trapped_rule"]
    out = []
    for c, ch in enumerate(cell["chains_data"]):
        if (abs(ch["median_log_sigma"] - T["anchor_log_sigma"]) > T["log_sigma_tolerance"]
                or abs(ch["median_h_last"] - T["anchor_h_last"]) > T["h_last_tolerance"]):
            out.append(c)
    return out


# ---- Part 2: the funnel (WP90 / WP89 / WP85 harness)

def run_funnel(cid: str, arm: str, seed: int) -> None:
    if cell_path(cid).exists():
        return
    CELLS.mkdir(parents=True, exist_ok=True)
    out = cell_path(cid)
    spec = PROTOCOL["funnel"]
    t0 = time.time()
    rc, stderr = run_process([str(BIN / "funnel"), arm, str(spec["warmup"]), str(spec["draws"]), str(seed), str(out)], "funnel")
    if rc != 0 or not out.exists():
        write_cell(cid, {"id": cid, "kind": "funnel", "arm": arm, "seed": seed, "status": "error", "returncode": rc,
                         "stderr": stderr[-4000:]})
    else:
        c = json.loads(out.read_text(encoding="utf-8"))
        c.update(id=cid, kind="funnel", status="ok")
        write_cell(cid, c)
    c = load(cid)
    log(f"{cid} [{time.time() - t0:.1f}s] {c.get('status')} p5 {(c.get('tail_mass') or {}).get('estimate')} fnv {c.get('draws_fnv')} "
        f"fired {funnel_fired(c) if ok(c) else None} {stderr.strip()[-200:] if rc != 0 else ''}")


def funnel_fired(c: dict) -> list[int]:
    return [i for i, ch in enumerate(c["chains_data"]) if any(x["restarted"] for x in ch.get("trapped_chain_checks", []))]


# ---- Part 1: posteriordb (WP90 cell, WP85 scoring)

def pdb_json(rel: str):
    p = PDB / rel
    if p.suffix == ".zip":
        with zipfile.ZipFile(p) as z:
            return json.loads(z.read(z.namelist()[0]).decode("utf-8"))
    return json.loads(p.read_text(encoding="utf-8"))


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
    info = pdb_json(f"posteriors/{model}.json")
    ref = pdb_json(f"reference_posteriors/draws/draws/{info['reference_posterior_name']}.json.zip")
    names = list(ref[0].keys())
    arr = np.asarray([[c[n] for n in names] for c in ref], dtype=np.float64)
    arr = np.transpose(arr, (0, 2, 1))
    return {"names": names, **arviz_stats(arr)}


@functools.lru_cache(maxsize=None)
def stan_model(model: str):
    import bridgestan as bs
    return bs.StanModel(str(MODELS / f"{model}_model.so"), data=(MODELS / f"{model}.data.json").read_text(encoding="utf-8"), seed=1)


def failure(cid, model, arm, seed, status, message) -> dict:
    return {"id": cid, "kind": "pdb", "model": model, "arm": arm, "seed": seed, "status": status, "error": message,
            "passed": False, "gates": {"completed": False, "no_sampler_error": False}}


def run_pdb(cid: str, model: str, arm: str, seed: int) -> None:
    if cell_path(cid).exists():
        return
    CELLS.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    DRAWS.mkdir(parents=True, exist_ok=True)
    raw = WORK / f"{cid}.raw.json"
    if raw.exists():
        raw.unlink()
    so, data = MODELS / f"{model}_model.so", MODELS / f"{model}.data.json"
    t0 = time.time()
    rc, stderr = run_process([str(BIN / "pdb-cell"), str(so), str(data), arm, str(seed), str(raw), str(CHAINS)], "pdb")
    if rc != 0 or not raw.exists():
        cell = failure(cid, model, arm, seed, "timeout" if rc == "timeout" else "error", stderr.strip()[-2000:] or f"exit {rc}")
        cell["returncode"] = rc
        write_cell(cid, cell)
    else:
        o = json.loads(raw.read_text(encoding="utf-8"))
        if o.get("status") != "ok":
            write_cell(cid, failure(cid, model, arm, seed, "error", str(o.get("error", "unknown"))))
        else:
            try:
                write_cell(cid, score_pdb(cid, model, arm, seed, o))
            except Exception as e:  # scoring failures are results
                write_cell(cid, failure(cid, model, arm, seed, "error", f"scoring: {e!r}"))
    if raw.exists():
        raw.unlink()
    c = load(cid)
    if ok(c):
        log(f"{cid} [{time.time() - t0:.1f}s] ok grads {c['gradients_total']} warm {c['gradients_warmup']} minbulk {c['min_bulk_ess']:.0f} "
            f"mintail {c['min_tail_ess']:.0f} rhat {c['max_rank_rhat']:.4f} div {c['divergences']} "
            f"|z| {c['max_abs_z'] if c['max_abs_z'] is None else round(c['max_abs_z'], 2)} passed {c['passed']} "
            f"fired {c['restarted_chains']} warned {c['chain_warning_chains']} hash {c['draw_hash']}")
    else:
        log(f"{cid} [{time.time() - t0:.1f}s] {c.get('status')}: {str(c.get('error', ''))[:300]}")


def score_pdb(cid: str, model: str, arm: str, seed: int, o: dict) -> dict:
    G = PROTOCOL["gates"]
    sm = stan_model(model)
    gates_only = model in set(PROTOCOL["gates_only_models"])
    if gates_only:  # v7 / WP46 rule: parameter-block coordinates, no reference, no z
        ref = None
        names = [bridgestan_name(n) for n in sm.param_names(include_tp=False, include_gq=False)]
    else:
        ref = reference(model)
        names = ref["names"]
    cnames = [bridgestan_name(n) for n in sm.param_names(include_tp=True, include_gq=False)]
    index = {n: i for i, n in enumerate(cnames)}
    missing = [n for n in names if n not in index]
    if missing:
        raise RuntimeError(f"gate parameters missing from param_constrain: {missing[:5]}")
    chains = o["chains_data"]
    unc = np.asarray([c["samples"] for c in chains], dtype=np.float64)
    con = np.empty(unc.shape[:2] + (len(cnames),))
    for c in range(unc.shape[0]):
        for d in range(unc.shape[1]):
            con[c, d] = sm.param_constrain(unc[c, d], include_tp=True, include_gq=False)
    draws = con[:, :, [index[n] for n in names]]
    st = arviz_stats(draws)
    divergences = sum(c["divergences"] for c in chains)
    grads = o["target_calls_total"]
    min_bulk, min_tail, max_rhat = float(np.nanmin(st["bulk_ess"])), float(np.nanmin(st["tail_ess"])), float(np.nanmax(st["rhat"]))
    gates = {"completed": True, "max_rank_rhat": max_rhat <= G["max_rank_rhat"], "min_bulk_ess": min_bulk >= G["min_bulk_ess"],
             "min_tail_ess": min_tail >= G["min_tail_ess"], "sampling_divergences": divergences == 0,
             "finite_draws": bool(np.isfinite(draws).all()), "no_sampler_error": True}
    if ref is not None:
        z = (st["mean"] - ref["mean"]) / np.sqrt(st["mcse"] ** 2 + ref["mcse"] ** 2)
        shifts = [float(np.nanmax(np.abs((draws[i].mean(0) - ref["mean"]) / ref["sd"]))) for i in range(draws.shape[0])]
    else:
        z = np.full(len(names), np.nan)
        shifts = None
    checks = [c["trapped_chain_checks"] for c in chains]
    steps99 = [c["step_at_transition_99"] for c in chains]
    med99 = statistics.median(steps99) if all(s is not None for s in steps99) else None
    np.savez_compressed(DRAWS / f"{cid}.npz", unconstrained=unc, constrained=draws, names=np.asarray(names))
    return {
        "id": cid, "kind": "pdb", "model": model, "arm": arm, "seed": seed, "status": "ok",
        "tier": "gates_only" if gates_only else "reference",
        "wall_seconds_pinned_cotenanted": o["wall_seconds"], "gradients_total": grads,
        "gradients_sampling": sum(c["retained_target_calls"] for c in chains),
        "gradients_warmup": sum(c["warmup_target_calls"] for c in chains),
        "warmup_calls_per_chain": [c["warmup_target_calls"] for c in chains],
        "gradients_start_search": o["init"]["start_search_calls"],
        "divergences": divergences, "warmup_divergences": sum(c["warmup_divergences"] for c in chains),
        "max_depth_stops": sum(c["maximum_depth_stops"] for c in chains),
        "min_bulk_ess": min_bulk, "min_tail_ess": min_tail, "max_rank_rhat": max_rhat,
        "argmin_bulk_ess": names[int(np.nanargmin(st["bulk_ess"]))],
        "min_bulk_ess_per_gradient": min_bulk / grads,
        "max_abs_z": float(np.nanmax(np.abs(z))) if ref is not None else None,
        "gates": gates, "passed": all(gates.values()),
        "per_chain_shift_ref_sd": shifts,
        "shifted_chains": [i for i, s in enumerate(shifts) if s > SHIFT] if shifts else [],
        "draw_hash": o["draw_hash"], "chain_draw_hashes": [c["draw_hash"] for c in chains],
        "chain_total_target_calls": [c["total_target_calls"] for c in chains],
        "target_calls_total": o["target_calls_total"],
        "chain_warnings": o.get("chain_warnings", []), "chain_warning_chains": sorted(set(o.get("chain_warning_chains", []))),
        "chain_warning_kinds": o.get("chain_warning_kinds", []),
        "trapped_chain_checks": checks,
        "restarted_chains": [i for i, cs in enumerate(checks) if any(x["restarted"] for x in cs)],
        "step_at_transition_99": steps99,
        "step_ratio_99": [s / med99 if (s is not None and med99) else None for s in steps99],
        "log_density_99": [cs[0]["abandoned_log_density"] if cs else None for cs in checks],
        "warmup_end": [c.get("warmup_end") for c in chains], "sampling_end": [c.get("sampling_end") for c in chains],
        "final_step_size": [c["final_step_size"] for c in chains],
        "initial_mass": [mass_summary(c.get("initial_mass_diagonal")) for c in chains],
        "effective_seeds": [c["effective_seed"] for c in chains],
        "dimension": o["dimension"], "execution": o.get("execution"), "replicas": o.get("replicas"),
        "init": o["init"]["detail"].get("rule"), "algorithm_revision": o["algorithm_revision"],
        "warmup_config_used": o.get("warmup_config_used"),
        "parameters": {n: {"mean": float(st["mean"][i]), "bulk_ess": float(st["bulk_ess"][i]), "tail_ess": float(st["tail_ess"][i]),
                           "rhat": float(st["rhat"][i]), "z": float(z[i])} for i, n in enumerate(names)},
    }


# --------------------------------------------------------------------------- manifest

def manifest() -> list[dict]:
    cells = []
    for block in PROTOCOL["blocks"]:
        if block["kind"] == "pdb":
            for model in block["models"]:
                for seed in block["seeds"]:
                    for arm in block["arms"]:
                        cells.append({"id": f"P-{model}-{arm}-{seed}", "kind": "pdb", "model": model, "arm": arm, "seed": seed, "block": "P"})
        else:
            for seed in block["seeds"]:
                for arm in block["arms"]:
                    cells.append({"id": f"{block['name']}-{arm}-{seed}", "kind": block["kind"], "arm": arm, "seed": seed, "block": block["name"]})
    return cells


def run_cell(c: dict) -> None:
    if cell_path(c["id"]).exists():
        return
    if c["kind"] == "sv":
        run_sv(c["id"], c["arm"], c["seed"])
    elif c["kind"] == "funnel":
        run_funnel(c["id"], c["arm"], c["seed"])
    elif c["kind"] == "pdb":
        run_pdb(c["id"], c["model"], c["arm"], c["seed"])
    else:
        raise ValueError(c)


def run(part: str | None, lane: int = 0, lanes: int = 1) -> None:
    global LOG_SUFFIX
    LOG_SUFFIX = f"-lane{lane}" if lanes > 1 else ""
    ART.mkdir(parents=True, exist_ok=True)
    affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None
    (ART / f"measured_on{LOG_SUFFIX}.json").write_text(json.dumps({
        "affinity": affinity, "lane": lane, "lanes": lanes,
        "RAYON_NUM_THREADS": os.environ.get("RAYON_NUM_THREADS"), "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
        "cwd": os.getcwd(), "python": sys.version, "pid": os.getpid()}, indent=1) + "\n", encoding="utf-8")
    log(f"run start part={part} lane={lane}/{lanes} affinity={affinity}")
    for i, c in enumerate(manifest()):
        if part and part != "all" and c["block"] != part:
            continue
        if i % lanes != lane:
            continue
        run_cell(c)
    log(f"run complete part={part} lane={lane}/{lanes}")


# --------------------------------------------------------------------------- smoke (non-evidence, disclosed)

def smoke() -> None:
    """The diagnostic seed (protocol.json `smoke.seed`, never evidence): one kidiq cell per arm (reference tier),
    one GLMM_Poisson cell per arm (gates-only tier), one funnel cell per arm, one SV cell per arm, each with the
    custom_noop arm added (must be bit-identical to defaults / diag), then the analysis over them."""
    global ART, CELLS, TELEM, DRAWS
    CELLS, TELEM, DRAWS = ART / "smoke" / "cells", ART / "smoke" / "telemetry", ART / "smoke" / "draws"
    s = int(PROTOCOL["smoke"]["seed"])
    pdb_arms = ["defaults", NOOP, CANDIDATE, NOGUARD]
    for model in ("kidiq-kidscore_momhsiq", "GLMM_Poisson_data-GLMM_Poisson_model"):
        for arm in pdb_arms:
            run_pdb(f"P-{model}-{arm}-{s}", model, arm, s)
    for arm in ("diag", NOOP, CANDIDATE, NOGUARD, "diag-best16", f"{CANDIDATE}-best16"):
        run_funnel(f"F-{arm}-{s}", arm, s)
    for arm in pdb_arms:
        run_sv(f"S-{arm}-{s}", arm, s)
    checks = {}
    for model in ("kidiq-kidscore_momhsiq", "GLMM_Poisson_data-GLMM_Poisson_model"):
        a, b = load(f"P-{model}-defaults-{s}"), load(f"P-{model}-{NOOP}-{s}")
        checks[f"P:{model}"] = identity(a, b) if ok(a) and ok(b) else {"holds": False, "error": True}
    a, b = load(f"F-diag-{s}"), load(f"F-{NOOP}-{s}")
    checks["F"] = identity(a, b) if ok(a) and ok(b) else {"holds": False, "error": True}
    a, b = load(f"S-defaults-{s}"), load(f"S-{NOOP}-{s}")
    checks["S"] = identity(a, b) if ok(a) and ok(b) else {"holds": False, "error": True}
    for k, v in checks.items():
        log(f"smoke custom_noop identity {k}: {v}")
    (ART / "smoke" / "noop-identity.json").write_text(json.dumps(checks, indent=1) + "\n", encoding="utf-8")
    for arm in (CANDIDATE, NOGUARD):
        c = load(f"S-{arm}-{s}")
        if ok(c):
            log(f"smoke SV {arm} initial mass per chain: {[ch.get('initial_mass') for ch in c['chains_data']]}")
    # the analysis code over the smoke cells: the protocol narrowed to the smoke seed and the two smoke models
    ART = ART / "smoke"
    for b in PROTOCOL["blocks"]:
        b["seeds"] = [s]
        if b["kind"] == "pdb":
            b["models"] = ["kidiq-kidscore_momhsiq", "GLMM_Poisson_data-GLMM_Poisson_model"]
    analyze({"smoke": True, "custom_noop_identity": checks})


# --------------------------------------------------------------------------- analysis

def geomean(xs):
    return math.exp(statistics.fmean(math.log(x) for x in xs))


def fired_chains(c: dict) -> list[int]:
    if c.get("kind") == "pdb":
        return list(c.get("restarted_chains", []))
    return [i for i, ch in enumerate(c["chains_data"]) if any(x["restarted"] for x in ch.get("trapped_chain_checks", []))]


def per_chain_identity(d: dict, g: dict) -> tuple[list[str], list[str], list[int], list[int]]:
    """(per-chain draw hashes d, g), per-chain total target calls for two cells of any kind."""
    if d.get("kind") == "pdb":
        return (d["chain_draw_hashes"], g["chain_draw_hashes"], d["chain_total_target_calls"], g["chain_total_target_calls"])
    if d.get("kind") == "funnel":
        return ([ch["draws_fnv"] for ch in d["chains_data"]], [ch["draws_fnv"] for ch in g["chains_data"]],
                [ch["target_calls"] for ch in d["chains_data"]], [ch["target_calls"] for ch in g["chains_data"]])
    return ([ch["draw_hash"] for ch in d["chains_data"]], [ch["draw_hash"] for ch in g["chains_data"]],
            [ch["total_target_calls"] for ch in d["chains_data"]], [ch["total_target_calls"] for ch in g["chains_data"]])


def cell_hash_and_calls(c: dict) -> tuple[str, int]:
    if c.get("kind") == "funnel":
        return c["draws_fnv"], c["target_calls_total"]
    return c["draw_hash"], c["target_calls_total"]


def identity(d: dict, g: dict) -> dict:
    """Bit identity of two cells (the smoke's custom_noop check, R7): per chain and whole cell."""
    hd, hg, cd, cg = per_chain_identity(d, g)
    chains_identical = all(hd[i] == hg[i] and cd[i] == cg[i] for i in range(len(hd)))
    whole = cell_hash_and_calls(d) == cell_hash_and_calls(g)
    return {"holds": chains_identical and whole, "chains_identical": chains_identical, "whole_cell_identical": whole,
            "hashes": [cell_hash_and_calls(d), cell_hash_and_calls(g)]}


def named_chains(c: dict) -> list[int]:
    if "chain_warning_chains" in c:
        return sorted(set(c["chain_warning_chains"]))
    return sorted({w["chain"] for w in c.get("chain_warnings", []) if isinstance(w, dict)})


def firing_record(block: str, key: str, arm: str, g: dict, chain: int) -> dict:
    """One guard firing: the chain's score at the window close, its log density there against the chain
    median, whether the restarted chain was warned / shifted, and the cell's gate result."""
    if g.get("kind") == "pdb":
        checks = g["trapped_chain_checks"]
        chk = next(x for x in checks[chain] if x["restarted"])
        lp99 = [cs[0]["abandoned_log_density"] for cs in checks if cs]
        shift = (g.get("per_chain_shift_ref_sd") or [None] * CHAINS)[chain]
        passed = bool(g.get("passed"))
    else:
        chs = g["chains_data"]
        chk = next(x for x in chs[chain]["trapped_chain_checks"] if x["restarted"])
        lp99 = [ch["trapped_chain_checks"][0]["abandoned_log_density"] for ch in chs if ch.get("trapped_chain_checks")]
        shift, passed = None, None
    med = statistics.median(lp99) if lp99 else None
    return {"block": block, "cell": key, "arm": arm, "chain": chain, "transition": chk["transition"], "step": chk["step"],
            "median_step": chk["median_step"], "step_ratio": chk["step"] / chk["median_step"] if chk["median_step"] else None,
            "log_density_99": chk["abandoned_log_density"], "chain_median_log_density_99": med,
            "shortfall_99_nats": (med - chk["abandoned_log_density"]) if med is not None else None,
            "abandoned_target_calls": chk["abandoned_target_calls"],
            "restarted_chain_warned": chain in named_chains(g), "restarted_chain_shift_ref_sd": shift, "cell_passed": passed}


def bootstrap_median(xs: list[float]) -> dict:
    if not xs:
        return {"pairs": 0, "median": None, "bootstrap_95_interval_of_median": None, "min": None, "max": None}
    rng = np.random.default_rng(0)
    boot = [float(np.median(rng.choice(xs, size=len(xs), replace=True))) for _ in range(2000)]
    return {"pairs": len(xs), "median": statistics.median(xs), "bootstrap_95_interval_of_median": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))],
            "min": min(xs), "max": max(xs)}


def analyze(env: dict | None = None) -> None:
    env = env or {}
    man = manifest()
    cells = {c["id"]: load(c["id"]) for c in man}
    blocks = {b["name"]: b for b in PROTOCOL["blocks"]}
    P, F, S = blocks["P"], blocks["F"], blocks["S"]
    arms = [CANDIDATE, NOGUARD]
    summary: dict = {"schema": "grad-init-metric-v1-summary", "ledger_id": PROTOCOL["ledger_id"], "environment": env}
    errors: list[str] = []
    firings: list[dict] = []

    # ---- Part 1
    seeds = P["seeds"]
    need = math.ceil(5 * len(seeds) / 6)
    per_model: dict = {}
    headline = {a: {} for a in arms}
    warm = {a: {} for a in arms}
    paired_all = {a: [] for a in arms}
    new_div_models, new_div_passing, gates_drop = [], [], []
    for m in P["models"]:
        d = [cells.get(f"P-{m}-defaults-{s}") for s in seeds]
        for s, x in zip(seeds, d):
            if not ok(x):
                errors.append(x["id"] if x else f"P-{m}-defaults-{s} (missing)")
        row = {"passes_defaults": sum(bool(ok(x) and x["passed"]) for x in d),
               "divergences_defaults": sum(x.get("divergences", 0) for x in d if ok(x)),
               "warned_cells_defaults": [s for s, x in zip(seeds, d) if ok(x) and x["chain_warning_chains"]],
               "fired_cells_defaults": [s for s, x in zip(seeds, d) if ok(x) and x["restarted_chains"]],
               "max_rank_rhat_defaults": [x["max_rank_rhat"] if ok(x) else None for x in d],
               "gradients_warmup_defaults_median": statistics.median([x["gradients_warmup"] for x in d if ok(x)]) if any(ok(x) for x in d) else None}
        for s, x in zip(seeds, d):
            if ok(x):
                for ch in x["restarted_chains"]:
                    firings.append(firing_record("P", f"{m}:{s}", "defaults", x, ch))
        for a in arms:
            g = [cells.get(f"P-{m}-{a}-{s}") for s in seeds]
            paired, wratio = [], []
            for s, x, y in zip(seeds, d, g):
                if not ok(y):
                    errors.append(y["id"] if y else f"P-{m}-{a}-{s} (missing)")
                if ok(x) and ok(y):
                    if x["min_bulk_ess_per_gradient"] > 0:
                        paired.append(y["min_bulk_ess_per_gradient"] / x["min_bulk_ess_per_gradient"])
                        paired_all[a].append(paired[-1])
                    wx, wy = statistics.median(x["warmup_calls_per_chain"]), statistics.median(y["warmup_calls_per_chain"])
                    if wx > 0:
                        wratio.append(wy / wx)
                    for ch in y["restarted_chains"]:
                        firings.append(firing_record("P", f"{m}:{s}", a, y, ch))
                    if a == CANDIDATE and x["passed"] and y["divergences"] > x["divergences"]:
                        new_div_passing.append(f"P:{m}:{s}")
            if len(paired) >= need:
                headline[a][m] = statistics.median(paired)
            if len(wratio) >= need:
                warm[a][m] = statistics.median(wratio)
            passes = sum(bool(ok(y) and y["passed"]) for y in g)
            div = sum(y.get("divergences", 0) for y in g if ok(y))
            if a == CANDIDATE:
                if div > row["divergences_defaults"]:
                    new_div_models.append(m)
                if passes < row["passes_defaults"]:
                    gates_drop.append(m)
            row[a] = {"passes": passes, "paired_ratios": paired, "headline_ratio": headline[a].get(m),
                      "warmup_gradient_ratios": wratio, "warmup_gradient_ratio": warm[a].get(m), "divergences": div,
                      "fired_cells": [s for s, y in zip(seeds, g) if ok(y) and y["restarted_chains"]],
                      "warned_cells": [s for s, y in zip(seeds, g) if ok(y) and y["chain_warning_chains"]],
                      "max_rank_rhat": [y["max_rank_rhat"] if ok(y) else None for y in g],
                      "max_abs_z_passing": max([y["max_abs_z"] for y in g if ok(y) and y["passed"] and y.get("max_abs_z") is not None], default=None),
                      "gradients_warmup_median": statistics.median([y["gradients_warmup"] for y in g if ok(y)]) if any(ok(y) for y in g) else None,
                      "initial_mass_range": [min((im["min"] for y in g if ok(y) for im in y["initial_mass"] if im), default=None),
                                             max((im["max"] for y in g if ok(y) for im in y["initial_mass"] if im), default=None)],
                      "wall_per_gradient_ratio": statistics.median([(y["wall_seconds_pinned_cotenanted"] / y["gradients_total"]) / (x["wall_seconds_pinned_cotenanted"] / x["gradients_total"])
                                                                    for x, y in zip(d, g) if ok(x) and ok(y)] or [float("nan")])}
        per_model[m] = row
    passes = {"defaults": sum(v["passes_defaults"] for v in per_model.values())}
    for a in arms:
        passes[a] = sum(v[a]["passes"] for v in per_model.values())
    part1_errors = [e for e in errors if e.startswith("P")]

    # ---- Part 2
    def funnel_arm(arm: str) -> dict:
        cs = {s: cells.get(f"F-{arm}-{s}") for s in F["seeds"]}
        for s, c in cs.items():
            if not ok(c):
                errors.append(c["id"] if c else f"F-{arm}-{s} (missing)")
        cs = {s: c for s, c in cs.items() if ok(c)}
        for s, c in cs.items():
            for ch in funnel_fired(c):
                firings.append(firing_record("F", str(s), arm, c, ch))
        est = [c["tail_mass"]["estimate"] for c in cs.values()]
        p5 = statistics.fmean(est) if est else None
        se = statistics.stdev(est) / math.sqrt(len(est)) if len(est) > 1 else None
        return {"cells": len(cs), "p5": p5, "se": se, "abs_error": abs(p5 - EXACT_P5) if p5 is not None else None,
                "z": (p5 - EXACT_P5) / se if (p5 is not None and se) else None,
                "within_2se": (p5 is not None and se is not None and abs(p5 - EXACT_P5) <= 2 * se),
                "divergences": sum(ch["divergences"] for c in cs.values() for ch in c["chains_data"]),
                "fired_cells": [s for s, c in cs.items() if funnel_fired(c)], "fired_chains": sum(len(funnel_fired(c)) for c in cs.values()),
                "min_step_ratio_at_close": min((x["step"] / x["median_step"] for c in cs.values() for ch in c["chains_data"] for x in ch.get("trapped_chain_checks", []) if x["median_step"]), default=None),
                "median_wall": statistics.median([c["wall_seconds"] for c in cs.values() if "wall_seconds" in c]) if cs and "wall_seconds" in next(iter(cs.values())) else None}
    funnel = {a: funnel_arm(a) for a in F["arms"]}

    # ---- Part 3
    sv = {}
    for arm in ["defaults", CANDIDATE, NOGUARD]:
        a = {"cells": 0, "chains": 0, "trapped_chains": 0, "trapped_cells": 0, "trapped": [], "warned_chains": 0, "walls": [],
             "fired": [], "target_calls_total": 0, "warmup_calls_total": 0, "start_log_sigma_gt_1_3": 0}
        for s in S["seeds"]:
            c = cells.get(f"S-{arm}-{s}")
            if not ok(c):
                errors.append(c["id"] if c else f"S-{arm}-{s} (missing)")
                continue
            tr = sv_trapped(c)
            a["cells"] += 1
            a["chains"] += len(c["chains_data"])
            a["trapped_chains"] += len(tr)
            a["trapped_cells"] += bool(tr)
            a["warned_chains"] += len(c.get("chain_warning_chains") or [])
            a["walls"].append(c["wall_seconds_pinned_cotenanted"])
            a["target_calls_total"] += c["target_calls_total"]
            a["warmup_calls_total"] += sum(ch["warmup_target_calls"] for ch in c["chains_data"])
            a["start_log_sigma_gt_1_3"] += sum(1 for x in c["start_log_sigma"] if x > 1.3)
            for ch in tr:
                a["trapped"].append({"seed": s, "chain": ch, "start_log_sigma": c["start_log_sigma"][ch],
                                     "median_log_sigma": c["chains_data"][ch]["median_log_sigma"],
                                     "step_99": c["chains_data"][ch]["step_at_transition"].get("99"),
                                     "warmup_calls": c["chains_data"][ch]["warmup_target_calls"],
                                     "initial_mass": c["chains_data"][ch].get("initial_mass"),
                                     "warned": ch in (c.get("chain_warning_chains") or [])})
            for ch in fired_chains(c):
                rec = firing_record("S", str(s), arm, c, ch)
                rec["start_log_sigma"] = c["start_log_sigma"][ch]
                rec["restarted_chain_census_trapped"] = ch in tr
                a["fired"].append(rec)
        a["median_wall"] = statistics.median(a["walls"]) if a["walls"] else None
        a.pop("walls")
        a["firings"] = len(a["fired"])
        sv[arm] = a

    # ---- rules
    hl = headline[CANDIDATE]
    wl = warm[CANDIDATE]
    n_cells = len(P["models"]) * len(seeds)
    cand_errors = [e for e in errors if e.startswith("P") and (f"-{CANDIDATE}-" in e or "-defaults-" in e)]
    rules = {
        "R1_passes": {"defaults": passes["defaults"], CANDIDATE: passes[CANDIDATE], NOGUARD: passes[NOGUARD], "cells_per_arm": n_cells,
                      "part1_errors": part1_errors, "held": not part1_errors and passes[CANDIDATE] >= passes["defaults"]},
        "R2_headline_ge_0.98": {"geomean": geomean(list(hl.values())) if hl else None, "models": len(hl),
                                "models_without_5_paired_seeds": [m for m in P["models"] if m not in hl],
                                "paired_per_seed": bootstrap_median(paired_all[CANDIDATE]),
                                "noguard_geomean": geomean(list(headline[NOGUARD].values())) if headline[NOGUARD] else None,
                                "noguard_paired_per_seed": bootstrap_median(paired_all[NOGUARD]),
                                "held": len(hl) == len(P["models"]) and geomean(list(hl.values())) >= 0.98},
        "R3_warmup_gradients_and_gates": {"warmup_gradient_ratio_geomean": geomean(list(wl.values())) if wl else None,
                                          "per_model_warmup_gradient_ratio": wl,
                                          "noguard_warmup_gradient_ratio_geomean": geomean(list(warm[NOGUARD].values())) if warm[NOGUARD] else None,
                                          "models_with_gate_drop": gates_drop,
                                          "held": len(wl) == len(P["models"]) and not gates_drop and not cand_errors},
        "R4_no_new_divergences": {"models_with_more_candidate_divergences": new_div_models, "passing_cells_with_new_divergences": new_div_passing,
                                  "held": not new_div_models and not new_div_passing},
        "R5_funnel": {**{k: funnel[CANDIDATE][k] for k in ("cells", "p5", "se", "z", "within_2se", "fired_chains", "fired_cells", "divergences")},
                      "exact": EXACT_P5, "diag": funnel["diag"], "noguard": funnel[NOGUARD],
                      "held": funnel[CANDIDATE]["cells"] == len(F["seeds"]) and funnel[CANDIDATE]["within_2se"]},
        "R6_sv_trapped": {"noguard_trapped_chains": sv[NOGUARD]["trapped_chains"], "noguard_chains": sv[NOGUARD]["chains"],
                          "candidate_trapped_chains": sv[CANDIDATE]["trapped_chains"], "candidate_chains": sv[CANDIDATE]["chains"],
                          "candidate_firings": sv[CANDIDATE]["firings"],
                          "defaults_trapped_chains": sv["defaults"]["trapped_chains"], "defaults_chains": sv["defaults"]["chains"],
                          "defaults_firings": sv["defaults"]["firings"],
                          "held": sv[NOGUARD]["cells"] == len(S["seeds"]) and sv[CANDIDATE]["cells"] == len(S["seeds"])
                          and sv[NOGUARD]["trapped_chains"] <= 1 and sv[CANDIDATE]["trapped_chains"] == 0},
        "R7_library_integrity": {k: env.get(k) for k in ("kernel_fingerprint_default_passed", "kernel_fingerprint_research_passed",
                                                         "grad_init_metric_tests_passed", "trapped_chain_restart_tests_passed",
                                                         "clippy_library_clean", "clippy_study_clean", "smoke_custom_noop_identical")},
    }
    rules["R7_library_integrity"]["held"] = all(bool(v) for v in rules["R7_library_integrity"].values())
    failed = [k.split("_")[0] for k, r in rules.items() if not r["held"]]
    verdict = ("QUALIFIES for a default-flip confirmation: every preregistered rule holds (proposed, not flipped)" if not failed
               else "DOES NOT QUALIFY (failed: " + ", ".join(failed) + "); stays research")
    wall_ratios = [v[CANDIDATE]["wall_per_gradient_ratio"] for v in per_model.values() if v[CANDIDATE]["wall_per_gradient_ratio"] == v[CANDIDATE]["wall_per_gradient_ratio"]]
    gains = sorted(((m, r) for m, r in hl.items()), key=lambda t: t[1])
    reported = {"models_below_0.9": [m for m, r in hl.items() if r < 0.9], "models_above_1.1": [m for m, r in hl.items() if r > 1.1],
                "headline_per_model_sorted": gains,
                "wall_per_gradient_candidate_over_defaults_geomean": geomean(wall_ratios) if wall_ratios else None,
                "firings": {a: len([f for f in firings if f["arm"] == a]) for a in ("defaults", CANDIDATE, NOGUARD)},
                "firings_by_block": {b: {a: len([f for f in firings if f["arm"] == a and f["block"] == b]) for a in ("defaults", CANDIDATE)} for b in ("P", "F")},
                "sv_median_wall": {k: v["median_wall"] for k, v in sv.items()},
                "sv_target_calls_total": {k: v["target_calls_total"] for k, v in sv.items()},
                "sv_warmup_calls_total": {k: v["warmup_calls_total"] for k, v in sv.items()},
                "errors": errors}
    summary.update(verdict=verdict, rules=rules, reported=reported, per_model=per_model, funnel=funnel, sv=sv, firings=firings,
                   predictions=score_predictions(rules, per_model, funnel, sv, passes))
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, default=float) + "\n", encoding="utf-8")
    (ART / "results-table.md").write_text(results_table(summary), encoding="utf-8")
    print(json.dumps({"verdict": verdict, "rules": {k: v["held"] for k, v in rules.items()}}, indent=1))
    log("analysis written")


def score_predictions(rules, per_model, funnel, sv, passes) -> dict:
    P = PROTOCOL["predictions"]
    R2, R3 = rules["R2_headline_ge_0.98"], rules["R3_warmup_gradients_and_gates"]
    hl = {m: v[CANDIDATE]["headline_ratio"] for m, v in per_model.items() if v[CANDIDATE]["headline_ratio"] is not None}
    div_equal = sum(1 for v in per_model.values() if v[CANDIDATE]["divergences"] == v["divergences_defaults"])
    g, w = R2["geomean"], R3["warmup_gradient_ratio_geomean"]
    pm = R2["paired_per_seed"]["median"]
    out = {
        "P1_part1_passes": {"text": P["P1"], "observed": {"defaults": passes["defaults"], CANDIDATE: passes[CANDIDATE]},
                            "held": 88 <= passes["defaults"] <= 100 and -3 <= passes[CANDIDATE] - passes["defaults"] <= 4},
        "P2_headline": {"text": P["P2"], "observed": {"geomean": g, "paired_median": pm, "min_model": min(hl.values()) if hl else None},
                        "held": g is not None and 0.97 <= g <= 1.08 and pm is not None and 0.95 <= pm <= 1.10},
        "P3_warmup_gradients": {"text": P["P3"], "observed": {"geomean": w, "gate_drops": R3["models_with_gate_drop"]},
                                "held": w is not None and 0.80 <= w <= 1.02 and not R3["models_with_gate_drop"]},
        "P4_divergences": {"text": P["P4"], "observed": {"held_R4": rules["R4_no_new_divergences"]["held"], "models_equal": div_equal},
                           "held": rules["R4_no_new_divergences"]["held"] and div_equal >= 18},
        "P5_funnel": {"text": P["P5"], "observed": {a: {"within_2se": funnel[a]["within_2se"], "fired": funnel[a]["fired_chains"]} for a in funnel},
                      "held": all(funnel[a]["within_2se"] for a in ("diag", CANDIDATE, NOGUARD)) and funnel[CANDIDATE]["fired_chains"] == 0},
        "P6_sv": {"text": P["P6"], "observed": {a: {"trapped": sv[a]["trapped_chains"], "firings": sv[a]["firings"]} for a in sv},
                  "held": 3 <= sv["defaults"]["trapped_chains"] <= 16 and 6 <= sv["defaults"]["firings"] <= 16
                  and sv[NOGUARD]["trapped_chains"] <= 2 and sv[CANDIDATE]["trapped_chains"] == 0 and sv[CANDIDATE]["firings"] <= 3},
        "P7_library": {"text": P["P7"], "held": rules["R7_library_integrity"]["held"]},
    }
    return out


def results_table(s: dict) -> str:
    r = s["rules"]
    f = lambda x, sp=".3g": "-" if x is None else format(x, sp)  # noqa: E731
    L = ["# WP94 results (generated by `run_study.py analyze`)", "", f"Verdict: {s['verdict']}", "",
         "## Rules", "", "| rule | observed | held |", "|---|---|---|"]
    R1 = r["R1_passes"]
    L.append(f"| R1 passes gradinit >= defaults (Part 1) | gradinit {R1[CANDIDATE]}, defaults {R1['defaults']}, gradinit-noguard {R1[NOGUARD]} of {R1['cells_per_arm']}; errors {R1['part1_errors']} | {R1['held']} |")
    R2 = r["R2_headline_ge_0.98"]
    ps = R2["paired_per_seed"]
    L.append(f"| R2 headline ESS/gradient gradinit/defaults >= 0.98 | geomean {f(R2['geomean'], '.4f')} over {R2['models']} models; paired per-seed median {f(ps['median'], '.4f')}, bootstrap 95% {ps['bootstrap_95_interval_of_median']}, range [{f(ps['min'], '.3f')}, {f(ps['max'], '.3f')}]; noguard geomean {f(R2['noguard_geomean'], '.4f')} | {R2['held']} |")
    R3 = r["R3_warmup_gradients_and_gates"]
    L.append(f"| R3 warmup gradients (median ratio reported) and no model's gates drop | warmup-gradient ratio geomean {f(R3['warmup_gradient_ratio_geomean'], '.4f')} (noguard {f(R3['noguard_warmup_gradient_ratio_geomean'], '.4f')}); gate drops {R3['models_with_gate_drop']} | {R3['held']} |")
    R4 = r["R4_no_new_divergences"]
    L.append(f"| R4 no new divergences | models {R4['models_with_more_candidate_divergences']}, passing cells {R4['passing_cells_with_new_divergences']} | {R4['held']} |")
    R5 = r["R5_funnel"]
    L.append(f"| R5 funnel P5 within 2 s.e. of {EXACT_P5:.5f} (gradinit) | {R5['cells']} cells, P5 {f(R5['p5'], '.5f')} +- {f(R5['se'], '.5f')} (z {f(R5['z'], '.2f')}), fired chains {R5['fired_chains']}; diag P5 {f(R5['diag']['p5'], '.5f')} +- {f(R5['diag']['se'], '.5f')}; noguard P5 {f(R5['noguard']['p5'], '.5f')} +- {f(R5['noguard']['se'], '.5f')} | {R5['held']} |")
    R6 = r["R6_sv_trapped"]
    L.append(f"| R6 SV trapped chains: noguard <= 1/480, gradinit 0/480 | noguard {R6['noguard_trapped_chains']}/{R6['noguard_chains']}; gradinit {R6['candidate_trapped_chains']}/{R6['candidate_chains']} with {R6['candidate_firings']} guard firings; defaults {R6['defaults_trapped_chains']}/{R6['defaults_chains']} with {R6['defaults_firings']} firings | {R6['held']} |")
    R7 = r["R7_library_integrity"]
    L.append(f"| R7 library and flag-off integrity | {', '.join(f'{k} {v}' for k, v in R7.items() if k != 'held')} | {R7['held']} |")
    L += ["", "## Part 1 per model (gradinit vs defaults; gradinit-noguard in the last columns)", "",
          "| model | pass defaults / gradinit / noguard | headline gradinit | headline noguard | warmup-grad ratio gradinit | warmup-grad ratio noguard | div d / g / ng | fired cells d / g | warned cells d / g | initial mass range (gradinit) | wall/grad ratio |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for m, v in s["per_model"].items():
        g, n = v[CANDIDATE], v[NOGUARD]
        L.append(f"| {m} | {v['passes_defaults']} / {g['passes']} / {n['passes']} | {f(g['headline_ratio'], '.3f')} | {f(n['headline_ratio'], '.3f')} | {f(g['warmup_gradient_ratio'], '.3f')} | {f(n['warmup_gradient_ratio'], '.3f')} | {v['divergences_defaults']} / {g['divergences']} / {n['divergences']} | {v['fired_cells_defaults']} / {g['fired_cells']} | {v['warned_cells_defaults']} / {g['warned_cells']} | [{f(g['initial_mass_range'][0])}, {f(g['initial_mass_range'][1])}] | {f(g['wall_per_gradient_ratio'], '.3f')} |")
    L += ["", "## Part 2 (funnel)", "", "| arm | cells | P5 | s.e. | z | divergences | fired chains | min step ratio at the window close |", "|---|---|---|---|---|---|---|---|"]
    for a, v in s["funnel"].items():
        L.append(f"| {a} | {v['cells']} | {f(v['p5'], '.5f')} | {f(v['se'], '.5f')} | {f(v['z'], '.2f')} | {v['divergences']} | {v['fired_chains']} | {f(v['min_step_ratio_at_close'])} |")
    L += ["", "## Part 3 (SV, WP89 census with the frozen anchor)", "", "| arm | cells | chains | trapped chains | trapped cells | guard firings | warned chains | starts at log_sigma > 1.3 | total target calls | total warmup calls | median wall s |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for arm, a in s["sv"].items():
        L.append(f"| {arm} | {a['cells']} | {a['chains']} | {a['trapped_chains']} | {a['trapped_cells']} | {a['firings']} | {a['warned_chains']} | {a['start_log_sigma_gt_1_3']} | {a['target_calls_total']} | {a['warmup_calls_total']} | {f(a['median_wall'], '.2f')} |")
    L += ["", "### Trapped chains", "", "| arm | seed | chain | start log_sigma | median log_sigma | step at 99 | warmup calls | initial mass (log_sigma, z median) | warned |", "|---|---|---|---|---|---|---|---|---|"]
    for arm, a in s["sv"].items():
        for t in a["trapped"]:
            im = t.get("initial_mass") or {}
            L.append(f"| {arm} | {t['seed']} | {t['chain']} | {f(t['start_log_sigma'])} | {f(t['median_log_sigma'])} | {f(t['step_99'])} | {t['warmup_calls']} | {f(im.get('log_sigma'))}, {f(im.get('z_median'))} | {t['warned']} |")
    L += ["", "### Guard firings (every arm and part)", "", "| part | cell | arm | chain | step | median step | ratio | lp at close | chain median lp | shortfall (nats) | restarted chain warned | cell passed |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in s["firings"] + [x for a in s["sv"].values() for x in a["fired"]]:
        L.append(f"| {x['block']} | {x['cell']} | {x['arm']} | {x['chain']} | {f(x['step'])} | {f(x['median_step'])} | {f(x['step_ratio'])} | {f(x['log_density_99'], '.1f')} | {f(x['chain_median_log_density_99'], '.1f')} | {f(x['shortfall_99_nats'], '.1f')} | {x['restarted_chain_warned']} | {x['cell_passed']} |")
    L += ["", "## Predictions", ""]
    for k, p in s["predictions"].items():
        L.append(f"- {k}: {p['text']} -> observed {p.get('observed')}; held: {p['held']}")
    L += ["", "## Reported", "", "```json", json.dumps(s["reported"], indent=1, default=float), "```", ""]
    return "\n".join(L)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "manifest"
    if cmd == "manifest":
        for c in manifest():
            print(c["id"])
    elif cmd == "smoke":
        smoke()
    elif cmd == "run":
        part = sys.argv[2] if len(sys.argv) > 2 else None
        lane = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        lanes = int(sys.argv[4]) if len(sys.argv) > 4 else 1
        run(part, lane, lanes)
    elif cmd == "analyze":
        p = ART / "environment.json"
        analyze(json.loads(p.read_text(encoding="utf-8")) if p.exists() else {})
    else:
        raise SystemExit(f"unknown command {cmd}")
