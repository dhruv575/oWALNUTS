#!/usr/bin/env python3
"""WP45 thread-scaling driver (stdlib only).

    python run_grid.py pilot   [--out artifacts]          # baseline grid, three targets, 3 reps
    python run_grid.py profile [--out artifacts]          # phase-1 profile (allocs, timeline, allocator ablation, CAS bench)
    python run_grid.py ab      [--out artifacts]          # interleaved baseline/fixed A/B (decision cells)
    python run_grid.py analyze [--out artifacts]          # summary.json + results-table.md
    python run_grid.py quiet                              # everything above into artifacts/quiet/ (idle machine)

Binaries come from build_bins.py (bin/baseline, bin/fixed). Cells run strictly
sequentially in the frozen order of protocol.json; nothing is retried.
"""
from __future__ import annotations

import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
BIN = HERE / "bin"
LEVELS = [1, 2, 4, 8, 16]


def log(msg: str, logfile: Path) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with logfile.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd: list[str], logfile: Path) -> int:
    log("$ " + " ".join(cmd), logfile)
    env = dict(os.environ, TS_STUDY_DIR=str(HERE))
    with logfile.open("a", encoding="utf-8") as f:
        p = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=env)
    log(f"exit {p.returncode}", logfile)
    return p.returncode


def measured_on(out: Path, label: str) -> None:
    path = out / f"measured_on-{label}.json"
    info = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "binaries": {arm: (BIN / arm / "COMMIT").read_text().strip() for arm in ("baseline", "fixed") if (BIN / arm / "COMMIT").exists()},
        "note": PROTOCOL["contention_note"] if out.name != "quiet" else "quiet rerun; the operator asserts the machine was otherwise idle",
    }
    try:
        info["other_processes_rustc_cargo_python"] = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Process | Where-Object { $_.Name -match 'rustc|cargo|python|stan|nutpie' }).Count"],
            capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception as e:  # noqa: BLE001
        info["other_processes_rustc_cargo_python"] = f"unavailable: {e}"
    path.write_text(json.dumps(info, indent=2), encoding="utf-8")


def pilot(out: Path) -> None:
    logfile = out / "run-log.txt"
    measured_on(out, "pilot")
    for spec in PROTOCOL["grid"]["targets"]:
        run([str(BIN / "baseline" / "grid.exe"), spec["target"], "--out", str(out / "grid"), "--arm", "baseline",
             "--reps", str(PROTOCOL["grid"]["reps"]), f"--{spec['cells']}"], logfile)


def profile(out: Path) -> None:
    logfile = out / "profile-log.txt"
    measured_on(out, "profile")
    exe = str(BIN / "baseline" / "profile.exe")
    for step in PROTOCOL["profile"]["steps"]:
        args = [exe, step["mode"]]
        if "target" in step:
            args.append(step["target"])
        args += ["--out", str(out / "profile" / step["file"])]
        if "cells" in step:
            args += ["--cells", step["cells"]]
        if "reps" in step:
            args += ["--reps", str(step["reps"])]
        run(args, logfile)


def ab(out: Path) -> None:
    logfile = out / "ab-log.txt"
    measured_on(out, "ab")
    for block in PROTOCOL["ab"]["blocks"]:
        for rep in range(block["reps"]):
            for index, cell in enumerate(block["cells"]):
                arms = ["baseline", "fixed"] if (rep + index) % 2 == 0 else ["fixed", "baseline"]
                for arm in arms:
                    run([str(BIN / arm / "grid.exe"), block["target"], "--out", str(out / "ab"), "--arm", arm,
                         "--rep-start", str(rep), "--reps", "1", "--cells", cell], logfile)


# --------------------------------------------------------------------------- analysis


def load_cells(d: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((d / "cells").glob("*.json"))] if (d / "cells").exists() else []


