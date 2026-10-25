#!/usr/bin/env python3
"""Build the WP50E replay child against this worktree's HEAD and lay out
exe-only launch directories: v5_owned, v5_unserialised (byte-identical copies)
and wp50d (a copy of the hash-pinned WP50D child exe).

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
ARMS = HERE / "build" / "arms"
V5_EXE = "bridgestan-windows-root-cause-v5.exe"
WP50D_EXE = "bridgestan-windows-root-cause-v4.exe"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if ARMS.exists():
        raise SystemExit(f"refusing to replace {ARMS}")
    env = dict(os.environ, RUSTUP_TOOLCHAIN=PROTOCOL["toolchain"])
    crate = HERE / "child" / "Cargo.toml"
    for args in (["test", "--release", "--locked", "--offline", "-j", "4"],
                 ["build", "--release", "--locked", "--offline", "-j", "4"]):
        subprocess.run(["cargo", *args, "--manifest-path", str(crate)], env=env, check=True)
    built = HERE / "child" / "target" / "release" / V5_EXE
    original = Path(PROTOCOL["assets"]["wp50d_exe"])
    if sha256(original) != PROTOCOL["assets"]["wp50d_exe_sha256"]:
        raise SystemExit("WP50D exe hash mismatch")
    layout = {"v5_owned": (built, V5_EXE), "v5_unserialised": (built, V5_EXE),
              "wp50d": (original, WP50D_EXE)}
    manifest = {
        "schema": "bridgestan-windows-root-cause-v5-build",
        "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "worktree_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPOSITORY,
                                                 text=True).strip(),
        "library_diff_vs_head": subprocess.check_output(
            ["git", "diff", "--stat", "HEAD", "--", "src", "integrations/bridgestan/src"],
            cwd=REPOSITORY, text=True),
        "toolchain": PROTOCOL["toolchain"],
        "v5_exe": {"bytes": built.stat().st_size, "sha256": sha256(built)},
        "wp50d_exe": {"source": str(original), "sha256": sha256(original)},
        "arms": {},
    }
    for name, (source, exe_name) in layout.items():
        directory = ARMS / name
        directory.mkdir(parents=True)
        shutil.copy2(source, directory / exe_name)
        manifest["arms"][name] = {"exe": str(directory / exe_name),
                                  "sha256": sha256(directory / exe_name),
                                  "directory_listing": sorted(p.name for p in directory.iterdir())}
    (HERE / "artifacts").mkdir(exist_ok=True)
    (HERE / "artifacts" / "build-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
