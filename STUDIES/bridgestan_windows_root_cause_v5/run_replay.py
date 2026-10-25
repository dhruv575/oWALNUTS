#!/usr/bin/env python3
"""WP50E deterministic replay orchestrator.

    python run_replay.py verify    # assets, binaries, exe-only launch dirs
    python run_replay.py run       # the one permitted launch of the frozen order
    python run_replay.py analyze   # regenerate the summary from immutable records

Strictly sequential; one process at a time; PowerShell launch under the
registry PATH (as WP50D). A durable launch marker precedes each process; no
relaunch. Failures are results. Diagnostic only; not posterior evidence.
"""
from __future__ import annotations

import hashlib
import json
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
DIRS = {k: ART / k for k in ("launches", "processes", "raw", "heartbeats")}
POWERSHELL = PROTOCOL["launcher"]["executable"]
TIMEOUT = PROTOCOL["timeout_seconds_per_child"]
ASSETS = PROTOCOL["assets"]
TEMP = Path(os.environ.get("TEMP", ""))
NEEDLE = "kernel attempted a nonfinite target position"
WP50D_NEEDLE = NEEDLE + " (chain 2, transition 9)"
SHELL_VARS = ("MSYSTEM", "MSYSTEM_PREFIX", "MSYSTEM_CHOST", "MSYSTEM_CARCH", "MINGW_PREFIX",
              "MINGW_CHOST", "MINGW_PACKAGE_PREFIX", "ORIGINAL_PATH", "ORIGINAL_TEMP",
              "ORIGINAL_TMP", "EXEPATH", "PLINK_PROTOCOL", "SHLVL", "OLDPWD", "PWD",
              "_", "TERM", "SHELL", "HOME", "MANPATH", "INFOPATH", "PKG_CONFIG_PATH",
              "ACLOCAL_PATH", "CONFIG_SITE", "LANG", "DISPLAY", "HOSTNAME", "TMPDIR")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exe_for(arm: dict) -> Path:
    if arm["exe"] == "wp50d":
        return HERE / "build" / "arms" / "wp50d" / "bridgestan-windows-root-cause-v4.exe"
    return HERE / "build" / "arms" / f"v5_{arm['dispatch']}" / "bridgestan-windows-root-cause-v5.exe"


def rc_forms(code: int | None) -> dict | None:
    if code is None:
        return None
    unsigned = code & 0xFFFFFFFF
    return {"raw": code, "unsigned_32": unsigned, "hex_32": f"0x{unsigned:08X}"}


def base_environment() -> dict:
    script = ("[Environment]::GetEnvironmentVariable('Path','Machine') + ';' + "
              "[Environment]::GetEnvironmentVariable('Path','User')")
    path = subprocess.check_output([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command",
                                    script], text=True).strip()
    env = {k: v for k, v in os.environ.items() if k.upper() not in SHELL_VARS}
    env["PATH"] = path
    env["RUST_BACKTRACE"] = "0"
    return env


