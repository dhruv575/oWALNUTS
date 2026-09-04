#!/usr/bin/env python3
"""Write the final WP37A SHA-256 inventory."""

import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXCLUDED = {
    HERE / "CHECKSUMS.sha256",
}


def included(path: Path) -> bool:
    if not path.is_file() or path in EXCLUDED:
        return False
    relative = path.relative_to(HERE)
    if any(part in {"target", ".venv", "__pycache__"} for part in relative.parts):
        return False
    return ".tmp-" not in path.name


paths = sorted(
    (path for path in HERE.rglob("*") if included(path)),
    key=lambda path: path.relative_to(HERE).as_posix(),
)
lines = [
    f"{hashlib.sha256(path.read_bytes()).hexdigest()}  "
    f"{path.relative_to(HERE).as_posix()}"
    for path in paths
]
(HERE / "CHECKSUMS.sha256").write_text(
    "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
)
print(f"{len(lines)} files hashed")
