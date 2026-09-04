#!/usr/bin/env python3
"""Write or verify checkout-portable SHA-256 checksums for this study."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "CHECKSUMS.sha256"
EXCLUDED_PARTS = {"target", "__pycache__", ".pytest_cache"}
TEXT_SUFFIXES = {".json", ".md", ".py", ".rs", ".toml", ".txt", ".stderr", ".stdout"}


def included_files() -> list[Path]:
    return sorted(
        path
        for path in HERE.rglob("*")
        if path.is_file()
        and path != MANIFEST
        and not any(part in EXCLUDED_PARTS for part in path.relative_to(HERE).parts)
    )


def canonical_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES or path.name in {".gitattributes"}:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return data


def digest(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def write() -> None:
    lines = [f"{digest(path)}  {path.relative_to(HERE).as_posix()}" for path in included_files()]
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def verify() -> None:
    expected: dict[str, str] = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        checksum, relative = line.split("  ", 1)
        expected[relative] = checksum
    actual = {
        path.relative_to(HERE).as_posix(): digest(path)
        for path in included_files()
    }
    if expected != actual:
        missing = sorted(expected.keys() - actual.keys())
        extra = sorted(actual.keys() - expected.keys())
        changed = sorted(
            name for name in expected.keys() & actual.keys() if expected[name] != actual[name]
        )
        raise SystemExit(f"checksum mismatch: missing={missing}, extra={extra}, changed={changed}")
    print(f"verified {len(actual)} files")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if command == "write":
        write()
    elif command == "verify":
        verify()
    else:
        raise SystemExit("usage: checksums.py [write|verify]")
