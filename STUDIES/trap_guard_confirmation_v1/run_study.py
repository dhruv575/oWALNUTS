#!/usr/bin/env python3
"""WP90 driver (`STUDIES/trap_guard_confirmation_v1`): default-flip confirmation of `guard-0.01-0`
(the WP67 trapped-chain restart rule at step ratio 0.01, scored at the end of the first slow window).

    python run_study.py manifest            # the frozen cell order (from protocol.json)
    python run_study.py smoke               # non-evidence smoke on the diagnostic seed (disclosed, before the freeze)
    python run_study.py run [S|F|P]         # every evidence cell in manifest order (resumable; never reruns a written cell)
    python run_study.py analyze             # artifacts/summary.json + artifacts/results-table.md

Run on the Linux box, inside lane 1, as `taskset -c 0-3 ~/venv/bin/python run_study.py run` with
`RAYON_NUM_THREADS=4 OMP_NUM_THREADS=1`. Environment: `WP90_ART` (artifact root, default `artifacts/`),
`WP90_MODELS` (BridgeStan model libraries + data of the 22 v7 posteriors), `WP90_WORK` (scratch),
`WP90_BIN` (release binaries), `WP90_DRAWS` (retained draws, out of git, hashed).

Parts (protocol.json `blocks`, run in the order S, F, P):
- `S` (Part 3): `sv-cell` (Rust, WP89's cell verbatim) on the WP84 SV model, 4 x 1,000/1,000, arms
  `defaults` / `guard-0.01-0`; the retained [mu, log_sigma, h_last] draws go to `WP90_DRAWS` right after
  the cell is written and the WP89 census (frozen anchor) decides trapped chains.
- `F` (Part 2): `funnel` (WP89's / WP85's harness), Neal's 10-D funnel at 4 x 2,000/20,000, `diag` /
  `guard-0.01-0`.
- `P` (Part 1): `pdb-cell` (WP89's / WP67's cell) on the 22 v7 posteriors at 4 x 1,000/1,000,
  `defaults` / `guard-0.01-0`, scored by the v7 gates with WP85's two tiers (reference draws for 18
  posteriors, gates-only parameter-block coordinates for the 4 without reference draws).

Harness reuse: `pdb_cell.rs`, `sv_cell.rs`, `funnel.rs` are WP89's (changes listed in PREREGISTRATION.md);
the Part 1 scoring is WP85's `run_pdb_cell` on WP89's cell output; the SV census is WP89's `analyze`.
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
ART = Path(os.environ.get("WP90_ART", HERE / "artifacts"))
CELLS = ART / "cells"
TELEM = ART / "telemetry"
WORK = Path(os.environ.get("WP90_WORK", HERE / "work"))
MODELS = Path(os.environ.get("WP90_MODELS", HERE / "models"))
BIN = Path(os.environ.get("WP90_BIN", HERE / "target" / "release"))
DRAWS = Path(os.environ.get("WP90_DRAWS", ART / "draws"))
DATA = HERE / "models" / "data.json"
PDB = Path(os.environ.get("WP90_POSTERIORDB", Path.home() / "infra" / "posteriordb" / "posterior_database"))
N = 250
CHAINS = 4
CHECKPOINTS = {"init": 74, "S1": 99, "S2": 149, "S3": 249, "S4": 449, "S5": 949, "term": 999}
SHIFT = 3.0  # trapped chain on a reference-tier model: more than 3 reference SD off (WP67 / WP69)
EXACT_P5 = 0.0477903522728147
GUARD = "guard-0.01-0"


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    ART.mkdir(parents=True, exist_ok=True)
    with (ART / "run-log.txt").open("a", encoding="utf-8") as f:
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
    """Move the retained [mu, log_sigma, h_last] draws out of the cell into WP90_DRAWS/<cid>.npz and
    leave the per-chain summaries the census reads (WP89 `strip_draws.py`, applied at write time)."""
    if c.get("status") != "ok" or "draws_mu_logsigma_hlast" not in c["chains_data"][0]:
        return c
    DRAWS.mkdir(parents=True, exist_ok=True)
    arr = np.asarray([ch.pop("draws_mu_logsigma_hlast") for ch in c["chains_data"]], dtype=np.float64)
    mu, ls, hl = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    for ch, s in zip(c["chains_data"], chain_summary(mu, ls, hl)):
        ch.update(s)
        ch["step_at_checkpoints"] = {k: ch["step_at_transition"].get(str(t)) for k, t in CHECKPOINTS.items()}
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


# ---- Part 2: the funnel (WP89 / WP85 harness)

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


# ---- Part 1: posteriordb (WP89 cell, WP85 scoring)

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
        log(f"{cid} [{time.time() - t0:.1f}s] ok grads {c['gradients_total']} minbulk {c['min_bulk_ess']:.0f} mintail {c['min_tail_ess']:.0f} "
            f"rhat {c['max_rank_rhat']:.4f} div {c['divergences']} |z| {c['max_abs_z'] if c['max_abs_z'] is None else round(c['max_abs_z'], 2)} "
            f"passed {c['passed']} ratio99 {min([r for r in c['step_ratio_99'] if r is not None], default=float('nan')):.3g} "
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


def run(part: str | None) -> None:
    ART.mkdir(parents=True, exist_ok=True)
    (ART / "measured_on.json").write_text(json.dumps({
        "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "RAYON_NUM_THREADS": os.environ.get("RAYON_NUM_THREADS"), "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
        "cwd": os.getcwd(), "python": sys.version, "pid": os.getpid()}, indent=1) + "\n", encoding="utf-8")
    log(f"run start part={part} affinity={sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else 'n/a'}")
    for c in manifest():
        if part and c["block"] != part:
            continue
        run_cell(c)
    log(f"run complete part={part}")


# --------------------------------------------------------------------------- smoke (non-evidence, disclosed)

def smoke() -> None:
    """The diagnostic seed (protocol.json `smoke.seed`, never evidence): one pdb pair (kidiq, reference tier), one
    gates-only defaults cell (GLMM_Poisson), one funnel pair, one SV pair, then the analysis over them."""
    global ART, CELLS, TELEM, DRAWS
    CELLS, TELEM, DRAWS = ART / "smoke" / "cells", ART / "smoke" / "telemetry", ART / "smoke" / "draws"
    s = int(PROTOCOL["smoke"]["seed"])
    for arm in ("defaults", GUARD):
        run_pdb(f"P-kidiq-kidscore_momhsiq-{arm}-{s}", "kidiq-kidscore_momhsiq", arm, s)
    for arm in ("defaults", GUARD):
        run_pdb(f"P-GLMM_Poisson_data-GLMM_Poisson_model-{arm}-{s}", "GLMM_Poisson_data-GLMM_Poisson_model", arm, s)
    for arm in ("diag", GUARD):
        run_funnel(f"F-{arm}-{s}", arm, s)
    for arm in ("defaults", GUARD):
        run_sv(f"S-{arm}-{s}", arm, s)
    a, b = load(f"P-kidiq-kidscore_momhsiq-defaults-{s}"), load(f"P-kidiq-kidscore_momhsiq-{GUARD}-{s}")
    log(f"smoke kidiq identity: {a.get('draw_hash')} == {b.get('draw_hash')} -> {a.get('draw_hash') == b.get('draw_hash')}; "
        f"calls {a.get('target_calls_total')} vs {b.get('target_calls_total')}; checks {b.get('trapped_chain_checks')}")
    a, b = load(f"F-diag-{s}"), load(f"F-{GUARD}-{s}")
    log(f"smoke funnel identity: {a.get('draws_fnv')} == {b.get('draws_fnv')} -> {a.get('draws_fnv') == b.get('draws_fnv')}")
    a, b = load(f"S-defaults-{s}"), load(f"S-{GUARD}-{s}")
    log(f"smoke sv identity: {a.get('draw_hash')} == {b.get('draw_hash')} -> {a.get('draw_hash') == b.get('draw_hash')}; trapped {sv_trapped(a)} / {sv_trapped(b)}")
    # the analysis code over the smoke cells: the protocol narrowed to the smoke seed and the two smoke models
    ART = ART / "smoke"
    for b in PROTOCOL["blocks"]:
        b["seeds"] = [s]
        if b["kind"] == "pdb":
            b["models"] = ["kidiq-kidscore_momhsiq", "GLMM_Poisson_data-GLMM_Poisson_model"]
    analyze({"smoke": True})


# --------------------------------------------------------------------------- analysis

def geomean(xs):
    return math.exp(statistics.fmean(math.log(x) for x in xs))


def fired_chains(c: dict) -> list[int]:
    if c.get("kind") == "pdb":
        return list(c.get("restarted_chains", []))
    return [i for i, ch in enumerate(c["chains_data"]) if any(x["restarted"] for x in ch.get("trapped_chain_checks", []))]


def per_chain_identity(d: dict, g: dict) -> tuple[list[str], list[int], list[int]]:
    """(per-chain draw hashes d, g), per-chain total target calls for the defaults / guard cells of any kind."""
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
    """R2 on one pair: unfired -> whole-cell and per-chain identity; fired -> untouched chains identical."""
    fired = fired_chains(g)
    hd, hg, cd, cg = per_chain_identity(d, g)
    untouched = [i for i in range(len(hd)) if i not in fired]
    chains_identical = all(hd[i] == hg[i] and cd[i] == cg[i] for i in untouched)
    if fired:
        return {"fired": fired, "holds": chains_identical, "untouched_identical": chains_identical}
    whole = cell_hash_and_calls(d) == cell_hash_and_calls(g)
    return {"fired": [], "holds": chains_identical and whole, "whole_cell_identical": whole}


def named_chains(c: dict) -> list[int]:
    """Chains named by the chain warnings: `chain_warning_chains` (sv, pdb cells) or the funnel's warning records."""
    if "chain_warning_chains" in c:
        return sorted(set(c["chain_warning_chains"]))
    return sorted({w["chain"] for w in c.get("chain_warnings", []) if isinstance(w, dict)})


