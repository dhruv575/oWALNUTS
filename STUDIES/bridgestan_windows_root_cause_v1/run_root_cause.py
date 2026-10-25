#!/usr/bin/env python3
"""WP50 Windows BridgeStan heap-corruption root-cause orchestrator.

    python run_root_cause.py verify --binary target/release/<bin>.exe
    python run_root_cause.py run    --binary target/release/<bin>.exe
    python run_root_cause.py analyze

The frozen matrix is `protocol.json`. Each child is launched sequentially with
a durable exclusive pre-launch marker; an existing process record or an orphan
marker is never relaunched (failures and interruptions are results). The parent
records the Windows return code in raw/signed/unsigned/hex form, timeout state,
stdout/stderr, and the child's atomic heartbeat sequence. This is a process
diagnostic only; outputs are not posterior evidence.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
ART = HERE / "artifacts"
LAUNCHES = ART / "launches"
PROCESSES = ART / "processes"
RAW = ART / "raw"
HEARTBEATS = ART / "heartbeats"
STDOUT = ART / "stdout"
STDERR = ART / "stderr"

PRELOAD = PROTOCOL["preload"]
TIMEOUT = PROTOCOL["timeout_seconds_per_child"]
HEAP_CORRUPTION = "0xC0000374"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def return_code_forms(code: int) -> dict:
    unsigned = code & 0xFFFFFFFF
    signed = unsigned - (1 << 32) if unsigned >= (1 << 31) else unsigned
    return {
        "raw": code,
        "signed_32": signed,
        "unsigned_32": unsigned,
        "hex_32": f"0x{unsigned:08X}",
    }


def child_list() -> list[dict]:
    children: list[dict] = []
    for arm in PROTOCOL["arms"]:
        name = arm["arm"]
        for seed in arm["seeds"]:
            children.append(
                {
                    "case_id": f"{name}-{seed}",
                    "arm": name,
                    "binary_arm": arm["binary_arm"],
                    "model": arm["model"],
                    "data": arm["data"],
                    "seed": seed,
                    "replicas": arm["replicas"],
                    "threads": arm["threads"],
                    "rounds": arm["rounds"],
                    "calls_per_thread": arm["calls_per_thread"],
                    "radius": arm["radius"],
                }
            )
    return children


def read_heartbeats(hb_dir: Path) -> list[dict]:
    events = []
    if hb_dir.is_dir():
        for path in sorted(hb_dir.glob("[0-9]*.json")):
            try:
                ev = json.loads(path.read_text(encoding="utf-8"))
                ev["_file"] = path.name
                events.append(ev)
            except (OSError, json.JSONDecodeError):
                pass
    events.sort(key=lambda e: e.get("sequence", 1 << 30))
    return events


def launch_child(binary: Path, child: dict) -> dict:
    case = child["case_id"]
    marker = LAUNCHES / f"{case}.json"
    record = PROCESSES / f"{case}.json"
    if record.exists():
        return json.loads(record.read_text(encoding="utf-8"))
    if marker.exists():
        # Orphan marker: a prior attempt did not record a process. Never relaunch.
        rec = {
            "schema": "bridgestan-windows-root-cause-v1-process",
            "case_id": case,
            "status": "interrupted_not_relaunched",
            **child,
        }
        record.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        return rec

    for d in (LAUNCHES, PROCESSES, RAW, STDOUT, STDERR, HEARTBEATS):
        d.mkdir(parents=True, exist_ok=True)
    # Exclusive durable marker before launch.
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"case_id": case, "launch_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **child}, fh, indent=2)

    hb_dir = HEARTBEATS / case
    out = RAW / f"{case}.json"
    preload_arg = ";".join(PRELOAD) if PRELOAD else "none"
    cmd = [
        str(binary),
        child["binary_arm"],
        str(HERE / child["model"]),
        str(HERE / child["data"]),
        str(child["seed"]),
        str(child["replicas"]),
        str(child["threads"]),
        str(child["rounds"]),
        str(child["calls_per_thread"]),
        str(child["radius"]),
        str(hb_dir),
        str(out),
        preload_arg,
    ]
    started = time.time()
    timed_out = False
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT, cwd=str(HERE)
        )
        code = proc.returncode
        stdout, stderr = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        code = None
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
    duration = time.time() - started

    (STDOUT / f"{case}.txt").write_text(stdout or "", encoding="utf-8")
    (STDERR / f"{case}.txt").write_text(stderr or "", encoding="utf-8")
    hbs = read_heartbeats(hb_dir)
    raw_result = None
    if out.exists():
        try:
            raw_result = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw_result = None

    expected_last = "process/complete"
    last_hb = f"{hbs[-1]['stage']}/{hbs[-1]['boundary']}" if hbs else None
    heartbeat_complete = last_hb == expected_last
    rc_forms = return_code_forms(code) if code is not None else None
    silent = (not stdout) and (not stderr)
    success = (
        (not timed_out)
        and code == 0
        and raw_result is not None
        and raw_result.get("status") == "ok"
        and heartbeat_complete
    )
    rec = {
        "schema": "bridgestan-windows-root-cause-v1-process",
        "case_id": case,
        **child,
        "duration_seconds": duration,
        "timed_out": timed_out,
        "return_code": rc_forms,
        "raw_output_exists": raw_result is not None,
        "raw_status": raw_result.get("status") if raw_result else None,
        "heartbeat_count": len(hbs),
        "last_heartbeat": last_hb,
        "heartbeat_complete": heartbeat_complete,
        "stdout": stdout,
        "stderr": stderr,
        "silent": silent,
        "process_success": success,
        "process_fault": not success,
        "is_heap_corruption": bool(rc_forms and rc_forms["hex_32"] == HEAP_CORRUPTION),
        "status": "ok" if success else "fault",
    }
    record.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    # Clean resident replica copies left by this child.
    for d in Path(os.environ.get("TEMP", "/tmp")).glob(f"wp50-replicas-*-{child['seed']}"):
        shutil.rmtree(d, ignore_errors=True)
    return rec


def cmd_run(binary: Path) -> None:
    children = child_list()
    log(f"frozen matrix: {len(children)} children across {len(PROTOCOL['arms'])} arms")
    for i, child in enumerate(children, 1):
        rec = launch_child(binary, child)
        flag = ""
        if rec.get("process_fault"):
            flag = f" FAULT {rec.get('return_code', {}).get('hex_32', '?')}"
        log(f"[{i}/{len(children)}] {rec['case_id']}: {rec['status']}{flag}")
    cmd_analyze()


def cmd_analyze() -> None:
    children = child_list()
    by_arm: dict[str, dict] = {}
    for child in children:
        rec_path = PROCESSES / f"{child['case_id']}.json"
        arm = child["arm"]
        a = by_arm.setdefault(
            arm,
            {
                "arm": arm,
                "planned": 0,
                "recorded": 0,
                "success": 0,
                "faults": 0,
                "heap_corruption": 0,
                "timeouts": 0,
                "silent_faults": 0,
                "missing_raw_on_fault": 0,
                "last_heartbeat_on_fault": {},
                "fault_cases": [],
            },
        )
        a["planned"] += 1
        if not rec_path.exists():
            continue
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        a["recorded"] += 1
        if rec.get("process_success"):
            a["success"] += 1
        else:
            a["faults"] += 1
            a["fault_cases"].append(rec["case_id"])
            if rec.get("is_heap_corruption"):
                a["heap_corruption"] += 1
            if rec.get("timed_out"):
                a["timeouts"] += 1
            if rec.get("silent"):
                a["silent_faults"] += 1
            if not rec.get("raw_output_exists"):
                a["missing_raw_on_fault"] += 1
            lh = rec.get("last_heartbeat")
            a["last_heartbeat_on_fault"][lh] = a["last_heartbeat_on_fault"].get(lh, 0) + 1

    summary = {
        "schema": "bridgestan-windows-root-cause-v1-summary",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "arms": by_arm,
    }
    ART.mkdir(exist_ok=True)
    (ART / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log("arm counts (recorded/planned  success  faults  heap0xC0000374):")
    for arm, a in by_arm.items():
        log(
            f"  {arm:22s} {a['recorded']:3d}/{a['planned']:<3d}  ok={a['success']:<4d} "
            f"fault={a['faults']:<4d} heap={a['heap_corruption']:<4d} "
            f"last_hb={a['last_heartbeat_on_fault']}"
        )


def cmd_verify(binary: Path) -> None:
    problems = []
    import hashlib

    if not binary.exists():
        problems.append(f"binary missing: {binary}")
    checks = [("model", HERE / PROTOCOL["model"]["path"], PROTOCOL["model"]["sha256"]),
              ("data", HERE / PROTOCOL["data"]["path"], PROTOCOL["data"]["sha256"])]
    for label, path, sha in checks:
        if not path.exists():
            problems.append(f"{label} missing: {path}")
            continue
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        if got != sha:
            problems.append(f"{label} sha256 mismatch: {got} != {sha}")
    for arm in PROTOCOL["arms"]:
        for key in ("model", "data"):
            if not (HERE / arm[key]).exists():
                problems.append(f"{arm['arm']} {key} missing: {arm[key]}")
    for dep in PRELOAD:
        if not Path(dep).exists():
            problems.append(f"preload missing: {dep}")
    total = sum(len(a["seeds"]) for a in PROTOCOL["arms"])
    log(f"planned children: {total}; timeout/child: {TIMEOUT}s")
    if problems:
        for p in problems:
            log(f"PROBLEM: {p}")
        sys.exit(1)
    log("verify: assets present and hashes match")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    cmd = sys.argv[1]
    binary = None
    if "--binary" in sys.argv:
        binary = Path(sys.argv[sys.argv.index("--binary") + 1]).resolve()
    if cmd == "verify":
        cmd_verify(binary)
    elif cmd == "run":
        if not binary:
            sys.exit("run requires --binary")
        cmd_run(binary)
    elif cmd == "analyze":
        cmd_analyze()
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