def ps_command(exe: Path, args: list[str]) -> list[str]:
    quoted = " ".join("'" + a.replace("'", "''") + "'" for a in args)
    return [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-Command", f"& '{exe}' {quoted}; exit $LASTEXITCODE"]


def cells() -> list[dict]:
    out = []
    for item in PROTOCOL["order"]:
        name, rep = item.split("#")
        out.append({"case_id": f"{name}-{rep}", "arm": name, "rep": int(rep),
                    **PROTOCOL["arms"][name]})
    return out


def command_for(cell: dict) -> list[str]:
    out = DIRS["raw"] / f"{cell['case_id']}.json"
    if cell["exe"] == "wp50d":
        args = ["static_unserialised", ASSETS["model"], ASSETS["data"], ASSETS["preload"],
                str(PROTOCOL["seed"]), str(DIRS["heartbeats"] / cell["case_id"]), str(out)]
    else:
        args = [cell["dispatch"], cell["policy"], ASSETS["model"], ASSETS["data"],
                ASSETS["preload"], str(out)]
    return ps_command(exe_for(cell), args)


def launch(cell: dict, env: dict) -> dict:
    record = DIRS["processes"] / f"{cell['case_id']}.json"
    marker = DIRS["launches"] / f"{cell['case_id']}.json"
    if record.exists():
        return json.loads(record.read_text(encoding="utf-8"))
    if marker.exists():
        rec = {**cell, "status": "interrupted_not_relaunched"}
        record.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        return rec
    cmd = command_for(cell)
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({**cell, "command": cmd, "launch_unix_ms": int(time.time() * 1000)}, handle)
    started = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                            cwd=str(HERE), text=True, encoding="utf-8", errors="replace")
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        timed_out = True
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        stdout, stderr = proc.communicate()
    ended = time.time()
    out = DIRS["raw"] / f"{cell['case_id']}.json"
    raw = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
    pid = (raw or {}).get("pid")
    if pid is None and cell["exe"] == "wp50d":
        beats = sorted((DIRS["heartbeats"] / cell["case_id"]).glob("[0-9]*.json"))
        if beats:
            pid = json.loads(beats[0].read_text(encoding="utf-8")).get("pid")
    if pid is not None:
        shutil.rmtree(TEMP / f"wp50d-unserialised-{pid}", ignore_errors=True)
        for directory in (TEMP / "owalnuts-bridgestan-cache-v1").glob(f"process-{pid}-*"):
            shutil.rmtree(directory, ignore_errors=True)
    rec = {"schema": "bridgestan-windows-root-cause-v5-process", **cell, "command": cmd,
           "child_pid": pid, "started_unix_ms": int(started * 1000),
           "ended_unix_ms": int(ended * 1000), "duration_seconds": ended - started,
           "timed_out": timed_out, "launcher_return_code": rc_forms(None if timed_out else proc.returncode),
           "stdout": stdout, "stderr": stderr, "raw_output_exists": raw is not None}
    record.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    return rec


