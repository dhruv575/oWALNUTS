#!/usr/bin/env python3
"""Build the WP50C Phase B child against the integration's reproducing commit 9edcbac.

    python build_child.py          # refuses to replace an existing build/

1. `git archive 9edcbac` into `build/tree-9edcbac/` (gitignored).
2. Copy this study's committed `child/` crate into
   `build/tree-9edcbac/STUDIES/bridgestan_windows_root_cause_v3/` so its
   relative path dependencies resolve to the 9edcbac sampler and BridgeStan
   integration, and build it `--release --locked` with the GNU toolchain.
3. Create `build/child/arms/plain/` holding only a copy of the child exe (no
   runtime DLL), so any runtime DLL a model binds comes from the launcher's
   PATH (WinLibs under the PowerShell registry PATH).
4. Write `artifacts/phase-b-build-manifest.json` (commit, toolchain, hashes).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[1]
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
COMMIT = PROTOCOL["phase_b"]["code_path_commit"]
TOOLCHAIN = PROTOCOL["toolchain"]
BUILD = HERE / "build" / "child"
TREE = BUILD / "tree-9edcbac"
ARMS = BUILD / "arms"
EXE_NAME = "bridgestan-windows-root-cause-v3.exe"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if BUILD.exists():
        raise SystemExit(f"refusing to replace existing build directory: {BUILD}")
    BUILD.mkdir()
    archive = BUILD / "tree.tar"
    subprocess.run(
        ["git", "archive", "--format=tar", "-o", str(archive), COMMIT],
        cwd=REPOSITORY,
        check=True,
    )
    with tarfile.open(archive) as source:
        source.extractall(TREE, filter="data")
    archive.unlink()
    crate = TREE / "STUDIES" / HERE.name
    crate.mkdir(parents=True)
    shutil.copy2(HERE / "child" / "Cargo.toml", crate / "Cargo.toml")
    shutil.copy2(HERE / "child" / "Cargo.lock", crate / "Cargo.lock")
    shutil.copytree(HERE / "child" / "src", crate / "src")
    env = dict(os.environ, RUSTUP_TOOLCHAIN=TOOLCHAIN)
    for args in (["test", "--release", "--locked"], ["build", "--release", "--locked"]):
        subprocess.run(
            ["cargo", *args, "--manifest-path", str(crate / "Cargo.toml")],
            cwd=TREE,
            env=env,
            check=True,
        )
    built = crate / "target" / "release" / EXE_NAME
    manifest = {
        "schema": "bridgestan-windows-root-cause-v3-build",
        "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "code_path_commit": subprocess.check_output(
            ["git", "rev-parse", COMMIT], cwd=REPOSITORY, text=True
        ).strip(),
        "toolchain": TOOLCHAIN,
        "child_exe": {"bytes": built.stat().st_size, "sha256": sha256(built)},
        "arms": {},
    }
    directory = ARMS / "plain"
    directory.mkdir(parents=True)
    shutil.copy2(built, directory / EXE_NAME)
    if sha256(directory / EXE_NAME) != manifest["child_exe"]["sha256"]:
        raise SystemExit("exe copy differs from the built child")
    manifest["arms"]["plain"] = {"directory": str(directory),
                                 "directory_listing": sorted(p.name for p in directory.iterdir())}
    (HERE / "artifacts").mkdir(exist_ok=True)
    (HERE / "artifacts" / "phase-b-build-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
