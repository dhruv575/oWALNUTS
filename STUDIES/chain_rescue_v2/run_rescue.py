#!/usr/bin/env python3
"""Execute and analyze the frozen WP36 chain-rescue-v2 protocol.

Commands:
  run_rescue.py verify
  run_rescue.py run
  run_rescue.py analyze
  run_rescue.py conformance

`run` is the only command that launches evidence cells. It follows the frozen
target/seed/rotated-arm order and refuses every rerun once either a launch
marker or process record exists.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import statistics
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np

HERE = Path(__file__).resolve().parent
PROTOCOL_PATH = HERE / "protocol.json"
PROTOCOL = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
ARTIFACTS = HERE / "artifacts"
RAW = ARTIFACTS / "raw"
PROCESSES = ARTIFACTS / "processes"
LAUNCHES = ARTIFACTS / "launches"
HEARTBEATS = ARTIFACTS / "heartbeats"
STDOUT = ARTIFACTS / "stdout"
STDERR = ARTIFACTS / "stderr"
CELLS = ARTIFACTS / "cells"
DRAWS = ARTIFACTS / "draws"
CONFORMANCE = ARTIFACTS / "conformance" / "observe-vs-disabled.json"

DEFAULT_ASSETS = Path(
    r"C:\dev\owalnuts-wt\posteriordb-v6\STUDIES\posteriordb_bench_v6"
)
ASSETS = Path(os.environ.get("WP36_ASSETS", DEFAULT_ASSETS))
MODEL_DIR = Path(os.environ.get("WP36_MODEL_DIR", ASSETS / "models"))
PDB_PATH = Path(
    os.environ.get("WP36_POSTERIORDB_PATH", ASSETS / "posteriordb" / "posterior_database")
)
BIN_DIR = Path(os.environ.get("WP36_BIN_DIR", HERE / "target" / "release"))
EXE = ".exe" if os.name == "nt" else ""
HARNESS = BIN_DIR / f"chain-rescue-v2{EXE}"
FUNNEL = BIN_DIR / f"funnel{EXE}"
CONFORMANCE_BIN = BIN_DIR / f"conformance{EXE}"

ARMS = ("observe", "current", "two_hit")
TARGETS = tuple(PROTOCOL["execution_order"]["target_order"])
MODELS = tuple(PROTOCOL["posteriordb"]["models"])
SEEDS = tuple(int(seed) for seed in PROTOCOL["seeds"])
TIMEOUT = int(os.environ.get("WP36_CELL_TIMEOUT_SECONDS", "7200"))
INITIAL_DOMAIN = b"chain_rescue_v2.initial_position.v1"
RETAINED_DOMAIN = b"chain_rescue_v2.retained_unconstrained.v1"
ARRAY_DOMAIN = b"chain_rescue_v2.numpy_array.v1"
BOUNDARY_FIELDS = set(PROTOCOL["telemetry"]["required_per_boundary_per_chain"])
RESTART_FIELDS = set(PROTOCOL["telemetry"]["required_on_restart"])
OUTCOMES = set(PROTOCOL["telemetry"]["outcomes"])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def short(target: str) -> str:
    return target.replace("-", "__").replace("'", "").replace(" ", "_")


def cell_id(target: str, arm: str, seed: int) -> str:
    return f"{short(target)}-{arm}-{seed}"


def raw_path(target: str, arm: str, seed: int) -> Path:
    return RAW / f"{cell_id(target, arm, seed)}.json"


def process_path(target: str, arm: str, seed: int) -> Path:
    return PROCESSES / f"{cell_id(target, arm, seed)}.json"


def cell_path(target: str, arm: str, seed: int) -> Path:
    return CELLS / f"{cell_id(target, arm, seed)}.json"


def arm_order(seed_index: int) -> tuple[str, str, str]:
    return (
        ("observe", "current", "two_hit"),
        ("current", "two_hit", "observe"),
        ("two_hit", "observe", "current"),
    )[seed_index % 3]


def planned_cells() -> list[tuple[str, int, str]]:
    return [
        (target, seed, arm)
        for target in TARGETS
        for index, seed in enumerate(SEEDS)
        for arm in arm_order(index)
    ]


def initial_position_sha256(position: Iterable[float]) -> str:
    values = list(position)
    digest = hashlib.sha256()
    digest.update(INITIAL_DOMAIN)
    digest.update(struct.pack("<Q", len(values)))
    for value in values:
        digest.update(struct.pack("<d", float(value)))
    return digest.hexdigest()


def rust_retained_sha256(values: np.ndarray) -> str:
    array = np.asarray(values, dtype="<f8", order="C")
    if array.ndim != 2:
        raise ValueError("Rust retained hash requires a 2-D draw matrix")
    digest = hashlib.sha256()
    digest.update(RETAINED_DOMAIN)
    digest.update(struct.pack("<Q", array.shape[0]))
    digest.update(struct.pack("<Q", array.shape[1]))
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def array_sha256(values: np.ndarray) -> str:
    array = np.asarray(values, dtype="<f8", order="C")
    digest = hashlib.sha256()
    digest.update(ARRAY_DOMAIN)
    digest.update(struct.pack("<Q", array.ndim))
    for extent in array.shape:
        digest.update(struct.pack("<Q", extent))
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def return_code_forms(code: int | None) -> dict[str, int | str | None]:
    if code is None:
        return {"raw": None, "signed_32": None, "unsigned_32": None, "hex_32": None}
    unsigned = code & 0xFFFFFFFF
    signed = unsigned - (1 << 32) if unsigned >= (1 << 31) else unsigned
    return {
        "raw": code,
        "signed_32": signed,
        "unsigned_32": unsigned,
        "hex_32": f"0x{unsigned:08X}",
    }


def expected_heartbeat_sequence() -> list[tuple[str, str]]:
    return [
        ("process", "start"),
        ("load", "before"),
        ("load", "after"),
        ("initialization", "before"),
        ("initialization", "after"),
        ("sampling", "before"),
        ("sampling", "after"),
        ("result", "before"),
        ("result", "after"),
        ("drop", "before"),
        ("drop", "after"),
        ("process", "complete"),
    ]


def heartbeat_assessment(path: Path) -> tuple[bool, list[dict[str, Any]], list[str]]:
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    for event_path in sorted(path.glob("*.json")):
        try:
            event = json.loads(event_path.read_text(encoding="utf-8"))
            event["_file"] = event_path.name
            events.append(event)
        except Exception as error:  # malformed durable output is itself evidence
            errors.append(f"{event_path.name}: {error}")
    sequence = [event.get("sequence") for event in events]
    if sequence != list(range(len(events))):
        errors.append(f"non-contiguous heartbeat sequence: {sequence}")
    actual = [(event.get("stage"), event.get("boundary")) for event in events]
    if actual != expected_heartbeat_sequence():
        errors.append(
            f"heartbeat sequence mismatch: got {actual}, expected {expected_heartbeat_sequence()}"
        )
    return not errors, events, errors


def decode_capture(value: bytes | str | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def model_paths(target: str) -> tuple[Path, Path]:
    stem = short(target)
    return MODEL_DIR / f"{stem}_model.so", MODEL_DIR / f"{stem}.data.json"


def validate_environment(require_binaries: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    if len(planned_cells()) != 288:
        errors.append(f"planned cell count is {len(planned_cells())}, expected 288")
    if len(SEEDS) != 12 or len(set(SEEDS)) != 12:
        errors.append("protocol must contain 12 unique evidence seeds")
    if TARGETS[-1] != "funnel-10d" or tuple(TARGETS[:-1]) != MODELS:
        errors.append("target order does not match the frozen model order plus funnel")
    observed_models = {}
    for target in MODELS:
        model, data = model_paths(target)
        observed_models[target] = {
            "model": str(model),
            "model_exists": model.is_file(),
            "data": str(data),
            "data_exists": data.is_file(),
        }
        if not model.is_file() or not data.is_file():
            errors.append(f"external compiled model/data missing for {target}")
    binaries = {
        "cell": str(HARNESS),
        "funnel": str(FUNNEL),
        "conformance": str(CONFORMANCE_BIN),
    }
    if require_binaries:
        for name, value in binaries.items():
            if not Path(value).is_file():
                errors.append(f"{name} binary missing: {value}")
    pdb_commit = None
    if PDB_PATH.exists():
        try:
            completed = subprocess.run(
                ["git", "-C", str(PDB_PATH), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode == 0:
                pdb_commit = completed.stdout.strip()
                if pdb_commit != PROTOCOL["posteriordb"]["commit"]:
                    errors.append(
                        f"posteriordb commit {pdb_commit} != frozen "
                        f"{PROTOCOL['posteriordb']['commit']}"
                    )
        except OSError as error:
            errors.append(f"could not inspect posteriordb checkout: {error}")
    else:
        errors.append(f"posteriordb checkout missing: {PDB_PATH}")
    result = {
        "verified": not errors,
        "errors": errors,
        "protocol_sha256": sha256(PROTOCOL_PATH),
        "assets": str(ASSETS),
        "model_dir": str(MODEL_DIR),
        "posteriordb_path": str(PDB_PATH),
        "posteriordb_commit": pdb_commit,
        "models": observed_models,
        "binaries": binaries,
    }
    if errors:
        raise RuntimeError("; ".join(errors))
    return result


def validate_boundary(event: dict[str, Any], target: str, arm: str, seed: int) -> list[str]:
    errors = [f"missing boundary field {name}" for name in sorted(BOUNDARY_FIELDS - event.keys())]
    if event.get("target") != target or event.get("arm") != arm or event.get("seed") != seed:
        errors.append("boundary target/arm/seed does not match its cell")
    outcome = event.get("outcome")
    if outcome not in OUTCOMES:
        errors.append(f"invalid outcome {outcome!r}")
    if outcome == "restarted":
        errors.extend(
            f"restart field {name} is missing/null"
            for name in sorted(RESTART_FIELDS)
            if event.get(name) is None
        )
    elif any(event.get(name) is not None for name in RESTART_FIELDS):
        errors.append("non-restart boundary contains restart-only fields")
    if arm == "observe" and (
        outcome in {"restarted", "pending_first_hit"}
        or event.get("source_window_position_index") is not None
        or event.get("installed_position_sha256") is not None
    ):
        errors.append("observe consumed or simulated rescue state")
    if event.get("step_hit") and event.get("density_hit"):
        if event.get("observed_canonical_criterion") != "Step":
            errors.append("canonical criterion did not give Step priority")
    return errors


def validate_raw(
    raw: Any, target: str, arm: str, seed: int
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(raw, dict):
        return False, ["raw result is not an object"]
    expected_schema = (
        "chain-rescue-v2-funnel-raw" if target == "funnel-10d" else "chain-rescue-v2-cell-raw"
    )
    if raw.get("schema") != expected_schema:
        errors.append(f"schema is {raw.get('schema')!r}, expected {expected_schema!r}")
    if raw.get("complete") is not True:
        errors.append("raw result is not marked complete")
    if raw.get("target") != target or raw.get("arm") != arm or raw.get("seed") != seed:
        errors.append("raw target/arm/seed mismatch")
    if raw.get("status") not in {"ok", "sampler_error"}:
        errors.append(f"invalid raw status {raw.get('status')!r}")
    starts = raw.get("initial_positions")
    hashes = raw.get("initial_position_sha256")
    if not isinstance(starts, list) or not isinstance(hashes, list):
        errors.append("initial positions or hashes are not arrays")
    elif len(starts) != len(hashes):
        errors.append("initial position/hash lengths differ")
    else:
        for index, (start, recorded) in enumerate(zip(starts, hashes)):
            try:
                actual = initial_position_sha256(start)
                if actual != recorded:
                    errors.append(f"initial position hash mismatch for chain {index}")
            except Exception as error:
                errors.append(f"could not hash initial chain {index}: {error}")
    if raw.get("status") == "sampler_error":
        if not raw.get("error"):
            errors.append("sampler_error result lacks an error message")
        return not errors, errors
    if len(starts or []) != 4 or len(hashes or []) != 4:
        errors.append("successful cell does not contain four starts and hashes")
    chains = raw.get("chains_data")
    if not isinstance(chains, list) or len(chains) != 4:
        errors.append("successful cell does not contain four chain records")
        return not errors, errors
    expected_draws = 20_000 if target == "funnel-10d" else 1_000
    restarts: list[dict[str, Any]] = []
    for index, chain in enumerate(chains):
        if chain.get("chain") != index:
            errors.append(f"chain record {index} has the wrong index")
        if chain.get("initial_position_sha256") != hashes[index]:
            errors.append(f"chain {index} repeats a different initial hash")
        samples = chain.get("samples")
        try:
            array = np.asarray(samples, dtype=np.float64)
            if array.ndim != 2 or array.shape[0] != expected_draws:
                errors.append(f"chain {index} retained draw shape is {array.shape}")
            elif rust_retained_sha256(array) != chain.get("retained_unconstrained_sha256"):
                errors.append(f"chain {index} retained hash mismatch")
        except Exception as error:
            errors.append(f"chain {index} retained draws are malformed: {error}")
        for event_index, event in enumerate(chain.get("chain_rescues", [])):
            event_errors = validate_boundary(event, target, arm, seed)
            errors.extend(
                f"chain {index} boundary {event_index}: {message}" for message in event_errors
            )
            if event.get("initial_position_sha256") != hashes[index]:
                errors.append(f"chain {index} boundary {event_index}: wrong initial hash")
            if event.get("outcome") == "restarted":
                restarts.append(event)
    if raw.get("actions") != restarts:
        errors.append("top-level actions are not exactly the ordered restart records")
    return not errors, errors


def interrupted_record(
    target: str, seed: int, arm: str, marker: Path
) -> dict[str, Any]:
    reason = (
        "launch marker exists without a process record; protocol forbids rerunning "
        "a potentially launched child"
    )
    return {
        "schema": "chain-rescue-v2-process",
        "cell_id": cell_id(target, arm, seed),
        "target": target,
        "seed": seed,
        "arm": arm,
        "status": "orchestrator_interrupted",
        "process_valid": False,
        "fault": True,
        "failure_reasons": [reason],
        "launch_marker": marker.relative_to(HERE).as_posix(),
        "return_code": return_code_forms(None),
        "timed_out": None,
        "raw_output_exists": None,
        "raw_schema_valid": False,
        "heartbeat_complete": False,
        "heartbeats": [],
    }


def process_failure_reasons(
    *,
    timed_out: bool,
    return_code: int | None,
    raw_exists: bool,
    raw_parse_error: str | None,
    raw_valid: bool,
    heartbeat_complete: bool,
) -> list[str]:
    reasons: list[str] = []
    if timed_out:
        reasons.append("child timed out")
    if return_code != 0:
        reasons.append(f"child return code was {return_code!r}, not zero")
    if not raw_exists:
        reasons.append("raw output is missing")
    elif raw_parse_error:
        reasons.append(f"raw output is malformed JSON: {raw_parse_error}")
    elif not raw_valid:
        reasons.append("raw output failed schema/protocol validation")
    if not heartbeat_complete:
        reasons.append("required heartbeat sequence is incomplete")
    return reasons


def run_case(target: str, seed: int, arm: str) -> dict[str, Any]:
    identifier = cell_id(target, arm, seed)
    record_path = PROCESSES / f"{identifier}.json"
    marker = LAUNCHES / f"{identifier}.json"
    if record_path.exists():
        return json.loads(record_path.read_text(encoding="utf-8"))
    if marker.exists():
        record = interrupted_record(target, seed, arm, marker)
        write_json(record_path, record)
        return record

    output = raw_path(target, arm, seed)
    heartbeat_dir = HEARTBEATS / identifier
    stdout_path = STDOUT / f"{identifier}.txt"
    stderr_path = STDERR / f"{identifier}.txt"
    if target == "funnel-10d":
        command = [
            str(FUNNEL),
            arm,
            str(seed),
            str(heartbeat_dir),
            str(output),
        ]
    else:
        model, data = model_paths(target)
        command = [
            str(HARNESS),
            target,
            str(model),
            str(data),
            arm,
            str(seed),
            str(heartbeat_dir),
            str(output),
            "4",
        ]
    write_json(
        marker,
        {
            "schema": "chain-rescue-v2-launch",
            "cell_id": identifier,
            "target": target,
            "seed": seed,
            "arm": arm,
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
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
            timeout=TIMEOUT,
            check=False,
        )
        code = completed.returncode
        stdout = decode_capture(completed.stdout)
        stderr = decode_capture(completed.stderr)
    except subprocess.TimeoutExpired as error:
        timed_out = True
        stdout = decode_capture(error.stdout)
        stderr = decode_capture(error.stderr)
    duration = time.perf_counter() - begin
    atomic_write_text(stdout_path, stdout)
    atomic_write_text(stderr_path, stderr)

    raw_exists = output.is_file()
    raw_value: Any = None
    raw_parse_error = None
    if raw_exists:
        try:
            raw_value = json.loads(output.read_text(encoding="utf-8"))
        except Exception as error:
            raw_parse_error = str(error)
    raw_valid, raw_errors = (
        validate_raw(raw_value, target, arm, seed)
        if raw_parse_error is None and raw_exists
        else (False, [raw_parse_error or "raw output is missing"])
    )
    heartbeat_complete, heartbeats, heartbeat_errors = heartbeat_assessment(heartbeat_dir)
    reasons = process_failure_reasons(
        timed_out=timed_out,
        return_code=code,
        raw_exists=raw_exists,
        raw_parse_error=raw_parse_error,
        raw_valid=raw_valid,
        heartbeat_complete=heartbeat_complete,
    )
    process_valid = not reasons
    record = {
        "schema": "chain-rescue-v2-process",
        "cell_id": identifier,
        "target": target,
        "seed": seed,
        "arm": arm,
        "status": "ok" if process_valid else "process_fault",
        "process_valid": process_valid,
        "fault": not process_valid,
        "failure_reasons": reasons,
        "command": command,
        "return_code": return_code_forms(code),
        "duration_seconds": duration,
        "timed_out": timed_out,
        "raw_output_exists": raw_exists,
        "raw_output_path": output.relative_to(HERE).as_posix(),
        "raw_output_bytes": output.stat().st_size if raw_exists else None,
        "raw_output_sha256": sha256(output) if raw_exists else None,
        "raw_output_status": raw_value.get("status") if isinstance(raw_value, dict) else None,
        "raw_parse_error": raw_parse_error,
        "raw_schema_valid": raw_valid,
        "raw_validation_errors": raw_errors,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_path": stdout_path.relative_to(HERE).as_posix(),
        "stderr_path": stderr_path.relative_to(HERE).as_posix(),
        "heartbeat_complete": heartbeat_complete,
        "heartbeat_errors": heartbeat_errors,
        "heartbeats": heartbeats,
        "last_heartbeat": heartbeats[-1] if heartbeats else None,
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(record_path, record)
    return record


def run_all() -> None:
    verification = validate_environment(require_binaries=True)
    measured = ARTIFACTS / "measured_on.json"
    if not measured.exists():
        write_json(
            measured,
            {
                "schema": "chain-rescue-v2-environment",
                "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "platform": platform.platform(),
                "processor": platform.processor(),
                "machine": platform.machine(),
                "python": sys.version,
                "cpu_count": os.cpu_count(),
                "verification": verification,
                "note": "wall time is reported but not gated on this shared machine",
            },
        )
    plan = planned_cells()
    for index, (target, seed, arm) in enumerate(plan, start=1):
        record = run_case(target, seed, arm)
        print(
            f"[{index:03}/{len(plan)}] {record['cell_id']}: {record['status']} "
            f"return={record['return_code']['hex_32']}",
            flush=True,
        )
    analyze()


# ---------------------------------------------------------------------------
# Draw transformation, diagnostics, and origin classification


def posterior(target: str):
    from posteriordb import PosteriorDatabase

    return PosteriorDatabase(str(PDB_PATH)).posterior(target)


def bridgestan_name(name: str) -> str:
    parts = name.split(".")
    if len(parts) == 1 or not all(part.isdigit() for part in parts[1:]):
        return name
    return f"{parts[0]}[{','.join(parts[1:])}]"


def arviz_stats(draws: np.ndarray) -> dict[str, np.ndarray]:
    import arviz as az

    dataset = az.convert_to_dataset({"p": draws})
    return {
        "mean": draws.reshape(-1, draws.shape[-1]).mean(axis=0),
        "sd": draws.reshape(-1, draws.shape[-1]).std(axis=0, ddof=1),
        "bulk_ess": np.asarray(az.ess(dataset, method="bulk").p.values, dtype=float),
        "tail_ess": np.asarray(
            az.ess(dataset, method="tail", prob=(0.05, 0.95)).p.values, dtype=float
        ),
        "rhat": np.asarray(az.rhat(dataset, method="rank").p.values, dtype=float),
        "mcse": np.asarray(az.mcse(dataset, method="mean").p.values, dtype=float),
    }


def reference(target: str) -> dict[str, Any]:
    raw = posterior(target).reference_draws()
    names = list(raw[0].keys())
    draws = np.asarray([[chain[name] for name in names] for chain in raw], dtype=np.float64)
    draws = np.transpose(draws, (0, 2, 1))
    return {
        "names": names,
        "draws": draws,
        "median": np.quantile(draws.reshape(-1, draws.shape[-1]), 0.5, axis=0, method="linear"),
        "iqr": np.quantile(draws.reshape(-1, draws.shape[-1]), 0.75, axis=0, method="linear")
        - np.quantile(draws.reshape(-1, draws.shape[-1]), 0.25, axis=0, method="linear"),
        **arviz_stats(draws),
    }


def stable_separated_origins(
    draws: np.ndarray,
    names: list[str],
    reference_median: np.ndarray,
    reference_iqr: np.ndarray,
) -> dict[str, Any]:
    if draws.shape[0] != 4 or draws.shape[1] < 2 or draws.shape[1] % 2:
        raise ValueError("origin classification requires four chains and two equal retained halves")
    half = draws.shape[1] // 2
    details: dict[str, Any] = {}
    origin_chains: list[int] = []
    for chain in range(4):
        others = np.delete(draws, chain, axis=0)
        separated: list[str] = []
        parameter_details: dict[str, Any] = {}
        for parameter, name in enumerate(names):
            values = [
                draws[chain, :half, parameter],
                draws[chain, half:, parameter],
                others[:, :half, parameter].reshape(-1),
                others[:, half:, parameter].reshape(-1),
            ]
            iqr = float(reference_iqr[parameter])
            median = float(reference_median[parameter])
            finite = all(np.isfinite(value).all() for value in values) and math.isfinite(
                iqr
            ) and math.isfinite(median)
            if not finite or iqr <= 0:
                continue
            a1, a2, b1, b2 = (float(value.mean()) for value in values)
            stable_a = abs(a1 - a2) <= 0.25 * iqr
            stable_b = abs(b1 - b2) <= 0.25 * iqr
            near_reference = (
                abs(b1 - median) <= 0.50 * iqr and abs(b2 - median) <= 0.50 * iqr
            )
            common_sign = any(
                sign * (a1 - b1) >= 1.50 * iqr
                and sign * (a2 - b2) >= 1.50 * iqr
                for sign in (-1.0, 1.0)
            )
            matched = stable_a and stable_b and near_reference and common_sign
            if matched:
                separated.append(name)
                parameter_details[name] = {
                    "a1": a1,
                    "a2": a2,
                    "b1": b1,
                    "b2": b2,
                    "reference_median": median,
                    "reference_iqr_type7": iqr,
                }
        if separated:
            origin_chains.append(chain)
        details[str(chain)] = {
            "stable_separated_origin": bool(separated),
            "parameters": separated,
            "parameter_details": parameter_details,
        }
    return {"chains": origin_chains, "by_chain": details}


def reference_z(mean: float, reference_mean: float, mcse: float, reference_mcse: float) -> float:
    return (mean - reference_mean) / math.sqrt(mcse * mcse + reference_mcse * reference_mcse)


def reference_metrics(
    draws: np.ndarray, names: list[str], ref: dict[str, Any]
) -> dict[str, Any]:
    stats = arviz_stats(draws)
    z = (stats["mean"] - ref["mean"]) / np.sqrt(stats["mcse"] ** 2 + ref["mcse"] ** 2)
    practical = np.abs(stats["mean"] - ref["mean"]) / ref["sd"]
    parameters = {}
    decisive = []
    for index, name in enumerate(names):
        row = {
            "mean": float(stats["mean"][index]),
            "sd": float(stats["sd"][index]),
            "mcse": float(stats["mcse"][index]),
            "bulk_ess": float(stats["bulk_ess"][index]),
            "tail_ess": float(stats["tail_ess"][index]),
            "rank_folded_split_rhat": float(stats["rhat"][index]),
            "reference_mean": float(ref["mean"][index]),
            "reference_sd": float(ref["sd"][index]),
            "reference_mcse": float(ref["mcse"][index]),
            "z": float(z[index]),
            "abs_dmean_over_reference_sd": float(practical[index]),
        }
        row["decisive_reference_disagreement"] = decisive_reference_disagreement(
            row["z"], row["abs_dmean_over_reference_sd"]
        )
        if row["decisive_reference_disagreement"]:
            decisive.append(name)
        parameters[name] = row
    absolute_z = np.abs(z)
    max_z_index = int(np.nanargmax(absolute_z))
    max_d_index = int(np.nanargmax(practical))
    return {
        "stats": stats,
        "parameters": parameters,
        "min_bulk_ess": float(np.nanmin(stats["bulk_ess"])),
        "min_tail_ess": float(np.nanmin(stats["tail_ess"])),
        "max_rank_folded_split_rhat": float(np.nanmax(stats["rhat"])),
        "max_abs_z": float(absolute_z[max_z_index]),
        "argmax_abs_z": names[max_z_index],
        "max_abs_dmean_over_reference_sd": float(practical[max_d_index]),
        "argmax_abs_dmean_over_reference_sd": names[max_d_index],
        "decisive_reference_disagreements": decisive,
    }


def decisive_reference_disagreement(z: float, practical_shift: float) -> bool:
    return bool(abs(z) > 4.0 and practical_shift >= 0.10)


def diagnostic_pass(
    max_rhat: float,
    min_bulk: float,
    min_tail: float,
    divergences: int,
    finite: bool,
    sampler_error: bool,
) -> tuple[bool, dict[str, bool]]:
    gates = {
        "max_rank_folded_split_rhat": max_rhat <= 1.01,
        "min_bulk_ess": min_bulk >= 400,
        "min_tail_ess": min_tail >= 400,
        "zero_retained_divergences": divergences == 0,
        "finite_draws": finite,
        "no_sampler_error": not sampler_error,
    }
    return all(gates.values()), gates


def action_summary(raw: dict[str, Any]) -> dict[str, Any]:
    actions = list(raw.get("actions", []))
    by_criterion = {"Step": 0, "LogDensity": 0}
    for action in actions:
        criterion = action.get("observed_canonical_criterion")
        by_criterion[criterion] = by_criterion.get(criterion, 0) + 1
    return {
        "restart_actions": len(actions),
        "restarted_chain_indices": sorted({int(action["chain"]) for action in actions}),
        "unique_restarted_chains": len({int(action["chain"]) for action in actions}),
        "actions_by_criterion": by_criterion,
        "actions": actions,
    }


def base_cell(raw: dict[str, Any], process: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "chain-rescue-v2-cell",
        "target": raw["target"],
        "arm": raw["arm"],
        "seed": raw["seed"],
        "process_valid": True,
        "process_record": process["cell_id"],
        "sampler_status": raw["status"],
        "sampler_error": raw.get("error"),
        "initial_position_sha256": raw.get("initial_position_sha256", []),
        "wall_seconds": raw.get("wall_seconds"),
        "target_calls_total": raw.get("target_calls_total"),
        "raw_output_sha256": process["raw_output_sha256"],
        **action_summary(raw),
    }


def sampler_error_cell(raw: dict[str, Any], process: dict[str, Any]) -> dict[str, Any]:
    cell = base_cell(raw, process)
    cell.update(
        {
            "raw_diagnostic_pass": False,
            "credited_diagnostic_pass": False,
            "diagnostic_gates": {"no_sampler_error": False},
            "origin_overwritten": False,
            "stable_separated_origins": None,
            "decisive_reference_disagreements": [],
            "efficiency": None,
        }
    )
    return cell


def transform_posteriordb(
    target: str, unconstrained: np.ndarray, names: list[str]
) -> np.ndarray:
    import bridgestan as bs

    model_path, data_path = model_paths(target)
    bs.compile.windows_dll_path_setup()
    model = bs.StanModel(
        str(model_path), data=data_path.read_text(encoding="utf-8"), seed=1
    )
    constrained_names = [
        bridgestan_name(name)
        for name in model.param_names(include_tp=True, include_gq=False)
    ]
    index = {name: position for position, name in enumerate(constrained_names)}
    missing = [name for name in names if name not in index]
    if missing:
        raise RuntimeError(f"reference parameters missing after constrain: {missing[:5]}")
    constrained = np.empty(unconstrained.shape[:2] + (len(names),), dtype=np.float64)
    columns = [index[name] for name in names]
    for chain in range(unconstrained.shape[0]):
        for draw in range(unconstrained.shape[1]):
            full = model.param_constrain(
                unconstrained[chain, draw], include_tp=True, include_gq=False
            )
            constrained[chain, draw] = np.asarray(full, dtype=np.float64)[columns]
    return constrained


def posteriordb_cell(
    raw: dict[str, Any], process: dict[str, Any], ref: dict[str, Any]
) -> dict[str, Any]:
    if raw["status"] != "ok":
        return sampler_error_cell(raw, process)
    unconstrained = np.asarray(
        [chain["samples"] for chain in raw["chains_data"]], dtype=np.float64
    )
    constrained = transform_posteriordb(raw["target"], unconstrained, ref["names"])
    metrics = reference_metrics(constrained, ref["names"], ref)
    finite = bool(np.isfinite(unconstrained).all() and np.isfinite(constrained).all())
    divergences = sum(
        int(chain["retained_diagnostics"]["divergences"])
        for chain in raw["chains_data"]
    )
    raw_pass, gates = diagnostic_pass(
        metrics["max_rank_folded_split_rhat"],
        metrics["min_bulk_ess"],
        metrics["min_tail_ess"],
        divergences,
        finite,
        False,
    )
    calls = int(raw["target_calls_total"])
    efficiency = min(metrics["min_bulk_ess"], metrics["min_tail_ess"]) / calls
    origins = stable_separated_origins(
        constrained, ref["names"], ref["median"], ref["iqr"]
    )
    draw_path = DRAWS / f"{cell_id(raw['target'], raw['arm'], raw['seed'])}.npz"
    draw_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        draw_path,
        unconstrained=unconstrained,
        constrained=constrained,
        names=np.asarray(ref["names"]),
    )
    cell = base_cell(raw, process)
    cell.update(
        {
            "finite_draws": finite,
            "divergences": divergences,
            "max_depth_stops": sum(
                int(chain["retained_diagnostics"]["maximum_depth_stops"])
                for chain in raw["chains_data"]
            ),
            "min_bulk_ess": metrics["min_bulk_ess"],
            "min_tail_ess": metrics["min_tail_ess"],
            "max_rank_folded_split_rhat": metrics["max_rank_folded_split_rhat"],
            "max_abs_z": metrics["max_abs_z"],
            "argmax_abs_z": metrics["argmax_abs_z"],
            "max_abs_dmean_over_reference_sd": metrics[
                "max_abs_dmean_over_reference_sd"
            ],
            "argmax_abs_dmean_over_reference_sd": metrics[
                "argmax_abs_dmean_over_reference_sd"
            ],
            "decisive_reference_disagreements": metrics[
                "decisive_reference_disagreements"
            ],
            "parameters": metrics["parameters"],
            "diagnostic_gates": gates,
            "raw_diagnostic_pass": raw_pass,
            "credited_diagnostic_pass": raw_pass,
            "origin_overwritten": False,
            "stable_separated_origins": origins if raw["arm"] == "observe" else None,
            "efficiency": efficiency,
            "unconstrained_sha256": array_sha256(unconstrained),
            "constrained_sha256": array_sha256(constrained),
            "per_chain_unconstrained_sha256": [
                chain["retained_unconstrained_sha256"] for chain in raw["chains_data"]
            ],
            "final_step_size": [
                chain["final_step_size"] for chain in raw["chains_data"]
            ],
            "final_metric_sha256": [
                chain["final_metric_sha256"] for chain in raw["chains_data"]
            ],
            "final_tuning_sha256": [
                chain["final_tuning_sha256"] for chain in raw["chains_data"]
            ],
            "retained_diagnostics_sha256": [
                chain["retained_diagnostics_sha256"] for chain in raw["chains_data"]
            ],
            "non_rescue_telemetry_sha256": [
                chain["non_rescue_telemetry_sha256"] for chain in raw["chains_data"]
            ],
            "work": [chain["work"] for chain in raw["chains_data"]],
            "draw_file": draw_path.relative_to(HERE).as_posix(),
            "draw_file_sha256": sha256(draw_path),
        }
    )
    return cell


def funnel_cell(raw: dict[str, Any], process: dict[str, Any]) -> dict[str, Any]:
    if raw["status"] != "ok":
        cell = sampler_error_cell(raw, process)
        cell["funnel_full_gate"] = False
        cell["tail_mass"] = None
        return cell
    unconstrained = np.asarray(
        [chain["samples"] for chain in raw["chains_data"]], dtype=np.float64
    )
    omega = unconstrained[:, :, 0:1]
    stats = arviz_stats(omega)
    indicator = (omega < -5.0).astype(np.float64)
    indicator_stats = arviz_stats(indicator)
    estimate = float(indicator.mean())
    mcse = float(indicator_stats["mcse"][0])
    z = (estimate - 0.0478) / mcse
    finite = bool(np.isfinite(unconstrained).all())
    divergences = sum(
        int(chain["retained_diagnostics"]["divergences"])
        for chain in raw["chains_data"]
    )
    full_gate_parts = {
        "omega_rank_folded_split_rhat": float(stats["rhat"][0]) <= 1.01,
        "omega_bulk_ess": float(stats["bulk_ess"][0]) >= 400,
        "zero_retained_divergences": divergences == 0,
        "finite_draws": finite,
        "no_sampler_error": True,
    }
    analytic_iqr = 6.0 * 0.6744897501960817
    origins = stable_separated_origins(
        omega,
        ["omega"],
        np.asarray([0.0]),
        np.asarray([analytic_iqr]),
    )
    draw_path = DRAWS / f"{cell_id(raw['target'], raw['arm'], raw['seed'])}.npz"
    draw_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(draw_path, unconstrained=unconstrained, omega=omega)
    cell = base_cell(raw, process)
    cell.update(
        {
            "finite_draws": finite,
            "divergences": divergences,
            "max_depth_stops": sum(
                int(chain["retained_diagnostics"]["maximum_depth_stops"])
                for chain in raw["chains_data"]
            ),
            "tail_mass": {"estimate": estimate, "mcse": mcse, "z": z, "exact": 0.0478},
            "omega_bulk_ess": float(stats["bulk_ess"][0]),
            "omega_tail_ess": float(stats["tail_ess"][0]),
            "omega_rank_folded_split_rhat": float(stats["rhat"][0]),
            "funnel_full_gate_parts": full_gate_parts,
            "funnel_full_gate": all(full_gate_parts.values()),
            "raw_diagnostic_pass": all(full_gate_parts.values()),
            "credited_diagnostic_pass": all(full_gate_parts.values()),
            "diagnostic_gates": full_gate_parts,
            "origin_overwritten": False,
            "stable_separated_origins": origins if raw["arm"] == "observe" else None,
            "decisive_reference_disagreements": [],
            "efficiency": None,
            "unconstrained_sha256": array_sha256(unconstrained),
            "constrained_sha256": array_sha256(omega),
            "per_chain_unconstrained_sha256": [
                chain["retained_unconstrained_sha256"] for chain in raw["chains_data"]
            ],
            "final_step_size": [
                chain["final_step_size"] for chain in raw["chains_data"]
            ],
            "final_metric_sha256": [
                chain["final_metric_sha256"] for chain in raw["chains_data"]
            ],
            "final_tuning_sha256": [
                chain["final_tuning_sha256"] for chain in raw["chains_data"]
            ],
            "retained_diagnostics_sha256": [
                chain["retained_diagnostics_sha256"] for chain in raw["chains_data"]
            ],
            "non_rescue_telemetry_sha256": [
                chain["non_rescue_telemetry_sha256"] for chain in raw["chains_data"]
            ],
            "work": [chain["work"] for chain in raw["chains_data"]],
            "draw_file": draw_path.relative_to(HERE).as_posix(),
            "draw_file_sha256": sha256(draw_path),
        }
    )
    return cell


def identity_signature(cell: dict[str, Any]) -> tuple[Any, ...]:
    return (
        cell.get("unconstrained_sha256"),
        cell.get("constrained_sha256"),
        cell.get("target_calls_total"),
        tuple(cell.get("final_step_size") or []),
        tuple(cell.get("final_metric_sha256") or []),
        tuple(cell.get("final_tuning_sha256") or []),
        tuple(cell.get("retained_diagnostics_sha256") or []),
        tuple(cell.get("non_rescue_telemetry_sha256") or []),
    )


def exact_sign_test(
    candidate: Iterable[float], comparator: Iterable[float], higher_is_better: bool
) -> dict[str, Any]:
    pairs = list(zip(candidate, comparator))
    differences = [a - b if higher_is_better else b - a for a, b in pairs]
    non_ties = [difference for difference in differences if difference != 0]
    wins = sum(difference > 0 for difference in non_ties)
    n = len(non_ties)
    p = (
        sum(math.comb(n, index) for index in range(wins, n + 1)) / (2**n)
        if n
        else 1.0
    )
    return {
        "complete_blocks": len(pairs),
        "non_tied_blocks": n,
        "ties": len(pairs) - n,
        "wins": wins,
        "losses": n - wins,
        "one_sided_exact_p": p,
        "passed": len(pairs) >= 10 and n >= 10 and p <= 0.05,
    }


def geometric_mean(values: Iterable[float]) -> float | None:
    values = list(values)
    if not values or any(not math.isfinite(value) or value <= 0 for value in values):
        return None
    return math.exp(sum(math.log(value) for value in values) / len(values))


def load_processes() -> dict[tuple[str, int, str], dict[str, Any]]:
    records = {}
    for path in sorted(PROCESSES.glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        records[(value["target"], int(value["seed"]), value["arm"])] = value
    return records


def classify_triplets(
    processes: dict[tuple[str, int, str], dict[str, Any]]
) -> tuple[dict[tuple[str, int], bool], dict[tuple[str, int], list[str]]]:
    valid: dict[tuple[str, int], bool] = {}
    reasons: dict[tuple[str, int], list[str]] = {}
    for target in TARGETS:
        for seed in SEEDS:
            failures: list[str] = []
            records = [processes.get((target, seed, arm)) for arm in ARMS]
            for arm, record in zip(ARMS, records):
                if record is None:
                    failures.append(f"{arm}: missing process record")
                elif not record.get("process_valid"):
                    failures.append(f"{arm}: process invalid")
            hashes = []
            for record in records:
                if record and record.get("process_valid"):
                    try:
                        raw = json.loads(
                            (HERE / record["raw_output_path"]).read_text(encoding="utf-8")
                        )
                        hashes.append(tuple(raw.get("initial_position_sha256", [])))
                    except Exception as error:
                        failures.append(f"could not inspect paired initial hashes: {error}")
            if len(hashes) == 3 and not all(value == hashes[0] for value in hashes[1:]):
                failures.append("initial-position hashes differ by arm")
            if len(hashes) == 3 and len(hashes[0]) != 4:
                failures.append("paired cells do not expose four initial-position hashes")
            valid[(target, seed)] = not failures
            reasons[(target, seed)] = failures
    return valid, reasons


def apply_origin_credit_and_identity(
    cells: dict[tuple[str, int, str], dict[str, Any]],
    triplet_valid: dict[tuple[str, int], bool],
) -> None:
    for target in TARGETS:
        for seed in SEEDS:
            if not triplet_valid[(target, seed)]:
                continue
            observe = cells[(target, seed, "observe")]
            origins = (observe.get("stable_separated_origins") or {}).get("chains", [])
            observe_hashes = observe.get("initial_position_sha256", [])
            for arm in ARMS:
                cell = cells[(target, seed, arm)]
                mapped = (
                    cell.get("initial_position_sha256") == observe_hashes
                    and len(observe_hashes) == 4
                )
                overwritten = bool(
                    mapped
                    and any(
                        int(action["chain"]) in origins
                        for action in cell.get("actions", [])
                    )
                )
                cell["mapped_stable_separated_origin_chains"] = origins if mapped else []
                cell["origin_overwritten"] = overwritten
                cell["credited_diagnostic_pass"] = bool(
                    cell.get("raw_diagnostic_pass") and not overwritten
                )
                if arm in {"current", "two_hit"} and cell.get("restart_actions") == 0:
                    cell["zero_action_identity_to_observe"] = (
                        identity_signature(cell) == identity_signature(observe)
                    )
                else:
                    cell["zero_action_identity_to_observe"] = None


def count_passes(
    cells: dict[tuple[str, int, str], dict[str, Any]],
    valid: dict[tuple[str, int], bool],
    target: str,
    arm: str,
) -> int:
    return sum(
        bool(cells[(target, seed, arm)].get("credited_diagnostic_pass"))
        for seed in SEEDS
        if valid[(target, seed)]
    )


def write_results_tables(summary: dict[str, Any]) -> None:
    cells = summary["cells"]
    lines = [
        "# chain_rescue_v2 — complete WP36 results",
        "",
        f"Mechanical decision: **{summary['mechanical_decision']}**.",
        "",
        "## Every planned cell",
        "",
        "| target | seed | arm | process | triplet | sampler | raw gate | credited gate | actions | origin overwritten | max R-hat | min bulk/tail ESS | max |z| | decisive | efficiency | no-fire identity |",
        "|---|---:|---|---|---|---|---|---|---:|---|---:|---|---:|---|---:|---|",
    ]
    for target, seed, arm in planned_cells():
        cell = cells.get(target, {}).get(str(seed), {}).get(arm)
        if not cell:
            lines.append(
                f"| {target} | {seed} | {arm} | missing | false | — | — | — | — | — | — | — | — | — | — | — |"
            )
            continue
        triplet = summary["triplets"][target][str(seed)]["valid"]
        lines.append(
            f"| {target} | {seed} | {arm} | {cell.get('process_valid')} | {triplet} | "
            f"{cell.get('sampler_status')} | {cell.get('raw_diagnostic_pass')} | "
            f"{cell.get('credited_diagnostic_pass')} | {cell.get('restart_actions')} | "
            f"{cell.get('origin_overwritten')} | {cell.get('max_rank_folded_split_rhat', cell.get('omega_rank_folded_split_rhat', '—'))} | "
            f"{cell.get('min_bulk_ess', cell.get('omega_bulk_ess', '—'))} / {cell.get('min_tail_ess', '—')} | "
            f"{cell.get('max_abs_z', (cell.get('tail_mass') or {}).get('z', '—'))} | "
            f"{','.join(cell.get('decisive_reference_disagreements', [])) or 'none'} | "
            f"{cell.get('efficiency', '—')} | {cell.get('zero_action_identity_to_observe', '—')} |"
        )
    lines.extend(
        [
            "",
            "## Decision gates",
            "",
            "| gate | passed | detail |",
            "|---|---|---|",
        ]
    )
    for name, gate in summary["decision_gates"].items():
        lines.append(f"| {name} | {gate['passed']} | `{json.dumps(gate, sort_keys=True)}` |")
    lines.extend(
        [
            "",
            "## Named exact sign tests",
            "",
            "| test | complete | non-tied | wins | losses | ties | one-sided p | pass |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for name, result in summary["sign_tests"].items():
        lines.append(
            f"| {name} | {result['complete_blocks']} | {result['non_tied_blocks']} | "
            f"{result['wins']} | {result['losses']} | {result['ties']} | "
            f"{result['one_sided_exact_p']:.8g} | {result['passed']} |"
        )
    lines.extend(
        [
            "",
            "## Predictions",
            "",
            "| prediction | held | value |",
            "|---|---|---|",
        ]
    )
    for name, prediction in summary["predictions"].items():
        lines.append(
            f"| {name} | {prediction.get('held')} | `{json.dumps(prediction.get('value'), sort_keys=True)}` |"
        )
    atomic_write_text(ARTIFACTS / "results-table.md", "\n".join(lines) + "\n")

    parameter_lines = [
        "# chain_rescue_v2 — complete parameter results",
        "",
        "| target | seed | arm | parameter | mean | MCSE | bulk ESS | tail ESS | rank folded split R-hat | reference mean/SD/MCSE | z | d | decisive |",
        "|---|---:|---|---|---:|---:|---:|---:|---:|---|---:|---:|---|",
    ]
    for target in MODELS:
        for seed in SEEDS:
            for arm in ARMS:
                cell = cells.get(target, {}).get(str(seed), {}).get(arm, {})
                for name, row in cell.get("parameters", {}).items():
                    parameter_lines.append(
                        f"| {target} | {seed} | {arm} | {name} | {row['mean']:.9g} | "
                        f"{row['mcse']:.9g} | {row['bulk_ess']:.7g} | {row['tail_ess']:.7g} | "
                        f"{row['rank_folded_split_rhat']:.7g} | {row['reference_mean']:.9g} / "
                        f"{row['reference_sd']:.9g} / {row['reference_mcse']:.9g} | "
                        f"{row['z']:.7g} | {row['abs_dmean_over_reference_sd']:.7g} | "
                        f"{row['decisive_reference_disagreement']} |"
                    )
    atomic_write_text(
        ARTIFACTS / "parameters-table.md", "\n".join(parameter_lines) + "\n"
    )


def analyze() -> dict[str, Any]:
    processes = load_processes()
    triplet_valid, triplet_reasons = classify_triplets(processes)
    refs: dict[str, dict[str, Any]] = {}
    flat_cells: dict[tuple[str, int, str], dict[str, Any]] = {}
    for target, seed, arm in planned_cells():
        process = processes.get((target, seed, arm))
        if not process or not process.get("process_valid"):
            continue
        raw = json.loads((HERE / process["raw_output_path"]).read_text(encoding="utf-8"))
        if target == "funnel-10d":
            cell = funnel_cell(raw, process)
        else:
            if target not in refs:
                refs[target] = reference(target)
            cell = posteriordb_cell(raw, process, refs[target])
        flat_cells[(target, seed, arm)] = cell
        write_json(cell_path(target, arm, seed), cell)
    apply_origin_credit_and_identity(flat_cells, triplet_valid)
    for (target, seed, arm), cell in flat_cells.items():
        write_json(cell_path(target, arm, seed), cell)

    failure_models = tuple(PROTOCOL["posteriordb"]["failure_class_models"])
    nuisance_models = tuple(PROTOCOL["posteriordb"]["nuisance_action_models"])
    failure_seeds = [
        seed
        for seed in SEEDS
        if all(triplet_valid[(target, seed)] for target in failure_models)
    ]
    nuisance_seeds = [
        seed
        for seed in SEEDS
        if all(triplet_valid[(target, seed)] for target in nuisance_models)
    ]
    failure_scores = {
        arm: [
            sum(
                bool(flat_cells[(target, seed, arm)].get("credited_diagnostic_pass"))
                for target in failure_models
            )
            for seed in failure_seeds
        ]
        for arm in ARMS
    }
    nuisance_scores = {
        arm: [
            sum(
                int(flat_cells[(target, seed, arm)].get("restart_actions", 0))
                for target in nuisance_models
            )
            for seed in nuisance_seeds
        ]
        for arm in ARMS
    }
    efficacy_sign = exact_sign_test(
        failure_scores["two_hit"], failure_scores["observe"], True
    )
    nuisance_sign = exact_sign_test(
        nuisance_scores["two_hit"], nuisance_scores["current"], False
    )

    launch_complete = all(
        (target, seed, arm) in processes for target, seed, arm in planned_cells()
    )
    valid_by_target = {
        target: sum(triplet_valid[(target, seed)] for seed in SEEDS) for target in TARGETS
    }
    completeness = (
        launch_complete
        and all(count >= 10 for count in valid_by_target.values())
        and efficacy_sign["complete_blocks"] >= 10
        and efficacy_sign["non_tied_blocks"] >= 10
        and nuisance_sign["complete_blocks"] >= 10
        and nuisance_sign["non_tied_blocks"] >= 10
    )

    pass_counts = {
        target: {
            arm: count_passes(flat_cells, triplet_valid, target, arm)
            for arm in ARMS
        }
        for target in TARGETS
    }
    safety_models = (
        "kidiq-kidscore_momhsiq",
        "earnings-logearn_interaction",
        "diamonds-diamonds",
        "mesquite-logmesquite_logvash",
    )
    safety_losses = {
        comparator: {
            target: max(
                0,
                pass_counts[target][comparator] - pass_counts[target]["two_hit"],
            )
            for target in safety_models
        }
        for comparator in ("observe", "current")
    }
    two_cells = [
        flat_cells[(target, seed, "two_hit")]
        for target in TARGETS
        for seed in SEEDS
        if triplet_valid[(target, seed)]
    ]
    two_origin = [
        f"{cell['target']}/{cell['seed']}"
        for cell in two_cells
        if cell.get("origin_overwritten")
    ]
    two_decisive = [
        f"{cell['target']}/{cell['seed']}/{name}"
        for cell in two_cells
        for name in cell.get("decisive_reference_disagreements", [])
    ]
    two_legacy = [
        f"{cell['target']}/{cell['seed']}"
        for cell in two_cells
        if cell.get("credited_diagnostic_pass") and cell.get("max_abs_z", 0) > 4.0
    ]
    safety = (
        not two_origin
        and not two_decisive
        and not two_legacy
        and all(loss <= 1 for losses in safety_losses.values() for loss in losses.values())
        and all(sum(losses.values()) <= 2 for losses in safety_losses.values())
    )

    current_failure_losses = {
        target: max(
            0, pass_counts[target]["current"] - pass_counts[target]["two_hit"]
        )
        for target in failure_models
    }
    efficacy = (
        efficacy_sign["passed"]
        and all(loss <= 1 for loss in current_failure_losses.values())
        and sum(current_failure_losses.values()) <= 2
    )
    nuisance_two = sum(nuisance_scores["two_hit"])
    nuisance_current = sum(nuisance_scores["current"])
    nuisance_ratio = (
        nuisance_two / nuisance_current
        if nuisance_current
        else (0.0 if nuisance_two == 0 else math.inf)
    )
    nuisance = nuisance_sign["passed"] and nuisance_ratio <= 0.60

    funnel_seeds = [
        seed for seed in SEEDS if triplet_valid[("funnel-10d", seed)]
    ]
    funnel_two = [
        flat_cells[("funnel-10d", seed, "two_hit")] for seed in funnel_seeds
    ]
    funnel_tail = all(
        cell.get("tail_mass") is not None
        and math.isfinite(cell["tail_mass"]["z"])
        and abs(cell["tail_mass"]["z"]) <= 2.0
        for cell in funnel_two
    )
    funnel_passes = {
        arm: sum(
            bool(flat_cells[("funnel-10d", seed, arm)].get("funnel_full_gate"))
            for seed in funnel_seeds
        )
        for arm in ARMS
    }
    funnel_gate = (
        len(funnel_seeds) >= 10
        and funnel_tail
        and funnel_passes["two_hit"] >= math.ceil(len(funnel_seeds) / 2)
        and all(
            funnel_passes["two_hit"] >= funnel_passes[arm] - 1
            for arm in ("observe", "current")
        )
    )

    conformance = (
        json.loads(CONFORMANCE.read_text(encoding="utf-8"))
        if CONFORMANCE.is_file()
        else {}
    )
    conformance_pass = (
        conformance.get("status") == "pass"
        and conformance.get("comparison", {}).get("bit_identical") is True
    )
    mesquite_zero = sum(
        triplet_valid[("mesquite-logmesquite_logvash", seed)]
        and flat_cells[("mesquite-logmesquite_logvash", seed, "two_hit")].get(
            "restart_actions"
        )
        == 0
        for seed in SEEDS
    )
    no_fire_failures = [
        f"{target}/{seed}/{arm}"
        for target in TARGETS
        for seed in SEEDS
        if triplet_valid[(target, seed)]
        for arm in ("current", "two_hit")
        if flat_cells[(target, seed, arm)].get("restart_actions") == 0
        and flat_cells[(target, seed, arm)].get("zero_action_identity_to_observe") is not True
    ]
    observe_mutations = [
        f"{target}/{seed}"
        for target in TARGETS
        for seed in SEEDS
        if triplet_valid[(target, seed)]
        and flat_cells[(target, seed, "observe")].get("restart_actions", 0) != 0
    ]
    no_fire = (
        conformance_pass
        and mesquite_zero >= 10
        and not no_fire_failures
        and not observe_mutations
    )

    efficiency_ratios: dict[str, list[float]] = {}
    efficiency_bad = []
    for target in MODELS:
        efficiency_ratios[target] = []
        for seed in SEEDS:
            if not triplet_valid[(target, seed)]:
                continue
            two = flat_cells[(target, seed, "two_hit")].get("efficiency")
            current = flat_cells[(target, seed, "current")].get("efficiency")
            if (
                two is None
                or current is None
                or not math.isfinite(two)
                or not math.isfinite(current)
                or two <= 0
                or current <= 0
            ):
                efficiency_bad.append(f"{target}/{seed}")
            else:
                efficiency_ratios[target].append(two / current)
    efficiency_medians = {
        target: statistics.median(values) if values else None
        for target, values in efficiency_ratios.items()
    }
    efficiency_geomean = geometric_mean(
        ratio for values in efficiency_ratios.values() for ratio in values
    )
    efficiency = (
        not efficiency_bad
        and all(
            value is not None and value >= 0.90
            for value in efficiency_medians.values()
        )
        and efficiency_geomean is not None
        and efficiency_geomean >= 0.95
    )

    gates = {
        "completeness": {
            "passed": completeness,
            "all_288_launch_records": launch_complete,
            "valid_triplets_by_target": valid_by_target,
        },
        "safety": {
            "passed": safety,
            "origin_overwritten": two_origin,
            "decisive_reference_disagreements": two_decisive,
            "legacy_reference_gate_violations": two_legacy,
            "credited_pass_losses": safety_losses,
        },
        "efficacy": {
            "passed": efficacy,
            "sign_test": efficacy_sign,
            "losses_to_current": current_failure_losses,
        },
        "nuisance_action_reduction": {
            "passed": nuisance,
            "sign_test": nuisance_sign,
            "two_hit_actions": nuisance_two,
            "current_actions": nuisance_current,
            "ratio": nuisance_ratio,
        },
        "funnel": {
            "passed": funnel_gate,
            "valid_seeds": funnel_seeds,
            "all_two_hit_abs_z_le_2": funnel_tail,
            "full_gate_counts": funnel_passes,
        },
        "no_fire": {
            "passed": no_fire,
            "pre_evidence_conformance": conformance_pass,
            "mesquite_two_hit_zero_action_cells": mesquite_zero,
            "identity_failures": no_fire_failures,
            "observe_mutations": observe_mutations,
        },
        "efficiency": {
            "passed": efficiency,
            "bad_cells": efficiency_bad,
            "per_model_median_ratio": efficiency_medians,
            "geometric_mean_ratio": efficiency_geomean,
        },
    }

    current_cells = [
        flat_cells[(target, seed, "current")]
        for target in TARGETS
        for seed in SEEDS
        if triplet_valid[(target, seed)]
    ]
    current_red_lines = {
        "origin_overwritten": [
            f"{cell['target']}/{cell['seed']}"
            for cell in current_cells
            if cell.get("origin_overwritten")
        ],
        "reference": [
            f"{cell['target']}/{cell['seed']}/{name}"
            for cell in current_cells
            for name in cell.get("decisive_reference_disagreements", [])
        ],
        "funnel": [
            f"funnel-10d/{cell['seed']}"
            for cell in current_cells
            if cell["target"] == "funnel-10d"
            and (
                cell.get("sampler_status") != "ok"
                or not cell.get("finite_draws", False)
                or cell.get("tail_mass") is None
                or abs(cell["tail_mass"]["z"]) > 3.0
            )
        ],
        "no_fire": [
            item for item in no_fire_failures if item.endswith("/current")
        ]
        + observe_mutations,
    }
    all_two_hit_gates = all(gate["passed"] for gate in gates.values())
    any_current_red_line = any(current_red_lines.values())
    decision = (
        "two_hit"
        if all_two_hit_gates
        else "no_rescue"
        if any_current_red_line
        else "current"
    )
    predictions = {
        "P1": {
            "held": nuisance if completeness else None,
            "value": {"ratio": nuisance_ratio, "sign_test": nuisance_sign},
        },
        "P2": {
            "held": efficacy if completeness else None,
            "value": {"sign_test": efficacy_sign, "losses": current_failure_losses},
        },
        "P3": {
            "held": (
                any(
                    flat_cells[("bball_drive_event_0-hmm_drive_0", seed, "observe")]
                    .get("stable_separated_origins", {})
                    .get("chains", [])
                    for seed in SEEDS
                    if triplet_valid[("bball_drive_event_0-hmm_drive_0", seed)]
                )
                and any(
                    item.startswith("bball_drive_event_0-hmm_drive_0/")
                    for item in current_red_lines["origin_overwritten"]
                )
                and any(
                    item.startswith("bball_drive_event_0-hmm_drive_0/")
                    for item in two_origin
                )
                and sum(
                    item.startswith("bball_drive_event_0-hmm_drive_0/")
                    for item in two_origin
                )
                < sum(
                    item.startswith("bball_drive_event_0-hmm_drive_0/")
                    for item in current_red_lines["origin_overwritten"]
                )
            )
            if completeness
            else None,
            "value": {
                "current_origin_overwrites": current_red_lines["origin_overwritten"],
                "two_hit_origin_overwrites": two_origin,
            },
        },
        "P4": {
            "held": not two_decisive and not current_red_lines["reference"]
            if completeness
            else None,
            "value": {
                "two_hit": two_decisive,
                "current": current_red_lines["reference"],
            },
        },
        "P5": {
            "held": funnel_gate if completeness else None,
            "value": gates["funnel"],
        },
        "P6": {
            "held": mesquite_zero >= 10 and not no_fire_failures
            if completeness
            else None,
            "value": mesquite_zero,
        },
        "P7": {
            "held": efficiency_geomean is not None and efficiency_geomean >= 0.95
            if completeness
            else None,
            "value": efficiency_geomean,
        },
        "P8": {
            "held": decision == "no_rescue" if completeness else None,
            "value": decision,
        },
    }
    nested_cells: dict[str, dict[str, dict[str, Any]]] = {}
    for (target, seed, arm), cell in flat_cells.items():
        nested_cells.setdefault(target, {}).setdefault(str(seed), {})[arm] = cell
    triplets = {
        target: {
            str(seed): {
                "valid": triplet_valid[(target, seed)],
                "exclusion_reasons": triplet_reasons[(target, seed)],
            }
            for seed in SEEDS
        }
        for target in TARGETS
    }
    summary = {
        "schema": "chain-rescue-v2-summary",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "protocol_sha256": sha256(PROTOCOL_PATH),
        "amendment_1_sha256": sha256(HERE / "AMENDMENT-1.md"),
        "mechanical_decision": decision,
        "current_red_lines": current_red_lines,
        "decision_gates": gates,
        "sign_tests": {
            "failure_class_two_hit_over_observe": efficacy_sign,
            "nuisance_fewer_two_hit_than_current": nuisance_sign,
        },
        "failure_class_scores": {
            "seeds": failure_seeds,
            "scores": failure_scores,
        },
        "nuisance_action_scores": {
            "seeds": nuisance_seeds,
            "scores": nuisance_scores,
        },
        "pass_counts": pass_counts,
        "efficiency_ratios": efficiency_ratios,
        "predictions": predictions,
        "triplets": triplets,
        "cells": nested_cells,
    }
    write_json(ARTIFACTS / "summary.json", summary)
    write_results_tables(summary)
    print(f"mechanical decision: {decision}")
    return summary


def run_conformance() -> None:
    if CONFORMANCE.exists():
        raise RuntimeError(f"conformance output already exists: {CONFORMANCE}")
    if not CONFORMANCE_BIN.is_file():
        raise RuntimeError(f"conformance binary is missing: {CONFORMANCE_BIN}")
    completed = subprocess.run(
        [str(CONFORMANCE_BIN), str(CONFORMANCE)],
        cwd=HERE,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="")
    if completed.returncode != 0:
        raise RuntimeError(
            f"conformance failed with {return_code_forms(completed.returncode)['hex_32']}"
        )
    result = json.loads(CONFORMANCE.read_text(encoding="utf-8"))
    if result.get("comparison", {}).get("bit_identical") is not True:
        raise RuntimeError("conformance result did not record bit identity")
    print("pre-evidence conformance: PASS (observe is bit-identical to disabled)")


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if command == "verify":
        print(json.dumps(validate_environment(require_binaries=True), indent=2, sort_keys=True))
    elif command == "run":
        run_all()
    elif command == "analyze":
        analyze()
    elif command == "conformance":
        run_conformance()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
