#!/usr/bin/env python3
"""Frozen WP37B preparation, one-shot execution, and mechanical analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, BinaryIO, Iterable

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WP35 = Path(r"C:\dev\owalnuts-wt\posteriordb-v6\STUDIES\posteriordb_bench_v6")
WP35_PYTHON = WP35 / ".venv" / "Scripts" / "python.exe"
PDB_CHECKOUT = Path(r"C:\dev\owalnuts-wt\posteriordb-pinned")
PDB_COMMIT = "28f8d3d6e975315f42aa274a8399f21e07a43b30"
BASELINE_COMMIT = "a630e04151842cf7a92131dcadd8e9412c675f5b"
BASELINE_TREE = "59ff3f52debb54fd8cea62effd51982c7ecd7a88"
ALGORITHM_REVISION = "walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10"
SEEDS = list(range(96101, 96107))
ARMS = ["finest_to_coarsest", "coarsest_to_finest"]

TARGETS: list[dict[str, Any]] = [
    {
        "id": "posteriordb_accel_gp",
        "posterior": "mcycle_gp-accel_gp",
        "model": "accel_gp",
        "slug": "mcycle_gp__accel_gp",
        "dimension": 66,
        "warmup": 1000,
        "retained": 1000,
        "timeout": 1800,
        "role": 0,
    },
    {
        "id": "posteriordb_gp_pois_regr",
        "posterior": "gp_pois_regr-gp_pois_regr",
        "model": "gp_pois_regr",
        "slug": "gp_pois_regr__gp_pois_regr",
        "dimension": 13,
        "warmup": 1000,
        "retained": 1000,
        "timeout": 900,
        "role": 0,
    },
    {
        "id": "posteriordb_eight_schools_centered",
        "posterior": "eight_schools-eight_schools_centered",
        "model": "eight_schools_centered",
        "slug": "eight_schools__eight_schools_centered",
        "dimension": 10,
        "warmup": 1000,
        "retained": 1000,
        "timeout": 600,
        "role": 0,
    },
    {
        "id": "posteriordb_eight_schools_noncentered",
        "posterior": "eight_schools-eight_schools_noncentered",
        "model": "eight_schools_noncentered",
        "slug": "eight_schools__eight_schools_noncentered",
        "dimension": 10,
        "warmup": 1000,
        "retained": 1000,
        "timeout": 600,
        "role": 0,
    },
    {
        "id": "neal_funnel_10d",
        "dimension": 10,
        "warmup": 2000,
        "retained": 20000,
        "timeout": 1800,
        "role": 1,
    },
    {
        "id": "gaussian_100d",
        "dimension": 100,
        "warmup": 1000,
        "retained": 1000,
        "timeout": 300,
        "role": 2,
    },
    {
        "id": "state_space_sspd11_t1000",
        "dimension": 1006,
        "warmup": 500,
        "retained": 2000,
        "timeout": 900,
        "role": 1,
    },
]
TARGET_BY_ID = {target["id"]: target for target in TARGETS}


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(f"{path}.tmp")
    with temporary.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def normalized_document_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig")
    return sha256_bytes(text.replace("\r\n", "\n").replace("\r", "\n").encode())


def git(*arguments: str, cwd: Path = ROOT) -> str:
    return subprocess.check_output(["git", *arguments], cwd=cwd, text=True).strip()


class Canon:
    def __init__(self, domain: str, version: int):
        self.data = bytearray(domain.encode() + b"\0" + struct.pack("<H", version))

    def u8(self, value: int) -> None:
        self.data += struct.pack("<B", value)

    def boolean(self, value: bool) -> None:
        self.u8(int(value))

    def u64(self, value: int) -> None:
        if not 0 <= value < 2**64:
            raise ValueError(f"u64 out of range: {value}")
        self.data += struct.pack("<Q", value)

    def f64(self, value: float) -> None:
        self.data += struct.pack("<d", value)

    def string(self, value: str) -> None:
        encoded = value.encode()
        self.u64(len(encoded))
        self.data += encoded

    def option(self, value: Any, write) -> None:
        self.u8(value is not None)
        if value is not None:
            write(value)

    def vector(self, values: Iterable[Any], write) -> None:
        values = list(values)
        self.u64(len(values))
        for value in values:
            write(value)


def artifact_record(
    role: int,
    index: int,
    identity: str,
    path: Path,
    *,
    commit: str | None = None,
    tree: str | None = None,
    blob: str | None = None,
) -> dict[str, Any]:
    digest, size = sha256_file(path)
    return {
        "role": role,
        "index": index,
        "identity": identity,
        "path": str(path.resolve()),
        "byte_length": size,
        "sha256": digest,
        "git_commit": commit,
        "git_tree": tree,
        "git_blob": blob,
    }


def materialize_git_blob(destination: Path, revision: str, source: str) -> None:
    atomic_write(
        destination,
        subprocess.check_output(["git", "show", f"{revision}:{source}"], cwd=ROOT),
    )


def write_artifact_record(encoder: Canon, record: dict[str, Any]) -> None:
    encoder.u8(record["role"])
    encoder.u64(record["index"])
    encoder.string(record["identity"])
    encoder.u64(record["byte_length"])
    encoder.data += bytes.fromhex(record["sha256"])
    encoder.option(record["git_commit"], encoder.string)
    encoder.option(record["git_tree"], encoder.string)
    encoder.option(record["git_blob"], encoder.string)


def tree_manifest(directory: Path) -> bytes:
    rows = []
    for path in sorted(
        (
            path
            for path in directory.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix != ".pyc"
        ),
        key=lambda path: path.relative_to(directory).as_posix().encode(),
    ):
        digest, size = sha256_file(path)
        rows.append(f"{digest} {size} {path.relative_to(directory).as_posix()}\n")
    return "".join(rows).encode()


def ensure_models() -> dict[str, dict[str, Any]]:
    script = """
