#!/usr/bin/env python3
"""Run the one-shot matrix frozen in FINAL-QUALIFICATION.md."""
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
PROTOCOL = HERE / "FINAL-QUALIFICATION.md"
ARTIFACTS = HERE / "artifacts" / "final-qualification"
PROCESSES = ARTIFACTS / "processes"
RAW = ARTIFACTS / "raw"
HEARTBEATS = ARTIFACTS / "heartbeats"
STDOUT = ARTIFACTS / "stdout"
STDERR = ARTIFACTS / "stderr"
LAUNCHES = ARTIFACTS / "launches"
BINARY_MANIFEST = ARTIFACTS / "binary-manifest.json"
HISTORICAL_INTEGRITY = ARTIFACTS / "historical-integrity.json"
MEASURED_ON = ARTIFACTS / "measured-on.json"
WINDOWS_EVENTS = ARTIFACTS / "windows-events.json"
EVENT_CORRELATIONS = ARTIFACTS / "event-correlations.json"
SUMMARY = ARTIFACTS / "summary.json"
BASELINE_COMMIT = "14b1791"
ALGORITHM_REVISION = "walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10"
TIMEOUT_SECONDS = 90
EVENT_SETTLE_SECONDS = 20

MODEL_ROOT = Path(
    r"C:\dev\owalnuts-wt\posteriordb-v6"
    r"\STUDIES\posteriordb_bench_v6\models"
)
MODELS = {
    "sblrc": {
        "model": MODEL_ROOT / "sblrc__blr_model.so",
        "model_sha256": "b77acc367c40b3afbb51f239e87fe896c1e7631643352361734b0dbacb0c50f1",
        "model_bytes": 3_891_206,
        "data": MODEL_ROOT / "sblrc__blr.data.json",
        "data_sha256": "2227de01d39e50560dd8341a84ed176a2a081cc8c8a841261dd4d6c38b47dc9c",
        "data_bytes": 11_288,
    },
    "diamonds": {
        "model": MODEL_ROOT / "diamonds__diamonds_model.so",
        "model_sha256": "49cb5dfd1963bbb78ce157db36bd6442fe8549bdc4ca0cb4f7cc09b447319ccf",
        "model_bytes": 4_010_328,
        "data": MODEL_ROOT / "diamonds__diamonds.data.json",
        "data_sha256": "b8ff4fbdb0f7501b961f795d1d5cf27831a0dba909ff6582b3e57996ef3dbd3e",
        "data_bytes": 2_330_437,
    },
    "mesquite": {
        "model": MODEL_ROOT / "mesquite__logmesquite_logvash_model.so",
        "model_sha256": "15221433ff586e954e9066eb8b19c3ac9367ea2f322ef24ed4a61b7018bfcc18",
        "model_bytes": 3_915_548,
        "data": MODEL_ROOT / "mesquite__logmesquite_logvash.data.json",
        "data_sha256": "b0133a4fd9fbb447514616395878c3bf33d3d693927e10e16e848fd1e9160d97",
        "data_bytes": 1_599,
    },
}
SEED_BLOCKS = (
    ("ordinary", "sblrc", 4_940_001, 4_940_180),
    ("ordinary", "diamonds", 4_940_201, 4_940_380),
    ("ordinary", "mesquite", 4_940_401, 4_940_580),
    ("concurrent", "sblrc", 4_940_601, 4_940_660),
    ("concurrent", "diamonds", 4_940_701, 4_940_760),
    ("concurrent", "mesquite", 4_940_801, 4_940_860),
)
PROTECTED_HISTORICAL_PATHS = (
    "STUDIES/bridgestan_lifetime_v1/artifacts/launches",
    "STUDIES/bridgestan_lifetime_v1/artifacts/processes",
    "STUDIES/bridgestan_lifetime_v1/artifacts/raw",
    "STUDIES/bridgestan_lifetime_v1/artifacts/heartbeats",
    "STUDIES/bridgestan_lifetime_v1/artifacts/stdout",
    "STUDIES/bridgestan_lifetime_v1/artifacts/stderr",
    "STUDIES/bridgestan_lifetime_v1/artifacts/windows-events.json",
    "STUDIES/bridgestan_lifetime_v1/artifacts/binaries.json",
    "STUDIES/bridgestan_owned_worker_v1/artifacts/launches",
    "STUDIES/bridgestan_owned_worker_v1/artifacts/processes",
    "STUDIES/bridgestan_owned_worker_v1/artifacts/raw",
    "STUDIES/bridgestan_owned_worker_v1/artifacts/heartbeats",
    "STUDIES/bridgestan_owned_worker_v1/artifacts/stdout",
    "STUDIES/bridgestan_owned_worker_v1/artifacts/stderr",
    "STUDIES/bridgestan_owned_worker_v1/artifacts/windows-events.json",
    "STUDIES/bridgestan_owned_worker_v1/artifacts/binaries.json",
)


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


