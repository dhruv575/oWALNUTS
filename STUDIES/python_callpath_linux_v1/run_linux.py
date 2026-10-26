#!/usr/bin/env python3
"""python_callpath_linux_v1 driver (WP78; see PREREGISTRATION.md, protocol.json).

    python run_linux.py run                         # every micro + sampler cell, frozen order; skips written cells
    python run_linux.py micro <target> <path>       # one micro cell (child process)
    python run_linux.py cell <target> <arm> <threads> <seed>   # one Python / nutpie sampler cell (child)
    python run_linux.py setupcheck                  # value/gradient agreement of every path (setup, not evidence)
    WP78_SMOKE=1 WP78_ART=<dir> python run_linux.py run   # plumbing check: seed 1, short runs, outside artifacts/

Runs on the shared Linux box, lane 4: the caller pins the whole process tree
with ``taskset -c 12-15`` (children inherit the affinity) and sources the
lane ``env.sh``. Every cell runs in its own child process, strictly one at a
time. Cells write ``artifacts/{micro,cells}/*.json`` (metrics) and
``artifacts/draws/*.npy`` (raw draws, not committed, hashed in
CHECKSUMS.sha256). Failures are cells with ``status != "ok"``; nothing is
rerun.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import signal
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
ART = Path(os.environ.get("WP78_ART", str(HERE / "artifacts")))
SEEDS = PROTOCOL["seeds"]
TARGETS = PROTOCOL["targets"]
OW_ARMS = PROTOCOL["owalnuts_arms"]
NUTPIE_ARMS = PROTOCOL["nutpie_arms"]
MICRO_PATHS = PROTOCOL["micro_paths"]
THREADS = PROTOCOL["threads"]
N_MICRO = PROTOCOL["micro_calls"]
TIMEOUT = PROTOCOL["cell_timeout_seconds"]
SAMPLER = PROTOCOL["sampler"]
GATES = PROTOCOL["gates"]
if os.environ.get("WP78_SMOKE"):
    # Plumbing check only (protocol "smoke"): seed 1, short runs, written
    # outside artifacts/ (WP78_ART must point elsewhere), then deleted.
    assert "WP78_ART" in os.environ, "smoke needs WP78_ART outside artifacts/"
    SEEDS = [1]
    TARGETS = PROTOCOL["smoke"]["targets"]
    N_MICRO = PROTOCOL["smoke"]["micro_calls"]
    SAMPLER = dict(SAMPLER, warmup=PROTOCOL["smoke"]["warmup"], draws=PROTOCOL["smoke"]["draws"])
HIER_DATA = HERE / "models" / "hier_data.json"
RUST_BIN = Path(os.environ.get("WP78_RUST_BIN", str(HERE / "rust" / "target" / "release" / "wp78-rust")))


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=float), encoding="utf-8")


def micro_points(dim: int) -> list[np.ndarray]:
    rng = np.random.default_rng(PROTOCOL["micro_point_seed"])
    return [np.ascontiguousarray(rng.uniform(-1.0, 1.0, dim)) for _ in range(16)]


# --------------------------------------------------------------------------- targets per arm


def build_target(target: str, arm: str, threads: int):
    """(sample_target, dim, keep) for an oWALNUTS Python arm (protocol arm_definitions)."""
    import owalnuts
    import callpath_targets as T

    dim = T.DIM[target]
    if arm == "py-njit":
        f, core = T.njit_callable(target)
        return f, dim, core
    if arm == "cfunc":
        cft, raw, core = T.cfunc_safe_target(target)
        return cft, dim, (raw, core)
    if arm == "jax":
        return owalnuts.from_jax(T.jax_logp(target)), dim, None
    if arm == "pymc":
        # The documented rule: the default wrapper is threads=1 only;
        # thread_safe=True (one compiled function per worker thread) for threads > 1.
        tgt, d, _q0, _names, _unravel = owalnuts.from_pymc(T.pymc_model(target), thread_safe=threads > 1)
        assert d == dim
        return tgt, dim, None
    if arm == "pymc-gilfree":
        tgt, d, _q0, _names, _unravel = owalnuts.from_pymc(T.pymc_model(target), gil_free=True)
        assert d == dim
        return tgt, dim, None
    raise ValueError(arm)


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


def call_once(tgt, q):
    """One evaluation through the Python surface (cfunc targets via ctypes)."""
    import owalnuts

    if isinstance(tgt, owalnuts.CFuncTarget):
        return ctypes_caller(tgt)(q)
    return tgt(q)


# --------------------------------------------------------------------------- micro cells


def time_calls(fn, qs, n: int) -> dict:
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


def run_micro(target: str, path: str) -> dict:
    import owalnuts
    import callpath_targets as T

    t0 = time.perf_counter()
    tgt, dim, keep = build_target(target, path, 1)
    qs = micro_points(dim)
    for q in qs * 8:  # prime
        call_once(tgt, q)
    construct = time.perf_counter() - t0
    rec = {"target": target, "path": path, "construct_seconds": construct, "components": {}}
    rec["components"]["adapter_call"] = time_calls(lambda q: call_once(tgt, q), qs, N_MICRO)
    if not isinstance(tgt, owalnuts.CFuncTarget):
        wrapped = owalnuts.wrap_callable(tgt)
        rec["components"]["wrap_callable(adapter)"] = time_calls(wrapped, qs, N_MICRO)
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
        vg = jax.jit(jax.value_and_grad(T.jax_logp(target)))
        vg(qs[0])
        rec["components"]["jit_vg(numpy)+block"] = time_calls(lambda q: jax.block_until_ready(vg(q)), qs, N_MICRO)
    if path == "pymc":
        fn = T.pymc_model(target).logp_dlogp_function(ravel_inputs=True)
        fn.set_extra_values({})
        fn(qs[0])
        rec["components"]["ValueGradFunction(q)"] = time_calls(fn, qs, N_MICRO)
        pf = fn._pytensor_function
        pf(qs[0])
        pf.trust_input = True
        rec["components"]["pytensor_function(q) trust_input"] = time_calls(pf, qs, N_MICRO)
    rec["status"] = "ok"
    rec["packages"] = package_versions()
    return rec


def run_micro_rust(target: str, out: Path) -> dict:
    import callpath_targets as T

    pts = out.with_suffix(".points.json")
    pts.parent.mkdir(parents=True, exist_ok=True)
    pts.write_text(json.dumps([q.tolist() for q in micro_points(T.DIM[target])]), encoding="utf-8")
    raw = out.with_suffix(".raw.json")
    cmd = [str(RUST_BIN), "micro", target, str(HIER_DATA) if target == "hier" else "-", str(pts), str(N_MICRO),
           str(raw)]
    cp = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    pts.unlink()
    if cp.returncode != 0 or not raw.exists():
        return {"target": target, "path": "rust", "status": "error", "error": cp.stderr[-3000:]}
    comp = json.loads(raw.read_text(encoding="utf-8"))
    raw.unlink()
    return {"target": target, "path": "rust", "status": "ok",
            "components": {"native_eval (Instant per call)": {k: comp[k] for k in ("median_us", "p10_us", "p90_us",
                                                                                  "calls")},
                           "timer_overhead": {"median_us": comp["timer_overhead_median_us"]},
                           "native_loop_mean": {"median_us": comp["loop_mean_us"],
                                                "note": "median over 5 repeats of the mean of 10^4 calls in one loop"}}}


# --------------------------------------------------------------------------- sampler cells


def summarize(target: str, samples: np.ndarray, divergences: int) -> dict:
    import owalnuts
    import callpath_targets as T

    f, names = T.functionals(target, samples)
    rows = owalnuts.summary(f, names)
    bulk = {r["name"]: r["ess_bulk"] for r in rows}
    tail = {r["name"]: r["ess_tail"] for r in rows}
    rhat = {r["name"]: r["rhat"] for r in rows}
    out = {
        "min_bulk_ess": float(min(bulk.values())), "argmin_bulk": min(bulk, key=bulk.get),
        "min_tail_ess": float(min(tail.values())), "max_rhat": float(max(rhat.values())),
        "finite_draws": bool(np.isfinite(samples).all()), "divergences": int(divergences),
    }
    out["gates"] = {
        "max_rank_rhat": out["max_rhat"] <= GATES["max_rank_rhat"],
        "min_bulk_ess": out["min_bulk_ess"] >= GATES["min_bulk_ess"],
        "min_tail_ess": out["min_tail_ess"] >= GATES["min_tail_ess"],
        "sampling_divergences": divergences == 0,
        "finite_draws": out["finite_draws"],
    }
    out["passed"] = all(out["gates"].values())
    return out


def sha(samples: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(samples, dtype=np.float64).tobytes()).hexdigest()


def save_draws(name: str, samples: np.ndarray) -> None:
    d = ART / "draws"
    d.mkdir(parents=True, exist_ok=True)
    np.save(d / f"{name}.npy", np.ascontiguousarray(samples, dtype=np.float64))


def cell_name(target: str, arm: str, threads: int, seed: int) -> str:
    return f"{target}-{arm}-t{threads}-{seed}"


def run_owalnuts_cell(target: str, arm: str, threads: int, seed: int) -> dict:
    import owalnuts

    t0 = time.perf_counter()
    tgt, dim, keep = build_target(target, arm, threads)
    # Prime once at the zero vector (WP47 amendment A3): lazy JIT compilation
    # counts as construction, not sampling. A pure function: draws unchanged.
    call_once(tgt, np.zeros(dim))
    construct = time.perf_counter() - t0
    t1 = time.perf_counter()
    res = owalnuts.sample(tgt, dim, chains=SAMPLER["chains"], warmup=SAMPLER["warmup"], draws=SAMPLER["draws"],
                          seed=seed, threads=threads)
    wall = time.perf_counter() - t1
    # Untimed, after the run: the start-selection evaluations of the default
    # best-of-16 rule (not in target_calls), and the starts themselves.
    det = owalnuts.best_of_starts(tgt, dim, chains=SAMPLER["chains"], seed=seed, return_details=True)
    start_evals = int(sum(det["evaluations"]))
    chains = res.chains
    div = sum(int(c["work_retained"]["divergences"]) for c in chains)
    calls = int(res.target_calls)
    rec = {
        "target": target, "arm": arm, "threads": threads, "seed": seed, "status": "ok",
        "construct_seconds": construct, "wall_seconds": wall, "wall_seconds_rust": res.wall_seconds,
        "target_calls": calls, "start_selection_calls": start_evals, "gradients_total": calls + start_evals,
        "start_chosen": [int(x) for x in det["chosen"]], "start_evaluations": [int(x) for x in det["evaluations"]],
        "starts_sha256": sha(np.asarray(det["starts"])),
        "attached_seconds": res.target_attached_seconds,
        "attached_fraction": res.target_attached_seconds / res.wall_seconds if res.wall_seconds else None,
        "wall_per_call_us": 1e6 * res.wall_seconds / calls,
        "gradients_warmup": sum(int(c["work_discarded"]["target_calls_total"]) for c in chains),
        "gradients_sampling": sum(int(c["work_retained"]["target_calls_total"]) for c in chains),
        "max_depth_stops": sum(int(c["work_retained"]["maximum_depth_stops"]) for c in chains),
        "final_step_size": [float(c["metadata"]["final_step_size"]) for c in chains],
        "health": res.health(), "samples_sha256": sha(res.samples),
        **summarize(target, res.samples, div),
    }
    rec["ess_per_second"] = rec["min_bulk_ess"] / wall
    rec["ess_per_gradient"] = rec["min_bulk_ess"] / rec["gradients_total"]
    save_draws(cell_name(target, arm, threads, seed), res.samples)
    return rec


def run_nutpie_cell(target: str, arm: str, threads: int, seed: int) -> dict:
    import nutpie
    import callpath_targets as T

    t0 = time.perf_counter()
    compiled = nutpie.compile_pymc_model(T.pymc_model(target))
    construct = time.perf_counter() - t0
    t1 = time.perf_counter()
    idata = nutpie.sample(compiled, draws=SAMPLER["draws"], tune=SAMPLER["warmup"], chains=SAMPLER["chains"],
                          cores=threads, seed=seed, progress_bar=False, save_warmup=True)
    wall = time.perf_counter() - t1
    samples = T.unconstrained_from_posterior(target, idata.posterior)
    st, wst = idata.sample_stats, idata.warmup_sample_stats
    g_samp = int(st["n_steps"].values.sum())
    g_warm = int(wst["n_steps"].values.sum())
    div = int(st["diverging"].values.sum())
    rec = {
        "target": target, "arm": arm, "threads": threads, "seed": seed, "status": "ok",
        "construct_seconds": construct, "wall_seconds": wall,
        "gradients_total": g_samp + g_warm, "gradients_sampling": g_samp, "gradients_warmup": g_warm,
        "gradients_kind": "leapfrog n_steps (warmup + draws)",
        "wall_per_call_us": 1e6 * wall / (g_samp + g_warm),
        "mean_tree_depth": float(np.asarray(st["depth"].values).mean()),
        "final_step_size": [float(x) for x in np.asarray(st["step_size"].values)[:, -1]],
        "max_depth_stops": int(np.asarray(st["maxdepth_reached"].values).sum()) if "maxdepth_reached" in st else None,
        "samples_sha256": sha(samples),
        **summarize(target, samples, div),
    }
    rec["ess_per_second"] = rec["min_bulk_ess"] / wall
    rec["ess_per_gradient"] = rec["min_bulk_ess"] / rec["gradients_total"]
    save_draws(cell_name(target, arm, threads, seed), samples)
    return rec


def run_rust_cell(target: str, threads: int, seed: int) -> dict:
    tmp = ART / "rust-raw"
    tmp.mkdir(parents=True, exist_ok=True)
    name = cell_name(target, "rust", threads, seed)
    out, binf = tmp / f"{name}.json", tmp / f"{name}.bin"
    for p in (out, binf):
        if p.exists():
            p.unlink()
    cmd = [str(RUST_BIN), "cell", target, str(HIER_DATA) if target == "hier" else "-", str(seed), str(threads),
           str(out), str(binf)]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return {"target": target, "arm": "rust", "threads": threads, "seed": seed, "status": "timeout"}
    if cp.returncode != 0 or not out.exists():
        return {"target": target, "arm": "rust", "threads": threads, "seed": seed, "status": "error",
                "error": cp.stderr[-3000:]}
    raw = json.loads(out.read_text(encoding="utf-8"))
    dim = raw["dimension"]
    samples = np.fromfile(binf, dtype="<f8").reshape(SAMPLER["chains"], SAMPLER["draws"], dim)
    binf.unlink()
    cd = raw["chains_data"]
    div = sum(c["work_retained"]["divergences"] for c in cd)
    calls = raw["counted_calls_sampler"]
    rec = {
        "target": target, "arm": "rust", "threads": threads, "seed": seed, "status": "ok",
        "wall_seconds": raw["wall_seconds_with_starts"], "wall_seconds_rust": raw["wall_seconds"],
        "target_calls": calls, "kernel_total_target_calls": raw["kernel_total_target_calls"],
        "start_selection_calls": raw["counted_calls_start_selection"],
        "gradients_total": raw["counted_calls_total"],
        "start_evaluations": raw["init"]["evaluations_per_chain"],
        "wall_per_call_us": 1e6 * raw["wall_seconds"] / calls,
        "gradients_warmup": sum(c["work_discarded"]["target_calls_total"] for c in cd),
        "gradients_sampling": sum(c["work_retained"]["target_calls_total"] for c in cd),
        "max_depth_stops": sum(c["work_retained"]["maximum_depth_stops"] for c in cd),
        "final_step_size": [c["final_step_size"] for c in cd],
        "algorithm_revision": raw["algorithm_revision"],
        "samples_sha256": sha(samples),
        **summarize(target, samples, div),
    }
    rec["ess_per_second"] = rec["min_bulk_ess"] / rec["wall_seconds"]
    rec["ess_per_gradient"] = rec["min_bulk_ess"] / rec["gradients_total"]
    save_draws(name, samples)
    return rec


def package_versions() -> dict:
    out = {"python": sys.version.split()[0], "executable": sys.executable}
    for m in ("numpy", "numba", "llvmlite", "jax", "jaxlib", "pymc", "pytensor", "nutpie", "arviz", "owalnuts"):
        mod = sys.modules.get(m)
        if mod is not None:
            out[m] = getattr(mod, "__version__", "?")
    try:
        import owalnuts
        out["owalnuts_file"] = owalnuts.__file__
        out["algorithm_revision"] = owalnuts.ALGORITHM_REVISION
    except Exception:  # noqa: BLE001
        pass
    out["affinity"] = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None
    return out


# --------------------------------------------------------------------------- plan / orchestration


def plan() -> list[tuple]:
    """Frozen order: micro cells first (targets outer, paths rotated per
    target), then sampler cells: seeds outer, targets, then the (arm x
    threads) list rotated by (3 * seed index + target index)."""
    steps: list[tuple] = []
    for ti, target in enumerate(TARGETS):
        paths = MICRO_PATHS[ti:] + MICRO_PATHS[:ti]
        for path in paths:
            steps.append(("micro", target, path))
    for si, seed in enumerate(SEEDS):
        for ti, target in enumerate(TARGETS):
            arms = [(a, t) for a in OW_ARMS + NUTPIE_ARMS for t in THREADS]
            r = (si * 3 + ti) % len(arms)
            arms = arms[r:] + arms[:r]
            for arm, t in arms:
                steps.append(("cell", target, arm, str(t), str(seed)))
    return steps


def out_path(step: tuple) -> Path:
    if step[0] == "micro":
        return ART / "micro" / f"{step[1]}-{step[2]}.json"
    _, target, arm, t, seed = step
    return ART / "cells" / f"{cell_name(target, arm, int(t), int(seed))}.json"


def child_env() -> dict:
    return dict(os.environ, JAX_PLATFORMS="cpu", PYTHONIOENCODING="utf-8")


def run_child(step: tuple, out: Path) -> str | None:
    p = subprocess.Popen([sys.executable, "-I", str(Path(__file__)), *step], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, env=child_env(), start_new_session=True)
    try:
        _, stderr = p.communicate(timeout=TIMEOUT)
        if p.returncode == 0 and out.exists():
            return None
        return f"exit {p.returncode}: {stderr[-3000:]}"
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        if out.exists():
            out.unlink()
        return f"timeout {TIMEOUT}s"


def describe(rec: dict) -> str:
    if rec.get("status") != "ok":
        return f"{rec.get('status')} {str(rec.get('error', ''))[:200]}"
    if "components" in rec:
        c = rec["components"]
        k = next(iter(c))
        return f"ok {k} {c[k]['median_us']:.2f}us"
    return (f"ok wall {rec['wall_seconds']:.2f}s us/call {rec['wall_per_call_us']:.2f} grads {rec['gradients_total']} "
            f"minESS {rec['min_bulk_ess']:.0f} ESS/s {rec['ess_per_second']:.0f} rhat {rec['max_rhat']:.4f} "
            f"div {rec['divergences']} pass {rec['passed']}")


def run_all() -> None:
    steps = plan()
    log(f"{len(steps)} steps")
    meta = ART / "measured_on.json"
    if not meta.exists():
        def sh(cmd):
            try:
                return subprocess.run(cmd, capture_output=True, text=True, shell=True).stdout
            except Exception as e:  # noqa: BLE001
                return str(e)
        write_json(meta, {"platform": platform.platform(), "processor": platform.processor(),
                          "cpu_count": os.cpu_count(), "affinity": sorted(os.sched_getaffinity(0)),
                          "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                          "lscpu": sh("lscpu"), "uname": sh("uname -a"),
                          "git_head": sh(f"git -C {HERE} rev-parse HEAD").strip(),
                          "git_status": sh(f"git -C {HERE} status --short").strip(),
                          "env": {k: os.environ.get(k) for k in ("RAYON_NUM_THREADS", "OMP_NUM_THREADS", "JAX_PLATFORMS",
                                                                 "PYTENSOR_FLAGS", "NUMBA_CACHE_DIR", "TMPDIR")},
                          "rust_bin": str(RUST_BIN),
                          "rust_bin_sha256": hashlib.sha256(RUST_BIN.read_bytes()).hexdigest() if RUST_BIN.exists() else None,
                          "note": "pinned to lane 4 (cores 12-15) of a shared 16-core box with three other lanes active: "
                                  "walls are pinned, co-tenanted (shared L3 and memory bandwidth)"})
    for i, step in enumerate(steps):
        out = out_path(step)
        if out.exists():
            continue
        t = time.perf_counter()
        if step[0] == "micro" and step[2] == "rust":
            try:
                rec = run_micro_rust(step[1], out)
            except Exception as e:  # noqa: BLE001
                rec = {"target": step[1], "path": "rust", "status": "error", "error": f"{type(e).__name__}: {e}"}
            write_json(out, rec)
        elif step[0] == "cell" and step[2] == "rust":
            try:
                rec = run_rust_cell(step[1], int(step[3]), int(step[4]))
            except Exception as e:  # noqa: BLE001
                rec = {"target": step[1], "arm": "rust", "threads": int(step[3]), "seed": int(step[4]),
                       "status": "error", "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()}
            write_json(out, rec)
        else:
            err = run_child(step, out)
            if err:
                write_json(out, {"step": list(step), "status": "process_error", "error": err})
        rec = json.loads(out.read_text(encoding="utf-8"))
        log(f"{i + 1}/{len(steps)} {' '.join(step[1:])} {describe(rec)} ({time.perf_counter() - t:.0f}s)")
    log("all steps done")


def child(argv: list[str]) -> None:
    kind = argv[0]
    if kind == "micro":
        step = ("micro", argv[1], argv[2])
        out = out_path(step)
        try:
            rec = run_micro(argv[1], argv[2])
        except Exception as e:  # noqa: BLE001
            rec = {"target": argv[1], "path": argv[2], "status": "error", "error": f"{type(e).__name__}: {e}",
                   "traceback": traceback.format_exc()}
    else:
        target, arm, threads, seed = argv[1], argv[2], int(argv[3]), int(argv[4])
        out = out_path(("cell", target, arm, str(threads), str(seed)))
        try:
            if arm in NUTPIE_ARMS:
                rec = run_nutpie_cell(target, arm, threads, seed)
            else:
                rec = run_owalnuts_cell(target, arm, threads, seed)
            rec["packages"] = package_versions()
        except Exception as e:  # noqa: BLE001
            rec = {"target": target, "arm": arm, "threads": threads, "seed": seed, "status": "error",
                   "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()}
    write_json(out, rec)


# --------------------------------------------------------------------------- setup checks (not evidence)


def setupcheck() -> None:
    """Value/gradient agreement of every path at 5 points per model (setup, not evidence)."""
    import callpath_targets as T

    report = {}
    for target in TARGETS:
        dim = T.DIM[target]
        rng = np.random.default_rng(1)
        pts = [rng.uniform(-1.0, 1.0, dim) for _ in range(5)]
        ref = [T.numpy_target(target)(q) for q in pts]
        tmp = ART.parent / "setup-points.json"
        tmp.write_text(json.dumps([q.tolist() for q in pts]), encoding="utf-8")
        rout = ART.parent / "setup-rust.json"
        subprocess.run([str(RUST_BIN), "eval", target, str(HIER_DATA) if target == "hier" else "-", str(tmp),
                        str(rout)], check=True)
        rust = json.loads(rout.read_text(encoding="utf-8"))
        tmp.unlink()
        rout.unlink()
        rows = {"rust": [(r["logp"], np.asarray(r["grad"])) for r in rust]}
        for arm in ("py-njit", "cfunc", "jax", "pymc", "pymc-gilfree"):
            tgt, _dim, _keep = build_target(target, arm, 1)
            rows[arm] = [tuple(np.copy(x) if isinstance(x, np.ndarray) else x for x in call_once(tgt, q)) for q in pts]
        out = {}
        for arm, vals in rows.items():
            dv = [float(v[0]) - float(r[0]) for v, r in zip(vals, ref)]
            dg = max(float(np.max(np.abs(np.asarray(v[1]) - r[1]))) for v, r in zip(vals, ref))
            out[arm] = {"value_minus_numpy": dv, "max_abs_grad_diff": dg}
        report[target] = out
        log(f"{target}: " + ", ".join(f"{a} dg={o['max_abs_grad_diff']:.1e}" for a, o in out.items()))
    print(json.dumps(report, indent=1, default=float))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "run":
        run_all()
    elif cmd in ("micro", "cell"):
        child(sys.argv[1:])
    elif cmd == "setupcheck":
        setupcheck()
    else:
        raise SystemExit(__doc__)