def audit_firing(block: str, key: str, d: dict, g: dict, chain: int) -> dict:
    """R7 record of one firing: the chain's score, its log density at the scoring transition against the chain
    median, the trapped tests at the defaults (T1 warnings, T2 reference shift, T3 the WP89 signature on the
    recorded quantities) and whether the restarted chain passed."""
    if g.get("kind") == "pdb":
        checks = g["trapped_chain_checks"]
        chk = next(x for x in checks[chain] if x["restarted"])
        lp99 = [cs[0]["abandoned_log_density"] for cs in checks if cs]
        d_sampling = d.get("sampling_end") or []
        d_warned = d.get("chain_warning_chains", [])
        d_shift = (d.get("per_chain_shift_ref_sd") or [None] * 4)[chain]
        g_shift = (g.get("per_chain_shift_ref_sd") or [None] * 4)[chain]
        g_warned = g.get("chain_warning_chains", [])
        passed = bool(g.get("passed"))
    else:
        chs = g["chains_data"]
        chk = next(x for x in chs[chain]["trapped_chain_checks"] if x["restarted"])
        lp99 = [ch["trapped_chain_checks"][0]["abandoned_log_density"] for ch in chs if ch.get("trapped_chain_checks")]
        d_sampling = [ch.get("sampling_end") or {"median_log_density": ch.get("sampling_end_median_log_density"),
                                                 "log_density_iqr": ch.get("sampling_end_log_density_iqr")}
                      for ch in d["chains_data"]]
        d_warned = named_chains(d)
        d_shift = g_shift = None
        g_warned = named_chains(g)
        passed = None
    ratio = chk["step"] / chk["median_step"] if chk["median_step"] else None
    med_lp99 = statistics.median(lp99) if lp99 else None
    ref = [s["median_log_density"] for s in d_sampling if s and s.get("median_log_density") is not None]
    iqr = [s["log_density_iqr"] for s in d_sampling if s and s.get("log_density_iqr") is not None]
    ref_m, iqr_m = (statistics.median(ref) if ref else None), (statistics.median(iqr) if iqr else None)
    T = PROTOCOL["trapped_definition"]
    t1 = chain in d_warned
    t2 = d_shift is not None and d_shift > SHIFT
    t3 = ref_m is not None and iqr_m is not None and chk["abandoned_log_density"] < ref_m - T["iqr_factor"] * iqr_m
    return {"block": block, "cell": key, "chain": chain, "transition": chk["transition"], "step": chk["step"],
            "median_step": chk["median_step"], "step_ratio": ratio, "log_density_99": chk["abandoned_log_density"],
            "chain_median_log_density_99": med_lp99,
            "shortfall_99_nats": (med_lp99 - chk["abandoned_log_density"]) if med_lp99 is not None else None,
            "defaults_retained_reference_log_density": ref_m, "defaults_retained_median_iqr": iqr_m,
            "T1_defaults_warnings_name_chain": t1, "T2_defaults_reference_shift_gt_3sd": t2, "defaults_shift_ref_sd": d_shift,
            "T3_wp89_signature_lp99_below_reference_minus_3iqr": t3, "trapped_at_defaults": bool(t1 or t2 or t3),
            "abandoned_target_calls": chk["abandoned_target_calls"], "replacement_start_log_density": chk.get("replacement_start_log_density"),
            "restarted_chain_shift_ref_sd": g_shift, "restarted_chain_warned": chain in g_warned,
            "guard_cell_passed": passed, "defaults_cell_passed": d.get("passed") if d.get("kind") == "pdb" else None,
            "restarted_chain_ok": (g_shift is None or g_shift <= SHIFT) and chain not in g_warned}


