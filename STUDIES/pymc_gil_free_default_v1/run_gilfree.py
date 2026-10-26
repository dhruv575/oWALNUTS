#!/usr/bin/env python3
"""pymc_gil_free_default_v1 driver (WP83; PREREGISTRATION.md, protocol.json).

    python run_gilfree.py run                                   # every cell, frozen order, skips written cells
    python run_gilfree.py cell <model> <arm> <threads> <seed>   # child
    python run_gilfree.py robust <model> <rep>                  # child

Run pinned (taskset -c 12-15) with the lane env.sh sourced. One child process
per cell, strictly sequential. Failures are cells with status != "ok"; a child
that dies is recorded with its exit code (a fault). Nothing is rerun.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
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
ART = Path(os.environ.get("WP83_ART", str(HERE / "artifacts")))
S = P["sampler"]
G = P["gates"]


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def write_json(p: Path, o):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(o, indent=1, default=float), encoding="utf-8")


def sha(a):
    return hashlib.sha256(np.ascontiguousarray(a, dtype=np.float64).tobytes()).hexdigest()


def target_for(model, arm, threads):
    import owalnuts
    if arm == "default":
        return owalnuts.from_pymc(model, thread_safe=threads > 1)
    if arm == "numba":
        return owalnuts.from_pymc(model, mode="NUMBA", thread_safe=threads > 1)
    if arm == "gilfree":
        return owalnuts.from_pymc(model, gil_free=True)
    raise ValueError(arm)


def summarize(name, samples, div):
    import owalnuts
    import callpath_targets as T
    if name == "eight":
        f, names = T.functionals("eight", samples)
    else:
        f, names = samples, [f"q{i}" for i in range(samples.shape[-1])]
    rows = owalnuts.summary(np.ascontiguousarray(f), names)
    out = {"min_bulk_ess": min(r["ess_bulk"] for r in rows), "min_tail_ess": min(r["ess_tail"] for r in rows),
           "max_rhat": max(r["rhat"] for r in rows), "divergences": int(div),
           "mean": [r["mean"] for r in rows], "mcse_mean": [r["mcse_mean"] for r in rows], "names": names,
           "finite_draws": bool(np.isfinite(samples).all())}
    out["passed"] = bool(out["max_rhat"] <= G["max_rank_rhat"] and out["min_bulk_ess"] >= G["min_bulk_ess"]
                         and out["min_tail_ess"] >= G["min_tail_ess"] and div == 0 and out["finite_draws"])
    return out


def run_cell(name, arm, threads, seed, keep_draws=True):
    import owalnuts
    import models as M
    rec = {"model": name, "arm": arm, "threads": threads, "seed": seed}
    t0 = time.perf_counter()
    model = M.build(name)
    try:
        tgt, dim, _q0, _names, _unravel = target_for(model, arm, threads)
    except Exception as e:  # noqa: BLE001 - a construction failure is a result
        rec.update(status="construct_error", error=f"{type(e).__name__}: {e}",
                   construct_seconds=time.perf_counter() - t0)
        return rec
    rec["construct_seconds"] = time.perf_counter() - t0
    rec["dim"] = int(dim)
    rec["target_type"] = type(tgt).__name__
    rec["target_callable"] = callable(tgt)
    t1 = time.perf_counter()
    try:
        res = owalnuts.sample(tgt, dim, chains=S["chains"], warmup=S["warmup"], draws=S["draws"], seed=seed,
                              threads=threads)
    except Exception as e:  # noqa: BLE001
        rec.update(status="sample_error", error=f"{type(e).__name__}: {e}", traceback=traceback.format_exc())
        return rec
    wall = time.perf_counter() - t1
    div = sum(int(c["work_retained"]["divergences"]) for c in res.chains)
    rec.update(status="ok", wall_seconds=wall, wall_seconds_rust=res.wall_seconds, target_calls=int(res.target_calls),
               wall_per_call_us=1e6 * res.wall_seconds / res.target_calls, samples_sha256=sha(res.samples),
               **summarize(name, res.samples, div))
    rec["ess_per_second"] = rec["min_bulk_ess"] / wall
    if keep_draws:
        d = ART / "draws"
        d.mkdir(parents=True, exist_ok=True)
        np.save(d / f"{name}-{arm}-t{threads}-{seed}.npy", res.samples)
    return rec


def versions():
    out = {"python": sys.version.split()[0]}
    for m in ("numpy", "numba", "pymc", "pytensor", "owalnuts"):
        if m in sys.modules:
            out[m] = getattr(sys.modules[m], "__version__", "?")
    out["affinity"] = sorted(os.sched_getaffinity(0))
    return out


def plan():
    steps = []
    arms = [tuple(x) for x in P["breadth_arms"]]
    for si, seed in enumerate(P["seeds"]):
        for mi, m in enumerate(P["models"]):
            r = (si + mi) % len(arms)
            for a, t in arms[r:] + arms[:r]:
                steps.append(("cell", m, a, str(t), str(seed)))
    for m in P["robustness"]["models"]:
        for rep in range(1, P["robustness"]["reps"] + 1):
            steps.append(("robust", m, str(rep)))
    return steps


def out_path(step):
    if step[0] == "cell":
        return ART / "cells" / f"{step[1]}-{step[2]}-t{step[3]}-{step[4]}.json"
    return ART / "robust" / f"{step[1]}-{int(step[2]):03d}.json"


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
                          "note": "lane 4 (cores 12-15) of a shared box, other lanes active: walls pinned, co-tenanted"})
    log(f"{len(steps)} steps")
    for i, step in enumerate(steps):
        out = out_path(step)
        if out.exists():
            continue
        t = time.perf_counter()
        p = subprocess.Popen([sys.executable, "-I", str(Path(__file__)), *step], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            _, err = p.communicate(timeout=P["cell_timeout_seconds"])
            if p.returncode != 0 or not out.exists():
                write_json(out, {"step": list(step), "status": "process_fault", "exit_code": p.returncode,
                                 "stderr": err[-3000:]})
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.communicate()
            write_json(out, {"step": list(step), "status": "timeout"})
        r = json.loads(out.read_text(encoding="utf-8"))
        if r.get("status") == "ok":
            extra = (f"us/grad {r['wall_per_call_us']:.2f} minESS {r['min_bulk_ess']:.0f} rhat {r['max_rhat']:.4f} "
                     f"div {r['divergences']} pass {r['passed']} sha {r['samples_sha256'][:10]}")
        else:
            extra = str(r.get("error", r.get("stderr", "")))[:200]
        log(f"{i + 1}/{len(steps)} {' '.join(step[1:])} {r.get('status')} {extra} ({time.perf_counter() - t:.0f}s)")
    log("all steps done")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "run":
        run_all()
    elif cmd == "cell":
        step = tuple(sys.argv[1:])
        rec = run_cell(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]))
        rec["packages"] = versions()
        write_json(out_path(step), rec)
    elif cmd == "robust":
        step = tuple(sys.argv[1:])
        rp = P["robustness"]
        rec = run_cell(sys.argv[2], "gilfree", rp["threads"], rp["seed"], keep_draws=False)
        rec["rep"] = int(sys.argv[3])
        for k in ("mean", "mcse_mean", "names"):
            rec.pop(k, None)
        write_json(out_path(step), rec)
    else:
        raise SystemExit(__doc__)
