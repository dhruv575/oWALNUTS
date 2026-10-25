#!/usr/bin/env python3
"""Build the WP50D gate child against this worktree's HEAD and lay out one
exe-only launch directory per arm (byte-identical copies, so the Event 1000
application path identifies the arm).

    python build_child.py          # refuses to replace an existing build/arms
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[1]
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
TOOLCHAIN = PROTOCOL["toolchain"]
EXE_NAME = "bridgestan-windows-root-cause-v4.exe"
ARMS = HERE / "build" / "arms"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if ARMS.exists():
        raise SystemExit(f"refusing to replace {ARMS}")
    env = dict(os.environ, RUSTUP_TOOLCHAIN=TOOLCHAIN)
    crate = HERE / "child" / "Cargo.toml"
    for args in (["test", "--release", "--locked", "--offline", "-j", "4"],
                 ["build", "--release", "--locked", "--offline", "-j", "4"]):
        subprocess.run(["cargo", *args, "--manifest-path", str(crate)], env=env, check=True)
    built = HERE / "child" / "target" / "release" / EXE_NAME
    digest = sha256(built)
    manifest = {
        "schema": "bridgestan-windows-root-cause-v4-build",
        "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "worktree_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPOSITORY,
                                                 text=True).strip(),
        "library_diff_vs_head": subprocess.check_output(
            ["git", "diff", "--stat", "HEAD", "--", "src", "integrations/bridgestan/src"],
            cwd=REPOSITORY, text=True),
        "toolchain": TOOLCHAIN,
        "child_exe": {"bytes": built.stat().st_size, "sha256": digest},
        "arms": {},
    }
    for arm in PROTOCOL["arms"]:
        directory = ARMS / arm
        directory.mkdir(parents=True)
        shutil.copy2(built, directory / EXE_NAME)
        if sha256(directory / EXE_NAME) != digest:
            raise SystemExit("exe copy differs from the built child")
        manifest["arms"][arm] = {"directory": str(directory),
                                 "directory_listing": sorted(p.name for p in directory.iterdir())}
    (HERE / "artifacts").mkdir(exist_ok=True)
    (HERE / "artifacts" / "build-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