EVENT_SCRIPT = r"""
$start = [DateTime]::Parse('{start}').ToLocalTime()
$end = [DateTime]::Parse('{end}').ToLocalTime()
$events = Get-WinEvent -FilterHashtable @{{LogName='Application'; Id=1000; StartTime=$start; EndTime=$end}} -ErrorAction SilentlyContinue
$rows = foreach ($e in $events) {{
  [pscustomobject]@{{ id=$e.Id; record_id=$e.RecordId; time_utc=$e.TimeCreated.ToUniversalTime().ToString('o');
    properties=@($e.Properties | ForEach-Object {{ [string]$_.Value }}) }}
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
    return {"window_utc": [iso(start_ms - 60_000), iso(end_ms + 20_000)],
            "returncode": proc.returncode, "stderr": proc.stderr, "events": rows}


def crash_events(records: list[dict], events: dict) -> dict:
    """Event 1000 attributed by exe path + PID + launch window (WP50D rule)."""
    out = {}
    for event in events.get("events", []):
        props = event.get("properties") or []
        if len(props) < 11:
            continue
        when = datetime.fromisoformat(event["time_utc"][:26]).replace(tzinfo=timezone.utc).timestamp()
        for rec in records:
            try:
                pid = int(props[8])
            except ValueError:
                continue
            if (props[10].lower() == str(exe_for(rec)).lower() and rec.get("child_pid") == pid
                    and rec["started_unix_ms"] / 1000 - 1 <= when <= rec["ended_unix_ms"] / 1000 + 5):
                out[rec["case_id"]] = {"exception_code": props[6], "module": props[3]}
    return out


def reproduced_v5(raw: dict | None) -> bool:
    e = (raw or {}).get("error") or {}
    return ((raw or {}).get("status") == "sampler_error" and e.get("kind") == "Numerical"
            and NEEDLE in e.get("display", "") and e.get("chain") == 2 and e.get("transition") == 9)


def chain_stream(raw: dict | None, chain: int = 2) -> dict | None:
    for s in (raw or {}).get("chain_streams", []):
        if s["chain"] == chain:
            return s
    return None


def analyze() -> dict:
    records = {json.loads(p.read_text(encoding="utf-8"))["case_id"]: json.loads(p.read_text(encoding="utf-8"))
               for p in sorted(DIRS["processes"].glob("*.json"))}
    raws = {c: (json.loads((DIRS["raw"] / f"{c}.json").read_text(encoding="utf-8"))
                if (DIRS["raw"] / f"{c}.json").exists() else None) for c in records}
    events_path = ART / "windows-events.json"
    events = json.loads(events_path.read_text(encoding="utf-8")) if events_path.exists() else {"events": []}
    crashes = crash_events(list(records.values()), events)
    rows = {}
    for case, rec in records.items():
        raw = raws[case]
        rc = (rec.get("launcher_return_code") or {}).get("unsigned_32")
        row = {"arm": rec["arm"], "rep": rec["rep"], "launcher_rc": rc, "timed_out": rec.get("timed_out"),
               "event_1000": crashes.get(case), "duration_seconds": rec.get("duration_seconds")}
        if rec["exe"] == "wp50d":
            row["reproduced"] = rc == 1 and WP50D_NEEDLE in (rec.get("stderr") or "")
            row["stderr"] = rec.get("stderr")
            row["crash"] = bool(crashes.get(case)) or rec.get("timed_out") or rc not in (0, 1)
        else:
            s = chain_stream(raw)
            row.update({
                "reproduced": reproduced_v5(raw), "status": (raw or {}).get("status"),
                "error": (raw or {}).get("error"), "target_layer": (raw or {}).get("target_layer"),
                "chain2_stream": None if s is None else {k: s[k] for k in (
                    "observations", "hash_fnv1a64", "last_transition", "last_target_call")},
                "chain2_first_kernel_nonfinite_target_call": None if s is None or not s.get("first_kernel_nonfinite")
                else s["first_kernel_nonfinite"]["target_call"],
                "starts_bits": (raw or {}).get("starts_bits"),
                "draws_fingerprint": (raw or {}).get("draws_fingerprint_fnv1a64"),
                "nonfinite_position_rejections_per_chain": (raw or {}).get("nonfinite_position_rejections_per_chain"),
                "effective_replicas": (raw or {}).get("effective_replicas"),
                "execution": (raw or {}).get("execution"),
                "crash": bool(crashes.get(case)) or bool(rec.get("timed_out")) or rc != 0 or raw is None,
            })
        rows[case] = row
    gating = [r for c, r in rows.items() if PROTOCOL["arms"][r["arm"]]["gating"]]
    a = [r for r in gating if r["arm"] == "A_owned_abort"]
    b = [r for r in gating if r["arm"] == "B_unserialised_abort"]
    signature = lambda r: json.dumps([r.get("chain2_stream"), r.get("chain2_first_kernel_nonfinite_target_call"),
                                      r.get("starts_bits")], sort_keys=True)
    first_kernel = {}
    for case, raw in raws.items():
        s = chain_stream(raw)
        if s and s.get("first_kernel_nonfinite") is not None:
            first_kernel[case] = json.dumps(s["first_kernel_nonfinite"], sort_keys=True)
    identity = (len(gating) == 6 and len({signature(r) for r in gating}) == 1
                and len({first_kernel.get(c) for c, r in rows.items()
                         if PROTOCOL["arms"][r["arm"]]["gating"]}) == 1)
    any_crash = any(r["crash"] for r in gating)
    if len(gating) == 6 and all(r["reproduced"] for r in gating) and identity and not any_crash:
        verdict = "DETERMINISTIC_DISPATCH_INDEPENDENT"
    elif len(gating) == 6 and all(r["reproduced"] for r in b) and not any(r["reproduced"] for r in a):
        verdict = "NOT_ESTABLISHED_UNSERIALISED_ONLY"
    elif len(gating) == 6 and not any(r["reproduced"] for r in gating):
        verdict = "NOT_ESTABLISHED_NOT_REPRODUCED"
    else:
        verdict = "NOT_ESTABLISHED_NONDETERMINISTIC"
    reproducing = [r for r in gating if r["reproduced"]]
    integration = None
    if reproducing:
        clean = all(r["error"]["kind"] == "Numerical" and not r["error"]["has_target_source"]
                    and r["target_layer"]["nonfinite_inputs"] == 0 for r in reproducing)
        integration = "not_an_integration_bug" if clean else "possible_integration_bug"
    c = [r for r in rows.values() if r["arm"] == "C_wp50d_original"]
    d = rows.get("D_owned_reject-1")
    e = rows.get("E_unserialised_reject-1")
    summary = {
        "schema": "bridgestan-windows-root-cause-v5-summary", "verdict": verdict,
        "gating_reproduced": f"{sum(r['reproduced'] for r in gating)}/{len(gating)}",
        "A_reproduced": f"{sum(r['reproduced'] for r in a)}/{len(a)}",
        "B_reproduced": f"{sum(r['reproduced'] for r in b)}/{len(b)}",
        "stream_identity": identity, "gating_crash": any_crash,
        "C_wp50d_reproduced": f"{sum(r['reproduced'] for r in c)}/{len(c)}",
        "integration_question": integration,
        "reject_policy": {
            "D_status": (d or {}).get("status"), "E_status": (e or {}).get("status"),
            "D_rejections": (d or {}).get("nonfinite_position_rejections_per_chain"),
            "E_rejections": (e or {}).get("nonfinite_position_rejections_per_chain"),
            "draws_equal": bool(d and e and d.get("draws_fingerprint")
                                and d.get("draws_fingerprint") == e.get("draws_fingerprint")),
        },
        "rows": rows,
    }
    (ART / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    for case, r in rows.items():
        log(f"{case:26s} reproduced={r['reproduced']} rc={r['launcher_rc']} crash={r['crash']} "
            f"stream={r.get('chain2_stream')}")
    log(f"verdict={verdict} identity={identity} C={summary['C_wp50d_reproduced']} "
        f"integration={integration} reject={summary['reject_policy']}")
    return summary


def verify() -> dict:
    problems = []
    for key in ("model", "preload", "data", "wp50d_exe"):
        path = Path(ASSETS[key])
        if not path.exists() or sha256(path) != ASSETS[f"{key}_sha256"]:
            problems.append(f"{key} missing or hash mismatch")
    manifest_path = ART / "build-manifest.json"
    if not manifest_path.exists():
        problems.append("not built")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name, info in manifest["arms"].items():
            exe = Path(info["exe"])
            if not exe.exists() or sha256(exe) != info["sha256"]:
                problems.append(f"{name} exe differs")
            elif len(list(exe.parent.iterdir())) != 1:
                problems.append(f"{name} launch dir not exe-only")
    result = {"planned": len(cells()), "problems": problems}
    log(json.dumps(result))
    if problems:
        sys.exit(1)
    return result


def run() -> None:
    for directory in DIRS.values():
        directory.mkdir(parents=True, exist_ok=True)
    if any(DIRS["launches"].iterdir()):
        raise SystemExit("launch markers already exist; the single permitted launch was used")
    verify()
    env = base_environment()
    first = int(time.time() * 1000)
    for i, cell in enumerate(cells(), 1):
        rec = launch(cell, env)
        log(f"[{i}/{len(cells())}] {cell['case_id']} rc={(rec.get('launcher_return_code') or {}).get('hex_32')}")
    time.sleep(PROTOCOL["event_settle_seconds"])
    (ART / "windows-events.json").write_text(
        json.dumps(capture_events(first, int(time.time() * 1000)), indent=2) + "\n", encoding="utf-8")
    analyze()


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    {"verify": verify, "run": run, "analyze": analyze}.get(command, lambda: sys.exit(__doc__))()
