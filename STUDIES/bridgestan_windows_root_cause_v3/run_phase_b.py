#!/usr/bin/env python3
"""WP50C Phase B stress-gate orchestrator: static-runtime vs dynamic-runtime DLLs.

    python run_phase_b.py verify   # assets, binary, exe-only launch dir
    python run_phase_b.py probe    # pre-launch manipulation check (no sampling)
    python run_phase_b.py run      # the one permitted launch of the frozen matrix
    python run_phase_b.py analyze  # regenerate summaries from immutable records

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
PB = PROTOCOL["phase_b"]
ART = HERE / "artifacts" / "phase-b"
DIRS = {k: ART / k for k in ("launches", "processes", "raw", "heartbeats", "stdout", "stderr")}
EXE_NAME = "bridgestan-windows-root-cause-v3.exe"
EXE = HERE / "build" / "child" / "arms" / "plain" / EXE_NAME
POWERSHELL = PB["launcher"]["executable"]
TIMEOUT = PB["timeout_seconds_per_child"]
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
    """Frozen order: PB["blocks"] blocks; block b holds per_block children of
    each arm (5 static_long, 1 control_long, 1 static_short, 1 control_short),
    rotated left by b mod 8."""
    out = []
    for b in range(PB["blocks"]):
        block = []
        for name, arm in PB["arms"].items():
            for k in range(arm["per_block"]):
                seed = arm["first_seed"] + b * arm["per_block"] + k
                block.append({"case_id": f"{name}-{seed}", "arm": name, "seed": seed,
                              "model": arm["model"], "data": arm["data"],
                              "preload": arm["preload"], "warmup": arm["warmup"],
                              "retained": arm["retained"],
                              "expect_runtime": arm["expect_runtime"]})
        r = b % len(block)
        out.extend(block[r:] + block[:r])
    return out


def child_command(child: dict) -> tuple[list[str], Path, Path]:
    hb = DIRS["heartbeats"] / child["case_id"]
    out = DIRS["raw"] / f"{child['case_id']}.json"
    args = ["sblrc", child["model"], child["data"], str(child["seed"]), str(hb), str(out),
            child["preload"], str(child["warmup"]), str(child["retained"])]
    quoted = " ".join("'" + a.replace("'", "''") + "'" for a in args)
    script = f"& '{EXE}' {quoted}; exit $LASTEXITCODE"
    cmd = [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
           "-Command", script]
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
        rec = {"schema": "bridgestan-windows-root-cause-v3-phase-b-process", **child,
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
    expected = PB["expected_heartbeats"]
    observed = [f"{b['stage']}/{b['boundary']}" for b in beats]
    complete = observed == expected
    if child_pid is not None:
        for directory in CACHE_ROOT.glob(f"process-{child_pid}-*"):
            shutil.rmtree(directory, ignore_errors=True)
    rec = {
        "schema": "bridgestan-windows-root-cause-v3-phase-b-process", **child,
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
    return {"schema": "bridgestan-windows-root-cause-v3-phase-b-windows-events",
            "window_utc": [iso(start_ms - 60_000), iso(end_ms + 20_000)],
            "returncode": proc.returncode, "stderr": proc.stderr, "events": rows}


def event_unix_seconds(text: str | None) -> float | None:
    if not text:
        return None
    from datetime import datetime, timezone
    return datetime.fromisoformat(text[:26]).replace(tzinfo=timezone.utc).timestamp()


def in_lifetime(rec: dict, when: float) -> bool:
    """Event time inside the child's launch window (1 s before launch to 5 s
    after the launcher returned)."""
    start = rec.get("started_unix_ms", 0) / 1000
    return start - 1 <= when <= start + (rec.get("duration_seconds") or 0) + 5


def correlate(records: list[dict], events: dict) -> dict:
    """Event 1000: properties[6]=exception code, [3]=module, [8]=pid, [10]=app path.

    Analysis correction (post-run, records unchanged): Get-WinEvent renders the
    PID property in decimal on this host; the original implementation parsed it
    as hex and therefore matched nothing. Decimal is tried first, then hex.

    WP50C Phase B analysis correction (post-run, records unchanged): all
    Phase B arms share one exe path and Windows reused PID 26612 within the
    run, so PID + path attributed one event (record 30065) to two children,
    one launched 15 minutes after the event. An event is now attributed only
    to a child whose launch window contains the event time. The
    as-preregistered summary is preserved as
    artifacts/phase-b/summary-as-preregistered-pid-only-correlation.json.
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
        when = event_unix_seconds(event.get("time_utc"))
        for rec in records:
            if rec.get("child_pid") == pid and str(EXE).lower() == app and (
                    when is None or in_lifetime(rec, when)):
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