def cases() -> list[dict[str, Any]]:
    return [
        {
            "mode": mode,
            "shape": shape,
            "seed": seed,
            "model": str(MODELS[shape]["model"]),
            "data": str(MODELS[shape]["data"]),
        }
        for mode, shape, first, last in SEED_BLOCKS
        for seed in range(first, last + 1)
    ]


def validate_matrix() -> None:
    expanded = cases()
    if len(expanded) != 720:
        raise RuntimeError(f"final matrix expands to {len(expanded)}, expected 720")
    counts = {
        mode: sum(case["mode"] == mode for case in expanded)
        for mode in ("ordinary", "concurrent")
    }
    if counts != {"ordinary": 540, "concurrent": 180}:
        raise RuntimeError(f"incorrect mode counts: {counts}")
    identities = [
        (case["mode"], case["shape"], case["seed"]) for case in expanded
    ]
    if len(set(identities)) != len(identities):
        raise RuntimeError("duplicate final matrix cell")
    if any(992_000 <= case["seed"] < 994_000 for case in expanded):
        raise RuntimeError("historical 992xxx/993xxx seed entered final matrix")


def case_id(case: dict[str, Any]) -> str:
    return f"final-{case['mode']}-{case['shape']}-{case['seed']}"


def git_object(commit: str, path: str) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", f"{commit}:{path}"],
        cwd=HERE,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def verify_historical_integrity() -> dict[str, Any]:
    rows = []
    for path in PROTECTED_HISTORICAL_PATHS:
        baseline = git_object(BASELINE_COMMIT, path)
        current = git_object("HEAD", path)
        rows.append(
            {
                "path": path,
                "baseline_object": baseline,
                "current_object": current,
                "equal": baseline is not None and baseline == current,
            }
        )
    return {
        "schema": "bridgestan-owned-worker-final-historical-integrity",
        "baseline_commit": BASELINE_COMMIT,
        "verified_utc": utc_now(),
        "paths": rows,
        "verified": all(row["equal"] for row in rows),
    }


def binary_details(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "exists": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else None,
        "sha256": sha256(path) if path.is_file() else None,
    }


def verify_inputs(binary: Path) -> dict[str, Any]:
    validate_matrix()
    errors: list[str] = []
    assets: list[dict[str, Any]] = []
    for shape, expected in MODELS.items():
        row: dict[str, Any] = {"shape": shape}
        for kind in ("model", "data"):
            path = Path(expected[kind])
            observed = {
                "path": str(path),
                "exists": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else None,
                "sha256": sha256(path) if path.is_file() else None,
            }
            observed["matches_protocol"] = (
                observed["exists"]
                and observed["bytes"] == expected[f"{kind}_bytes"]
                and observed["sha256"] == expected[f"{kind}_sha256"]
            )
            if not observed["matches_protocol"]:
                errors.append(f"{shape} {kind} does not match final protocol")
            row[kind] = observed
        assets.append(row)
    binary_record = binary_details(binary)
    if not binary_record["exists"]:
        errors.append(f"final child binary is missing: {binary_record['path']}")
    integrity = verify_historical_integrity()
    if not integrity["verified"]:
        errors.append("historical raw artifact Git objects differ from 14b1791")
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=HERE,
        capture_output=True,
        text=True,
        check=True,
    )
    source_commit = completed.stdout.strip()
    return {
        "schema": "bridgestan-owned-worker-final-input-verification",
        "verified": not errors,
        "errors": errors,
        "source_commit": source_commit,
        "protocol_sha256": sha256(PROTOCOL),
        "binary": binary_record,
        "assets": assets,
        "historical_integrity": integrity,
        "matrix": {
            "ordinary": 540,
            "concurrent": 180,
            "total": 720,
        },
    }


