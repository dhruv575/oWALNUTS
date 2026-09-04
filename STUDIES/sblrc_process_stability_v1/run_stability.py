#!/usr/bin/env python3
"""Run and analyze the preregistered sblrc process-stability diagnostic.

This driver intentionally computes no posterior-performance statistics.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
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
HARNESS = HERE / "target" / "release" / (
    "sblrc-process-stability-v1.exe" if os.name == "nt" else "sblrc-process-stability-v1"
)
FORBIDDEN_SEED = 90101


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temp.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def decode_capture(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def return_code_forms(code: int | None) -> dict[str, int | str | None]:
    if code is None:
        return {
            "raw": None,
            "signed_32": None,
            "unsigned_32": None,
            "hex_32": None,
        }
    unsigned = code & 0xFFFFFFFF
    signed = unsigned - (1 << 32) if unsigned >= (1 << 31) else unsigned
    return {
        "raw": code,
        "signed_32": signed,
        "unsigned_32": unsigned,
        "hex_32": f"0x{unsigned:08X}",
    }


def all_cases() -> list[tuple[dict[str, Any], int]]:
    return [
        (row, seed)
        for row in PROTOCOL["matrix"]
        for seed in row["seeds"]
    ]


def case_id(row: dict[str, Any], seed: int) -> str:
    return f"{row['id']}-{seed}"


def work_units(row: dict[str, Any]) -> int:
    if row["mode"] == "evaluate":
        return int(row["evaluations_per_thread"])
    if row["mode"] == "repeat_load_drop":
        return int(row["load_drop_cycles"])
    return 0


def verify_inputs(require_harness: bool = True) -> dict[str, Any]:
    cases = all_cases()
    seeds = [seed for _, seed in cases]
    errors: list[str] = []
    if FORBIDDEN_SEED in seeds or FORBIDDEN_SEED not in PROTOCOL["forbidden_seeds"]:
        errors.append(f"forbidden evidence seed {FORBIDDEN_SEED} is not excluded")
    if len(seeds) != len(set(seeds)):
        errors.append("diagnostic seeds are not unique")
    expected_count = int(PROTOCOL["execution"]["expected_child_count"])
    if len(cases) != expected_count:
        errors.append(f"protocol has {len(cases)} children, expected {expected_count}")
    for row in PROTOCOL["matrix"]:
        if len(row["seeds"]) != int(row["repetitions"]):
            errors.append(f"{row['id']}: repetitions do not match seed count")
        if row["mode"] == "sample":
            if PROTOCOL["sampler"]["warmup"] != 1000 or PROTOCOL["sampler"]["retained"] != 1000:
                errors.append(f"{row['id']}: sampling counts are not exactly 1000/1000")

    observed: dict[str, Any] = {}
    for name in ("model", "data"):
        spec = PROTOCOL["external_inputs"][name]
        path = Path(spec["path"])
        entry = {
            "path": str(path),
            "exists": path.is_file(),
            "bytes": path.stat().st_size if path.is_file() else None,
            "sha256": sha256(path) if path.is_file() else None,
        }
        entry["matches_protocol"] = (
            entry["exists"]
            and entry["bytes"] == spec["bytes"]
            and entry["sha256"] == spec["sha256"]
        )
        if not entry["matches_protocol"]:
            errors.append(f"{name} does not match frozen path/size/hash")
        observed[name] = entry
    observed["harness"] = {"path": str(HARNESS), "exists": HARNESS.is_file()}
    if require_harness and not HARNESS.is_file():
        errors.append(f"release harness is missing: {HARNESS}")
    observed["protocol_sha256"] = sha256(PROTOCOL_PATH)
    observed["verified"] = not errors
    observed["errors"] = errors
    if errors:
        raise RuntimeError("; ".join(errors))
    return observed


def expected_heartbeat_sequence(row: dict[str, Any]) -> list[tuple[str, str, int | None]]:
    expected: list[tuple[str, str, int | None]] = [("process", "start", None)]
    if row["mode"] == "repeat_load_drop":
        for cycle in range(int(row["load_drop_cycles"])):
            expected.extend(
                [
                    ("load", "before", cycle),
                    ("load", "after", cycle),
                    ("initialization", "before", cycle),
                    ("initialization", "after", cycle),
                    ("load_drop_work", "before", cycle),
                    ("load_drop_work", "after", cycle),
                    ("drop", "before", cycle),
                    ("drop", "after", cycle),
                ]
            )
        expected.extend(
            [
                ("result_write", "before", None),
                ("result_write", "after", None),
                ("process", "complete", None),
            ]
        )
        return expected

    stage = {
        "load_drop": "load_drop_work",
        "evaluate": "evaluation",
        "sample": "sampling",
    }[row["mode"]]
    expected.extend(
        [
            ("load", "before", None),
            ("load", "after", None),
            ("initialization", "before", None),
            ("initialization", "after", None),
            (stage, "before", None),
            (stage, "after", None),
            ("result_write", "before", None),
            ("result_write", "after", None),
            ("drop", "before", None),
            ("drop", "after", None),
            ("process", "complete", None),
        ]
    )
    return expected


def read_heartbeats(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    for event_path in sorted(path.glob("*.json")):
        try:
            event = json.loads(event_path.read_text(encoding="utf-8"))
            event["_file"] = event_path.name
            events.append(event)
        except Exception as error:  # noqa: BLE001 - malformed output is a result
            errors.append(f"{event_path.name}: {error}")
    return events, errors


def heartbeat_assessment(
    row: dict[str, Any], path: Path
) -> tuple[bool, list[dict[str, Any]], list[str]]:
    events, errors = read_heartbeats(path)
    actual = [
        (event.get("stage"), event.get("boundary"), event.get("cycle"))
        for event in events
    ]
    expected = expected_heartbeat_sequence(row)
    sequences = [event.get("sequence") for event in events]
    if sequences != list(range(len(events))):
        errors.append(f"non-contiguous sequence numbers: {sequences}")
    if actual != expected:
        errors.append(
            f"heartbeat sequence mismatch: observed {len(actual)}, expected {len(expected)}"
        )
    return not errors, events, errors


def interrupted_record(
    row: dict[str, Any], seed: int, identifier: str, marker: Path
) -> dict[str, Any]:
    message = (
        "launch marker existed without a process record; protocol forbids rerunning "
        "a potentially failed child"
    )
    return {
        "schema": "sblrc-process-stability-v1-process",
        "case_id": identifier,
        "matrix_id": row["id"],
        "mode": row["mode"],
        "seed": seed,
        "replicas": row["replicas"],
        "threads": row["threads"],
        "chains": row["chains"],
        "status": "orchestrator_interrupted",
        "success": False,
        "fault": True,
        "silent_failure": False,
        "failure_reasons": [message],
        "launch_marker": marker.relative_to(HERE).as_posix(),
        "return_code": return_code_forms(None),
        "duration_seconds": None,
        "timed_out": None,
        "raw_output_exists": None,
        "stdout": "",
        "stderr": "",
        "heartbeats": [],
        "heartbeat_complete": False,
        "heartbeat_errors": [message],
        "last_heartbeat": None,
    }


def run_case(row: dict[str, Any], seed: int) -> dict[str, Any]:
    identifier = case_id(row, seed)
    record_path = PROCESSES / f"{identifier}.json"
    marker = LAUNCHES / f"{identifier}.json"
    if record_path.exists():
        return json.loads(record_path.read_text(encoding="utf-8"))
    if marker.exists():
        record = interrupted_record(row, seed, identifier, marker)
        write_json(record_path, record)
        return record

    raw_path = RAW / f"{identifier}.json"
    heartbeat_path = HEARTBEATS / identifier
    stdout_path = STDOUT / f"{identifier}.txt"
    stderr_path = STDERR / f"{identifier}.txt"
    command = [
        str(HARNESS),
        row["mode"],
        PROTOCOL["external_inputs"]["model"]["path"],
        PROTOCOL["external_inputs"]["data"]["path"],
        str(seed),
        str(row["replicas"]),
        str(row["threads"]),
        str(row["chains"]),
        str(heartbeat_path),
        str(raw_path),
        str(work_units(row)),
    ]
    write_json(
        marker,
        {
            "case_id": identifier,
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "command": command,
        },
    )
    begin = time.perf_counter()
    return_code: int | None = None
    timed_out = False
    stdout = ""
    stderr = ""
    try:
        completed = subprocess.run(
            command,
            cwd=HERE,
            capture_output=True,
            timeout=PROTOCOL["execution"]["timeout_seconds_per_child"],
            check=False,
        )
        return_code = completed.returncode
        stdout = decode_capture(completed.stdout)
        stderr = decode_capture(completed.stderr)
    except subprocess.TimeoutExpired as error:
        timed_out = True
        stdout = decode_capture(error.stdout)
        stderr = decode_capture(error.stderr)
    duration = time.perf_counter() - begin
    atomic_write_text(stdout_path, stdout)
    atomic_write_text(stderr_path, stderr)

    raw_exists = raw_path.is_file()
    raw_result: Any = None
    raw_error: str | None = None
    if raw_exists:
        try:
            raw_result = json.loads(raw_path.read_text(encoding="utf-8"))
        except Exception as error:  # noqa: BLE001 - malformed child output is a result
            raw_error = str(error)
    heartbeat_complete, events, heartbeat_errors = heartbeat_assessment(
        row, heartbeat_path
    )

    reasons: list[str] = []
    if timed_out:
        reasons.append("child timed out")
    if return_code != 0:
        reasons.append(f"child return code was {return_code!r}, not zero")
    if not raw_exists:
        reasons.append("raw output is missing")
    elif raw_error:
        reasons.append(f"raw output is not valid JSON: {raw_error}")
    elif raw_result.get("status") != "ok":
        reasons.append(f"raw output status is {raw_result.get('status')!r}, not 'ok'")
    if not heartbeat_complete:
        reasons.append("required heartbeat sequence is incomplete")
    success = not reasons
    silent = not success and not stdout.strip() and not stderr.strip()
    record = {
        "schema": "sblrc-process-stability-v1-process",
        "case_id": identifier,
        "matrix_id": row["id"],
        "mode": row["mode"],
        "seed": seed,
        "replicas": row["replicas"],
        "threads": row["threads"],
        "chains": row["chains"],
        "work_units": work_units(row),
        "warmup": 1000 if row["mode"] == "sample" else None,
        "retained": 1000 if row["mode"] == "sample" else None,
        "status": "ok" if success else "fault",
        "success": success,
        "fault": not success,
        "silent_failure": silent,
        "failure_reasons": reasons,
        "command": command,
        "return_code": return_code_forms(return_code),
        "duration_seconds": duration,
        "timed_out": timed_out,
        "raw_output_exists": raw_exists,
        "raw_output_path": raw_path.relative_to(HERE).as_posix(),
        "raw_output_status": raw_result.get("status") if isinstance(raw_result, dict) else None,
        "raw_output_error": raw_error,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_path": stdout_path.relative_to(HERE).as_posix(),
        "stderr_path": stderr_path.relative_to(HERE).as_posix(),
        "heartbeats": events,
        "heartbeat_complete": heartbeat_complete,
        "heartbeat_errors": heartbeat_errors,
        "last_heartbeat": events[-1] if events else None,
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evidence_use": "forbidden; process diagnostic only",
    }
    write_json(record_path, record)
    return record


def append_log(message: str) -> None:
    path = ARTIFACTS / "run-log.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] {message}\n")
        stream.flush()


def run_all() -> None:
    verification = verify_inputs(require_harness=True)
    ARTIFACTS.mkdir(exist_ok=True)
    measured = ARTIFACTS / "measured_on.json"
    if not measured.exists():
        write_json(
            measured,
            {
                "schema": "sblrc-process-stability-v1-environment",
                "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "platform": platform.platform(),
                "processor": platform.processor(),
                "machine": platform.machine(),
                "python": sys.version,
                "cpu_count": os.cpu_count(),
                "protocol_sha256": verification["protocol_sha256"],
                "input_verification": verification,
                "evidence_use": "forbidden; process diagnostic only",
            },
        )
    append_log(
        f"verified frozen inputs; launching {len(all_cases())} diagnostic children; "
        f"seed {FORBIDDEN_SEED} forbidden"
    )
    for index, (row, seed) in enumerate(all_cases(), start=1):
        identifier = case_id(row, seed)
        record = run_case(row, seed)
        code = record["return_code"]["hex_32"]
        append_log(
            f"{index:02}/{len(all_cases())} {identifier}: {record['status']} "
            f"return={code} raw={record['raw_output_exists']} "
            f"heartbeats={len(record['heartbeats'])} duration={record['duration_seconds']}"
        )
        print(
            f"[{index:02}/{len(all_cases())}] {identifier}: {record['status']} "
            f"return={code} raw={record['raw_output_exists']} "
            f"{record['duration_seconds']:.3f}s"
            if record["duration_seconds"] is not None
            else f"[{index:02}/{len(all_cases())}] {identifier}: {record['status']}",
            flush=True,
        )
    analyze()


def load_records() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(PROCESSES.glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        records[value["case_id"]] = value
    return records


def analyze() -> dict[str, Any]:
    records = load_records()
    planned = all_cases()
    missing = [
        case_id(row, seed)
        for row, seed in planned
        if case_id(row, seed) not in records
    ]
    ordered = [
        records[case_id(row, seed)]
        for row, seed in planned
        if case_id(row, seed) in records
    ]
    faults = [record for record in ordered if record.get("fault")]
    silent = [record for record in faults if record.get("silent_failure")]
    by_matrix: dict[str, Any] = {}
    for row in PROTOCOL["matrix"]:
        row_records = [
            records[case_id(row, seed)]
            for seed in row["seeds"]
            if case_id(row, seed) in records
        ]
        durations = [
            record["duration_seconds"]
            for record in row_records
            if record.get("duration_seconds") is not None
        ]
        row_faults = [record for record in row_records if record.get("fault")]
        by_matrix[row["id"]] = {
            "mode": row["mode"],
            "replicas": row["replicas"],
            "threads": row["threads"],
            "chains": row["chains"],
            "planned": row["repetitions"],
            "recorded": len(row_records),
            "successes": sum(bool(record.get("success")) for record in row_records),
            "faults": len(row_faults),
            "silent_failures": sum(
                bool(record.get("silent_failure")) for record in row_records
            ),
            "raw_outputs_missing": sum(
                record.get("raw_output_exists") is False for record in row_records
            ),
            "heartbeat_incomplete": sum(
                not bool(record.get("heartbeat_complete")) for record in row_records
            ),
            "duration_seconds": {
                "minimum": min(durations) if durations else None,
                "median": statistics.median(durations) if durations else None,
                "maximum": max(durations) if durations else None,
            },
            "fault_cases": [record["case_id"] for record in row_faults],
        }

    complete = len(ordered) == len(planned) and not missing
    if not complete:
        verdict = "incomplete"
        verdict_text = (
            f"The fixed matrix is incomplete: {len(ordered)}/{len(planned)} child "
            "records are present. No reproduction conclusion is made."
        )
    elif faults:
        verdict = "fault_reproduced"
        verdict_text = (
            f"A process-stability fault reproduced in {len(faults)}/{len(ordered)} "
            f"diagnostic children; {len(silent)} were silent by the frozen rule. "
            "Heartbeat localization is descriptive and does not establish root cause."
        )
    else:
        verdict = "fault_not_reproduced"
        verdict_text = (
            f"The WP35 silent process fault did not reproduce in any of the "
            f"{len(ordered)} preregistered diagnostic children. This bounded negative "
            "result does not identify the cause of the original exit."
        )
    summary = {
        "schema": "sblrc-process-stability-v1-summary",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "protocol_sha256": sha256(PROTOCOL_PATH),
        "expected_children": len(planned),
        "recorded_children": len(ordered),
        "missing_children": missing,
        "matrix_complete": complete,
        "successes": sum(bool(record.get("success")) for record in ordered),
        "faults": len(faults),
        "silent_failures": len(silent),
        "raw_outputs_missing": sum(
            record.get("raw_output_exists") is False for record in ordered
        ),
        "heartbeat_incomplete": sum(
            not bool(record.get("heartbeat_complete")) for record in ordered
        ),
        "forbidden_seed_90101_run": any(
            record.get("seed") == FORBIDDEN_SEED for record in ordered
        ),
        "verdict": verdict,
        "verdict_text": verdict_text,
        "root_cause": "not established",
        "diagnostic_only": True,
        "by_matrix": by_matrix,
        "fault_details": [
            {
                "case_id": record["case_id"],
                "reasons": record["failure_reasons"],
                "silent": record["silent_failure"],
                "return_code": record["return_code"],
                "last_heartbeat": record["last_heartbeat"],
                "raw_output_exists": record["raw_output_exists"],
            }
            for record in faults
        ],
    }
    write_json(ARTIFACTS / "summary.json", summary)

    lines = [
        "# sblrc process stability diagnostic v1 — results",
        "",
        verdict_text,
        "",
        "These are process-lifecycle diagnostics, not posterior-performance evidence. "
        "Durations are reported only to identify hangs/timeouts.",
        "",
        "| matrix row | config | planned | success | faults | silent | raw missing | heartbeat incomplete | duration median / max (s) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in PROTOCOL["matrix"]:
        result = by_matrix[row["id"]]
        duration = result["duration_seconds"]
        median = "—" if duration["median"] is None else f"{duration['median']:.4f}"
        maximum = "—" if duration["maximum"] is None else f"{duration['maximum']:.4f}"
        lines.append(
            f"| {row['id']} | r{row['replicas']} / t{row['threads']} / "
            f"c{row['chains']} | {result['planned']} | {result['successes']} | "
            f"{result['faults']} | {result['silent_failures']} | "
            f"{result['raw_outputs_missing']} | {result['heartbeat_incomplete']} | "
            f"{median} / {maximum} |"
        )
    lines.extend(
        [
            "",
            "## Classification",
            "",
            f"- Matrix complete: `{complete}` ({len(ordered)}/{len(planned)} records).",
            f"- Faults: `{len(faults)}`; silent faults: `{len(silent)}`.",
            f"- Evidence seed 90101 run: `{summary['forbidden_seed_90101_run']}`.",
            f"- Root cause: `{summary['root_cause']}`.",
        ]
    )
    if faults:
        lines.extend(["", "## Fault records", ""])
        for fault in summary["fault_details"]:
            last = fault["last_heartbeat"]
            location = (
                f"{last.get('stage')}/{last.get('boundary')}"
                if isinstance(last, dict)
                else "none"
            )
            lines.append(
                f"- `{fault['case_id']}`: {', '.join(fault['reasons'])}; "
                f"return `{fault['return_code']['hex_32']}`; last heartbeat `{location}`."
            )
    atomic_write_text(ARTIFACTS / "results-table.md", "\n".join(lines) + "\n")
    atomic_write_text(
        ARTIFACTS / "verdict.md",
        "# Verdict\n\n"
        + verdict_text
        + "\n\nRoot cause: not established. This study is not posterior-performance evidence.\n",
    )
    print(verdict_text)
    return summary


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "run"
    if command == "verify":
        print(json.dumps(verify_inputs(require_harness=True), indent=2, sort_keys=True))
    elif command == "run":
        run_all()
    elif command == "analyze":
        analyze()
    else:
        raise SystemExit("usage: run_stability.py [verify|run|analyze]")


if __name__ == "__main__":
    main()
