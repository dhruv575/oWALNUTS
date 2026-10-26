#!/usr/bin/env python3
"""pymc_gil_free_determinism_v1 driver (WP86; PREREGISTRATION.md, protocol.json).

    python run_determinism.py run                              # every process, frozen order, skips written records
    python run_determinism.py proc <arm> <model> <index>       # child (one fresh process)

Run pinned (taskset -c 4-7) with the lane env.sh sourced. One child process per record,
strictly sequential. Before every cold process the parent deletes the whole numba cache
directory (NUMBA_CACHE_DIR) and PyTensor's base compiledir (which holds PyTensor's numba
cache); a warm process runs on whatever the preceding process of the same (arm, model) left.
Nothing is rerun; a child that dies or times out is a record with its status.
"""
from __future__ import annotations

import ctypes
import functools
import hashlib
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
P = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
ART = Path(os.environ.get("WP86_ART", str(HERE / "artifacts")))
S = P["sampler"]
LANE = Path(os.environ.get("WP86_LANE", "~/lanes/pymc_gil_free_determinism_v1")).expanduser()
NUMBA_CACHE = Path(os.environ.get("NUMBA_CACHE_DIR", str(LANE / "cache" / "numba")))
PYTENSOR_BASE = LANE / "cache" / "pytensor"
PYTENSOR_FAST = {"arcp", "contract", "afn", "reassoc", "nsz"}  # PyTensor 2.38's numba fastmath set


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def write_json(p: Path, o):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(o, indent=1, default=float), encoding="utf-8")


def sha(a):
    return hashlib.sha256(np.ascontiguousarray(a, dtype=np.float64).tobytes()).hexdigest()


def ulp_distance(a: np.ndarray, b: np.ndarray) -> int:
    """Largest distance in units in the last place between equal-sign finite doubles (inf if signs differ)."""
    a = np.ascontiguousarray(a, dtype=np.float64).ravel()
    b = np.ascontiguousarray(b, dtype=np.float64).ravel()
    ia, ib = a.view(np.int64).astype(object), b.view(np.int64).astype(object)
    worst = 0
    for x, y, u, v in zip(a, b, ia, ib):
        if x == y or (np.isnan(x) and np.isnan(y)):
            continue
        if np.sign(x) != np.sign(y) or not (np.isfinite(x) and np.isfinite(y)):
            return -1  # sentinel: not comparable in ulps
        worst = max(worst, abs(int(u) - int(v)))
    return worst


# --------------------------------------------------------------------------- the child


def arm_env(arm: str) -> dict:
    """Environment of a child process for an arm (PyTensor flags only; cfunc flags are patched in the child)."""
    flags = [f"base_compiledir={PYTENSOR_BASE}"] + P["arms"][arm].get("pytensor_flags", [])
    env = dict(os.environ)
    env["PYTENSOR_FLAGS"] = ",".join(flags)
    env["NUMBA_CACHE_DIR"] = str(NUMBA_CACHE)
    return env


def patch_cfunc(arm: str) -> None:
    """Arms that change only the cfunc wrapper's numba flags: wrap numba.cfunc before owalnuts uses it."""
    import numba

    extra = dict(P["arms"][arm].get("cfunc_kwargs", {}))
    if extra.get("fastmath") == "pytensor":
        extra["fastmath"] = set(PYTENSOR_FAST)
    if not extra:
        return
    original = numba.cfunc
    numba.cfunc = functools.partial(original, **extra)


def cache_files(p: Path) -> int:
    return sum(1 for q in p.rglob("*") if q.is_file()) if p.exists() else 0


def ir_evidence(raw) -> dict:
    out = {}
    try:
        ir = raw.inspect_llvm()
        out.update(llvm_chars=len(ir), llvm_sha256=hashlib.sha256(ir.encode()).hexdigest(),
                   llvm_fmuladd=ir.count("llvm.fmuladd"), llvm_fma=ir.count("llvm.fma."),
                   llvm_define=ir.count("\ndefine "), llvm_declare=ir.count("\ndeclare "),
                   llvm_call=ir.count(" call "), llvm_fast_flags=ir.count(" fast ") + ir.count(" contract "))
    except Exception as e:  # noqa: BLE001
        out["llvm_error"] = f"{type(e).__name__}: {e}"
    try:
        asm = raw.inspect_asm()
        out.update(asm_chars=len(asm), asm_sha256=hashlib.sha256(asm.encode()).hexdigest(),
                   asm_vfmadd=asm.count("vfmadd") + asm.count("vfnmadd") + asm.count("vfmsub"),
                   asm_call=asm.count("\tcall"))
    except Exception as e:  # noqa: BLE001
        out["asm_error"] = f"{type(e).__name__}: {e}"
    return out


