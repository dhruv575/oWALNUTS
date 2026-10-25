#!/usr/bin/env python3
"""nutpie_per_gradient_gap_v1 driver (WP58; see PREREGISTRATION.md).

    python run_gap.py run                     # every cell, frozen order, skips cells already written
    python run_gap.py cell <model> <arm> <seed>   # one Python cell (child process)
    python run_gap.py smoke                   # setup checks only (no evidence; seed 1)

Python cells run in their own child process under the study venv (threads=1,
nutpie cores=1). Rust cells run the `gap-harness` binary (threads=4) and are
post-processed here. Every cell writes ``artifacts/cells/<model>-<arm>-<seed>.json``
(metrics) and ``artifacts/draws/...`` (raw draws, not committed). Failures are
cells with ``status != "ok"``; nothing is rerun.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
ART = Path(os.environ.get("GAP_ART", str(HERE / "artifacts")))
CELLS = ART / "cells"
DRAWS = ART / "draws"
MASS = ART / "nutpie-mass"
MODELS = HERE / "models"
HARNESS = HERE / "rust" / "target" / "release" / "gap-harness.exe"
CH, WU, DR = 4, 1000, 1000
PYMC_MODELS = PROTOCOL["pymc_models"]
STAN_MODELS = PROTOCOL["stan_models"]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=float), encoding="utf-8")


# --------------------------------------------------------------------------- densities


class Counter:
    """Counts every call of the wrapped log-density-and-gradient callable."""

    def __init__(self, fn):
        self.fn = fn
        self.n = 0

    def __call__(self, q):
        self.n += 1
        return self.fn(q)


def stan_model(model: str):
    import bridgestan as bs

    bs.compile.windows_dll_path_setup()
    so = MODELS / f"{model}_model.so"
    data = (MODELS / f"{model}.data.json").read_text(encoding="utf-8")
    return bs.StanModel(str(so), data=data, seed=1)


def density(model: str):
    """(callable q -> (logp, grad), dim) on the unconstrained space."""
    if model in PYMC_MODELS:
        import owalnuts
        import callpath_targets as T

        tgt, dim, _q0, _names, _unravel = owalnuts.from_pymc(T.pymc_model(model))
        return tgt, dim
    sm = stan_model(STAN_MODELS[model])
    dim = sm.param_unc_num()
    zero = np.zeros(dim)

    def f(q):
        try:
            lp, g = sm.log_density_gradient(np.ascontiguousarray(q, dtype=np.float64), propto=False, jacobian=True)
        except RuntimeError:
            # A Stan exception is a zero-density point, as in the Rust BridgeStan target.
            return -np.inf, zero
        return float(lp), np.asarray(g, dtype=np.float64)
    return f, dim


def functionals(model: str, s: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """Every unconstrained coordinate plus the eight theta_j for both Eight
    Schools parametrisations (rank-based ESS/R-hat are invariant to the
    coordinate-wise monotone constraining transforms of these models)."""
    import callpath_targets as T

    if model in PYMC_MODELS:
        return T.functionals(model, s)
    dim = s.shape[-1]
    names = [f"q{i}" for i in range(dim)]
    if model == "eight_nc":  # theta_trans[8], mu, log tau
        theta = s[..., 8:9] + np.exp(s[..., 9:10]) * s[..., :8]
        s = np.concatenate([s, theta], -1)
        names += [f"theta_{i + 1}" for i in range(8)]
    return np.ascontiguousarray(s), names


def summarize(model: str, samples: np.ndarray, divergences: int) -> dict:
    import owalnuts

    f, names = functionals(model, samples)
    rows = owalnuts.summary(f, names)
    bulk = {r["name"]: r["ess_bulk"] for r in rows}
    tail = {r["name"]: r["ess_tail"] for r in rows}
    rhat = {r["name"]: r["rhat"] for r in rows}
    g = PROTOCOL["gates"]
    out = {
        "min_bulk_ess": float(min(bulk.values())), "argmin_bulk": min(bulk, key=bulk.get),
        "min_tail_ess": float(min(tail.values())), "max_rhat": float(max(rhat.values())),
        "finite_draws": bool(np.isfinite(samples).all()), "divergences": int(divergences),
    }
    out["gates"] = {
        "max_rank_rhat": out["max_rhat"] <= g["max_rank_rhat"],
        "min_bulk_ess": out["min_bulk_ess"] >= g["min_bulk_ess"],
        "min_tail_ess": out["min_tail_ess"] >= g["min_tail_ess"],
        "sampling_divergences": divergences == 0,
        "finite_draws": out["finite_draws"],
    }
    out["passed"] = all(out["gates"].values())
    return out


def ess_per_grad(rec: dict) -> None:
    rec["ess_per_gradient"] = rec["min_bulk_ess"] / rec["gradients_total"]
    rec["ess_per_gradient_sampling"] = rec["min_bulk_ess"] / rec["gradients_sampling"]


def save_draws(model: str, arm: str, seed: int, samples: np.ndarray) -> None:
    DRAWS.mkdir(parents=True, exist_ok=True)
    np.save(DRAWS / f"{model}-{arm}-{seed}.npy", samples.astype(np.float64))


# --------------------------------------------------------------------------- oWALNUTS (Python package)


def py_arm_config(arm: str, model: str, seed: int, dim: int):
    import owalnuts

    arm = arm.removesuffix("-uinit")  # amendment A1: same arm, init="uniform"

    if arm == "py-default":
        return owalnuts.Tuning(), owalnuts.Adaptation(), None
    if arm == "py-delta2":
        return owalnuts.Tuning(max_error=2.0), owalnuts.Adaptation(), None
    if arm == "py-levels1":
        return owalnuts.Tuning(max_refinement_levels=1), owalnuts.Adaptation(), None
    if arm == "py-nutpiemetric":
        m = np.asarray(json.loads((MASS / f"{model}-{seed}.json").read_text(encoding="utf-8"))["momentum_covariance"])
        assert m.shape == (dim,)
        return owalnuts.Tuning(), owalnuts.Adaptation(adapt_mass=False), m
    raise ValueError(arm)


def run_owalnuts_py(model: str, arm: str, seed: int) -> dict:
    import owalnuts

    fn, dim = density(model)
    fn(np.zeros(dim))  # prime (compiles nothing for PyTensor C; pure function)
    counter = Counter(fn)
    tuning, adaptation, mass = py_arm_config(arm, model, seed, dim)
    t = time.perf_counter()
    uinit = arm.endswith("-uinit")
    res = owalnuts.sample(counter, dim, chains=CH, warmup=WU, draws=DR, seed=seed, threads=1,
                          tuning=tuning, adaptation=adaptation, mass=mass, init="uniform" if uinit else None)
    start_calls = counter.n - int(res.target_calls) if uinit else 0
    wall = time.perf_counter() - t
    chains = res.chains
    wt = lambda c, k: int(c[k]["target_calls_total"])  # noqa: E731
    g_warm = sum(wt(c, "work_discarded") for c in chains)
    g_samp = sum(wt(c, "work_retained") for c in chains)
    g_kernel_total = sum(wt(c, "work_total") for c in chains)
    g_initial = sum(int(c["work_total"]["target_calls_total"]) - int(c["work_total"]["target_calls_forward"])
                    - int(c["work_total"]["target_calls_reverse"]) for c in chains)
    div = sum(int(c["work_retained"]["divergences"]) for c in chains)
    rec = {
        "model": model, "arm": arm, "seed": seed, "path": "python", "status": "ok", "wall_seconds": wall,
        "dimension": dim, "threads": 1,
        "gradients_total": int(res.target_calls) + start_calls, "init": "uniform" if uinit else "None (numpy uniform(-2,2))",
        "gradients_sampling": g_samp, "gradients_warmup": g_warm, "gradients_start_selection": start_calls,
        "gradients_initial_evaluation": g_initial,
        "gradients_kernel_telemetry_total": g_kernel_total,
        "gradients_counted_callbacks": counter.n,
        "accounting_check": {"transport_minus_counted": int(res.target_calls) + start_calls - counter.n,
                             "kernel_minus_counted": g_kernel_total - counter.n},
        "final_step_size": [float(c["metadata"]["final_step_size"]) for c in chains],
        "mean_depth": float(np.mean([np.asarray(c["depth"])[WU:].mean() for c in chains])),
        "mean_gradients_per_transition": g_samp / (CH * DR),
        "mean_leaves_built": float(np.mean([np.asarray(c["leaves_built"])[WU:].mean() for c in chains])),
        "mean_macro_length": float(np.mean([np.asarray(c["trajectory_macro_length"])[WU:].mean() for c in chains])),
        "fraction_selected_refined": float(np.mean([(np.asarray(c["selected_refinement_level"])[WU:] > 0).mean() for c in chains])),
        "retained_reverse_calls": sum(int(c["work_retained"]["target_calls_reverse"]) for c in chains),
        "retained_leaves_built": sum(int(c["work_retained"]["leaves_built"]) for c in chains),
        "max_depth_stops": sum(int(c["work_retained"]["maximum_depth_stops"]) for c in chains),
        "refinement_exhaustion_stops": sum(int(c["work_retained"]["refinement_exhaustion_stops"]) for c in chains),
        "acceptance_statistic": None,
        "acceptance_statistic_note": "the Python package does not expose the per-transition acceptance statistic",
        "mass_diagonal": [list(map(float, c["metadata"]["mass_diagonal"])) for c in chains],
        "algorithm_revision": res.algorithm_revision,
        **summarize(model, res.samples, div),
    }
    ess_per_grad(rec)
    save_draws(model, arm, seed, res.samples)
    return rec


# --------------------------------------------------------------------------- nutpie


def nutpie_pyfunc(fn, dim: int, counter_box: list):
    """nutpie.from_pyfunc around the same density callable, counting calls."""
    from nutpie.compiled_pyfunc import from_pyfunc

    def make_logp_fn():
        def logp(x, **_shared):
            counter_box[0] += 1
            lp, g = fn(x)
            return float(lp), np.ascontiguousarray(g, dtype=np.float64)
        return logp

    def make_expand_fn(*_args):
        def expand(x, **_shared):
            return {"x": np.array(x, dtype=np.float64)}
        return expand

    def init(seed):
        return np.random.default_rng(seed).uniform(-2.0, 2.0, dim)

    return from_pyfunc(dim, make_logp_fn, make_expand_fn, [np.dtype("float64")], [(dim,)], ["x"],
                       make_initial_point_fn=init)


def run_nutpie(model: str, arm: str, seed: int) -> dict:
    import nutpie
    import callpath_targets as T

    box = [0]
    native = model in PYMC_MODELS and arm in ("nutpie", "nutpie-drawmetric")
    if native:
        compiled = nutpie.compile_pymc_model(T.pymc_model(model))
        dim = T.DIM[model]
        path = "nutpie.compile_pymc_model (numba backend)"
    else:
        fn, dim = density(model)
        fn(np.zeros(dim))
        compiled = nutpie_pyfunc(fn, dim, box)
        path = "nutpie.from_pyfunc around the study density callable (counted)"
    kw = {"use_grad_based_mass_matrix": False} if arm == "nutpie-drawmetric" else {}
    box[0] = 0
    t = time.perf_counter()
    idata = nutpie.sample(compiled, draws=DR, tune=WU, chains=CH, cores=1, seed=seed, progress_bar=False,
                          save_warmup=True, store_mass_matrix=True, **kw)
    wall = time.perf_counter() - t
    if native:
        samples = T.unconstrained_from_posterior(model, idata.posterior)
    else:
        samples = np.asarray(idata.posterior["x"].values, dtype=np.float64)
    st, wst = idata.sample_stats, idata.warmup_sample_stats
    g_samp = int(st["n_steps"].values.sum())
    g_warm = int(wst["n_steps"].values.sum())
    div = int(st["diverging"].values.sum())
    inv = np.asarray(st["mass_matrix_inv"].values)[:, -1, :]  # (chains, dim), final
    rec = {
        "model": model, "arm": arm, "seed": seed, "path": path, "status": "ok", "wall_seconds": wall,
        "dimension": dim, "cores": 1, "kwargs": kw,
        "gradients_total": g_samp + g_warm, "gradients_sampling": g_samp, "gradients_warmup": g_warm,
        "gradients_start_selection": None,
        "gradients_counted_callbacks": None if native else box[0],
        "accounting_check": None if native else {"n_steps_minus_counted": g_samp + g_warm - box[0]},
        "final_step_size": [float(x) for x in np.asarray(st["step_size"].values)[:, -1]],
        "mean_depth": float(np.asarray(st["depth"].values).mean()),
        "mean_gradients_per_transition": g_samp / (CH * DR),
        "acceptance_statistic": float(np.asarray(st["mean_tree_accept"].values).mean()),
        "max_depth_stops": int(np.asarray(st["maxdepth_reached"].values).sum()) if "maxdepth_reached" in st else None,
        "final_mass_matrix_inv": inv.tolist(),
        **summarize(model, samples, div),
    }
    ess_per_grad(rec)
    save_draws(model, arm, seed, samples)
    if arm == "nutpie":
        # Transplant for the *-nutpiemetric arms: momentum covariance M = 1 / (chain-mean inverse mass).
        write_json(MASS / f"{model}-{seed}.json", {"source": f"{model}-nutpie-{seed}",
                                                     "mass_matrix_inv_chain_mean": inv.mean(0).tolist(),
                                                     "momentum_covariance": (1.0 / inv.mean(0)).tolist()})
    return rec


# --------------------------------------------------------------------------- Rust harness


def rust_cell(model: str, arm: str, seed: int) -> dict:
    a = arm.removeprefix("rs-")
    DRAWS.mkdir(parents=True, exist_ok=True)
    tmp = ART / "rust-raw"
    tmp.mkdir(parents=True, exist_ok=True)
    out = tmp / f"{model}-{arm}-{seed}.json"
    binf = DRAWS / f"{model}-{arm}-{seed}.bin"
    for p in (out, binf):
        if p.exists():
            p.unlink()
    if model in PYMC_MODELS:
        kind, p1, p2 = model, str(MODELS / "hier_data.json") if model == "hier" else "-", "-"
    else:
        m = STAN_MODELS[model]
        kind, p1, p2 = "stan", str(MODELS / f"{m}_model.so"), str(MODELS / f"{m}.data.json")
    mass = str(MASS / f"{model}-{seed}.mass-only.json") if a == "nutpiemetric" else "-"
    if a == "nutpiemetric":
        src = json.loads((MASS / f"{model}-{seed}.json").read_text(encoding="utf-8"))
        Path(mass).write_text(json.dumps(src["momentum_covariance"]), encoding="utf-8")
    cmd = [str(HARNESS), kind, p1, p2, a, str(seed), str(out), str(binf), str(PROTOCOL["rust_threads"]), mass]
    env = dict(os.environ, RUSTUP_TOOLCHAIN="1.88.0-x86_64-pc-windows-gnu")
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=PROTOCOL["cell_timeout_seconds"], env=env)
    except subprocess.TimeoutExpired:
        return {"model": model, "arm": arm, "seed": seed, "status": "timeout"}
    if cp.returncode != 0 or not out.exists():
        return {"model": model, "arm": arm, "seed": seed, "status": "error", "error": cp.stderr[-3000:]}
    raw = json.loads(out.read_text(encoding="utf-8"))
    dim = raw["dimension"]
    samples = np.fromfile(binf, dtype="<f8").reshape(CH, DR, dim)
    np.save(DRAWS / f"{model}-{arm}-{seed}.npy", samples)
    binf.unlink()
    cd = raw["chains_data"]
    g_samp = sum(c["work_retained"]["target_calls_total"] for c in cd)
    g_warm = sum(c["work_discarded"]["target_calls_total"] for c in cd)
    g_kernel = sum(c["work_total"]["target_calls_total"] for c in cd)
    div = sum(c["work_retained"]["divergences"] for c in cd)
    rec = {
        "model": model, "arm": arm, "seed": seed, "path": "rust", "status": "ok",
        "wall_seconds": raw["wall_seconds"], "dimension": dim, "threads": raw["threads"],
        "gradients_total": raw["counted_calls_total"],
        "gradients_sampling": g_samp, "gradients_warmup": g_warm,
        "gradients_start_selection": raw["counted_calls_start_selection"],
        "gradients_initial_evaluation": sum(c["work_total"]["target_calls_initial"] for c in cd),
        "gradients_kernel_telemetry_total": g_kernel,
        "gradients_counted_callbacks": raw["counted_calls_total"],
        "accounting_check": {"kernel_plus_start_minus_counted": g_kernel + raw["counted_calls_start_selection"]
                             - raw["counted_calls_total"],
                             "posterior_total_minus_kernel": raw["kernel_total_target_calls"] - g_kernel},
        "final_step_size": [c["final_step_size"] for c in cd],
        "mean_depth": float(np.mean([c["retained_mean_depth"] for c in cd])),
        "mean_gradients_per_transition": g_samp / (CH * DR),
        "mean_leaves_built": float(np.mean([c["retained_mean_leaves_built"] for c in cd])),
        "mean_orbit_states": float(np.mean([c["retained_mean_orbit_states"] for c in cd])),
        "mean_macro_length": float(np.mean([c["retained_mean_macro_length"] for c in cd])),
        "fraction_selected_refined": float(np.mean([c["retained_fraction_selected_refined"] for c in cd])),
        "retained_reverse_calls": sum(c["work_retained"]["target_calls_reverse"] for c in cd),
        "retained_leaves_built": sum(c["work_retained"]["leaves_built"] for c in cd),
        "retained_refinement_level_built": [sum(x) for x in zip(*[c["work_retained"]["refinement_level_built"] + [0] * 9
                                                                  for c in cd])][:9],
        "max_depth_stops": sum(c["work_retained"]["maximum_depth_stops"] for c in cd),
        "refinement_exhaustion_stops": sum(c["work_retained"]["refinement_exhaustion_stops"] for c in cd),
        "acceptance_statistic": float(np.nanmean([c["warmup_last100_mean_acceptance_statistic"] for c in cd])),
        "acceptance_statistic_note": "mean of the arm's own dual-averaging statistic over the last 100 warmup "
                                     "transitions (retained transitions are not captured by the facade)",
        "mass_diagonal": [c["mass_diagonal"] for c in cd],
        "tuning": raw["tuning"], "adaptation": raw["adaptation"], "init": raw["init"],
        "algorithm_revision": raw["algorithm_revision"],
        **summarize(model, samples, div),
    }
    ess_per_grad(rec)
    return rec


# --------------------------------------------------------------------------- plan / orchestration


def arms_for(model: str) -> list[str]:
    arms = list(PROTOCOL["python_nutpie_arms"])
    if model in STAN_MODELS:
        arms.remove("nutpie-counted")  # the Stan nutpie arm is itself counted
    return arms + PROTOCOL["python_owalnuts_arms"] + PROTOCOL["rust_arms"]


def plan() -> list[tuple[str, str, int]]:
    """Frozen order: seeds outer, models in protocol order, arms in protocol
    order (nutpie first: the *-nutpiemetric arms transplant its metric)."""
    steps = [(m, a, s) for s in PROTOCOL["seeds"] for m in PROTOCOL["models"] for a in arms_for(m)]
    a1 = PROTOCOL.get("amendment_A1")
    if a1:
        steps += [(m, a, s) for s in PROTOCOL["seeds"] for m in a1["added_models"] for a in a1["added_arms"]]
    return steps


def cell_path(model: str, arm: str, seed: int) -> Path:
    return CELLS / f"{model}-{arm}-{seed}.json"


def run_all() -> None:
    steps = plan()
    log(f"{len(steps)} cells")
    meta = ART / "measured_on.json"
    if not meta.exists():
        write_json(meta, {"platform": platform.platform(), "processor": platform.processor(),
                          "cpu_count": os.cpu_count(),
                          "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                          "note": "shared 16-core machine with sibling agents: every wall is contended"})
    for i, (model, arm, seed) in enumerate(steps):
        out = cell_path(model, arm, seed)
        if out.exists():
            continue
        t = time.perf_counter()
        if arm.startswith("rs-"):
            try:
                rec = rust_cell(model, arm, seed)
            except Exception as e:  # noqa: BLE001 - failures are results
                rec = {"model": model, "arm": arm, "seed": seed, "status": "error",
                       "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()}
            write_json(out, rec)
        else:
            env = dict(os.environ, PYTHONIOENCODING="utf-8",
                       PYTENSOR_FLAGS=f"compiledir={PROTOCOL['pytensor_compiledir']}")
            p = subprocess.Popen([sys.executable, str(Path(__file__)), "cell", model, arm, str(seed)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
            try:
                _, stderr = p.communicate(timeout=PROTOCOL["cell_timeout_seconds"])
                err = None if (p.returncode == 0 and out.exists()) else f"exit {p.returncode}: {stderr[-3000:]}"
            except subprocess.TimeoutExpired:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
                p.communicate()
                if out.exists():
                    out.unlink()
                err = "timeout"
            if err:
                write_json(out, {"model": model, "arm": arm, "seed": seed, "status": "process_error", "error": err})
        rec = json.loads(out.read_text(encoding="utf-8"))
        extra = ""
        if rec.get("status") == "ok":
            extra = (f"grads {rec['gradients_total']} minESS {rec['min_bulk_ess']:.0f} "
                     f"ESS/grad {1e3 * rec['ess_per_gradient']:.3f}e-3 h {np.mean(rec['final_step_size']):.3g} "
                     f"depth {rec['mean_depth']:.2f} rhat {rec['max_rhat']:.4f} div {rec['divergences']} "
                     f"pass {rec['passed']}")
        log(f"{i + 1}/{len(steps)} {model} {arm} {seed} {rec.get('status')} {extra} ({time.perf_counter() - t:.0f}s)")


def child(model: str, arm: str, seed: int) -> None:
    out = cell_path(model, arm, seed)
    try:
        if arm.startswith("nutpie"):
            rec = run_nutpie(model, arm, seed)
        else:
            rec = run_owalnuts_py(model, arm, seed)
        rec["packages"] = package_versions()
    except Exception as e:  # noqa: BLE001 - failures are results
        rec = {"model": model, "arm": arm, "seed": seed, "status": "error", "error": f"{type(e).__name__}: {e}",
               "traceback": traceback.format_exc()}
    write_json(out, rec)


def package_versions() -> dict:
    out = {"python": sys.version.split()[0]}
    for m in ("numpy", "numba", "pymc", "pytensor", "nutpie", "owalnuts", "bridgestan"):
        mod = sys.modules.get(m)
        if mod is not None:
            out[m] = getattr(mod, "__version__", "?")
    return out


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "run":
        run_all()
    elif cmd == "cell":
        child(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    else:
        raise SystemExit(__doc__)
