#!/usr/bin/env python3
"""WP50C Phase C payoff orchestrator: owned-worker serialised vs unserialised
multi-replica target, HEAD sampler, static-runtime DLLs.

    python run_phase_c.py build    # build payoff/ (HEAD) and the exe-only launch dir
    python run_phase_c.py verify   # assets, exe hash
    python run_phase_c.py run      # the one permitted launch of the frozen matrix
    python run_phase_c.py analyze  # regenerate summary from immutable records

Strictly sequential; PowerShell launch under the registry PATH (as Phase B).
Failures are results; nothing is rerun. Wall times are contended.
"""
from __future__ import annotations

import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import run_phase_b as B

HERE = Path(__file__).resolve().parent
PC = B.PROTOCOL["phase_c"]
ART = HERE / "artifacts" / "phase-c"
EXE_NAME = "bridgestan-windows-payoff-v3.exe"
EXE = HERE / "build" / "payoff" / "plain" / EXE_NAME
MANIFEST = HERE / "artifacts" / "phase-c-build-manifest.json"
log, sha256, rc_forms = B.log, B.sha256, B.rc_forms


def cells() -> list[dict]:
    """Per (model, seed index i): arms in PC["arm_order"], reversed when i is odd."""
    out = []
    for model, spec in PC["models"].items():
        for i, seed in enumerate(spec["seeds"]):
            arms = PC["arm_order"] if i % 2 == 0 else PC["arm_order"][::-1]
            for arm in arms:
                out.append({"case_id": f"{model}-{seed}-{arm}", "model_name": model, "seed": seed,
                            "arm": arm, "model": spec["model"], "data": spec["data"],
                            "preload": PC["preload"]})
    return out


def build() -> None:
    env = dict(os.environ, RUSTUP_TOOLCHAIN=B.PROTOCOL["toolchain"])
    crate = HERE / "payoff" / "Cargo.toml"
    for args in (["test", "--release", "--locked", "--offline", "-j", "2"],
                 ["build", "--release", "--locked", "--offline", "-j", "2"]):
        subprocess.run(["cargo", *args, "--manifest-path", str(crate)], env=env, check=True)
    built = HERE / "payoff" / "target" / "release" / EXE_NAME
    if EXE.parent.exists():
        raise SystemExit(f"refusing to replace {EXE.parent}")
    EXE.parent.mkdir(parents=True)
    shutil.copy2(built, EXE)
    repo = HERE.parents[1]
    manifest = {"schema": "bridgestan-windows-payoff-v3-build",
                "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "worktree_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo,
                                                         text=True).strip(),
                "toolchain": B.PROTOCOL["toolchain"],
                "child_exe": {"bytes": EXE.stat().st_size, "sha256": sha256(EXE)},
                "directory_listing": sorted(p.name for p in EXE.parent.iterdir())}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    log(json.dumps(manifest, indent=2))


def verify() -> dict:
    problems = []
    assets = [(PC["preload"], PC["preload_sha256"])]
    for spec in PC["models"].values():
        assets += [(spec["model"], spec["model_sha256"]), (spec["data"], spec["data_sha256"])]
    for path, want in assets:
        if not Path(path).exists():
            problems.append(f"missing {path}")
        elif sha256(Path(path)) != want:
            problems.append(f"sha256 mismatch {path}")
    if not MANIFEST.exists() or not EXE.exists():
        problems.append("payoff child not built")
    elif sha256(EXE) != json.loads(MANIFEST.read_text(encoding="utf-8"))["child_exe"]["sha256"]:
        problems.append("payoff exe differs from manifest")
    result = {"planned_children": len(cells()), "problems": problems}
    log(json.dumps(result, indent=2))
    if problems:
        sys.exit(1)
    return result


def launch(child: dict, env: dict) -> dict:
    record = ART / "processes" / f"{child['case_id']}.json"
    marker = ART / "launches" / f"{child['case_id']}.json"
    if record.exists():
        return json.loads(record.read_text(encoding="utf-8"))
    if marker.exists():
        rec = {**child, "status": "interrupted_not_relaunched", "process_fault": True}
        record.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        return rec
    out = ART / "raw" / f"{child['case_id']}.json"
    args = [child["arm"], child["model_name"], child["model"], child["data"], child["preload"],
            str(child["seed"]), str(out)]
    quoted = " ".join("'" + a.replace("'", "''") + "'" for a in args)
    cmd = [B.POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
           "-Command", f"& '{EXE}' {quoted}; exit $LASTEXITCODE"]
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({**child, "command": cmd, "launch_unix_ms": int(time.time() * 1000)}, handle)
    started = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                            cwd=str(HERE), text=True, encoding="utf-8", errors="replace")
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=PC["timeout_seconds_per_child"])
    except subprocess.TimeoutExpired:
        timed_out = True
        B.kill_tree(proc.pid)
        stdout, stderr = proc.communicate()
    code = None if timed_out else proc.returncode
    raw = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
    rec = {"schema": "bridgestan-windows-payoff-v3-process", **child, "command": cmd,
           "launcher_pid": proc.pid, "started_unix_ms": int(started * 1000),
           "launcher_wall_seconds_contended": time.time() - started, "timed_out": timed_out,
           "launcher_return_code": rc_forms(code), "stdout": stdout, "stderr": stderr,
           "raw": raw, "process_fault": timed_out or code != 0 or raw is None
           or raw.get("status") != "ok"}
    record.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    return rec