def analyze(env: dict | None = None) -> None:
    env = env or {}
    man = manifest()
    cells = {c["id"]: load(c["id"]) for c in man}
    blocks = {b["name"]: b for b in PROTOCOL["blocks"]}
    P, F, S = blocks["P"], blocks["F"], blocks["S"]
    guard = GUARD
    summary: dict = {"schema": "trap-guard-confirmation-v1-summary", "ledger_id": PROTOCOL["ledger_id"], "environment": env}
    ident_checked, ident_failed, errors, firings = [], [], [], []

    # ---- Part 1
    seeds = P["seeds"]
    need = math.ceil(5 * len(seeds) / 6)
    per_model, headline, paired_all = {}, {}, []
    new_div_models, new_div_passing, below = [], [], []
    for m in P["models"]:
        d = [cells.get(f"P-{m}-defaults-{s}") for s in seeds]
        g = [cells.get(f"P-{m}-{guard}-{s}") for s in seeds]
        paired = []
        for s, x, y in zip(seeds, d, g):
            for c in (x, y):
                if not ok(c):
                    errors.append(c["id"] if c else f"P-{m}-?-{s} (missing)")
            if ok(x) and ok(y):
                if x["min_bulk_ess_per_gradient"] > 0:
                    paired.append(y["min_bulk_ess_per_gradient"] / x["min_bulk_ess_per_gradient"])
                    paired_all.append(paired[-1])
                idn = identity(x, y)
                ident_checked.append(f"P:{m}:{s}")
                if not idn["holds"]:
                    ident_failed.append(f"P:{m}:{s}")
                for ch in idn["fired"]:
                    firings.append(audit_firing("P", f"{m}:{s}", x, y, ch))
                if x["passed"] and y["divergences"] > x["divergences"]:
                    new_div_passing.append(f"P:{m}:{s}")
        if len(paired) >= need:
            headline[m] = statistics.median(paired)
        dd = sum(x.get("divergences", 0) for x in d if ok(x))
        dg = sum(y.get("divergences", 0) for y in g if ok(y))
        if dg > dd:
            new_div_models.append(m)
        if m not in headline or headline[m] < 0.9:
            below.append(m)
        ratios = [min(r for r in x["step_ratio_99"] if r is not None) for x in d if ok(x) and any(r is not None for r in x["step_ratio_99"])]
        per_model[m] = {"passes_defaults": sum(bool(ok(x) and x["passed"]) for x in d), "passes_guard": sum(bool(ok(y) and y["passed"]) for y in g),
                        "paired_ratios": paired, "headline_ratio": headline.get(m), "divergences_defaults": dd, "divergences_guard": dg,
                        "fired_cells": [s for s, y in zip(seeds, g) if ok(y) and y["restarted_chains"]],
                        "min_step_ratio_99_defaults": min(ratios) if ratios else None,
                        "warned_cells_defaults": [s for s, x in zip(seeds, d) if ok(x) and x["chain_warning_chains"]],
                        "shifted_cells_defaults": [s for s, x in zip(seeds, d) if ok(x) and x["shifted_chains"]],
                        "max_rank_rhat_defaults": [x["max_rank_rhat"] if ok(x) else None for x in d],
                        "max_abs_z_passing_guard": max([y["max_abs_z"] for y in g if ok(y) and y["passed"] and y.get("max_abs_z") is not None], default=None),
                        "wall_per_gradient_ratio": statistics.median([(y["wall_seconds_pinned_cotenanted"] / y["gradients_total"]) / (x["wall_seconds_pinned_cotenanted"] / x["gradients_total"])
                                                                      for x, y in zip(d, g) if ok(x) and ok(y)] or [float("nan")])}
    passes = {"defaults": sum(v["passes_defaults"] for v in per_model.values()), "guard": sum(v["passes_guard"] for v in per_model.values())}
    rng = np.random.default_rng(0)
    boot = [float(np.median(rng.choice(paired_all, size=len(paired_all), replace=True))) for _ in range(2000)] if paired_all else []
    paired_summary = {"pairs": len(paired_all), "median": statistics.median(paired_all) if paired_all else None,
                      "bootstrap_95_interval_of_median": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))] if boot else None,
                      "min": min(paired_all) if paired_all else None, "max": max(paired_all) if paired_all else None,
                      "pairs_not_equal_to_1": sum(1 for r in paired_all if r != 1.0)}

    # ---- Part 2
    fd = {s: cells.get(f"F-diag-{s}") for s in F["seeds"]}
    fg = {s: cells.get(f"F-{guard}-{s}") for s in F["seeds"]}
    for s in F["seeds"]:
        for c in (fd[s], fg[s]):
            if not ok(c):
                errors.append(c["id"] if c else f"F-?-{s} (missing)")
        if ok(fd[s]) and ok(fg[s]):
            idn = identity(fd[s], fg[s])
            ident_checked.append(f"F:{s}")
            if not idn["holds"]:
                ident_failed.append(f"F:{s}")
            for ch in idn["fired"]:
                firings.append(audit_firing("F", str(s), fd[s], fg[s], ch))

    def funnel_arm(cs: dict) -> dict:
        cs = {s: c for s, c in cs.items() if ok(c)}
        est = [c["tail_mass"]["estimate"] for c in cs.values()]
        p5 = statistics.fmean(est) if est else None
        se = statistics.stdev(est) / math.sqrt(len(est)) if len(est) > 1 else None
        return {"cells": len(cs), "p5": p5, "se": se, "abs_error": abs(p5 - EXACT_P5) if p5 is not None else None,
                "within_2se": (p5 is not None and se is not None and abs(p5 - EXACT_P5) <= 2 * se),
                "divergences": sum(ch["divergences"] for c in cs.values() for ch in c["chains_data"]),
                "fired_cells": [s for s, c in cs.items() if funnel_fired(c)], "fired_chains": sum(len(funnel_fired(c)) for c in cs.values()),
                "min_step_ratio_99": min((x["step"] / x["median_step"] for c in cs.values() for ch in c["chains_data"] for x in ch.get("trapped_chain_checks", []) if x["median_step"]), default=None)}
    funnel = {"diag": funnel_arm(fd), "guard": funnel_arm(fg)}

    # ---- Part 3
    sd = {s: cells.get(f"S-defaults-{s}") for s in S["seeds"]}
    sg = {s: cells.get(f"S-{guard}-{s}") for s in S["seeds"]}
    sv = {"defaults": {"cells": 0, "chains": 0, "trapped_chains": 0, "trapped_cells": 0, "trapped": [], "warned_chains": 0, "walls": []},
          "guard": {"cells": 0, "chains": 0, "trapped_chains": 0, "trapped_cells": 0, "trapped": [], "warned_chains": 0, "walls": [], "fired": []}}
    for s in S["seeds"]:
        for arm, c in (("defaults", sd[s]), ("guard", sg[s])):
            if not ok(c):
                errors.append(c["id"] if c else f"S-{arm}-{s} (missing)")
                continue
            a = sv[arm]
            tr = sv_trapped(c)
            a["cells"] += 1
            a["chains"] += len(c["chains_data"])
            a["trapped_chains"] += len(tr)
            a["trapped_cells"] += bool(tr)
            a["warned_chains"] += len(c.get("chain_warning_chains") or [])
            a["walls"].append(c["wall_seconds_pinned_cotenanted"])
            for ch in tr:
                a["trapped"].append({"seed": s, "chain": ch, "start_log_sigma": c["start_log_sigma"][ch],
                                     "median_log_sigma": c["chains_data"][ch]["median_log_sigma"],
                                     "step_99": c["chains_data"][ch]["step_at_transition"].get("99"),
                                     "warned": ch in (c.get("chain_warning_chains") or [])})
        if ok(sd[s]) and ok(sg[s]):
            idn = identity(sd[s], sg[s])
            ident_checked.append(f"S:{s}")
            if not idn["holds"]:
                ident_failed.append(f"S:{s}")
            for ch in idn["fired"]:
                rec = audit_firing("S", str(s), sd[s], sg[s], ch)
                rec["defaults_census_trapped"] = ch in sv_trapped(sd[s])
                rec["guard_census_trapped"] = ch in sv_trapped(sg[s])
                sv["guard"]["fired"].append(rec)
    for a in sv.values():
        a["median_wall"] = statistics.median(a["walls"]) if a["walls"] else None
        a.pop("walls")

    # ---- rules
    hz = [v["max_abs_z_passing_guard"] for v in per_model.values() if v["max_abs_z_passing_guard"] is not None]
    false_firings = [f for f in firings if not f["trapped_at_defaults"]]
    n_cells = len(P["models"]) * len(seeds)
    rules = {
        "R1_passes": {"defaults": passes["defaults"], "guard": passes["guard"], "cells_per_arm": n_cells,
                      "held": not any(e.startswith("P") for e in errors) and passes["guard"] >= passes["defaults"]},
        "R2_bit_identity": {"pairs_checked": len(ident_checked), "pairs_failed": ident_failed, "errors": errors,
                            "held": bool(ident_checked) and not ident_failed and not errors},
        "R3_no_new_divergences": {"models_with_more_guard_divergences": new_div_models, "passing_cells_with_new_divergences": new_div_passing,
                                  "held": not new_div_models and not new_div_passing},
        "R4_headline_ge_0.98": {"geomean": geomean(list(headline.values())) if headline else None, "models": len(headline),
                                "models_without_5_paired_seeds": [m for m in P["models"] if m not in headline],
                                "paired_per_seed": paired_summary,
                                "held": len(headline) == len(P["models"]) and geomean(list(headline.values())) >= 0.98},
        "R5_funnel": {**funnel["guard"], "exact": EXACT_P5, "diag_p5": funnel["diag"]["p5"],
                      "held": funnel["guard"]["cells"] == len(F["seeds"]) and funnel["guard"]["within_2se"]},
        "R6_sv_guard_zero_trapped": {"guard_trapped_chains": sv["guard"]["trapped_chains"], "guard_chains": sv["guard"]["chains"],
                                     "defaults_trapped_chains": sv["defaults"]["trapped_chains"], "defaults_chains": sv["defaults"]["chains"],
                                     "held": sv["guard"]["cells"] == len(S["seeds"]) and sv["guard"]["trapped_chains"] == 0},
        "R7_false_firings": {"firings_parts_1_2": firings, "false_firings": false_firings, "count_false": len(false_firings),
                             "held": not false_firings and not errors},
        "R8_library_integrity": {k: env.get(k) for k in ("library_diff_empty", "kernel_fingerprint_default_passed", "kernel_fingerprint_research_passed",
                                                         "trapped_chain_restart_tests_passed", "clippy_library_clean", "clippy_study_clean")},
    }
    rules["R8_library_integrity"]["held"] = all(bool(v) for v in rules["R8_library_integrity"].values())
    failed = [k.split("_")[0] for k, r in rules.items() if not r["held"]]
    verdict = "QUALIFIES: every preregistered rule holds; proposed for the flip" if not failed else "DOES NOT QUALIFY (failed: " + ", ".join(failed) + "); stays research"
    wall_ratios = [v["wall_per_gradient_ratio"] for v in per_model.values() if v["wall_per_gradient_ratio"] == v["wall_per_gradient_ratio"]]
    reported = {"max_abs_z_passing_guard": max(hz) if hz else None, "models_below_0.9": below,
                "wall_per_gradient_guard_over_defaults_geomean": geomean(wall_ratios) if wall_ratios else None,
                "part1_firings": len([f for f in firings if f["block"] == "P"]), "part2_firings": len([f for f in firings if f["block"] == "F"]),
                "part3_firings": len(sv["guard"]["fired"]), "sv_median_wall": {k: v["median_wall"] for k, v in sv.items()},
                "funnel_diag": funnel["diag"]}
    summary.update(verdict=verdict, rules=rules, reported=reported, per_model=per_model, funnel=funnel, sv=sv,
                   predictions=score_predictions(rules, per_model, firings, sv, funnel))
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, default=float) + "\n", encoding="utf-8")
    (ART / "results-table.md").write_text(results_table(summary), encoding="utf-8")
    print(json.dumps({"verdict": verdict, "rules": {k: v["held"] for k, v in rules.items()}}, indent=1))
    log("analysis written")


