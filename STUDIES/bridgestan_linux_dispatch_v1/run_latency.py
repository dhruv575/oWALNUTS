#!/usr/bin/env python3
"""WP65 part (a) driver: gradient-call latency per BridgeStan dispatch path.

    python run_latency.py run       # every (repeat, model, build) process once, sequentially
    python run_latency.py analyze   # artifacts/latency/summary.json + results-table.md

One `target/release/latency` process per (repeat, model, build); repeats are the outer loop so
that drift on the shared box spreads over models and builds. A process that fails is recorded
as a failed row and is not rerun. Run under `taskset -c 4-7`; children inherit it.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
LAT = PROTOCOL["part_a_latency"]
ART = HERE / "artifacts" / "latency"
BIN = HERE / "target" / "release" / "latency"
MODELS = HERE / "models"
PATHS = ["raw1", "direct1", "direct4", "replicated1", "replicated4"]


def short(model: str) -> str:
    return model.replace("-", "__")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def out_path(model: str, build: str, repeat: int) -> Path:
    return ART / "raw" / f"{short(model)}-{build}-{repeat}.json"


def run() -> None:
    (ART / "raw").mkdir(parents=True, exist_ok=True)
    (ART / "processes").mkdir(parents=True, exist_ok=True)
    for repeat in range(1, LAT["repeats"] + 1):
        for model in LAT["models"]:
            for build in LAT["builds"]:
                out = out_path(model, build, repeat)
                record = ART / "processes" / f"{short(model)}-{build}-{repeat}.json"
                marker = ART / "processes" / f"{short(model)}-{build}-{repeat}.launched"
                if record.exists() or marker.exists():
                    continue  # never relaunched
                marker.write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + "\n", encoding="utf-8")
                so = MODELS / build / f"{short(model)}_model.so"
                data = MODELS / f"{short(model)}.data.json"
                cmd = [str(BIN), str(so), str(data), build, str(repeat), str(out)]
                t = time.perf_counter()
                try:
                    cp = subprocess.run(cmd, capture_output=True, text=True, timeout=LAT["process_timeout_seconds"])
                    rc, stdout, stderr = cp.returncode, cp.stdout, cp.stderr
                except subprocess.TimeoutExpired as e:
                    rc, stdout, stderr = "timeout", str(e.stdout or ""), str(e.stderr or "")
                wall = time.perf_counter() - t
                rec = {"model": model, "build": build, "repeat": repeat, "returncode": rc,
                       "process_wall_seconds": wall, "stdout_tail": stdout[-2000:], "stderr_tail": stderr[-4000:],
                       "output_present": out.exists()}
                record.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
                log(f"{model} {build} r{repeat}: rc {rc} in {wall:.1f}s")


def analyze() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    rows = {}
    failures = []
    for model in LAT["models"]:
        for build in LAT["builds"]:
            for repeat in range(1, LAT["repeats"] + 1):
                p = out_path(model, build, repeat)
                if not p.exists():
                    failures.append(f"{model}/{build}/{repeat}")
                    continue
                d = json.loads(p.read_text(encoding="utf-8"))
                for path in d["paths"]:
                    rows.setdefault((model, build, path["path"]), []).append(path)
                rows.setdefault((model, build, "_meta"), []).append(d)

    def med(model: str, build: str, path: str, key: str) -> float | None:
        vals = [r[key] for r in rows.get((model, build, path), [])]
        return statistics.median(vals) if vals else None

    table = {}
    for model in LAT["models"]:
        table[model] = {}
        for build in LAT["builds"]:
            meta = rows.get((model, build, "_meta"), [])
            table[model][build] = {
                "repeats": len(meta),
                "dimension": meta[0]["dimension"] if meta else None,
                "calls_per_caller": [m["calls_per_caller"] for m in meta],
                "direct_execution": meta[0]["direct"]["execution"] if meta else None,
                "direct_compiled_threading": meta[0]["direct"]["compiled_threading"] if meta else None,
                "replicated_execution": meta[0]["replicated"]["execution"] if meta else None,
                "replicated_effective_replicas": meta[0]["replicated"]["effective_replicas"] if meta else None,
                "cpus_allowed_list": sorted({m["cpus_allowed_list"] for m in meta if m.get("cpus_allowed_list")}),
                "paths": {path: {"median_us_per_call_per_caller": med(model, build, path, "us_per_call_per_caller"),
                                 "median_aggregate_us_per_gradient": med(model, build, path, "aggregate_us_per_gradient"),
                                 "median_gradients_per_second": med(model, build, path, "gradients_per_second"),
                                 "us_per_call_per_caller_values": [r["us_per_call_per_caller"] for r in rows.get((model, build, path), [])],
                                 "recoverable_failures": [r["recoverable_failures"] for r in rows.get((model, build, path), [])],
                                 "value_checksums": sorted({r["value_checksum"] for r in rows.get((model, build, path), [])})}
                          for path in PATHS},
            }

    def r(model, b1, p1, b2, p2, key="median_gradients_per_second"):
        x = table[model][b1]["paths"][p1][key]
        y = table[model][b2]["paths"][p2][key]
        return x / y if x and y else None

    ratios = {}
    for model in LAT["models"]:
        ratios[model] = {
            "A1_threads_over_nothreads_raw1_latency": r(model, "threads", "raw1", "nothreads", "raw1", "median_us_per_call_per_caller"),
            "A2_replicated4_over_direct4_throughput_nothreads": r(model, "nothreads", "replicated4", "nothreads", "direct4"),
            "A3_threads_direct4_over_nothreads_direct4_throughput": r(model, "threads", "direct4", "nothreads", "direct4"),
            "A4_direct1_over_raw1_latency_nothreads": r(model, "nothreads", "direct1", "nothreads", "raw1", "median_us_per_call_per_caller"),
            "A4_direct1_over_raw1_latency_threads": r(model, "threads", "direct1", "threads", "raw1", "median_us_per_call_per_caller"),
            "A4_replicated1_over_direct1_latency_nothreads": r(model, "nothreads", "replicated1", "nothreads", "direct1", "median_us_per_call_per_caller"),
            "A4_replicated1_over_direct1_latency_threads": r(model, "threads", "replicated1", "threads", "direct1", "median_us_per_call_per_caller"),
            "reported_replicated4_over_replicated1_per_caller_latency_nothreads": r(model, "nothreads", "replicated4", "nothreads", "replicated1", "median_us_per_call_per_caller"),
            "reported_threads_replicated4_over_threads_direct4_throughput": r(model, "threads", "replicated4", "threads", "direct4"),
            "reported_direct4_over_direct1_per_caller_latency_nothreads": r(model, "nothreads", "direct4", "nothreads", "direct1", "median_us_per_call_per_caller"),
        }
    pr = LAT["predictions"]

    def every(key, test):
        vals = [ratios[m][key] for m in LAT["models"]]
        return {"values": dict(zip(LAT["models"], vals)),
                "held": (all(test(v) for v in vals) if all(v is not None for v in vals) and not failures else None)}

    a4keys = [k for k in ratios[LAT["models"][0]] if k.startswith("A4_")]
    a4_vals = {f"{m}/{k}": ratios[m][k] for m in LAT["models"] for k in a4keys}
    predictions = {
        "A1": {**every("A1_threads_over_nothreads_raw1_latency", lambda v: v <= pr["A1"]["threshold"]), "threshold": pr["A1"]["threshold"]},
        "A2": {**every("A2_replicated4_over_direct4_throughput_nothreads", lambda v: v >= pr["A2"]["threshold"]), "threshold": pr["A2"]["threshold"]},
        "A3": {**every("A3_threads_direct4_over_nothreads_direct4_throughput", lambda v: v >= pr["A3"]["threshold"]), "threshold": pr["A3"]["threshold"]},
        "A4": {"values": a4_vals, "threshold": pr["A4"]["threshold"],
               "held": (all(v is not None and v <= pr["A4"]["threshold"] for v in a4_vals.values()) if not failures else None)},
    }
    summary = {"schema": "bridgestan-linux-dispatch-v1-latency-summary", "failures": failures, "table": table,
               "ratios": ratios, "predictions": predictions,
               "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
               "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (ART / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    def f(x, fmt=".3f"):
        return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)

    lines = ["# WP65 part (a): gradient-call latency per dispatch path", "",
             f"Medians over {LAT['repeats']} processes per (model, build); pinned to cores 4-7, co-tenanted. "
             "`us/call` = wall per call per caller; `agg us/grad` = wall / (callers x calls).", "",
             "| model | build | path | execution | us/call per caller | agg us/grad | grads/s |", "|---|---|---|---|---:|---:|---:|"]
    for model in LAT["models"]:
        for build in LAT["builds"]:
            t = table[model][build]
            for path in PATHS:
                p = t["paths"][path]
                ex = {"raw1": "raw fn pointer", "direct1": t["direct_execution"], "direct4": t["direct_execution"],
                      "replicated1": t["replicated_execution"], "replicated4": t["replicated_execution"]}[path]
                lines.append(f"| {model} | {build} | {path} | {ex} | {f(p['median_us_per_call_per_caller'])} | "
                             f"{f(p['median_aggregate_us_per_gradient'])} | {f(p['median_gradients_per_second'], ',.0f')} |")
    lines += ["", "## Ratios", "", "| ratio | " + " | ".join(LAT["models"]) + " |", "|---|" + "---:|" * len(LAT["models"])]
    for k in ratios[LAT["models"][0]]:
        lines.append(f"| {k} | " + " | ".join(f(ratios[m][k]) for m in LAT["models"]) + " |")
    lines += ["", "## Preregistered predictions", "", "| prediction | statement | held |", "|---|---|---|"]
    for k, v in predictions.items():
        lines.append(f"| {k} | {pr[k]['statement']} | {v['held']} |")
    if failures:
        lines += ["", f"Failed or missing processes: {failures}"]
    (ART / "results-table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    {"run": run, "analyze": analyze}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