def med(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return statistics.median(xs) if xs else None


def analyze(out: Path) -> None:
    summary: dict = {"protocol_sha256_note": "see CHECKSUMS.sha256", "grid": {}, "ab": {}, "profile": {}}
    lines = ["# WP45 thread scaling — results tables", "",
             f"Source: `{out.name}`. " + ("CONTENDED PILOT: wall-clock numbers were measured while other agents shared the 16 cores." if out.name != "quiet" else "Quiet rerun."), ""]
    grid = load_cells(out / "grid")
    fp_issues = []
    for target in sorted({c["target"] for c in grid}):
        cells = [c for c in grid if c["target"] == target]
        per = {}
        for c in cells:
            per.setdefault((c["chains"], c["threads"]), []).append(c)
        # Bit-identity across threads and reps at fixed chains.
        for chains in LEVELS:
            fps = {c["fingerprint"] for c in cells if c["chains"] == chains and c["status"] == "ok"}
            if len(fps) > 1:
                fp_issues.append(f"{target} c{chains}: {len(fps)} distinct fingerprints")
        rows = {}
        for (chains, threads), cs in sorted(per.items()):
            ok = [c for c in cs if c["status"] == "ok"]
            wall = med([c["wall_s"] for c in ok])
            base = med([c["wall_s"] for c in per.get((chains, 1), []) if c["status"] == "ok"])
            eff_threads = min(threads, chains)
            speedup = base / wall if base and wall else None
            cpu = med([c["counters"]["process_cpu_s"] / c["wall_s"] for c in ok])
            other = med([(c["counters"]["system_busy_core_s"] - c["counters"]["process_cpu_s"]) / c["wall_s"] for c in ok])
            imbalance = med([c["gradients_max_chain"] * chains / c["gradients_total"] for c in ok])
            rows[f"c{chains}-t{threads}"] = {
                "chains": chains, "threads": threads, "n_ok": len(ok), "n": len(cs),
                "wall_s_median": wall, "wall_s_all": [c["wall_s"] for c in ok],
                "speedup_vs_t1": speedup, "efficiency": speedup / eff_threads if speedup else None,
                "process_cpu_per_wall_median": cpu, "other_load_cores_median": other,
                "max_chain_over_mean_chain_gradients": imbalance,
                "gradients_total": ok[0]["gradients_total"] if ok else None,
                "min_bulk_ess": ok[0]["min_bulk_ess"] if ok else None,
                "min_bulk_ess_per_second_median": med([c["min_bulk_ess_per_second"] for c in ok]),
                "gradients_per_second_median": med([c["gradients_per_second"] for c in ok]),
                "page_faults_median": med([c["counters"]["page_faults"] for c in ok]),
                "kernel_cpu_fraction_median": med([c["counters"]["process_kernel_s"] / max(c["counters"]["process_cpu_s"], 1e-9) for c in ok]),
                "metadata_thread_count": ok[0]["metadata_thread_count"] if ok else None,
            }
        w11 = rows.get("c1-t1", {}).get("wall_s_median")
        for k in [1, 2, 4, 8, 16]:
            r = rows.get(f"c{k}-t{k}")
            if r and w11:
                r["weak_scaling_wall11_over_wallkk"] = w11 / r["wall_s_median"]
        summary["grid"][target] = rows
        lines += [f"## Grid: {target}", "",
                  "| chains | threads | n ok | wall s (median) | speedup vs t=1 | efficiency | CPU/wall | other load (cores) | max/mean chain grads | ESS/s | grads/s | page faults | kernel CPU frac |",
                  "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for r in rows.values():
            f = lambda v, p=3: "-" if v is None else (f"{v:.{p}f}" if isinstance(v, float) else str(v))
            lines.append(f"| {r['chains']} | {r['threads']} | {r['n_ok']}/{r['n']} | {f(r['wall_s_median'])} | {f(r['speedup_vs_t1'], 2)} | {f(r['efficiency'], 2)} | {f(r['process_cpu_per_wall_median'], 2)} | {f(r['other_load_cores_median'], 1)} | {f(r['max_chain_over_mean_chain_gradients'], 3)} | {f(r['min_bulk_ess_per_second_median'], 0)} | {f(r['gradients_per_second_median'], 0)} | {f(r['page_faults_median'], 0)} | {f(r['kernel_cpu_fraction_median'], 3)} |")
        lines.append("")
    summary["grid_fingerprint_issues"] = fp_issues
    lines += ["Fingerprint check (draws + transition diagnostics + telemetry, fixed target and chains, every thread count and repetition): "
              + ("all identical." if not fp_issues and grid else "; ".join(fp_issues) or "no cells"), ""]

    abcells = load_cells(out / "ab")
    if abcells:
        lines += ["## A/B: baseline vs fixed (interleaved)", "",
                  "| target | chains=threads | baseline walls | fixed walls | baseline/fixed (medians) | draws+work identical | metadata identical |",
                  "|---|---:|---|---|---:|---|---|"]
        for target in sorted({c["target"] for c in abcells}):
            for k in LEVELS:
                b = [c for c in abcells if c["target"] == target and c["chains"] == k and c["threads"] == k and c["arm"] == "baseline" and c["status"] == "ok"]
                x = [c for c in abcells if c["target"] == target and c["chains"] == k and c["threads"] == k and c["arm"] == "fixed" and c["status"] == "ok"]
                if not b and not x:
                    continue
                bw, xw = med([c["wall_s"] for c in b]), med([c["wall_s"] for c in x])
                ident = len({c["fingerprint"] for c in b + x}) == 1
                meta = len({tuple(f["metadata"] for f in c["chain_fingerprints"]) for c in b + x}) == 1
                sp = bw / xw if bw and xw else None
                summary["ab"][f"{target}-c{k}"] = {"baseline_walls": [c["wall_s"] for c in b], "fixed_walls": [c["wall_s"] for c in x],
                                                     "speedup_baseline_over_fixed": sp, "draws_work_identical": ident, "metadata_identical": meta,
                                                     "n_baseline": len(b), "n_fixed": len(x)}
                lines.append(f"| {target} | {k} | {', '.join(f'{c['wall_s']:.3f}' for c in b)} | {', '.join(f'{c['wall_s']:.3f}' for c in x)} | {sp:.3f} | {ident} | {meta} |" if sp else f"| {target} | {k} | - | - | - | {ident} | {meta} |")
        rule = PROTOCOL["decision_rule"]
        g = summary["ab"]
        def sp(k):
            return (g.get(f"gauss100-c{k}") or {}).get("speedup_baseline_over_fixed")
        identical = all(v["draws_work_identical"] and v["metadata_identical"] for v in g.values())
        hit = any((sp(k) or 0) >= rule["min_speedup"] for k in (8, 16))
        no_reg = all((sp(k) or 0) >= 1 / rule["max_slowdown_ratio"] for k in (1, 4))
        verdict = identical and hit and no_reg
        summary["decision"] = {"bit_identical": identical, "speedup_c8": sp(8), "speedup_c16": sp(16), "ratio_c1": sp(1), "ratio_c4": sp(4),
                               "meets_speedup": hit, "no_regression": no_reg, "merge": verdict}
        lines += ["", f"Decision rule (protocol.json): bit-identical={identical}, speedup c8={sp(8)}, c16={sp(16)}, no regression at 1/4 threads={no_reg} -> **{'MERGE' if verdict else 'DO NOT MERGE'}**", ""]

    prof = out / "profile"
    if prof.exists():
        for p in sorted(prof.glob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            summary["profile"][p.stem] = d
            lines += [f"## Profile: {p.stem}", ""]
            if d["mode"] == "cas-bench":
                lines += ["| work steps | arm | threads | ns/op/thread |", "|---:|---|---:|---:|"]
                lines += [f"| {r['work_steps']} | {r['arm']} | {r['threads']} | {r['ns_per_op_per_thread']:.1f} |" for r in d["results"]]
            else:
                lines += ["| chains | threads | rep | allocator | wall s | allocs/gradient | allocs/transition/chain | fingerprint |", "|---:|---:|---:|---|---:|---:|---:|---|"]
                for r in d["results"]:
                    lines.append(f"| {r['chains']} | {r['threads']} | {r['rep']} | {r['allocator']} | {r['cell']['wall_s']:.3f} | {r['allocs_per_gradient']:.3f} | {r['allocs_per_transition_per_chain']:.2f} | {r['cell']['fingerprint']} |")
                if d["mode"] == "timeline":
                    lines += ["", "Per-thread probe (inside = user target; outside = kernel + driver + sampler wrappers, CPU-time based):", "",
                              "| chains | threads | slot | calls | span s | CPU/span | ns/call span | ns/call inside | ns/call outside (CPU) | samples P/E/LPE |", "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
                    for r in d["results"]:
                        for s in r["threads_report"] or []:
                            if s["calls"] == 0:
                                continue
                            c = s["processor_class_samples"]
                            lines.append(f"| {r['chains']} | {r['threads']} | {s['slot']} | {s['calls']} | {s['active_span_s']:.3f} | {s['cpu_fraction_of_span']:.2f} | {s['ns_per_call_span']:.0f} | {s['ns_per_call_inside_target']:.0f} | {s['ns_per_call_outside_target_cpu']:.0f} | {c['P']}/{c['E']}/{c['LPE']} |")
            lines.append("")
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (out / "results-table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out / 'summary.json'} and results-table.md")


def main() -> None:
    cmd = sys.argv[1]
    out = HERE / "artifacts"
    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if cmd == "quiet":
        out = HERE / "artifacts" / "quiet"
        out.mkdir(parents=True, exist_ok=True)
        pilot(out)
        profile(out)
        ab(out)
        analyze(out)
        return
    {"pilot": pilot, "profile": profile, "ab": ab, "analyze": analyze}[cmd](out)


if __name__ == "__main__":
    main()
