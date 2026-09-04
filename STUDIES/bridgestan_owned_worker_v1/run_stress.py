#!/usr/bin/env python3
"""Run the frozen BridgeStan owned-worker parent/child diagnostic."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
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
WINDOWS_EVENTS = ARTIFACTS / "windows-events.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write(path: Path, text: str, *, replace: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not replace:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        return
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def write_json(path: Path, value: Any, *, replace: bool = True) -> None:
    atomic_write(
        path,
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        replace=replace,
    )


def seed_cases(model: dict[str, Any], schedule: str) -> list[dict[str, Any]]:
    first = int(model[f"{schedule}_seed_start"])
    last = int(model[f"{schedule}_seed_end"])
    return [{**model, "schedule": schedule, "seed": seed} for seed in range(first, last + 1)]


def arm_cases(mode: str) -> list[dict[str, Any]]:
    if mode not in PROTOCOL["execution"]["mode_order"]:
        raise ValueError(f"unknown mode {mode}")
    schedules = ("paired",) if mode == "comparator" else ("paired", "extension")
    result = [
        case
        for schedule in schedules
        for model in PROTOCOL["models"]
        for case in seed_cases(model, schedule)
    ]
    expected = int(PROTOCOL["execution"]["children"][mode])
    if len(result) != expected:
        raise RuntimeError(f"{mode} expands to {len(result)} cases, expected {expected}")
    return result


def validate_matrix() -> None:
    comparator = arm_cases("comparator")
    owned = arm_cases("owned")
    paired = [case for case in owned if case["schedule"] == "paired"]
    if [(case["shape"], case["seed"]) for case in comparator] != [
        (case["shape"], case["seed"]) for case in paired
    ]:
        raise RuntimeError("paired schedules differ")
    allowed = [range(int(first), int(last) + 1) for first, last in PROTOCOL["forbidden_evidence"]["allowed_seed_ranges"]]
    for case in owned:
        if not any(case["seed"] in interval for interval in allowed):
            raise RuntimeError(f"seed outside allowed diagnostic ranges: {case['seed']}")


def binary_details(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "exists": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else None,
        "sha256": sha256(path) if path.is_file() else None,
    }


def verify_inputs(owned: Path, comparator: Path) -> dict[str, Any]:
    validate_matrix()
    errors: list[str] = []
    observed_models: list[dict[str, Any]] = []
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
        "owned": binary_details(owned),
        "comparator": binary_details(comparator),
    }
    for mode, details in binaries.items():
        if not details["exists"]:
            errors.append(f"{mode} binary is missing: {details['path']}")
    return {
        "verified": not errors,
        "errors": errors,
        "protocol_sha256": sha256(PROTOCOL_PATH),
        "preregistration_sha256": sha256(HERE / "PREREGISTRATION.md"),
        "models": observed_models,
        "binaries": binaries,
    }


def freeze_binary_manifest(owned: Path, comparator: Path) -> dict[str, Any]:
    verification = verify_inputs(owned, comparator)
    if not verification["verified"]:
        raise RuntimeError("; ".join(verification["errors"]))
    manifest = {
        "schema": "bridgestan-owned-worker-v1-binaries",
        "captured_before_execution_utc": utc_now(),
        "protocol_sha256": verification["protocol_sha256"],
        "preregistration_sha256": verification["preregistration_sha256"],
        "owned_source_commit": PROTOCOL["owned_source_commit"],
        "comparator_source_commit": PROTOCOL["comparator_source_commit"],
        "binaries": verification["binaries"],
        "models": verification["models"],
    }
    if BINARY_MANIFEST.exists():
        existing = json.loads(BINARY_MANIFEST.read_text(encoding="utf-8"))
        if existing["binaries"] != manifest["binaries"]:
            raise RuntimeError("binary manifest exists but binary identities changed")
        return existing
    write_json(BINARY_MANIFEST, manifest, replace=False)
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
    return f"{mode}-{case['schedule']}-{case['shape']}-{case['seed']}"


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
        except Exception as error:
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
    return {
        "schema": "bridgestan-owned-worker-v1-process",
        "case_id": case_id(mode, case),
        "mode": mode,
        "schedule": case["schedule"],
        "shape": case["shape"],
        "seed": case["seed"],
        "status": "orchestrator_interrupted",
        "process_success": False,
        "process_fault": True,
        "failure_reasons": [
            "prelaunch marker exists without process record; no rerun is permitted"
        ],
        "return_code": return_code_forms(None),
        "timed_out": None,
        "raw_output_exists": None,
        "heartbeat_complete": False,
        "heartbeats": [],
        "last_heartbeat": None,
        "launch_marker": marker.relative_to(HERE).as_posix(),
        "child_pid": None,
        "process_started_unix_ms": None,
    }


def run_case(mode: str, binary: Path, case: dict[str, Any]) -> dict[str, Any]:
    identifier = case_id(mode, case)
    record_path = PROCESSES / f"{identifier}.json"
    marker_path = LAUNCHES / f"{identifier}.json"
    if record_path.exists():
        return json.loads(record_path.read_text(encoding="utf-8"))
    if marker_path.exists():
        record = interrupted_record(mode, case, marker_path)
        write_json(record_path, record, replace=False)
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
    launch_started_utc = utc_now()
    write_json(
        marker_path,
        {
            "case_id": identifier,
            "mode": mode,
            "schedule": case["schedule"],
            "started_utc": launch_started_utc,
            "binary_sha256": sha256(binary),
            "command": command,
        },
        replace=False,
    )
    begin = time.perf_counter()
    code: int | None = None
    timed_out = False
    stdout_bytes = b""
    stderr_bytes = b""
    process_started_unix_ms = int(time.time() * 1000)
    process = subprocess.Popen(command, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    child_pid = process.pid
    try:
        stdout_bytes, stderr_bytes = process.communicate(
            timeout=int(PROTOCOL["execution"]["timeout_seconds_per_child"])
        )
        code = process.returncode
    except subprocess.TimeoutExpired as error:
        timed_out = True
        process.kill()
        final_stdout, final_stderr = process.communicate()
        stdout_bytes = (error.stdout or b"") + final_stdout
        stderr_bytes = (error.stderr or b"") + final_stderr
        code = process.returncode
    duration = time.perf_counter() - begin
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    atomic_write(stdout_path, stdout, replace=False)
    atomic_write(stderr_path, stderr, replace=False)

    raw_result: dict[str, Any] | None = None
    raw_error: str | None = None
    if raw_path.is_file():
        try:
            raw_result = json.loads(raw_path.read_text(encoding="utf-8"))
        except Exception as error:
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
        "schema": "bridgestan-owned-worker-v1-process",
        "case_id": identifier,
        "mode": mode,
        "schedule": case["schedule"],
        "shape": case["shape"],
        "seed": case["seed"],
        "requested_replicas": 4,
        "threads": 4,
        "chains": 4,
        "warmup_per_chain": 4,
        "retained_per_chain": 4,
        "status": "ok" if not reasons else "process_fault",
        "process_success": not reasons,
        "process_fault": bool(reasons),
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
        "launch_started_utc": launch_started_utc,
        "finished_utc": utc_now(),
        "child_pid": child_pid,
        "process_started_unix_ms": process_started_unix_ms,
        "binary_path": str(binary.resolve()),
        "diagnostic_only": True,
    }
    write_json(record_path, record, replace=False)
    return record


def capture_windows_events(started_utc: str, finished_utc: str) -> dict[str, Any]:
    if os.name != "nt":
        return {"available": False, "reason": "not Windows", "events": []}
    script = (
        f"$s=[DateTimeOffset]::Parse('{started_utc}').LocalDateTime;"
        f"$e=[DateTimeOffset]::Parse('{finished_utc}').LocalDateTime;"
        "$x=@(Get-WinEvent -FilterHashtable "
        "@{LogName='Application';Id=1000,1001;StartTime=$s;EndTime=$e} "
        "-ErrorAction SilentlyContinue | ForEach-Object { [pscustomobject]@{"
        "time_created_utc=$_.TimeCreated.ToUniversalTime().ToString('o');"
        "id=$_.Id;provider_name=$_.ProviderName;record_id=$_.RecordId;"
        "event_process_id=$_.ProcessId;message=$_.Message}});"
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
        "query_started_utc": started_utc,
        "query_finished_utc": finished_utc,
        "events": parsed,
    }


def parse_event_1000(event: dict[str, Any]) -> dict[str, Any] | None:
    if int(event.get("id", event.get("Id", -1))) != 1000:
        return None
    message = str(event.get("message", event.get("Message", "")))
    patterns = {
        "process_id_hex": r"(?im)^Faulting process id:\s*(0x[0-9a-f]+)\s*$",
        "application_start_hex": r"(?im)^Faulting application start time:\s*(0x[0-9a-f]+)\s*$",
        "application_path": r"(?im)^Faulting application path:\s*(.+?)\s*$",
        "exception_code": r"(?im)^Exception code:\s*(0x[0-9a-f]+)\s*$",
        "faulting_module": r"(?im)^Faulting module name:\s*([^,\r\n]+)",
        "report_id": r"(?im)^Report Id:\s*(.+?)\s*$",
    }
    values: dict[str, Any] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, message)
        values[key] = match.group(1).strip() if match else None
    if values["process_id_hex"] is not None:
        values["faulting_process_id"] = int(values["process_id_hex"], 16)
    else:
        values["faulting_process_id"] = None
    if values["application_start_hex"] is not None:
        ticks = int(values["application_start_hex"], 16)
        values["application_start_unix_ms"] = (ticks - 116444736000000000) // 10000
    else:
        values["application_start_unix_ms"] = None
    return values


def normalize_windows_path(path: str) -> str:
    return os.path.normcase(os.path.abspath(path)).replace("/", "\\")


def correlated_event_1000(
    record: dict[str, Any], events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if record.get("child_pid") is None or record.get("process_started_unix_ms") is None:
        return []
    expected_path = normalize_windows_path(record["binary_path"])
    result: list[dict[str, Any]] = []
    for event in events:
        parsed = parse_event_1000(event)
        if parsed is None:
            continue
        if parsed["faulting_process_id"] != record["child_pid"]:
            continue
        application_path = parsed.get("application_path")
        if application_path is None or normalize_windows_path(application_path) != expected_path:
            continue
        event_start = parsed.get("application_start_unix_ms")
        if event_start is None or abs(event_start - record["process_started_unix_ms"]) > 5000:
            continue
        result.append({"event": event, "parsed": parsed})
    return result


def load_records() -> dict[str, dict[str, Any]]:
    return {
        record["case_id"]: record
        for path in sorted(PROCESSES.glob("*.json"))
        for record in [json.loads(path.read_text(encoding="utf-8"))]
    }


def event_capture() -> dict[str, Any]:
    if not WINDOWS_EVENTS.exists():
        return {"available": False, "reason": "event capture missing", "events": []}
    return json.loads(WINDOWS_EVENTS.read_text(encoding="utf-8"))


def median_duration(records: list[dict[str, Any]]) -> float | None:
    values = [
        float(record["duration_seconds"])
        for record in records
        if record.get("process_success") and record.get("duration_seconds") is not None
    ]
    return statistics.median(values) if values else None


CLAIMED_PARITY_FIELDS = (
    "sample_fingerprint_fnv1a64",
    "target_calls",
    "recoverable_failures",
    "algorithm_revision",
    "samples_observed",
)

PAIRED_EQUAL_FIELDS = (
    "schema",
    "status",
    "shape",
    "seed",
    "model",
    "data",
    "diagnostic_only",
    *CLAIMED_PARITY_FIELDS,
    "diagnostic_checksum",
    "all_retained_values_finite",
    "dimension",
    "requested_replicas",
    "threads",
    "chains",
    "warmup_per_chain",
    "retained_per_chain",
    "threading",
)


def paired_invariant_differences(
    comparator: dict[str, Any], owned: dict[str, Any]
) -> dict[str, list[Any]]:
    return {
        field: [comparator.get(field), owned.get(field)]
        for field in PAIRED_EQUAL_FIELDS
        if comparator.get(field) != owned.get(field)
    }


def owned_effective_replica_violation(record: dict[str, Any]) -> str | None:
    raw = record.get("raw_result")
    if not isinstance(raw, dict):
        return "raw output unavailable"
    if raw.get("effective_replicas") != 1:
        return f"effective_replicas={raw.get('effective_replicas')!r}, expected 1"
    return None


def correlated_signatures(
    mode_records: list[dict[str, Any]],
    correlations: dict[str, list[dict[str, Any]]],
) -> dict[str, int]:
    signatures: dict[str, int] = {}
    for record in mode_records:
        for correlation in correlations[record["case_id"]]:
            parsed = correlation["parsed"]
            exception = str(parsed.get("exception_code") or "unknown").lower()
            module = str(parsed.get("faulting_module") or "unknown").lower()
            key = f"{exception}/{module}"
            signatures[key] = signatures.get(key, 0) + 1
    return dict(sorted(signatures.items()))


def analyze() -> dict[str, Any]:
    records = load_records()
    expected = {
        mode: [case_id(mode, case) for case in arm_cases(mode)]
        for mode in PROTOCOL["execution"]["mode_order"]
    }
    expected_ids = [identifier for mode in PROTOCOL["execution"]["mode_order"] for identifier in expected[mode]]
    missing = [identifier for identifier in expected_ids if identifier not in records]
    ordered = [records[identifier] for identifier in expected_ids if identifier in records]
    capture = event_capture()
    windows_events = capture.get("events", []) if capture.get("available") else []
    correlations = {
        record["case_id"]: correlated_event_1000(record, windows_events)
        for record in ordered
    }
    write_json(
        ARTIFACTS / "event-correlations.json",
        {
            "schema": "bridgestan-owned-worker-v1-event-correlations",
            "event_capture_available": bool(capture.get("available")),
            "records": correlations,
        },
    )

    by_mode: dict[str, Any] = {}
    for mode in PROTOCOL["execution"]["mode_order"]:
        mode_records = [record for record in ordered if record["mode"] == mode]
        final_faults = [
            record
            for record in mode_records
            if record["process_fault"] or correlations[record["case_id"]]
        ]
        by_mode[mode] = {
            "planned": len(expected[mode]),
            "recorded": len(mode_records),
            "process_successes": sum(bool(record["process_success"]) for record in mode_records),
            "process_faults": sum(bool(record["process_fault"]) for record in mode_records),
            "faults_including_correlated_event_1000": len(final_faults),
            "nonzero_exits": sum(
                record["return_code"]["raw"] not in (0, None) for record in mode_records
            ),
            "timeouts": sum(bool(record["timed_out"]) for record in mode_records),
            "missing_outputs": sum(
                record["raw_output_exists"] is not True for record in mode_records
            ),
            "incomplete_heartbeats": sum(
                not bool(record["heartbeat_complete"]) for record in mode_records
            ),
            "correlated_event_1000": sum(
                bool(correlations[record["case_id"]]) for record in mode_records
            ),
            "event_1000_signatures": correlated_signatures(mode_records, correlations),
            "nominal_success_event_faults": sum(
                bool(record["process_success"]) and bool(correlations[record["case_id"]])
                for record in mode_records
            ),
            "duration_seconds_median": median_duration(mode_records),
            "by_shape": {
                shape: {
                    "planned": sum(
                        case["shape"] == shape for case in arm_cases(mode)
                    ),
                    "recorded": sum(record["shape"] == shape for record in mode_records),
                    "faults": sum(
                        record["shape"] == shape
                        and (record["process_fault"] or bool(correlations[record["case_id"]]))
                        for record in mode_records
                    ),
                    "duration_seconds_median": median_duration(
                        [record for record in mode_records if record["shape"] == shape]
                    ),
                }
                for shape in ("sblrc", "diamonds", "mesquite")
            },
        }

    comparable = 0
    mismatches: list[dict[str, Any]] = []
    mismatch_counts = {field: 0 for field in PAIRED_EQUAL_FIELDS}
    for case in arm_cases("comparator"):
        left_record = records.get(case_id("comparator", case))
        right_record = records.get(case_id("owned", case))
        left = left_record.get("raw_result") if left_record else None
        right = right_record.get("raw_result") if right_record else None
        if not isinstance(left, dict) or not isinstance(right, dict):
            continue
        if left.get("status") != "ok" or right.get("status") != "ok":
            continue
        comparable += 1
        differences = paired_invariant_differences(left, right)
        if differences:
            for field in differences:
                mismatch_counts[field] += 1
            mismatches.append(
                {
                    "shape": case["shape"],
                    "seed": case["seed"],
                    "differences": differences,
                }
            )

    paired_comparator = [
        record
        for record in ordered
        if record["mode"] == "comparator" and record["schedule"] == "paired"
    ]
    paired_owned = [
        record
        for record in ordered
        if record["mode"] == "owned" and record["schedule"] == "paired"
    ]
    comparator_median = median_duration(paired_comparator)
    paired_owned_median = median_duration(paired_owned)
    full_owned_median = by_mode.get("owned", {}).get("duration_seconds_median")
    overhead_ratio = (
        paired_owned_median / comparator_median
        if paired_owned_median is not None and comparator_median not in (None, 0.0)
        else None
    )
    owned_records = [record for record in ordered if record["mode"] == "owned"]
    effective_replica_violations = [
        {
            "case_id": record["case_id"],
            "reason": violation,
        }
        for record in owned_records
        if (violation := owned_effective_replica_violation(record)) is not None
    ]
    owned = by_mode.get("owned", {})
    owned_complete = owned.get("recorded") == int(PROTOCOL["execution"]["children"]["owned"])
    accepted = (
        owned_complete
        and bool(capture.get("available"))
        and owned.get("faults_including_correlated_event_1000") == 0
        and owned.get("nonzero_exits") == 0
        and owned.get("timeouts") == 0
        and owned.get("missing_outputs") == 0
        and owned.get("incomplete_heartbeats") == 0
        and owned.get("correlated_event_1000") == 0
        and not effective_replica_violations
        and not mismatches
    )
    n = int(owned.get("recorded", 0))
    upper = (
        1.0 - math.pow(0.05, 1.0 / n)
        if n and owned.get("faults_including_correlated_event_1000") == 0
        else None
    )
    summary = {
        "schema": "bridgestan-owned-worker-v1-summary",
        "generated_utc": utc_now(),
        "protocol_sha256": sha256(PROTOCOL_PATH),
        "planned_records": len(expected_ids),
        "recorded_records": len(ordered),
        "missing_records": missing,
        "event_capture_available": bool(capture.get("available")),
        "by_mode": by_mode,
        "parity": {
            "planned_paired_cells": len(arm_cases("comparator")),
            "comparable_successful_raw_cells": comparable,
            "claimed_fields": list(CLAIMED_PARITY_FIELDS),
            "equal_fields": list(PAIRED_EQUAL_FIELDS),
            "mismatch_count": len(mismatches),
            "mismatch_counts_by_field": mismatch_counts,
            "mismatches": mismatches,
        },
        "owned_effective_replicas": {
            "required": 1,
            "checked_children": len(owned_records),
            "violation_count": len(effective_replica_violations),
            "violations": effective_replica_violations,
        },
        "performance": {
            "paired_comparator_median_seconds": comparator_median,
            "paired_owned_median_seconds": paired_owned_median,
            "full_owned_median_seconds": full_owned_median,
            "owned_over_comparator_median_ratio": overhead_ratio,
            "interpretation": "descriptive process-level timing only",
        },
        "owned_zero_failure_one_sided_95_percent_upper_bound": upper,
        "owned_zero_failure_one_sided_95_percent_upper_bound_percent": (
            upper * 100.0 if upper is not None else None
        ),
        "accepted": accepted,
        "mitigation_gate_blocked": not accepted,
        "release_blocked": True,
        "release_blockers": [
            "Windows MSVC qualification",
            "Linux and macOS BridgeStan qualification",
            "cross-platform package/wheel matrix",
            "Windows Python from_stan remains disabled",
        ],
        "root_cause": "not established",
        "scope": PROTOCOL["acceptance"]["scope"],
        "diagnostic_only": True,
    }
    write_json(ARTIFACTS / "summary.json", summary)
    return summary


def run_all(owned: Path, comparator: Path) -> dict[str, Any]:
    freeze_binary_manifest(owned, comparator)
    ARTIFACTS.mkdir(exist_ok=True)
    measured = ARTIFACTS / "measured_on.json"
    if not measured.exists():
        write_json(
            measured,
            {
                "schema": "bridgestan-owned-worker-v1-environment",
                "started_utc": utc_now(),
                "platform": platform.platform(),
                "processor": platform.processor(),
                "machine": platform.machine(),
                "python": sys.version,
                "cpu_count": os.cpu_count(),
                "binary_manifest_sha256": sha256(BINARY_MANIFEST),
            },
            replace=False,
        )
    binaries = {"comparator": comparator, "owned": owned}
    total = sum(len(arm_cases(mode)) for mode in PROTOCOL["execution"]["mode_order"])
    index = 0
    for mode in PROTOCOL["execution"]["mode_order"]:
        for case in arm_cases(mode):
            index += 1
            record = run_case(mode, binaries[mode], case)
            print(
                f"[{index:03}/{total}] {record['case_id']}: {record['status']} "
                f"return={record['return_code']['hex_32']} "
                f"{record.get('duration_seconds', 0):.3f}s",
                flush=True,
            )
    if not WINDOWS_EVENTS.exists():
        settle = int(PROTOCOL["execution"]["event_settle_seconds"])
        if settle:
            time.sleep(settle)
        study_started = json.loads(measured.read_text(encoding="utf-8"))["started_utc"]
        query_start = (
            datetime.fromisoformat(study_started.replace("Z", "+00:00"))
            - timedelta(seconds=5)
        ).isoformat().replace("+00:00", "Z")
        write_json(
            WINDOWS_EVENTS,
            capture_windows_events(query_start, utc_now()),
            replace=False,
        )
    summary = analyze()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("verify", "run", "prepare"):
        child = subparsers.add_parser(command)
        child.add_argument("--owned", type=Path, required=True)
        child.add_argument("--comparator", type=Path, required=True)
    subparsers.add_parser("analyze")
    args = parser.parse_args()
    if args.command == "verify":
        print(json.dumps(verify_inputs(args.owned, args.comparator), indent=2, sort_keys=True))
    elif args.command == "prepare":
        print(
            json.dumps(
                freeze_binary_manifest(args.owned, args.comparator),
                indent=2,
                sort_keys=True,
            )
        )
    elif args.command == "run":
        run_all(args.owned, args.comparator)
    else:
        print(json.dumps(analyze(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