def score_predictions(rules, per_model, firings, sv, funnel) -> dict:
    P = PROTOCOL["predictions"]
    p1 = [f for f in firings if f["block"] == "P"]
    out = {
        "P1_part1_firings_0_to_2_only_lotka_or_GLMM_all_trapped": {
            "text": P["P1"], "observed": {"firings": len(p1), "models": sorted({f["cell"].split(":")[0] for f in p1}),
                                          "all_trapped": all(f["trapped_at_defaults"] for f in p1)},
            "held": len(p1) <= 2 and all(f["cell"].split(":")[0] in ("hudson_lynx_hare-lotka_volterra", "GLMM_Poisson_data-GLMM_Poisson_model") for f in p1)
            and all(f["trapped_at_defaults"] for f in p1)},
        "P2_part1_passes": {"text": P["P2"], "observed": {"defaults": rules["R1_passes"]["defaults"], "guard": rules["R1_passes"]["guard"]},
                            "held": 98 <= rules["R1_passes"]["defaults"] <= 112 and rules["R1_passes"]["guard"] >= rules["R1_passes"]["defaults"]},
        "P3_headline": {"text": P["P3"], "observed": rules["R4_headline_ge_0.98"]["geomean"],
                        "held": rules["R4_headline_ge_0.98"]["geomean"] is not None and 0.99 <= rules["R4_headline_ge_0.98"]["geomean"] <= 1.02},
        "P4_funnel": {"text": P["P4"], "observed": {"fired_chains": funnel["guard"]["fired_chains"], "within_2se": funnel["guard"]["within_2se"]},
                      "held": funnel["guard"]["fired_chains"] == 0 and funnel["guard"]["within_2se"]},
        "P5_sv": {"text": P["P5"], "observed": {"defaults_trapped": sv["defaults"]["trapped_chains"], "guard_trapped": sv["guard"]["trapped_chains"],
                                                "guard_firings": len(sv["guard"]["fired"]),
                                                "firings_trapped_or_signature": sum(1 for f in sv["guard"]["fired"] if f["defaults_census_trapped"] or f["trapped_at_defaults"])},
                  "held": 3 <= sv["defaults"]["trapped_chains"] <= 16 and sv["guard"]["trapped_chains"] == 0 and 6 <= len(sv["guard"]["fired"]) <= 16
                  and all(f["defaults_census_trapped"] or f["trapped_at_defaults"] for f in sv["guard"]["fired"])},
        "P6_bit_identity": {"text": P["P6"], "held": rules["R2_bit_identity"]["held"]},
        "P7_library": {"text": P["P7"], "held": rules["R8_library_integrity"]["held"]},
    }
    return out