def prepare(binary: Path) -> dict[str, Any]:
    verification = verify_inputs(binary)
    if not verification["verified"]:
        raise RuntimeError("; ".join(verification["errors"]))
    if BINARY_MANIFEST.exists() or HISTORICAL_INTEGRITY.exists():
        raise RuntimeError("final pre-run manifests already exist; refusing replacement")
    manifest = {
        key: verification[key]
        for key in (
            "schema",
            "source_commit",
            "protocol_sha256",
            "binary",
            "assets",
            "matrix",
        )
    }
    manifest["schema"] = "bridgestan-owned-worker-final-binary-manifest"
    manifest["captured_before_execution_utc"] = utc_now()
    write_json(BINARY_MANIFEST, manifest, replace=False)
    write_json(
        HISTORICAL_INTEGRITY,
        verification["historical_integrity"],
        replace=False,
    )
    return manifest


def return_code_forms(code: int | None) -> dict[str, int | str | None]:
    if code is None:
        return {
            "raw": None,
            "signed_32": None,
            "unsigned_32": None,
            "hex_32": None,
        }
    unsigned = code & 0xFFFF_FFFF
    signed = unsigned - (1 << 32) if unsigned >= (1 << 31) else unsigned
    return {
        "raw": code,
        "signed_32": signed,
        "unsigned_32": unsigned,
        "hex_32": f"0x{unsigned:08X}",
    }


def expected_heartbeats(mode: str) -> list[tuple[str, str]]:
    if mode == "ordinary":
        run_events = [
            (f"ordinary-{label}-{stage}", boundary)
            for label in ("a", "b")
            for stage, boundaries in (
                ("load", ("before", "after")),
                ("initialization", ("before", "after")),
                ("sampling", ("before", "after")),
                ("drop", ("before", "after")),
            )
            for boundary in boundaries
        ]
    elif mode == "concurrent":
        run_events = [("multi-target", "before"), ("multi-target", "after")]
    else:
        raise ValueError(f"unknown mode {mode}")
    return [
        ("process", "start"),
        *run_events,
        ("parity-check", "before"),
        ("parity-check", "after"),
        ("result-write", "before"),
        ("result-write", "after"),
        ("process", "complete"),
    ]


def assess_heartbeats(
    path: Path, case: dict[str, Any]
) -> tuple[bool, list[dict[str, Any]], list[str]]:
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    for event_path in sorted(path.glob("*.json")):
        try:
            event = json.loads(event_path.read_text(encoding="utf-8"))
            event["_file"] = event_path.name
            events.append(event)
        except Exception as error:  # noqa: BLE001 - malformed evidence is data
            errors.append(f"{event_path.name}: {error}")
    if [event.get("sequence") for event in events] != list(range(len(events))):
        errors.append("heartbeat sequence is not contiguous")
    actual = [(event.get("stage"), event.get("boundary")) for event in events]
    expected = expected_heartbeats(case["mode"])
    if actual != expected:
        errors.append(
            f"heartbeat sequence differs: observed {len(actual)}, "
            f"expected {len(expected)}"
        )
    for event in events:
        for field, expected_value in (
            ("schema", "bridgestan-owned-worker-final-qualification-heartbeat"),
            ("mode", case["mode"]),
            ("shape", case["shape"]),
            ("seed", case["seed"]),
            ("requested_replicas", 4),
            ("threads", 4),
        ):
            if event.get(field) != expected_value:
                errors.append(
                    f"{event.get('_file')} {field}={event.get(field)!r}, "
                    f"expected {expected_value!r}"
                )
    return not errors, events, errors


def expected_settings(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "shape": case["shape"],
        "seed": case["seed"],
        "requested_replicas": 4,
        "threads": 4,
        "chains": 4,
        "warmup_per_chain": 4,
        "retained_per_chain": 4,
        "metric": "diagonal",
        "adaptation": "default",
        "tuning": "default",
        "limits": "admit_worst_case",
        "model": case["model"],
        "data": case["data"],
    }


