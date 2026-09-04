#!/usr/bin/env python3
"""Execute and analyze the frozen WP36 chain-rescue-v2 protocol.

Commands:
  run_rescue.py verify
  run_rescue.py verify-rebuild
  run_rescue.py run
  run_rescue.py analyze
  run_rescue.py prepare-provenance  # curator-only, create-new
  run_rescue.py rebind-amendment-3-provenance  # curator-only, create-new
  run_rescue.py rebind-post-run-provenance  # curator-only, create-new
  run_rescue.py conformance         # curator-only, create-new

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
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np

HERE = Path(__file__).resolve().parent
PROTOCOL_PATH = HERE / "protocol.json"
PROTOCOL = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
AMENDMENT_1 = HERE / "AMENDMENT-1.md"
AMENDMENT_2 = HERE / "AMENDMENT-2.md"
AMENDMENT_3 = HERE / "AMENDMENT-3.md"
POST_RUN_CORRECTION = HERE / "POST-RUN-CORRECTION.md"
LEDGER_ENTRY = HERE / "LEDGER-ENTRY.md"
ARTIFACTS = HERE / "artifacts"
RAW = ARTIFACTS / "raw"
PROCESSES = ARTIFACTS / "processes"
LAUNCHES = ARTIFACTS / "launches"
HEARTBEATS = ARTIFACTS / "heartbeats"
STDOUT = ARTIFACTS / "stdout"
STDERR = ARTIFACTS / "stderr"
CELLS = ARTIFACTS / "cells"
DRAWS = ARTIFACTS / "draws"
LEGACY_CONFORMANCE = ARTIFACTS / "conformance" / "observe-vs-disabled.json"
CONFORMANCE_INDEX = ARTIFACTS / "conformance" / "current.json"
LEGACY_INPUT_MANIFEST = ARTIFACTS / "provenance" / "external-inputs.json"
LEGACY_BUILD_MANIFEST = ARTIFACTS / "provenance" / "build-manifest.json"
PROVENANCE_INDEX = ARTIFACTS / "provenance" / "current.json"
AMENDMENT_3_PROVENANCE_INDEX = (
    ARTIFACTS / "provenance" / "current-amendment-3.json"
)
POST_RUN_PROVENANCE_INDEX = ARTIFACTS / "provenance" / "current-post-run.json"

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
INSTALLED_DOMAIN = b"chain_rescue_v2.installed_position.v1"
RETAINED_DOMAIN = b"chain_rescue_v2.retained_unconstrained.v1"
ARRAY_DOMAIN = b"chain_rescue_v2.numpy_array.v1"
BOUNDARY_FIELDS = set(PROTOCOL["telemetry"]["required_per_boundary_per_chain"])
RESTART_FIELDS = set(PROTOCOL["telemetry"]["required_on_restart"])
RESTART_FIELDS.add("installed_unconstrained_position")
OUTCOMES = set(PROTOCOL["telemetry"]["outcomes"])
EXPECTED_PYTHON = "3.11.16"
EXPECTED_ARVIZ = "0.23.4"
EXPECTED_NUMPY = "2.4.6"
EXPECTED_BRIDGESTAN = "2.9.0"
EXPECTED_POSTERIORDB = "0.2.0"
EXPECTED_SCIPY = "1.17.1"
EXPECTED_PANDAS = "3.0.5"
EXPECTED_XARRAY = "2026.7.0"
EXPECTED_XARRAY_EINSTATS = "0.9.1"
EXPECTED_TOOLCHAIN = "1.88.0-x86_64-pc-windows-gnu"
WORK_FIELDS = {
    "transitions",
    "momentum_refreshes",
    "standard_normal_components",
    "target_calls_initial",
    "target_calls_forward",
    "target_calls_reverse",
    "target_calls_total",
    "forward_refinement_attempts",
    "forward_micro_steps_executed",
    "reverse_coarsening_attempts",
    "reverse_micro_steps_executed",
    "leaves_attempted",
    "leaves_built",
    "direction_draws",
    "uniform_draws",
    "maximum_depth_stops",
    "recoverable_target_failures",
    "zero_density_evaluations",
    "divergences",
    "invalid_evaluation_stops",
    "refinement_exhaustion_stops",
    "reverse_coarser_stops",
    "reverse_coarser_rejections",
    "accepted_forward_micro_steps",
    "refinement_level_built",
}
DIAGNOSTIC_FIELDS = {
    "divergences",
    "maximum_depth_stops",
    "invalid_evaluation_stops",
    "recoverable_target_failures",
    "zero_density_evaluations",
    "refinement_exhaustion_stops",
    "reverse_coarser_stops",
    "reverse_coarser_rejections",
    "target_calls_total",
}
FUNNEL_FULL_GATE_FIELDS = (
    "omega_rank_folded_split_rhat",
    "omega_bulk_ess",
    "zero_retained_divergences",
    "finite_draws",
    "no_sampler_error",
)


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


def exclusive_write_json(path: Path, value: Any) -> None:
    """Create an immutable JSON marker; never replace an existing path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def authenticated_pointer_path(index: Path, field: str, legacy: Path) -> Path:
    if not index.is_file():
        return legacy
    pointer = json.loads(index.read_text(encoding="utf-8"))
    record = pointer.get(field)
    if not isinstance(record, dict):
        raise RuntimeError(f"{index} lacks pointer field {field}")
    path = HERE / record.get("path", "")
    try:
        path.resolve().relative_to(ARTIFACTS.resolve())
    except ValueError as error:
        raise RuntimeError(f"{index} points outside artifacts") from error
    if not file_matches_record(path, record):
        raise RuntimeError(f"{index} does not authenticate {field}")
    return path


def provenance_paths() -> tuple[Path, Path]:
    index = (
        POST_RUN_PROVENANCE_INDEX
        if POST_RUN_PROVENANCE_INDEX.is_file()
        else (
            AMENDMENT_3_PROVENANCE_INDEX
            if AMENDMENT_3_PROVENANCE_INDEX.is_file()
            else PROVENANCE_INDEX
        )
    )
    return (
        authenticated_pointer_path(
            index, "external_inputs", LEGACY_INPUT_MANIFEST
        ),
        authenticated_pointer_path(
            index, "build_manifest", LEGACY_BUILD_MANIFEST
        ),
    )


def current_conformance_path() -> Path:
    return authenticated_pointer_path(
        CONFORMANCE_INDEX, "conformance", LEGACY_CONFORMANCE
    )


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


def installed_position_sha256(position: Iterable[float]) -> str:
    values = list(position)
    digest = hashlib.sha256()
    digest.update(INSTALLED_DOMAIN)
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


def names_sha256(names: Iterable[str]) -> str:
    names = list(names)
    digest = hashlib.sha256()
    digest.update(b"chain_rescue_v2.names.v1")
    digest.update(struct.pack("<Q", len(names)))
    for name in names:
        encoded = name.encode("utf-8")
        digest.update(struct.pack("<Q", len(encoded)))
        digest.update(encoded)
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


