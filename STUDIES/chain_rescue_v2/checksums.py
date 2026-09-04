#!/usr/bin/env python3
"""Write CHECKSUMS.sha256 for the WP36 protocol, harness, and durable artifacts."""

import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_FILES = [
    "PREREGISTRATION.md",
    "protocol.json",
    "AMENDMENT-1.md",
    "README.md",
    ".gitignore",
    "Cargo.toml",
    "Cargo.lock",
    "src/arms.rs",
    "src/main.rs",
    "src/bin/funnel.rs",
    "src/bin/conformance.rs",
    "run_rescue.py",
    "test_run_rescue.py",
    "checksums.py",
]
paths = [HERE / name for name in SOURCE_FILES]
paths.extend(
    sorted(
        path
        for path in (HERE / "artifacts").rglob("*")
        if path.is_file() and ".tmp-" not in path.name
    )
)
lines = [
    f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(HERE).as_posix()}"
    for path in paths
]
(HERE / "CHECKSUMS.sha256").write_text(
    "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
)
print(f"{len(lines)} files hashed")