def dispatcher_stats(inner) -> dict:
    st = getattr(inner, "stats", None)
    if st is None:
        return {}
    return {"cache_hits": {str(k): int(v) for k, v in dict(getattr(st, "cache_hits", {})).items()},
            "cache_misses": {str(k): int(v) for k, v in dict(getattr(st, "cache_misses", {})).items()}}


def gradient_probe(target, fn, q0: np.ndarray) -> dict:
    """The cfunc (through ctypes) and the compiled PyTensor function it wraps, at fixed points."""
    spec = P["gradient_probe"]
    rng = np.random.default_rng(spec["rng_seed"])
    pts = q0[None, :] + spec["scale"] * rng.standard_normal((spec["points"], q0.size))
    proto = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_ssize_t, ctypes.POINTER(ctypes.c_double),
                             ctypes.POINTER(ctypes.c_double), ctypes.c_void_p)
    caller = proto(target.address)
    cf_v, cf_g, fn_v, fn_g = [], [], [], []
    for x in pts:
        x = np.ascontiguousarray(x, dtype=np.float64)
        g = np.zeros(x.size)
        v = caller(x.size, x.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                   g.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), None)
        cf_v.append(v)
        cf_g.append(g)
        lv, lg = fn(x.copy())
        fn_v.append(float(np.asarray(lv).sum()))
        fn_g.append(np.asarray(lg, dtype=np.float64).copy())
    cf_v, fn_v = np.asarray(cf_v), np.asarray(fn_v)
    cf_g, fn_g = np.asarray(cf_g), np.asarray(fn_g)
    finite = np.isfinite(fn_v) & np.isfinite(fn_g).all(axis=1)
    same = [(cf_v[i] == fn_v[i] or (np.isnan(cf_v[i]) and np.isnan(fn_v[i]))) and np.array_equal(cf_g[i], fn_g[i], equal_nan=True)
            for i in range(len(pts))]
    fin = finite & np.isfinite(cf_v)
    return {"points": len(pts), "finite_points": int(finite.sum()),
            "points_bit_different": int(sum(not s for s in same)),
            "max_abs_diff_logp": float(np.max(np.abs(cf_v[fin] - fn_v[fin]))) if fin.any() else None,
            "max_abs_diff_grad": float(np.max(np.abs(cf_g[fin] - fn_g[fin]))) if fin.any() else None,
            "max_ulp_logp": ulp_distance(cf_v[fin], fn_v[fin]) if fin.any() else None,
            "max_ulp_grad": ulp_distance(cf_g[fin], fn_g[fin]) if fin.any() else None,
            "within_1e-15_relative": bool(np.all(np.abs(cf_g[fin] - fn_g[fin]) <= 1e-15 * np.maximum(1.0, np.abs(fn_g[fin]))))
            if fin.any() else None,
            "cfunc_sha256": sha(np.concatenate([cf_v, cf_g.ravel()])),
            "fn_sha256": sha(np.concatenate([fn_v, fn_g.ravel()]))}


def sample_hash(target, dim, threads) -> dict:
    import owalnuts
    t = time.perf_counter()
    res = owalnuts.sample(target, dim, chains=S["chains"], warmup=S["warmup"], draws=S["draws"], seed=P["seed"],
                          threads=threads)
    return {"sha256": sha(res.samples), "wall_seconds": time.perf_counter() - t, "target_calls": int(res.target_calls),
            "wall_per_call_us": 1e6 * res.wall_seconds / res.target_calls,
            "divergences": sum(int(c["work_retained"]["divergences"]) for c in res.chains)}


def run_proc(arm: str, model_name: str, index: int) -> dict:
    cache_state = "cold" if index % 2 == 0 else "warm"
    rec = {"arm": arm, "model": model_name, "index": index, "cache": cache_state,
           "numba_cache_files_at_start": cache_files(NUMBA_CACHE),
           "pytensor_cache_files_at_start": cache_files(PYTENSOR_BASE),
           "pytensor_flags": os.environ.get("PYTENSOR_FLAGS"), "pid": os.getpid()}
    patch_cfunc(arm)
    import owalnuts
    import models as M
    import pytensor
    rec["pytensor_numba_fastmath"] = bool(pytensor.config.numba__fastmath)
    rec["pytensor_numba_cache"] = bool(pytensor.config.numba__cache)
    model = M.build(model_name)
    t0 = time.perf_counter()
    target, dim, q0, _names, _unravel = owalnuts.from_pymc(model, gil_free=True)
    rec["gil_free_construct_seconds"] = time.perf_counter() - t0
    raw, inner, fn, _frozen = target.keep_alive
    rec["dim"] = int(dim)
    rec["inner_dispatcher"] = dispatcher_stats(inner)
    rec["cfunc_ir"] = ir_evidence(raw)
    rec["gradient_probe"] = gradient_probe(target, fn, np.asarray(q0, dtype=np.float64))

    def same_fn(q):  # the compiled PyTensor function gil_free wraps, as a Python callable (from_pymc's code)
        logp, grad = fn(np.asarray(q, dtype=np.float64))
        return float(logp), np.asarray(grad, dtype=np.float64)

    rec["gilfree_t1"] = sample_hash(target, dim, 1)
    rec["callable_same_fn_t1"] = sample_hash(same_fn, dim, 1)
    rec["identical_same_fn"] = rec["gilfree_t1"]["sha256"] == rec["callable_same_fn_t1"]["sha256"]
    if index in P["arms"][arm].get("thread_indices", []) or P["arms"][arm].get("threads4_every_process"):
        rec["gilfree_t4"] = sample_hash(target, dim, 4)
        rec["identical_t1_t4"] = rec["gilfree_t1"]["sha256"] == rec["gilfree_t4"]["sha256"]
    if P["arms"][arm].get("wp83_control"):
        t0 = time.perf_counter()
        ctl, cdim, _q, _n, _u = owalnuts.from_pymc(M.build(model_name), mode="NUMBA")
        rec["wp83_control_construct_seconds"] = time.perf_counter() - t0
        rec["wp83_control_t1"] = sample_hash(ctl, cdim, 1)
        rec["identical_wp83_control"] = rec["gilfree_t1"]["sha256"] == rec["wp83_control_t1"]["sha256"]
    rec["status"] = "ok"
    return rec


