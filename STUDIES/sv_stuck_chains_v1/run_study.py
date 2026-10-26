#!/usr/bin/env python3
"""WP89 driver (`STUDIES/sv_stuck_chains_v1`): the WP84 SV model, one chain frozen in warmup.

    python run_study.py manifest            # the frozen cell order (from protocol.json)
    python run_study.py smoke               # non-evidence smoke on diagnostic seeds (disclosed, before the freeze)
    python run_study.py run [part]          # every evidence cell in manifest order (resumable; never reruns a written cell)
    python run_study.py analyze             # artifacts/summary.json + artifacts/results-table.md

Run on the Linux box, inside lane 1, as `taskset -c 0-3 ~/venv/bin/python run_study.py run`
with `RAYON_NUM_THREADS=4 OMP_NUM_THREADS=1`. Environment: `WP89_ART` (artifact root, default
`artifacts/`), `WP89_MODELS` (BridgeStan model libraries for the house models), `WP89_WORK`
(scratch: CmdStan executable, telemetry before gzip), `WP89_BIN` (release binaries).

Cell kinds:
- `sv-owalnuts`: `sv-cell` (Rust; per-transition telemetry gzipped to artifacts/telemetry, out of git).
- `sv-cmdstan`: CmdStan 2.39.0 via cmdstanpy, defaults, `save_warmup=True`, inits drawn here
  (uniform(-2, 2), numpy seeded by the cell seed) so the start can be recorded; the start's log
  density is the numpy density (checked against `sv-cell`'s Rust density in the smoke).
- `sv-nutpie`: nutpie 0.16.8 defaults (its own standard-normal init), `save_warmup=True`,
  `store_mass_matrix=True`; the first warmup draw stands in for the start (nutpie does not
  expose the init point).
- `funnel`: Neal's 10-D funnel, 4 x 2,000/20,000 (WP85 harness), the candidate vs `diag`.
- `pdb`: three house posteriordb models, v7 gates (WP67 harness and scoring, verbatim).

Harness reuse (every change is listed in PREREGISTRATION.md): `sv_cell.rs` is the WP67
`trap_cell.rs` observer pattern on the WP84 `Sv` target; `pdb_cell.rs` / scoring are WP67's;
`funnel.rs` is WP85's. CmdStan / nutpie arms follow WP84's `run_cells.py` with warmup saved.
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
import traceback
import zipfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8")) if (HERE / "protocol.json").exists() else {}
ART = Path(os.environ.get("WP89_ART", HERE / "artifacts"))
CELLS = ART / "cells"
TELEM = ART / "telemetry"
WORK = Path(os.environ.get("WP89_WORK", HERE / "work"))
MODELS = Path(os.environ.get("WP89_MODELS", HERE / "models"))
BIN = Path(os.environ.get("WP89_BIN", HERE / "target" / "release"))
DATA = HERE / "models" / "data.json"
STAN = HERE / "models" / "sv.stan"
PDB = Path(os.path.expanduser("~/infra/posteriordb/posterior_database"))
N = 250
CHAINS = 4
# Stan's schedule at 1,000 warmup: ends of init / S1 / S2 / S3 / S4 / S5 / term.
CHECKPOINTS = {"init": 74, "S1": 99, "S2": 149, "S3": 249, "S4": 449, "S5": 949, "term": 999}
SHIFT = 3.0  # trapped chain on a house model: more than 3 reference SD off (WP67)


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# --------------------------------------------------------------------------- the SV model in numpy

_DATA = json.loads(DATA.read_text(encoding="utf-8"))


def stan_data(n: int) -> dict:
    p = _DATA["priors"]
    return dict(n=n, y=_DATA["y"][:n], rho=_DATA["rho"], nu=_DATA["nu"], mu_mean=p["mu_mean"], mu_sd=p["mu_sd"],
                log_sigma_mean=p["log_sigma_mean"], log_sigma_sd=p["log_sigma_sd"], beta_sd=p["beta_sd"])


def numpy_lp(q: np.ndarray, n: int) -> float:
    """The normalised log density of the Rust `Sv` target (and `sv.stan` up to a constant)."""
    p, rho, nu = _DATA["priors"], _DATA["rho"], _DATA["nu"]
    y = np.asarray(_DATA["y"][:n])
    mu, ls, beta, z = q[0], q[1], q[2], np.asarray(q[3:3 + n])
    sigma = math.exp(ls)

    def norm(x, m, s):
        u = (x - m) / s
        return -0.5 * u * u - math.log(s) - 0.5 * math.log(2 * math.pi)

    lp = norm(mu, p["mu_mean"], p["mu_sd"]) + norm(ls, p["log_sigma_mean"], p["log_sigma_sd"]) + norm(beta, 0.0, p["beta_sd"])
    lp += float(np.sum(-0.5 * z * z - 0.5 * math.log(2 * math.pi)))
    h = np.empty(n)
    h[0] = mu + sigma * z[0] / math.sqrt(1 - rho * rho)
    for i in range(1, n):
        h[i] = mu + rho * (h[i - 1] - mu) + sigma * z[i]
    cst = math.lgamma((nu + 1) / 2) - math.lgamma(nu / 2) - 0.5 * math.log(nu * math.pi)
    r = y - beta
    a = r * r * np.exp(-h) / nu
    lp += float(np.sum(cst - 0.5 * h - 0.5 * (nu + 1) * np.log1p(a)))
    return lp


def h_last(mu, ls, z, rho):
    """Vectorised h_n over draws: mu, ls (draws,), z (draws, n)."""
    s = np.exp(ls)
    h = mu + s * z[:, 0] / math.sqrt(1 - rho * rho)
    for i in range(1, z.shape[1]):
        h = mu + rho * (h - mu) + s * z[:, i]
    return h


# --------------------------------------------------------------------------- cells

def cell_path(cid: str) -> Path:
    return CELLS / f"{cid}.json"


def write_cell(cid: str, payload: dict) -> None:
    CELLS.mkdir(parents=True, exist_ok=True)
    cell_path(cid).write_text(json.dumps(payload) + "\n", encoding="utf-8")


def gzip_telemetry(cid: str, raw: Path) -> None:
    if raw.exists():
        TELEM.mkdir(parents=True, exist_ok=True)
        with open(raw, "rb") as f, gzip.open(TELEM / f"{cid}.json.gz", "wb", compresslevel=6) as g:
            g.write(f.read())
        raw.unlink()


def run_sv_owalnuts(cid: str, arm: str, seed: int) -> None:
    if cell_path(cid).exists():
        return
    WORK.mkdir(parents=True, exist_ok=True)
    out, raw = cell_path(cid), WORK / f"{cid}.telemetry.json"
    CELLS.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    cmd = [str(BIN / "sv-cell"), str(DATA), str(N), arm, str(seed), str(out), str(raw), str(CHAINS)]
    cp = subprocess.run(cmd, capture_output=True, text=True)
    log(f"{cid} [{time.time() - t0:.1f}s] rc {cp.returncode} {cp.stderr.strip()[-300:]}")
    gzip_telemetry(cid, raw)
    if cp.returncode != 0 or not out.exists():
        write_cell(cid, {"id": cid, "kind": "sv-owalnuts", "arm": arm, "seed": seed, "status": "error",
                         "returncode": cp.returncode, "stderr": cp.stderr[-4000:]})


def chain_summary(mu, ls, hl):
    """Per-chain retained summaries: mu, ls, hl are (chains, draws)."""
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


def run_sv_cmdstan(cid: str, seed: int) -> None:
    if cell_path(cid).exists():
        return
    import cmdstanpy
    cmdstanpy.set_cmdstan_path(os.path.expanduser(PROTOCOL["software"]["cmdstan_path"]))
    exe_dir = WORK / "cmdstan-exe"
    exe_dir.mkdir(parents=True, exist_ok=True)
    src = exe_dir / "sv.stan"
    if not src.exists():
        src.write_text(STAN.read_text(encoding="utf-8"), encoding="utf-8")
    model = cmdstanpy.CmdStanModel(stan_file=str(src))
    rng = np.random.default_rng(seed)
    inits = [rng.uniform(-2.0, 2.0, size=3 + N) for _ in range(CHAINS)]
    init_dicts = [dict(mu=float(q[0]), log_sigma=float(q[1]), beta=float(q[2]), z=[float(v) for v in q[3:]]) for q in inits]
    rec = {"id": cid, "kind": "sv-cmdstan", "arm": "cmdstan", "seed": seed, "n": N,
           "init": {"rule": "uniform(-2, 2) per unconstrained coordinate, numpy default_rng(seed), one candidate (CmdStan's rule)",
                    "start_log_densities": [numpy_lp(q, N) for q in inits]},
           "start_log_sigma": [float(q[1]) for q in inits], "start_mu": [float(q[0]) for q in inits]}
    tmp = WORK / "stan-tmp" / cid
    tmp.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        fit = model.sample(data=stan_data(N), chains=CHAINS, parallel_chains=CHAINS, seed=seed, inits=init_dicts,
                           save_warmup=True, show_progress=False, output_dir=str(tmp))
        wall = time.time() - t0
        d = fit.draws(inc_warmup=True, concat_chains=False)  # (draws, chains, cols)
        cols = list(fit.column_names)
        get = lambda name: d[:, :, cols.index(name)].T  # (chains, draws)
        W = int(fit.num_draws_warmup)
        step, lp, ls, mu, hl = get("stepsize__"), get("lp__"), get("log_sigma"), get("mu"), get("h_last")
        div = get("divergent__")
        rec.update(status="ok", wall_seconds_pinned_cotenanted=wall, warmup=W, retained=int(d.shape[0]) - W,
                   warmup_step_trace=[[float(x) for x in step[c, :W]] for c in range(CHAINS)],
                   warmup_lp_trace_every_10=[[float(x) for x in lp[c, :W:10]] for c in range(CHAINS)],
                   warmup_log_sigma_trace_every_10=[[float(x) for x in ls[c, :W:10]] for c in range(CHAINS)],
                   step_at_checkpoints=[{k: float(step[c, t]) for k, t in CHECKPOINTS.items()} for c in range(CHAINS)],
                   final_step_size=[float(s) for s in np.atleast_1d(fit.step_size)],
                   inverse_metric_diagonal=[[float(x) for x in np.atleast_2d(fit.metric)[c]] for c in range(CHAINS)],
                   divergences=[int(div[c, W:].sum()) for c in range(CHAINS)],
                   warmup_divergences=[int(div[c, :W].sum()) for c in range(CHAINS)],
                   chains_data=chain_summary(mu[:, W:], ls[:, W:], hl[:, W:]),
                   retained_lp_median=[float(np.median(lp[c, W:])) for c in range(CHAINS)],
                   retained_draws_mu_logsigma_hlast=[np.stack([mu[c, W:], ls[c, W:], hl[c, W:]], -1).round(6).tolist()
                                                     for c in range(CHAINS)],
                   rhat=rhat_stats(mu[:, W:], ls[:, W:], hl[:, W:]))
    except Exception as e:  # failures are results
        rec.update(status="error", wall_seconds_pinned_cotenanted=time.time() - t0, error=repr(e),
                   traceback=traceback.format_exc()[-4000:])
    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()
    write_cell(cid, rec)
    log(f"{cid} [{rec['wall_seconds_pinned_cotenanted']:.1f}s] {rec['status']}")


@functools.lru_cache(maxsize=None)
def nutpie_model():
    import nutpie
    return nutpie.compile_stan_model(code=STAN.read_text(encoding="utf-8"))


def run_sv_nutpie(cid: str, seed: int) -> None:
    if cell_path(cid).exists():
        return
    import nutpie
    compiled = nutpie_model()
    rec = {"id": cid, "kind": "sv-nutpie", "arm": "nutpie", "seed": seed, "n": N,
           "init": {"rule": "nutpie default for Stan models: standard normal per unconstrained coordinate "
                            "(nutpie src/stan.rs init_position); the start itself is not exposed, the first warmup draw stands in"}}
    t0 = time.time()
    try:
        m = compiled.with_data(**stan_data(N))
        tr = nutpie.sample(m, chains=CHAINS, cores=CHAINS, seed=seed, save_warmup=True, progress_bar=False,
                           store_mass_matrix=True)
        wall = time.time() - t0
        ws, wp, ss, post = tr.warmup_sample_stats, tr.warmup_posterior, tr.sample_stats, tr.posterior
        step_w = np.asarray(ws["step_size"])  # (chains, tune)
        logp_w = np.asarray(ws["logp"])
        ls_w, mu_w = np.asarray(wp["log_sigma"]), np.asarray(wp["mu"])
        mm = np.asarray(ws["mass_matrix_inv"]) if "mass_matrix_inv" in ws else None  # (chains, tune, dim)
        W = step_w.shape[1]
        mu, ls, hl = (np.asarray(post[v]) for v in ("mu", "log_sigma", "h_last"))
        cps = {k: min(t, W - 1) for k, t in CHECKPOINTS.items()}
        rec.update(status="ok", wall_seconds_pinned_cotenanted=wall, warmup=W, retained=int(mu.shape[1]),
                   first_draw_log_density=[float(logp_w[c, 0]) for c in range(CHAINS)],
                   first_draw_log_sigma=[float(ls_w[c, 0]) for c in range(CHAINS)],
                   first_draw_mu=[float(mu_w[c, 0]) for c in range(CHAINS)],
                   first_draw_step=[float(step_w[c, 0]) for c in range(CHAINS)],
                   warmup_step_trace=[[float(x) for x in step_w[c]] for c in range(CHAINS)],
                   warmup_lp_trace_every_10=[[float(x) for x in logp_w[c, ::10]] for c in range(CHAINS)],
                   warmup_log_sigma_trace_every_10=[[float(x) for x in ls_w[c, ::10]] for c in range(CHAINS)],
                   step_at_checkpoints=[{k: float(step_w[c, t]) for k, t in cps.items()} for c in range(CHAINS)],
                   final_step_size=[float(np.asarray(ss["step_size"])[c, -1]) for c in range(CHAINS)],
                   inverse_metric_diagonal_at=({str(t): [[float(x) for x in mm[c, t]] for c in range(CHAINS)]
                                               for t in (0, 9, 19, 49, 99, 299, W - 1)} if mm is not None else None),
                   divergences=[int(x) for x in np.asarray(ss["diverging"]).sum(axis=1)],
                   warmup_divergences=[int(x) for x in np.asarray(ws["diverging"]).sum(axis=1)],
                   chains_data=chain_summary(mu, ls, hl),
                   retained_lp_median=[float(np.median(np.asarray(ss["logp"])[c])) for c in range(CHAINS)],
                   retained_draws_mu_logsigma_hlast=[np.stack([mu[c], ls[c], hl[c]], -1).round(6).tolist() for c in range(CHAINS)],
                   rhat=rhat_stats(mu, ls, hl))
    except Exception as e:
        rec.update(status="error", wall_seconds_pinned_cotenanted=time.time() - t0, error=repr(e),
                   traceback=traceback.format_exc()[-4000:])
    write_cell(cid, rec)
    log(f"{cid} [{rec['wall_seconds_pinned_cotenanted']:.1f}s] {rec['status']}")


def run_funnel(cid: str, arm: str, seed: int) -> None:
    if cell_path(cid).exists():
        return
    CELLS.mkdir(parents=True, exist_ok=True)
    out = cell_path(cid)
    t0 = time.time()
    cmd = [str(BIN / "funnel"), arm, "2000", "20000", str(seed), str(out)]
    cp = subprocess.run(cmd, capture_output=True, text=True)
    log(f"{cid} [{time.time() - t0:.1f}s] rc {cp.returncode} {cp.stderr.strip()[-200:]}")
    if cp.returncode != 0 or not out.exists():
        write_cell(cid, {"id": cid, "kind": "funnel", "arm": arm, "seed": seed, "status": "error",
                         "returncode": cp.returncode, "stderr": cp.stderr[-4000:]})


# ---- house models (WP67 scoring, verbatim except the artifact paths)

def short(model: str) -> str:
    return model.replace("-", "__")


def _zip_json(path: Path):
    with zipfile.ZipFile(path) as z:
        inner = [n for n in z.namelist() if n.endswith(".json")][0]
        return json.loads(z.read(inner).decode("utf-8"))


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
    return {"mean": arr.reshape(-1, arr.shape[-1]).mean(0), "sd": arr.reshape(-1, arr.shape[-1]).std(0, ddof=1),
            "bulk_ess": bulk, "tail_ess": tail, "rhat": rhat, "mcse": mcse}


@functools.lru_cache(maxsize=None)
def reference(model: str) -> dict:
    info = json.loads((PDB / "posteriors" / f"{model}.json").read_text(encoding="utf-8"))
    ref = _zip_json(PDB / "reference_posteriors" / "draws" / "draws" / f"{info['reference_posterior_name']}.json.zip")
    names = list(ref[0].keys())
    arr = np.asarray([[c[n] for n in names] for c in ref], dtype=np.float64)
    arr = np.transpose(arr, (0, 2, 1))
    return {"names": names, **arviz_stats(arr)}


@functools.lru_cache(maxsize=None)
def stan_model(model: str):
    import bridgestan as bs
    so, data = MODELS / f"{model}_model.so", MODELS / f"{model}.data.json"
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


def score(model: str, draws: np.ndarray, grads_total: int, divergences: int) -> dict:
    G = PROTOCOL["gates"]
    ref = reference(model)
    st = arviz_stats(draws)
    z = (st["mean"] - ref["mean"]) / np.sqrt(st["mcse"] ** 2 + ref["mcse"] ** 2)
    min_bulk, min_tail = float(np.nanmin(st["bulk_ess"])), float(np.nanmin(st["tail_ess"]))
    max_rhat, max_abs_z = float(np.nanmax(st["rhat"])), float(np.nanmax(np.abs(z)))
    shifts = [float(np.nanmax(np.abs((draws[i].mean(0) - ref["mean"]) / ref["sd"]))) for i in range(draws.shape[0])]
    gates = {"completed": True, "max_rank_rhat": max_rhat <= G["max_rank_rhat"], "min_bulk_ess": min_bulk >= G["min_bulk_ess"],
             "min_tail_ess": min_tail >= G["min_tail_ess"], "sampling_divergences": divergences == 0,
             "finite_draws": bool(np.isfinite(draws).all())}
    return {"min_bulk_ess": min_bulk, "min_tail_ess": min_tail, "max_rank_rhat": max_rhat, "max_abs_z": max_abs_z,
            "min_bulk_ess_per_gradient": min_bulk / grads_total, "per_chain_shift_ref_sd": shifts,
            "trapped_chains": [i for i, s in enumerate(shifts) if s > SHIFT], "divergences": divergences,
            "gradients_total": grads_total, "gates": gates, "passed": all(gates.values())}


def run_pdb(cid: str, model: str, arm: str, seed: int) -> None:
    if cell_path(cid).exists():
        return
    CELLS.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    raw = WORK / f"{cid}.raw.json"
    so, data = MODELS / f"{model}_model.so", MODELS / f"{model}.data.json"
    t0 = time.time()
    cmd = [str(BIN / "pdb-cell"), str(so), str(data), arm, str(seed), str(raw), str(CHAINS)]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=PROTOCOL["timeouts"]["pdb_process_seconds"])
        rc, stderr = cp.returncode, cp.stderr
    except subprocess.TimeoutExpired:
        rc, stderr = "timeout", "timeout"
    rec = {"id": cid, "kind": "pdb", "model": model, "arm": arm, "seed": seed, "returncode": rc}
    try:
        if rc != 0 or not raw.exists():
            raise RuntimeError(f"cell process failed: {stderr[-2000:]}")
        r = json.loads(raw.read_text(encoding="utf-8"))
        if r.get("status") != "ok":
            raise RuntimeError(f"sampler error: {r.get('error')}")
        unc = np.asarray([c["samples"] for c in r["chains_data"]], dtype=np.float64)
        ref = reference(model)
        con = constrain(model, unc, ref["names"])
        div = sum(c["divergences"] for c in r["chains_data"])
        grads = sum(c["total_target_calls"] for c in r["chains_data"]) + r["init"]["start_search_calls"]
        sc = score(model, con, grads, div)
        checks = [c["trapped_chain_checks"] for c in r["chains_data"]]
        rec.update(status="ok", wall_seconds_pinned_cotenanted=r["wall_seconds"], draw_hash=r["draw_hash"],
                   chain_draw_hashes=[c["draw_hash"] for c in r["chains_data"]],
                   chain_warnings=r["chain_warnings"], trapped_chain_checks=checks,
                   restarted_chains=[i for i, cs in enumerate(checks) if any(x["restarted"] for x in cs)],
                   step_at_transition_99=[c["step_at_transition_99"] for c in r["chains_data"]],
                   target_calls_total=r["target_calls_total"], **sc)
    except Exception as e:
        rec.update(status="error", error=repr(e), passed=False, gates={"completed": False})
    if raw.exists():
        raw.unlink()
    write_cell(cid, rec)
    log(f"{cid} [{time.time() - t0:.1f}s] {rec['status']} passed={rec.get('passed')} rhat={rec.get('max_rank_rhat')}")


# --------------------------------------------------------------------------- manifest

def manifest() -> list[dict]:
    cells = []
    for block in PROTOCOL["blocks"]:
        for seed in block["seeds"]:
            for arm in block["arms"]:
                if block["kind"] == "pdb":
                    for model in block["models"]:
                        cells.append({"id": f"{block['name']}-{model}-{arm}-{seed}", "kind": "pdb", "model": model,
                                      "arm": arm, "seed": seed, "block": block["name"]})
                else:
                    cells.append({"id": f"{block['name']}-{arm}-{seed}", "kind": block["kind"], "arm": arm, "seed": seed,
                                  "block": block["name"]})
    return cells


def run_cell(c: dict) -> None:
    if cell_path(c["id"]).exists():
        return
    if c["kind"] == "sv":
        if c["arm"] == "cmdstan":
            run_sv_cmdstan(c["id"], c["seed"])
        elif c["arm"] == "nutpie":
            run_sv_nutpie(c["id"], c["seed"])
        else:
            run_sv_owalnuts(c["id"], c["arm"], c["seed"])
    elif c["kind"] == "funnel":
        run_funnel(c["id"], c["arm"], c["seed"])
    elif c["kind"] == "pdb":
        run_pdb(c["id"], c["model"], c["arm"], c["seed"])
    else:
        raise ValueError(c)


def run(part: str | None) -> None:
    (ART / "measured_on.json").write_text(json.dumps({"affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
                                                     "RAYON_NUM_THREADS": os.environ.get("RAYON_NUM_THREADS"),
                                                     "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
                                                     "cwd": os.getcwd(), "python": sys.version}, indent=1) + "\n", encoding="utf-8")
    for c in manifest():
        if part and not c["block"].startswith(part):
            continue
        run_cell(c)


# --------------------------------------------------------------------------- smoke (non-evidence)

def smoke() -> None:
    """Disclosed, non-evidence: diagnostic seeds 9989001.. (never evidence seeds). Checks every code path,
    the numpy density against the Rust density, and `custom_noop` == `defaults` bit for bit."""
    global CELLS, TELEM
    CELLS, TELEM = ART / "smoke" / "cells", ART / "smoke" / "telemetry"
    WORK.mkdir(parents=True, exist_ok=True)
    # density check: numpy vs Rust on the recorded starts of a defaults cell
    seeds = [9989001 + i for i in range(int(os.environ.get("WP89_SMOKE_SEEDS", "30")))]
    for s in seeds:
        run_sv_owalnuts(f"smoke-defaults-{s}", "defaults", s)
    for s in seeds[:2]:
        run_sv_owalnuts(f"smoke-custom_noop-{s}", "custom_noop", s)
        a, b = json.loads(cell_path(f"smoke-defaults-{s}").read_text()), json.loads(cell_path(f"smoke-custom_noop-{s}").read_text())
        log(f"identity {s}: {a['draw_hash']} == {b['draw_hash']} -> {a['draw_hash'] == b['draw_hash']}")
        run_sv_cmdstan(f"smoke-cmdstan-{s}", s)
        run_sv_nutpie(f"smoke-nutpie-{s}", s)
    for arm in os.environ.get("WP89_SMOKE_ARMS", "").split(","):
        if arm:
            for s in seeds[:2]:
                run_sv_owalnuts(f"smoke-{arm}-{s}", arm, s)
    # numpy density vs CmdStan init lp: compare numpy_lp at a random point with sv-cell's recorded start log density
    a = json.loads(cell_path(f"smoke-defaults-{seeds[0]}").read_text())
    tel = json.loads(gzip.open(TELEM / f"smoke-defaults-{seeds[0]}.json.gz").read())
    log(f"rust start lps {a['init']['start_log_densities'][:2]}; telemetry rows per chain {[len(r) for r in tel['rows']]}")
    run_funnel(f"smoke-funnel-diag-{seeds[0]}", "diag", seeds[0])
    run_funnel(f"smoke-funnel-restart-{seeds[0]}", "restart", seeds[0])
    run_pdb(f"smoke-pdb-earnings-defaults-{seeds[0]}", "earnings-logearn_interaction", "defaults", seeds[0])


# --------------------------------------------------------------------------- analysis

def load(cid: str) -> dict | None:
    p = cell_path(cid)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def trapped_chains(cell: dict, anchor_ls: float, anchor_hl: float) -> list[int]:
    """The frozen census: a chain is trapped when the median of its retained log_sigma is more than
    LS_TOL from the anchor, or the median of its h_last more than HL_TOL from the anchor."""
    T = PROTOCOL["trapped_rule"]
    out = []
    for c, ch in enumerate(cell["chains_data"]):
        if abs(ch["median_log_sigma"] - anchor_ls) > T["log_sigma_tolerance"] or abs(ch["median_h_last"] - anchor_hl) > T["h_last_tolerance"]:
            out.append(c)
    return out


def owalnuts_chain_summaries(cell: dict) -> dict:
    """Bring an sv-owalnuts cell to the common per-chain summary shape."""
    if cell.get("status") != "ok" or "draws_mu_logsigma_hlast" not in cell["chains_data"][0]:
        return cell  # a CmdStan / nutpie cell, or an oWALNUTS cell already stripped by strip_draws.py
    arr = np.asarray([c["draws_mu_logsigma_hlast"] for c in cell["chains_data"]])  # (chains, draws, 3)
    for c, ch in enumerate(cell["chains_data"]):
        ch.update(median_log_sigma=float(np.median(arr[c, :, 1])), median_mu=float(np.median(arr[c, :, 0])),
                  median_h_last=float(np.median(arr[c, :, 2])), sd_log_sigma=float(np.std(arr[c, :, 1])),
                  mean_log_sigma=float(np.mean(arr[c, :, 1])))
        ch["step_at_checkpoints"] = {k: ch["step_at_transition"].get(str(t)) for k, t in CHECKPOINTS.items()}
    return cell


def collapse_window(steps_by_chain: list[dict]) -> list[str | None]:
    """Per chain, the first checkpoint at which its step is below the collapse ratio times the median
    over chains of the step at that checkpoint (None = never)."""
    ratio = PROTOCOL["trapped_rule"]["collapse_ratio"]
    out = []
    for c in range(len(steps_by_chain)):
        first = None
        for k in CHECKPOINTS:
            vals = [s.get(k) for s in steps_by_chain]
            if any(v is None for v in vals):
                continue
            med = statistics.median(vals)
            if vals[c] < ratio * med:
                first = k
                break
        out.append(first)
    return out


def analyze() -> None:
    import scipy.stats as st
    cells = {c["id"]: load(c["id"]) for c in manifest()}
    man = manifest()
    blocks = {b["name"]: b for b in PROTOCOL["blocks"]}
    # anchors from the nutpie arm of part A (the arm that trapped 0/300 in WP84)
    nut = [cells[c["id"]] for c in man if c["block"] == "A" and c["arm"] == "nutpie" and cells[c["id"]] and cells[c["id"]]["status"] == "ok"]
    anchor_ls = float(np.median([ch["median_log_sigma"] for c in nut for ch in c["chains_data"]]))
    anchor_hl = float(np.median([ch["median_h_last"] for c in nut for ch in c["chains_data"]]))
    summary = {"anchor": {"log_sigma": anchor_ls, "h_last": anchor_hl, "nutpie_cells": len(nut)}, "arms": {}, "cells": {}}
    per_arm: dict[str, dict] = {}
    for c in man:
        if c["kind"] != "sv":
            continue
        cell = cells[c["id"]]
        key = f"{c['block']}-{c['arm']}"
        a = per_arm.setdefault(key, {"block": c["block"], "arm": c["arm"], "cells": 0, "ok": 0, "errors": 0, "chains": 0,
                                     "trapped_chains": 0, "trapped_cells": 0, "trapped": [], "walls": [], "flag_agree": 0,
                                     "flagged_chains": 0, "restarted_chains": 0, "collapse_windows": [], "start_ls_trapped": [],
                                     "start_ls_healthy": [], "start_lp_trapped": [], "start_lp_healthy": [], "rhat_fail": 0,
                                     "trapped_final_step": [], "healthy_final_step": [], "bit_identical_to_defaults": 0,
                                     "unflagged_cells": 0, "ok_seeds": []})
        a["cells"] += 1
        if not cell or cell.get("status") != "ok":
            a["errors"] += 1
            continue
        cell = owalnuts_chain_summaries(cell)
        a["ok"] += 1
        a["ok_seeds"].append(c["seed"])
        a["walls"].append(cell["wall_seconds_pinned_cotenanted"])
        tr = trapped_chains(cell, anchor_ls, anchor_hl)
        a["chains"] += len(cell["chains_data"])
        a["trapped_chains"] += len(tr)
        a["trapped_cells"] += bool(tr)
        steps = [ch.get("step_at_checkpoints") or {} for ch in cell["chains_data"]] if c["arm"] not in ("cmdstan", "nutpie") else cell["step_at_checkpoints"]
        cw = collapse_window(steps)
        starts_ls = cell.get("start_log_sigma") or cell.get("first_draw_log_sigma")
        starts_lp = (cell.get("init") or {}).get("start_log_densities") or cell.get("first_draw_log_density")
        finals = cell.get("final_step_size") or [ch["final_step_size"] for ch in cell["chains_data"]]
        rh = cell.get("rhat")
        if rh and max(v["rhat"] for v in rh.values()) > 1.01:
            a["rhat_fail"] += 1
        for ch in range(len(cell["chains_data"])):
            (a["start_ls_trapped"] if ch in tr else a["start_ls_healthy"]).append(starts_ls[ch])
            (a["start_lp_trapped"] if ch in tr else a["start_lp_healthy"]).append(starts_lp[ch])
            (a["trapped_final_step"] if ch in tr else a["healthy_final_step"]).append(finals[ch])
        for ch in tr:
            a["collapse_windows"].append(cw[ch])
            a["trapped"].append({"seed": c["seed"], "chain": ch, "start_log_sigma": starts_ls[ch], "start_log_density": starts_lp[ch],
                                 "median_log_sigma": cell["chains_data"][ch]["median_log_sigma"], "final_step": finals[ch],
                                 "collapse_window": cw[ch], "flagged": ch in (cell.get("chain_warning_chains") or [])})
        flagged = set(cell.get("chain_warning_chains") or [])
        if c["arm"] not in ("cmdstan", "nutpie"):
            a["flagged_chains"] += len(flagged)
            a["flag_agree"] += set(tr) == flagged or (not tr and not flagged)
            checks = [x for ch in cell["chains_data"] for x in ch["trapped_chain_checks"]]
            a["restarted_chains"] += sum(x["restarted"] for x in checks)
            if c["block"] == "C":
                base = cells.get(f"A-defaults-{c['seed']}")
                if base and base.get("status") == "ok":
                    fired = [i for i, ch in enumerate(cell["chains_data"]) if any(x["restarted"] for x in ch["trapped_chain_checks"])]
                    if not fired:
                        a["unflagged_cells"] += 1
                        a["bit_identical_to_defaults"] += cell["draw_hash"] == base["draw_hash"]
                    else:
                        a.setdefault("fired_cells", []).append({"seed": c["seed"], "chains": fired,
                                                                "untouched_identical": all(cell["chains_data"][i]["draw_hash"] == base["chains_data"][i]["draw_hash"]
                                                                                           for i in range(4) if i not in fired),
                                                                "defaults_trapped": trapped_chains(owalnuts_chain_summaries(base), anchor_ls, anchor_hl),
                                                                "candidate_trapped": tr, "checks": checks})
        summary["cells"][c["id"]] = {"trapped": tr, "collapse_window": cw, "flagged": sorted(flagged), "rhat": rh}
    for key, a in per_arm.items():
        a["trapped_chain_rate"] = a["trapped_chains"] / a["chains"] if a["chains"] else None
        a["median_wall"] = statistics.median(a["walls"]) if a["walls"] else None
        a["collapse_window_counts"] = {str(k): a["collapse_windows"].count(k) for k in list(CHECKPOINTS) + [None]}
        a["start_ls_trapped_summary"] = quant(a["start_ls_trapped"])
        a["start_ls_healthy_summary"] = quant(a["start_ls_healthy"])
        a["trapped_final_step_summary"] = quant(a["trapped_final_step"])
        a["healthy_final_step_summary"] = quant(a["healthy_final_step"])
        for k in ("walls", "start_ls_trapped", "start_ls_healthy", "start_lp_trapped", "start_lp_healthy", "collapse_windows",
                  "trapped_final_step", "healthy_final_step"):
            a.pop(k)
    summary["arms"] = per_arm

    # ---- decision rules
    nut_a, def_a = per_arm.get("A-nutpie"), per_arm.get("A-defaults")
    rules = {}
    for cand in [arm for arm in blocks["C"]["arms"]] if "C" in blocks else []:
        ca = per_arm.get(f"C-{cand}")
        if not ca:
            continue
        k, n = ca["trapped_chains"], ca["chains"]
        fisher = st.fisher_exact([[k, n - k], [nut_a["trapped_chains"], nut_a["chains"] - nut_a["trapped_chains"]]])[1] if nut_a and n else None
        r1 = k == 0 or (fisher is not None and fisher >= 0.05 and def_a and k <= def_a["trapped_chains"] / 2)
        r2 = (ca["bit_identical_to_defaults"] == ca["unflagged_cells"]
              and all(f["untouched_identical"] for f in ca.get("fired_cells", [])) and ca["errors"] == 0)
        # funnel
        fd = {s: cells.get(f"F-diag-{s}") for s in blocks["F"]["seeds"]}
        fc = {s: cells.get(f"F-{cand}-{s}") for s in blocks["F"]["seeds"]}
        fired_f = [s for s, c in fc.items() if funnel_ok(c) and funnel_fired(c)]
        ident_f = [s for s, c in fc.items() if funnel_ok(c) and funnel_ok(fd[s]) and c["draws_fnv"] == fd[s]["draws_fnv"]]
        est = [c["tail_mass"]["estimate"] for c in fc.values() if funnel_ok(c)]
        p5 = statistics.fmean(est) if est else None
        se = statistics.stdev(est) / math.sqrt(len(est)) if len(est) > 1 else None
        exact = PROTOCOL["funnel"]["exact_p5"]
        r3 = bool(est) and len(est) == len(fc) and ((not fired_f and len(ident_f) == len(fc)) or (p5 is not None and abs(p5 - exact) <= 2 * se))
        # house models
        pd_d = {(m, s): cells.get(f"P-{m}-defaults-{s}") for m in blocks["P"]["models"] for s in blocks["P"]["seeds"]}
        pd_c = {(m, s): cells.get(f"P-{m}-{cand}-{s}") for m in blocks["P"]["models"] for s in blocks["P"]["seeds"]}
        pass_d = sum(bool(c and c.get("passed")) for c in pd_d.values())
        pass_c = sum(bool(c and c.get("passed")) for c in pd_c.values())
        fired_p = [k for k, c in pd_c.items() if c and c.get("restarted_chains")]
        fired_on_passing = [k for k in fired_p if pd_d[k] and pd_d[k].get("passed")]
        ident_p = sum(1 for k, c in pd_c.items() if c and pd_d[k] and not c.get("restarted_chains") and c.get("draw_hash") == pd_d[k].get("draw_hash"))
        unfired_p = sum(1 for k, c in pd_c.items() if c and c.get("status") == "ok" and not c.get("restarted_chains"))
        r4 = pass_c >= pass_d and not fired_on_passing and ident_p == unfired_p and all(c and c.get("status") == "ok" for c in pd_c.values())
        rules[cand] = {"R1_efficacy": {"holds": bool(r1), "trapped_chains": k, "chains": n, "nutpie_trapped": nut_a["trapped_chains"] if nut_a else None,
                                       "defaults_trapped": def_a["trapped_chains"] if def_a else None, "fisher_p_vs_nutpie": fisher},
                       "R2_fingerprint": {"holds": bool(r2), "unflagged_cells": ca["unflagged_cells"], "bit_identical": ca["bit_identical_to_defaults"],
                                          "fired_cells": len(ca.get("fired_cells", [])), "errors": ca["errors"]},
                       "R3_funnel": {"holds": bool(r3), "cells": len(est), "fired": fired_f, "identical_to_diag": len(ident_f), "p5": p5, "se": se, "exact": exact},
                       "R4_house": {"holds": bool(r4), "passes_candidate": pass_c, "passes_defaults": pass_d, "fired": [list(k) for k in fired_p],
                                    "fired_on_passing": [list(k) for k in fired_on_passing], "identical": ident_p, "unfired": unfired_p},
                       "R5_library": {"holds": None, "note": "cargo test (default and research) and clippy -D warnings; filled by hand from the logs"}}
        rules[cand]["qualifies_for_confirmation"] = all(rules[cand][r]["holds"] for r in ("R1_efficacy", "R2_fingerprint", "R3_funnel", "R4_house"))
    summary["rules"] = rules
    # funnel defaults and house defaults for the table
    summary["funnel"] = {arm: funnel_arm(cells, blocks, arm) for arm in blocks["F"]["arms"]} if "F" in blocks else {}
    summary["house"] = {arm: {m: [bool(cells.get(f"P-{m}-{arm}-{s}") and cells[f"P-{m}-{arm}-{s}"].get("passed")) for s in blocks["P"]["seeds"]]
                             for m in blocks["P"]["models"]} for arm in blocks["P"]["arms"]} if "P" in blocks else {}
    summary["predictions"] = predictions(per_arm)
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, default=float) + "\n", encoding="utf-8")
    (ART / "results-table.md").write_text(results_table(summary), encoding="utf-8")
    log("analysis written")


def quant(xs):
    xs = [x for x in xs if x is not None and np.isfinite(x)]
    if not xs:
        return None
    q = np.quantile(xs, [0, 0.25, 0.5, 0.75, 1]).tolist()
    return {"n": len(xs), "min": q[0], "q25": q[1], "median": q[2], "q75": q[3], "max": q[4]}


def funnel_ok(c) -> bool:
    # funnel.rs (WP85 harness) writes no `status` field: a cell is complete when it carries the
    # tail-mass block and a draws hash (`draws_fnv`, not `draw_hash` as in the SV/house cells).
    # The analysis read `status == "ok"` / `draw_hash` until the post-run fix of 2026-10-26, which
    # reported 0 funnel cells and an R3 of False; the cells themselves were never rerun.
    return bool(c) and c.get("status") != "error" and "tail_mass" in c and "draws_fnv" in c


def funnel_fired(c) -> bool:
    return any(x["restarted"] for ch in c["chains_data"] for x in ch.get("trapped_chain_checks", []))


def funnel_arm(cells, blocks, arm):
    cs = [cells.get(f"F-{arm}-{s}") for s in blocks["F"]["seeds"]]
    cs = [c for c in cs if funnel_ok(c)]
    est = [c["tail_mass"]["estimate"] for c in cs]
    return {"cells": len(cs), "p5": statistics.fmean(est) if est else None,
            "se": statistics.stdev(est) / math.sqrt(len(est)) if len(est) > 1 else None,
            "divergences": sum(ch["divergences"] for c in cs for ch in c["chains_data"]),
            "fired": sum(1 for c in cs if funnel_fired(c))}


def predictions(per_arm: dict) -> dict:
    P = PROTOCOL.get("predictions", {})
    out = {}
    for name, p in P.items():
        a = per_arm.get(p.get("arm", ""))
        if not a or a["chains"] == 0:
            out[name] = {"text": p["text"], "observed": None, "held": None}
            continue
        k = a["trapped_chains"]
        held = p["low"] <= k <= p["high"] if "low" in p else None
        out[name] = {"text": p["text"], "observed_trapped_chains": k, "chains": a["chains"], "held": held}
    return out


def results_table(s: dict) -> str:
    L = ["# WP89 results table (generated by run_study.py analyze)", "",
         f"Anchor (nutpie Part A medians): log_sigma {s['anchor']['log_sigma']:.3f}, h_last {s['anchor']['h_last']:.3f} "
         f"({s['anchor']['nutpie_cells']} cells).", "",
         "## Trapped chains per arm (frozen census: |median log_sigma - anchor| > tol or |median h_last - anchor| > tol)", "",
         "| block-arm | cells ok / errors | chains | trapped chains | trapped cells | rate | flagged by warnings | flags agree | restarted | median wall s | first collapse window of trapped chains | start log_sigma trapped (median) | start log_sigma healthy (median) | final step trapped (median) | final step healthy (median) |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, a in s["arms"].items():
        if not a["ok"]:
            L.append(f"| {key} | 0 / {a['errors']} | | | | | | | | | | | | | |")
            continue
        cw = {k: v for k, v in a["collapse_window_counts"].items() if v}
        f = lambda d: f"{d['median']:.3g}" if d else "-"
        L.append(f"| {key} | {a['ok']} / {a['errors']} | {a['chains']} | {a['trapped_chains']} | {a['trapped_cells']} | "
                 f"{(a['trapped_chain_rate'] or 0):.4f} | {a['flagged_chains']} | {a['flag_agree']} | {a['restarted_chains']} | "
                 f"{a['median_wall']:.2f} | {cw} | {f(a['start_ls_trapped_summary'])} | {f(a['start_ls_healthy_summary'])} | "
                 f"{f(a['trapped_final_step_summary'])} | {f(a['healthy_final_step_summary'])} |")
    L += ["", "## Candidates against the frozen rules", "",
          "| candidate | R1 efficacy | R2 fingerprint | R3 funnel | R4 house models | qualifies |", "|---|---|---|---|---|---|"]
    for cand, r in s["rules"].items():
        L.append(f"| {cand} | {r['R1_efficacy']['holds']} ({r['R1_efficacy']['trapped_chains']}/{r['R1_efficacy']['chains']}, "
                 f"nutpie {r['R1_efficacy']['nutpie_trapped']}, defaults {r['R1_efficacy']['defaults_trapped']}, Fisher p {r['R1_efficacy']['fisher_p_vs_nutpie']}) | "
                 f"{r['R2_fingerprint']['holds']} ({r['R2_fingerprint']['bit_identical']}/{r['R2_fingerprint']['unflagged_cells']} unfired identical, {r['R2_fingerprint']['fired_cells']} fired) | "
                 f"{r['R3_funnel']['holds']} (P5 {r['R3_funnel']['p5']}, se {r['R3_funnel']['se']}, fired {len(r['R3_funnel']['fired'])}, identical {r['R3_funnel']['identical_to_diag']}) | "
                 f"{r['R4_house']['holds']} (passes {r['R4_house']['passes_candidate']} vs {r['R4_house']['passes_defaults']}, fired {r['R4_house']['fired']}, identical {r['R4_house']['identical']}/{r['R4_house']['unfired']}) | "
                 f"{r['qualifies_for_confirmation']} |")
    L += ["", "## Funnel (4 x 2,000/20,000, 30 seeds)", "", "| arm | cells | P5 | s.e. | divergences | fired |", "|---|---|---|---|---|---|"]
    for arm, f in s["funnel"].items():
        L.append(f"| {arm} | {f['cells']} | {f['p5']} | {f['se']} | {f['divergences']} | {f['fired']} |" if f["cells"] else f"| {arm} | 0 | | | | |")
    L += ["", "## House models (v7 gates), passes per seed", ""]
    for arm, d in s["house"].items():
        L.append(f"- {arm}: " + ", ".join(f"{m} {sum(v)}/{len(v)}" for m, v in d.items()))
    L += ["", "## Predictions", ""]
    for name, p in s["predictions"].items():
        L.append(f"- {name}: {p['text']} -> observed {p.get('observed_trapped_chains')} of {p.get('chains')}; held: {p['held']}")
    L += ["", "## Trapped chains (every one)", "", "| block-arm | seed | chain | start log_sigma | start lp | median log_sigma | final step | collapse window | flagged |", "|---|---|---|---|---|---|---|---|---|"]
    for key, a in s["arms"].items():
        for t in a["trapped"]:
            L.append(f"| {key} | {t['seed']} | {t['chain']} | {t['start_log_sigma']:.3f} | {t['start_log_density']:.1f} | {t['median_log_sigma']:.3f} | {t['final_step']:.3g} | {t['collapse_window']} | {t['flagged']} |")
    return "\n".join(L) + "\n"


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
        analyze()
    else:
        raise SystemExit(f"unknown command {cmd}")
