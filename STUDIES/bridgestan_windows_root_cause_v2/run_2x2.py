#!/usr/bin/env python3
"""WP50B 2x2 orchestrator: libwinpthread source x launcher.

    python run_2x2.py verify     # assets, binaries, launch dirs, launchers
    python run_2x2.py run        # the one permitted launch of the frozen matrix
    python run_2x2.py analyze    # regenerate summaries from immutable records

Children run strictly sequentially. Before each child an exclusive durable
launch marker is created; an existing process record is never relaunched and
an orphan marker is recorded as an interruption, never relaunched. Failures
are results. Diagnostic only; not posterior evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
ART = HERE / "artifacts"
DIRS = {k: ART / k for k in ("launches", "processes", "raw", "heartbeats", "stdout", "stderr")}
EXE_NAME = "bridgestan-windows-root-cause-v2.exe"
BASH = PROTOCOL["launchers"]["bash"]["executable"]
POWERSHELL = PROTOCOL["launchers"]["powershell"]["executable"]
TIMEOUT = PROTOCOL["timeout_seconds_per_child"]
HEAP = 0xC0000374
CACHE_ROOT = Path(os.environ.get("TEMP", "")) / "owalnuts-bridgestan-cache-v1"
# Environment variables a Git Bash session injects; removed so both launchers
# start from the same registry-derived user environment.
SHELL_VARS = ("MSYSTEM", "MSYSTEM_PREFIX", "MSYSTEM_CHOST", "MSYSTEM_CARCH", "MINGW_PREFIX",
              "MINGW_CHOST", "MINGW_PACKAGE_PREFIX", "ORIGINAL_PATH", "ORIGINAL_TEMP",
              "ORIGINAL_TMP", "EXEPATH", "PLINK_PROTOCOL", "SHLVL", "OLDPWD", "PWD",
              "_", "TERM", "SHELL", "HOME", "MANPATH", "INFOPATH", "PKG_CONFIG_PATH",
              "ACLOCAL_PATH", "CONFIG_SITE", "LANG", "DISPLAY", "HOSTNAME", "TMPDIR")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rc_forms(code: int | None) -> dict | None:
    if code is None:
        return None
    unsigned = code & 0xFFFFFFFF
    signed = unsigned - (1 << 32) if unsigned >= (1 << 31) else unsigned
    return {"raw": code, "signed_32": signed, "unsigned_32": unsigned, "hex_32": f"0x{unsigned:08X}"}


def registry_path() -> str:
    script = ("[Environment]::GetEnvironmentVariable('Path','Machine') + ';' + "
              "[Environment]::GetEnvironmentVariable('Path','User')")
    return subprocess.check_output([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", script],
                                   text=True).strip()


def base_environment() -> dict:
    env = {k: v for k, v in os.environ.items() if k.upper() not in SHELL_VARS}
    env["PATH"] = registry_path()
    env["RUST_BACKTRACE"] = "0"
    return env


def cells() -> list[dict]:
    """Frozen order: ascending seed; within seed, the 4 cells rotated by seed index."""
    order = PROTOCOL["cell_order"]
    out = []
    for i, seed in enumerate(range(PROTOCOL["seeds"]["first"], PROTOCOL["seeds"]["last"] + 1)):
        rotation = order[i % len(order):] + order[: i % len(order)]
        for cell in rotation:
            launcher, dll = cell.split("/")
            out.append({"case_id": f"{launcher}-{dll}-{seed}", "cell": cell,
                        "launcher": launcher, "libwinpthread": dll, "seed": seed})
    return out


def child_command(child: dict) -> tuple[list[str], Path, Path]:
    exe = HERE / "build" / "arms" / child["libwinpthread"] / EXE_NAME
    hb = DIRS["heartbeats"] / child["case_id"]
    out = DIRS["raw"] / f"{child['case_id']}.json"
    args = ["sblrc", str(Path(PROTOCOL["model"]["path"])), str(Path(PROTOCOL["data"]["path"])),
            str(child["seed"]), str(hb), str(out)]
    if child["launcher"] == "powershell":
        quoted = " ".join("'" + a.replace("'", "''") + "'" for a in args)
        script = f"& '{exe}' {quoted}; exit $LASTEXITCODE"
        cmd = [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
               "-Command", script]
    else:
        cmd = [BASH, "-l", "-c", '"$0" "$@"; exit $?', exe.as_posix(), *args]
    return cmd, hb, out


def read_heartbeats(directory: Path) -> list[dict]:
    events = []
    if directory.is_dir():
        for path in sorted(directory.glob("[0-9]*.json")):
            try:
                event = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            event["_file"] = path.name
            events.append(event)
    return sorted(events, key=lambda e: e.get("sequence", 1 << 30))


def kill_tree(pid: int) -> None:
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)


def launch(child: dict, env: dict) -> dict:
    case = child["case_id"]
    record = DIRS["processes"] / f"{case}.json"
    marker = DIRS["launches"] / f"{case}.json"
    if record.exists():
        return json.loads(record.read_text(encoding="utf-8"))
    if marker.exists():
        rec = {"schema": "bridgestan-windows-root-cause-v2-process", **child,
               "status": "interrupted_not_relaunched", "process_fault": True}
        record.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        return rec
    cmd, hb, out = child_command(child)
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({**child, "command": cmd,
                   "launch_unix_ms": int(time.time() * 1000)}, handle, indent=2)
    started = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                            cwd=str(HERE), text=True, encoding="utf-8", errors="replace")
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_tree(proc.pid)
        stdout, stderr = proc.communicate()
    duration = time.time() - started
    code = None if timed_out else proc.returncode
    (DIRS["stdout"] / f"{case}.txt").write_text(stdout or "", encoding="utf-8")
    (DIRS["stderr"] / f"{case}.txt").write_text(stderr or "", encoding="utf-8")
    beats = read_heartbeats(hb)
    child_pid = beats[0].get("pid") if beats else None
    raw = None
    if out.exists():
        try:
            raw = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = None
    modules = next((b.get("detail") for b in beats
                    if b.get("stage") == "load" and b.get("boundary") == "after"), None)
    expected = PROTOCOL["expected_heartbeats"]
    observed = [f"{b['stage']}/{b['boundary']}" for b in beats]
    complete = observed == expected
    if child_pid is not None:
        for directory in CACHE_ROOT.glob(f"process-{child_pid}-*"):
            shutil.rmtree(directory, ignore_errors=True)
    rec = {
        "schema": "bridgestan-windows-root-cause-v2-process", **child,
        "command": cmd, "launcher_pid": proc.pid, "child_pid": child_pid,
        "started_unix_ms": int(started * 1000), "duration_seconds": duration,
        "timed_out": timed_out, "launcher_return_code": rc_forms(code),
        "raw_output_exists": raw is not None, "raw_status": raw.get("status") if raw else None,
        "heartbeats_observed": observed, "heartbeat_complete": complete,
        "last_heartbeat": observed[-1] if observed else None,
        "loaded_runtime_modules": modules, "stdout": stdout, "stderr": stderr,
        "silent": not stdout and not stderr,
        "process_fault": timed_out or code != 0 or raw is None
        or (raw or {}).get("status") != "ok" or not complete,
    }
    record.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    return rec


EVENT_SCRIPT = r"""
$start = [DateTime]::Parse('{start}').ToLocalTime()
$end = [DateTime]::Parse('{end}').ToLocalTime()
$events = Get-WinEvent -FilterHashtable @{{LogName='Application'; Id=1000,1001; StartTime=$start; EndTime=$end}} -ErrorAction SilentlyContinue
$rows = foreach ($e in $events) {{
  [pscustomobject]@{{ id=$e.Id; record_id=$e.RecordId; time_utc=$e.TimeCreated.ToUniversalTime().ToString('o');
    provider=$e.ProviderName; properties=@($e.Properties | ForEach-Object {{ [string]$_.Value }}) }}
}}
ConvertTo-Json -InputObject @($rows) -Depth 4
"""


def capture_events(start_ms: int, end_ms: int) -> dict:
    iso = lambda ms: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ms / 1000))
    script = EVENT_SCRIPT.format(start=iso(start_ms - 60_000), end=iso(end_ms + 20_000))
    proc = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", script],
                          capture_output=True, text=True)
    try:
        rows = json.loads(proc.stdout) if proc.stdout.strip() else []
    except json.JSONDecodeError:
        rows = []
    return {"schema": "bridgestan-windows-root-cause-v2-windows-events",
            "window_utc": [iso(start_ms - 60_000), iso(end_ms + 20_000)],
            "returncode": proc.returncode, "stderr": proc.stderr, "events": rows}


def correlate(records: list[dict], events: dict) -> dict:
    """Event 1000: properties[6]=exception code, [3]=module, [8]=pid, [10]=app path.

    Analysis correction (post-run, records unchanged): Get-WinEvent renders the
    PID property in decimal on this host; the original implementation parsed it
    as hex and therefore matched nothing. Decimal is tried first, then hex.
    """
    by_case = {}
    for event in events.get("events", []):
        if event.get("id") != 1000:
            continue
        props = event.get("properties") or []
        if len(props) < 11:
            continue
        text = props[8].strip().lower()
        try:
            pid = int(text, 16) if text.startswith("0x") else int(text)
        except ValueError:
            continue
        app = props[10].lower()
        for rec in records:
            exe = (HERE / "build" / "arms" / rec["libwinpthread"] / EXE_NAME)
            if rec.get("child_pid") == pid and str(exe).lower() == app:
                by_case[rec["case_id"]] = {"exception_code": props[6], "module": props[3],
                                           "module_path": props[11] if len(props) > 11 else None,
                                           "offset": props[7], "record_id": event.get("record_id")}
    return by_case


def fisher_one_sided(a: int, n1: int, b: int, n2: int) -> float:
    """P(X >= a) under the hypergeometric null for a faults in group 1 of n1."""
    total, k = n1 + n2, a + b
    def pmf(x: int) -> float:
        return math.comb(n1, x) * math.comb(n2, k - x) / math.comb(total, k)
    return sum(pmf(x) for x in range(a, min(n1, k) + 1)) if k else 1.0


def analyze() -> dict:
    records = [json.loads(p.read_text(encoding="utf-8"))
               for p in sorted(DIRS["processes"].glob("*.json"))]
    events = json.loads((ART / "windows-events.json").read_text(encoding="utf-8")) \
        if (ART / "windows-events.json").exists() else {"events": []}
    events_by_case = correlate(records, events)
    planned = {c["case_id"] for c in cells()}
    table = {}
    manipulation_failures = []
    for rec in records:
        ev = events_by_case.get(rec["case_id"])
        rc = rec.get("launcher_return_code") or {}
        fault = bool(rec.get("process_fault")) or ev is not None
        heap = rc.get("unsigned_32") == HEAP or (ev is not None and ev["exception_code"].lower()
                                                 in ("c0000374", "0xc0000374"))
        mods = rec.get("loaded_runtime_modules") or {}
        wp = (mods.get("libwinpthread-1.dll") or {}).get("path", "") or ""
        arm_dir = str(HERE / "build" / "arms" / rec["libwinpthread"]).lower()
        if mods and not wp.lower().startswith(arm_dir):
            manipulation_failures.append(rec["case_id"])
        cell = table.setdefault(rec["cell"], {"children": 0, "faults": 0, "heap_corruption": 0,
                                               "event_1000": 0, "silent_faults": 0,
                                               "last_heartbeat_on_fault": {},
                                               "fault_cases": [], "runtime_modules_seen": {}})
        cell["children"] += 1
        for name, info in mods.items():
            key = f"{name}={(info or {}).get('path')} ({(info or {}).get('bytes')} B)"
            cell["runtime_modules_seen"][key] = cell["runtime_modules_seen"].get(key, 0) + 1
        if ev:
            cell["event_1000"] += 1
        if fault:
            cell["faults"] += 1
            cell["fault_cases"].append({"case": rec["case_id"], "launcher_rc": rc.get("hex_32"),
                                        "last_heartbeat": rec.get("last_heartbeat"), "event": ev})
            lh = rec.get("last_heartbeat")
            cell["last_heartbeat_on_fault"][lh] = cell["last_heartbeat_on_fault"].get(lh, 0) + 1
            if rec.get("silent"):
                cell["silent_faults"] += 1
        if heap:
            cell["heap_corruption"] += 1
    def margin(field: str, level: str) -> tuple[int, int]:
        rows = [v for k, v in table.items() if (k.split("/")[0] if field == "launcher" else k.split("/")[1]) == level]
        return sum(r["faults"] for r in rows), sum(r["children"] for r in rows)
    margins = {}
    for field, levels in (("launcher", ("powershell", "bash")), ("libwinpthread", ("git", "winlibs"))):
        (fa, na), (fb, nb) = margin(field, levels[0]), margin(field, levels[1])
        margins[field] = {levels[0]: [fa, na], levels[1]: [fb, nb],
                          f"fisher_one_sided_p_{levels[0]}_greater": fisher_one_sided(fa, na, fb, nb),
                          f"fisher_one_sided_p_{levels[1]}_greater": fisher_one_sided(fb, nb, fa, na)}
    summary = {"schema": "bridgestan-windows-root-cause-v2-summary",
               "planned_children": len(planned), "recorded_children": len(records),
               "missing_records": sorted(planned - {r["case_id"] for r in records}),
               "cells": table, "margins": margins,
               "event_1000_correlated": len(events_by_case),
               "manipulation_failures": manipulation_failures}
    (ART / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    for name, cell in sorted(table.items()):
        log(f"{name:20s} n={cell['children']:3d} faults={cell['faults']:3d} heap={cell['heap_corruption']:3d} "
            f"ev1000={cell['event_1000']:3d}")
    log(f"margins: {json.dumps(margins)}")
    log(f"manipulation failures: {len(manipulation_failures)}")
    return summary


def verify() -> dict:
    problems = []
    for key in ("model", "data"):
        path = Path(PROTOCOL[key]["path"])
        if not path.exists() or sha256(path) != PROTOCOL[key]["sha256"]:
            problems.append(f"{key} missing or hash mismatch: {path}")
    manifest_path = ART / "build-manifest.json"
    if not manifest_path.exists():
        problems.append("build manifest missing; run build_child.py")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for label, spec in PROTOCOL["libwinpthread"].items():
            directory = HERE / "build" / "arms" / label
            exe, dll = directory / EXE_NAME, directory / "libwinpthread-1.dll"
            if not exe.exists() or sha256(exe) != manifest["child_exe"]["sha256"]:
                problems.append(f"{label}: exe missing or differs from manifest")
            if not dll.exists() or sha256(dll) != spec["sha256"]:
                problems.append(f"{label}: libwinpthread missing or hash mismatch")
            extra = sorted(p.name for p in directory.iterdir()) if directory.exists() else []
            if extra != sorted([EXE_NAME, "libwinpthread-1.dll"]):
                problems.append(f"{label}: unexpected launch-directory contents {extra}")
    for name in (BASH, POWERSHELL):
        if not shutil.which(name) and not Path(name).exists():
            problems.append(f"launcher missing: {name}")
    for p in PROTOCOL["preload_note_dlls"]:
        if not Path(p).exists():
            problems.append(f"preload missing: {p}")
    result = {"planned_children": len(cells()), "problems": problems}
    log(json.dumps(result, indent=2))
    if problems:
        sys.exit(1)
    return result


def probe() -> None:
    """Pre-launch manipulation check: one no-sampling probe per cell, through
    the real launcher and environment, recording which runtime DLLs bound."""
    env = base_environment()
    results = {}
    for cell in PROTOCOL["cell_order"]:
        launcher, dll = cell.split("/")
        exe = HERE / "build" / "arms" / dll / EXE_NAME
        args = ["probe", str(Path(PROTOCOL["model"]["path"])), str(Path(PROTOCOL["data"]["path"]))]
        if launcher == "powershell":
            quoted = " ".join("'" + a.replace("'", "''") + "'" for a in args)
            cmd = [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                   "-Command", f"& '{exe}' {quoted}; exit $LASTEXITCODE"]
        else:
            cmd = [BASH, "-l", "-c", '"$0" "$@"; exit $?', exe.as_posix(), *args]
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(HERE),
                              timeout=TIMEOUT)
        try:
            report = json.loads(proc.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            report = None
        mods = (report or {}).get("loaded_runtime_modules") or {}
        wp = ((mods.get("libwinpthread-1.dll") or {}).get("path") or "").lower()
        results[cell] = {"returncode": rc_forms(proc.returncode), "stderr": proc.stderr,
                         "report": report,
                         "libwinpthread_in_cell_dir": wp.startswith(str(exe.parent).lower())}
        log(f"{cell}: rc={proc.returncode} libwinpthread_in_cell_dir="
            f"{results[cell]['libwinpthread_in_cell_dir']}")
        for name, info in mods.items():
            log(f"    {name}: {(info or {}).get('path')} ({(info or {}).get('bytes')} B)")
    ART.mkdir(exist_ok=True)
    (ART / "manipulation-check.json").write_text(json.dumps(results, indent=2) + "\n",
                                                encoding="utf-8")


def run() -> None:
    for directory in DIRS.values():
        directory.mkdir(parents=True, exist_ok=True)
    if any(DIRS["launches"].iterdir()):
        raise SystemExit("launch markers already exist; the single permitted launch was used")
    verify()
    env = base_environment()
    (ART / "launch-environment.json").write_text(json.dumps(
        {"PATH": env["PATH"], "removed_shell_vars": [v for v in SHELL_VARS if v in os.environ]},
        indent=2) + "\n", encoding="utf-8")
    plan = cells()
    first_ms = int(time.time() * 1000)
    for i, child in enumerate(plan, 1):
        rec = launch(child, env)
        flag = "" if not rec.get("process_fault") else \
            f" FAULT rc={(rec.get('launcher_return_code') or {}).get('hex_32')} last={rec.get('last_heartbeat')}"
        log(f"[{i}/{len(plan)}] {rec['case_id']}{flag}")
    time.sleep(PROTOCOL["event_settle_seconds"])
    events = capture_events(first_ms, int(time.time() * 1000))
    (ART / "windows-events.json").write_text(json.dumps(events, indent=2) + "\n", encoding="utf-8")
    analyze()


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    {"verify": verify, "probe": probe, "run": run, "analyze": analyze}.get(
        command, lambda: sys.exit(__doc__))()
