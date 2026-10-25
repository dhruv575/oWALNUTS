#!/usr/bin/env python3
"""python_callpath_v1 driver (WP47; see PREREGISTRATION.md).

    python run_callpath.py run <phase>            # every micro + sampler cell of a phase, frozen order
    python run_callpath.py micro <phase> <build> <target> <path>
    python run_callpath.py cell <phase> <build> <target> <arm> <threads> <seed>
    python run_callpath.py analyze

Each cell runs in its own child process under the interpreter of its build
(``protocol.json`` ``builds``), so one process imports one framework, exactly
as a user would. Cells write ``artifacts/<phase>/{micro,cells}/*.json``
(metrics only) and ``artifacts/<phase>/draws/*.npz`` (raw draws, not
committed). Failures are recorded as cells with ``status != "ok"``.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
import traceback
from pathlib import Path

os.environ.setdefault("JAX_PLATFORMS", "cpu")
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
ART = HERE / "artifacts"
SEEDS = PROTOCOL["seeds"]
TARGETS = PROTOCOL["targets"]
OW_ARMS = PROTOCOL["owalnuts_arms"]
NUTPIE_ARMS = PROTOCOL["nutpie_arms"]
MICRO_PATHS = PROTOCOL["micro_paths"]
THREADS = PROTOCOL["threads"]
N_MICRO = PROTOCOL["micro_calls"]
TIMEOUT = PROTOCOL["cell_timeout_seconds"]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=float), encoding="utf-8")


# --------------------------------------------------------------------------- targets per arm


def build_target(target: str, arm: str, threads: int):
    """Return (sample_target, dim, keep) for an oWALNUTS arm."""
    import owalnuts
    import callpath_targets as T

    dim = T.DIM[target]
    if arm == "py-numpy":
        return T.numpy_target(target), dim, None
    if arm == "py-njit":
        f, core = T.njit_callable(target)
        return f, dim, core
    if arm == "cfunc":
        cft, raw, core = T.cfunc_target(target)
        return cft, dim, (raw, core)
    if arm == "jax":
        return owalnuts.from_jax(T.jax_logp(target)), dim, None
    if arm == "torch":
        return owalnuts.from_torch(T.torch_logp(target)), dim, None
    if arm in ("pymc", "pymc-numba"):
        mode = "NUMBA" if arm == "pymc-numba" else None
        # The documented rule: the default wrapper is threads=1 only;
        # thread_safe=True (one compiled function per thread) for threads > 1.
        tgt, d, _q0, _names, _unravel = owalnuts.from_pymc(T.pymc_model(target), mode=mode, thread_safe=threads > 1)
        assert d == dim
        return tgt, dim, None
    if arm == "pymc-gilfree":
        tgt, d, _q0, _names, _unravel = owalnuts.from_pymc(T.pymc_model(target), gil_free=True)
        assert d == dim
        return tgt, dim, None
    raise ValueError(arm)


def call_once(tgt, q):
    """One evaluation through the Python surface (cfunc targets via ctypes)."""
    import owalnuts

    if isinstance(tgt, owalnuts.CFuncTarget):
        return ctypes_caller(tgt)(q)
    return tgt(q)


_CALLERS: dict = {}


def ctypes_caller(cft):
    import ctypes

    key = cft.address
    if key not in _CALLERS:
        proto = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_ssize_t, ctypes.POINTER(ctypes.c_double),
                                 ctypes.POINTER(ctypes.c_double), ctypes.c_void_p)
        fn = proto(cft.address)
        dim = cft.dim
        g = np.zeros(dim)
        gp = g.ctypes.data_as(ctypes.POINTER(ctypes.c_double))

        def call(q):
            q = np.ascontiguousarray(q, dtype=np.float64)
            return fn(dim, q.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), gp, None), g
        _CALLERS[key] = call
    return _CALLERS[key]


# --------------------------------------------------------------------------- microbenchmarks


def time_calls(fn, qs, n: int) -> dict:
    """Median/p10/p90 of n individually timed calls (perf_counter_ns)."""
    t = time.perf_counter_ns
    out = np.empty(n)
    m = len(qs)
    for i in range(n):
        q = qs[i % m]
        a = t()
        fn(q)
        out[i] = t() - a
    us = out / 1000.0
    return {"median_us": float(np.median(us)), "p10_us": float(np.percentile(us, 10)),
            "p90_us": float(np.percentile(us, 90)), "mean_us": float(us.mean()), "calls": n}


def run_micro(phase: str, build: str, target: str, path: str) -> dict:
    import owalnuts
    import callpath_targets as T

    t0 = time.perf_counter()
    tgt, dim, keep = build_target(target, path, 1)
    rng = np.random.default_rng(PROTOCOL["micro_point_seed"])
    qs = [np.ascontiguousarray(rng.uniform(-1.0, 1.0, dim)) for _ in range(16)]
    for q in qs * 8:  # prime (JIT compiles, caches)
        call_once(tgt, q)
    construct = time.perf_counter() - t0
    rec = {"phase": phase, "build": build, "target": target, "path": path, "construct_seconds": construct,
           "components": {}}
    rec["components"]["adapter_call"] = time_calls(lambda q: call_once(tgt, q), qs, N_MICRO)
    if not isinstance(tgt, owalnuts.CFuncTarget):
        wrapped = owalnuts.wrap_callable(tgt)
        rec["components"]["wrap_callable(adapter)"] = time_calls(wrapped, qs, N_MICRO)
    # Decomposition: the raw compiled function without adapter glue.
    if path in ("py-njit", "cfunc"):
        core = keep if path == "py-njit" else keep[1]
        g = np.empty(dim)
        rec["components"]["njit_core_from_python"] = time_calls(lambda q: core(q, g), qs, N_MICRO)
        import numba

        @numba.njit
        def loop(core_, qarr, g_, n):
            s = 0.0
            for i in range(n):
                s += core_(qarr[i % qarr.shape[0]], g_)
            return s
        qarr = np.stack(qs)
        loop(core, qarr, g, 10)
        reps = []
        for _ in range(5):
            a = time.perf_counter_ns()
            loop(core, qarr, g, N_MICRO)
            reps.append((time.perf_counter_ns() - a) / 1000.0 / N_MICRO)
        rec["components"]["njit_loop_mean"] = {"median_us": float(statistics.median(reps)),
                                               "note": "median over 5 repeats of the mean of 10^4 calls inside one njit loop"}
    if path == "jax":
        import jax
        import jax.numpy as jnp
        vg = jax.jit(jax.value_and_grad(T.jax_logp(target)))
        vg(qs[0])
        rec["components"]["jit_vg(numpy)+block"] = time_calls(lambda q: jax.block_until_ready(vg(q)), qs, N_MICRO)
        rec["components"]["jit_vg(jnp.asarray)+block"] = time_calls(
            lambda q: jax.block_until_ready(vg(jnp.asarray(q))), qs, N_MICRO)
    if path in ("pymc", "pymc-numba"):
        mode = "NUMBA" if path == "pymc-numba" else None
        fn = T.pymc_model(target).logp_dlogp_function(ravel_inputs=True, mode=mode)
        fn.set_extra_values({})
        fn(qs[0])
        rec["components"]["ValueGradFunction(q)"] = time_calls(fn, qs, N_MICRO)
        pf = fn._pytensor_function
        pf(qs[0])
        rec["components"]["pytensor_function(q)"] = time_calls(pf, qs, N_MICRO)
        pf.trust_input = True
        rec["components"]["pytensor_function(q) trust_input"] = time_calls(pf, qs, N_MICRO)
    rec["status"] = "ok"
    rec["packages"] = package_versions()
    return rec


# --------------------------------------------------------------------------- sampler cells


def summarize(target: str, samples: np.ndarray) -> dict:
    import owalnuts
    import callpath_targets as T

    f, names = T.functionals(target, samples)
    rows = owalnuts.summary(f, names)
    bulk = {r["name"]: r["ess_bulk"] for r in rows}
    tail = {r["name"]: r["ess_tail"] for r in rows}
    rhat = {r["name"]: r["rhat"] for r in rows}
    return {
        "min_bulk_ess": float(min(bulk.values())), "argmin_bulk": min(bulk, key=bulk.get),
        "min_tail_ess": float(min(tail.values())), "max_rhat": float(max(rhat.values())),
        "mean": {r["name"]: r["mean"] for r in rows}, "mcse_mean": {r["name"]: r["mcse_mean"] for r in rows},
    }


def sha(samples: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(samples, dtype=np.float64).tobytes()).hexdigest()


def run_owalnuts_cell(phase: str, build: str, target: str, arm: str, threads: int, seed: int) -> dict:
    import owalnuts

    t0 = time.perf_counter()
    tgt, dim, keep = build_target(target, arm, threads)
    construct = time.perf_counter() - t0
    s = PROTOCOL["sampler"]
    t1 = time.perf_counter()
    res = owalnuts.sample(tgt, dim, chains=s["chains"], warmup=s["warmup"], draws=s["draws"], seed=seed,
                          threads=threads)
    wall = time.perf_counter() - t1
    h = res.health()
    summ = summarize(target, res.samples)
    rec = {
        "phase": phase, "build": build, "target": target, "arm": arm, "threads": threads, "seed": seed,
        "status": "ok", "construct_seconds": construct, "wall_seconds": wall,
        "wall_seconds_rust": res.wall_seconds, "target_calls": res.target_calls,
        "retained_target_calls": res.retained_target_calls,
        "attached_seconds": res.target_attached_seconds,
        "attached_fraction": res.target_attached_seconds / res.wall_seconds if res.wall_seconds else None,
        "wall_per_call_us": 1e6 * res.wall_seconds / res.target_calls,
        "health": h, "samples_sha256": sha(res.samples),
        "ess_per_second": summ["min_bulk_ess"] / wall,
        "ess_per_call": summ["min_bulk_ess"] / res.target_calls,
        **summ,
    }
    save_draws(phase, build, target, arm, threads, seed, res.samples)
    return rec


def run_nutpie_cell(phase: str, build: str, target: str, arm: str, threads: int, seed: int) -> dict:
    import nutpie
    import callpath_targets as T

    t0 = time.perf_counter()
    compiled = nutpie.compile_pymc_model(T.pymc_model(target))
    construct = time.perf_counter() - t0
    s = PROTOCOL["sampler"]
    t1 = time.perf_counter()
    idata = nutpie.sample(compiled, draws=s["draws"], tune=s["warmup"], chains=s["chains"], cores=threads,
                          seed=seed, progress_bar=False, save_warmup=True)
    wall = time.perf_counter() - t1
    samples = T.unconstrained_from_posterior(target, idata.posterior)
    st, wst = idata.sample_stats, idata.warmup_sample_stats
    grads = int(st["n_steps"].values.sum() + wst["n_steps"].values.sum())
    div = int(st["diverging"].values.sum())
    summ = summarize(target, samples)
    rec = {
        "phase": phase, "build": build, "target": target, "arm": arm, "threads": threads, "seed": seed,
        "status": "ok", "construct_seconds": construct, "wall_seconds": wall,
        "target_calls": grads, "target_calls_kind": "leapfrog n_steps (warmup + draws)",
        "health": {"divergences": div,
                   "maximum_depth_stops": int(np.asarray(st.maxdepth_reached).sum()) if "maxdepth_reached" in st
                   else int((np.asarray(st.depth) >= 10).sum()),
                   "mean_tree_depth": float(np.asarray(st.depth).mean()),
                   "step_size": float(np.asarray(st.step_size)[:, -1].mean())},
        "samples_sha256": sha(samples), "ess_per_second": summ["min_bulk_ess"] / wall,
        "ess_per_call": summ["min_bulk_ess"] / grads, **summ,
    }
    save_draws(phase, build, target, arm, threads, seed, samples)
    return rec


def save_draws(phase, build, target, arm, threads, seed, samples) -> None:
    d = ART / phase / "draws"
    d.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(d / f"{build}-{target}-{arm}-t{threads}-{seed}.npz", samples=samples.astype(np.float64))


def package_versions() -> dict:
    out = {"python": sys.version.split()[0], "executable": sys.executable}
    for m in ("numpy", "numba", "jax", "torch", "pymc", "pytensor", "nutpie", "owalnuts"):
        mod = sys.modules.get(m)
        if mod is not None:
            out[m] = getattr(mod, "__version__", "?")
    try:
        import owalnuts
        out["owalnuts_file"] = owalnuts.__file__
        out["algorithm_revision"] = owalnuts.ALGORITHM_REVISION
    except Exception:  # noqa: BLE001
        pass
    if "torch" in sys.modules:
        out["torch_num_threads"] = sys.modules["torch"].get_num_threads()
    return out


# --------------------------------------------------------------------------- plan


def plan(phase: str) -> list[tuple]:
    """Frozen order. Micro cells first (targets outer, paths rotated per
    target), then sampler cells: seeds outer, targets, then the arm x threads
    list rotated by (seed index * 3 + target index) so no arm always runs
    first or last; builds interleave inside each arm (phase 2)."""
    ph = PROTOCOL["phases"][phase]
    builds = ph["builds"]
    steps: list[tuple] = []
    for ti, target in enumerate(TARGETS):
        paths = MICRO_PATHS[ti:] + MICRO_PATHS[:ti]
        for path in paths:
            if path not in ph["arms"]:
                continue
            for b in builds:
                steps.append(("micro", phase, b, target, path))
    for si, seed in enumerate(SEEDS):
        for ti, target in enumerate(TARGETS):
            arms = [(a, t) for a in ph["arms"] + ph.get("nutpie_arms", []) for t in THREADS]
            r = (si * 3 + ti) % len(arms)
            arms = arms[r:] + arms[:r]
            for arm, t in arms:
                for b in (builds if arm in OW_ARMS else builds[:1]):
                    steps.append(("cell", phase, b, target, arm, str(t), str(seed)))
    return steps


def out_path(step: tuple) -> Path:
    if step[0] == "micro":
        _, phase, b, target, path = step
        return ART / phase / "micro" / f"{b}-{target}-{path}.json"
    _, phase, b, target, arm, t, seed = step
    return ART / phase / "cells" / f"{b}-{target}-{arm}-t{t}-{seed}.json"


def run_phase(phase: str) -> None:
    steps = plan(phase)
    log(f"phase {phase}: {len(steps)} steps")
    meta = ART / phase / "measured_on.json"
    if not meta.exists():
        write_json(meta, {"platform": platform.platform(), "processor": platform.processor(),
                          "cpu_count": os.cpu_count(), "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                          "builds": {b: PROTOCOL["builds"][b] for b in PROTOCOL["phases"][phase]["builds"]},
                          "note": "shared 16-core machine, ~10 concurrent agents: every wall is contended"})
    for i, step in enumerate(steps):
        out = out_path(step)
        if out.exists():
            continue
        build = step[2]
        exe = PROTOCOL["builds"][build]["python"]
        env = dict(os.environ, JAX_PLATFORMS="cpu", PYTHONIOENCODING="utf-8",
                   PYTENSOR_FLAGS=f"compiledir={PROTOCOL['pytensor_compiledir']}")
        t = time.perf_counter()
        try:
            p = subprocess.run([exe, str(Path(__file__)), *step], capture_output=True, text=True, timeout=TIMEOUT,
                               env=env)
            ok = p.returncode == 0 and out.exists()
            err = None if ok else f"exit {p.returncode}: {p.stderr[-3000:]}"
        except subprocess.TimeoutExpired:
            ok, err = False, f"timeout {TIMEOUT}s"
        if not ok:
            write_json(out, {"step": list(step), "status": "process_error", "error": err})
        rec = json.loads(out.read_text(encoding="utf-8"))
        extra = ""
        if rec.get("status") == "ok" and step[0] == "cell":
            extra = (f"wall {rec['wall_seconds']:.2f}s calls {rec['target_calls']} minESS {rec['min_bulk_ess']:.0f} "
                     f"ESS/s {rec['ess_per_second']:.0f} rhat {rec['max_rhat']:.4f} div {rec['health']['divergences']}")
        elif rec.get("status") == "ok":
            extra = f"adapter {rec['components']['adapter_call']['median_us']:.2f}us"
        log(f"{i + 1}/{len(steps)} {' '.join(step[2:])} {rec.get('status')} {extra} ({time.perf_counter() - t:.0f}s)")


def child(argv: list[str]) -> None:
    kind = argv[0]
    out = out_path(tuple(argv))
    try:
        if kind == "micro":
            _, phase, b, target, path = argv
            rec = run_micro(phase, b, target, path)
        else:
            _, phase, b, target, arm, t, seed = argv
            fn = run_nutpie_cell if arm in NUTPIE_ARMS else run_owalnuts_cell
            rec = fn(phase, b, target, arm, int(t), int(seed))
            rec["packages"] = package_versions()
    except Exception as e:  # noqa: BLE001 - failures are results
        rec = {"step": argv, "status": "error", "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()}
    write_json(out, rec)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "run":
        run_phase(sys.argv[2])
    elif cmd in ("micro", "cell"):
        child(sys.argv[1:])
    elif cmd == "analyze":
        import analyze_callpath
        analyze_callpath.main()
    else:
        raise SystemExit(__doc__)
