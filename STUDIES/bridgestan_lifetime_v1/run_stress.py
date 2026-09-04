#!/usr/bin/env python3
"""Run the frozen BridgeStan lifetime parent/child diagnostic."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PROTOCOL_PATH = HERE / "protocol.json"
PROTOCOL = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
ARTIFACTS = HERE / "artifacts"
PROCESSES = ARTIFACTS / "processes"
RAW = ARTIFACTS / "raw"
HEARTBEATS = ARTIFACTS / "heartbeats"
STDOUT = ARTIFACTS / "stdout"
STDERR = ARTIFACTS / "stderr"
LAUNCHES = ARTIFACTS / "launches"
BINARY_MANIFEST = ARTIFACTS / "binaries.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def write_json(path: Path, value: Any) -> None:
    atomic_write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def cases() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for model in PROTOCOL["models"]:
        seeds = range(int(model["seed_start"]), int(model["seed_end"]) + 1)
        expanded = [{**model, "seed": seed} for seed in seeds]
        if len(expanded) != int(model["repetitions"]):
            raise RuntimeError(f"{model['shape']}: seed range/repetition mismatch")
        result.extend(expanded)
    expected = int(PROTOCOL["execution"]["children_per_mode"])
    if len(result) != expected:
        raise RuntimeError(f"protocol expands to {len(result)} cases, expected {expected}")
    seeds = [case["seed"] for case in result]
    forbidden = PROTOCOL["forbidden_evidence"]
    if seeds != list(
        range(
            int(forbidden["diagnostic_seed_minimum"]),
            int(forbidden["diagnostic_seed_maximum"]) + 1,
        )
    ):
        raise RuntimeError("diagnostic seeds are not one contiguous frozen range")
    return result


def binary_details(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "exists": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else None,
        "sha256": sha256(path) if path.is_file() else None,
    }


def verify_inputs(fixed: Path, baseline: Path) -> dict[str, Any]:
    errors: list[str] = []
    observed_models: list[dict[str, Any]] = []
    cases()
    for row in PROTOCOL["models"]:
        observed: dict[str, Any] = {"shape": row["shape"]}
        for kind in ("model", "data"):
            expected = row[kind]
            path = Path(expected["path"])
            actual = {
                "path": str(path),
                "exists": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else None,
                "sha256": sha256(path) if path.is_file() else None,
            }
            actual["matches_protocol"] = (
                actual["exists"]
                and actual["bytes"] == expected["bytes"]
                and actual["sha256"] == expected["sha256"]
            )
            if not actual["matches_protocol"]:
                errors.append(f"{row['shape']} {kind} does not match protocol")
            observed[kind] = actual
        observed_models.append(observed)
    binaries = {
        "fixed": binary_details(fixed),
        "baseline": binary_details(baseline),
    }
    for mode, details in binaries.items():
        if not details["exists"]:
            errors.append(f"{mode} binary is missing: {details['path']}")
    return {
        "verified": not errors,
        "errors": errors,
        "protocol_sha256": sha256(PROTOCOL_PATH),
        "models": observed_models,
        "binaries": binaries,
    }


def freeze_binary_manifest(fixed: Path, baseline: Path) -> dict[str, Any]:
    verification = verify_inputs(fixed, baseline)
    if not verification["verified"]:
        raise RuntimeError("; ".join(verification["errors"]))
    manifest = {
        "schema": "bridgestan-lifetime-v1-binaries",
        "captured_before_execution_utc": utc_now(),
        "protocol_sha256": verification["protocol_sha256"],
        "fixed_source_commit": PROTOCOL["fixed_source_commit"],
        "baseline_source_commit": PROTOCOL["baseline_source_commit"],
        "binaries": verification["binaries"],
        "models": verification["models"],
    }
    if BINARY_MANIFEST.exists():
        existing = json.loads(BINARY_MANIFEST.read_text(encoding="utf-8"))
        if existing["binaries"] != manifest["binaries"]:
            raise RuntimeError("binary manifest exists but binary identities changed")
        return existing
    write_json(BINARY_MANIFEST, manifest)
    return manifest


def return_code_forms(code: int | None) -> dict[str, int | str | None]:
    if code is None:
        return {"raw": None, "signed_32": None, "unsigned_32": None, "hex_32": None}
    unsigned = code & 0xFFFF_FFFF
    signed = unsigned - (1 << 32) if unsigned >= (1 << 31) else unsigned
    return {
        "raw": code,
        "signed_32": signed,
        "unsigned_32": unsigned,
        "hex_32": f"0x{unsigned:08X}",
    }


def case_id(mode: str, case: dict[str, Any]) -> str:
    return f"{mode}-{case['shape']}-{case['seed']}"


def expected_heartbeats() -> list[tuple[str, str]]:
    return [
        ("process", "start"),
        ("load", "before"),
        ("load", "after"),
        ("initialization", "before"),
        ("initialization", "after"),
        ("sampling", "before"),
        ("sampling", "after"),
        ("result_write", "before"),
        ("result_write", "after"),
        ("drop", "before"),
        ("drop", "after"),
        ("process", "complete"),
    ]


def assess_heartbeats(path: Path) -> tuple[bool, list[dict[str, Any]], list[str]]:
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    for event_path in sorted(path.glob("*.json")):
        try:
            event = json.loads(event_path.read_text(encoding="utf-8"))
            event["_file"] = event_path.name
            events.append(event)
        except Exception as error:  # malformed diagnostic output is a result
            errors.append(f"{event_path.name}: {error}")
    sequences = [event.get("sequence") for event in events]
    if sequences != list(range(len(events))):
        errors.append("heartbeat sequence is not contiguous")
    actual = [(event.get("stage"), event.get("boundary")) for event in events]
    if actual != expected_heartbeats():
        errors.append(
            f"heartbeat sequence differs: observed {len(actual)}, "
            f"expected {len(expected_heartbeats())}"
        )
    return not errors, events, errors


def interrupted_record(mode: str, case: dict[str, Any], marker: Path) -> dict[str, Any]:
    reason = "prelaunch marker exists without process record; no rerun is permitted"
    return {
        "schema": "bridgestan-lifetime-v1-process",
        "case_id": case_id(mode, case),
        "mode": mode,
        "shape": case["shape"],
        "seed": case["seed"],
        "status": "orchestrator_interrupted",
        "success": False,
        "fault": True,
        "failure_reasons": [reason],
        "return_code": return_code_forms(None),
        "timed_out": None,
        "raw_output_exists": None,
        "heartbeat_complete": False,
        "heartbeats": [],
        "last_heartbeat": None,
        "launch_marker": marker.relative_to(HERE).as_posix(),
    }


def run_case(mode: str, binary: Path, case: dict[str, Any]) -> dict[str, Any]:
    identifier = case_id(mode, case)
    record_path = PROCESSES / f"{identifier}.json"
    marker_path = LAUNCHES / f"{identifier}.json"
    if record_path.exists():
        return json.loads(record_path.read_text(encoding="utf-8"))
    if marker_path.exists():
        record = interrupted_record(mode, case, marker_path)
        write_json(record_path, record)
        return record

    raw_path = RAW / f"{identifier}.json"
    heartbeat_path = HEARTBEATS / identifier
    stdout_path = STDOUT / f"{identifier}.txt"
    stderr_path = STDERR / f"{identifier}.txt"
    command = [
        str(binary.resolve()),
        case["shape"],
        case["model"]["path"],
        case["data"]["path"],
        str(case["seed"]),
        str(heartbeat_path),
        str(raw_path),
    ]
    started_utc = utc_now()
    write_json(
        marker_path,
        {
            "case_id": identifier,
            "started_utc": started_utc,
            "binary_sha256": sha256(binary),
            "command": command,
        },
    )
    begin = time.perf_counter()
    code: int | None = None
    timed_out = False
    stdout = ""
    stderr = ""
    try:
        completed = subprocess.run(
            command,
            cwd=HERE,
            capture_output=True,
            timeout=int(PROTOCOL["execution"]["timeout_seconds_per_child"]),
            check=False,
        )
        code = completed.returncode
        stdout = completed.stdout.decode("utf-8", errors="replace")
        stderr = completed.stderr.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired as error:
        timed_out = True
        stdout = (error.stdout or b"").decode("utf-8", errors="replace")
        stderr = (error.stderr or b"").decode("utf-8", errors="replace")
    duration = time.perf_counter() - begin
    atomic_write(stdout_path, stdout)
    atomic_write(stderr_path, stderr)

    raw_result: dict[str, Any] | None = None
    raw_error: str | None = None
    if raw_path.is_file():
        try:
            raw_result = json.loads(raw_path.read_text(encoding="utf-8"))
        except Exception as error:  # malformed diagnostic output is a result
            raw_error = str(error)
    heartbeat_complete, events, heartbeat_errors = assess_heartbeats(heartbeat_path)
    reasons: list[str] = []
    if timed_out:
        reasons.append("child timed out")
    if code != 0:
        reasons.append(f"child return code was {code!r}, not zero")
    if not raw_path.is_file():
        reasons.append("raw output is missing")
    elif raw_error:
        reasons.append(f"raw output is malformed: {raw_error}")
    elif raw_result is None or raw_result.get("status") != "ok":
        reasons.append("raw output status is not ok")
    elif not raw_result.get("all_retained_values_finite"):
        reasons.append("raw output contains nonfinite retained values")
    if not heartbeat_complete:
        reasons.append("required heartbeat sequence is incomplete")
    record = {
        "schema": "bridgestan-lifetime-v1-process",
        "case_id": identifier,
        "mode": mode,
        "shape": case["shape"],
        "seed": case["seed"],
        "replicas": 4,
        "threads": 4,
        "chains": 4,
        "warmup_per_chain": 4,
        "retained_per_chain": 4,
        "status": "ok" if not reasons else "fault",
        "success": not reasons,
        "fault": bool(reasons),
        "failure_reasons": reasons,
        "return_code": return_code_forms(code),
        "timed_out": timed_out,
        "duration_seconds": duration,
        "raw_output_exists": raw_path.is_file(),
        "raw_output_error": raw_error,
        "raw_result": raw_result,
        "heartbeat_complete": heartbeat_complete,
        "heartbeat_errors": heartbeat_errors,
        "heartbeats": events,
        "last_heartbeat": events[-1] if events else None,
        "stdout_path": stdout_path.relative_to(HERE).as_posix(),
        "stderr_path": stderr_path.relative_to(HERE).as_posix(),
        "stdout": stdout,
        "stderr": stderr,
        "started_utc": started_utc,
        "finished_utc": utc_now(),
        "diagnostic_only": True,
    }
    write_json(record_path, record)
    return record


def capture_windows_events(started_utc: str, finished_utc: str) -> dict[str, Any]:
    if os.name != "nt":
        return {"available": False, "reason": "not Windows", "events": []}
    script = (
        f"$s=[DateTimeOffset]::Parse('{started_utc}').LocalDateTime;"
        f"$e=[DateTimeOffset]::Parse('{finished_utc}').LocalDateTime;"
        "$x=Get-WinEvent -FilterHashtable "
        "@{LogName='Application';Id=1000,1001;StartTime=$s;EndTime=$e} "
        "-ErrorAction Stop | Select-Object TimeCreated,Id,ProviderName,ProcessId,Message;"
        "$x | ConvertTo-Json -Depth 4 -Compress"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    parsed: Any = []
    parse_error: str | None = None
    if completed.returncode == 0 and completed.stdout.strip():
        try:
            parsed = json.loads(completed.stdout)
            if isinstance(parsed, dict):
                parsed = [parsed]
        except json.JSONDecodeError as error:
            parse_error = str(error)
    return {
        "available": completed.returncode == 0 and parse_error is None,
        "return_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "parse_error": parse_error,
        "events": parsed,
    }


def load_records() -> dict[str, dict[str, Any]]:
    return {
        record["case_id"]: record
        for path in sorted(PROCESSES.glob("*.json"))
        for record in [json.loads(path.read_text(encoding="utf-8"))]
    }


def analyze() -> dict[str, Any]:
    records = load_records()
    planned = cases()
    expected_ids = [
        case_id(mode, case)
        for mode in PROTOCOL["execution"]["mode_order"]
        for case in planned
    ]
    missing = [identifier for identifier in expected_ids if identifier not in records]
    ordered = [records[identifier] for identifier in expected_ids if identifier in records]
    by_mode: dict[str, Any] = {}
    for mode in PROTOCOL["execution"]["mode_order"]:
        mode_records = [record for record in ordered if record["mode"] == mode]
        by_mode[mode] = {
            "planned": len(planned),
            "recorded": len(mode_records),
            "successes": sum(bool(record["success"]) for record in mode_records),
            "faults": sum(bool(record["fault"]) for record in mode_records),
            "timeouts": sum(bool(record["timed_out"]) for record in mode_records),
            "missing_outputs": sum(
                record["raw_output_exists"] is False for record in mode_records
            ),
            "incomplete_heartbeats": sum(
                not bool(record["heartbeat_complete"]) for record in mode_records
            ),
            "by_shape": {
                shape: {
                    "planned": sum(case["shape"] == shape for case in planned),
                    "recorded": sum(record["shape"] == shape for record in mode_records),
                    "faults": sum(
                        record["shape"] == shape and bool(record["fault"])
                        for record in mode_records
                    ),
                }
                for shape in ("sblrc", "diamonds", "mesquite")
            },
        }

    comparable = 0
    mismatches: list[dict[str, Any]] = []
    for case in planned:
        baseline = records.get(case_id("baseline", case), {}).get("raw_result")
        fixed = records.get(case_id("fixed", case), {}).get("raw_result")
        if not isinstance(baseline, dict) or not isinstance(fixed, dict):
            continue
        comparable += 1
        left = baseline.get("sample_fingerprint_fnv1a64")
        right = fixed.get("sample_fingerprint_fnv1a64")
        if left != right:
            mismatches.append(
                {
                    "shape": case["shape"],
                    "seed": case["seed"],
                    "baseline": left,
                    "fixed": right,
                }
            )

    fixed = by_mode.get("fixed", {})
    fixed_complete = fixed.get("recorded") == len(planned)
    parity_complete = comparable == len(planned)
    accepted = (
        fixed_complete
        and fixed.get("faults") == 0
        and fixed.get("timeouts") == 0
        and fixed.get("missing_outputs") == 0
        and fixed.get("incomplete_heartbeats") == 0
        and parity_complete
        and not mismatches
    )
    n = int(fixed.get("recorded", 0))
    upper = 1.0 - math.pow(0.05, 1.0 / n) if n and fixed.get("faults") == 0 else None
    summary = {
        "schema": "bridgestan-lifetime-v1-summary",
        "generated_utc": utc_now(),
        "protocol_sha256": sha256(PROTOCOL_PATH),
        "planned_records": len(expected_ids),
        "recorded_records": len(ordered),
        "missing_records": missing,
        "by_mode": by_mode,
        "parity": {
            "planned": len(planned),
            "comparable": comparable,
            "complete": parity_complete,
            "mismatch_count": len(mismatches),
            "mismatches": mismatches,
        },
        "fixed_zero_failure_one_sided_95_percent_upper_bound": upper,
        "accepted": accepted,
        "root_cause": "not established",
        "baseline_fixed_comparison": (
            "conclusive for deterministic fingerprints"
            if parity_complete
            else "inconclusive because one or more paired raw outputs are unavailable"
        ),
        "diagnostic_only": True,
    }
    write_json(ARTIFACTS / "summary.json", summary)
    return summary


def run_all(fixed: Path, baseline: Path) -> dict[str, Any]:
    manifest = freeze_binary_manifest(fixed, baseline)
    ARTIFACTS.mkdir(exist_ok=True)
    started_utc = utc_now()
    measured = ARTIFACTS / "measured_on.json"
    if not measured.exists():
        write_json(
            measured,
            {
                "schema": "bridgestan-lifetime-v1-environment",
                "started_utc": started_utc,
                "platform": platform.platform(),
                "processor": platform.processor(),
                "machine": platform.machine(),
                "python": sys.version,
                "cpu_count": os.cpu_count(),
                "binary_manifest_sha256": sha256(BINARY_MANIFEST),
            },
        )
    binaries = {"baseline": baseline, "fixed": fixed}
    total = len(cases()) * len(binaries)
    index = 0
    for mode in PROTOCOL["execution"]["mode_order"]:
        for case in cases():
            index += 1
            record = run_case(mode, binaries[mode], case)
            print(
                f"[{index:03}/{total}] {record['case_id']}: {record['status']} "
                f"return={record['return_code']['hex_32']} "
                f"{record.get('duration_seconds', 0):.3f}s",
                flush=True,
            )
    finished_utc = utc_now()
    events_path = ARTIFACTS / "windows-events.json"
    if not events_path.exists():
        write_json(events_path, capture_windows_events(started_utc, finished_utc))
    summary = analyze()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("verify", "run", "prepare"):
        child = subparsers.add_parser(command)
        child.add_argument("--fixed", type=Path, required=True)
        child.add_argument("--baseline", type=Path, required=True)
    subparsers.add_parser("analyze")
    args = parser.parse_args()
    if args.command == "verify":
        print(json.dumps(verify_inputs(args.fixed, args.baseline), indent=2, sort_keys=True))
    elif args.command == "prepare":
        print(
            json.dumps(
                freeze_binary_manifest(args.fixed, args.baseline),
                indent=2,
                sort_keys=True,
            )
        )
    elif args.command == "run":
        run_all(args.fixed, args.baseline)
    else:
        print(json.dumps(analyze(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
