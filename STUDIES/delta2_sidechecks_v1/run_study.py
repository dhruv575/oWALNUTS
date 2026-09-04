#!/usr/bin/env python3
"""Prepare provenance and execute the frozen WP37A one-shot manifest.

Commands:
  run_study.py verify
  run_study.py prepare-provenance
  run_study.py run

Only ``run`` launches evidence. A marker or process record permanently forbids
a second launch of its tuple.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[1]
PREREGISTRATION = HERE / "PREREGISTRATION.md"
PROTOCOL = HERE / "protocol.json"
AMENDMENT = HERE / "AMENDMENT-1.md"
MANIFEST = HERE / "MANIFEST.txt"
PROVENANCE = HERE / "PROVENANCE.json"
CONFORMANCE = HERE / "CONFORMANCE.json"
ARTIFACTS = HERE / "artifacts"
LAUNCHES = ARTIFACTS / "launches"
PROCESSES = ARTIFACTS / "processes"
RAW = ARTIFACTS / "raw"
STDOUT = ARTIFACTS / "stdout"
STDERR = ARTIFACTS / "stderr"
RUN_LOG = ARTIFACTS / "run-log.ndjson"
TOOLCHAIN = "1.88.0-x86_64-pc-windows-gnu"
EXE = ".exe" if os.name == "nt" else ""
BINARY = HERE / "target" / "release" / f"delta2-sidechecks-v1{EXE}"
BASELINE_COMMIT = "443e86a3bb053ed1a2a1560caca5266427a3b35c"
BASELINE_TREE = "b534495caf9fd8de5aa8f76a6d84be60a79e52eb"
PREREG_COMMIT = "150b34ad88fa24d50392ff8c692f5308512f16a6"
AMENDMENT_COMMIT = "a9efca2"
EXPECTED_NORMALIZED = {
    "PREREGISTRATION.md": "4f61248d8207e0b3fc84f9d55e3a093b8fb963e1c6d1ba0e88ee1669a2aecf73",
    "protocol.json": "bf82f4a075c2811666b845cb90e763a94a7eb76c979d956377913be2dc9ce58b",
}
EXPECTED_MANIFEST_SHA256 = (
    "7ed4837570692ce2c7f44939d0e32b276b14eb834d86b4869d3de44149138c86"
)
EXPECTED_ARVIZ = "0.23.4"
TIMEOUTS = {"funnel": 3600, "eight_schools_strict": 900, "gaussian100": 600}
RAW_SCHEMA = "owalnuts-delta2-sidechecks-v1-raw"
RAW_COMPLETE = "WP37A_CELL_COMPLETE_V1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_bytes(path: Path) -> bytes:
    text = path.read_text(encoding="utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")


def atomic_write_new(path: Path, data: bytes) -> None:
    """Create a path atomically without replacing any existing file."""
    if path.exists():
        raise FileExistsError(f"refusing to replace immutable path: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(8)}")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            raise FileExistsError(f"immutable destination appeared: {path}")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def exclusive_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def git(*args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", "-C", str(REPOSITORY), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def parse_manifest() -> list[dict[str, Any]]:
    data = MANIFEST.read_bytes()
    if b"\r" in data or not data.endswith(b"\n"):
        raise RuntimeError("MANIFEST.txt must be UTF-8/LF with a final newline")
    if sha256_bytes(data) != EXPECTED_MANIFEST_SHA256:
        raise RuntimeError(
            f"manifest hash {sha256_bytes(data)} != {EXPECTED_MANIFEST_SHA256}"
        )
    entries: list[dict[str, Any]] = []
    for line in data.decode("utf-8").splitlines():
        ordinal, target, seed, repetition, arm, sentinel = line.split("|")
        entries.append(
            {
                "ordinal": int(ordinal),
                "target": target,
                "seed": int(seed),
                "zero_based_repetition": int(repetition),
                "arm": arm,
                "sentinel": sentinel,
            }
        )
    tuples = {
        (
            row["ordinal"],
            row["target"],
            row["seed"],
            row["zero_based_repetition"],
            row["arm"],
            row["sentinel"],
        )
        for row in entries
    }
    if len(entries) != 84 or len(tuples) != 84:
        raise RuntimeError("manifest does not contain 84 unique tuples")
    if [row["ordinal"] for row in entries] != list(range(1, 85)):
        raise RuntimeError("manifest ordinals are not exactly 1 through 84")
    counts = {
        target: sum(row["target"] == target for row in entries)
        for target in TIMEOUTS
    }
    if counts != {"funnel": 24, "eight_schools_strict": 36, "gaussian100": 24}:
        raise RuntimeError(f"manifest target counts are wrong: {counts}")
    if any(
        row["seed"] not in range(93101, 93113)
        or row["arm"] not in {"fixed1", "fixed2"}
        for row in entries
    ):
        raise RuntimeError("manifest contains an unregistered seed or arm")
    for row in entries:
        if row["target"] == "eight_schools_strict":
            expected = f"REPEAT_{row['zero_based_repetition'] + 1}_OF_3"
            if (
                row["seed"] > 93106
                or row["zero_based_repetition"] not in {0, 1, 2}
                or row["sentinel"] != expected
            ):
                raise RuntimeError(f"invalid repeated tuple: {row}")
        elif row["zero_based_repetition"] != 0 or row["sentinel"] != "SINGLE":
            raise RuntimeError(f"invalid single tuple: {row}")
    return entries


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


def cell_id(row: dict[str, Any]) -> str:
    return (
        f"{row['ordinal']:02d}-{row['target']}-{row['seed']}-"
        f"r{row['zero_based_repetition']}-{row['arm']}"
    )


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(HERE).as_posix()
        if path.is_relative_to(HERE)
        else str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def tool_output(command: list[str], *, cwd: Path = HERE) -> str:
    completed = subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise RuntimeError(
            completed.stderr.strip() or f"{' '.join(command)} returned {completed.returncode}"
        )
    return completed.stdout.strip()


def frozen_file_records() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in (PREREGISTRATION, PROTOCOL, AMENDMENT):
        relative = path.relative_to(REPOSITORY).as_posix()
        current = path.read_bytes()
        registered = subprocess.run(
            ["git", "-C", str(REPOSITORY), "show", f"{AMENDMENT_COMMIT}:{relative}"],
            capture_output=True,
            check=False,
        )
        if registered.returncode != 0 or registered.stdout != current:
            raise RuntimeError(f"{path.name} differs from preregistration/amendment commit")
        record = file_record(path)
        record["utf8_lf_normalized_sha256"] = sha256_bytes(normalized_bytes(path))
        records[path.name] = record
    for name, expected in EXPECTED_NORMALIZED.items():
        if records[name]["utf8_lf_normalized_sha256"] != expected:
            raise RuntimeError(f"{name} normalized hash differs from frozen hash")
    return records


def verify_static(require_provenance: bool = False) -> dict[str, Any]:
    entries = parse_manifest()
    frozen = frozen_file_records()
    if git("rev-parse", f"{BASELINE_COMMIT}^{{tree}}") != BASELINE_TREE:
        raise RuntimeError("source baseline tree does not match the frozen baseline")
    rustc = tool_output(["rustup", "run", TOOLCHAIN, "rustc", "-Vv"])
    if "release: 1.88.0" not in rustc or "host: x86_64-pc-windows-gnu" not in rustc:
        raise RuntimeError(f"wrong Rust toolchain:\n{rustc}")
    result: dict[str, Any] = {
        "manifest_entries": len(entries),
        "manifest_sha256": sha256(MANIFEST),
        "frozen_files": frozen,
        "rustc_vv": rustc,
    }
    if require_provenance:
        provenance = load_and_verify_provenance()
        result["provenance_sha256"] = sha256(PROVENANCE)
        result["harness_source"] = provenance["harness_source"]
        try:
            import arviz as az
        except ImportError as error:
            raise RuntimeError("ArviZ is unavailable in the runner environment") from error
        if az.__version__ != EXPECTED_ARVIZ:
            raise RuntimeError(f"ArviZ {az.__version__} != {EXPECTED_ARVIZ}")
        result["arviz"] = az.__version__
    return result


def source_records() -> list[dict[str, Any]]:
    paths = git(
        "ls-files",
        "Cargo.toml",
        "Cargo.lock",
        "src/*.rs",
        "src/**/*.rs",
        "STUDIES/delta2_sidechecks_v1/Cargo.toml",
        "STUDIES/delta2_sidechecks_v1/Cargo.lock",
        "STUDIES/delta2_sidechecks_v1/.gitattributes",
        "STUDIES/delta2_sidechecks_v1/.gitignore",
        "STUDIES/delta2_sidechecks_v1/build.rs",
        "STUDIES/delta2_sidechecks_v1/src/*.rs",
        "STUDIES/delta2_sidechecks_v1/run_study.py",
        "STUDIES/delta2_sidechecks_v1/analyze.py",
        "STUDIES/delta2_sidechecks_v1/test_study.py",
        "STUDIES/delta2_sidechecks_v1/checksums.py",
        "STUDIES/delta2_sidechecks_v1/MANIFEST.txt",
        "STUDIES/delta2_sidechecks_v1/PREREGISTRATION.md",
        "STUDIES/delta2_sidechecks_v1/protocol.json",
        "STUDIES/delta2_sidechecks_v1/AMENDMENT-1.md",
    ).splitlines()
    return [
        {
            "path": path.replace("\\", "/"),
            "bytes": (REPOSITORY / path).stat().st_size,
            "sha256": sha256(REPOSITORY / path),
            "git_blob_sha1": git("rev-parse", f"HEAD:{path}"),
        }
        for path in sorted(set(paths))
    ]


def build_release(source_commit: str, source_tree: str) -> None:
    environment = os.environ.copy()
    environment["WP37A_HARNESS_COMMIT"] = source_commit
    environment["WP37A_HARNESS_TREE"] = source_tree
    completed = subprocess.run(
        [
            "cargo",
            f"+{TOOLCHAIN}",
            "build",
            "--release",
            "--locked",
            "--manifest-path",
            str(HERE / "Cargo.toml"),
        ],
        cwd=REPOSITORY,
        env=environment,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"release build failed with {completed.returncode}")


def prepare_provenance() -> None:
    if PROVENANCE.exists() or CONFORMANCE.exists():
        raise RuntimeError("provenance/conformance is immutable and already exists")
    if any(path.exists() for path in (LAUNCHES, PROCESSES, RAW)):
        raise RuntimeError("evidence paths already exist")
    if git("status", "--porcelain=v1", "--untracked-files=all"):
        raise RuntimeError("worktree must be clean before the bound release build")
    verification = verify_static()
    source_commit = git("rev-parse", "HEAD")
    source_tree = git("rev-parse", "HEAD^{tree}")
    build_release(source_commit, source_tree)
    configs = json.loads(tool_output([str(BINARY), "configs"]))
    if (
        configs["harness_source_commit"] != source_commit
        or configs["harness_source_tree"] != source_tree
    ):
        raise RuntimeError("release binary is not bound to the source commit/tree")
    if configs["binary"] != {
        "bytes": BINARY.stat().st_size,
        "sha256": sha256(BINARY),
    }:
        raise RuntimeError("release binary self-record is inconsistent")
    subprocess.run(
        [str(BINARY), "fingerprint", str(CONFORMANCE)],
        cwd=HERE,
        check=True,
    )
    conformance = json.loads(CONFORMANCE.read_text(encoding="utf-8"))
    if (
        conformance["schema"] != "owalnuts-delta2-sidechecks-v1-fingerprint"
        or conformance["evidence"] is not False
        or conformance["configs"] != configs["effective_configs"]
    ):
        raise RuntimeError("non-evidence fingerprint conformance failed")
    cargo_lock = HERE / "Cargo.lock"
    if not cargo_lock.is_file():
        raise RuntimeError("study Cargo.lock is missing")
    entries = parse_manifest()
    provenance = {
        "schema": "owalnuts-delta2-sidechecks-v1-provenance",
        "schema_version": 1,
        "created_utc": utc_now(),
        "baseline": {"commit": BASELINE_COMMIT, "tree": BASELINE_TREE},
        "preregistration_commits": {
            "preregistration": PREREG_COMMIT,
            "amendment": git("rev-parse", AMENDMENT_COMMIT),
        },
        "normalized_source_files": verification["frozen_files"],
        "harness_source": {
            "commit": source_commit,
            "tree": source_tree,
            "records": source_records(),
        },
        "binary": file_record(BINARY),
        "binary_build": {
            "command": (
                f"cargo +{TOOLCHAIN} build --release --locked "
                f"--manifest-path {HERE / 'Cargo.toml'}"
            ),
            "embedded_commit": source_commit,
            "embedded_tree": source_tree,
            "target": "x86_64-pc-windows-gnu",
        },
        "cargo_lock": file_record(cargo_lock),
        "rustc_vv": verification["rustc_vv"],
        "cargo_version": tool_output(["rustup", "run", TOOLCHAIN, "cargo", "-V"]),
        "os_cpu": {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "processor_identifier": os.environ.get("PROCESSOR_IDENTIFIER"),
            "logical_cpu_count": os.cpu_count(),
        },
        "python": {
            "executable": sys.executable,
            "version": sys.version,
        },
        "algorithm_revision": configs["algorithm_revision"],
        "effective_configs": configs["effective_configs"],
        "effective_configs_document_sha256": sha256_bytes(canonical_json(configs)),
        "manifest": {
            "path": "MANIFEST.txt",
            "bytes": MANIFEST.stat().st_size,
            "sha256": sha256(MANIFEST),
            "entries": entries,
            "count": len(entries),
            "target_counts": {
                target: sum(row["target"] == target for row in entries)
                for target in TIMEOUTS
            },
        },
        "conformance": file_record(CONFORMANCE),
        "evidence_state": "NO_EVIDENCE_LAUNCHED",
    }
    atomic_write_new(
        PROVENANCE,
        (json.dumps(provenance, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    print(
        f"prepared immutable provenance for {source_commit[:12]}: "
        f"binary {provenance['binary']['sha256']}"
    )


def load_and_verify_provenance() -> dict[str, Any]:
    if not PROVENANCE.is_file():
        raise RuntimeError("PROVENANCE.json is missing")
    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    if provenance.get("schema") != "owalnuts-delta2-sidechecks-v1-provenance":
        raise RuntimeError("wrong provenance schema")
    if provenance["baseline"] != {"commit": BASELINE_COMMIT, "tree": BASELINE_TREE}:
        raise RuntimeError("provenance baseline mismatch")
    if provenance["manifest"]["sha256"] != sha256(MANIFEST):
        raise RuntimeError("provenance manifest hash mismatch")
    if provenance["manifest"]["entries"] != parse_manifest():
        raise RuntimeError("provenance manifest entries mismatch")
    for name, record in provenance["normalized_source_files"].items():
        path = HERE / name
        if (
            record["bytes"] != path.stat().st_size
            or record["sha256"] != sha256(path)
            or record["utf8_lf_normalized_sha256"]
            != sha256_bytes(normalized_bytes(path))
        ):
            raise RuntimeError(f"provenance frozen-file mismatch: {name}")
    if (
        provenance["binary"]["bytes"] != BINARY.stat().st_size
        or provenance["binary"]["sha256"] != sha256(BINARY)
    ):
        raise RuntimeError("release binary does not match provenance")
    lock = HERE / provenance["cargo_lock"]["path"]
    if (
        provenance["cargo_lock"]["bytes"] != lock.stat().st_size
        or provenance["cargo_lock"]["sha256"] != sha256(lock)
    ):
        raise RuntimeError("Cargo.lock does not match provenance")
    if provenance["conformance"] != file_record(CONFORMANCE):
        raise RuntimeError("conformance record does not match provenance")
    if git("status", "--porcelain=v1", "--untracked-files=all"):
        raise RuntimeError("worktree must be clean before evidence")
    if git("ls-files", "--error-unmatch", str(PROVENANCE.relative_to(REPOSITORY))) == "":
        raise RuntimeError("PROVENANCE.json is not committed")
    return provenance


def repetition_mask(row: dict[str, Any]) -> tuple[str, str]:
    if row["target"] != "eight_schools_strict":
        return "0", "0"
    mask = 0
    if LAUNCHES.exists():
        for path in LAUNCHES.glob("*.json"):
            try:
                marker = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            tuple_ = marker.get("manifest", {})
            if (
                tuple_.get("target") == row["target"]
                and tuple_.get("seed") == row["seed"]
                and tuple_.get("arm") == row["arm"]
            ):
                repetition = tuple_.get("zero_based_repetition")
                if repetition in {0, 1, 2}:
                    mask |= 1 << repetition
    before = f"{mask:03b}"
    bit = 1 << row["zero_based_repetition"]
    if mask & bit:
        raise RuntimeError(f"repetition bit already set for {cell_id(row)}")
    return before, f"{mask | bit:03b}"


def append_log(value: dict[str, Any]) -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def interrupted_process(row: dict[str, Any], marker: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "owalnuts-delta2-sidechecks-v1-process",
        "schema_version": 1,
        "manifest": row,
        "nonce": marker.get("nonce"),
        "status": "orchestrator_interrupted_before_process_record",
        "process_valid": False,
        "failure_reasons": [
            "authenticated launch marker existed without a durable process record; rerun forbidden"
        ],
        "process_created": None,
        "timed_out": None,
        "return_code": return_code_forms(None),
        "command": marker.get("command"),
        "timestamps": {
            "marker_created_utc": marker.get("created_utc"),
            "record_created_utc": utc_now(),
        },
    }


def launch_cell(row: dict[str, Any]) -> dict[str, Any]:
    identifier = cell_id(row)
    marker_path = LAUNCHES / f"{identifier}.json"
    process_path = PROCESSES / f"{identifier}.json"
    raw_path = RAW / f"{identifier}.json"
    stdout_path = STDOUT / f"{identifier}.bin"
    stderr_path = STDERR / f"{identifier}.bin"
    if process_path.exists():
        return json.loads(process_path.read_text(encoding="utf-8"))
    if marker_path.exists():
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        process = interrupted_process(row, marker)
        exclusive_write_json(process_path, process)
        return process
    for path in (raw_path, stdout_path, stderr_path):
        if path.exists():
            raise RuntimeError(f"unregistered preexisting output forbids launch: {path}")
    before_mask, after_mask = repetition_mask(row)
    nonce = secrets.token_hex(32)
    command = [
        str(BINARY.resolve()),
        "cell",
        str(row["ordinal"]),
        row["target"],
        str(row["seed"]),
        str(row["zero_based_repetition"]),
        row["arm"],
        row["sentinel"],
        str(PROVENANCE.resolve()),
        str(raw_path.resolve()),
    ]
    marker = {
        "schema": "owalnuts-delta2-sidechecks-v1-launch",
        "schema_version": 1,
        "manifest": row,
        "nonce": nonce,
        "created_utc": utc_now(),
        "command": command,
        "timeout_seconds": TIMEOUTS[row["target"]],
        "repetition_mask_before": before_mask,
        "repetition_mask_after": after_mask,
        "provenance_record_sha256": sha256(PROVENANCE),
        "binary_sha256": sha256(BINARY),
    }
    exclusive_write_json(marker_path, marker)
    created_utc: str | None = None
    exited_utc: str | None = None
    return_code: int | None = None
    timed_out = False
    process_created = False
    launch_error: str | None = None
    stdout = b""
    stderr = b""
    begin = time.perf_counter()
    try:
        process = subprocess.Popen(
            command,
            cwd=HERE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        process_created = True
        created_utc = utc_now()
        try:
            stdout, stderr = process.communicate(timeout=TIMEOUTS[row["target"]])
        except subprocess.TimeoutExpired as error:
            timed_out = True
            process.kill()
            late_stdout, late_stderr = process.communicate()
            stdout = (error.output or b"") + (late_stdout or b"")
            stderr = (error.stderr or b"") + (late_stderr or b"")
        return_code = process.returncode
        exited_utc = utc_now()
    except Exception as error:  # launch/setup failures are durable outcomes
        launch_error = f"{type(error).__name__}: {error}"
    duration = time.perf_counter() - begin
    atomic_write_new(stdout_path, stdout)
    atomic_write_new(stderr_path, stderr)
    raw_exists = raw_path.is_file()
    raw_bytes = raw_path.stat().st_size if raw_exists else None
    raw_sha = sha256(raw_path) if raw_exists else None
    raw_parse_error: str | None = None
    raw_value: dict[str, Any] | None = None
    if raw_exists:
        try:
            parsed = json.loads(raw_path.read_text(encoding="utf-8"))
            raw_value = parsed if isinstance(parsed, dict) else None
            if raw_value is None:
                raw_parse_error = "raw JSON is not an object"
        except Exception as error:  # malformed raw is a process result
            raw_parse_error = f"{type(error).__name__}: {error}"
    raw_mtime_ns = raw_path.stat().st_mtime_ns if raw_exists else None
    reasons: list[str] = []
    if not process_created:
        reasons.append("child process was not created")
    if launch_error:
        reasons.append(launch_error)
    if timed_out:
        reasons.append("child crossed its target-specific timeout")
    if return_code != 0:
        reasons.append(f"child exit status {return_code!r} is not zero")
    if not raw_exists:
        reasons.append("raw result is missing")
    if raw_parse_error:
        reasons.append(f"raw result malformed: {raw_parse_error}")
    if raw_value is not None:
        if raw_value.get("schema") != RAW_SCHEMA:
            reasons.append("raw result schema mismatch")
        if raw_value.get("completion_sentinel") != RAW_COMPLETE:
            reasons.append("raw result completion sentinel mismatch")
        if raw_value.get("manifest") != row:
            reasons.append("raw result manifest tuple mismatch")
    process_record = {
        "schema": "owalnuts-delta2-sidechecks-v1-process",
        "schema_version": 1,
        "manifest": row,
        "nonce": nonce,
        "launch_marker": marker_path.relative_to(HERE).as_posix(),
        "command": command,
        "working_directory": str(HERE.resolve()),
        "timeout_seconds": TIMEOUTS[row["target"]],
        "process_created": process_created,
        "timed_out": timed_out,
        "return_code": return_code_forms(return_code),
        "duration_seconds": duration,
        "timestamps": {
            "marker_created_utc": marker["created_utc"],
            "process_created_utc": created_utc,
            "process_exit_observed_utc": exited_utc,
            "record_created_utc": utc_now(),
        },
        "stdout": {
            "path": stdout_path.relative_to(HERE).as_posix(),
            "bytes": len(stdout),
            "sha256": sha256_bytes(stdout),
            "closed": process_created,
        },
        "stderr": {
            "path": stderr_path.relative_to(HERE).as_posix(),
            "bytes": len(stderr),
            "sha256": sha256_bytes(stderr),
            "closed": process_created,
        },
        "raw_result": {
            "path": raw_path.relative_to(HERE).as_posix(),
            "state": (
                "missing"
                if not raw_exists
                else "present_after_timeout"
                if timed_out
                else "atomically_published_before_exit"
            ),
            "exists": raw_exists,
            "bytes": raw_bytes,
            "sha256": raw_sha,
            "mtime_ns": raw_mtime_ns,
            "parse_error": raw_parse_error,
            "schema": raw_value.get("schema") if raw_value else None,
            "completion_sentinel": (
                raw_value.get("completion_sentinel") if raw_value else None
            ),
            "variant": raw_value.get("variant") if raw_value else None,
        },
        "status": "process_valid" if not reasons else "process_invalid",
        "process_valid": not reasons,
        "failure_reasons": reasons,
    }
    exclusive_write_json(process_path, process_record)
    return process_record


def verify_final_repetition_masks(entries: list[dict[str, Any]]) -> dict[str, str]:
    masks: dict[str, int] = {}
    for row in entries:
        if row["target"] != "eight_schools_strict":
            continue
        key = f"{row['seed']}/{row['arm']}"
        marker = LAUNCHES / f"{cell_id(row)}.json"
        if marker.is_file():
            masks[key] = masks.get(key, 0) | (1 << row["zero_based_repetition"])
    return {key: f"{value:03b}" for key, value in sorted(masks.items())}


def run_all() -> None:
    verification = verify_static(require_provenance=True)
    provenance = load_and_verify_provenance()
    if provenance["evidence_state"] != "NO_EVIDENCE_LAUNCHED":
        raise RuntimeError("provenance does not declare the required pre-evidence state")
    entries = parse_manifest()
    append_log(
        {
            "event": "run_start_or_resume",
            "utc": utc_now(),
            "planned": len(entries),
            "provenance_sha256": verification["provenance_sha256"],
        }
    )
    for index, row in enumerate(entries, start=1):
        record = launch_cell(row)
        append_log(
            {
                "event": "cell_observed",
                "utc": utc_now(),
                "ordinal": row["ordinal"],
                "cell_id": cell_id(row),
                "status": record["status"],
                "process_valid": record["process_valid"],
                "timed_out": record["timed_out"],
                "return_code": record["return_code"],
            }
        )
        duration = record.get("duration_seconds")
        print(
            f"[{index:02d}/84] {cell_id(row)}: {record['status']}"
            + (f" {duration:.3f}s" if isinstance(duration, (int, float)) else ""),
            flush=True,
        )
    masks = verify_final_repetition_masks(entries)
    append_log(
        {
            "event": "run_complete",
            "utc": utc_now(),
            "process_records": sum(path.is_file() for path in PROCESSES.glob("*.json")),
            "final_repetition_masks": masks,
        }
    )
    if set(masks.values()) != {"111"} or len(masks) != 12:
        raise RuntimeError(f"strict-track final repetition masks are incomplete: {masks}")


def main() -> None:
    command = sys.argv[1:] or ["verify"]
    if command == ["verify"]:
        print(json.dumps(verify_static(require_provenance=PROVENANCE.exists()), indent=2))
    elif command == ["prepare-provenance"]:
        prepare_provenance()
    elif command == ["run"]:
        run_all()
    else:
        raise SystemExit("usage: run_study.py verify|prepare-provenance|run")


if __name__ == "__main__":
    main()