def manipulation_ok(rec: dict) -> bool:
    mods = rec.get("loaded_runtime_modules")
    if not mods:
        return True  # unobservable (died before load/after); counted separately
    expect = PB["runtime_expectations"][rec["expect_runtime"]]
    for name, want in expect.items():
        got = ((mods.get(name) or {}).get("path") or "").lower()
        if want is None and got:
            return False
        if want is not None and not got.startswith(want.lower()):
            return False
    return True


def analyze() -> dict:
    records = [json.loads(p.read_text(encoding="utf-8"))
               for p in sorted(DIRS["processes"].glob("*.json"))]
    events_path = ART / "windows-events.json"
    events = json.loads(events_path.read_text(encoding="utf-8")) if events_path.exists() \
        else {"events": []}
    events_by_case = correlate(records, events)
    planned = {c["case_id"] for c in cells()}
    table = {}
    for rec in records:
        ev = events_by_case.get(rec["case_id"])
        rc = rec.get("launcher_return_code") or {}
        fault = bool(rec.get("process_fault")) or ev is not None
        heap = rc.get("unsigned_32") == HEAP or (
            ev is not None and ev["exception_code"].lower() in ("c0000374", "0xc0000374"))
        arm = table.setdefault(rec["arm"], {
            "children": 0, "faults": 0, "heap_corruption": 0, "event_1000": 0,
            "hidden_exit0_faults": 0, "manipulation_failures": [], "unobservable_modules": 0,
            "last_heartbeat_on_fault": {}, "fault_cases": [], "durations": []})
        arm["children"] += 1
        arm["durations"].append(rec.get("duration_seconds"))
        if not rec.get("loaded_runtime_modules"):
            arm["unobservable_modules"] += 1
        if not manipulation_ok(rec):
            arm["manipulation_failures"].append(rec["case_id"])
        if ev:
            arm["event_1000"] += 1
            if rc.get("unsigned_32") == 0 and not rec.get("process_fault"):
                arm["hidden_exit0_faults"] += 1
        if fault:
            arm["faults"] += 1
            arm["fault_cases"].append({"case": rec["case_id"], "launcher_rc": rc.get("hex_32"),
                                       "last_heartbeat": rec.get("last_heartbeat"), "event": ev})
            lh = rec.get("last_heartbeat")
            arm["last_heartbeat_on_fault"][lh] = arm["last_heartbeat_on_fault"].get(lh, 0) + 1
        if heap:
            arm["heap_corruption"] += 1
    for arm in table.values():
        d = sorted(x for x in arm.pop("durations") if x is not None)
        arm["median_duration_seconds_contended"] = d[len(d) // 2] if d else None
        n = arm["children"]
        arm["upper95_if_zero"] = 1 - 0.05 ** (1 / n) if n else None
    s_long, c_long = table.get("static_long", {}), table.get("control_long", {})
    gate = {"static_long_faults": s_long.get("faults"),
            "static_long_children": s_long.get("children"),
            "control_long_faults": c_long.get("faults")}
    if s_long.get("children") != PB["arms"]["static_long"]["per_block"] * PB["blocks"]:
        gate["verdict"] = "incomplete"
    elif s_long.get("faults", 1) == 0 and c_long.get("faults", 0) >= 1:
        gate["verdict"] = "fix_supported"
    elif s_long.get("faults", 1) == 0:
        gate["verdict"] = "inconclusive_control_did_not_reproduce"
    else:
        gate["verdict"] = "fix_not_supported"
    summary = {"schema": "bridgestan-windows-root-cause-v3-phase-b-summary",
               "planned_children": len(planned), "recorded_children": len(records),
               "missing_records": sorted(planned - {r["case_id"] for r in records}),
               "arms": table, "gate": gate, "event_1000_correlated": len(events_by_case)}
    (ART / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    for name, arm in sorted(table.items()):
        log(f"{name:15s} n={arm['children']:3d} faults={arm['faults']:3d} "
            f"heap={arm['heap_corruption']:3d} ev1000={arm['event_1000']:3d} "
            f"hidden0={arm['hidden_exit0_faults']} manip_fail={len(arm['manipulation_failures'])}")
    log(f"gate: {json.dumps(gate)}")
    return summary


def verify() -> dict:
    problems = []
    for name, arm in PB["arms"].items():
        for key in ("model", "data", "preload"):
            path = Path(arm[key])
            want = arm.get(f"{key}_sha256")
            if not path.exists():
                problems.append(f"{name} {key} missing: {path}")
            elif want and sha256(path) != want:
                problems.append(f"{name} {key} sha256 mismatch: {path}")
    manifest = ART.parent / "phase-b-build-manifest.json"
    if not manifest.exists() or not EXE.exists():
        problems.append("child not built; run build_child.py")
    elif sha256(EXE) != json.loads(manifest.read_text(encoding="utf-8"))["child_exe"]["sha256"]:
        problems.append("child exe differs from build manifest")
    elif sorted(p.name for p in EXE.parent.iterdir()) != [EXE_NAME]:
        problems.append("launch directory is not exe-only")
    result = {"planned_children": len(cells()), "problems": problems}
    log(json.dumps(result, indent=2))
    if problems:
        sys.exit(1)
    return result


def probe() -> None:
    """Pre-launch manipulation check: one no-sampling probe per DLL set through
    the PowerShell launcher, recording which runtime DLLs bind."""
    ART.mkdir(parents=True, exist_ok=True)
    env = base_environment()
    results = {}
    for name in ("static_long", "control_long"):
        arm = PB["arms"][name]
        args = ["probe", arm["model"], arm["data"], arm["preload"]]
        quoted = " ".join("'" + a.replace("'", "''") + "'" for a in args)
        cmd = [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
               "-Command", f"& '{EXE}' {quoted}; exit $LASTEXITCODE"]
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(HERE),
                              timeout=TIMEOUT)
        try:
            report = json.loads(proc.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            report = None
        mods = (report or {}).get("loaded_runtime_modules")
        rec = {"expect_runtime": arm["expect_runtime"], "loaded_runtime_modules": mods}
        ok = bool(mods) and manipulation_ok(rec)
        results[arm["expect_runtime"]] = {"returncode": rc_forms(proc.returncode),
                                          "stderr": proc.stderr, "report": report,
                                          "matches_expectation": ok}
        log(f"{arm['expect_runtime']}: rc={proc.returncode} matches_expectation={ok}")
        for mod, info in (mods or {}).items():
            log(f"    {mod}: {(info or {}).get('path') if info else None}")
    (ART.parent / "phase-b-manipulation-check.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8")


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
    time.sleep(PB["event_settle_seconds"])
    events = capture_events(first_ms, int(time.time() * 1000))
    (ART / "windows-events.json").write_text(json.dumps(events, indent=2) + "\n", encoding="utf-8")
    analyze()


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    {"verify": verify, "probe": probe, "run": run, "analyze": analyze}.get(
        command, lambda: sys.exit(__doc__))()
