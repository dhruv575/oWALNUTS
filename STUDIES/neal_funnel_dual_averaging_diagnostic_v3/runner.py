"""Checksum-bound process launcher for frozen diagnostic v3."""
import argparse, hashlib, json, os, subprocess, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXE = ROOT / "target" / "launch-validation" / "release" / "neal-funnel-dual-averaging-diagnostic-v3.exe"
CELLS, WALL = 12, 300

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def atomic_create(path, value):
    path = Path(path)
    if path.exists(): raise FileExistsError(path)
    fd, temporary = tempfile.mkstemp(prefix=path.name, suffix=".pending", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2); stream.flush(); os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)

def validate(path):
    value = json.loads(Path(path).read_text())
    required = {
        "authorized": True, "cells": CELLS, "callback_cap": 1_000_000_000,
        "wall_cap_seconds": WALL, "protocol_sha256": digest(ROOT/"protocol.json"),
        "rust_runner_sha256": digest(ROOT/"src"/"main.rs"),
        "launcher_sha256": digest(__file__), "analyzer_sha256": digest(ROOT/"analyze.py"),
        "kernel_sha256": digest(ROOT/".."/".."/"src"/"kernel.rs"),
        "facade_sha256": digest(ROOT/".."/".."/"src"/"walnutpie.rs"),
        "root_lock_sha256": digest(ROOT/".."/".."/"Cargo.lock"),
    }
    bad = [key for key, expected in required.items() if value.get(key) != expected]
    if bad: raise RuntimeError(f"authorization mismatch: {', '.join(bad)}")
    subprocess.run([EXE, "--validate-authorization", path], cwd=ROOT, check=True)

def run(path, output):
    validate(path)
    output.mkdir(exist_ok=False)
    for index in range(CELLS):
        try:
            subprocess.run([EXE, "--cell", str(index), output/f"cell-{index:02}.json", path],
                           cwd=ROOT, check=True, timeout=WALL)
        except subprocess.TimeoutExpired as error:
            atomic_create(output/f"cell-{index:02}.deadline.json",
                          {"cell_index":index,"reason":"hard process deadline","wall_cap_seconds":WALL})
            raise RuntimeError(f"cell {index} exceeded deadline") from error

if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--authorization",type=Path,required=True)
    parser.add_argument("--output",type=Path); parser.add_argument("--validate-only",action="store_true")
    args=parser.parse_args(); validate(args.authorization)
    if not args.validate_only:
        if args.output is None: parser.error("--output required")
        run(args.authorization,args.output)
