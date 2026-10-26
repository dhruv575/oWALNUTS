#!/usr/bin/env python3
"""WP65 part (b) driver: fault rate per BridgeStan dispatch path over >= 500 child processes each.

    python run_stress.py probe     # manipulation check (probe seed, no sampling); refuses `run` unless it passed
    python run_stress.py run       # the frozen matrix, once; never relaunches a launched child
    python run_stress.py analyze   # artifacts/stress/summary.json + result.md

Seeds 65201001..65201500 are shared by the three paths (paired). Child i runs the three paths in
the order rotated by i mod 3, strictly one process at a time. Before each child the parent
creates an exclusive launch marker; a marker without a process record is reported as an
interruption, never relaunched. Run under `taskset -c 4-7`; children inherit it.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import signal
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
ST = PROTOCOL["part_b_fault_rate"]
ART = HERE / "artifacts" / "stress"
CHILD = HERE / "target" / "release" / "stress_child"
MODELS = HERE / "models"
ARMS = list(ST["arms"])
SEEDS = list(range(ST["seeds"][0], ST["seeds"][1] + 1))
EXPECTED_HEARTBEATS = ["process-start", "load-before", "load-after", "initialization-before", "initialization-after",
                       "sampling-before", "sampling-after", "drop-before", "drop-after", "result_write-before",
                       "result_write-after", "process-complete"]
STDERR_MARKERS = ST["stderr_fault_markers"]


def model_paths(arm: str) -> tuple[Path, Path]:
    spec = ST["arms"][arm]
    m = ST["model"].replace("-", "__")
    return MODELS / spec["build"] / f"{m}_model.so", MODELS / f"{m}.data.json"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def probe() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    out = {}
    for arm in ARMS:
        so, data = model_paths(arm)
        cp = subprocess.run([str(CHILD), "probe", arm, str(so), str(data)], capture_output=True, text=True, timeout=120)
        try:
            out[arm] = {"returncode": cp.returncode, **json.loads(cp.stdout)}
        except json.JSONDecodeError:
            out[arm] = {"returncode": cp.returncode, "stdout": cp.stdout[-2000:], "stderr": cp.stderr[-2000:],
                        "execution_as_expected": False}
        out[arm]["library_sha256"] = hashlib.sha256(so.read_bytes()).hexdigest()
    out["passed"] = all(out[a].get("returncode") == 0 and out[a].get("execution_as_expected") for a in ARMS)
    (ART / "probe.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=1))


def classify(rec: dict) -> list[str]:
    faults = []
    rc = rec["returncode"]
    if rc == "timeout":
        faults.append("timeout")
    elif isinstance(rc, int) and rc < 0:
        faults.append(f"signal_{rec.get('signal_name') or -rc}")
    elif rc != 0:
        faults.append("nonzero_exit")
    out = rec.get("output")
    if out is None:
        faults.append("missing_or_invalid_output")
    else:
        if out.get("status") != "ok":
            faults.append("status_not_ok")
        if not out.get("execution_as_expected"):
            faults.append("execution_mismatch")
        if not out.get("all_retained_values_finite"):
            faults.append("nonfinite_draws")
        if out.get("draws_observed") != 4 * 1000:
            faults.append("draw_count")
    if rec.get("heartbeats") != EXPECTED_HEARTBEATS:
        faults.append("heartbeats_incomplete")
    low = rec.get("stderr_tail", "").lower()
    hits = [m for m in STDERR_MARKERS if m.lower() in low]
    if hits:
        faults.append("stderr_marker:" + ",".join(hits))
    return faults


def run_one(arm: str, seed: int) -> None:
    proc_dir, launch_dir = ART / "processes", ART / "launches"
    record = proc_dir / f"{arm}-{seed}.json"
    marker = launch_dir / f"{arm}-{seed}.launched"
    if record.exists() or marker.exists():
        return
    with open(marker, "x", encoding="utf-8") as fh:  # exclusive: a launched child is never relaunched
        fh.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + "\n")
    so, data = model_paths(arm)
    hb = ART / "heartbeats" / f"{arm}-{seed}"
    out = ART / "raw" / f"{arm}-{seed}.json"
    cmd = [str(CHILD), arm, str(so), str(data), str(seed), str(hb), str(out)]
    t = time.perf_counter()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=ST["child_timeout_seconds"])
        rc, stdout, stderr = cp.returncode, cp.stdout, cp.stderr
    except subprocess.TimeoutExpired as e:
        rc, stdout, stderr = "timeout", str(e.stdout or ""), str(e.stderr or "")
    wall = time.perf_counter() - t
    try:
        output = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
    except json.JSONDecodeError:
        output = None
    beats = []
    if hb.exists():
        for p in sorted(hb.glob("*.json")):
            parts = p.stem.split("-", 1)
            beats.append(parts[1] if len(parts) == 2 else p.stem)
    rec = {"arm": arm, "seed": seed, "started_utc": started, "returncode": rc,
           "signal_name": signal.Signals(-rc).name if isinstance(rc, int) and rc < 0 else None,
           "process_wall_seconds": wall, "stdout_tail": stdout[-2000:], "stderr_tail": stderr[-4000:],
           "heartbeats": beats, "output": output}
    rec["faults"] = classify(rec)
    record.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
    if rec["faults"]:
        log(f"FAULT {arm} {seed}: {rec['faults']} rc={rc} {stderr.strip()[-300:]}")


def run() -> None:
    p = ART / "probe.json"
    if not p.exists() or not json.loads(p.read_text(encoding="utf-8")).get("passed"):
        raise SystemExit("the manipulation probe has not passed; run `probe` first")
    for d in ("processes", "launches", "heartbeats", "raw"):
        (ART / d).mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    for i, seed in enumerate(SEEDS):
        k = i % len(ARMS)
        for arm in ARMS[k:] + ARMS[:k]:
            run_one(arm, seed)
        if (i + 1) % 25 == 0:
            log(f"{i + 1}/{len(SEEDS)} seeds done in {time.perf_counter() - started:.0f}s")


def upper_bound(k: int, n: int, alpha: float = 0.05) -> float:
    """One-sided exact (Clopper-Pearson) upper bound on the fault probability."""
    if n == 0:
        return float("nan")
    if k >= n:
        return 1.0

    def cdf(p: float) -> float:
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))

    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if cdf(mid) > alpha:
            lo = mid
        else:
            hi = mid
    return hi


def analyze() -> None:
    recs = {}
    for p in sorted((ART / "processes").glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        recs[(r["arm"], r["seed"])] = r
    launched = {tuple(p.stem.rsplit("-", 1)) for p in (ART / "launches").glob("*.launched")}
    interrupted = sorted(f"{a}-{s}" for a, s in launched if (a, int(s)) not in recs)
    per_arm = {}
    for arm in ARMS:
        rs = [recs[(arm, s)] for s in SEEDS if (arm, s) in recs]
        faulted = [r for r in rs if r["faults"]]
        kinds: dict = {}
        for r in faulted:
            for f in r["faults"]:
                kinds[f] = kinds.get(f, 0) + 1
        ok = [r for r in rs if not r["faults"]]
        walls = [r["output"]["sampling_wall_seconds_pinned_cotenanted"] for r in ok]
        n = len(rs) + sum(1 for x in interrupted if x.startswith(arm + "-"))
        k = len(faulted) + sum(1 for x in interrupted if x.startswith(arm + "-"))
        per_arm[arm] = {
            "children_recorded": len(rs), "children_counted": n, "faults": k, "fault_kinds": kinds,
            "faulted": [{"seed": r["seed"], "faults": r["faults"], "returncode": r["returncode"],
                         "stderr_tail": r["stderr_tail"][-500:]} for r in faulted],
            "upper_bound_95_one_sided": upper_bound(k, n),
            "median_sampling_wall_seconds": statistics.median(walls) if walls else None,
            "median_process_wall_seconds": statistics.median([r["process_wall_seconds"] for r in ok]) if ok else None,
            "leftover_copy_dirs": sum(1 for r in ok if r["output"].get("leftover_copy_dirs")),
            "model_mapped_after_drop": sum(1 for r in ok if any("_model.so" in m for m in (r["output"].get("mapped_after_drop") or []))),
            "executions": sorted({r["output"]["execution"] for r in ok}),
        }

    def parity(a: str, b: str) -> dict:
        both = [s for s in SEEDS if (a, s) in recs and (b, s) in recs and not recs[(a, s)]["faults"] and not recs[(b, s)]["faults"]]
        same = [s for s in both if recs[(a, s)]["output"]["draws_fingerprint_fnv1a64"] == recs[(b, s)]["output"]["draws_fingerprint_fnv1a64"]
                and recs[(a, s)]["output"]["target_calls"] == recs[(b, s)]["output"]["target_calls"]]
        return {"comparable": len(both), "identical": len(same), "differing_seeds": sorted(set(both) - set(same))[:50]}

    par = {"serialised_vs_replicated": parity("serialised", "replicated"),
           "serialised_vs_threaded_direct": parity("serialised", "threaded_direct")}
    pr = ST["predictions"]
    n_needed = len(SEEDS)
    predictions = {
        "B1_zero_faults_every_path": {"value": {a: per_arm[a]["faults"] for a in ARMS},
                                      "held": all(per_arm[a]["faults"] == 0 and per_arm[a]["children_counted"] == n_needed for a in ARMS)},
        "B2_serialised_replicated_fingerprint_parity_every_seed": {"value": par["serialised_vs_replicated"],
            "held": par["serialised_vs_replicated"]["identical"] == n_needed},
        "reported_serialised_vs_threaded_direct_parity": {"value": par["serialised_vs_threaded_direct"]},
    }
    summary = {"schema": "bridgestan-linux-dispatch-v1-stress-summary", "per_arm": per_arm, "parity": par,
               "interrupted": interrupted, "predictions": predictions, "statements": {k: v["statement"] for k, v in pr.items()},
               "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
               "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# WP65 part (b): fault rate per dispatch path", "",
             f"{ST['model']}, 4 chains / 4 threads, 1,000/1,000, seeds {SEEDS[0]}..{SEEDS[-1]} shared by the paths; "
             "one child at a time, pinned to cores 4-7.", "",
             "| path | execution | children | faults | 95% upper bound | fault kinds | median sampling wall s |",
             "|---|---|---:|---:|---:|---|---:|"]
    for a in ARMS:
        e = per_arm[a]
        lines.append(f"| {a} | {', '.join(e['executions'])} | {e['children_counted']} | {e['faults']} | "
                     f"{e['upper_bound_95_one_sided']:.4%} | {e['fault_kinds'] or '—'} | "
                     f"{e['median_sampling_wall_seconds'] if e['median_sampling_wall_seconds'] is None else format(e['median_sampling_wall_seconds'], '.3f')} |")
    lines += ["", f"Parity serialised vs replicated: {par['serialised_vs_replicated']['identical']}/"
              f"{par['serialised_vs_replicated']['comparable']} identical fingerprints and call counts; "
              f"serialised vs threaded_direct (different library build, reported): {par['serialised_vs_threaded_direct']['identical']}/"
              f"{par['serialised_vs_threaded_direct']['comparable']}.", f"Interrupted launches: {interrupted or 'none'}.", "",
              "| prediction | held |", "|---|---|"]
    for k, v in predictions.items():
        lines.append(f"| {k} | {v.get('held', 'reported')} |")
    (ART / "result.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    {"probe": probe, "run": run, "analyze": analyze}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
