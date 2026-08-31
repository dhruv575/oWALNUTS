"""Authorization-gated, process-isolated launcher for frozen pilot v2."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXE = ROOT / "target" / "launch-validation" / "release" / "neal-funnel-intervention-pilot-v2.exe"
CELLS = 12
WALL_SECONDS = 300


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_create(path: Path, value: object) -> None:
    if path.exists():
        raise FileExistsError(path)
    handle, temporary = tempfile.mkstemp(prefix=path.name, suffix=".pending", dir=path.parent)
    try:
        with os.fdopen(handle, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def validate_authorization(path: Path) -> dict:
    authorization = json.loads(path.read_text())
    required = {
        "authorized": True,
        "cells": CELLS,
        "callback_cap": 1_000_000_000,
        "wall_cap_seconds": WALL_SECONDS,
        "protocol_sha256": digest(ROOT / "protocol.json"),
        "rust_runner_sha256": digest(ROOT / "src" / "main.rs"),
        "launcher_sha256": digest(Path(__file__)),
        "analyzer_sha256": digest(ROOT / "analyze.py"),
        "kernel_sha256": digest(ROOT / ".." / ".." / "src" / "kernel.rs"),
        "facade_sha256": digest(ROOT / ".." / ".." / "src" / "walnutpie.rs"),
        "root_lock_sha256": digest(ROOT / ".." / ".." / "Cargo.lock"),
    }
    mismatches = [key for key, value in required.items() if authorization.get(key) != value]
    if mismatches:
        raise RuntimeError(f"authorization mismatch: {', '.join(mismatches)}")
    subprocess.run([EXE, "--validate-authorization", path], check=True, cwd=ROOT)
    return authorization


def run_grid(authorization: Path, output: Path) -> None:
    validate_authorization(authorization)
    output.mkdir(parents=False, exist_ok=False)
    for index in range(CELLS):
        artifact = output / f"cell-{index:02}.json"
        try:
            subprocess.run(
                [EXE, "--cell", str(index), artifact, authorization],
                check=True,
                cwd=ROOT,
                timeout=WALL_SECONDS,
            )
        except subprocess.TimeoutExpired as error:
            atomic_create(
                output / f"cell-{index:02}.deadline.json",
                {
                    "schema": "neal-funnel-intervention-pilot-v2-resource-failure",
                    "cell_index": index,
                    "wall_cap_seconds": WALL_SECONDS,
                    "reason": "hard process deadline",
                },
            )
            raise RuntimeError(f"cell {index} exceeded hard process deadline") from error


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    validate_authorization(args.authorization)
    if not args.validate_only:
        if args.output is None:
            parser.error("--output is required unless --validate-only")
        run_grid(args.authorization, args.output)


if __name__ == "__main__":
    main()
