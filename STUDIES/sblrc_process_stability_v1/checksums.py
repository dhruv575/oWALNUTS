#!/usr/bin/env python3
"""Write CHECKSUMS.sha256 for the diagnostic protocol, code, and artifacts."""
from __future__ import annotations

import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXED = [
    ".gitignore",
    "Cargo.toml",
    "Cargo.lock",
    "PREREGISTRATION.md",
    "README.md",
    "checksums.py",
    "protocol.json",
    "run_stability.py",
    "src/main.rs",
    "test_run_stability.py",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


paths = [HERE / relative for relative in FIXED]
artifacts = HERE / "artifacts"
if artifacts.exists():
    paths.extend(
        path
        for path in sorted(artifacts.rglob("*"))
        if path.is_file() and "launches" not in path.parts
    )
missing = [path for path in paths if not path.is_file()]
if missing:
    raise SystemExit(f"missing checksum inputs: {missing}")
lines = [
    f"{digest(path)}  {path.relative_to(HERE).as_posix()}"
    for path in paths
]
(HERE / "CHECKSUMS.sha256").write_text(
    "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
)
print(f"{len(lines)} files hashed")