def validate_sample_observation(
    observation: Any, case: dict[str, Any], label: str
) -> list[str]:
    if not isinstance(observation, dict):
        return [f"{label} is not an object"]
    errors = []
    expected = {
        "settings": expected_settings(case),
        "samples_observed": 16,
        "all_retained_values_finite": True,
        "algorithm_revision": ALGORITHM_REVISION,
        "threading": "Serialised",
        "execution": "OwnedSerialised",
        "requested_replicas": 4,
        "effective_replicas": 1,
    }
    for field, value in expected.items():
        if observation.get(field) != value:
            errors.append(
                f"{label}.{field}={observation.get(field)!r}, expected {value!r}"
            )
    for field in (
        "sample_fingerprint_fnv1a64",
        "diagnostic_checksum",
        "target_calls",
        "recoverable_failures",
        "dimension",
        "parameter_names",
        "model_info",
        "compiled_threading",
    ):
        if field not in observation:
            errors.append(f"{label}.{field} is missing")
    if not isinstance(observation.get("target_calls"), int) or (
        observation.get("target_calls", 0) <= 0
    ):
        errors.append(f"{label}.target_calls is not positive")
    return errors


def validate_concurrent_observation(
    observation: Any, case: dict[str, Any], label: str
) -> list[str]:
    if not isinstance(observation, dict):
        return [f"{label} is not an object"]
    errors = []
    expected = {
        "settings": expected_settings(case),
        "probe_count": 16,
        "all_values_finite": True,
        "target_calls": 16,
        "recoverable_failures": 0,
        "threading": "Serialised",
        "execution": "OwnedSerialised",
        "requested_replicas": 4,
        "effective_replicas": 1,
    }
    for field, value in expected.items():
        if observation.get(field) != value:
            errors.append(
                f"{label}.{field}={observation.get(field)!r}, expected {value!r}"
            )
    for field in (
        "position_fingerprint_fnv1a64",
        "value_gradient_fingerprint_fnv1a64",
        "diagnostic_checksum",
        "dimension",
        "parameter_names",
        "model_info",
        "compiled_threading",
    ):
        if field not in observation:
            errors.append(f"{label}.{field} is missing")
    return errors


def validate_raw(raw: Any, case: dict[str, Any]) -> list[str]:
    if not isinstance(raw, dict):
        return ["raw result is not an object"]
    errors = []
    expected_common = {
        "schema": "bridgestan-owned-worker-final-qualification-child",
        "status": "ok",
        "diagnostic_only": True,
        "mode": case["mode"],
        "shape": case["shape"],
        "seed": case["seed"],
        "requested_replicas": 4,
        "threads": 4,
        "parity_exact": True,
    }
    for field, value in expected_common.items():
        if raw.get(field) != value:
            errors.append(f"{field}={raw.get(field)!r}, expected {value!r}")
    if case["mode"] == "ordinary":
        for field, value in (
            ("effective_replicas", 1),
            ("chains", 4),
            ("warmup_per_chain", 4),
            ("retained_per_chain", 4),
            ("expected_samples_per_run", 16),
        ):
            if raw.get(field) != value:
                errors.append(f"{field}={raw.get(field)!r}, expected {value!r}")
        errors.extend(validate_sample_observation(raw.get("run_a"), case, "run_a"))
        errors.extend(validate_sample_observation(raw.get("run_b"), case, "run_b"))
        if raw.get("run_a") != raw.get("run_b"):
            errors.append("ordinary run_a and run_b differ")
    elif case["mode"] == "concurrent":
        for field, value in (
            ("effective_replicas", [1, 1, 1, 1]),
            ("target_instances", 4),
            ("probes_per_instance", 16),
            ("expected_calls_per_instance", 16),
            ("expected_calls_total", 64),
            ("calls_per_instance", [16, 16, 16, 16]),
            ("calls_total", 64),
        ):
            if raw.get(field) != value:
                errors.append(f"{field}={raw.get(field)!r}, expected {value!r}")
        instances = raw.get("instances")
        if not isinstance(instances, list) or len(instances) != 4:
            errors.append("instances must contain exactly four observations")
        else:
            for index, observation in enumerate(instances):
                errors.extend(
                    validate_concurrent_observation(
                        observation, case, f"instances[{index}]"
                    )
                )
            if instances[1:] != [instances[0]] * 3:
                errors.append("concurrent target observations differ")
    else:
        errors.append(f"unknown raw mode {case['mode']!r}")
    return errors


