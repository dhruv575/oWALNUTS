#!/usr/bin/env python3
"""Build the frozen comparator and owned-worker diagnostic children."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[1]
COMPARATOR_COMMIT = "9edcbac"


def run(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--comparator-root",
        type=Path,
        default=Path(r"C:\dev\owalnuts-build-bridgestan-owned-comparator-9edcbac"),
    )
    parser.add_argument(
        "--toolchain",
        default="+1.88.0-x86_64-pc-windows-gnu",
    )
    args = parser.parse_args()
    destination = args.comparator_root.resolve()
    if destination.exists():
        raise SystemExit(f"refusing to replace comparator root: {destination}")
    destination.mkdir(parents=True)
    archive = destination.parent / f"{destination.name}.tar"
    if archive.exists():
        raise SystemExit(f"refusing to replace archive: {archive}")
    try:
        run(
            ["git", "archive", "--format=tar", "-o", str(archive), COMPARATOR_COMMIT],
            REPOSITORY,
        )
        with tarfile.open(archive) as source:
            source.extractall(destination, filter="data")
        comparator_study = destination / "STUDIES" / HERE.name
        (comparator_study / "src").mkdir(parents=True)
        shutil.copy2(HERE / "Cargo.toml", comparator_study / "Cargo.toml")
        shutil.copy2(HERE / "Cargo.lock", comparator_study / "Cargo.lock")
        shutil.copy2(HERE / "src" / "main.rs", comparator_study / "src" / "main.rs")
        run(
            [
                "cargo",
                args.toolchain,
                "build",
                "--release",
                "--locked",
                "--manifest-path",
                str(comparator_study / "Cargo.toml"),
            ],
            destination,
        )
        run(
            [
                "cargo",
                args.toolchain,
                "build",
                "--release",
                "--locked",
                "--manifest-path",
                str(HERE / "Cargo.toml"),
            ],
            REPOSITORY,
        )
    finally:
        archive.unlink(missing_ok=True)
    comparator = (
        comparator_study / "target" / "release" / "bridgestan-owned-worker-v1.exe"
    )
    owned = HERE / "target" / "release" / "bridgestan-owned-worker-v1.exe"
    print(f"comparator={comparator}")
    print(f"owned={owned}")


if __name__ == "__main__":
    main()
