#!/usr/bin/env python3
"""WP50D confirmatory stress gate orchestrator.

    python run_gate.py verify    # assets, binaries, exe-only launch dirs
    python run_gate.py probe     # pre-launch manipulation check (no sampling)
    python run_gate.py run       # the one permitted launch of the frozen matrix
    python run_gate.py analyze   # regenerate the summary from immutable records

Children run strictly sequentially, one at a time, 4 threads each. An
exclusive durable launch marker precedes every child; an existing record is
never relaunched and an orphan marker is recorded as an interruption, never
relaunched. Failures are results. Diagnostic only; not posterior evidence.

The crash-event correlation rule is frozen in protocol.json
`event_correlation` and implemented in `correlate()` BEFORE any evidence.
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
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
ART = HERE / "artifacts"
DIRS = {k: ART / k for k in ("launches", "processes", "raw", "heartbeats", "stdout", "stderr")}
EXE_NAME = "bridgestan-windows-root-cause-v4.exe"
POWERSHELL = PROTOCOL["launcher"]["executable"]
TIMEOUT = PROTOCOL["timeout_seconds_per_child"]
CORR = PROTOCOL["event_correlation"]
HEAP = 0xC0000374
TEMP = Path(os.environ.get("TEMP", ""))
SHELL_VARS = ("MSYSTEM", "MSYSTEM_PREFIX", "MSYSTEM_CHOST", "MSYSTEM_CARCH", "MINGW_PREFIX",
              "MINGW_CHOST", "MINGW_PACKAGE_PREFIX", "ORIGINAL_PATH", "ORIGINAL_TEMP",
              "ORIGINAL_TMP", "EXEPATH", "PLINK_PROTOCOL", "SHLVL", "OLDPWD", "PWD",
              "_", "TERM", "SHELL", "HOME", "MANPATH", "INFOPATH", "PKG_CONFIG_PATH",
              "ACLOCAL_PATH", "CONFIG_SITE", "LANG", "DISPLAY", "HOSTNAME", "TMPDIR")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exe_for(arm: str) -> Path:
    return HERE / "build" / "arms" / arm / EXE_NAME


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


def ps_command(exe: Path, args: list[str]) -> list[str]:
    quoted = " ".join("'" + a.replace("'", "''") + "'" for a in args)
    return [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-Command", f"& '{exe}' {quoted}; exit $LASTEXITCODE"]


# ------------------------------------------------------------------ matrix ---

def block_order() -> list[str]:
    """Frozen interleaving of single-arm blocks: each arm's j-th block (of n)
    gets key (j + 0.5) / n; blocks run in ascending key, ties in arm order."""
    keys = []
    for rank, (name, arm) in enumerate(PROTOCOL["arms"].items()):
        n = arm["children"] // PROTOCOL["block_size"]
        keys += [((j + 0.5) / n, rank, name) for j in range(n)]
    return [name for _, _, name in sorted(keys)]


def cells() -> list[dict]:
    next_seed = {name: arm["first_seed"] for name, arm in PROTOCOL["arms"].items()}
    out = []
    for block, name in enumerate(block_order()):
        arm = PROTOCOL["arms"][name]
        for _ in range(PROTOCOL["block_size"]):
            seed = next_seed[name]
            next_seed[name] += 1
            out.append({"case_id": f"{name}-{seed}", "arm": name, "seed": seed, "block": block,
                        "model": arm["model"], "data": PROTOCOL["data"]["path"],
                        "preload": arm["preload"], "expect_runtime": arm["expect_runtime"]})
    return out


# ------------------------------------------------------------------ launch ---

def read_heartbeats(directory: Path) -> list[dict]:
    events = []
    if directory.is_dir():
        for path in sorted(directory.glob("[0-9]*.json")):
            try:
                event = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            events.append(event)
    return sorted(events, key=lambda e: e.get("sequence", 1 << 30))


def kill_tree(pid: int) -> None:
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)


def cleanup(child_pid: int | None) -> None:
    if child_pid is None:
        return
    shutil.rmtree(TEMP / f"wp50d-unserialised-{child_pid}", ignore_errors=True)
    for directory in (TEMP / "owalnuts-bridgestan-cache-v1").glob(f"process-{child_pid}-*"):
        shutil.rmtree(directory, ignore_errors=True)


def launch(child: dict, env: dict) -> dict:
    case = child["case_id"]
    record = DIRS["processes"] / f"{case}.json"
    marker = DIRS["launches"] / f"{case}.json"
    if record.exists():
        return json.loads(record.read_text(encoding="utf-8"))
    if marker.exists():
        rec = {"schema": "bridgestan-windows-root-cause-v4-process", **child,
               "status": "interrupted_not_relaunched", "process_fault": True}
        record.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        return rec
    hb = DIRS["heartbeats"] / case
    out = DIRS["raw"] / f"{case}.json"
    cmd = ps_command(exe_for(child["arm"]), [child["arm"], child["model"], child["data"],
                                             child["preload"], str(child["seed"]), str(hb),
                                             str(out)])
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({**child, "command": cmd, "launch_unix_ms": int(time.time() * 1000)}, handle,
                  indent=2)
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
    ended = time.time()
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
    detail = {f"{b['stage']}/{b['boundary']}": b.get("detail") for b in beats}
    observed = [f"{b['stage']}/{b['boundary']}" for b in beats]
    complete = observed == PROTOCOL["expected_heartbeats"]
    cleanup(child_pid)
    rec = {
        "schema": "bridgestan-windows-root-cause-v4-process", **child,
        "command": cmd, "launcher_pid": proc.pid, "child_pid": child_pid,
        "started_unix_ms": int(started * 1000), "ended_unix_ms": int(ended * 1000),
        "duration_seconds": ended - started, "timed_out": timed_out,
        "launcher_return_code": rc_forms(code),
        "raw_output_exists": raw is not None, "raw_status": (raw or {}).get("status"),
        "heartbeats_observed": observed, "heartbeat_complete": complete,
        "last_heartbeat": observed[-1] if observed else None,
        "modules_after_load": detail.get("load/after"),
        "modules_after_drop": detail.get("drop/after"),
        "effective_replicas": (raw or {}).get("effective_replicas"),
        "draws_fingerprint": (raw or {}).get("draws_fingerprint_fnv1a64"),
        "stdout": stdout, "stderr": stderr,
        "process_fault": timed_out or code != 0 or raw is None
        or (raw or {}).get("status") != "ok" or not complete,
    }
    record.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    return rec


# ------------------------------------------------------------------ events ---

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
    return {"schema": "bridgestan-windows-root-cause-v4-windows-events",
            "window_utc": [iso(start_ms - 60_000), iso(end_ms + 20_000)],
            "returncode": proc.returncode, "stderr": proc.stderr, "events": rows}


def event_unix_seconds(text: str | None) -> float | None:
    if not text:
        return None
    return datetime.fromisoformat(text[:26]).replace(tzinfo=timezone.utc).timestamp()


def correlate(records: list[dict], events: dict) -> tuple[dict, list[dict]]:
    """Frozen rule (protocol.json event_correlation): an Application Error
    Event 1000 is attributed to a child iff (a) properties[10] (application
    path) equals that child's arm exe path, case-insensitively, (b)
    properties[8] (PID, decimal; 0x-prefixed parsed as hex) equals the child's
    PID from its heartbeats, and (c) the event time lies in
    [launcher start - before_s, launcher end + after_s]. Each event is
    attributed to at most one child; a matching ambiguity is reported. Events
    whose application path is any arm exe and that match no child are
    returned as unattributed."""
    by_case, unattributed = {}, []
    exes = {str(exe_for(a)).lower(): a for a in PROTOCOL["arms"]}
    for event in events.get("events", []):
        props = event.get("properties") or []
        if event.get("id") != 1000 or len(props) < 11:
            continue
        app = props[10].strip().lower()
        if app not in exes:
            continue
        text = props[8].strip().lower()
        try:
            pid = int(text, 16) if text.startswith("0x") else int(text)
        except ValueError:
            pid = None
        when = event_unix_seconds(event.get("time_utc"))
        row = {"exception_code": props[6], "module": props[3],
               "module_path": props[11] if len(props) > 11 else None, "offset": props[7],
               "record_id": event.get("record_id"), "time_utc": event.get("time_utc"),
               "pid": pid, "app_arm": exes[app]}
        matches = [rec for rec in records
                   if rec.get("child_pid") == pid and rec["arm"] == exes[app] and when is not None
                   and rec["started_unix_ms"] / 1000 - CORR["before_seconds"] <= when
                   <= rec.get("ended_unix_ms", 0) / 1000 + CORR["after_seconds"]]
        if len(matches) == 1:
            by_case[matches[0]["case_id"]] = row
        else:
            unattributed.append({**row, "candidate_cases": [m["case_id"] for m in matches]})
    return by_case, unattributed


# ------------------------------------------------------------------ stats ----

def hypergeom_pmf(x: int, n1: int, n2: int, k: int) -> float:
    return math.comb(n1, x) * math.comb(n2, k - x) / math.comb(n1 + n2, k)


def fisher(a: int, n1: int, b: int, n2: int) -> dict:
    """a faults of n1 (control) vs b of n2 (static). one_sided = P(X >= a)."""
    k = a + b
    if k == 0:
        return {"one_sided_control_greater": 1.0, "two_sided": 1.0}
    lo, hi = max(0, k - n2), min(n1, k)
    pmf = {x: hypergeom_pmf(x, n1, n2, k) for x in range(lo, hi + 1)}
    observed = pmf[a]
    return {"one_sided_control_greater": sum(p for x, p in pmf.items() if x >= a),
            "two_sided": min(1.0, sum(p for p in pmf.values() if p <= observed * (1 + 1e-9)))}


def upper95(k: int, n: int) -> float:
    """One-sided 95% Clopper-Pearson upper bound (= 1 - 0.05**(1/n) at k=0)."""
    if n == 0:
        return float("nan")
    if k >= n:
        return 1.0
    cdf = lambda p: sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if cdf(mid) > 0.05 else (lo, mid)
    return hi


# ----------------------------------------------------------------- analyze ---

def manipulation_ok(mods: dict | None, expect: str) -> bool | None:
    if not mods:
        return None
    for name, want in PROTOCOL["runtime_expectations"][expect].items():
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
    by_case, unattributed = correlate(records, events)
    planned = {c["case_id"] for c in cells()}
    table = {}
    for rec in records:
        ev = by_case.get(rec["case_id"])
        rc = rec.get("launcher_return_code") or {}
        fault = bool(rec.get("process_fault")) or ev is not None
        arm = table.setdefault(rec["arm"], {
            "children": 0, "faults": 0, "heap_corruption": 0, "event_1000": 0,
            "hidden_exit0_faults": 0, "manipulation_failures": [], "modules_unobserved": 0,
            "effective_replicas": {}, "last_heartbeat_on_fault": {}, "fault_cases": [],
            "durations": []})
        arm["children"] += 1
        arm["durations"].append(rec.get("duration_seconds"))
        eff = str(rec.get("effective_replicas"))
        arm["effective_replicas"][eff] = arm["effective_replicas"].get(eff, 0) + 1
        checks = [manipulation_ok(rec.get("modules_after_load"), rec["expect_runtime"])]
        if rec["expect_runtime"] == "static":
            checks.append(manipulation_ok(rec.get("modules_after_drop"), "static"))
        if None in checks:
            arm["modules_unobserved"] += 1
        if False in checks:
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
        if rc.get("unsigned_32") == HEAP or (ev and ev["exception_code"].lower().endswith("c0000374")):
            arm["heap_corruption"] += 1
    # Frozen conservative rule: an unattributed event on the STATIC exe path is a static fault.
    static_unattributed = [u for u in unattributed if u["app_arm"] == "static_unserialised"]
    if "static_unserialised" in table:
        table["static_unserialised"]["unattributed_events_counted"] = len(static_unattributed)
        table["static_unserialised"]["faults"] += len(static_unattributed)
    for name, arm in table.items():
        d = sorted(x for x in arm.pop("durations") if x is not None)
        arm["median_duration_seconds_contended"] = d[len(d) // 2] if d else None
        arm["upper95_fault_rate"] = upper95(arm["faults"], arm["children"])
    s = table.get("static_unserialised", {})
    gate = {"static_faults": s.get("faults"), "static_children": s.get("children"),
            "static_upper95_fault_rate": s.get("upper95_fault_rate"),
            "static_manipulation_failures": len(s.get("manipulation_failures", []))}
    complete = (not (planned - {r["case_id"] for r in records})
                and s.get("children") == PROTOCOL["arms"]["static_unserialised"]["children"])
    for control in ("dynamic_unserialised", "dynamic_owned"):
        c = table.get(control, {})
        gate[f"{control}_faults"] = c.get("faults")
        gate[f"fisher_{control}_vs_static"] = fisher(c.get("faults", 0), c.get("children", 0),
                                                     s.get("faults", 0), s.get("children", 0))
        if not complete:
            verdict = "incomplete"
        elif gate["static_manipulation_failures"]:
            verdict = "invalid_static_manipulation"
        elif s["faults"] == 0 and c.get("faults", 0) >= 1:
            verdict = "supported"
        elif s["faults"] == 0:
            verdict = "inconclusive_control_did_not_reproduce"
        else:
            verdict = "not_supported"
        gate[f"verdict_control_{control}"] = verdict
    gate["verdict"] = gate[f"verdict_control_{PROTOCOL['decision_rule']['primary_control']}"]
    summary = {"schema": "bridgestan-windows-root-cause-v4-summary",
               "planned_children": len(planned), "recorded_children": len(records),
               "missing_records": sorted(planned - {r["case_id"] for r in records}),
               "arms": table, "gate": gate, "event_1000_attributed": len(by_case),
               "event_1000_unattributed": unattributed}
    (ART / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    for name, arm in sorted(table.items()):
        log(f"{name:21s} n={arm['children']:4d} faults={arm['faults']:3d} "
            f"heap={arm['heap_corruption']:3d} ev1000={arm['event_1000']:3d} "
            f"hidden0={arm['hidden_exit0_faults']} manip_fail={len(arm['manipulation_failures'])} "
            f"ub95={arm['upper95_fault_rate']:.5f}")
    log(f"gate: {json.dumps(gate)}")
    log(f"unattributed events: {len(unattributed)}")
    return summary


# ----------------------------------------------------------- verify/probe ---

def verify() -> dict:
    problems = []
    assets = [(PROTOCOL["data"]["path"], PROTOCOL["data"]["sha256"])]
    for arm in PROTOCOL["arms"].values():
        assets += [(arm["model"], arm["model_sha256"]), (arm["preload"], arm["preload_sha256"])]
    for path, want in assets:
        if not Path(path).exists():
            problems.append(f"missing {path}")
        elif sha256(Path(path)) != want:
            problems.append(f"sha256 mismatch {path}")
    manifest = ART / "build-manifest.json"
    if not manifest.exists():
        problems.append("child not built; run build_child.py")
    else:
        digest = json.loads(manifest.read_text(encoding="utf-8"))["child_exe"]["sha256"]
        for arm in PROTOCOL["arms"]:
            exe = exe_for(arm)
            if not exe.exists() or sha256(exe) != digest:
                problems.append(f"{arm}: exe missing or differs from manifest")
            elif sorted(p.name for p in exe.parent.iterdir()) != [EXE_NAME]:
                problems.append(f"{arm}: launch directory is not exe-only")
    result = {"planned_children": len(cells()), "problems": problems}
    log(json.dumps(result, indent=2))
    if problems:
        sys.exit(1)
    return result


def probe() -> None:
    env = base_environment()
    results = {}
    for name, arm in PROTOCOL["arms"].items():
        cmd = ps_command(exe_for(name), ["probe", name, arm["model"], PROTOCOL["data"]["path"],
                                         arm["preload"]])
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(HERE),
                              timeout=TIMEOUT)
        try:
            report = json.loads(proc.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            report = None
        mods = (report or {}).get("loaded_runtime_modules")
        ok = manipulation_ok(mods, arm["expect_runtime"]) is True
        results[name] = {"returncode": rc_forms(proc.returncode), "stderr": proc.stderr,
                         "report": report, "matches_expectation": ok}
        log(f"{name}: rc={proc.returncode} matches_expectation={ok}")
        for mod, info in (mods or {}).items():
            log(f"    {mod}: {(info or {}).get('path') if info else None}")
    for child_pid_dir in TEMP.glob("wp50d-unserialised-*"):
        shutil.rmtree(child_pid_dir, ignore_errors=True)
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
        if rec.get("process_fault") or i % 50 == 0:
            rc = (rec.get("launcher_return_code") or {}).get("hex_32")
            flag = f" FAULT rc={rc} last={rec.get('last_heartbeat')}" if rec.get("process_fault") else ""
            log(f"[{i}/{len(plan)}] {rec['case_id']}{flag}")
    time.sleep(PROTOCOL["event_settle_seconds"])
    events = capture_events(first_ms, int(time.time() * 1000))
    (ART / "windows-events.json").write_text(json.dumps(events, indent=2) + "\n", encoding="utf-8")
    analyze()


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    {"verify": verify, "probe": probe, "run": run, "analyze": analyze}.get(
        command, lambda: sys.exit(__doc__))()
