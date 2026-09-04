#!/usr/bin/env python3
"""Write or verify checkout-portable SHA-256 checksums for this study."""
from __future__ import annotations

import hashlib
import io
import subprocess
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "CHECKSUMS.sha256"
EXCLUDED_PARTS = {"target", "__pycache__", ".pytest_cache"}
TEXT_SUFFIXES = {
    ".json",
    ".lock",
    ".md",
    ".py",
    ".rs",
    ".sha256",
    ".stderr",
    ".stdout",
    ".toml",
    ".txt",
}


def included_files() -> list[Path]:
    return sorted(
        path
        for path in HERE.rglob("*")
        if path.is_file()
        and path != MANIFEST
        and not any(part in EXCLUDED_PARTS for part in path.relative_to(HERE).parts)
    )


def included_relative(relative: str) -> bool:
    path = Path(relative)
    return (
        path.name != MANIFEST.name
        and not any(part in EXCLUDED_PARTS for part in path.parts)
    )


def canonical_bytes(data: bytes, relative: str) -> bytes:
    path = Path(relative)
    if path.suffix.lower() in TEXT_SUFFIXES or path.name == ".gitattributes":
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return data


def digest(path: Path) -> str:
    relative = path.relative_to(HERE).as_posix()
    return hashlib.sha256(canonical_bytes(path.read_bytes(), relative)).hexdigest()


def git(*args: str, text: bool = False) -> subprocess.CompletedProcess:
    completed = subprocess.run(
        ["git", "-C", str(HERE), *args],
        capture_output=True,
        text=text,
        check=False,
    )
    if completed.returncode != 0:
        stderr = (
            completed.stderr.strip()
            if text
            else completed.stderr.decode(errors="replace").strip()
        )
        raise SystemExit(f"git {' '.join(args)} failed: {stderr}")
    return completed


def expected_checksums() -> dict[str, str]:
    expected: dict[str, str] = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        checksum, relative = line.split("  ", 1)
        if relative in expected:
            raise SystemExit(f"duplicate checksum entry: {relative}")
        expected[relative] = checksum
    return expected


def compare(label: str, expected: dict[str, str], actual: dict[str, str]) -> None:
    if expected == actual:
        return
    missing = sorted(expected.keys() - actual.keys())
    extra = sorted(actual.keys() - expected.keys())
    changed = sorted(
        name for name in expected.keys() & actual.keys() if expected[name] != actual[name]
    )
    raise SystemExit(
        f"{label} checksum mismatch: missing={missing}, extra={extra}, changed={changed}"
    )


def worktree_checksums() -> dict[str, str]:
    return {
        path.relative_to(HERE).as_posix(): digest(path)
        for path in included_files()
    }


def git_checksums() -> dict[str, str]:
    root = Path(git("rev-parse", "--show-toplevel", text=True).stdout.strip())
    prefix = HERE.relative_to(root).as_posix()
    archive = git(
        "archive",
        "--format=tar",
        "HEAD",
        "--",
        f":(top){prefix}",
    ).stdout
    actual = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
        for member in tar:
            if not member.isfile():
                continue
            relative = member.name
            if not included_relative(relative):
                continue
            extracted = tar.extractfile(member)
            if extracted is None:
                raise SystemExit(f"could not read Git blob: {relative}")
            actual[relative] = hashlib.sha256(
                canonical_bytes(extracted.read(), relative)
            ).hexdigest()
    return actual


def write() -> None:
    lines = [
        f"{digest(path)}  {path.relative_to(HERE).as_posix()}"
        for path in included_files()
    ]
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def verify_worktree() -> None:
    expected = expected_checksums()
    compare("worktree", expected, worktree_checksums())
    print(f"verified {len(expected)} files in worktree")


def verify() -> None:
    expected = expected_checksums()
    compare("worktree", expected, worktree_checksums())
    compare("Git HEAD", expected, git_checksums())
    print(f"verified {len(expected)} files in worktree and Git HEAD")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if command == "write":
        write()
    elif command == "verify-worktree":
        verify_worktree()
    elif command == "verify":
        verify()
    else:
        raise SystemExit("usage: checksums.py [write|verify-worktree|verify]")
