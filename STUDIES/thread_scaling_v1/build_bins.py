#!/usr/bin/env python3
"""Build the WP45 harness binaries for each arm from a pinned library commit.

    python build_bins.py baseline            # library at the study base commit 3583d130
    python build_bins.py fixed <commit>      # library at the fix commit
    python build_bins.py both <fix-commit>

Each arm extracts the library and the two integration crates from git at the
named commit into build/<arm>-src/, copies this study's harness (Cargo.toml,
src/) from the working tree, builds `--release` with the GNU toolchain and
copies grid.exe / profile.exe to bin/<arm>/. The harness code is identical
across arms; only the owalnuts library differs.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE_COMMIT = "3583d130"
TOOLCHAIN = "1.88.0-x86_64-pc-windows-gnu"
PATHS = ["Cargo.toml", "Cargo.lock", "src", "integrations/autodiff", "integrations/bridgestan", "integrations/enzyme"]


def build(arm: str, commit: str) -> None:
    root = HERE / "build" / f"{arm}-src"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    archive = HERE / "build" / f"{arm}.tar"
    subprocess.run(["git", "archive", "--format=tar", "-o", str(archive), commit, *PATHS], cwd=REPO, check=True)
    with tarfile.open(archive) as t:
        t.extractall(root, filter="data")
    archive.unlink()
    study = root / "STUDIES" / HERE.name
    (study / "src").mkdir(parents=True)
    shutil.copy2(HERE / "Cargo.toml", study / "Cargo.toml")
    if (HERE / "Cargo.lock").exists():
        shutil.copy2(HERE / "Cargo.lock", study / "Cargo.lock")
    shutil.copytree(HERE / "src", study / "src", dirs_exist_ok=True)
    env = dict(os.environ, RUSTUP_TOOLCHAIN=TOOLCHAIN)
    subprocess.run(["cargo", "build", "--release", "--manifest-path", str(study / "Cargo.toml")], env=env, check=True)
    out = HERE / "bin" / arm
    out.mkdir(parents=True, exist_ok=True)
    for exe in ["grid.exe", "profile.exe"]:
        shutil.copy2(study / "target" / "release" / exe, out / exe)
    (out / "COMMIT").write_text(subprocess.run(["git", "rev-parse", commit], cwd=REPO, capture_output=True, text=True, check=True).stdout)
    print(f"built {arm} from {commit} -> {out}")


def main() -> None:
    arm = sys.argv[1]
    if arm in ("baseline", "both"):
        build("baseline", BASE_COMMIT)
    if arm in ("fixed", "both"):
        build("fixed", sys.argv[2])


if __name__ == "__main__":
    main()