def run_case(binary: Path, case: dict[str, Any]) -> dict[str, Any]:
    identifier = case_id(case)
    marker_path = LAUNCHES / f"{identifier}.json"
    record_path = PROCESSES / f"{identifier}.json"
    raw_path = RAW / f"{identifier}.json"
    heartbeat_path = HEARTBEATS / identifier
    stdout_path = STDOUT / f"{identifier}.txt"
    stderr_path = STDERR / f"{identifier}.txt"
    for path in (marker_path, record_path, raw_path, heartbeat_path):
        if path.exists():
            raise RuntimeError(
                f"{path} already exists; no final child may be resumed or rerun"
            )
    command = [
        str(binary.resolve()),
        case["mode"],
        case["shape"],
        case["model"],
        case["data"],
        str(case["seed"]),
        str(heartbeat_path),
        str(raw_path),
    ]
    launch_started_utc = utc_now()
    write_json(
        marker_path,
        {
            "schema": "bridgestan-owned-worker-final-launch",
            "case_id": identifier,
            "mode": case["mode"],
            "shape": case["shape"],
            "seed": case["seed"],
            "started_utc": launch_started_utc,
            "binary_sha256": sha256(binary),
            "command": command,
        },
        replace=False,
    )
    begin = time.perf_counter()
    process_started_unix_ms = int(time.time() * 1000)
    process = subprocess.Popen(
        command,
        cwd=HERE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    code: int | None = None
    timed_out = False
    stdout_bytes = b""
    stderr_bytes = b""
    try:
        stdout_bytes, stderr_bytes = process.communicate(timeout=TIMEOUT_SECONDS)
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
    raw_parse_error: str | None = None
    if raw_path.is_file():
        try:
            raw_result = json.loads(raw_path.read_text(encoding="utf-8"))
        except Exception as error:  # noqa: BLE001 - malformed evidence is data
            raw_parse_error = str(error)
    raw_errors = (
        validate_raw(raw_result, case)
        if raw_parse_error is None and raw_path.is_file()
        else []
    )
    heartbeat_complete, heartbeats, heartbeat_errors = assess_heartbeats(
        heartbeat_path, case
    )
    reasons = []
    if timed_out:
        reasons.append("child timed out")
    if code != 0:
        reasons.append(f"child return code was {code!r}, not zero")
    if not raw_path.is_file():
        reasons.append("raw output is missing")
    elif raw_parse_error:
        reasons.append(f"raw output is malformed: {raw_parse_error}")
    reasons.extend(f"raw invariant: {error}" for error in raw_errors)
    if not heartbeat_complete:
        reasons.append("required heartbeat sequence is incomplete")
    record = {
        "schema": "bridgestan-owned-worker-final-process",
        "case_id": identifier,
        "mode": case["mode"],
        "shape": case["shape"],
        "seed": case["seed"],
        "status": "ok" if not reasons else "process_fault",
        "process_success": not reasons,
        "process_fault": bool(reasons),
        "failure_reasons": reasons,
        "return_code": return_code_forms(code),
        "timed_out": timed_out,
        "duration_seconds": duration,
        "raw_output_exists": raw_path.is_file(),
        "raw_output_error": raw_parse_error,
        "raw_invariant_errors": raw_errors,
        "raw_result": raw_result,
        "heartbeat_complete": heartbeat_complete,
        "heartbeat_errors": heartbeat_errors,
        "heartbeats": heartbeats,
        "last_heartbeat": heartbeats[-1] if heartbeats else None,
        "stdout_path": stdout_path.relative_to(HERE).as_posix(),
        "stderr_path": stderr_path.relative_to(HERE).as_posix(),
        "stdout": stdout,
        "stderr": stderr,
        "launch_started_utc": launch_started_utc,
        "finished_utc": utc_now(),
        "child_pid": process.pid,
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
        "-ErrorAction Stop | ForEach-Object { [pscustomobject]@{"
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
    if completed.returncode == 0:
        try:
            parsed = json.loads(completed.stdout) if completed.stdout.strip() else []
            if isinstance(parsed, dict):
                parsed = [parsed]
            if not isinstance(parsed, list):
                parse_error = "event query did not return a list"
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
        "application_start_hex": (
            r"(?im)^Faulting application start time:\s*(0x[0-9a-f]+)\s*$"
        ),
        "application_path": r"(?im)^Faulting application path:\s*(.+?)\s*$",
        "exception_code": r"(?im)^Exception code:\s*(0x[0-9a-f]+)\s*$",
        "faulting_module": r"(?im)^Faulting module name:\s*([^,\r\n]+)",
        "report_id": r"(?im)^Report Id:\s*(.+?)\s*$",
    }
    values: dict[str, Any] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, message)
        values[key] = match.group(1).strip() if match else None
    values["faulting_process_id"] = (
        int(values["process_id_hex"], 16)
        if values["process_id_hex"] is not None
        else None
    )
    if values["application_start_hex"] is not None:
        ticks = int(values["application_start_hex"], 16)
        values["application_start_unix_ms"] = (
            ticks - 116444736000000000
        ) // 10000
    else:
        values["application_start_unix_ms"] = None
    return values