import importlib.util, json, sys
from pathlib import Path
runner_path = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("wp35_runner", runner_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
targets = json.loads(sys.argv[2])
out = {}
for target in targets:
    so, data = module.prepare_bridgestan(target["posterior"])
    reference = module.reference(target["posterior"])
    out[target["id"]] = {
        "model_library": str(so.resolve()),
        "data_json": str(data.resolve()),
        "reference_names": list(reference["names"]),
        "reference_mean": [float(x) for x in reference["mean"]],
        "reference_sd": [float(x) for x in reference["sd"]],
        "reference_mcse": [float(x) for x in reference["mcse"]],
    }
print(json.dumps(out, separators=(",", ":")))
"""
    bridge_targets = [target for target in TARGETS if "posterior" in target]
    completed = subprocess.run(
        [
            str(WP35_PYTHON),
            "-c",
            script,
            str(WP35 / "run_posteriordb.py"),
            json.dumps(bridge_targets),
        ],
        cwd=WP35,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout.splitlines()[-1])


def ordered_cells(model_metadata: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    cells = []
    ordinal = 0
    for target in TARGETS:
        for seed_index, seed in enumerate(SEEDS):
            arms = ARMS if seed_index % 2 == 0 else list(reversed(ARMS))
            for arm in arms:
                metadata = model_metadata.get(target["id"], {})
                cells.append(
                    {
                        "ordinal": ordinal,
                        "id": f'{target["id"]}/{seed}/{arm}',
                        "target": target["id"],
                        "seed": seed,
                        "arm": arm,
                        "warmup": target["warmup"],
                        "retained": target["retained"],
                        "timeout_seconds": target["timeout"],
                        "model_library": metadata.get("model_library"),
                        "data_json": metadata.get("data_json"),
                        "reference_names": metadata.get(
                            "reference_names",
                            (
                                [
                                    "mu",
                                    "sigma_x",
                                    "alpha",
                                    "beta",
                                    "gamma",
                                    "nu",
                                    "x_terminal",
                                    "x_path_mean",
                                ]
                                if target["id"] == "state_space_sspd11_t1000"
                                else []
                            ),
                        ),
                    }
                )
                ordinal += 1
    assert ordinal == 84
    return cells


def option_string(encoder: Canon, value: str | None) -> None:
    encoder.option(value, encoder.string)


def option_u64(encoder: Canon, value: int | None) -> None:
    encoder.option(value, encoder.u64)


def option_f64(encoder: Canon, value: float | None) -> None:
    encoder.option(value, encoder.f64)


def option_vector_f64(encoder: Canon, value: list[float] | None) -> None:
    encoder.option(value, lambda values: encoder.vector(values, encoder.f64))


def fixed_start_pin(target: dict[str, Any], config: Path) -> dict[str, Any] | None:
    if target["id"] == "neal_funnel_10d":
        path = config / "funnel_starts.bin"
        if not path.exists():
            data = b"".join(
                struct.pack("<d", value)
                for omega in (-3.0, -1.0, 1.0, 3.0)
                for value in [omega, *([0.0] * 9)]
            )
            atomic_write(path, data)
        digest, _ = sha256_file(path)
        return {
            "role": "wp37a-fixed-funnel-starts",
            "identity": "given omega=-3,-1,1,3; x[1..9]=0",
            "sha256": digest,
        }
    if target["id"] == "state_space_sspd11_t1000":
        path = (
            ROOT
            / "STUDIES"
            / "sspd11_confirmation_v1"
            / "primary"
            / "starts"
            / "sspd-11.json"
        )
        digest, _ = sha256_file(path)
        return {
            "role": "sspd-canonical-fixed-starts",
            "identity": "STUDIES/sspd11_confirmation_v1/primary/starts/sspd-11.json",
            "sha256": digest,
        }
    return None


def write_artifact_pin(encoder: Canon, pin: dict[str, Any]) -> None:
    encoder.string(pin["role"])
    encoder.string(pin["identity"])
    encoder.data += bytes.fromhex(pin["sha256"])


def target_artifacts(
    target: dict[str, Any],
    metadata: dict[str, dict[str, Any]],
    config: Path,
    repository_tree: str,
) -> list[dict[str, Any]]:
    if "posterior" in target:
        model = metadata[target["id"]]
        slug = target["slug"]
        records = [
            artifact_record(
                0,
                0,
                f"posteriordb commit {PDB_COMMIT} tree {repository_tree}",
                config / "posteriordb-tree.txt",
                commit=PDB_COMMIT,
                tree=repository_tree,
            ),
            artifact_record(
                1,
                0,
                "WP35 STUDIES/posteriordb_bench_v6/protocol.json",
                WP35 / "protocol.json",
            ),
            artifact_record(
                2,
                0,
                "WP35 STUDIES/posteriordb_bench_v6/run_posteriordb.py",
                WP35 / "run_posteriordb.py",
            ),
            artifact_record(
                3,
                0,
                f"WP35 models/{slug}.stan",
                WP35 / "models" / f"{slug}.stan",
            ),
            artifact_record(
                4,
                0,
                f"WP35 models/{slug}.data.json",
                Path(model["data_json"]),
            ),
            artifact_record(
                5,
                0,
                f"WP35 models/{slug}_model.so",
                Path(model["model_library"]),
            ),
            artifact_record(
                6,
                0,
                "BridgeStan 2.9.0 Python/source runtime tree manifest",
                config / "bridgestan-runtime-tree.txt",
            ),
        ]
        dependency_manifest = config / "native-dependencies.json"
        dependencies = json.loads(dependency_manifest.read_text())
        for index, dependency in enumerate(dependencies):
            records.append(
                artifact_record(
                    7,
                    index,
                    dependency["identity"],
                    Path(dependency["path"]),
                )
            )
        return records
    if target["id"] in {"neal_funnel_10d", "gaussian_100d"}:
        return [
            artifact_record(
                8,
                0,
                "STUDIES/delta2_sidechecks_v1/src/main.rs",
                config / "wp37a-pure-target-source.rs",
                commit="e91458dca1aa7944b07c65514ad2313b4a60cd4d",
                blob="0385e3fbcd2caad2c92c81a02b0ec148f02d2543",
            )
        ]
    state = ROOT / "STUDIES" / "sspd11_confirmation_v1" / "primary"
    paths = [
        config / "sspd-canonical-source.rs",
        state / "src" / "main.rs",
        state / "protocol.json",
        state / "starts" / "sspd-11.json",
        state / "fixtures" / "polyscope_parity.json",
        config / "sspd-target-fixture.json",
    ]
    identities = [
        "STUDIES/sspd11_confirmation_v1/primary/src/canonical.rs",
        "STUDIES/sspd11_confirmation_v1/primary/src/main.rs",
        "STUDIES/sspd11_confirmation_v1/primary/protocol.json",
        "STUDIES/sspd11_confirmation_v1/primary/starts/sspd-11.json",
        "STUDIES/sspd11_confirmation_v1/primary/fixtures/polyscope_parity.json",
        "STUDIES/sspd11_confirmation_v1/primary/fixtures/sspd-11-n1000-mixed-regular-moderate-h1-none-none-cold.json",
    ]
    return [
        artifact_record(
            role,
            0,
            identity,
            path,
            commit=BASELINE_COMMIT,
            blob=git("rev-parse", f"{BASELINE_COMMIT}:{identity}"),
        )
        for role, path, identity in zip(range(9, 15), paths, identities, strict=True)
    ]


def pair_common_record(
    target: dict[str, Any],
    artifacts: list[dict[str, Any]],
    config: Path,
) -> bytes:
    encoder = Canon(
        "owalnuts.reverse_coarsening_order_v1.pair_common_static_config", 3
    )
    encoder.string("reverse_coarsening_order_v1")
    encoder.string("WP37B")
    encoder.string(BASELINE_COMMIT)
    encoder.string(BASELINE_TREE)
    encoder.string(ALGORITHM_REVISION)
    bridge = "posterior" in target
    encoder.string(target["id"])
    encoder.u8(1 if bridge else 0)  # TargetBackend
    encoder.u8(target["role"])  # TargetRole
    encoder.u64(target["dimension"])
    encoder.u8(0)  # DeterministicFiniteOrRecoverable
    option_string(encoder, target.get("posterior"))
    option_string(encoder, target.get("model"))
    option_string(encoder, PDB_COMMIT if bridge else None)
    encoder.u64(4 if bridge else 0)
    encoder.u64(1 if bridge else 0)
    encoder.u8(1 if bridge else 0)  # ThreadingMode
    encoder.u8(1 if bridge else 0)  # ExecutionMode
    encoder.vector(artifacts, lambda record: write_artifact_record(encoder, record))
    encoder.u8(0)  # RepeatedHalvingDoublingV1
    encoder.string("repeated-halving-doubling-v1")
    encoder.u64(4)
    encoder.u64(4)
    encoder.u64(target["warmup"])
    encoder.u64(target["retained"])
    encoder.u64(target["timeout"])
    encoder.u64(30)
    encoder.boolean(True)
    uniform = target["id"].startswith("posteriordb_") or target["id"] == "gaussian_100d"
    encoder.u8(1 if uniform else 0)
    option_f64(encoder, 2.0 if uniform else None)
    option_u64(encoder, 100 if uniform else None)
    option_u64(encoder, 0x5EED141700000000 if uniform else None)
    fixed = fixed_start_pin(target, config)
    encoder.option(fixed, lambda pin: write_artifact_pin(encoder, pin))
    option_u64(encoder, 4 if fixed else None)
    encoder.string("splitmix64(base_seed.wrapping_add(chain_index as u64))")
    encoder.string("rand::rngs::SmallRng")
    encoder.string("rand_distr::StandardNormal")
    encoder.f64(0.5)
    encoder.u64(10)
    encoder.u64(1)
    encoder.u64(8)
    encoder.f64(1.0)
    encoder.f64(1000.0)
    encoder.u8(0)  # momentum sum
    encoder.u8(0)  # retained exhaustion stop
    encoder.u8(0)  # diagonal metric
    encoder.boolean(True)
    option_vector_f64(encoder, None)
    encoder.u8(0)  # dual averaging
    encoder.f64(0.8)
    encoder.boolean(True)
    encoder.option(0, encoder.u8)  # warmup exhaustion
    encoder.u8(0)  # Stan regularization
    option_string(encoder, None)  # rescue
    option_string(encoder, None)  # initial step search
    encoder.u64(75)
    encoder.u64(25)
    encoder.u64(50)
    encoder.vector([], encoder.u64)
    encoder.string("CurrentCoarseEndpoint")
    encoder.f64(0.05)
    encoder.f64(10.0)
    encoder.f64(0.75)
    option_string(encoder, None)  # paper
    encoder.f64(1.0)
    encoder.boolean(False)
    option_f64(encoder, None)
    option_f64(encoder, None)
    option_f64(encoder, None)
    option_f64(encoder, None)
    encoder.boolean(True)
    encoder.u8(0)  # biased progressive
    encoder.u8(0)  # Barker
    encoder.boolean(True)
    option_u64(encoder, None)
    option_u64(encoder, None)
    encoder.boolean(False)
    option_u64(encoder, None)
    encoder.u64(3)
    return bytes(encoder.data)


def prepare_runtime_manifests(config: Path) -> None:
    query = (
        "import bridgestan, bridgestan.compile as compile, json; "
        "from pathlib import Path; "
        "print(json.dumps({'package': str(Path(bridgestan.__file__).parent), "
        "'home': str(Path(compile.get_bridgestan_path()))}))"
    )
    result = json.loads(
        subprocess.check_output([str(WP35_PYTHON), "-c", query], text=True)
    )
    package = Path(result["package"])
    atomic_write(config / "bridgestan-runtime-tree.txt", tree_manifest(package))
    dependencies = []
    tbb = Path(result["home"]) / "stan" / "lib" / "stan_math" / "lib" / "tbb" / "tbb.dll"
    if tbb.exists():
        dependencies.append({"identity": "BridgeStan tbb.dll", "path": str(tbb.resolve())})
    atomic_write(
        config / "native-dependencies.json", canonical_json(dependencies)
    )


def conformance_bytes() -> bytes:
    encoder = Canon("owalnuts.reverse_coarsening_order_v1.conformance", 2)
    encoder.u64(0)
    encoder.u64(2**64 - 1)
    encoder.f64(-0.0)
    encoder.f64(float.fromhex("0x1.0000000000001p+0"))
    encoder.boolean(False)
    encoder.boolean(True)
    encoder.option(None, encoder.u64)
    encoder.option(7, encoder.u64)
    encoder.string("")
    encoder.string("WP37B/λ")
    encoder.vector([], encoder.u64)
    encoder.vector([1, 2, 3], encoder.u64)
    enum_widths = [2, 2, 2, 3, 6, 2, 6, 4, 1, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 2, 2, 3, 3]
    encoder.u64(len(enum_widths))
    for width in enum_widths:
        encoder.u64(width)
        for tag in range(width):
            encoder.u8(tag)
    valid_leaf_rows = [
        (0, True, True, 2, None, True),
        (1, False, False, 0, 0, False),
        (1, True, True, 2, 1, False),
        (1, False, False, 0, 2, False),
        (1, True, True, 2, 2, False),
    ]
    encoder.u64(len(valid_leaf_rows))
    for outcome, level, endpoint, schedule, rejection, built in valid_leaf_rows:
        encoder.u8(outcome)
        encoder.boolean(level)
        encoder.boolean(endpoint)
        encoder.u64(schedule)
        encoder.option(rejection, encoder.u8)
        encoder.boolean(built)
    encoder.u64(6)
    for error_kind in range(6):
        encoder.u8(error_kind)
        encoder.u8(min(error_kind, 4))
        encoder.string(f"fatal-{error_kind}")
    return bytes(encoder.data)


def check_conformance() -> None:
    fixture = json.loads((HERE / "conformance.json").read_text())
    actual = conformance_bytes()
    if actual.hex() != fixture["canonical_hex"]:
        raise RuntimeError("independent Python conformance bytes mismatch")
    if sha256_bytes(actual) != fixture["sha256"]:
        raise RuntimeError("independent Python conformance hash mismatch")


def prepare(args: argparse.Namespace) -> None:
    if (HERE / "evidence").exists():
        raise RuntimeError("evidence directory already exists; preparation is frozen")
    binary = Path(args.binary).resolve()
    if not binary.exists():
        raise FileNotFoundError(binary)
    rustc = subprocess.check_output(
        ["rustc", "+1.88.0-x86_64-pc-windows-gnu", "-Vv"], text=True
    )
    if "release: 1.88.0" not in rustc or "host: x86_64-pc-windows-gnu" not in rustc:
        raise RuntimeError("release binary must use pinned GNU Rust 1.88.0")
    if git("status", "--porcelain"):
        raise RuntimeError("prepare requires the committed core/harness worktree")
    core_commit = git("rev-parse", "HEAD")
    core_tree = git("rev-parse", "HEAD^{tree}")
    if git("rev-parse", "HEAD~4") != "84a76b1a47ae43034ac460e7d409cc0d4e5ec5f2":
        raise RuntimeError("unexpected preregistration ancestry")
    if git("rev-parse", "HEAD~3") != "460233719a03202d6632fbf3e7a11b709186bad2":
        raise RuntimeError("unexpected Amendment 1 ancestry")
    if git("rev-parse", "HEAD~2") != "c10a253a19096941fb79015b3975cba6c489ddc6":
        raise RuntimeError("unexpected Amendment 2 ancestry")
    if git("rev-parse", "HEAD~1") != "7d08d0ff574d144faebdd5fc645492d3c2af16ec":
        raise RuntimeError("unexpected Amendment 3 ancestry")
    expected_documents = {
        "PREREGISTRATION.md": "ba4a3a9e64c8757d021ec9886e24f537c4059e8deb24565f1bd90ba94d98234d",
        "protocol.json": "6dc9deaf1a3133c9e308a68bd6352f0a30cf61653ee7dad8da93dba59a4b9c81",
        "AMENDMENT-1.md": "83c0f92f4314449c52746ab44e5a9185b18b97359884b11c4556abb940a6a1ca",
        "AMENDMENT-2.md": "564e35b1424a738b6d424f05f84138f45d97176fd70287465e8a9f943f2e5162",
    }
    for name, expected in expected_documents.items():
        if normalized_document_sha256(HERE / name) != expected:
            raise RuntimeError(f"frozen document hash mismatch: {name}")
    if not PDB_CHECKOUT.exists():
        raise FileNotFoundError(PDB_CHECKOUT)
    if git("rev-parse", "HEAD", cwd=PDB_CHECKOUT) != PDB_COMMIT:
        raise RuntimeError("posteriordb checkout commit mismatch")
    repository_tree = git("rev-parse", "HEAD^{tree}", cwd=PDB_CHECKOUT)
    config = HERE / "config"
    config.mkdir(exist_ok=True)
    materialize_git_blob(
        config / "wp37a-pure-target-source.rs",
        BASELINE_COMMIT,
        "STUDIES/delta2_sidechecks_v1/src/main.rs",
    )
    materialize_git_blob(
        config / "sspd-canonical-source.rs",
        BASELINE_COMMIT,
        "STUDIES/sspd11_confirmation_v1/primary/src/canonical.rs",
    )
    materialize_git_blob(
        config / "sspd-target-fixture.json",
        BASELINE_COMMIT,
        "STUDIES/sspd11_confirmation_v1/primary/fixtures/sspd-11-n1000-mixed-regular-moderate-h1-none-none-cold.json",
    )
    tree_rows = subprocess.check_output(
        ["git", "ls-tree", "-r", "--full-tree", PDB_COMMIT],
        cwd=PDB_CHECKOUT,
    )
    atomic_write(config / "posteriordb-tree.txt", tree_rows)
    prepare_runtime_manifests(config)
    metadata = ensure_models()
    atomic_write(config / "reference_metadata.json", canonical_json(metadata))
    cells = ordered_cells(metadata)
    artifacts_by_target = {}
    config_index: dict[str, Any] = {"targets": {}, "arms": {}}
    for target in TARGETS:
        artifacts = target_artifacts(target, metadata, config, repository_tree)
        artifacts_by_target[target["id"]] = artifacts
        pair_bytes = pair_common_record(target, artifacts, config)
        pair_path = config / f'{target["id"]}.pair_common.bin'
        atomic_write(pair_path, pair_bytes)
        pair_hash = sha256_bytes(pair_bytes)
        config_index["targets"][target["id"]] = {
            "file": pair_path.name,
            "sha256": pair_hash,
            "artifacts": artifacts,
        }
    for arm_index, arm in enumerate(ARMS):
        # Arm records are target-specific because they embed that target's
        # pair-common hash; use one file per target and arm.
        config_index["arms"][arm] = {}
        for target in TARGETS:
            pair_hash = config_index["targets"][target["id"]]["sha256"]
            encoder = Canon("owalnuts.reverse_coarsening_order_v1.arm_config", 3)
            encoder.data += bytes.fromhex(pair_hash)
            encoder.u8(arm_index)
            encoder.u8(arm_index)
            path = config / f'{target["id"]}.{arm}.arm.bin'
            data = bytes(encoder.data)
            atomic_write(path, data)
            config_index["arms"][arm][target["id"]] = {
                "file": path.name,
                "sha256": sha256_bytes(data),
            }
    for cell in cells:
        cell["pair_common_sha256"] = config_index["targets"][cell["target"]][
            "sha256"
        ]
        cell["arm_config_sha256"] = config_index["arms"][cell["arm"]][
            cell["target"]
        ]["sha256"]
    manifest = {
        "schema": "owalnuts-reverse-coarsening-order-v1-manifest",
        "version": 3,
        "cells": cells,
    }
    manifest_bytes = canonical_json(manifest)
    atomic_write(HERE / "manifest.json", manifest_bytes)
    atomic_write(HERE / "config-index.json", canonical_json(config_index))
    conformance = conformance_bytes()
    atomic_write(
        HERE / "conformance.json",
        canonical_json(
            {
                "schema": "owalnuts-reverse-coarsening-order-v1-conformance",
                "canonical_hex": conformance.hex(),
                "sha256": sha256_bytes(conformance),
            }
        ),
    )
    check_conformance()
    binary_hash, binary_size = sha256_file(binary)
    provenance = {
        "schema": "owalnuts-reverse-coarsening-order-v1-provenance",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_baseline": {"commit": BASELINE_COMMIT, "tree": BASELINE_TREE},
        "preregistration_commits": [
            "84a76b1a47ae43034ac460e7d409cc0d4e5ec5f2",
            "460233719a03202d6632fbf3e7a11b709186bad2",
            "c10a253a19096941fb79015b3975cba6c489ddc6",
            "7d08d0ff574d144faebdd5fc645492d3c2af16ec",
        ],
        "core_harness": {"commit": core_commit, "tree": core_tree},
        "binary": {
            "path": str(binary),
            "sha256": binary_hash,
            "byte_length": binary_size,
        },
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "config_index_sha256": sha256_file(HERE / "config-index.json")[0],
        "cargo_lock": {
            "root": sha256_file(ROOT / "Cargo.lock")[0],
            "study": sha256_file(HERE / "Cargo.lock")[0],
        },
        "rustc_vv": rustc,
        "cargo_profile": "release",
        "features": ["research"],
        "os": os.name,
        "platform": sys.platform,
        "cpu": os.environ.get("PROCESSOR_IDENTIFIER"),
        "posteriordb": {"commit": PDB_COMMIT, "tree": repository_tree},
        "model_metadata": metadata,
        "target_artifacts": artifacts_by_target,
        "documents_lf_normalized": {
            name: normalized_document_sha256(HERE / name)
            for name in [
                "PREREGISTRATION.md",
                "protocol.json",
                "AMENDMENT-1.md",
                "AMENDMENT-2.md",
                "AMENDMENT-3.md",
            ]
        },
    }
    atomic_write(HERE / "PROVENANCE.json", canonical_json(provenance))
    print(f"prepared 84 cells for core commit {core_commit}")


def process_start_time(pid: int) -> str | None:
    command = (
        f"(Get-Process -Id {pid}).StartTime.ToUniversalTime()"
        ".ToString('yyyy-MM-ddTHH:mm:ss.fffffffZ')"
    )
    try:
        return subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", command],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        return None


def authenticate_raw(raw: dict[str, Any], cell: dict[str, Any], artifacts: Path) -> None:
    if (
        raw.get("schema") != "owalnuts-reverse-coarsening-order-v1-cell"
        or raw.get("completion") != "WP37B_CELL_COMPLETE_V1"
        or raw.get("status") != "ok"
        or raw.get("ordinal") != cell["ordinal"]
        or raw.get("cell_id") != cell["id"]
    ):
        raise RuntimeError(f"raw schema/identity failure for {cell['id']}")
    if (
        raw["records"]["pair_common_static_config"]["sha256"]
        != cell["pair_common_sha256"]
        or raw["records"]["arm_config"]["sha256"] != cell["arm_config_sha256"]
    ):
        raise RuntimeError(f"static config authentication failed for {cell['id']}")
    for key, record in raw["records"].items():
        if key in {
            "pair_common_static_config",
            "arm_config",
            "fatal_errors",
            "public_errors",
        }:
            continue
        path = artifacts / record["file"]
        digest, size = sha256_file(path)
        expected_digest = record.get("compressed_sha256", record.get("sha256"))
        expected_size = record.get("compressed_bytes", record.get("bytes"))
        if digest != expected_digest or size != expected_size:
            raise RuntimeError(f"{key} artifact authentication failed for {cell['id']}")


def execute(args: argparse.Namespace) -> None:
    manifest_path = HERE / "manifest.json"
    provenance_path = HERE / "PROVENANCE.json"
    manifest = json.loads(manifest_path.read_text())
    provenance = json.loads(provenance_path.read_text())
    if len(manifest["cells"]) != 84:
        raise RuntimeError("manifest does not contain 84 cells")
    if git("status", "--porcelain"):
        raise RuntimeError("evidence launch requires a clean provenance commit")
    if git("rev-parse", "HEAD") == provenance["core_harness"]["commit"]:
        raise RuntimeError("provenance/conformance must be committed after core/harness")
    binary = Path(provenance["binary"]["path"])
    if sha256_file(binary)[0] != provenance["binary"]["sha256"]:
        raise RuntimeError("release binary hash mismatch")
    if sha256_file(manifest_path)[0] != provenance["manifest_sha256"]:
        raise RuntimeError("ordered manifest hash mismatch")
    config_index = json.loads((HERE / "config-index.json").read_text())
    if sha256_file(HERE / "config-index.json")[0] != provenance["config_index_sha256"]:
        raise RuntimeError("configuration index hash mismatch")
    for target_record in config_index["targets"].values():
        if (
            sha256_file(HERE / "config" / target_record["file"])[0]
            != target_record["sha256"]
        ):
            raise RuntimeError("pair-common static configuration hash mismatch")
    for arm_records in config_index["arms"].values():
        for arm_record in arm_records.values():
            if (
                sha256_file(HERE / "config" / arm_record["file"])[0]
                != arm_record["sha256"]
            ):
                raise RuntimeError("arm configuration hash mismatch")
    evidence = HERE / "evidence"
    markers = evidence / "launch-markers"
    raw_directory = evidence / "raw"
    process_directory = evidence / "process"
    logs = evidence / "logs"
    artifacts = evidence / "artifacts"
    for directory in [markers, raw_directory, process_directory, logs, artifacts]:
        directory.mkdir(parents=True, exist_ok=False)
    run_started = time.time()
    for cell in manifest["cells"]:
        ordinal = cell["ordinal"]
        stem = f"{ordinal:03d}-{cell['id'].replace('/', '-')}"
        marker = markers / f"{stem}.launch.json"
        raw_path = raw_directory / f"{stem}.json"
        process_path = process_directory / f"{stem}.json"
        stdout_path = logs / f"{stem}.stdout.txt"
        stderr_path = logs / f"{stem}.stderr.txt"
        command = [
            str(binary),
            str(manifest_path),
            str(ordinal),
            str(raw_path),
            str(artifacts),
        ]
        launch = {
            "cell_id": cell["id"],
            "ordinal": ordinal,
            "command": command,
            "parent_launch_utc": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            ),
            "parent_launch_epoch_ns": time.time_ns(),
        }
        atomic_write(marker, canonical_json(launch))
        started_ns = time.time_ns()
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        started_at = process_start_time(process.pid)
        timed_out = False
        termination = None
        try:
            stdout, stderr = process.communicate(timeout=cell["timeout_seconds"])
        except subprocess.TimeoutExpired:
            timed_out = True
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T"],
                capture_output=True,
            )
            try:
                stdout, stderr = process.communicate(timeout=30)
                termination = "graceful_process_tree"
            except subprocess.TimeoutExpired:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                )
                stdout, stderr = process.communicate()
                termination = "forced_process_tree"
        ended_ns = time.time_ns()
        atomic_write(stdout_path, stdout)
        atomic_write(stderr_path, stderr)
        raw_state = "missing"
        raw_sha256 = None
        raw_size = None
        validation_error = None
        if raw_path.exists():
            raw_state = "present"
            raw_sha256, raw_size = sha256_file(raw_path)
            try:
                authenticate_raw(json.loads(raw_path.read_text()), cell, artifacts)
                raw_state = "authenticated"
            except Exception as error:  # preserve exact failed evidence
                validation_error = str(error)
        returncode = process.returncode
        record = {
            "schema": "owalnuts-reverse-coarsening-order-v1-process",
            "cell_id": cell["id"],
            "ordinal": ordinal,
            "command": command,
            "pid": process.pid,
            "process_start_time_utc": started_at,
            "parent_started_epoch_ns": started_ns,
            "parent_ended_epoch_ns": ended_ns,
            "duration_seconds": (ended_ns - started_ns) / 1e9,
            "stdout": {
                "file": stdout_path.name,
                "sha256": sha256_bytes(stdout),
                "bytes": len(stdout),
            },
            "stderr": {
                "file": stderr_path.name,
                "sha256": sha256_bytes(stderr),
                "bytes": len(stderr),
            },
            "timed_out": timed_out,
            "termination": termination,
            "exit_status": {
                "raw_signed": returncode,
                "unsigned": returncode & 0xFFFFFFFF,
                "hex": f"0x{returncode & 0xFFFFFFFF:08x}",
            },
            "raw_result": {
                "state": raw_state,
                "sha256": raw_sha256,
                "bytes": raw_size,
                "validation_error": validation_error,
            },
        }
        atomic_write(process_path, canonical_json(record))
        print(
            f"[{ordinal + 1:02d}/84] {cell['id']} "
            f"exit={returncode} raw={raw_state} wall={record['duration_seconds']:.1f}s",
            flush=True,
        )
        if timed_out or returncode != 0 or raw_state != "authenticated":
            raise RuntimeError(
                f"first-evidence defect at {cell['id']}; preserved and stopped without rerun"
            )
    atomic_write(
        evidence / "RUN-COMPLETE.json",
        canonical_json(
            {
                "cells": 84,
                "started_epoch": run_started,
                "ended_epoch": time.time(),
                "wall_seconds": time.time() - run_started,
            }
        ),
    )


def summed_phase(raw: dict[str, Any], phase: int) -> dict[str, int]:
    keys = raw["work"]["chains"][0][phase].keys()
    return {
        key: sum(chain[phase][key] for chain in raw["work"]["chains"])
        for key in keys
        if isinstance(raw["work"]["chains"][0][phase][key], int)
    }


def canonical_equal(
    binary: Path, artifacts: Path, left: dict[str, Any], right: dict[str, Any], key: str
) -> bool:
    left_record = left["records"][key]
    right_record = right["records"][key]
    if (
        left_record["canonical_sha256"] != right_record["canonical_sha256"]
        or left_record["canonical_bytes"] != right_record["canonical_bytes"]
    ):
        return False
    return (
        subprocess.run(
            [
                str(binary),
                "--compare",
                str(artifacts / left_record["file"]),
                str(artifacts / right_record["file"]),
            ],
            capture_output=True,
        ).returncode
        == 0
    )


def reverse_offsets(path: Path) -> tuple[int, dict[tuple[int, ...], tuple[int, int]]]:
    import mmap

    records: dict[tuple[int, ...], tuple[int, int]] = {}
    with path.open("rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
        terminator = data.find(b"\0")
        if terminator < 0:
            raise RuntimeError("reverse record domain terminator missing")
        offset = terminator + 3
        count = struct.unpack_from("<Q", data, offset)[0]
        offset += 8
        for _ in range(count):
            key = struct.unpack_from("<7Q", data, offset)
            offset += 56
            payload_start = offset
            tag = data[offset]
            offset += 1
            dimension = struct.unpack_from("<Q", data, offset)[0]
            offset += 8 + 8 * dimension
            log_option = data[offset]
            offset += 1 + (8 if log_option else 0)
            gradient_option = data[offset]
            offset += 1
            if gradient_option:
                gradient_dimension = struct.unpack_from("<Q", data, offset)[0]
                offset += 8 + 8 * gradient_dimension
            if tag not in (0, 1):
                raise RuntimeError("invalid reverse evaluation tag")
            if key in records:
                raise RuntimeError(f"duplicate reverse key {key}")
            records[key] = (payload_start, offset - payload_start)
        if offset != len(data):
            raise RuntimeError("trailing bytes in reverse record")
    return count, records


def compare_reverse_shared(
    binary: Path,
    artifacts: Path,
    left: dict[str, Any],
    right: dict[str, Any],
    temporary: Path,
) -> dict[str, int]:
    import mmap

    temporary.mkdir(exist_ok=True)
    paths = []
    for name, raw in [("left", left), ("right", right)]:
        output = temporary / f"{name}.bin"
        subprocess.run(
            [
                str(binary),
                "--decompress",
                str(artifacts / raw["records"]["reverse_evaluations"]["file"]),
                str(output),
            ],
            check=True,
        )
        paths.append(output)
    left_count, left_offsets = reverse_offsets(paths[0])
    right_count, right_offsets = reverse_offsets(paths[1])
    shared = sorted(left_offsets.keys() & right_offsets.keys())
    mismatches = 0
    with paths[0].open("rb") as left_file, paths[1].open("rb") as right_file:
        with mmap.mmap(left_file.fileno(), 0, access=mmap.ACCESS_READ) as left_data:
            with mmap.mmap(right_file.fileno(), 0, access=mmap.ACCESS_READ) as right_data:
                for key in shared:
                    left_offset, left_length = left_offsets[key]
                    right_offset, right_length = right_offsets[key]
                    if left_length != right_length or left_data[
                        left_offset : left_offset + left_length
                    ] != right_data[right_offset : right_offset + right_length]:
                        mismatches += 1
    for path in paths:
        path.unlink()
    return {
        "incumbent_records": left_count,
        "candidate_records": right_count,
        "shared_keys": len(shared),
        "shared_key_mismatches": mismatches,
        "incumbent_only": len(left_offsets.keys() - right_offsets.keys()),
        "candidate_only": len(right_offsets.keys() - left_offsets.keys()),
    }


def read_diagnostic_draws(path: Path) -> tuple[Any, Any | None]:
    import numpy as np

    with path.open("rb") as handle:
        if handle.read(8) != b"WP37BDRW":
            raise RuntimeError("diagnostic draw magic mismatch")
        chains, draws, dimension = struct.unpack("<3Q", handle.read(24))
        unconstrained = np.fromfile(
            handle, dtype="<f8", count=chains * draws * dimension
        ).reshape(chains, draws, dimension)
        reference_columns = struct.unpack("<Q", handle.read(8))[0]
        reference = None
        if reference_columns:
            reference = np.fromfile(
                handle, dtype="<f8", count=chains * draws * reference_columns
            ).reshape(chains, draws, reference_columns)
        if handle.read(1):
            raise RuntimeError("trailing diagnostic draw bytes")
    return unconstrained, reference


def arviz_summary(draws) -> dict[str, Any]:
    import arviz as az
    import numpy as np

    data = az.convert_to_dataset({"p": draws})
    flat = draws.reshape(-1, draws.shape[-1])
    return {
        "mean": flat.mean(0).tolist(),
        "sd": flat.std(0, ddof=1).tolist(),
        "mcse": np.asarray(az.mcse(data, method="mean").p.values).tolist(),
        "rhat": np.asarray(az.rhat(data, method="rank").p.values).tolist(),
        "bulk_ess": np.asarray(az.ess(data, method="bulk").p.values).tolist(),
        "tail_ess": np.asarray(
            az.ess(data, method="tail", prob=(0.05, 0.95)).p.values
        ).tolist(),
    }


def validity_summary(
    target: str,
    raw: dict[str, Any],
    artifacts: Path,
    reference_metadata: dict[str, Any],
) -> dict[str, Any]:
    import numpy as np

    unconstrained, reference = read_diagnostic_draws(
        artifacts / raw["records"]["diagnostic_draws"]["file"]
    )
    if target.startswith("posteriordb_"):
        if reference is None:
            raise RuntimeError("posteriordb reference draws missing")
        summary = arviz_summary(reference)
        reference_info = reference_metadata[target]
        denominator = np.sqrt(
            np.square(summary["mcse"]) + np.square(reference_info["reference_mcse"])
        )
        summary["reference_z"] = (
            (np.asarray(summary["mean"]) - reference_info["reference_mean"])
            / denominator
        ).tolist()
        summary["parameter_names"] = reference_info["reference_names"]
        return summary
    if target == "neal_funnel_10d":
        omega = unconstrained[:, :, :1]
        summary = arviz_summary(omega)
        values = omega[:, :, 0]
        for threshold, exact in [
            (-5, 0.0477903522728147),
            (-6, 0.0227501319481792),
        ]:
            indicator = values < threshold
            probability = float(indicator.mean())
            mcse = math.sqrt(probability * (1.0 - probability) / indicator.size)
            summary[f"p_omega_lt_{abs(threshold)}"] = probability
            summary[f"p_omega_lt_{abs(threshold)}_mcse"] = mcse
            summary[f"p_omega_lt_{abs(threshold)}_z"] = (
                (probability - exact) / mcse if mcse else None
            )
        summary["variance_omega"] = float(values.var(ddof=1))
        return summary
    if target == "gaussian_100d":
        return arviz_summary(unconstrained)
    if reference is None or reference.shape[-1] != 8:
        raise RuntimeError("state-space functional draws missing")
    summary = arviz_summary(reference)
    summary["functional_names"] = [
        "mu",
        "sigma_x",
        "alpha",
        "beta",
        "gamma",
        "nu",
        "x_terminal",
        "x_path_mean",
    ]
    return summary


def checked_sum(values: Iterable[int]) -> int:
    total = 0
    for value in values:
        total += value
        if total >= 2**64:
            raise OverflowError("u64 checked sum overflow")
    return total


def analyze(_args: argparse.Namespace) -> None:
    evidence = HERE / "evidence"
    manifest = json.loads((HERE / "manifest.json").read_text())
    provenance = json.loads((HERE / "PROVENANCE.json").read_text())
    binary = Path(provenance["binary"]["path"])
    artifacts = evidence / "artifacts"
    raw_by_key: dict[tuple[str, int, str], dict[str, Any]] = {}
    process_records = sorted((evidence / "process").glob("*.json"))
    raw_records = sorted((evidence / "raw").glob("*.json"))
    markers = sorted((evidence / "launch-markers").glob("*.json"))
    for path in raw_records:
        raw = json.loads(path.read_text())
        raw_by_key[(raw["target"], raw["seed"], raw["arm"])] = raw
    m1 = (
        len(markers) == 84
        and len(process_records) == 84
        and len(raw_records) == 84
        and all(
            json.loads(path.read_text())["raw_result"]["state"] == "authenticated"
            and json.loads(path.read_text())["exit_status"]["raw_signed"] == 0
            for path in process_records
        )
    )
    config_index = json.loads((HERE / "config-index.json").read_text())
    for target, record in config_index["targets"].items():
        if sha256_file(HERE / "config" / record["file"])[0] != record["sha256"]:
            m1 = False
    pair_reports = []
    all_identity = True
    all_health = True
    w1 = True
    phase_units = 0
    target_totals: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )
    global_totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    temporary = evidence / "analysis-temporary"
    reference_metadata = json.loads((HERE / "config" / "reference_metadata.json").read_text())
    validity: dict[str, Any] = {}
    for target in TARGETS:
        target_id = target["id"]
        for seed in SEEDS:
            incumbent = raw_by_key[(target_id, seed, "finest_to_coarsest")]
            candidate = raw_by_key[(target_id, seed, "coarsest_to_finest")]
            identity = {
                key: canonical_equal(binary, artifacts, incumbent, candidate, key)
                for key in [
                    "initial_positions",
                    "initializer_attempts",
                    "semantic",
                    "forward_calls",
                    "stops",
                ]
            }
            reverse_shared = compare_reverse_shared(
                binary, artifacts, incumbent, candidate, temporary
            )
            identity["reverse_shared_keys"] = reverse_shared["shared_key_mismatches"] == 0
            pair_identity = all(identity.values())
            all_identity &= pair_identity
            phases = []
            pair_health = True
            for phase_index, phase_name in enumerate(["warmup", "retained"]):
                incumbent_phase = summed_phase(incumbent, phase_index)
                candidate_phase = summed_phase(candidate, phase_index)
                unit_pass = (
                    candidate_phase["reverse_calls"] <= incumbent_phase["reverse_calls"]
                    and candidate_phase["gated_kernel_calls"]
                    <= incumbent_phase["gated_kernel_calls"]
                )
                w1 &= unit_pass
                phase_units += 1
                health_keys = [
                    "invalid_forward_rejections",
                    "invalid_reverse_rejections",
                    "invalid_stops",
                    "divergences",
                    "refinement_exhaustions",
                ]
                health_pass = all(
                    candidate_phase[key] <= incumbent_phase[key] for key in health_keys
                )
                pair_health &= health_pass
                for arm, values in [
                    ("incumbent", incumbent_phase),
                    ("candidate", candidate_phase),
                ]:
                    for key in ["reverse_calls", "gated_kernel_calls"]:
                        target_totals[target_id][arm][key] += values[key]
                        target_totals[target_id][arm][f"{phase_name}_{key}"] += values[key]
                        global_totals[arm][key] += values[key]
                phases.append(
                    {
                        "phase": phase_name,
                        "incumbent": incumbent_phase,
                        "candidate": candidate_phase,
                        "reverse_ratio": (
                            candidate_phase["reverse_calls"]
                            / incumbent_phase["reverse_calls"]
                            if incumbent_phase["reverse_calls"]
                            else None
                        ),
                        "gated_kernel_ratio": (
                            candidate_phase["gated_kernel_calls"]
                            / incumbent_phase["gated_kernel_calls"]
                            if incumbent_phase["gated_kernel_calls"]
                            else None
                        ),
                        "W1": unit_pass,
                        "health": health_pass,
                    }
                )
            all_health &= pair_health
            validity_key = f"{target_id}/{seed}"
            validity[validity_key] = validity_summary(
                target_id, incumbent, artifacts, reference_metadata
            )
            pair_reports.append(
                {
                    "target": target_id,
                    "seed": seed,
                    "identity": identity,
                    "identity_pass": pair_identity,
                    "reverse_shared": reverse_shared,
                    "health_pass": pair_health,
                    "phases": phases,
                    "validity_key": validity_key,
                }
            )
    if temporary.exists():
        temporary.rmdir()
    w2_multiply_ok = (
        20 * global_totals["candidate"]["reverse_calls"] < 2**64
        and 19 * global_totals["incumbent"]["reverse_calls"] < 2**64
    )
    w2 = (
        global_totals["candidate"]["gated_kernel_calls"]
        < global_totals["incumbent"]["gated_kernel_calls"]
        and global_totals["incumbent"]["reverse_calls"] > 0
        and w2_multiply_ok
        and 20 * global_totals["candidate"]["reverse_calls"]
        <= 19 * global_totals["incumbent"]["reverse_calls"]
    )
    target_report = {}
    w3 = True
    for target in TARGETS:
        target_id = target["id"]
        totals = target_totals[target_id]
        passed = (
            totals["candidate"]["reverse_calls"] <= totals["incumbent"]["reverse_calls"]
            and totals["candidate"]["gated_kernel_calls"]
            <= totals["incumbent"]["gated_kernel_calls"]
        )
        w3 &= passed
        target_report[target_id] = {
            "incumbent": dict(totals["incumbent"]),
            "candidate": dict(totals["candidate"]),
            "reverse_ratio": (
                totals["candidate"]["reverse_calls"] / totals["incumbent"]["reverse_calls"]
                if totals["incumbent"]["reverse_calls"]
                else None
            ),
            "gated_kernel_ratio": totals["candidate"]["gated_kernel_calls"]
            / totals["incumbent"]["gated_kernel_calls"],
            "W3": passed,
        }
    gates = {
        "M1_completeness_authentication": m1,
        "M2_identity_C2": all_identity,
        "M3_health": all_health,
        "W1_84_pair_phases": w1 and phase_units == 84,
        "W2_global_strict_and_5pct": w2,
        "W3_target_nonincrease": w3,
    }
    passed = all(gates.values())
    verdict = (
        "QUALIFY_COARSEST_FIRST_OPT_IN_FOR_FINITE_OR_RECOVERABLE_TARGETS"
        if passed
        else "KEEP_FINEST_TO_COARSEST"
    )
    run_complete = json.loads((evidence / "RUN-COMPLETE.json").read_text())
    analysis = {
        "schema": "owalnuts-reverse-coarsening-order-v1-analysis",
        "process_counts": {
            "launch_markers": len(markers),
            "process_records": len(process_records),
            "raw_records": len(raw_records),
            "paired_blocks": len(pair_reports),
            "pair_phase_units": phase_units,
        },
        "gates": gates,
        "verdict": verdict,
        "defaults_changed": False,
        "global": {
            "incumbent": dict(global_totals["incumbent"]),
            "candidate": dict(global_totals["candidate"]),
            "reverse_ratio": global_totals["candidate"]["reverse_calls"]
            / global_totals["incumbent"]["reverse_calls"],
            "gated_kernel_ratio": global_totals["candidate"]["gated_kernel_calls"]
            / global_totals["incumbent"]["gated_kernel_calls"],
            "W2_integer_left": 20 * global_totals["candidate"]["reverse_calls"],
            "W2_integer_right": 19 * global_totals["incumbent"]["reverse_calls"],
        },
        "targets": target_report,
        "pairs": pair_reports,
        "validity": validity,
        "runtime": run_complete,
    }
    atomic_write(evidence / "analysis.json", canonical_json(analysis))
    write_reports(analysis)
    checksums()
    print(json.dumps({"gates": gates, "verdict": verdict}, indent=2))


def ratio(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.6f}"


def write_reports(analysis: dict[str, Any]) -> None:
    lines = [
        "# WP37B reverse coarsening order",
        "",
        "This directory contains the frozen preregistration, implementation, "
        "authenticated one-shot evidence, and mechanical analysis.",
        "",
        "## Result",
        "",
        f"Verdict: `{analysis['verdict']}`.",
        "",
        "| Gate | Pass |",
        "|---|---:|",
    ]
    lines.extend(
        f"| `{gate}` | `{str(passed).lower()}` |"
        for gate, passed in analysis["gates"].items()
    )
    lines.extend(
        [
            "",
            "## Work ratios",
            "",
            "| Target | reverse calls candidate/incumbent | gated kernel calls candidate/incumbent |",
            "|---|---:|---:|",
        ]
    )
    for target, report in analysis["targets"].items():
        lines.append(
            f"| `{target}` | {ratio(report['reverse_ratio'])} | "
            f"{ratio(report['gated_kernel_ratio'])} |"
        )
    lines.append(
        f"| **overall** | **{ratio(analysis['global']['reverse_ratio'])}** | "
        f"**{ratio(analysis['global']['gated_kernel_ratio'])}** |"
    )
    lines.extend(
        [
            "",
            "All 84 cells are one-shot records. Wall time and posterior diagnostics "
            "are descriptive only. Every Rust and Python default remains "
            "`FinestToCoarsest`.",
            "",
        ]
    )
    atomic_write(HERE / "README.md", "\n".join(lines).encode())
    ledger = [
        "### WP37B — reverse coarsening order mechanical qualification",
        f"- Verdict: `{analysis['verdict']}`.",
        "- Counts: 84 launch markers, 84 process records, 84 authenticated raw "
        "records, 42 paired blocks, 84 pair-phase units.",
        f"- Semantic/cause/forward identity: "
        f"`{analysis['gates']['M2_identity_C2']}`.",
        f"- Overall reverse-call ratio: `{ratio(analysis['global']['reverse_ratio'])}`; "
        f"gated-kernel-call ratio: `{ratio(analysis['global']['gated_kernel_ratio'])}`.",
        f"- Evidence wall: `{analysis['runtime']['wall_seconds']:.3f}` seconds.",
        "- Scope: mechanical qualification only; defaults, Python behavior, "
        "algorithm revision, replay, and fingerprints remain unchanged.",
        "",
    ]
    atomic_write(HERE / "LEDGER-ENTRY.md", "\n".join(ledger).encode())


def checksums() -> None:
    exclusions = {
        "CHECKSUMS.sha256",
        "target",
        "__pycache__",
        "analysis-temporary",
    }
    rows = []
    for path in sorted(
        (
            path
            for path in HERE.rglob("*")
            if path.is_file()
            and not any(part in exclusions for part in path.relative_to(HERE).parts)
            and not path.name.endswith(".tmp")
        ),
        key=lambda path: path.relative_to(HERE).as_posix().encode(),
    ):
        digest, _ = sha256_file(path)
        rows.append(f"{digest}  {path.relative_to(HERE).as_posix()}\n")
    atomic_write(HERE / "CHECKSUMS.sha256", "".join(rows).encode())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--binary", required=True)
    subparsers.add_parser("execute")
    subparsers.add_parser("analyze")
    subparsers.add_parser("check-conformance")
    subparsers.add_parser("checksums")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "prepare":
        prepare(args)
    elif args.command == "execute":
        execute(args)
    elif args.command == "analyze":
        analyze(args)
    elif args.command == "check-conformance":
        check_conformance()
    elif args.command == "checksums":
        checksums()
    else:
        raise AssertionError(args.command)


if __name__ == "__main__":
    main()