def events_for(records: list[dict], events: dict) -> dict:
    """Event 1000 rows whose app path is the payoff exe and whose time falls in a
    child's launch window (the child PID is not otherwise recorded)."""
    hits = {}
    for event in events.get("events", []):
        props = event.get("properties") or []
        if event.get("id") != 1000 or len(props) < 11 or props[10].lower() != str(EXE).lower():
            continue
        hits.setdefault("unattributed", []).append({"exception_code": props[6],
                                                    "module": props[3],
                                                    "time_utc": event.get("time_utc")})
    return hits


def analyze() -> dict:
    records = [json.loads(p.read_text(encoding="utf-8"))
               for p in sorted((ART / "processes").glob("*.json"))]
    events_path = ART / "windows-events.json"
    events = json.loads(events_path.read_text(encoding="utf-8")) if events_path.exists() \
        else {"events": []}
    by = {(r["model_name"], r["seed"], r["arm"]): r for r in records}
    pairs, assertions_ok = [], True
    for model, spec in PC["models"].items():
        for seed in spec["seeds"]:
            s, u = by.get((model, seed, "serialised")), by.get((model, seed, "unserialised"))
            row = {"model": model, "seed": seed}
            if not s or not u or s.get("process_fault") or u.get("process_fault"):
                row["status"] = "fault_or_missing"
                assertions_ok = False
                pairs.append(row)
                continue
            rs, ru = s["raw"], u["raw"]
            row["identical"] = {k: rs[k] == ru[k] for k in (
                "start_gradient_hash_fnv1a64", "draws_fingerprint_fnv1a64", "target_calls",
                "draws_observed")}
            assertions_ok &= all(row["identical"].values())
            for arm, r in (("serialised", rs), ("unserialised", ru)):
                row[arm] = {k: r[k] for k in (
                    "sampling_wall_seconds_contended", "sampling_cpu_user_seconds",
                    "sampling_cpu_kernel_seconds", "process_wall_seconds_contended",
                    "effective_replicas", "execution")}
            row["payoff_wall_ratio_serialised_over_unserialised"] = (
                rs["sampling_wall_seconds_contended"] / ru["sampling_wall_seconds_contended"])
            row["cpu_ratio_serialised_over_unserialised"] = (
                (rs["sampling_cpu_user_seconds"] + rs["sampling_cpu_kernel_seconds"])
                / (ru["sampling_cpu_user_seconds"] + ru["sampling_cpu_kernel_seconds"]))
            row["status"] = "ok"
            pairs.append(row)
    per_model = {}
    for model in PC["models"]:
        ratios = [p["payoff_wall_ratio_serialised_over_unserialised"] for p in pairs
                  if p["model"] == model and p["status"] == "ok"]
        per_model[model] = {"wall_ratios": ratios,
                            "median_wall_ratio": statistics.median(ratios) if ratios else None}
    unattributed = events_for(records, events)
    faults = sum(bool(r.get("process_fault")) for r in records) + len(
        unattributed.get("unattributed", []))
    rule = PC["recommendation_rule"]
    medians = [m["median_wall_ratio"] for m in per_model.values()]
    recommend = (assertions_ok and faults == 0 and all(m is not None for m in medians)
                 and min(medians) >= rule["min_median_wall_ratio_each_model"])
    summary = {"schema": "bridgestan-windows-payoff-v3-summary", "children": len(records),
               "planned": len(cells()), "faults_event_inclusive": faults,
               "event_1000_payoff_exe": unattributed, "assertions_identical": assertions_ok,
               "pairs": pairs, "per_model": per_model,
               "phase_c_condition_for_default_change_met": recommend}
    (ART / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    for p in pairs:
        log(f"{p['model']:6s} {p['seed']} {p['status']} "
            f"ratio={p.get('payoff_wall_ratio_serialised_over_unserialised')} "
            f"identical={p.get('identical')}")
    log(f"per_model={json.dumps(per_model)} faults={faults} condition_met={recommend}")
    return summary


def run() -> None:
    for sub in ("launches", "processes", "raw"):
        (ART / sub).mkdir(parents=True, exist_ok=True)
    if any((ART / "launches").iterdir()):
        raise SystemExit("launch markers already exist; the single permitted launch was used")
    verify()
    env = B.base_environment()
    first_ms = int(time.time() * 1000)
    plan = cells()
    for i, child in enumerate(plan, 1):
        rec = launch(child, env)
        raw = rec.get("raw") or {}
        log(f"[{i}/{len(plan)}] {rec['case_id']} fault={rec.get('process_fault')} "
            f"wall={raw.get('sampling_wall_seconds_contended')}")
    time.sleep(PC["event_settle_seconds"])
    events = B.capture_events(first_ms, int(time.time() * 1000))
    (ART / "windows-events.json").write_text(json.dumps(events, indent=2) + "\n", encoding="utf-8")
    analyze()
    for directory in Path(os.environ.get("TEMP", "")).glob("wp50c-unserialised-*"):
        shutil.rmtree(directory, ignore_errors=True)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    {"build": build, "verify": verify, "run": run, "analyze": analyze}.get(
        command, lambda: sys.exit(__doc__))()