def normalize_windows_path(path: str) -> str:
    return os.path.normcase(os.path.abspath(path)).replace("/", "\\")


def correlated_event_1000(
    record: dict[str, Any], events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    expected_path = normalize_windows_path(record["binary_path"])
    result = []
    for event in events:
        parsed = parse_event_1000(event)
        if parsed is None:
            continue
        if parsed["faulting_process_id"] != record["child_pid"]:
            continue
        application_path = parsed.get("application_path")
        if application_path is None:
            continue
        if normalize_windows_path(application_path) != expected_path:
            continue
        event_start = parsed.get("application_start_unix_ms")
        if event_start is None:
            continue
        if abs(event_start - record["process_started_unix_ms"]) > 5000:
            continue
        result.append({"event": event, "parsed": parsed})
    return result


def event_parse_anomalies(
    binary_path: str, events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    expected_path = normalize_windows_path(binary_path)
    expected_name = Path(binary_path).name.lower()
    anomalies = []
    for event in events:
        parsed = parse_event_1000(event)
        if parsed is None:
            continue
        message = str(event.get("message", "")).lower()
        application_path = parsed.get("application_path")
        mentions_binary = expected_name in message
        path_matches = (
            application_path is not None
            and normalize_windows_path(application_path) == expected_path
        )
        required = (
            parsed.get("faulting_process_id"),
            parsed.get("application_start_unix_ms"),
            application_path,
        )
        if (mentions_binary or path_matches) and any(value is None for value in required):
            anomalies.append({"event": event, "parsed": parsed})
    return anomalies


def load_records() -> dict[str, dict[str, Any]]:
    return {
        record["case_id"]: record
        for path in sorted(PROCESSES.glob("*.json"))
        for record in [json.loads(path.read_text(encoding="utf-8"))]
    }


def median_duration(records: list[dict[str, Any]]) -> float | None:
    durations = [
        float(record["duration_seconds"])
        for record in records
        if record.get("duration_seconds") is not None
    ]
    return statistics.median(durations) if durations else None


def zero_failure_upper_bound(n: int) -> float:
    return 1.0 - math.pow(0.05, 1.0 / n)


def analyze() -> dict[str, Any]:
    expected_cases = cases()
    expected_ids = [case_id(case) for case in expected_cases]
    records = load_records()
    missing = [identifier for identifier in expected_ids if identifier not in records]
    unexpected = sorted(set(records) - set(expected_ids))
    ordered = [records[identifier] for identifier in expected_ids if identifier in records]
    expected_set = set(expected_ids)
    artifact_inventories = {
        "launches": {path.stem for path in LAUNCHES.glob("*.json")},
        "processes": {path.stem for path in PROCESSES.glob("*.json")},
        "raw": {path.stem for path in RAW.glob("*.json")},
        "heartbeats": {path.name for path in HEARTBEATS.iterdir()}
        if HEARTBEATS.exists()
        else set(),
        "stdout": {path.stem for path in STDOUT.glob("*.txt")},
        "stderr": {path.stem for path in STDERR.glob("*.txt")},
    }
    artifact_inventory = {
        kind: {
            "count": len(observed),
            "missing": sorted(expected_set - observed),
            "unexpected": sorted(observed - expected_set),
            "exact": observed == expected_set,
        }
        for kind, observed in artifact_inventories.items()
    }
    capture = (
        json.loads(WINDOWS_EVENTS.read_text(encoding="utf-8"))
        if WINDOWS_EVENTS.exists()
        else {"available": False, "reason": "event capture missing", "events": []}
    )
    events = capture.get("events", []) if capture.get("available") else []
    correlations = {
        record["case_id"]: correlated_event_1000(record, events)
        for record in ordered
    }
    binary_path = (
        ordered[0]["binary_path"]
        if ordered
        else json.loads(BINARY_MANIFEST.read_text(encoding="utf-8"))["binary"][
            "path"
        ]
    )
    event_anomalies = event_parse_anomalies(binary_path, events)
    write_json(
        EVENT_CORRELATIONS,
        {
            "schema": "bridgestan-owned-worker-final-event-correlations",
            "event_capture_available": bool(capture.get("available")),
            "parse_anomalies": event_anomalies,
            "records": correlations,
        },
    )

    by_mode: dict[str, Any] = {}
    for mode, planned in (("ordinary", 540), ("concurrent", 180)):
        mode_records = [record for record in ordered if record["mode"] == mode]
        final_faults = [
            record
            for record in mode_records
            if record["process_fault"] or correlations[record["case_id"]]
        ]
        by_mode[mode] = {
            "planned": planned,
            "recorded": len(mode_records),
            "process_successes": sum(
                bool(record["process_success"]) for record in mode_records
            ),
            "process_faults": sum(
                bool(record["process_fault"]) for record in mode_records
            ),
            "faults_including_correlated_event_1000": len(final_faults),
            "nonzero_exits": sum(
                record["return_code"]["raw"] not in (0, None)
                for record in mode_records
            ),
            "timeouts": sum(bool(record["timed_out"]) for record in mode_records),
            "missing_outputs": sum(
                record["raw_output_exists"] is not True for record in mode_records
            ),
            "incomplete_heartbeats": sum(
                not bool(record["heartbeat_complete"]) for record in mode_records
            ),
            "raw_invariant_failures": sum(
                bool(record["raw_invariant_errors"]) for record in mode_records
            ),
            "correlated_event_1000": sum(
                bool(correlations[record["case_id"]]) for record in mode_records
            ),
            "duration_seconds_median": median_duration(mode_records),
            "by_shape": {
                shape: {
                    "planned": 180 if mode == "ordinary" else 60,
                    "recorded": sum(
                        record["shape"] == shape for record in mode_records
                    ),
                    "faults": sum(
                        record["shape"] == shape
                        and (
                            record["process_fault"]
                            or bool(correlations[record["case_id"]])
                        )
                        for record in mode_records
                    ),
                    "duration_seconds_median": median_duration(
                        [
                            record
                            for record in mode_records
                            if record["shape"] == shape
                        ]
                    ),
                }
                for shape in ("sblrc", "diamonds", "mesquite")
            },
        }

    total_faults = sum(
        row["faults_including_correlated_event_1000"] for row in by_mode.values()
    )
    accepted = (
        len(ordered) == 720
        and not missing
        and not unexpected
        and all(row["exact"] for row in artifact_inventory.values())
        and bool(capture.get("available"))
        and not event_anomalies
        and total_faults == 0
        and all(
            row["recorded"] == row["planned"]
            and row["nonzero_exits"] == 0
            and row["timeouts"] == 0
            and row["missing_outputs"] == 0
            and row["incomplete_heartbeats"] == 0
            and row["raw_invariant_failures"] == 0
            and row["correlated_event_1000"] == 0
            for row in by_mode.values()
        )
    )
    complete_zero = len(ordered) == 720 and not missing and total_faults == 0
    bounds = {
        "ordinary": zero_failure_upper_bound(540) if complete_zero else None,
        "concurrent": zero_failure_upper_bound(180) if complete_zero else None,
        "combined": zero_failure_upper_bound(720) if complete_zero else None,
    }
    summary = {
        "schema": "bridgestan-owned-worker-final-summary",
        "generated_utc": utc_now(),
        "source_commit": json.loads(
            BINARY_MANIFEST.read_text(encoding="utf-8")
        )["source_commit"],
        "protocol_sha256": sha256(PROTOCOL),
        "planned_records": 720,
        "recorded_records": len(ordered),
        "missing_records": missing,
        "unexpected_records": unexpected,
        "artifact_inventory": artifact_inventory,
        "event_capture_available": bool(capture.get("available")),
        "event_parse_anomalies": event_anomalies,
        "by_mode": by_mode,
        "faults_including_correlated_event_1000": total_faults,
        "exact_parity_and_invariant_failures": sum(
            bool(record["raw_invariant_errors"]) for record in ordered
        ),
        "zero_failure_one_sided_95_percent_upper_bounds": bounds,
        "zero_failure_one_sided_95_percent_upper_bounds_percent": {
            key: value * 100.0 if value is not None else None
            for key, value in bounds.items()
        },
        "accepted": accepted,
        "mitigation_gate_blocked": not accepted,
        "release_blocked": True,
        "remaining_release_blockers": [
            "Windows MSVC qualification",
            "Linux and macOS BridgeStan qualification",
            "cross-platform package/wheel matrix",
            "Windows Python from_stan remains disabled",
        ],
        "scope": (
            "Windows GNU, one host, three frozen WP35 model/data assets, "
            "short diagnostic runs and concurrent four-target probes"
        ),
        "diagnostic_only": True,
    }
    write_json(SUMMARY, summary)
    return summary


def run_all(binary: Path) -> dict[str, Any]:
    if any(LAUNCHES.glob("*.json")) or any(PROCESSES.glob("*.json")):
        raise RuntimeError(
            "final launch/process records already exist; no resume or rerun is permitted"
        )
    if not BINARY_MANIFEST.exists():
        prepare(binary)
    manifest = json.loads(BINARY_MANIFEST.read_text(encoding="utf-8"))
    actual_binary = binary_details(binary)
    if actual_binary != manifest["binary"]:
        raise RuntimeError("final child binary differs from the pre-run manifest")
    integrity = verify_historical_integrity()
    if not integrity["verified"]:
        raise RuntimeError("historical raw artifacts changed after final prepare")
    if MEASURED_ON.exists() or WINDOWS_EVENTS.exists():
        raise RuntimeError("final execution/event records already exist")
    write_json(
        MEASURED_ON,
        {
            "schema": "bridgestan-owned-worker-final-environment",
            "started_utc": utc_now(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "machine": platform.machine(),
            "python": sys.version,
            "cpu_count": os.cpu_count(),
            "binary_manifest_sha256": sha256(BINARY_MANIFEST),
            "historical_integrity_sha256": sha256(HISTORICAL_INTEGRITY),
        },
        replace=False,
    )
    expanded = cases()
    for index, case in enumerate(expanded, 1):
        record = run_case(binary, case)
        print(
            f"[{index:03}/720] {record['case_id']}: {record['status']} "
            f"return={record['return_code']['hex_32']} "
            f"{record['duration_seconds']:.3f}s",
            flush=True,
        )
    time.sleep(EVENT_SETTLE_SECONDS)
    started = json.loads(MEASURED_ON.read_text(encoding="utf-8"))["started_utc"]
    query_start = (
        datetime.fromisoformat(started.replace("Z", "+00:00"))
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
    for command in ("verify", "prepare", "run"):
        child = subparsers.add_parser(command)
        child.add_argument("--binary", type=Path, required=True)
    subparsers.add_parser("analyze")
    args = parser.parse_args()
    if args.command == "verify":
        print(json.dumps(verify_inputs(args.binary), indent=2, sort_keys=True))
    elif args.command == "prepare":
        print(json.dumps(prepare(args.binary), indent=2, sort_keys=True))
    elif args.command == "run":
        run_all(args.binary)
    else:
        print(json.dumps(analyze(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