def results_table(s: dict) -> str:
    r = s["rules"]
    f = lambda x, sp=".3g": "-" if x is None else format(x, sp)  # noqa: E731
    L = ["# WP90 results (generated by `run_study.py analyze`)", "", f"Verdict: {s['verdict']}", "",
         "## Rules", "", "| rule | observed | held |", "|---|---|---|"]
    L.append(f"| R1 passes guard >= defaults (Part 1) | {r['R1_passes']['guard']} vs {r['R1_passes']['defaults']} of {r['R1_passes']['cells_per_arm']} | {r['R1_passes']['held']} |")
    L.append(f"| R2 bit identity (unfired cells whole, fired cells' untouched chains; all parts) | {r['R2_bit_identity']['pairs_checked']} pairs, failed {r['R2_bit_identity']['pairs_failed']}, errors {r['R2_bit_identity']['errors']} | {r['R2_bit_identity']['held']} |")
    L.append(f"| R3 no new divergences | models {r['R3_no_new_divergences']['models_with_more_guard_divergences']}, passing cells {r['R3_no_new_divergences']['passing_cells_with_new_divergences']} | {r['R3_no_new_divergences']['held']} |")
    ps = r["R4_headline_ge_0.98"]["paired_per_seed"]
    L.append(f"| R4 headline ESS/gradient guard/defaults >= 0.98 | geomean {f(r['R4_headline_ge_0.98']['geomean'], '.4f')} over {r['R4_headline_ge_0.98']['models']} models; paired per-seed median {f(ps['median'], '.4f')}, bootstrap 95% {ps['bootstrap_95_interval_of_median']}, range [{f(ps['min'], '.4f')}, {f(ps['max'], '.4f')}], pairs != 1: {ps['pairs_not_equal_to_1']} | {r['R4_headline_ge_0.98']['held']} |")
    R5 = r["R5_funnel"]
    L.append(f"| R5 funnel P5 within 2 s.e. of {EXACT_P5:.5f} | {R5['cells']} cells, P5 {f(R5['p5'], '.5f')} +- {f(R5['se'], '.5f')}, fired chains {R5['fired_chains']} (cells {R5['fired_cells']}), min ratio {f(R5['min_step_ratio_99'])}; diag P5 {f(R5['diag_p5'], '.5f')} | {R5['held']} |")
    R6 = r["R6_sv_guard_zero_trapped"]
    L.append(f"| R6 SV trapped chains guard 0 | guard {R6['guard_trapped_chains']}/{R6['guard_chains']}, defaults {R6['defaults_trapped_chains']}/{R6['defaults_chains']} | {R6['held']} |")
    R7 = r["R7_false_firings"]
    L.append(f"| R7 false firings over Parts 1-2 = 0 | firings {len(R7['firings_parts_1_2'])}, false {R7['count_false']} | {R7['held']} |")
    R8 = r["R8_library_integrity"]
    L.append(f"| R8 library integrity | {', '.join(f'{k} {v}' for k, v in R8.items() if k != 'held')} | {R8['held']} |")
    L += ["", "## Part 1 per model", "", "| model | pass defaults / guard | headline guard/defaults | div d / g | fired cells | min step ratio at 99 (defaults) | warned cells (defaults) | shifted cells (defaults) | wall/grad ratio |", "|---|---|---|---|---|---|---|---|---|"]
    for m, v in s["per_model"].items():
        L.append(f"| {m} | {v['passes_defaults']} / {v['passes_guard']} | {f(v['headline_ratio'], '.4f')} | {v['divergences_defaults']} / {v['divergences_guard']} | {v['fired_cells']} | {f(v['min_step_ratio_99_defaults'])} | {v['warned_cells_defaults']} | {v['shifted_cells_defaults']} | {f(v['wall_per_gradient_ratio'], '.3f')} |")
    L += ["", "## Firing audit (R7; every firing on Parts 1-2, then Part 3 for the record)", "",
          "| part | cell | chain | step | median step | ratio | lp at 99 | chain median lp at 99 | shortfall (nats) | T1 warned | T2 shift > 3 SD | T3 signature | trapped | restarted chain ok | guard cell passed |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in list(R7["firings_parts_1_2"]) + list(s["sv"]["guard"]["fired"]):
        L.append(f"| {x['block']} | {x['cell']} | {x['chain']} | {f(x['step'])} | {f(x['median_step'])} | {f(x['step_ratio'])} | {f(x['log_density_99'], '.1f')} | {f(x['chain_median_log_density_99'], '.1f')} | {f(x['shortfall_99_nats'], '.1f')} | {x['T1_defaults_warnings_name_chain']} | {x['T2_defaults_reference_shift_gt_3sd']} | {x['T3_wp89_signature_lp99_below_reference_minus_3iqr']} | {x['trapped_at_defaults']}{' (census ' + str(x.get('defaults_census_trapped')) + ')' if 'defaults_census_trapped' in x else ''} | {x['restarted_chain_ok']} | {x['guard_cell_passed']} |")
    L += ["", "## Part 3 (SV, WP89 census with the frozen anchor)", "", "| arm | cells | chains | trapped chains | trapped cells | warned chains | median wall s |", "|---|---|---|---|---|---|---|"]
    for arm, a in s["sv"].items():
        L.append(f"| {arm} | {a['cells']} | {a['chains']} | {a['trapped_chains']} | {a['trapped_cells']} | {a['warned_chains']} | {f(a['median_wall'], '.2f')} |")
    L += ["", "| arm | seed | chain | start log_sigma | median log_sigma | step at 99 | warned |", "|---|---|---|---|---|---|---|"]
    for arm, a in s["sv"].items():
        for t in a["trapped"]:
            L.append(f"| {arm} | {t['seed']} | {t['chain']} | {f(t['start_log_sigma'])} | {f(t['median_log_sigma'])} | {f(t['step_99'])} | {t['warned']} |")
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
        run(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "analyze":
        p = ART / "environment.json"
        analyze(json.loads(p.read_text(encoding="utf-8")) if p.exists() else {})
    else:
        raise SystemExit(f"unknown command {cmd}")