# --------------------------------------------------------------------------- the parent


def plan():
    steps = []
    for arm in P["order"]["arms"]:
        spec = P["arms"][arm]
        for model in spec["models"]:
            for index in range(spec["processes"]):
                steps.append((arm, model, index))
    return steps


def out_path(arm, model, index):
    return ART / "procs" / arm / f"{model}-{int(index):02d}.json"


def purge_caches():
    for p in (NUMBA_CACHE, PYTENSOR_BASE):
        if p.exists():
            shutil.rmtree(p)


def sh(c):
    return subprocess.run(c, shell=True, capture_output=True, text=True).stdout.strip()


def run_all():
    steps = plan()
    meta = ART / "measured_on.json"
    if not meta.exists():
        write_json(meta, {"platform": platform.platform(), "affinity": sorted(os.sched_getaffinity(0)),
                          "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                          "git_head": sh(f"git -C {HERE} rev-parse HEAD"),
                          "git_status": sh(f"git -C {HERE} status --short"),
                          "pip_freeze": sh(f"{sys.executable} -m pip freeze"),
                          "note": "lane 2 (cores 4-7) of a shared box, other lanes active: walls pinned, co-tenanted"})
    log(f"{len(steps)} processes")
    for i, (arm, model, index) in enumerate(steps):
        out = out_path(arm, model, index)
        if out.exists():
            continue
        if index % 2 == 0:
            purge_caches()
        t = time.perf_counter()
        p = subprocess.Popen([sys.executable, "-I", str(Path(__file__)), "proc", arm, model, str(index)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
                             env=arm_env(arm))
        try:
            _, err = p.communicate(timeout=P["process_timeout_seconds"])
            if p.returncode != 0 or not out.exists():
                write_json(out, {"arm": arm, "model": model, "index": index, "cache": "cold" if index % 2 == 0 else "warm",
                                 "status": "process_fault", "exit_code": p.returncode, "stderr": err[-3000:]})
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.communicate()
            write_json(out, {"arm": arm, "model": model, "index": index, "status": "timeout"})
        r = json.loads(out.read_text(encoding="utf-8"))
        if r.get("status") == "ok":
            g = r["gradient_probe"]
            extra = (f"{r['cache']} gf {r['gilfree_t1']['sha256'][:10]} fn {r['callable_same_fn_t1']['sha256'][:10]} "
                     f"same {r['identical_same_fn']} t4 {r.get('identical_t1_t4', '-')} gradbits {g['points_bit_different']} "
                     f"ulp {g['max_ulp_grad']} hits {r['inner_dispatcher'].get('cache_hits')}")
        else:
            extra = str(r.get("error", r.get("stderr", "")))[-300:]
        log(f"{i + 1}/{len(steps)} {arm} {model} {index} {r.get('status')} {extra} ({time.perf_counter() - t:.0f}s)")
    log("all processes done")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "run":
        run_all()
    elif cmd == "proc":
        arm, model, index = sys.argv[2], sys.argv[3], int(sys.argv[4])
        try:
            rec = run_proc(arm, model, index)
        except Exception as e:  # noqa: BLE001 - a failure is a record
            rec = {"arm": arm, "model": model, "index": index, "status": "error",
                   "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[-3000:]}
        rec["packages"] = {m: getattr(sys.modules[m], "__version__", "?") for m in ("numpy", "numba", "pymc", "pytensor", "owalnuts", "llvmlite") if m in sys.modules}
        write_json(out_path(arm, model, index), rec)
    else:
        raise SystemExit(__doc__)
