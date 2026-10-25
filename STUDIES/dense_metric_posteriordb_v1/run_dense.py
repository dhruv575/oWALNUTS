#!/usr/bin/env python3
"""WP48 dense-metric posteriordb screen driver (posteriordb_bench_v6 harness, three oWALNUTS metric arms).

    python run_dense.py prepare            # compile BridgeStan libraries, write reference statistics (no sampling)
    python run_dense.py run                # every model / arm / seed in protocol order (resumable)
    python run_dense.py cell <model> <arm> # one model/arm, all seeds (child process)
    python run_dense.py cmdstan            # CmdStan metric=dense_e on the three target models
    python run_dense.py checks             # funnel side check, dense arms
    python run_dense.py overhead           # gradient and kernel cost decomposition (not evidence cells)
    python run_dense.py analyze            # artifacts/summary.json + artifacts/results-table.md

Each cell writes `artifacts/cells/<model>-<arm>-<seed>.json` (metrics, no draws) and
`artifacts/draws/<model>-<arm>-<seed>.npz` (constrained reference-parameter draws and
unconstrained draws; uncommitted). Failures are cells with status != "ok".
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
DRAWS = ART / "draws"
MODELS = HERE / "models"
CMDSTAN_MODELS = MODELS / "cmdstan"
PDB_PATH = HERE / PROTOCOL["posteriordb"]["path"]
CMDSTAN_HOME = Path(PROTOCOL["cmdstan_dense"]["cmdstan_home"])
HARNESS = HERE / "target" / "release" / "dense-cell.exe"
FUNNEL = HERE / "target" / "release" / "funnel.exe"
OVERHEAD = HERE / "target" / "release" / "overhead.exe"
ARMS = list(PROTOCOL["arms"].keys())  # owalnuts-diag, -dense, -dense-seeded, -dense-stan
MODE = {"owalnuts-diag": "diag", "owalnuts-dense": "dense", "owalnuts-dense-seeded": "dense-seeded", "owalnuts-dense-stan": "dense-stan"}
SEEDS = PROTOCOL["seeds"]
TIMEOUT = PROTOCOL["cell_timeout_seconds"]
TARGETS = PROTOCOL["target_models"]
V6 = HERE.parent / "posteriordb_bench_v6" / "artifacts" / "cells"
os.environ.setdefault("MAKE", "mingw32-make")
os.environ.setdefault("RUSTUP_TOOLCHAIN", "1.88.0-x86_64-pc-windows-gnu")


def short(model: str) -> str:
    return model.replace("-", "__")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------- posteriordb


def posterior(model: str):
    from posteriordb import PosteriorDatabase

    return PosteriorDatabase(str(PDB_PATH)).posterior(model)


def bridgestan_name(name: str) -> str:
    parts = name.split(".")
    if len(parts) == 1 or not all(p.isdigit() for p in parts[1:]):
        return name
    return f"{parts[0]}[{','.join(parts[1:])}]"


def reference(model: str) -> dict:
    p = posterior(model)
    ref = p.reference_draws()
    names = list(ref[0].keys())
    arr = np.asarray([[c[n] for n in names] for c in ref], dtype=np.float64)
    arr = np.transpose(arr, (0, 2, 1))
    return {"names": names, "draws": arr, **arviz_stats(arr)}


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


def prepare_bridgestan(model: str) -> tuple[Path, Path]:
    import bridgestan as bs

    p = posterior(model)
    MODELS.mkdir(exist_ok=True)
    stan = MODELS / f"{short(model)}.stan"
    data = MODELS / f"{short(model)}.data.json"
    if not stan.exists():
        shutil.copyfile(p.model.code_file_path("stan"), stan)
    if not data.exists():
        data.write_text(json.dumps(p.data.values()), encoding="utf-8")
    so = stan.with_name(f"{stan.stem}_model.so")
    if not so.exists():
        t = time.perf_counter()
        bs.compile_model(stan, make_args=[])
        log(f"bridgestan compiled {model} in {time.perf_counter() - t:.1f}s")
    return so, data


def stan_model(model: str):
    import bridgestan as bs

    so, data = prepare_bridgestan(model)
    bs.compile.windows_dll_path_setup()
    return bs.StanModel(str(so), data=data.read_text(encoding="utf-8"), seed=1)


# --------------------------------------------------------------------------- metric geometry


def corr_stats(unc: np.ndarray) -> dict:
    """unc: (n, d) unconstrained draws. Max |off-diagonal correlation| and correlation condition number."""
    d = unc.shape[1]
    if d < 2:
        return {"max_abs_corr": 0.0, "corr_condition": 1.0}
    c = np.corrcoef(unc, rowvar=False)
    off = np.abs(c[~np.eye(d, dtype=bool)])
    ev = np.linalg.eigvalsh(c)
    return {"max_abs_corr": float(np.nanmax(off)), "corr_condition": float(ev[-1] / max(ev[0], 1e-300))}


def preconditioned_condition(sigma: np.ndarray, mass: np.ndarray) -> float:
    """Condition number of the posterior covariance in the metric's whitened coordinates.

    mass is the installed momentum covariance M (= target precision): a vector
    (diagonal) or a matrix (dense). Whitened covariance is L^T Sigma L with M = L L^T.
    """
    if mass.ndim == 1:
        s = np.sqrt(mass)
        a = sigma * s[:, None] * s[None, :]
    else:
        lower = np.linalg.cholesky(0.5 * (mass + mass.T))
        a = lower.T @ sigma @ lower
    ev = np.linalg.eigvalsh(0.5 * (a + a.T))
    return float(ev[-1] / max(ev[0], 1e-300))


def metric_condition(mass: np.ndarray) -> float:
    if mass.ndim == 1:
        return float(mass.max() / mass.min())
    ev = np.linalg.eigvalsh(0.5 * (mass + mass.T))
    return float(ev[-1] / max(ev[0], 1e-300))


def shipped_dense_precision(cov: np.ndarray, n: int) -> np.ndarray:
    """The shipped MeanVarianceShrinkage estimator applied to a covariance (prediction tool; no ridge loop)."""
    d = cov.shape[0]
    s = min(max(d / (n + d), 0.05), 0.8)
    out = cov * (1 - s)
    np.fill_diagonal(out, (1 - s) * np.diag(cov) + s * max(np.mean(np.diag(cov)), 1e-12))
    return np.linalg.inv(out)


def stan_dense_precision(cov: np.ndarray, n: int) -> np.ndarray:
    out = (n / (n + 5.0)) * cov + 1e-3 * (5.0 / (n + 5.0)) * np.eye(cov.shape[0])
    return np.linalg.inv(out)


def stan_diag_mass(cov: np.ndarray, n: int) -> np.ndarray:
    return 1.0 / ((n / (n + 5.0)) * np.diag(cov) + 1e-3 * (5.0 / (n + 5.0)))


# --------------------------------------------------------------------------- metrics


def metrics(model, arm, seed, draws, names, ref, wall, grads_total, grads_sampling, divergences,
            max_depth_stops, extra) -> dict:
    st = arviz_stats(draws)
    finite = bool(np.isfinite(draws).all())
    z = (st["mean"] - ref["mean"]) / np.sqrt(st["mcse"] ** 2 + ref["mcse"] ** 2)
    min_bulk = float(np.nanmin(st["bulk_ess"]))
    min_tail = float(np.nanmin(st["tail_ess"]))
    max_rhat = float(np.nanmax(st["rhat"]))
    g = PROTOCOL["gates"]
    gates = {
        "max_rank_rhat": max_rhat <= g["max_rank_rhat"],
        "min_bulk_ess": min_bulk >= g["min_bulk_ess"],
        "min_tail_ess": min_tail >= g["min_tail_ess"],
        "sampling_divergences": divergences == 0,
        "finite_draws": finite,
        "no_sampler_error": True,
    }
    n_draws = draws.shape[0] * draws.shape[1]
    return {
        "schema": "dense-metric-posteriordb-v1-cell-metrics",
        "model": model, "arm": arm, "seed": seed, "status": "ok",
        "dimension_reference_params": len(names),
        "wall_seconds_contended": wall,
        "gradients_total": grads_total,
        "gradients_sampling": grads_sampling,
        "divergences": divergences,
        "max_depth_stops": max_depth_stops,
        "depth_cap_fraction": max_depth_stops / n_draws,
        "min_bulk_ess": min_bulk, "min_tail_ess": min_tail, "max_rank_rhat": max_rhat,
        "argmin_bulk_ess": names[int(np.nanargmin(st["bulk_ess"]))],
        "min_bulk_ess_per_gradient": min_bulk / grads_total,
        "min_tail_ess_per_gradient": min_tail / grads_total,
        "min_bulk_ess_per_second_contended": min_bulk / wall,
        "max_abs_z": float(np.nanmax(np.abs(z))),
        "argmax_abs_z": names[int(np.nanargmax(np.abs(z)))],
        "agreement_flag": bool(np.nanmax(np.abs(z)) > 4),
        "gates": gates,
        "passed": all(gates.values()),
        "parameters": {
            n: {"mean": float(st["mean"][i]), "bulk_ess": float(st["bulk_ess"][i]),
                "tail_ess": float(st["tail_ess"][i]), "rhat": float(st["rhat"][i]), "z": float(z[i])}
            for i, n in enumerate(names)
        },
        **extra,
    }


def failure(model, arm, seed, status, message, **extra) -> dict:
    return {"schema": "dense-metric-posteriordb-v1-cell-metrics", "model": model, "arm": arm, "seed": seed,
            "status": status, "error": message, "passed": False, "gates": {"no_sampler_error": False}, **extra}


def cell_path(model, arm, seed) -> Path:
    return CELLS / f"{short(model)}-{arm}-{seed}.json"


def write_cell(cell: dict) -> None:
    CELLS.mkdir(parents=True, exist_ok=True)
    cell_path(cell["model"], cell["arm"], cell["seed"]).write_text(
        json.dumps(cell, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if cell["status"] == "ok":
        log(f"  {cell['arm']} {cell['seed']}: wall {cell['wall_seconds_contended']:.2f}s grads {cell['gradients_total']} "
            f"minbulk {cell['min_bulk_ess']:.0f} mintail {cell['min_tail_ess']:.0f} rhat {cell['max_rank_rhat']:.4f} "
            f"div {cell['divergences']} caps {cell['max_depth_stops']} max|z| {cell['max_abs_z']:.2f} passed {cell['passed']}")
    else:
        log(f"  {cell['arm']} {cell['seed']}: {cell['status']}: {cell.get('error', '')[:300]}")


def run_owalnuts(model: str, arm: str, seed: int, ref: dict) -> dict:
    so, data = prepare_bridgestan(model)
    raw = DRAWS / f"{short(model)}-{arm}-{seed}.raw.json"
    DRAWS.mkdir(parents=True, exist_ok=True)
    if raw.exists():
        raw.unlink()
    cmd = [str(HARNESS), str(so), str(data), MODE[arm], str(seed), str(raw), "4"]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return failure(model, arm, seed, "timeout", f"exceeded {TIMEOUT}s")
    if cp.returncode != 0 or not raw.exists():
        return failure(model, arm, seed, "error", cp.stderr.strip()[-2000:])
    out = json.loads(raw.read_text(encoding="utf-8"))
    if out.get("status") != "ok":
        return failure(model, arm, seed, "error", out.get("error", "unknown"), wall_seconds_contended=out.get("wall_seconds"))
    sm = stan_model(model)
    cnames = [bridgestan_name(n) for n in sm.param_names(include_tp=True, include_gq=False)]
    unc = np.asarray([c["samples"] for c in out["chains_data"]], dtype=np.float64)  # (chains, draws, d)
    con = np.empty(unc.shape[:2] + (len(cnames),))
    for c in range(unc.shape[0]):
        for d in range(unc.shape[1]):
            con[c, d] = sm.param_constrain(unc[c, d], include_tp=True, include_gq=False)
    index = {n: i for i, n in enumerate(cnames)}
    missing = [n for n in ref["names"] if n not in index]
    if missing:
        return failure(model, arm, seed, "error", f"reference parameters not produced: {missing[:5]}")
    draws = con[:, :, [index[n] for n in ref["names"]]]
    chains = out["chains_data"]
    dim = out["dimension"]
    pooled = unc.reshape(-1, dim)
    sigma = np.cov(pooled, rowvar=False).reshape(dim, dim)
    # Installed metric per chain: diagonal mass, or the last installed dense precision.
    installed = []
    for c in chains:
        if MODE[arm] == "diag":
            installed.append(np.asarray(c["mass_diagonal"], dtype=float))
        elif c.get("final_mass_dense") is not None:
            installed.append(np.asarray(c["final_mass_dense"], dtype=float).reshape(dim, dim))
        else:
            installed.append(np.eye(dim))  # no dense window installed: identity
    kappa_pre = [preconditioned_condition(sigma, m) for m in installed]
    kappa_metric = [metric_condition(m) for m in installed]
    # Predictor (diag arm only, but computed for every arm): first 500 retained draws per chain, pooled.
    window = unc[:, :500, :].reshape(-1, dim)
    extra = {
        "unconstrained_dimension": dim,
        "final_step_size": [c["final_step_size"] for c in chains],
        "per_chain_target_calls": [c["total_target_calls"] for c in chains],
        "per_chain_depth_caps": [c["maximum_depth_stops"] for c in chains],
        "invalid_stops": sum(c["invalid_stops"] for c in chains),
        "refinement_exhaustions": sum(c["refinement_exhaustions"] for c in chains),
        "frozen_chains": sum(1 for c in chains if c["refinement_exhaustions"] > out["retained"] // 2),
        "warmup_divergences": sum(c["warmup_divergences"] for c in chains),
        "retained_depth_histogram": [sum(x) for x in zip(*(c["retained_depth_histogram"] for c in chains))],
        "start_search_calls": out["init"]["start_search_calls"],
        "warmup_config": out["warmup_config"],
        "tuning": out["tuning"],
        "algorithm_revision": out["algorithm_revision"],
        "metric_updates": [c["metric_updates"] for c in chains],
        "dense_installed_windows": [sum(1 for u in c["metric_updates"] if u["outcome"] == "Installed") for c in chains],
        "preconditioned_condition_per_chain": kappa_pre,
        "preconditioned_condition_median": float(np.median(kappa_pre)),
        "installed_metric_condition_per_chain": kappa_metric,
        "installed_metric_condition_median": float(np.median(kappa_metric)),
        "posterior_unconstrained_corr": corr_stats(pooled),
        "predictor_window_corr": corr_stats(window),
        "per_chain_bulk_ess_min": [float(np.nanmin(arviz_stats(draws[i:i + 1])["bulk_ess"])) for i in range(draws.shape[0])],
    }
    cell = metrics(model, arm, seed, draws, ref["names"], ref, out["wall_seconds"], out["target_calls_total"],
                   sum(c["retained_target_calls"] for c in chains), sum(c["divergences"] for c in chains),
                   sum(c["maximum_depth_stops"] for c in chains), extra)
    np.savez_compressed(DRAWS / f"{short(model)}-{arm}-{seed}.npz", draws=draws, names=np.asarray(ref["names"]),
                        unconstrained=unc, installed=np.asarray(installed, dtype=float))
    raw.unlink()
    return cell


def run_model_arm(model: str, arm: str) -> None:
    ref = reference(model)
    for seed in SEEDS:
        if cell_path(model, arm, seed).exists():
            continue
        try:
            cell = run_owalnuts(model, arm, seed, ref)
        except Exception as e:  # noqa: BLE001
            cell = failure(model, arm, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
        write_cell(cell)


def machine_note() -> None:
    ART.mkdir(exist_ok=True)
    machine = ART / "measured_on.json"
    if not machine.exists():
        machine.write_text(json.dumps({
            "platform": platform.platform(), "processor": platform.processor(),
            "cpu_count": os.cpu_count(), "python": sys.version.split()[0],
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "note": "shared 16-core machine; about ten agents ran concurrently; every wall is contended and an upper bound",
        }, indent=2) + "\n", encoding="utf-8")


def run_all(models: list[str], arms: list[str]) -> None:
    machine_note()
    for model in models:
        log(f"== {model}")
        try:
            prepare_bridgestan(model)
        except Exception as e:  # noqa: BLE001
            for arm in arms:
                for seed in SEEDS:
                    if not cell_path(model, arm, seed).exists():
                        write_cell(failure(model, arm, seed, "compile_error", str(e)[-2000:]))
            continue
        for arm in arms:
            if all(cell_path(model, arm, s).exists() for s in SEEDS):
                continue
            cmd = [sys.executable, str(Path(__file__)), "cell", model, arm]
            try:
                cp = subprocess.run(cmd, timeout=TIMEOUT * len(SEEDS) + 600, text=True)
                if cp.returncode != 0:
                    log(f"child for {model}/{arm} exited {cp.returncode}")
            except subprocess.TimeoutExpired:
                log(f"child for {model}/{arm} timed out")
            for seed in SEEDS:
                if not cell_path(model, arm, seed).exists():
                    write_cell(failure(model, arm, seed, "timeout_or_crash", "child process ended without writing the cell"))


# --------------------------------------------------------------------------- CmdStan dense_e reference


def run_cmdstan_dense() -> None:
    import cmdstanpy

    machine_note()
    cmdstanpy.set_cmdstan_path(str(CMDSTAN_HOME))
    CMDSTAN_MODELS.mkdir(parents=True, exist_ok=True)
    arm = "cmdstan-dense"
    for model in TARGETS:
        ref = reference(model)
        stan = CMDSTAN_MODELS / f"{short(model)}.stan"
        if not stan.exists():
            shutil.copyfile(posterior(model).model.code_file_path("stan"), stan)
        m = cmdstanpy.CmdStanModel(stan_file=str(stan))
        sm = stan_model(model)
        for seed in SEEDS:
            if cell_path(model, arm, seed).exists():
                continue
            try:
                cell = cmdstan_cell(model, seed, ref, m, sm)
            except Exception as e:  # noqa: BLE001
                cell = failure(model, arm, seed, "error", f"{e}\n{traceback.format_exc()[-1500:]}")
            write_cell(cell)


def cmdstan_cell(model, seed, ref, m, sm) -> dict:
    p = posterior(model)
    outdir = ART / "cmdstan-output" / f"{short(model)}-{seed}"
    if outdir.exists():
        shutil.rmtree(outdir)
    outdir.mkdir(parents=True)
    t = time.perf_counter()
    fit = m.sample(data=p.data.values(), chains=4, parallel_chains=4, seed=seed, iter_warmup=1000,
                   iter_sampling=1000, metric="dense_e", save_warmup=True, show_progress=False,
                   show_console=False, output_dir=str(outdir))
    wall = time.perf_counter() - t
    cols = list(fit.column_names)
    all_draws = np.asarray(fit.draws(inc_warmup=True))
    col = {n: i for i, n in enumerate(cols)}
    n_warm = all_draws.shape[0] - 1000
    leap = all_draws[:, :, col["n_leapfrog__"]]
    div = int(all_draws[n_warm:, :, col["divergent__"]].sum())
    depth = int((all_draws[n_warm:, :, col["treedepth__"]] >= 10).sum())
    draws = np.transpose(all_draws[n_warm:, :, [col[n] for n in ref["names"]]], (1, 0, 2))
    # Unconstrain the parameter block through BridgeStan to measure the whitened condition number.
    pnames = [bridgestan_name(n) for n in sm.param_names(include_tp=False, include_gq=False)]
    pidx = [col[n] for n in pnames]
    unc = np.asarray([[sm.param_unconstrain(all_draws[n_warm + i, c, pidx]) for i in range(1000)]
                      for c in range(all_draws.shape[1])])
    dim = unc.shape[-1]
    sigma = np.cov(unc.reshape(-1, dim), rowvar=False).reshape(dim, dim)
    inv_metrics = np.asarray(fit.metric)  # (chains, d, d) inverse metric = covariance
    masses = [np.linalg.inv(im) for im in inv_metrics]
    kappa_pre = [preconditioned_condition(sigma, mm) for mm in masses]
    extra = {
        "unconstrained_dimension": dim,
        "step_size": [float(x) for x in np.asarray(fit.step_size).ravel()],
        "per_chain_target_calls": [int(x) for x in leap.sum(axis=0)],
        "preconditioned_condition_per_chain": kappa_pre,
        "preconditioned_condition_median": float(np.median(kappa_pre)),
        "installed_metric_condition_median": float(np.median([metric_condition(mm) for mm in masses])),
        "posterior_unconstrained_corr": corr_stats(unc.reshape(-1, dim)),
        "settings": "CmdStan 2.39.0 defaults except metric=dense_e: adapt_delta 0.8, max_treedepth 10, uniform(-2,2) init",
    }
    cell = metrics(model, "cmdstan-dense", seed, draws, ref["names"], ref, wall, int(leap.sum()),
                   int(leap[n_warm:].sum()), div, depth, extra)
    np.savez_compressed(DRAWS / f"{short(model)}-cmdstan-dense-{seed}.npz", draws=draws, unconstrained=unc)
    return cell


# --------------------------------------------------------------------------- side checks


def run_checks() -> None:
    fdir = ART / "funnel"
    fdir.mkdir(parents=True, exist_ok=True)
    for arm in PROTOCOL["funnel"]["arms"]:
        for seed in PROTOCOL["funnel"]["seeds"]:
            out = fdir / f"{arm}-{seed}.json"
            if out.exists():
                continue
            log(f"funnel {arm} {seed}")
            cp = subprocess.run([str(FUNNEL), arm, str(seed), str(out)], capture_output=True, text=True)
            log(f"  {cp.stderr.strip()[-300:]}")


def run_overhead() -> None:
    odir = ART / "overhead"
    odir.mkdir(parents=True, exist_ok=True)
    dims = set()
    for model in PROTOCOL["models"]:
        so, data = prepare_bridgestan(model)
        out = odir / f"grad-{short(model)}.json"
        npz = DRAWS / f"{short(model)}-owalnuts-diag-{SEEDS[0]}.npz"
        sm = stan_model(model)
        dims.add(sm.param_unc_num())
        if out.exists() or not npz.exists():
            continue
        unc = np.load(npz, allow_pickle=True)["unconstrained"]
        pts = unc[:, ::40, :].reshape(-1, unc.shape[-1])[:100]
        pfile = odir / f"points-{short(model)}.json"
        pfile.write_text(json.dumps(pts.tolist()), encoding="utf-8")
        cp = subprocess.run([str(OVERHEAD), "grad", str(so), str(data), str(pfile), str(out)], capture_output=True, text=True)
        log(f"grad {model}: {cp.stderr.strip()[-200:]}")
        pfile.unlink()
    for d in sorted(dims):
        out = odir / f"kernel-d{d}.json"
        if out.exists():
            continue
        cp = subprocess.run([str(OVERHEAD), "kernel", str(d), str(out)], capture_output=True, text=True)
        log(f"kernel d={d}: {cp.stderr.strip()[-300:]}")


# --------------------------------------------------------------------------- prepare (reference geometry; no sampling)


def prepare() -> None:
    """Compile every model and compute reference-posterior geometry used for the frozen predictions."""
    rows = {}
    for model in PROTOCOL["models"]:
        sm = stan_model(model)
        p = posterior(model)
        ref = p.reference_draws()
        pnames = [bridgestan_name(n) for n in sm.param_names(include_tp=False, include_gq=False)]
        names = list(ref[0].keys())
        missing = [n for n in pnames if n not in names]
        row = {"unconstrained_dimension": sm.param_unc_num(), "parameters": len(pnames)}
        if missing:
            row["error"] = f"reference lacks parameter-block columns {missing[:5]}"
            rows[model] = row
            continue
        idx = [names.index(n) for n in pnames]
        unc = []
        for chain in ref:
            arr = np.asarray([chain[n] for n in names], dtype=float).T
            unc.extend(sm.param_unconstrain(arr[i, idx]) for i in range(arr.shape[0]))
        unc = np.asarray(unc)
        d = unc.shape[1]
        cov = np.cov(unc, rowvar=False).reshape(d, d)
        var = np.diag(cov)
        n = 500  # the last slow window of the 1,000-transition schedule
        row.update(corr_stats(unc))
        row.update({
            "variance_ratio_max_over_min": float(var.max() / var.min()),
            "min_variance_over_mean_variance": float(var.min() / var.mean()),
            "kappa_identity": metric_condition(cov),
            "kappa_stan_diag_oracle": preconditioned_condition(cov, stan_diag_mass(cov, n)),
            "kappa_shipped_dense_oracle": preconditioned_condition(cov, shipped_dense_precision(cov, n)),
            "kappa_stan_dense_oracle": preconditioned_condition(cov, stan_dense_precision(cov, n)),
            "reference_draws": int(unc.shape[0]),
        })
        rows[model] = row
        log(f"{model}: d={d} max|corr|={row['max_abs_corr']:.3f} kdiag={row['kappa_stan_diag_oracle']:.1f} "
            f"kdense={row['kappa_shipped_dense_oracle']:.1f} kstan={row['kappa_stan_dense_oracle']:.1f}")
    ART.mkdir(exist_ok=True)
    (ART / "reference-geometry.json").write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- analysis


def geomean(xs):
    xs = [x for x in xs if x and math.isfinite(x) and x > 0]
    return float(math.exp(sum(math.log(x) for x in xs) / len(xs))) if xs else float("nan")


def med(xs):
    xs = [x for x in xs if x is not None and math.isfinite(x)]
    return statistics.median(xs) if xs else None


def analyze() -> None:
    models = PROTOCOL["models"]
    cells = {}
    for path in sorted(CELLS.glob("*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        c.pop("parameters", None)
        c.pop("metric_updates", None)
        cells.setdefault(c["model"], {}).setdefault(c["arm"], {})[str(c["seed"])] = c
    # quiet-machine cost model
    odir = ART / "overhead"
    grad_cost = {}
    kernel_cost = {}
    for model in models:
        f = odir / f"grad-{short(model)}.json"
        if f.exists():
            grad_cost[model] = json.loads(f.read_text())["seconds_per_gradient_min_of_7"]
    for f in odir.glob("kernel-d*.json"):
        k = json.loads(f.read_text())
        kernel_cost[k["dimension"]] = {a: v["kernel_overhead_per_gradient"] for a, v in k["arms"].items()}

    def quiet_wall(c):
        model, arm = c["model"], c["arm"]
        d = c.get("unconstrained_dimension")
        if model not in grad_cost or d not in kernel_cost or arm not in MODE:
            return None
        per = grad_cost[model] + max(kernel_cost[d][MODE[arm]], 0.0)
        return max(c["per_chain_target_calls"]) * per

    all_arms = ARMS + ["cmdstan-dense"]
    per_model = {}
    for model in models:
        row = {}
        for arm in all_arms:
            seeds = cells.get(model, {}).get(arm, {})
            if not seeds:
                continue
            ok = [c for c in seeds.values() if c.get("status") == "ok"]
            for c in ok:
                qw = quiet_wall(c)
                c["quiet_wall_estimate_seconds"] = qw
                c["min_bulk_ess_per_second_quiet_estimate"] = (c["min_bulk_ess"] / qw) if qw else None
            e = {"n_cells": len(seeds), "n_ok": len(ok), "n_passed": sum(1 for c in ok if c["passed"]),
                 "statuses": {s: c.get("status") for s, c in seeds.items()},
                 "errors": {s: c.get("error", "")[:300] for s, c in seeds.items() if c.get("status") != "ok"},
                 "failed_gates": {s: [k for k, v in c["gates"].items() if not v] for s, c in seeds.items() if c.get("status") == "ok"},
                 "final_step_size": [c.get("final_step_size") or c.get("step_size") for c in ok]}
            for k in ["min_bulk_ess_per_gradient", "min_tail_ess_per_gradient", "min_bulk_ess", "min_tail_ess",
                      "max_rank_rhat", "max_abs_z", "gradients_total", "wall_seconds_contended", "depth_cap_fraction",
                      "divergences", "preconditioned_condition_median", "installed_metric_condition_median",
                      "min_bulk_ess_per_second_contended", "min_bulk_ess_per_second_quiet_estimate",
                      "quiet_wall_estimate_seconds"]:
                vals = [c.get(k) for c in ok]
                vals = [v for v in vals if v is not None and math.isfinite(v)]
                e[k] = {"median": med(vals), "values": vals}
            e["step_median"] = med([x for c in ok for x in (c.get("final_step_size") or c.get("step_size") or [])])
            e["predictor_window_max_abs_corr"] = med([c["predictor_window_corr"]["max_abs_corr"] for c in ok if "predictor_window_corr" in c])
            e["predictor_window_corr_condition"] = med([c["predictor_window_corr"]["corr_condition"] for c in ok if "predictor_window_corr" in c])
            e["predictor_window_max_abs_corr_per_seed"] = {s: c["predictor_window_corr"]["max_abs_corr"] for s, c in seeds.items() if c.get("status") == "ok" and "predictor_window_corr" in c}
            e["unconstrained_dimension"] = next((c.get("unconstrained_dimension") for c in ok), None)
            row[arm] = e
        per_model[model] = row

    def ratio(model, arm, base="owalnuts-diag", key="min_bulk_ess_per_gradient"):
        a = per_model[model].get(arm, {}).get(key, {}).get("median")
        b = per_model[model].get(base, {}).get(key, {}).get("median")
        return (a / b) if (a and b) else None

    comparisons = {}
    for arm in ("owalnuts-dense", "owalnuts-dense-seeded", "owalnuts-dense-stan"):
        rows = {}
        for model in models:
            if arm not in per_model[model] or "owalnuts-diag" not in per_model[model]:
                continue
            r = ratio(model, arm)
            gd = per_model[model][arm]["n_passed"]
            gb = per_model[model]["owalnuts-diag"]["n_passed"]
            cls = ("winner" if (r is not None and r >= 1.5 and gd >= gb) else
                   "loser" if (r is None or r < 1.0 or gd < gb) else "neutral")
            rows[model] = {"ratio_bulk_ess_per_gradient": r,
                           "ratio_bulk_ess_per_second_contended": ratio(model, arm, key="min_bulk_ess_per_second_contended"),
                           "ratio_bulk_ess_per_second_quiet_estimate": ratio(model, arm, key="min_bulk_ess_per_second_quiet_estimate"),
                           "gates": gd, "gates_diag": gb, "class": cls}
        complete = [m for m in rows if rows[m]["ratio_bulk_ess_per_gradient"]]
        target_rows = {m: rows.get(m) for m in TARGETS}
        advised = [m for m in TARGETS if rows.get(m) and rows[m]["class"] == "winner"]
        # auto rule
        D, cstar = PROTOCOL["auto_rule"]["D_star"], PROTOCOL["auto_rule"]["c_star"]
        selected = []
        for m in models:
            e = per_model[m].get("owalnuts-diag", {})
            dd, cc = e.get("unconstrained_dimension"), e.get("predictor_window_max_abs_corr")
            if dd is not None and cc is not None and dd <= D and cc >= cstar:
                selected.append(m)
        winners = [m for m in rows if rows[m]["class"] == "winner"]
        losers = [m for m in rows if rows[m]["class"] == "loser"]
        false_pos = [m for m in selected if m in losers]
        missed = [m for m in winners if m not in selected]
        comparisons[arm] = {
            "per_model": rows,
            "geomean_ratio_bulk_ess_per_gradient_all": geomean([rows[m]["ratio_bulk_ess_per_gradient"] for m in complete]),
            "geomean_ratio_bulk_ess_per_gradient_non_targets": geomean([rows[m]["ratio_bulk_ess_per_gradient"] for m in complete if m not in TARGETS]),
            "geomean_ratio_quiet_ess_per_second_all": geomean([rows[m]["ratio_bulk_ess_per_second_quiet_estimate"] for m in complete]),
            "gates_total": sum(rows[m]["gates"] for m in rows),
            "gates_total_diag": sum(rows[m]["gates_diag"] for m in rows),
            "targets": target_rows,
            "advised_targets": advised,
            "decision_document_dense": {"advised_models": advised,
                                        "verdict": ("supported" if len(advised) == 3 else "mixed" if advised else "not supported")},
            "auto_rule": {"D_star": D, "c_star": cstar, "selected": selected, "winners": winners, "losers": losers,
                          "false_positives": false_pos, "missed_winners": missed,
                          "recommend_auto": bool(winners and not false_pos and not missed)},
        }
    # funnel
    funnel = {}
    for f in sorted((ART / "funnel").glob("*.json")) if (ART / "funnel").exists() else []:
        c = json.loads(f.read_text())
        t = c["tail_mass"]
        funnel[f.stem] = {"estimate": t["estimate"], "z": t["z"], "z_batch_means": t["z_batch_means"],
                          "omega_bulk_ess": c["omega"]["bulk_ess"], "omega_rhat": c["omega"]["rhat"],
                          "target_calls_total": c["target_calls_total"],
                          "divergences": sum(ch["divergences"] for ch in c["chains_data"]),
                          "final_step_size": [ch["final_step_size"] for ch in c["chains_data"]]}
    # v6 CmdStan diag_e reference for the three target models
    v6 = {}
    for model in TARGETS:
        vals = []
        for seed in (90101, 90102, 90103):
            f = V6 / f"{short(model)}-cmdstan-{seed}.json"
            if f.exists():
                c = json.loads(f.read_text())
                vals.append(c)
        v6[model] = {"n_passed": sum(1 for c in vals if c.get("passed")),
                     "min_bulk_ess_per_gradient_median": med([c.get("min_bulk_ess_per_gradient") for c in vals]),
                     "max_depth_stops": [c.get("max_depth_stops") for c in vals],
                     "divergences": [c.get("divergences") for c in vals],
                     "step_size_median": med([x for c in vals for x in c.get("step_size", [])])}
    summary = {
        "schema": "dense-metric-posteriordb-v1-summary",
        "protocol_sha256": __import__("hashlib").sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "per_model": per_model, "comparisons": comparisons, "funnel": funnel,
        "cmdstan_diag_e_v6_reference": v6, "grad_cost_seconds": grad_cost,
        "kernel_overhead_seconds_per_gradient": {str(k): v for k, v in sorted(kernel_cost.items())},
        "cells": cells,
    }
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")

    def f(x, fmt):
        return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)

    L = ["# WP48 dense metric on posteriordb — results", "",
         "Seed medians over 3 seeds. `gates` = cells passing rank R-hat <= 1.01, bulk/tail ESS >= 400, zero retained "
         "divergences. `kappa` = condition number of the pooled retained unconstrained posterior covariance in the installed "
         "metric's whitened coordinates (median over chains). Walls are CONTENDED (about ten agents on 16 cores); "
         "`quiet ESS/s` uses the separately measured gradient and kernel costs.", "",
         "| model | d | arm | gates | grads | min bulk ESS | bulk ESS/grad x1e3 | ratio vs diag | step | cap frac | kappa | max R-hat | div | max abs z | wall s (contended) | quiet ESS/s |",
         "|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|"]
    for model in models:
        for arm in all_arms:
            e = per_model[model].get(arm)
            if not e:
                continue
            status = f"{e['n_passed']}/{e['n_cells']}" if e["n_ok"] else "/".join(sorted(set(e["statuses"].values())))
            r = ratio(model, arm) if arm != "owalnuts-diag" else 1.0
            L.append(f"| {model} | {e['unconstrained_dimension']} | {arm} | {status} | {f(e['gradients_total']['median'], ',.0f')} | "
                     f"{f(e['min_bulk_ess']['median'], ',.0f')} | {f((e['min_bulk_ess_per_gradient']['median'] or float('nan')) * 1e3, '.3f')} | "
                     f"{f(r, '.2f')} | {f(e['step_median'], '.3g')} | {f(e['depth_cap_fraction']['median'], '.3f')} | "
                     f"{f(e['preconditioned_condition_median']['median'], '.3g')} | {f(e['max_rank_rhat']['median'], '.4f')} | "
                     f"{','.join(str(int(x)) for x in e['divergences']['values'])} | {f(e['max_abs_z']['median'], '.2f')} | "
                     f"{f(e['wall_seconds_contended']['median'], '.2f')} | {f(e['min_bulk_ess_per_second_quiet_estimate']['median'], ',.1f')} |")
    for arm, comp in comparisons.items():
        L += ["", f"## {arm} versus owalnuts-diag", "",
              f"- geomean ESS/grad ratio, all complete models: {f(comp['geomean_ratio_bulk_ess_per_gradient_all'], '.3f')}; "
              f"non-target models: {f(comp['geomean_ratio_bulk_ess_per_gradient_non_targets'], '.3f')}; quiet ESS/s: {f(comp['geomean_ratio_quiet_ess_per_second_all'], '.3f')}",
              f"- gates {comp['gates_total']} versus diag {comp['gates_total_diag']}",
              f"- documentation decision: advised on {comp['advised_targets'] or 'none'} -> {comp['decision_document_dense']['verdict']}",
              f"- auto rule d <= {comp['auto_rule']['D_star']} and max|corr| >= {comp['auto_rule']['c_star']}: selected {comp['auto_rule']['selected']}; "
              f"winners {comp['auto_rule']['winners']}; losers {comp['auto_rule']['losers']}; false positives {comp['auto_rule']['false_positives']}; "
              f"missed {comp['auto_rule']['missed_winners']}; recommend auto: {comp['auto_rule']['recommend_auto']}", "",
              "| model | ESS/grad ratio | contended ESS/s ratio | quiet ESS/s ratio | gates | diag gates | class |", "|---|---:|---:|---:|---|---|---|"]
        for m, r in comp["per_model"].items():
            L.append(f"| {m} | {f(r['ratio_bulk_ess_per_gradient'], '.2f')} | {f(r['ratio_bulk_ess_per_second_contended'], '.2f')} | "
                     f"{f(r['ratio_bulk_ess_per_second_quiet_estimate'], '.2f')} | {r['gates']}/3 | {r['gates_diag']}/3 | {r['class']} |")
    L += ["", "## Predictor statistics (owalnuts-diag, first 500 retained draws per chain pooled; seed median)", "",
          "| model | d | max abs corr | corr condition |", "|---|---:|---:|---:|"]
    for m in models:
        e = per_model[m].get("owalnuts-diag", {})
        L.append(f"| {m} | {e.get('unconstrained_dimension')} | {f(e.get('predictor_window_max_abs_corr'), '.3f')} | {f(e.get('predictor_window_corr_condition'), '.3g')} |")
    L += ["", "## CmdStan diag_e reference (posteriordb_bench_v6 cells, seeds 90101-90103)", "",
          "| model | gates | bulk ESS/grad x1e3 | step | depth caps | divergences |", "|---|---|---:|---:|---|---|"]
    for m, v in v6.items():
        L.append(f"| {m} | {v['n_passed']}/3 | {f((v['min_bulk_ess_per_gradient_median'] or float('nan')) * 1e3, '.3f')} | {f(v['step_size_median'], '.3g')} | {v['max_depth_stops']} | {v['divergences']} |")
    L += ["", "## Funnel side check (P(omega < -5), exact 0.0478; gate |z| <= 2 per seed)", "",
          "| cell | estimate | MCSE z | batch-means z | omega bulk ESS | omega R-hat | divergences | final steps |", "|---|---:|---:|---:|---:|---:|---:|---|"]
    for k, v in funnel.items():
        L.append(f"| {k} | {v['estimate']:.4f} | {v['z']:+.2f} | {v['z_batch_means']:+.2f} | {v['omega_bulk_ess']:.0f} | {v['omega_rhat']:.4f} | {v['divergences']} | {', '.join(f'{x:.3g}' for x in v['final_step_size'])} |")
    L += ["", "## Cost decomposition (contended micro-benchmarks, minima over repetitions)", "",
          "| d | diag kernel us/grad | dense kernel us/grad | dense-seeded kernel us/grad | dense-stan kernel us/grad |", "|---:|---:|---:|---:|---:|"]
    for d, k in sorted(kernel_cost.items()):
        L.append(f"| {d} | {k['diag'] * 1e6:.3f} | {k['dense'] * 1e6:.3f} | {k['dense-seeded'] * 1e6:.3f} | {k['dense-stan'] * 1e6:.3f} |")
    L += ["", "| model | gradient us |", "|---|---:|"]
    for m, g in grad_cost.items():
        L.append(f"| {m} | {g * 1e6:.2f} |")
    (ART / "results-table.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] == "run":
        models, arms = PROTOCOL["models"], ARMS
        for a in args[1:]:
            if a.startswith("--models="):
                models = a.split("=", 1)[1].split(",")
            elif a.startswith("--arms="):
                arms = a.split("=", 1)[1].split(",")
        run_all(models, arms)
    elif args[0] == "cell":
        run_model_arm(args[1], args[2])
    elif args[0] == "prepare":
        prepare()
    elif args[0] == "cmdstan":
        run_cmdstan_dense()
    elif args[0] == "checks":
        run_checks()
    elif args[0] == "overhead":
        run_overhead()
    elif args[0] == "analyze":
        analyze()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