def git_output(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def package_versions() -> dict[str, str]:
    import arviz
    import bridgestan
    import pandas
    import posteriordb
    import scipy
    import xarray
    import xarray_einstats

    return {
        "python": sys.version.split()[0],
        "arviz": arviz.__version__,
        "numpy": np.__version__,
        "bridgestan": bridgestan.__version__,
        "posteriordb": posteriordb.__version__,
        "scipy": scipy.__version__,
        "pandas": pandas.__version__,
        "xarray": xarray.__version__,
        "xarray_einstats": xarray_einstats.__version__,
    }


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def file_matches_record(path: Path, record: dict[str, Any]) -> bool:
    return (
        path.is_file()
        and path.stat().st_size == record.get("bytes")
        and sha256(path) == record.get("sha256")
    )


def pe_sections(path: Path) -> dict[str, dict[str, Any]]:
    data = path.read_bytes()
    if data[:2] != b"MZ":
        raise ValueError(f"{path} is not a PE executable")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise ValueError(f"{path} has no PE signature")
    section_count = struct.unpack_from("<H", data, pe_offset + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe_offset + 20)[0]
    table = pe_offset + 24 + optional_size
    result = {}
    for index in range(section_count):
        offset = table + index * 40
        name = data[offset : offset + 8].rstrip(b"\0").decode("ascii", errors="replace")
        raw_size = struct.unpack_from("<I", data, offset + 16)[0]
        raw_offset = struct.unpack_from("<I", data, offset + 20)[0]
        raw = data[raw_offset : raw_offset + raw_size]
        result[name] = {
            "bytes": raw_size,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    return result


def pe_section_differences(
    expected: dict[str, dict[str, Any]], actual: dict[str, dict[str, Any]]
) -> list[str]:
    return sorted(
        name
        for name in set(expected) | set(actual)
        if expected.get(name) != actual.get(name)
    )


def source_file_records(repository: Path) -> list[dict[str, Any]]:
    paths = git_output(
        repository,
        "ls-files",
        "Cargo.toml",
        "Cargo.lock",
        "src/*.rs",
        "src/**/*.rs",
        "integrations/bridgestan/Cargo.toml",
        "integrations/bridgestan/src/*.rs",
        "STUDIES/chain_rescue_v2/Cargo.toml",
        "STUDIES/chain_rescue_v2/Cargo.lock",
        "STUDIES/chain_rescue_v2/src/*.rs",
        "STUDIES/chain_rescue_v2/src/**/*.rs",
        "STUDIES/chain_rescue_v2/run_rescue.py",
        "STUDIES/chain_rescue_v2/checksums.py",
        "STUDIES/chain_rescue_v2/test_run_rescue.py",
        "STUDIES/chain_rescue_v2/protocol.json",
        "STUDIES/chain_rescue_v2/PREREGISTRATION.md",
        "STUDIES/chain_rescue_v2/AMENDMENT-1.md",
        "STUDIES/chain_rescue_v2/AMENDMENT-2.md",
        "STUDIES/chain_rescue_v2/AMENDMENT-3.md",
        "STUDIES/chain_rescue_v2/POST-RUN-CORRECTION.md",
        "STUDIES/chain_rescue_v2/LEDGER-ENTRY.md",
        "STUDIES/chain_rescue_v2/README.md",
    ).splitlines()
    return [
        {
            "path": path.replace("\\", "/"),
            "bytes": (repository / path).stat().st_size,
            "sha256": sha256(repository / path),
            "git_blob_sha1": git_output(repository, "rev-parse", f"HEAD:{path}"),
        }
        for path in sorted(set(paths))
    ]


def inspect_external_inputs() -> dict[str, Any]:
    errors = []
    files = {}
    for target in MODELS:
        model, data = model_paths(target)
        files[target] = {}
        for kind, path in (("model", model), ("data", data)):
            if not path.is_file():
                errors.append(f"{kind} missing for {target}: {path}")
            else:
                files[target][kind] = file_record(path)
    if not PDB_PATH.exists():
        errors.append(f"posteriordb checkout missing: {PDB_PATH}")
        pdb = {}
    else:
        pdb = {
            "path": str(PDB_PATH.resolve()),
            "head": git_output(PDB_PATH, "rev-parse", "HEAD"),
            "tree": git_output(PDB_PATH, "rev-parse", "HEAD^{tree}"),
            "status_porcelain": git_output(PDB_PATH, "status", "--porcelain=v1"),
        }
        if pdb["head"] != PROTOCOL["posteriordb"]["commit"]:
            errors.append(
                f"posteriordb HEAD {pdb['head']} != {PROTOCOL['posteriordb']['commit']}"
            )
        if pdb["status_porcelain"]:
            errors.append("posteriordb checkout is not clean")
    versions = package_versions()
    expected_versions = {
        "python": EXPECTED_PYTHON,
        "arviz": EXPECTED_ARVIZ,
        "numpy": EXPECTED_NUMPY,
        "bridgestan": EXPECTED_BRIDGESTAN,
        "posteriordb": EXPECTED_POSTERIORDB,
        "scipy": EXPECTED_SCIPY,
        "pandas": EXPECTED_PANDAS,
        "xarray": EXPECTED_XARRAY,
        "xarray_einstats": EXPECTED_XARRAY_EINSTATS,
    }
    for name, expected in expected_versions.items():
        if versions[name] != expected:
            errors.append(f"{name} {versions[name]} != audited {expected}")
    result = {
        "schema": "chain-rescue-v2-external-inputs",
        "protocol_sha256": sha256(PROTOCOL_PATH),
        "amendment_1_sha256": sha256(AMENDMENT_1),
        "amendment_2_sha256": sha256(AMENDMENT_2),
        "amendment_3_sha256": sha256(AMENDMENT_3),
        "post_run_correction_sha256": sha256(POST_RUN_CORRECTION),
        "ledger_entry_sha256": sha256(LEDGER_ENTRY),
        "assets": str(ASSETS.resolve()),
        "model_dir": str(MODEL_DIR.resolve()),
        "posteriordb": pdb,
        "versions": versions,
        "expected_versions": expected_versions,
        "files": files,
        "verified": not errors,
        "errors": errors,
    }
    if errors:
        raise RuntimeError("; ".join(errors))
    return result


def logical_external_identity(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol_sha256": manifest.get("protocol_sha256"),
        "amendment_1_sha256": manifest.get("amendment_1_sha256"),
        "amendment_2_sha256": manifest.get("amendment_2_sha256"),
        "amendment_3_sha256": manifest.get("amendment_3_sha256"),
        "post_run_correction_sha256": manifest.get("post_run_correction_sha256"),
        "ledger_entry_sha256": manifest.get("ledger_entry_sha256"),
        "posteriordb": {
            key: manifest.get("posteriordb", {}).get(key)
            for key in ("head", "tree", "status_porcelain")
        },
        "versions": manifest.get("versions"),
        "files": {
            target: {
                kind: {
                    "bytes": record.get("bytes"),
                    "sha256": record.get("sha256"),
                }
                for kind, record in inputs.items()
            }
            for target, inputs in manifest.get("files", {}).items()
        },
    }


def prepare_provenance() -> None:
    if PROVENANCE_INDEX.exists():
        raise RuntimeError(
            "committed provenance is immutable; create a new study/version to regenerate it"
        )
    repository = Path(git_output(HERE, "rev-parse", "--show-toplevel"))
    if git_output(repository, "status", "--porcelain=v1"):
        raise RuntimeError("source worktree must be clean before audited build")
    source_commit = git_output(repository, "rev-parse", "HEAD")
    source_tree = git_output(repository, "rev-parse", "HEAD^{tree}")
    suffix = source_commit[:12]
    input_manifest = ARTIFACTS / "provenance" / f"external-inputs-{suffix}.json"
    build_manifest = ARTIFACTS / "provenance" / f"build-manifest-{suffix}.json"
    if input_manifest.exists() or build_manifest.exists():
        raise RuntimeError("versioned provenance path already exists; refusing replacement")
    external = inspect_external_inputs()
    external["implementation_source_commit"] = source_commit
    external["implementation_source_tree"] = source_tree
    exclusive_write_json(input_manifest, external)
    manifest_path = HERE / "Cargo.toml"
    build_command = [
        "cargo",
        f"+{EXPECTED_TOOLCHAIN}",
        "build",
        "--release",
        "--locked",
        "--manifest-path",
        str(manifest_path),
    ]
    subprocess.run(build_command, cwd=repository, check=True)
    primary = {
        "cell": HARNESS,
        "funnel": FUNNEL,
        "conformance": CONFORMANCE_BIN,
    }
    (HERE / "target").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="wp36-audited-rebuild-", dir=HERE / "target"
    ) as temporary:
        rebuild_command = build_command + ["--target-dir", temporary]
        subprocess.run(rebuild_command, cwd=repository, check=True)
        rebuilt = {
            name: Path(temporary) / "release" / path.name for name, path in primary.items()
        }
        executables = {}
        for name in primary:
            left = file_record(primary[name])
            right = file_record(rebuilt[name])
            left_sections = pe_sections(primary[name])
            right_sections = pe_sections(rebuilt[name])
            full_match = left["sha256"] == right["sha256"] and left["bytes"] == right["bytes"]
            section_match = left_sections == right_sections
            if not full_match and not section_match:
                different_sections = pe_section_differences(
                    left_sections, right_sections
                )
                raise RuntimeError(
                    f"isolated rebuild differs in PE sections for {name}: "
                    f"{different_sections}"
                )
            executables[name] = {
                "primary": left,
                "isolated_rebuild": right,
                "full_file_match": full_match,
                "all_pe_sections_match": section_match,
                "primary_pe_sections": left_sections,
                "isolated_pe_sections": right_sections,
            }
    build = {
        "schema": "chain-rescue-v2-build-manifest",
        "source_commit": source_commit,
        "source_tree": source_tree,
        "source_files": source_file_records(repository),
        "toolchain": EXPECTED_TOOLCHAIN,
        "rustc": subprocess.run(
            ["rustc", f"+{EXPECTED_TOOLCHAIN}", "--version"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip(),
        "cargo": subprocess.run(
            ["cargo", f"+{EXPECTED_TOOLCHAIN}", "--version"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip(),
        "build_command": build_command,
        "isolated_rebuild_command": rebuild_command,
        "external_input_manifest_sha256": sha256(input_manifest),
        "executables": executables,
    }
    exclusive_write_json(build_manifest, build)
    exclusive_write_json(
        PROVENANCE_INDEX,
        {
            "schema": "chain-rescue-v2-provenance-index",
            "immutable": True,
            "implementation_source_commit": source_commit,
            "implementation_source_tree": source_tree,
            "external_inputs": {
                **file_record(input_manifest),
                "path": input_manifest.relative_to(HERE).as_posix(),
            },
            "build_manifest": {
                **file_record(build_manifest),
                "path": build_manifest.relative_to(HERE).as_posix(),
            },
        },
    )
    print(f"wrote {input_manifest.relative_to(HERE)}")
    print(f"wrote {build_manifest.relative_to(HERE)}")
    print(f"wrote {PROVENANCE_INDEX.relative_to(HERE)}")


def is_rust_binary_source(path: str) -> bool:
    return (
        path in {"Cargo.toml", "Cargo.lock"}
        or path.endswith(".rs")
        or path.startswith("integrations/bridgestan/")
        or path
        in {
            "STUDIES/chain_rescue_v2/Cargo.toml",
            "STUDIES/chain_rescue_v2/Cargo.lock",
        }
    )


def canonical_source_matches(
    repository: Path, record: dict[str, Any]
) -> bool:
    path = repository / record["path"]
    if record.get("git_blob_sha1") is not None:
        actual_blob = (
            git_output(
                repository,
                "hash-object",
                f"--path={record['path']}",
                str(path),
            )
            if path.is_file()
            else None
        )
        return actual_blob == record["git_blob_sha1"]
    return file_matches_record(path, record)


def rebind_amendment_3_provenance() -> None:
    if AMENDMENT_3_PROVENANCE_INDEX.exists():
        raise RuntimeError("Amendment-3 provenance index already exists; refusing replacement")
    repository = Path(git_output(HERE, "rev-parse", "--show-toplevel"))
    if git_output(repository, "status", "--porcelain=v1"):
        raise RuntimeError("source worktree must be clean before provenance rebind")
    old_input = authenticated_pointer_path(
        PROVENANCE_INDEX, "external_inputs", LEGACY_INPUT_MANIFEST
    )
    old_build_path = authenticated_pointer_path(
        PROVENANCE_INDEX, "build_manifest", LEGACY_BUILD_MANIFEST
    )
    old_build = json.loads(old_build_path.read_text(encoding="utf-8"))
    rust_source_files = [
        record
        for record in old_build.get("source_files", [])
        if is_rust_binary_source(record["path"])
    ]
    changed_rust = [
        record["path"]
        for record in rust_source_files
        if not canonical_source_matches(repository, record)
    ]
    if changed_rust:
        raise RuntimeError(
            f"Rust binary sources changed; audited rebuild is required: {changed_rust}"
        )
    for name, path in (
        ("cell", HARNESS),
        ("funnel", FUNNEL),
        ("conformance", CONFORMANCE_BIN),
    ):
        if not file_matches_record(
            path, old_build["executables"][name]["primary"]
        ):
            raise RuntimeError(f"prepared executable changed before rebind: {name}")
    source_commit = git_output(repository, "rev-parse", "HEAD")
    source_tree = git_output(repository, "rev-parse", "HEAD^{tree}")
    suffix = source_commit[:12]
    input_manifest = (
        ARTIFACTS / "provenance" / f"external-inputs-amendment-3-{suffix}.json"
    )
    build_manifest = (
        ARTIFACTS / "provenance" / f"build-manifest-amendment-3-{suffix}.json"
    )
    if input_manifest.exists() or build_manifest.exists():
        raise RuntimeError("versioned Amendment-3 provenance path already exists")
    external = inspect_external_inputs()
    external["implementation_source_commit"] = source_commit
    external["implementation_source_tree"] = source_tree
    exclusive_write_json(input_manifest, external)
    build = {
        **old_build,
        "schema": "chain-rescue-v2-build-manifest-analysis-rebind",
        "provenance_revision": "amendment-3-analysis-only-rebind-v1",
        "source_commit": source_commit,
        "source_tree": source_tree,
        "source_files": source_file_records(repository),
        "external_input_manifest_sha256": sha256(input_manifest),
        "build_performed_for_rebind": False,
        "rust_binary_source_commit": old_build["source_commit"],
        "rust_binary_source_tree": old_build["source_tree"],
        "rust_binary_source_files": rust_source_files,
        "conformance_build_manifest_sha256": sha256(old_build_path),
        "reused_audited_executables": {
            "reason": (
                "Amendment 3 and its analyzer/report/documentation changes do not "
                "modify Rust binary sources"
            ),
            "build_manifest": {
                **file_record(old_build_path),
                "path": old_build_path.relative_to(HERE).as_posix(),
            },
            "external_inputs": {
                **file_record(old_input),
                "path": old_input.relative_to(HERE).as_posix(),
            },
        },
    }
    exclusive_write_json(build_manifest, build)
    exclusive_write_json(
        AMENDMENT_3_PROVENANCE_INDEX,
        {
            "schema": "chain-rescue-v2-provenance-index-amendment-3",
            "immutable": True,
            "implementation_source_commit": source_commit,
            "implementation_source_tree": source_tree,
            "external_inputs": {
                **file_record(input_manifest),
                "path": input_manifest.relative_to(HERE).as_posix(),
            },
            "build_manifest": {
                **file_record(build_manifest),
                "path": build_manifest.relative_to(HERE).as_posix(),
            },
            "reuses_immutable_binary_build": {
                **file_record(old_build_path),
                "path": old_build_path.relative_to(HERE).as_posix(),
            },
        },
    )
    print(f"wrote {input_manifest.relative_to(HERE)}")
    print(f"wrote {build_manifest.relative_to(HERE)}")
    print(f"wrote {AMENDMENT_3_PROVENANCE_INDEX.relative_to(HERE)}")


def rebind_post_run_provenance() -> None:
    if POST_RUN_PROVENANCE_INDEX.exists():
        raise RuntimeError("post-run provenance index already exists; refusing replacement")
    repository = Path(git_output(HERE, "rev-parse", "--show-toplevel"))
    if git_output(repository, "status", "--porcelain=v1"):
        raise RuntimeError("source worktree must be clean before post-run provenance rebind")
    old_input = authenticated_pointer_path(
        AMENDMENT_3_PROVENANCE_INDEX, "external_inputs", LEGACY_INPUT_MANIFEST
    )
    old_build_path = authenticated_pointer_path(
        AMENDMENT_3_PROVENANCE_INDEX, "build_manifest", LEGACY_BUILD_MANIFEST
    )
    old_build = json.loads(old_build_path.read_text(encoding="utf-8"))
    rust_source_files = old_build.get("rust_binary_source_files") or [
        record
        for record in old_build.get("source_files", [])
        if is_rust_binary_source(record["path"])
    ]
    changed_rust = [
        record["path"]
        for record in rust_source_files
        if not canonical_source_matches(repository, record)
    ]
    if changed_rust:
        raise RuntimeError(
            f"Rust binary sources changed; audited rebuild is required: {changed_rust}"
        )
    for name, path in (
        ("cell", HARNESS),
        ("funnel", FUNNEL),
        ("conformance", CONFORMANCE_BIN),
    ):
        if not file_matches_record(path, old_build["executables"][name]["primary"]):
            raise RuntimeError(f"prepared executable changed before post-run rebind: {name}")
    source_commit = git_output(repository, "rev-parse", "HEAD")
    source_tree = git_output(repository, "rev-parse", "HEAD^{tree}")
    suffix = source_commit[:12]
    input_manifest = (
        ARTIFACTS / "provenance" / f"external-inputs-post-run-{suffix}.json"
    )
    build_manifest = (
        ARTIFACTS / "provenance" / f"build-manifest-post-run-{suffix}.json"
    )
    if input_manifest.exists() or build_manifest.exists():
        raise RuntimeError("versioned post-run provenance path already exists")
    external = inspect_external_inputs()
    external["implementation_source_commit"] = source_commit
    external["implementation_source_tree"] = source_tree
    exclusive_write_json(input_manifest, external)
    build = {
        **old_build,
        "schema": "chain-rescue-v2-build-manifest-post-run-analysis-rebind",
        "provenance_revision": "post-run-derived-correction-v1",
        "source_commit": source_commit,
        "source_tree": source_tree,
        "source_files": source_file_records(repository),
        "external_input_manifest_sha256": sha256(input_manifest),
        "build_performed_for_rebind": False,
        "rust_binary_source_files": rust_source_files,
        "prior_analysis_provenance": {
            "build_manifest": {
                **file_record(old_build_path),
                "path": old_build_path.relative_to(HERE).as_posix(),
            },
            "external_inputs": {
                **file_record(old_input),
                "path": old_input.relative_to(HERE).as_posix(),
            },
        },
    }
    exclusive_write_json(build_manifest, build)
    exclusive_write_json(
        POST_RUN_PROVENANCE_INDEX,
        {
            "schema": "chain-rescue-v2-provenance-index-post-run",
            "immutable": True,
            "analysis_only": True,
            "implementation_source_commit": source_commit,
            "implementation_source_tree": source_tree,
            "external_inputs": {
                **file_record(input_manifest),
                "path": input_manifest.relative_to(HERE).as_posix(),
            },
            "build_manifest": {
                **file_record(build_manifest),
                "path": build_manifest.relative_to(HERE).as_posix(),
            },
            "prior_analysis_provenance": {
                **file_record(old_build_path),
                "path": old_build_path.relative_to(HERE).as_posix(),
            },
        },
    )
    print(f"wrote {input_manifest.relative_to(HERE)}")
    print(f"wrote {build_manifest.relative_to(HERE)}")
    print(f"wrote {POST_RUN_PROVENANCE_INDEX.relative_to(HERE)}")


def verify_provenance(require_binaries: bool = True) -> dict[str, Any]:
    errors = []
    input_manifest, build_manifest = provenance_paths()
    if not input_manifest.is_file() or not build_manifest.is_file():
        raise RuntimeError("audited input/build manifests are missing")
    frozen = json.loads(input_manifest.read_text(encoding="utf-8"))
    build = json.loads(build_manifest.read_text(encoding="utf-8"))
    current = inspect_external_inputs()
    if logical_external_identity(current) != logical_external_identity(frozen):
        errors.append("logical external provenance mismatch")
    if build.get("external_input_manifest_sha256") != sha256(input_manifest):
        errors.append("build manifest input-manifest hash mismatch")
    if (
        frozen.get("implementation_source_commit") != build.get("source_commit")
        or frozen.get("implementation_source_tree") != build.get("source_tree")
    ):
        errors.append("implementation source commit/tree provenance mismatch")
    repository = Path(git_output(HERE, "rev-parse", "--show-toplevel"))
    for record in build.get("source_files", []):
        if not canonical_source_matches(repository, record):
            errors.append(f"audited source mismatch: {record['path']}")
    reuse = build.get("reused_audited_executables")
    if reuse is not None:
        reused_build = HERE / reuse.get("build_manifest", {}).get("path", "")
        if not file_matches_record(reused_build, reuse.get("build_manifest", {})):
            errors.append("reused immutable build manifest authentication failed")
        reused_inputs = HERE / reuse.get("external_inputs", {}).get("path", "")
        if not file_matches_record(reused_inputs, reuse.get("external_inputs", {})):
            errors.append("reused immutable input manifest authentication failed")
        for record in build.get("rust_binary_source_files", []):
            if not canonical_source_matches(repository, record):
                errors.append(
                    f"reused binary source mismatch: {record['path']}"
                )
        if reused_build.is_file() and (
            build.get("conformance_build_manifest_sha256")
            != sha256(reused_build)
        ):
            errors.append("conformance reused-build hash mismatch")
    prior_analysis = build.get("prior_analysis_provenance")
    if prior_analysis is not None:
        for label in ("build_manifest", "external_inputs"):
            record = prior_analysis.get(label, {})
            path = HERE / record.get("path", "")
            if not file_matches_record(path, record):
                errors.append(f"prior analysis provenance mismatch: {label}")
    if build.get("toolchain") != EXPECTED_TOOLCHAIN:
        errors.append("build manifest toolchain mismatch")
    if require_binaries:
        for name, path in (
            ("cell", HARNESS),
            ("funnel", FUNNEL),
            ("conformance", CONFORMANCE_BIN),
        ):
            expected = build.get("executables", {}).get(name, {}).get("primary", {})
            if not file_matches_record(path, expected):
                errors.append(f"release executable mismatch: {name}")
    result = {
        "verified": not errors,
        "errors": errors,
        "mode": (
            "prepared_worktree_full_executable_authentication"
            if require_binaries
            else "source_and_logical_inputs_only"
        ),
        "input_manifest_path": input_manifest.relative_to(HERE).as_posix(),
        "build_manifest_path": build_manifest.relative_to(HERE).as_posix(),
        "input_manifest_sha256": sha256(input_manifest),
        "build_manifest_sha256": sha256(build_manifest),
        "source_commit": build.get("source_commit"),
        "source_tree": build.get("source_tree"),
        "executables": build.get("executables"),
    }
    if errors:
        raise RuntimeError("; ".join(errors))
    return result


def verify_rebuild() -> dict[str, Any]:
    provenance = verify_provenance(require_binaries=False)
    _, build_manifest = provenance_paths()
    build = json.loads(build_manifest.read_text(encoding="utf-8"))
    repository = Path(git_output(HERE, "rev-parse", "--show-toplevel"))
    rustc = subprocess.run(
        ["rustc", f"+{EXPECTED_TOOLCHAIN}", "--version"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    cargo = subprocess.run(
        ["cargo", f"+{EXPECTED_TOOLCHAIN}", "--version"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if rustc != build.get("rustc") or cargo != build.get("cargo"):
        raise RuntimeError("fresh rebuild Rust/Cargo versions differ from build manifest")
    command = [
        "cargo",
        f"+{EXPECTED_TOOLCHAIN}",
        "build",
        "--release",
        "--locked",
        "--manifest-path",
        str(HERE / "Cargo.toml"),
    ]
    (HERE / "target").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="wp36-verify-rebuild-", dir=HERE / "target"
    ) as temporary:
        subprocess.run(command + ["--target-dir", temporary], cwd=repository, check=True)
        results = {}
        names = {
            "cell": f"chain-rescue-v2{EXE}",
            "funnel": f"funnel{EXE}",
            "conformance": f"conformance{EXE}",
        }
        for name, filename in names.items():
            rebuilt = Path(temporary) / "release" / filename
            expected_sections = build["executables"][name]["primary_pe_sections"]
            actual_sections = pe_sections(rebuilt)
            differing = pe_section_differences(expected_sections, actual_sections)
            results[name] = {
                "equivalent": not differing,
                "different_pe_sections": differing,
                "rebuilt": file_record(rebuilt),
                "full_file_matches_prepared_worktree": (
                    sha256(rebuilt)
                    == build["executables"][name]["primary"]["sha256"]
                ),
            }
    if not all(result["equivalent"] for result in results.values()):
        raise RuntimeError(f"fresh rebuild PE section mismatch: {results}")
    return {
        "verified": True,
        "mode": "fresh_rebuild_pe_section_equivalence",
        "implementation_source_commit": provenance["source_commit"],
        "implementation_source_tree": provenance["source_tree"],
        "build_manifest_sha256": provenance["build_manifest_sha256"],
        "rustc": rustc,
        "cargo": cargo,
        "results": results,
    }


def validate_conformance_artifact() -> dict[str, Any]:
    conformance = current_conformance_path()
    _, build_manifest = provenance_paths()
    if not conformance.is_file():
        raise RuntimeError("current conformance artifact is missing")
    result = json.loads(conformance.read_text(encoding="utf-8"))
    errors = []
    comparison = result.get("comparison", {})
    required = (
        "bit_identical",
        "retained_draw_bytes_equal",
        "work_counters_equal",
        "final_adaptation_hashes_equal",
        "retained_diagnostics_equal",
        "non_rescue_telemetry_equal",
        "no_rescue_rng_mutation",
        "observed_hit_path_exercised",
    )
    if result.get("status") != "pass" or result.get("evidence") is not False:
        errors.append("conformance is not a non-evidence PASS")
    if not all(comparison.get(field) is True for field in required):
        errors.append("conformance identity/hit requirements are incomplete")
    if int(result.get("observe_hits", 0)) <= 0:
        errors.append("conformance did not exercise an observed hit")
    if int(comparison.get("observe_forbidden_outcomes", -1)) != 0:
        errors.append("conformance recorded forbidden observe outcomes")
    if result.get("protocol_sha256") != sha256(PROTOCOL_PATH):
        errors.append("conformance protocol hash mismatch")
    if result.get("amendment_1_sha256") != sha256(AMENDMENT_1):
        errors.append("conformance amendment-1 hash mismatch")
    if result.get("amendment_2_sha256") != sha256(AMENDMENT_2):
        errors.append("conformance amendment-2 hash mismatch")
    build = json.loads(build_manifest.read_text(encoding="utf-8"))
    expected_conformance_build = build.get(
        "conformance_build_manifest_sha256", sha256(build_manifest)
    )
    if result.get("build_manifest_sha256") != expected_conformance_build:
        errors.append("conformance build-manifest hash mismatch")
    expected_exe = build["executables"]["conformance"]["primary"]
    if result.get("immutable") is not True:
        errors.append("conformance artifact is not marked immutable")
    if (
        result.get("implementation_source_commit")
        != build.get("rust_binary_source_commit", build.get("source_commit"))
        or result.get("implementation_source_tree")
        != build.get("rust_binary_source_tree", build.get("source_tree"))
    ):
        errors.append("conformance implementation source mismatch")
    if result.get("conformance_executable") != expected_exe:
        errors.append("conformance executable provenance mismatch")
    if errors:
        raise RuntimeError("; ".join(errors))
    return {
        "authenticated": True,
        "artifact_path": conformance.relative_to(HERE).as_posix(),
        "artifact_sha256": sha256(conformance),
        "observe_hits": result["observe_hits"],
        "build_manifest_sha256": result["build_manifest_sha256"],
    }


def validate_environment(
    require_binaries: bool = True, require_conformance: bool = True
) -> dict[str, Any]:
    errors: list[str] = []
    if len(planned_cells()) != 288:
        errors.append(f"planned cell count is {len(planned_cells())}, expected 288")
    if len(SEEDS) != 12 or len(set(SEEDS)) != 12:
        errors.append("protocol must contain 12 unique evidence seeds")
    if TARGETS[-1] != "funnel-10d" or tuple(TARGETS[:-1]) != MODELS:
        errors.append("target order does not match the frozen model order plus funnel")
    try:
        provenance = verify_provenance(require_binaries=require_binaries)
    except Exception as error:
        provenance = None
        errors.append(str(error))
    try:
        conformance = validate_conformance_artifact() if require_conformance else None
    except Exception as error:
        conformance = None
        errors.append(str(error))
    result = {
        "verified": not errors,
        "errors": errors,
        "protocol_sha256": sha256(PROTOCOL_PATH),
        "amendment_1_sha256": sha256(AMENDMENT_1),
        "amendment_2_sha256": sha256(AMENDMENT_2),
        "amendment_3_sha256": sha256(AMENDMENT_3),
        "post_run_correction_sha256": sha256(POST_RUN_CORRECTION),
        "ledger_entry_sha256": sha256(LEDGER_ENTRY),
        "provenance": provenance,
        "conformance": conformance,
    }
    if errors:
        raise RuntimeError("; ".join(errors))
    return result


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def canonical_criterion(step_hit: bool, density_hit: bool) -> str | None:
    return "Step" if step_hit else "LogDensity" if density_hit else None


def expected_warmup_schedule(warmup: int) -> dict[str, Any]:
    initial = 75
    terminal = 50
    slow_end = warmup - terminal
    start = initial
    size = 25
    windows = []
    while start < slow_end:
        remaining = slow_end - start
        length = min(size, remaining)
        if remaining > length and remaining - length < size * 2:
            length = remaining
        end = start + length
        windows.append(
            {
                "window_index": len(windows),
                "start": start,
                "end": end,
                "window_transitions": length,
                "boundary_transition": end - 1,
            }
        )
        start = end
        size *= 2
    return {
        "schema": "chain-rescue-v2-warmup-schedule",
        "source": "sampler_metadata",
        "initial_fast_end": initial,
        "terminal_fast_start": slow_end,
        "used_short_warmup_fallback": False,
        "windows": windows,
    }


def validate_boundary(
    event: dict[str, Any],
    target: str,
    arm: str,
    seed: int,
    chain: int,
    dimension: int,
    expected_prior: tuple[str | None, int],
) -> tuple[list[str], tuple[str | None, int]]:
    errors = [
        f"missing boundary field {name}"
        for name in sorted(BOUNDARY_FIELDS - event.keys())
    ]
    errors.extend(
        f"missing restart-schema field {name}" for name in sorted(RESTART_FIELDS - event.keys())
    )
    if event.get("target") != target or event.get("arm") != arm or event.get("seed") != seed:
        errors.append("boundary target/arm/seed does not match its cell")
    if event.get("chain") != chain:
        errors.append(f"boundary chain is {event.get('chain')!r}, expected {chain}")
    for name in ("window_index", "transition", "window_transitions", "prior_streak", "resulting_streak"):
        if not isinstance(event.get(name), int) or event[name] < 0:
            errors.append(f"{name} is not a nonnegative integer")
    for name in ("eligible", "step_hit", "density_hit"):
        if not isinstance(event.get(name), bool):
            errors.append(f"{name} is not boolean")
    position = event.get("pre_action_unconstrained_position")
    if not isinstance(position, list) or len(position) != dimension or not all(
        finite_number(value) for value in position
    ):
        errors.append("pre-action position has wrong shape or nonfinite values")
    if event.get("initial_position_sha256") is None:
        errors.append("boundary initial-position hash is missing")

    outcome = event.get("outcome")
    if outcome not in OUTCOMES:
        errors.append(f"invalid outcome {outcome!r}")
    eligible = event.get("eligible") is True
    if eligible and event.get("skip_reason") is not None:
        errors.append("eligible boundary has a skip reason")
    if not eligible and event.get("skip_reason") not in {
        "ShortWindow",
        "NoSource",
        "NonFiniteScore",
    }:
        errors.append("ineligible boundary lacks an exact valid skip reason")
    if not eligible and outcome != "skipped":
        errors.append("ineligible boundary outcome is not skipped")

    if not finite_number(event.get("current_step")):
        errors.append("current_step is missing or nonfinite")
    if eligible:
        for name in (
            "median_step",
            "step_threshold",
            "median_log_density",
            "log_density_iqr",
            "density_reference",
            "density_spread",
            "density_gap",
            "density_threshold",
        ):
            if not finite_number(event.get(name)):
                errors.append(f"eligible boundary {name} is missing or nonfinite")
        if all(
            finite_number(event.get(name))
            for name in (
                "median_step",
                "step_threshold",
                "median_log_density",
                "density_reference",
                "density_spread",
                "density_gap",
                "density_threshold",
                "current_step",
            )
        ):
            if event["step_threshold"] != 0.1 * event["median_step"]:
                errors.append("step threshold does not equal 0.1 * median step")
            if event["density_threshold"] != 3.0 * event["density_spread"]:
                errors.append("density threshold does not equal 3.0 * spread")
            if event["density_gap"] != event["density_reference"] - event["median_log_density"]:
                errors.append("density gap is inconsistent")
            if event["step_hit"] != (event["current_step"] < event["step_threshold"]):
                errors.append("step_hit is inconsistent")
            if event["density_hit"] != (
                event["density_gap"] > event["density_threshold"]
            ):
                errors.append("density_hit is inconsistent")
    criterion = canonical_criterion(
        event.get("step_hit") is True, event.get("density_hit") is True
    ) if eligible else None
    if event.get("observed_canonical_criterion") != criterion:
        errors.append("canonical criterion is inconsistent")
    if event.get("outcome_criterion") != (
        criterion if outcome in {"observed_hit", "pending_first_hit", "restarted"} else None
    ):
        errors.append("outcome criterion is inconsistent")

    recorded_prior = (event.get("prior_criterion"), event.get("prior_streak"))
    if recorded_prior != expected_prior:
        errors.append(f"prior streak {recorded_prior!r} != expected {expected_prior!r}")
    if arm in {"observe", "current"}:
        expected_result = (None, 0)
        expected_outcome = (
            "skipped"
            if not eligible
            else ("observed_hit" if arm == "observe" else "restarted")
            if criterion is not None
            else "kept"
        )
    elif not eligible or criterion is None:
        expected_result = (None, 0)
        expected_outcome = "skipped" if not eligible else "kept"
    elif expected_prior == (criterion, 1):
        expected_result = (None, 0)
        expected_outcome = "restarted"
    else:
        expected_result = (criterion, 1)
        expected_outcome = "pending_first_hit"
    recorded_result = (event.get("resulting_criterion"), event.get("resulting_streak"))
    if recorded_result != expected_result:
        errors.append(f"resulting streak {recorded_result!r} != expected {expected_result!r}")
    if outcome != expected_outcome:
        errors.append(f"outcome {outcome!r} != expected {expected_outcome!r}")

    if outcome == "restarted":
        for name in RESTART_FIELDS:
            if event.get(name) is None:
                errors.append(f"restart field {name} is missing/null")
        installed = event.get("installed_unconstrained_position")
        if not isinstance(installed, list) or len(installed) != dimension or not all(
            finite_number(value) for value in installed
        ):
            errors.append("installed position has wrong shape or nonfinite values")
        elif installed_position_sha256(installed) != event.get("installed_position_sha256"):
            errors.append("installed position hash mismatch")
    elif any(event.get(name) is not None for name in RESTART_FIELDS):
        errors.append("non-restart boundary contains restart-only fields")
    if arm == "observe" and (
        outcome in {"restarted", "pending_first_hit"}
        or event.get("source_window_position_index") is not None
        or event.get("installed_position_sha256") is not None
    ):
        errors.append("observe consumed or simulated rescue state")
    return errors, expected_result


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
    if raw.get("schema_version") != 1:
        errors.append("raw schema_version is not 1")
    if raw.get("complete") is not True:
        errors.append("raw result is not marked complete")
    if raw.get("target") != target or raw.get("arm") != arm or raw.get("seed") != seed:
        errors.append("raw target/arm/seed mismatch")
    status = raw.get("status")
    if status not in {"ok", "sampler_error"}:
        errors.append(f"invalid raw status {raw.get('status')!r}")
    expected_warmup = 2_000 if target == "funnel-10d" else 1_000
    expected_retained = 20_000 if target == "funnel-10d" else 1_000
    for name, expected in (
        ("chains", 4),
        ("warmup", expected_warmup),
        ("retained", expected_retained),
        ("threads", 4),
    ):
        if raw.get(name) != expected:
            errors.append(f"{name} is {raw.get(name)!r}, expected {expected}")
    dimension = raw.get("dimension")
    if not isinstance(dimension, int) or dimension <= 0:
        errors.append("dimension is missing or invalid")
        dimension = 0
    elif target == "funnel-10d" and dimension != 10:
        errors.append("funnel dimension is not 10")
    if status == "ok" and (
        not isinstance(raw.get("target_calls_total"), int)
        or raw["target_calls_total"] <= 0
    ):
        errors.append("successful cell target_calls_total is missing/nonpositive")
    if status == "ok" and not isinstance(raw.get("tuning"), dict):
        errors.append("successful cell tuning settings are missing")
    if not isinstance(raw.get("algorithm_revision"), str) or not raw["algorithm_revision"]:
        errors.append("algorithm revision is missing")
    if target != "funnel-10d":
        init = raw.get("init")
        if (
            not isinstance(init, dict)
            or init.get("rule") != "owalnuts::sampler::Init::uniform()"
            or init.get("radius") != 2.0
            or init.get("max_attempts") != 100
            or not isinstance(init.get("start_search_calls"), int)
            or init.get("start_search_calls", -1) < 0
        ):
            errors.append("initialization settings/call count mismatch")
    warmup = raw.get("warmup_config")
    expected_policy = {"observe": "ObserveOnly", "current": "Immediate", "two_hit": "TwoHit"}[arm]
    if not isinstance(warmup, dict):
        errors.append("warmup_config is missing")
    else:
        rescue = warmup.get("chain_rescue")
        if (
            warmup.get("mode") != "dual_averaging"
            or warmup.get("target_accept") != 0.8
            or warmup.get("warmup_exhaustion_rule") != "AcceptUnlessDivergent"
            or warmup.get("metric_regularization") != "Stan"
            or warmup.get("mass_adaptation") is not True
            or warmup.get("explicit_arm") is not True
            or warmup.get("inherits_default_chain_rescue") is not False
            or not isinstance(rescue, dict)
            or rescue.get("mode") != "RestartFromBest"
            or rescue.get("policy") != expected_policy
            or rescue.get("step_ratio") != 0.1
            or rescue.get("log_density_iqr_factor") != 3.0
            or rescue.get("minimum_window_transitions") != 10
            or rescue.get("source_tie_rule")
            != "larger step, then larger median log density, then higher chain index"
        ):
            errors.append("explicit frozen arm/warmup configuration mismatch")
    starts = raw.get("initial_positions")
    hashes = raw.get("initial_position_sha256")
    if not isinstance(starts, list) or not isinstance(hashes, list):
        errors.append("initial positions or hashes are not arrays")
    elif len(starts) != len(hashes):
        errors.append("initial position/hash lengths differ")
    else:
        for index, (start, recorded) in enumerate(zip(starts, hashes)):
            if (
                not isinstance(start, list)
                or len(start) != dimension
                or not all(finite_number(value) for value in start)
            ):
                errors.append(f"initial position {index} has wrong shape/nonfinite values")
                continue
            try:
                actual = initial_position_sha256(start)
                if actual != recorded:
                    errors.append(f"initial position hash mismatch for chain {index}")
            except Exception as error:
                errors.append(f"could not hash initial chain {index}: {error}")
    if status == "sampler_error":
        if not raw.get("error"):
            errors.append("sampler_error result lacks an error message")
        stage = raw.get("stage")
        if stage not in {"init", "run"}:
            errors.append("sampler_error stage is not init or run")
        expected_unknown = stage == "run"
        if raw.get("telemetry_complete") is not False:
            errors.append("sampler_error incorrectly claims complete telemetry")
        if raw.get("telemetry_unknown") is not expected_unknown:
            errors.append("sampler_error telemetry_unknown is inconsistent with stage")
        if raw.get("rescue_history") != (
            "unavailable" if expected_unknown else "known_zero"
        ):
            errors.append("sampler_error rescue_history is inconsistent with stage")
        if raw.get("warmup_schedule") is not None:
            errors.append("sampler_error must mark warmup schedule unavailable")
        if expected_unknown:
            if (
                not isinstance(starts, list)
                or not isinstance(hashes, list)
                or len(starts) != 4
                or len(hashes) != 4
            ):
                errors.append("run-stage sampler error lacks four initial hashes")
            if raw.get("actions") is not None or raw.get("chains_data") is not None:
                errors.append("unknown run telemetry must be represented as null")
        elif raw.get("actions") != [] or raw.get("chains_data") != []:
            errors.append("init-stage sampler error must record known empty rescue history")
        return not errors, errors
    if (
        raw.get("telemetry_complete") is not True
        or raw.get("telemetry_unknown") is not False
        or raw.get("rescue_history") != "complete"
    ):
        errors.append("successful raw result lacks complete rescue telemetry")
    expected_schedule = expected_warmup_schedule(expected_warmup)
    if raw.get("warmup_schedule") != expected_schedule:
        errors.append("successful raw warmup schedule metadata is not exact")
    if (
        not isinstance(starts, list)
        or not isinstance(hashes, list)
        or len(starts) != 4
        or len(hashes) != 4
    ):
        errors.append("successful cell does not contain four starts and hashes")
        return not errors, errors
    chains = raw.get("chains_data")
    if not isinstance(chains, list) or len(chains) != 4:
        errors.append("successful cell does not contain four chain records")
        return not errors, errors
    expected_draws = expected_retained
    restarts: list[dict[str, Any]] = []
    chain_events: list[list[dict[str, Any]]] = []
    chain_target_calls = 0
    for index, chain in enumerate(chains):
        if not isinstance(chain, dict):
            errors.append(f"chain record {index} is not an object")
            chain = {}
        if chain.get("chain") != index:
            errors.append(f"chain record {index} has the wrong index")
        if chain.get("initial_position_sha256") != hashes[index]:
            errors.append(f"chain {index} repeats a different initial hash")
        if chain.get("initial_position") != starts[index]:
            errors.append(f"chain {index} initial position differs from top-level start")
        for name in (
            "retained_unconstrained_sha256",
            "retained_diagnostics_sha256",
            "non_rescue_telemetry_sha256",
            "final_metric_sha256",
            "final_tuning_sha256",
        ):
            value = chain.get(name)
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                errors.append(f"chain {index} {name} is not a lowercase SHA-256")
        if not finite_number(chain.get("final_step_size")) or not finite_number(
            chain.get("final_max_error")
        ):
            errors.append(f"chain {index} final tuning is missing/nonfinite")
        if not isinstance(chain.get("mass_diagonal"), list) or len(
            chain["mass_diagonal"]
        ) != dimension or not all(
            finite_number(value) and value > 0 for value in chain["mass_diagonal"]
        ):
            errors.append(f"chain {index} final metric has wrong dimension")
        work = chain.get("work")
        if not isinstance(work, dict):
            errors.append(f"chain {index} work telemetry is missing")
        else:
            for phase in ("discarded", "retained", "total"):
                values = work.get(phase)
                if (
                    not isinstance(values, dict)
                    or set(values) != WORK_FIELDS
                    or any(
                        (
                            not isinstance(value, list)
                            or any(
                                not isinstance(item, int) or item < 0 for item in value
                            )
                        )
                        if name == "refinement_level_built"
                        else (not isinstance(value, int) or value < 0)
                        for name, value in values.items()
                    )
                ):
                    errors.append(f"chain {index} {phase} work telemetry is invalid")
            for name in ("adaptation_target_calls", "target_calls_including_adaptation"):
                if not isinstance(work.get(name), int) or work[name] < 0:
                    errors.append(f"chain {index} work {name} is invalid")
            if all(
                isinstance(work.get(phase), dict)
                and set(work[phase]) == WORK_FIELDS
                and isinstance(work[phase]["refinement_level_built"], list)
                and all(
                    isinstance(value, int) and value >= 0
                    for value in work[phase]["refinement_level_built"]
                )
                and all(
                    isinstance(value, int) and value >= 0
                    for name, value in work[phase].items()
                    if name != "refinement_level_built"
                )
                for phase in ("discarded", "retained", "total")
            ):
                for name in WORK_FIELDS:
                    if name == "refinement_level_built":
                        length = max(
                            len(work["discarded"][name]),
                            len(work["retained"][name]),
                        )
                        expected_total = [
                            (
                                work["discarded"][name][level]
                                if level < len(work["discarded"][name])
                                else 0
                            )
                            + (
                                work["retained"][name][level]
                                if level < len(work["retained"][name])
                                else 0
                            )
                            for level in range(length)
                        ]
                    else:
                        expected_total = (
                            work["discarded"][name] + work["retained"][name]
                        )
                    if work["total"][name] != expected_total:
                        errors.append(
                            f"chain {index} total work does not add for {name}"
                        )
                if (
                    work.get("target_calls_including_adaptation")
                    != work["total"]["target_calls_total"]
                    + work.get("adaptation_target_calls", -1)
                ):
                    errors.append(
                        f"chain {index} target-call total excludes adaptation"
                    )
                else:
                    chain_target_calls += work["target_calls_including_adaptation"]
        retained_diagnostics = chain.get("retained_diagnostics")
        if (
            not isinstance(retained_diagnostics, dict)
            or set(retained_diagnostics) != DIAGNOSTIC_FIELDS
            or any(
                not isinstance(value, int) or value < 0
                for value in retained_diagnostics.values()
            )
        ):
            errors.append(f"chain {index} retained diagnostics are missing")
        elif isinstance(work, dict) and isinstance(work.get("retained"), dict):
            for name, value in retained_diagnostics.items():
                if value != work["retained"].get(name):
                    errors.append(
                        f"chain {index} retained diagnostic {name} disagrees with work"
                    )
        samples = chain.get("samples")
        try:
            array = np.asarray(samples, dtype=np.float64)
            if (
                array.ndim != 2
                or array.shape[0] != expected_draws
                or array.shape[1] != dimension
            ):
                errors.append(f"chain {index} retained draw shape is {array.shape}")
            elif rust_retained_sha256(array) != chain.get("retained_unconstrained_sha256"):
                errors.append(f"chain {index} retained hash mismatch")
        except Exception as error:
            errors.append(f"chain {index} retained draws are malformed: {error}")
        events = chain.get("chain_rescues")
        if not isinstance(events, list) or not events:
            errors.append(f"chain {index} has no successful-run boundary telemetry")
            events = []
        chain_events.append(events)
        expected_boundaries = [
            (
                window["window_index"],
                window["boundary_transition"],
                window["window_transitions"],
            )
            for window in expected_schedule["windows"]
        ]
        recorded_boundaries = [
            (
                event.get("window_index"),
                event.get("transition"),
                event.get("window_transitions"),
            )
            for event in events
            if isinstance(event, dict)
        ]
        if recorded_boundaries != expected_boundaries:
            errors.append(
                f"chain {index} rescue boundaries do not exactly match warmup schedule"
            )
        prior: tuple[str | None, int] = (None, 0)
        previous_window = -1
        previous_transition = -1
        for event_index, event in enumerate(events):
            if not isinstance(event, dict):
                errors.append(f"chain {index} boundary {event_index}: record is not an object")
                event = {}
                events[event_index] = event
            event_errors, prior = validate_boundary(
                event, target, arm, seed, index, dimension, prior
            )
            errors.extend(
                f"chain {index} boundary {event_index}: {message}" for message in event_errors
            )
            if event.get("window_index", -1) <= previous_window:
                errors.append(f"chain {index} boundaries are not monotone by window")
            if event.get("transition", -1) <= previous_transition:
                errors.append(f"chain {index} boundaries are not monotone by transition")
            previous_window = event.get("window_index", previous_window)
            previous_transition = event.get("transition", previous_transition)
            if event.get("initial_position_sha256") != hashes[index]:
                errors.append(f"chain {index} boundary {event_index}: wrong initial hash")
            if event.get("outcome") == "restarted":
                restarts.append(event)
    if chain_events and any(
        [(event.get("window_index"), event.get("transition")) for event in events]
        != [
            (event.get("window_index"), event.get("transition"))
            for event in chain_events[0]
        ]
        for events in chain_events[1:]
    ):
        errors.append("chains do not share common rescue windows")
    for boundary_index in range(min((len(events) for events in chain_events), default=0)):
        group = [events[boundary_index] for events in chain_events]
        common_fields = (
            "window_transitions",
            "eligible",
            "skip_reason",
            "median_step",
            "step_threshold",
            "density_reference",
            "density_spread",
            "density_threshold",
            "proposed_source_chain",
        )
        for name in common_fields:
            if any(event.get(name) != group[0].get(name) for event in group[1:]):
                errors.append(f"boundary {boundary_index} has inconsistent {name} across chains")
        if group[0].get("eligible") is True and all(
            finite_number(event.get("current_step"))
            and finite_number(event.get("median_log_density"))
            and event.get("observed_canonical_criterion") in {None, "Step", "LogDensity"}
            for event in group
        ):
            candidates = [
                index
                for index, event in enumerate(group)
                if event.get("observed_canonical_criterion") is None
            ]
            expected_source = (
                max(
                    candidates,
                    key=lambda index: (
                        group[index]["current_step"],
                        group[index]["median_log_density"],
                        index,
                    ),
                )
                if candidates
                else None
            )
            if group[0].get("proposed_source_chain") != expected_source:
                errors.append(
                    f"boundary {boundary_index} proposed source violates higher-index tie rule"
                )
            for event in group:
                if event.get("outcome") == "restarted":
                    if event.get("actual_source_chain") != expected_source:
                        errors.append(
                            f"boundary {boundary_index} proposed/actual source mismatch"
                        )
                    if expected_source is not None and event.get("installed_step") != group[
                        expected_source
                    ].get("current_step"):
                        errors.append(
                            f"boundary {boundary_index} installed step differs from source"
                        )
                    source_index = event.get("source_window_position_index")
                    if (
                        expected_source is None
                        or not isinstance(source_index, int)
                        or not (
                            0 <= source_index
                            < group[expected_source]["window_transitions"]
                        )
                    ):
                        errors.append(
                            f"boundary {boundary_index} source-window index is out of range"
                        )
        elif group[0].get("eligible") is True:
            errors.append(
                f"boundary {boundary_index} source cannot be authenticated from scores"
            )
    if raw.get("actions") != restarts:
        errors.append("top-level actions are not exactly the ordered restart records")
    initialization_calls = (
        raw.get("init", {}).get("start_search_calls", 0)
        if target != "funnel-10d"
        else 0
    )
    if (
        not isinstance(initialization_calls, int)
        or initialization_calls < 0
        or raw.get("target_calls_total") != chain_target_calls + initialization_calls
    ):
        errors.append("top-level target call total is inconsistent")
    return not errors, errors


def interrupted_record(
    target: str, seed: int, arm: str, marker: Path
) -> dict[str, Any]:
    reason = (
        "launch marker exists without a process record; protocol forbids rerunning "
        "a potentially launched child"
    )
    try:
        launch = json.loads(marker.read_text(encoding="utf-8"))
    except Exception:
        launch = {}
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
        "launch_marker_sha256": sha256(marker),
        "command": launch.get("command"),
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
        record = json.loads(record_path.read_text(encoding="utf-8"))
        marker_errors = validate_process_marker(record, marker)
        if marker_errors:
            record = dict(record)
            record["process_valid"] = False
            record["fault"] = True
            record["status"] = "process_fault"
            record.setdefault("failure_reasons", []).extend(marker_errors)
        return record
    if marker.exists():
        record = interrupted_record(target, seed, arm, marker)
        try:
            exclusive_write_json(record_path, record)
            return record
        except FileExistsError:
            return json.loads(record_path.read_text(encoding="utf-8"))

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
    launch = {
        "schema": "chain-rescue-v2-launch",
        "cell_id": identifier,
        "target": target,
        "seed": seed,
        "arm": arm,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "command": command,
    }
    try:
        exclusive_write_json(marker, launch)
    except FileExistsError as error:
        raise RuntimeError(
            f"launch marker was claimed concurrently for {identifier}; child not launched"
        ) from error
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
        "launch_marker": marker.relative_to(HERE).as_posix(),
        "launch_marker_sha256": sha256(marker),
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
    exclusive_write_json(record_path, record)
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


def bind_origin_initial_hashes(
    origins: dict[str, Any], initial_hashes: list[str]
) -> dict[str, Any]:
    if len(initial_hashes) != 4:
        raise ValueError("origin metadata requires four initial hashes")
    for chain in range(4):
        origins["by_chain"][str(chain)]["initial_position_sha256"] = initial_hashes[
            chain
        ]
    origins["origin_metadata"] = [
        {
            "chain": chain,
            "initial_position_sha256": initial_hashes[chain],
            "parameters": origins["by_chain"][str(chain)]["parameters"],
        }
        for chain in origins["chains"]
    ]
    return origins


def reference_z(mean: float, reference_mean: float, mcse: float, reference_mcse: float) -> float:
    denominator = math.sqrt(mcse * mcse + reference_mcse * reference_mcse)
    return (
        (mean - reference_mean) / denominator
        if denominator > 0 and math.isfinite(denominator)
        else math.nan
    )


def reference_metrics(
    draws: np.ndarray, names: list[str], ref: dict[str, Any]
) -> dict[str, Any]:
    stats = arviz_stats(draws)
    z = (stats["mean"] - ref["mean"]) / np.sqrt(stats["mcse"] ** 2 + ref["mcse"] ** 2)
    practical = np.abs(stats["mean"] - ref["mean"]) / ref["sd"]
    parameters = {}
    decisive = []
    nonfinite_required = []
    for index, name in enumerate(names):
        required_values = (
            stats["mean"][index],
            stats["sd"][index],
            stats["mcse"][index],
            stats["bulk_ess"][index],
            stats["tail_ess"][index],
            stats["rhat"][index],
            ref["mean"][index],
            ref["sd"][index],
            ref["mcse"][index],
            z[index],
            practical[index],
        )
        required_finite = all(math.isfinite(float(value)) for value in required_values)
        if not required_finite:
            nonfinite_required.append(name)
        row = {
            "mean": float(stats["mean"][index]) if math.isfinite(stats["mean"][index]) else None,
            "sd": float(stats["sd"][index]) if math.isfinite(stats["sd"][index]) else None,
            "mcse": float(stats["mcse"][index]) if math.isfinite(stats["mcse"][index]) else None,
            "bulk_ess": float(stats["bulk_ess"][index]) if math.isfinite(stats["bulk_ess"][index]) else None,
            "tail_ess": float(stats["tail_ess"][index]) if math.isfinite(stats["tail_ess"][index]) else None,
            "rank_folded_split_rhat": float(stats["rhat"][index]) if math.isfinite(stats["rhat"][index]) else None,
            "reference_mean": float(ref["mean"][index]) if math.isfinite(ref["mean"][index]) else None,
            "reference_sd": float(ref["sd"][index]) if math.isfinite(ref["sd"][index]) else None,
            "reference_mcse": float(ref["mcse"][index]) if math.isfinite(ref["mcse"][index]) else None,
            "z": float(z[index]) if math.isfinite(z[index]) else None,
            "abs_dmean_over_reference_sd": float(practical[index]) if math.isfinite(practical[index]) else None,
            "required_metrics_finite": required_finite,
        }
        row["decisive_reference_disagreement"] = bool(
            required_finite
            and decisive_reference_disagreement(
                row["z"], row["abs_dmean_over_reference_sd"]
            )
        )
        if row["decisive_reference_disagreement"]:
            decisive.append(name)
        parameters[name] = row
    all_required_finite = not nonfinite_required
    absolute_z = np.abs(z)
    max_z_index = int(np.argmax(absolute_z)) if all_required_finite else None
    max_d_index = int(np.argmax(practical)) if all_required_finite else None
    return {
        "stats": stats,
        "parameters": parameters,
        "required_metrics_finite": all_required_finite,
        "nonfinite_required_parameters": nonfinite_required,
        "min_bulk_ess": float(np.min(stats["bulk_ess"])) if all_required_finite else None,
        "min_tail_ess": float(np.min(stats["tail_ess"])) if all_required_finite else None,
        "max_rank_folded_split_rhat": float(np.max(stats["rhat"])) if all_required_finite else None,
        "max_abs_z": float(absolute_z[max_z_index]) if max_z_index is not None else None,
        "argmax_abs_z": names[max_z_index] if max_z_index is not None else None,
        "max_abs_dmean_over_reference_sd": float(practical[max_d_index]) if max_d_index is not None else None,
        "argmax_abs_dmean_over_reference_sd": names[max_d_index] if max_d_index is not None else None,
        "decisive_reference_disagreements": decisive,
    }


def decisive_reference_disagreement(z: float, practical_shift: float) -> bool:
    return bool(
        math.isfinite(z)
        and math.isfinite(practical_shift)
        and abs(z) > 4.0
        and practical_shift >= 0.10
    )


def diagnostic_pass(
    max_rhat: float | None,
    min_bulk: float | None,
    min_tail: float | None,
    divergences: int,
    finite: bool,
    sampler_error: bool,
    required_metrics_finite: bool = True,
) -> tuple[bool, dict[str, bool]]:
    gates = {
        "required_parameter_metrics_finite": required_metrics_finite,
        "max_rank_folded_split_rhat": finite_number(max_rhat) and max_rhat <= 1.01,
        "min_bulk_ess": finite_number(min_bulk) and min_bulk >= 400,
        "min_tail_ess": finite_number(min_tail) and min_tail >= 400,
        "zero_retained_divergences": divergences == 0,
        "finite_draws": finite,
        "no_sampler_error": not sampler_error,
    }
    return all(gates.values()), gates


def action_summary(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("actions") is None:
        return {
            "restart_actions": None,
            "restarted_chain_indices": None,
            "unique_restarted_chains": None,
            "actions_by_criterion": None,
            "actions": None,
            "telemetry_unknown": True,
        }
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
        "telemetry_unknown": False,
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
        "sampler_error_stage": raw.get("stage"),
        "rescue_history": raw.get("rescue_history"),
        "initial_position_sha256": raw.get("initial_position_sha256", []),
        "wall_seconds": raw.get("wall_seconds"),
        "target_calls_total": raw.get("target_calls_total"),
        "raw_output_sha256": process["raw_output_sha256"],
        "unknown_run_error_safety_failure": (
            raw.get("status") == "sampler_error" and raw.get("stage") == "run"
        ),
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
            "unknown_run_error_safety_failure": raw.get("stage") == "run",
        }
    )
    return cell


def transform_posteriordb(
    target: str, unconstrained: np.ndarray, names: list[str]
) -> tuple[np.ndarray, list[str], list[str], np.ndarray]:
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
    unconstrained_names = list(model.param_unc_names())
    if len(unconstrained_names) != unconstrained.shape[-1]:
        raise RuntimeError("BridgeStan unconstrained names do not match draw dimension")
    index = {name: position for position, name in enumerate(constrained_names)}
    missing = [name for name in names if name not in index]
    if missing:
        raise RuntimeError(f"reference parameters missing after constrain: {missing[:5]}")
    constrained = np.empty(
        unconstrained.shape[:2] + (len(constrained_names),), dtype=np.float64
    )
    columns = [index[name] for name in names]
    for chain in range(unconstrained.shape[0]):
        for draw in range(unconstrained.shape[1]):
            full = model.param_constrain(
                unconstrained[chain, draw], include_tp=True, include_gq=False
            )
            constrained[chain, draw] = np.asarray(full, dtype=np.float64)
    return constrained, constrained_names, unconstrained_names, constrained[:, :, columns]


def posteriordb_cell(
    raw: dict[str, Any], process: dict[str, Any], ref: dict[str, Any]
) -> dict[str, Any]:
    if raw["status"] != "ok":
        return sampler_error_cell(raw, process)
    unconstrained = np.asarray(
        [chain["samples"] for chain in raw["chains_data"]], dtype=np.float64
    )
    (
        constrained,
        constrained_names,
        unconstrained_names,
        reference_draws,
    ) = transform_posteriordb(raw["target"], unconstrained, ref["names"])
    metrics = reference_metrics(reference_draws, ref["names"], ref)
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
        metrics["required_metrics_finite"],
    )
    calls = int(raw["target_calls_total"])
    efficiency = (
        min(metrics["min_bulk_ess"], metrics["min_tail_ess"]) / calls
        if metrics["required_metrics_finite"] and calls > 0
        else None
    )
    origins = bind_origin_initial_hashes(
        stable_separated_origins(
            reference_draws, ref["names"], ref["median"], ref["iqr"]
        ),
        raw["initial_position_sha256"],
    )
    draw_path = DRAWS / f"{cell_id(raw['target'], raw['arm'], raw['seed'])}.npz"
    draw_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        draw_path,
        unconstrained=unconstrained,
        constrained=constrained,
        unconstrained_names=np.asarray(unconstrained_names),
        constrained_names=np.asarray(constrained_names),
        reference_draws=reference_draws,
        reference_names=np.asarray(ref["names"]),
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
            "required_metrics_finite": metrics["required_metrics_finite"],
            "nonfinite_required_parameters": metrics["nonfinite_required_parameters"],
            "parameters": metrics["parameters"],
            "diagnostic_gates": gates,
            "raw_diagnostic_pass": raw_pass,
            "credited_diagnostic_pass": raw_pass,
            "origin_overwritten": False,
            "stable_separated_origins": origins if raw["arm"] == "observe" else None,
            "efficiency": efficiency,
            "unconstrained_sha256": array_sha256(unconstrained),
            "constrained_sha256": array_sha256(constrained),
            "unconstrained_shape": list(unconstrained.shape),
            "constrained_shape": list(constrained.shape),
            "unconstrained_names": unconstrained_names,
            "unconstrained_names_sha256": names_sha256(unconstrained_names),
            "constrained_names": constrained_names,
            "constrained_names_sha256": names_sha256(constrained_names),
            "reference_draws_sha256": array_sha256(reference_draws),
            "reference_names": ref["names"],
            "reference_names_sha256": names_sha256(ref["names"]),
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
        cell["funnel_full_gate_parts"] = {
            field: False for field in FUNNEL_FULL_GATE_FIELDS
        }
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
    z = (estimate - 0.0478) / mcse if math.isfinite(mcse) and mcse > 0 else None
    finite = bool(np.isfinite(unconstrained).all())
    omega_full_gate_metrics_finite = all(
        math.isfinite(float(value))
        for value in (
            stats["bulk_ess"][0],
            stats["rhat"][0],
        )
    )
    tail_metrics_finite = (
        math.isfinite(float(stats["tail_ess"][0]))
        and math.isfinite(mcse)
        and z is not None
        and math.isfinite(z)
    )
    divergences = sum(
        int(chain["retained_diagnostics"]["divergences"])
        for chain in raw["chains_data"]
    )
    full_gate_parts = dict(
        zip(
            FUNNEL_FULL_GATE_FIELDS,
            (
                omega_full_gate_metrics_finite and float(stats["rhat"][0]) <= 1.01,
                omega_full_gate_metrics_finite and float(stats["bulk_ess"][0]) >= 400,
                divergences == 0,
                finite,
                True,
            ),
            strict=True,
        )
    )
    analytic_iqr = 6.0 * 0.6744897501960817
    origins = bind_origin_initial_hashes(
        stable_separated_origins(
            omega,
            ["omega"],
            np.asarray([0.0]),
            np.asarray([analytic_iqr]),
        ),
        raw["initial_position_sha256"],
    )
    draw_path = DRAWS / f"{cell_id(raw['target'], raw['arm'], raw['seed'])}.npz"
    draw_path.parent.mkdir(parents=True, exist_ok=True)
    funnel_names = ["omega"] + [f"x[{index}]" for index in range(1, 10)]
    np.savez_compressed(
        draw_path,
        unconstrained=unconstrained,
        constrained=unconstrained,
        unconstrained_names=np.asarray(funnel_names),
        constrained_names=np.asarray(funnel_names),
        omega=omega,
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
            "tail_mass": {"estimate": estimate, "mcse": mcse if math.isfinite(mcse) else None, "z": z, "exact": 0.0478},
            "omega_bulk_ess": float(stats["bulk_ess"][0]) if math.isfinite(stats["bulk_ess"][0]) else None,
            "omega_tail_ess": float(stats["tail_ess"][0]) if math.isfinite(stats["tail_ess"][0]) else None,
            "omega_rank_folded_split_rhat": float(stats["rhat"][0]) if math.isfinite(stats["rhat"][0]) else None,
            "omega_full_gate_metrics_finite": omega_full_gate_metrics_finite,
            "tail_metrics_finite": tail_metrics_finite,
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
            "constrained_sha256": array_sha256(unconstrained),
            "unconstrained_shape": list(unconstrained.shape),
            "constrained_shape": list(unconstrained.shape),
            "unconstrained_names": funnel_names,
            "constrained_names": funnel_names,
            "unconstrained_names_sha256": names_sha256(funnel_names),
            "constrained_names_sha256": names_sha256(funnel_names),
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
        tuple(cell.get("unconstrained_shape") or []),
        tuple(cell.get("constrained_shape") or []),
        cell.get("unconstrained_names_sha256"),
        cell.get("constrained_names_sha256"),
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
        expected_marker = LAUNCHES / f"{value.get('cell_id')}.json"
        marker_errors = validate_process_marker(value, expected_marker)
        if marker_errors:
            value["process_valid"] = False
            value["fault"] = True
            value["status"] = "process_fault"
            value.setdefault("failure_reasons", []).extend(marker_errors)
        records[(value["target"], int(value["seed"]), value["arm"])] = value
    return records


def process_fault_cell(
    target: str, seed: int, arm: str, process: dict[str, Any] | None
) -> dict[str, Any]:
    if process is None:
        return {
            "schema": "chain-rescue-v2-cell-report",
            "target": target,
            "seed": seed,
            "arm": arm,
            "process_valid": False,
            "process_status": "missing_process_record",
            "sampler_status": "process_fault",
            "failure_reasons": ["process record is missing"],
            "return_code": None,
            "last_heartbeat": None,
            "raw_output_exists": False,
        }
    timed_out = process.get("timed_out") is True
    return {
        "schema": "chain-rescue-v2-cell-report",
        "target": target,
        "seed": seed,
        "arm": arm,
        "process_valid": False,
        "process_record": process.get("cell_id"),
        "process_status": "timeout" if timed_out else "process_fault",
        "sampler_status": "timeout" if timed_out else "process_fault",
        "timed_out": timed_out,
        "duration_seconds": process.get("duration_seconds"),
        "failure_reasons": process.get("failure_reasons", []),
        "return_code": process.get("return_code"),
        "last_heartbeat": process.get("last_heartbeat"),
        "raw_output_exists": process.get("raw_output_exists", False),
        "raw_output_status": process.get("raw_output_status"),
        "raw_output_sha256": process.get("raw_output_sha256"),
    }


def process_accounting(
    processes: dict[tuple[str, int, str], dict[str, Any]]
) -> dict[str, Any]:
    faults = [process for process in processes.values() if not process.get("process_valid")]
    return {
        "launch_markers": len(list(LAUNCHES.glob("*.json"))),
        "process_records": len(processes),
        "process_valid": len(processes) - len(faults),
        "process_faults": len(faults),
        "heap_corruption_0xC0000374": sum(
            process.get("return_code", {}).get("hex_32") == "0xC0000374"
            for process in faults
        ),
        "timeouts": sum(process.get("timed_out") is True for process in faults),
        "post_result_drop_timeouts": sum(
            process.get("timed_out") is True
            and process.get("raw_output_exists") is True
            and process.get("last_heartbeat", {}).get("stage") == "drop"
            and process.get("last_heartbeat", {}).get("boundary") == "before"
            for process in faults
        ),
        "fault_cells": [
            process_fault_cell(
                process["target"], int(process["seed"]), process["arm"], process
            )
            for process in faults
        ],
    }


def validate_process_marker(
    process: dict[str, Any], marker: Path
) -> list[str]:
    if not marker.is_file():
        return ["process record exists without required launch marker"]
    if process.get("launch_marker_sha256") != sha256(marker):
        return ["launch marker hash does not authenticate against process record"]
    try:
        launch = json.loads(marker.read_text(encoding="utf-8"))
    except Exception as error:
        return [f"launch marker is malformed: {error}"]
    expected = {
        "schema": "chain-rescue-v2-launch",
        "cell_id": process.get("cell_id"),
        "target": process.get("target"),
        "seed": process.get("seed"),
        "arm": process.get("arm"),
        "command": process.get("command"),
    }
    if any(launch.get(name) != value for name, value in expected.items()):
        return ["launch marker contents do not match process record"]
    return []


def authenticate_raw(
    process: dict[str, Any], target: str, arm: str, seed: int
) -> dict[str, Any]:
    path = HERE / process["raw_output_path"]
    if not path.is_file():
        raise RuntimeError("authenticated raw file is missing")
    if path.stat().st_size != process.get("raw_output_bytes"):
        raise RuntimeError("raw file size differs from process record")
    actual_hash = sha256(path)
    if actual_hash != process.get("raw_output_sha256"):
        raise RuntimeError("raw file SHA-256 differs from process record")
    raw = json.loads(path.read_text(encoding="utf-8"))
    valid, errors = validate_raw(raw, target, arm, seed)
    if not valid:
        raise RuntimeError("strict raw validation failed: " + "; ".join(errors))
    return raw


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
                    hashes.append(
                        tuple(record.get("authenticated_initial_position_sha256", []))
                    )
            if len(hashes) == 3 and not all(value == hashes[0] for value in hashes[1:]):
                failures.append("initial-position hashes differ by arm")
            if len(hashes) == 3 and len(hashes[0]) != 4:
                failures.append("paired cells do not expose four initial-position hashes")
            valid[(target, seed)] = not failures
            reasons[(target, seed)] = failures
    return valid, reasons


def classify_origin_actions(
    cell: dict[str, Any], observe: dict[str, Any] | None
) -> dict[str, Any]:
    actions = cell.get("actions") or []
    origin_data = (
        observe.get("stable_separated_origins")
        if observe is not None
        else None
    )
    details = origin_data.get("by_chain") if isinstance(origin_data, dict) else None
    origin_chains = set(origin_data.get("chains", [])) if isinstance(origin_data, dict) else set()
    candidate_hashes = cell.get("initial_position_sha256") or []
    mappings = []
    for action_index, action in enumerate(actions):
        chain = int(action["chain"])
        row = {
            "action_index": action_index,
            "chain": chain,
            "candidate_initial_position_sha256": (
                candidate_hashes[chain] if chain < len(candidate_hashes) else None
            ),
            "observe_initial_position_sha256": None,
            "classification": "unknown",
            "reason": None,
        }
        observe_chain = details.get(str(chain)) if isinstance(details, dict) else None
        if observe_chain is None:
            row["reason"] = (
                "matching process-valid observe origin metadata is unavailable"
            )
        else:
            row["observe_initial_position_sha256"] = observe_chain.get(
                "initial_position_sha256"
            )
            if (
                row["candidate_initial_position_sha256"] is None
                or row["candidate_initial_position_sha256"]
                != row["observe_initial_position_sha256"]
            ):
                row["reason"] = "action-chain initial-position hash mismatch"
            elif chain in origin_chains:
                row["classification"] = "origin_overwritten"
            else:
                row["classification"] = "mapped_non_origin"
        mappings.append(row)
    overwrite_events = [
        actions[row["action_index"]]
        for row in mappings
        if row["classification"] == "origin_overwritten"
    ]
    unknown = [row for row in mappings if row["classification"] == "unknown"]
    mapped_origin_chains = sorted(
        chain
        for chain in origin_chains
        if (
            isinstance(details, dict)
            and details.get(str(chain), {}).get("initial_position_sha256")
            == (candidate_hashes[chain] if chain < len(candidate_hashes) else None)
        )
    )
    return {
        "origin_action_mappings": mappings,
        "origin_mapping_complete": not unknown,
        "origin_safety_unknown": bool(unknown),
        "origin_safety_unknown_actions": unknown,
        "origin_safety_unknown_event_count": len(unknown),
        "mapped_stable_separated_origin_chains": mapped_origin_chains,
        "origin_overwritten": bool(overwrite_events),
        "origin_overwrite_events": overwrite_events,
        "origin_overwrite_event_count": len(overwrite_events),
        "origin_overwritten_chain_indices": sorted(
            {int(action["chain"]) for action in overwrite_events}
        ),
        "origin_overwritten_unique_chains": len(
            {int(action["chain"]) for action in overwrite_events}
        ),
    }


def credited_pass_after_origin_mapping(
    raw_diagnostic_pass: bool, origin_result: dict[str, Any]
) -> bool:
    return bool(raw_diagnostic_pass and not origin_result["origin_overwritten"])


def apply_origin_credit_and_identity(
    cells: dict[tuple[str, int, str], dict[str, Any]],
    triplet_valid: dict[tuple[str, int], bool],
) -> None:
    for target in TARGETS:
        for seed in SEEDS:
            observe = cells.get((target, seed, "observe"))
            for arm in ARMS:
                cell = cells.get((target, seed, arm))
                if cell is None:
                    continue
                origin_result = classify_origin_actions(
                    cell, observe if arm in {"current", "two_hit"} else cell
                )
                cell.update(origin_result)
                cell["credited_diagnostic_pass"] = credited_pass_after_origin_mapping(
                    bool(cell.get("raw_diagnostic_pass")), origin_result
                )
                if (
                    triplet_valid[(target, seed)]
                    and arm in {"current", "two_hit"}
                    and cell.get("restart_actions") == 0
                    and observe is not None
                ):
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


def all_process_safety_findings(
    cells: Iterable[dict[str, Any]], arm: str
) -> dict[str, list[str]]:
    arm_cells = [cell for cell in cells if cell.get("arm") == arm]
    return {
        "origin_overwritten": [
            f"{cell['target']}/{cell['seed']}"
            for cell in arm_cells
            if cell.get("origin_overwritten")
        ],
        "origin_safety_unknown": [
            f"{cell['target']}/{cell['seed']}"
            for cell in arm_cells
            if cell.get("origin_safety_unknown")
        ],
        "reference": [
            f"{cell['target']}/{cell['seed']}/{name}"
            for cell in arm_cells
            for name in cell.get("decisive_reference_disagreements", [])
        ],
        "unknown_run_error": [
            f"{cell['target']}/{cell['seed']}"
            for cell in arm_cells
            if cell.get("unknown_run_error_safety_failure")
        ],
        "funnel": [
            f"funnel-10d/{cell['seed']}"
            for cell in arm_cells
            if cell.get("target") == "funnel-10d"
            and (
                cell.get("sampler_status") != "ok"
                or not cell.get("finite_draws", False)
                or cell.get("tail_mass") is None
                or not finite_number(cell["tail_mass"].get("z"))
                or abs(cell["tail_mass"]["z"]) > 3.0
            )
        ],
    }


def current_red_line_report(
    findings: dict[str, list[str]],
    no_fire_failures: list[str],
    observe_mutations: list[str],
) -> dict[str, list[str]]:
    return {
        "origin_overwritten": findings["origin_overwritten"],
        "reference": findings["reference"],
        "funnel": findings["funnel"],
        "unknown_run_error": findings["unknown_run_error"],
        "no_fire": no_fire_failures + observe_mutations,
    }


def candidate_origin_safety_pass(findings: dict[str, list[str]]) -> bool:
    return not findings["origin_overwritten"] and not findings[
        "origin_safety_unknown"
    ]


def prediction_p3_held(
    observe_origin_chain_occurrences: int,
    current: dict[str, Any],
    two_hit: dict[str, Any],
) -> bool:
    return bool(
        observe_origin_chain_occurrences > 0
        and current["unique_chain_occurrences"] > 0
        and two_hit["unique_chain_occurrences"] > 0
        and two_hit["unique_chain_occurrences"] < current["unique_chain_occurrences"]
        and two_hit["events"] <= current["events"]
    )


def prediction_p4_held(
    two_hit_decisive: list[str],
    current_decisive: list[str],
    raw_over_4_small_shift: list[str],
) -> bool:
    return bool(
        not two_hit_decisive
        and not current_decisive
        and raw_over_4_small_shift
    )


def prediction_p6_held(
    mesquite_two_hit_zero_actions: int,
    mesquite_two_hit_identity_failures: list[str],
) -> bool:
    return bool(
        mesquite_two_hit_zero_actions >= 10
        and not mesquite_two_hit_identity_failures
    )


def adjudicate_prediction_holds(
    nuisance: bool,
    efficacy: bool,
    p3: bool,
    p4: bool,
    funnel: bool,
    p6: bool,
    efficiency: bool,
    decision: str,
) -> dict[str, bool]:
    return {
        "P1": nuisance,
        "P2": efficacy,
        "P3": p3,
        "P4": p4,
        "P5": funnel,
        "P6": p6,
        "P7": efficiency,
        "P8": decision == "no_rescue",
    }


def evaluate_funnel_gate(
    cells: dict[tuple[str, int, str], dict[str, Any]],
    triplet_valid: dict[tuple[str, int], bool],
    seeds: Iterable[int],
) -> dict[str, Any]:
    seeds = list(seeds)
    candidate_cells = [
        cells[("funnel-10d", seed, "two_hit")]
        for seed in seeds
        if ("funnel-10d", seed, "two_hit") in cells
    ]
    tail_failures = [
        cell["seed"]
        for cell in candidate_cells
        if (
            cell.get("tail_mass") is None
            or not finite_number(cell["tail_mass"].get("z"))
            or abs(cell["tail_mass"]["z"]) > 2.0
        )
    ]
    candidate_full_gate_count = sum(
        cell.get("funnel_full_gate") is True for cell in candidate_cells
    )
    candidate_half_required = math.ceil(len(candidate_cells) / 2)
    paired_seeds = [
        seed for seed in seeds if triplet_valid.get(("funnel-10d", seed), False)
    ]
    paired_counts = {
        arm: sum(
            cells[("funnel-10d", seed, arm)].get("funnel_full_gate") is True
            for seed in paired_seeds
        )
        for arm in ARMS
    }
    paired_count_comparison = all(
        paired_counts["two_hit"] >= paired_counts[arm] - 1
        for arm in ("observe", "current")
    )
    return {
        "passed": (
            len(paired_seeds) >= 10
            and bool(candidate_cells)
            and not tail_failures
            and candidate_full_gate_count >= candidate_half_required
            and paired_count_comparison
        ),
        "candidate_process_valid_seeds": [cell["seed"] for cell in candidate_cells],
        "candidate_tail_z_failures": tail_failures,
        "candidate_all_abs_z_le_2": bool(candidate_cells) and not tail_failures,
        "candidate_full_gate_count": candidate_full_gate_count,
        "candidate_half_required": candidate_half_required,
        "paired_valid_seeds": paired_seeds,
        "paired_full_gate_counts": paired_counts,
        "paired_count_comparison": paired_count_comparison,
    }


def fixed_post_run_audit(summary: dict[str, Any]) -> dict[str, Any]:
    expected_predictions = {
        "P1": False,
        "P2": False,
        "P3": False,
        "P4": False,
        "P5": False,
        "P6": True,
        "P7": False,
        "P8": True,
    }
    expected_valid = {
        "bball_drive_event_0-hmm_drive_0": 10,
        "kidiq-kidscore_momhsiq": 12,
        "earnings-logearn_interaction": 12,
        "diamonds-diamonds": 9,
        "arma-arma11": 12,
        "hudson_lynx_hare-lotka_volterra": 12,
        "mesquite-logmesquite_logvash": 11,
        "funnel-10d": 12,
    }
    observed_predictions = {
        name: value["held"] for name, value in summary["predictions"].items()
    }
    checks = {
        "process_counts": {
            key: summary["process_accounting"][key]
            for key in (
                "launch_markers",
                "process_records",
                "process_valid",
                "process_faults",
                "heap_corruption_0xC0000374",
                "timeouts",
                "post_result_drop_timeouts",
            )
        }
        == {
            "launch_markers": 288,
            "process_records": 288,
            "process_valid": 281,
            "process_faults": 7,
            "heap_corruption_0xC0000374": 6,
            "timeouts": 1,
            "post_result_drop_timeouts": 1,
        },
        "valid_triplets": summary["decision_gates"]["completeness"][
            "valid_triplets_by_target"
        ]
        == expected_valid,
        "invalid_triplet_count": len(summary["invalid_triplets"]) == 6,
        "predictions": observed_predictions == expected_predictions,
        "mechanical_decision": summary["mechanical_decision"] == "no_rescue",
        "paired_gate_totals": summary["paired_standard_gate_totals"]
        == {
            "observe": {"raw": 71, "credited": 71},
            "current": {"raw": 74, "credited": 71},
            "two_hit": {"raw": 76, "credited": 72},
        },
        "action_origin_totals": summary["action_origin_totals"]
        == {
            "current": {
                "restart_events": 117,
                "origin_overwrite_events": 5,
                "origin_safety_unknown_events": 2,
            },
            "two_hit": {
                "restart_events": 58,
                "origin_overwrite_events": 5,
                "origin_safety_unknown_events": 2,
            },
        },
        "nuisance": (
            summary["decision_gates"]["nuisance_action_reduction"][
                "current_actions"
            ]
            == 35
            and summary["decision_gates"]["nuisance_action_reduction"][
                "two_hit_actions"
            ]
            == 14
            and summary["decision_gates"]["nuisance_action_reduction"]["sign_test"][
                "wins"
            ]
            == 8
            and summary["decision_gates"]["nuisance_action_reduction"]["sign_test"][
                "losses"
            ]
            == 1
            and summary["decision_gates"]["nuisance_action_reduction"]["sign_test"][
                "complete_blocks"
            ]
            == 9
            and math.isclose(
                summary["decision_gates"]["nuisance_action_reduction"]["sign_test"][
                    "one_sided_exact_p"
                ],
                0.01953125,
            )
        ),
        "efficacy": (
            summary["decision_gates"]["efficacy"]["sign_test"]["wins"] == 1
            and summary["decision_gates"]["efficacy"]["sign_test"]["losses"] == 0
            and summary["decision_gates"]["efficacy"]["sign_test"]["ties"] == 9
            and math.isclose(
                summary["decision_gates"]["efficacy"]["sign_test"][
                    "one_sided_exact_p"
                ],
                0.5,
            )
        ),
        "funnel": (
            summary["decision_gates"]["funnel"]["candidate_full_gate_count"] == 4
            and summary["decision_gates"]["funnel"]["candidate_half_required"] == 6
            and summary["decision_gates"]["funnel"]["candidate_tail_z_failures"]
            == [92107, 92111, 92112]
            and summary["decision_gates"]["funnel"]["gross_red_lines"]
            == ["funnel-10d/92111"]
        ),
        "no_fire": summary["decision_gates"]["no_fire"]["passed"] is True,
        "efficiency": (
            summary["decision_gates"]["efficiency"]["available_case_ratio_count"]
            == 77
            and math.isclose(
                summary["decision_gates"]["efficiency"][
                    "available_case_geometric_mean_ratio"
                ],
                0.8931682041554473,
            )
            and summary["decision_gates"]["efficiency"]["passed"] is False
        ),
        "origin_classifier_scope": (
            summary["stable_origin_classifier"]["hmm_origin_count"] == 0
            and summary["stable_origin_classifier"]["targets_with_origins"]
            == [
                "arma-arma11",
                "hudson_lynx_hare-lotka_volterra",
            ]
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "expected_predictions": expected_predictions,
        "observed_predictions": observed_predictions,
    }


def write_results_tables(summary: dict[str, Any]) -> None:
    cells = summary["cells"]
    lines = [
        "# chain_rescue_v2 — complete WP36 results",
        "",
        f"Mechanical decision: **{summary['mechanical_decision']}**.",
        (
            f"Process accounting: {summary['process_accounting']['launch_markers']}/288 "
            f"launches, {summary['process_accounting']['process_records']}/288 process "
            f"records, {summary['process_accounting']['process_valid']} process-valid, "
            f"{summary['process_accounting']['process_faults']} faults."
        ),
        (
            "Available-case efficiency: "
            f"{summary['decision_gates']['efficiency']['available_case_geometric_mean_ratio']:.6f} "
            f"over {summary['decision_gates']['efficiency']['available_case_ratio_count']} "
            "ratios; the registered full efficiency gate failed."
        ),
        (
            "Stable-origin limitation: "
            f"{summary['stable_origin_classifier']['substantive_limitation']}"
        ),
        "",
        "## Every planned cell",
        "",
        "| target | seed | arm | process | fault detail | triplet | sampler | raw gate | credited gate | actions | origin overwritten | max R-hat | min/omega bulk/tail ESS | reference max abs(z) / funnel signed tail z | decisive | efficiency | no-fire identity |",
        "|---|---:|---|---|---|---|---|---|---|---:|---|---:|---|---|---|---:|---|",
    ]
    for target, seed, arm in planned_cells():
        cell = cells.get(target, {}).get(str(seed), {}).get(arm)
        if not cell:
            lines.append(
                f"| {target} | {seed} | {arm} | process_fault | no report cell | false | process_fault | — | — | — | — | — | — | — | — | — | — |"
            )
            continue
        triplet = summary["triplets"][target][str(seed)]["valid"]
        process_status = (
            "ok" if cell.get("process_valid") else cell.get("process_status", "process_fault")
        )
        if cell.get("process_valid"):
            fault_detail = "—"
        else:
            return_code = (cell.get("return_code") or {}).get("hex_32") or "none"
            heartbeat = cell.get("last_heartbeat") or {}
            heartbeat_label = (
                f"{heartbeat.get('stage', 'none')}/{heartbeat.get('boundary', 'none')}"
            )
            raw_label = "present" if cell.get("raw_output_exists") else "absent"
            duration = cell.get("duration_seconds")
            duration_label = f"{duration:.3f}s" if finite_number(duration) else "—"
            fault_detail = (
                f"code={return_code}; last={heartbeat_label}; raw={raw_label}; "
                f"duration={duration_label}"
            )
        bulk = cell.get("min_bulk_ess", cell.get("omega_bulk_ess", "—"))
        tail = cell.get("min_tail_ess", cell.get("omega_tail_ess", "—"))
        if target == "funnel-10d":
            z_display = f"signed tail z={(cell.get('tail_mass') or {}).get('z', '—')}"
        else:
            z_display = f"max abs(z)={cell.get('max_abs_z', '—')}"
        lines.append(
            f"| {target} | {seed} | {arm} | {process_status} | {fault_detail} | {triplet} | "
            f"{cell.get('sampler_status')} | {cell.get('raw_diagnostic_pass')} | "
            f"{cell.get('credited_diagnostic_pass')} | {cell.get('restart_actions')} | "
            f"{cell.get('origin_overwritten')} | {cell.get('max_rank_folded_split_rhat', cell.get('omega_rank_folded_split_rhat', '—'))} | "
            f"{bulk} / {tail} | {z_display} | "
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
            "## Registered red lines",
            "",
            f"`{json.dumps(summary['registered_red_lines'], sort_keys=True)}`",
        ]
    )
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
    def number(value: Any, spec: str) -> str:
        return "—" if value is None or not finite_number(value) else format(value, spec)

    for target in MODELS:
        for seed in SEEDS:
            for arm in ARMS:
                cell = cells.get(target, {}).get(str(seed), {}).get(arm, {})
                for name, row in cell.get("parameters", {}).items():
                    parameter_lines.append(
                        f"| {target} | {seed} | {arm} | {name} | {number(row['mean'], '.9g')} | "
                        f"{number(row['mcse'], '.9g')} | {number(row['bulk_ess'], '.7g')} | "
                        f"{number(row['tail_ess'], '.7g')} | "
                        f"{number(row['rank_folded_split_rhat'], '.7g')} | "
                        f"{number(row['reference_mean'], '.9g')} / "
                        f"{number(row['reference_sd'], '.9g')} / "
                        f"{number(row['reference_mcse'], '.9g')} | "
                        f"{number(row['z'], '.7g')} | "
                        f"{number(row['abs_dmean_over_reference_sd'], '.7g')} | "
                        f"{row['decisive_reference_disagreement']} |"
                    )
    atomic_write_text(
        ARTIFACTS / "parameters-table.md", "\n".join(parameter_lines) + "\n"
    )


def analyze() -> dict[str, Any]:
    environment = validate_environment(require_binaries=True, require_conformance=True)
    processes = load_processes()
    authenticated_raw: dict[tuple[str, int, str], dict[str, Any]] = {}
    for key, process in processes.items():
        if not process.get("process_valid"):
            continue
        target, seed, arm = key
        try:
            authenticated_raw[key] = authenticate_raw(process, target, arm, seed)
            process["raw_authenticated"] = True
            process["authenticated_initial_position_sha256"] = authenticated_raw[key].get(
                "initial_position_sha256", []
            )
        except Exception as error:
            process["process_valid"] = False
            process["fault"] = True
            process["status"] = "process_fault"
            process["raw_authenticated"] = False
            process.setdefault("failure_reasons", []).append(str(error))
    triplet_valid, triplet_reasons = classify_triplets(processes)
    refs: dict[str, dict[str, Any]] = {}
    flat_cells: dict[tuple[str, int, str], dict[str, Any]] = {}
    for target, seed, arm in planned_cells():
        process = processes.get((target, seed, arm))
        if not process or not process.get("process_valid"):
            continue
        raw = authenticated_raw[(target, seed, arm)]
        if target == "funnel-10d":
            cell = funnel_cell(raw, process)
        else:
            if target not in refs:
                refs[target] = reference(target)
            cell = posteriordb_cell(raw, process, refs[target])
        flat_cells[(target, seed, arm)] = cell
        write_json(cell_path(target, arm, seed), cell)
    for target, seed, arm in planned_cells():
        if (target, seed, arm) not in flat_cells:
            write_json(
                cell_path(target, arm, seed),
                process_fault_cell(
                    target, seed, arm, processes.get((target, seed, arm))
                ),
            )
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
        and all(
            flat_cells[(target, seed, arm)].get("unique_restarted_chains")
            is not None
            for target in nuisance_models
            for arm in ARMS
        )
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
                int(flat_cells[(target, seed, arm)].get("unique_restarted_chains", 0))
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

    process_records_complete = all(
        (target, seed, arm) in processes for target, seed, arm in planned_cells()
    )
    launch_markers_complete = all(
        (LAUNCHES / f"{cell_id(target, arm, seed)}.json").is_file()
        for target, seed, arm in planned_cells()
    )
    launch_complete = process_records_complete and launch_markers_complete
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
        if (target, seed, "two_hit") in flat_cells
    ]
    two_findings = all_process_safety_findings(two_cells, "two_hit")
    two_origin = two_findings["origin_overwritten"]
    two_origin_unknown = two_findings["origin_safety_unknown"]
    two_decisive = two_findings["reference"]
    two_legacy = [
        f"{cell['target']}/{cell['seed']}"
        for cell in two_cells
        if cell.get("credited_diagnostic_pass") and cell.get("max_abs_z", 0) > 4.0
    ]
    two_unknown_run_errors = two_findings["unknown_run_error"]
    two_funnel_redlines = two_findings["funnel"]
    safety = (
        candidate_origin_safety_pass(two_findings)
        and not two_decisive
        and not two_legacy
        and not two_unknown_run_errors
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

    funnel_evaluation = evaluate_funnel_gate(flat_cells, triplet_valid, SEEDS)
    funnel_evaluation["gross_red_lines"] = two_funnel_redlines
    funnel_gate = funnel_evaluation["passed"]

    conformance_pass = environment["conformance"]["authenticated"]
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
        and flat_cells[(target, seed, "observe")].get("restart_actions") not in {0, None}
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
    efficiency_ratio_count = sum(len(values) for values in efficiency_ratios.values())
    efficiency_model_floor_failures = {
        target: value
        for target, value in efficiency_medians.items()
        if value is None or value < 0.90
    }
    efficiency = (
        not efficiency_bad
        and not efficiency_model_floor_failures
        and efficiency_geomean is not None
        and efficiency_geomean >= 0.95
    )

    gates = {
        "completeness": {
            "passed": completeness,
            "all_288_launch_records": launch_complete,
            "all_288_launch_markers": launch_markers_complete,
            "all_288_process_records": process_records_complete,
            "valid_triplets_by_target": valid_by_target,
        },
        "safety": {
            "passed": safety,
            "origin_overwritten": two_origin,
            "origin_safety_unknown": two_origin_unknown,
            "decisive_reference_disagreements": two_decisive,
            "legacy_reference_gate_violations": two_legacy,
            "unknown_run_errors": two_unknown_run_errors,
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
            **funnel_evaluation,
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
            "model_floor_failures": efficiency_model_floor_failures,
            "available_case_ratio_count": efficiency_ratio_count,
            "available_case_geometric_mean_ratio": efficiency_geomean,
            "registered_full_gate_requires_all_ratios": True,
        },
    }

    current_cells = [
        flat_cells[(target, seed, "current")]
        for target in TARGETS
        for seed in SEEDS
        if (target, seed, "current") in flat_cells
    ]
    current_findings = all_process_safety_findings(current_cells, "current")
    current_no_fire_failures = [
        item for item in no_fire_failures if item.endswith("/current")
    ]
    current_red_lines = current_red_line_report(
        current_findings, current_no_fire_failures, observe_mutations
    )
    all_two_hit_gates = all(gate["passed"] for gate in gates.values())
    any_current_red_line = any(current_red_lines.values())
    decision = (
        "two_hit"
        if all_two_hit_gates
        else "no_rescue"
        if any_current_red_line
        else "current"
    )
    hmm = "bball_drive_event_0-hmm_drive_0"
    hmm_observe_origins = sum(
        len(
            (flat_cells.get((hmm, seed, "observe"), {}).get("stable_separated_origins") or {}).get(
                "chains", []
            )
        )
        for seed in SEEDS
    )
    hmm_overwrites = {}
    for arm in ("current", "two_hit"):
        arm_cells = [
            flat_cells[(hmm, seed, arm)]
            for seed in SEEDS
            if (hmm, seed, arm) in flat_cells
        ]
        hmm_overwrites[arm] = {
            "unique_chain_occurrences": sum(
                cell.get("origin_overwritten_unique_chains", 0) for cell in arm_cells
            ),
            "events": sum(
                cell.get("origin_overwrite_event_count", 0) for cell in arm_cells
            ),
            "cells": [
                cell["seed"] for cell in arm_cells if cell.get("origin_overwritten")
            ],
        }
    mutating_raw_over_4_small_shift = [
        f"{cell['target']}/{cell['seed']}/{cell['arm']}/{name}"
        for cell in [*current_cells, *two_cells]
        for name, parameter in cell.get("parameters", {}).items()
        if parameter.get("z") is not None
        and abs(parameter["z"]) > 4.0
        and parameter.get("abs_dmean_over_reference_sd") is not None
        and parameter["abs_dmean_over_reference_sd"] < 0.10
    ]
    mesquite_two_hit_identity_failures = [
        f"mesquite-logmesquite_logvash/{seed}/two_hit"
        for seed in SEEDS
        if triplet_valid[("mesquite-logmesquite_logvash", seed)]
        and flat_cells[("mesquite-logmesquite_logvash", seed, "two_hit")].get(
            "restart_actions"
        )
        == 0
        and flat_cells[("mesquite-logmesquite_logvash", seed, "two_hit")].get(
            "zero_action_identity_to_observe"
        )
        is not True
    ]
    p3_held = prediction_p3_held(
        hmm_observe_origins,
        hmm_overwrites["current"],
        hmm_overwrites["two_hit"],
    )
    p4_held = prediction_p4_held(
        two_decisive,
        current_red_lines["reference"],
        mutating_raw_over_4_small_shift,
    )
    p6_held = prediction_p6_held(
        mesquite_zero, mesquite_two_hit_identity_failures
    )
    prediction_holds = adjudicate_prediction_holds(
        nuisance,
        efficacy,
        p3_held,
        p4_held,
        funnel_gate,
        p6_held,
        efficiency_geomean is not None and efficiency_geomean >= 0.95,
        decision,
    )
    predictions = {
        "P1": {
            "held": prediction_holds["P1"],
            "value": {"ratio": nuisance_ratio, "sign_test": nuisance_sign},
        },
        "P2": {
            "held": prediction_holds["P2"],
            "value": {"sign_test": efficacy_sign, "losses": current_failure_losses},
        },
        "P3": {
            "held": prediction_holds["P3"],
            "value": {
                "observe_origin_chain_occurrences": hmm_observe_origins,
                "overwrites": hmm_overwrites,
            },
        },
        "P4": {
            "held": prediction_holds["P4"],
            "value": {
                "two_hit": two_decisive,
                "current": current_red_lines["reference"],
                "raw_abs_z_over_4_with_shift_below_0_10": mutating_raw_over_4_small_shift,
            },
        },
        "P5": {
            "held": prediction_holds["P5"],
            "value": gates["funnel"],
        },
        "P6": {
            "held": prediction_holds["P6"],
            "value": {
                "zero_action_cells": mesquite_zero,
                "identity_failures": mesquite_two_hit_identity_failures,
            },
        },
        "P7": {
            "held": prediction_holds["P7"],
            "value": {
                "available_case_geometric_mean_ratio": efficiency_geomean,
                "available_case_ratio_count": efficiency_ratio_count,
                "registered_full_efficiency_gate": efficiency,
                "missing_or_invalid_ratios": efficiency_bad,
                "model_floor_failures": efficiency_model_floor_failures,
            },
        },
        "P8": {
            "held": prediction_holds["P8"],
            "value": decision,
        },
    }
    paired_standard_gate_totals = {
        arm: {
            "raw": sum(
                bool(flat_cells[(target, seed, arm)].get("raw_diagnostic_pass"))
                for target in MODELS
                for seed in SEEDS
                if triplet_valid[(target, seed)]
            ),
            "credited": sum(pass_counts[target][arm] for target in MODELS),
        }
        for arm in ARMS
    }
    action_origin_totals = {
        arm: {
            "restart_events": sum(
                cell.get("restart_actions") or 0
                for cell in (current_cells if arm == "current" else two_cells)
            ),
            "origin_overwrite_events": sum(
                cell.get("origin_overwrite_event_count") or 0
                for cell in (current_cells if arm == "current" else two_cells)
            ),
            "origin_safety_unknown_events": sum(
                cell.get("origin_safety_unknown_event_count") or 0
                for cell in (current_cells if arm == "current" else two_cells)
            ),
        }
        for arm in ("current", "two_hit")
    }
    origin_classifier_observations = [
        {
            "target": target,
            "seed": seed,
            "chains": (
                flat_cells[(target, seed, "observe")]["stable_separated_origins"][
                    "chains"
                ]
            ),
        }
        for target in TARGETS
        for seed in SEEDS
        if (target, seed, "observe") in flat_cells
        and (
            flat_cells[(target, seed, "observe")].get("stable_separated_origins")
            or {}
        ).get("chains")
    ]
    nested_cells: dict[str, dict[str, dict[str, Any]]] = {}
    for target, seed, arm in planned_cells():
        cell = flat_cells.get((target, seed, arm))
        if cell is None:
            cell = process_fault_cell(
                target, seed, arm, processes.get((target, seed, arm))
            )
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
    input_manifest, build_manifest = provenance_paths()
    conformance_artifact = current_conformance_path()
    accounting = process_accounting(processes)
    invalid_triplets = [
        f"{target}/{seed}"
        for target in TARGETS
        for seed in SEEDS
        if not triplet_valid[(target, seed)]
    ]
    summary = {
        "schema": "chain-rescue-v2-summary",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "protocol_sha256": sha256(PROTOCOL_PATH),
        "amendment_1_sha256": sha256(AMENDMENT_1),
        "amendment_2_sha256": sha256(AMENDMENT_2),
        "amendment_3_sha256": sha256(AMENDMENT_3),
        "post_run_correction_sha256": sha256(POST_RUN_CORRECTION),
        "ledger_entry_sha256": sha256(LEDGER_ENTRY),
        "input_manifest_sha256": sha256(input_manifest),
        "build_manifest_sha256": sha256(build_manifest),
        "conformance_sha256": sha256(conformance_artifact),
        "mechanical_decision": decision,
        "process_accounting": accounting,
        "invalid_triplets": invalid_triplets,
        "paired_standard_gate_totals": paired_standard_gate_totals,
        "action_origin_totals": action_origin_totals,
        "stable_origin_classifier": {
            "observations": origin_classifier_observations,
            "targets_with_origins": sorted(
                {row["target"] for row in origin_classifier_observations}
            ),
            "hmm_origin_count": hmm_observe_origins,
            "substantive_limitation": (
                "The classifier identified only frozen/pathological ARMA and "
                "lotka_volterra starts and no HMM origins; this limits substantive "
                "interpretation but does not alter the frozen fallback."
            ),
        },
        "current_red_lines": current_red_lines,
        "registered_red_lines": {
            "two_hit": {
                "origin_overwritten": two_findings["origin_overwritten"],
                "reference": two_findings["reference"],
                "funnel": two_findings["funnel"],
                "unknown_run_error": two_findings["unknown_run_error"],
                "no_fire": no_fire_failures + observe_mutations,
            },
            "current": current_red_lines,
        },
        "origin_safety_findings": {
            "two_hit": {
                "origin_overwritten": two_findings["origin_overwritten"],
                "origin_safety_unknown": two_findings["origin_safety_unknown"],
            },
            "current": {
                "origin_overwritten": current_findings["origin_overwritten"],
                "origin_safety_unknown": current_findings["origin_safety_unknown"],
            },
        },
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
    summary["post_run_correction_audit"] = fixed_post_run_audit(summary)
    if not summary["post_run_correction_audit"]["passed"]:
        failed = [
            name
            for name, passed in summary["post_run_correction_audit"][
                "checks"
            ].items()
            if not passed
        ]
        raise RuntimeError(f"post-run correction audit failed: {failed}")
    write_json(ARTIFACTS / "summary.json", summary)
    write_results_tables(summary)
    print(f"mechanical decision: {decision}")
    return summary


def run_conformance() -> None:
    provenance = verify_provenance(require_binaries=True)
    if CONFORMANCE_INDEX.exists():
        raise RuntimeError(
            "committed conformance is immutable; create a new study/version to regenerate it"
        )
    _, build_manifest = provenance_paths()
    conformance = ARTIFACTS / "conformance" / (
        f"observe-vs-disabled-{provenance['source_commit'][:12]}.json"
    )
    if conformance.exists():
        raise RuntimeError(f"versioned conformance already exists: {conformance}")
    candidate = HERE / "target" / f"conformance-candidate-{os.getpid()}.json"
    if candidate.exists():
        raise RuntimeError(f"temporary conformance path already exists: {candidate}")
    try:
        completed = subprocess.run(
            [str(CONFORMANCE_BIN), str(candidate)],
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
        result = json.loads(candidate.read_text(encoding="utf-8"))
        comparison = result.get("comparison", {})
        if (
            result.get("status") != "pass"
            or comparison.get("bit_identical") is not True
            or comparison.get("observed_hit_path_exercised") is not True
            or int(result.get("observe_hits", 0)) <= 0
        ):
            raise RuntimeError("candidate conformance did not prove hit-path bit identity")
        result.update(
            {
                "protocol_sha256": sha256(PROTOCOL_PATH),
                "amendment_1_sha256": sha256(AMENDMENT_1),
                "amendment_2_sha256": sha256(AMENDMENT_2),
                "amendment_3_sha256": sha256(AMENDMENT_3),
                "input_manifest_sha256": provenance["input_manifest_sha256"],
                "build_manifest_sha256": provenance["build_manifest_sha256"],
                "conformance_executable": json.loads(
                    build_manifest.read_text(encoding="utf-8")
                )["executables"]["conformance"]["primary"],
                "implementation_source_commit": provenance["source_commit"],
                "implementation_source_tree": provenance["source_tree"],
                "immutable": True,
                "authenticated_utc": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                ),
            }
        )
        exclusive_write_json(conformance, result)
        exclusive_write_json(
            CONFORMANCE_INDEX,
            {
                "schema": "chain-rescue-v2-conformance-index",
                "immutable_artifact": True,
                "implementation_source_commit": provenance["source_commit"],
                "implementation_source_tree": provenance["source_tree"],
                "conformance": {
                    **file_record(conformance),
                    "path": conformance.relative_to(HERE).as_posix(),
                },
            },
        )
        authenticated = validate_conformance_artifact()
        print(
            "pre-evidence conformance: PASS "
            f"({authenticated['observe_hits']} observed hits; authenticated)"
        )
    finally:
        if candidate.exists():
            candidate.unlink()


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if command == "verify":
        print(json.dumps(validate_environment(require_binaries=True), indent=2, sort_keys=True))
    elif command == "verify-rebuild":
        print(json.dumps(verify_rebuild(), indent=2, sort_keys=True))
    elif command == "prepare-provenance":
        prepare_provenance()
    elif command == "rebind-amendment-3-provenance":
        rebind_amendment_3_provenance()
    elif command == "rebind-post-run-provenance":
        rebind_post_run_provenance()
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
