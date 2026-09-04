#!/usr/bin/env python3
"""Write or verify checkout-portable checksums for the archived study."""
from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "CHECKSUMS.sha256"
FIXED = [
    ".gitignore",
    ".gitattributes",
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


def canonical_lf(data: bytes, source: str) -> bytes:
    """Return UTF-8 text with checkout-specific line endings normalized."""
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SystemExit(f"{source}: checksum input is not UTF-8 text") from error
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def digest(data: bytes, source: str) -> str:
    return hashlib.sha256(canonical_lf(data, source)).hexdigest()


def worktree_paths() -> list[Path]:
    paths = [Path(relative) for relative in FIXED]
    artifacts = HERE / "artifacts"
    if artifacts.exists():
        paths.extend(
            path.relative_to(HERE)
            for path in sorted(artifacts.rglob("*"))
            if path.is_file()
        )
    return paths


def worktree_read(relative: Path) -> bytes:
    path = HERE / relative
    if not path.is_file():
        raise SystemExit(f"missing checksum input: {relative.as_posix()}")
    return path.read_bytes()


def repository() -> tuple[Path, str]:
    root = Path(
        subprocess.check_output(
            ["git", "-C", str(HERE), "rev-parse", "--show-toplevel"],
            text=True,
        ).strip()
    )
    return root, HERE.relative_to(root).as_posix()


def git_read(root: Path, prefix: str, revision: str, relative: Path) -> bytes:
    spec = f"{revision}:{prefix}/{relative.as_posix()}"
    try:
        return subprocess.check_output(["git", "-C", str(root), "show", spec])
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"cannot read Git blob {spec}") from error


def git_paths(root: Path, prefix: str, revision: str) -> list[Path]:
    artifact_names = subprocess.check_output(
        [
            "git",
            "-C",
            str(root),
            "ls-tree",
            "-r",
            "--name-only",
            revision,
            "--",
            f"{prefix}/artifacts",
        ],
        text=True,
    ).splitlines()
    paths = [Path(relative) for relative in FIXED]
    paths.extend(
        Path(name.removeprefix(f"{prefix}/"))
        for name in artifact_names
    )
    return paths


def render(paths: list[Path], read: Callable[[Path], bytes]) -> str:
    lines = [
        f"{digest(read(path), path.as_posix())}  {path.as_posix()}"
        for path in paths
    ]
    return "\n".join(lines) + "\n"


def parse_manifest(data: bytes, source: str) -> list[tuple[str, Path]]:
    text = canonical_lf(data, source).decode("utf-8")
    entries: list[tuple[str, Path]] = []
    seen: set[Path] = set()
    for number, line in enumerate(text.splitlines(), start=1):
        try:
            checksum, name = line.split("  ", maxsplit=1)
        except ValueError as error:
            raise SystemExit(f"{source}:{number}: malformed checksum line") from error
        relative = Path(name)
        malformed = len(checksum) != 64 or any(
            character not in "0123456789abcdef" for character in checksum
        )
        if malformed:
            raise SystemExit(f"{source}:{number}: malformed SHA-256")
        if relative in seen:
            raise SystemExit(f"{source}:{number}: duplicate path {name}")
        seen.add(relative)
        entries.append((checksum, relative))
    return entries


def verify(
    entries: list[tuple[str, Path]],
    expected_paths: list[Path],
    read: Callable[[Path], bytes],
    source: str,
) -> None:
    manifest_paths = [path for _, path in entries]
    if manifest_paths != expected_paths:
        missing = [path.as_posix() for path in expected_paths if path not in manifest_paths]
        extra = [path.as_posix() for path in manifest_paths if path not in expected_paths]
        raise SystemExit(
            f"{source}: manifest path mismatch; missing={missing}, extra={extra}"
        )
    failures = []
    for expected, path in entries:
        actual = digest(read(path), path.as_posix())
        if actual != expected:
            failures.append(f"{path.as_posix()}: expected {expected}, got {actual}")
    if failures:
        raise SystemExit("\n".join(failures))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        nargs="?",
        choices=("write", "verify", "verify-git"),
        default="write",
    )
    parser.add_argument("revision", nargs="?", default="HEAD")
    args = parser.parse_args()

    if args.command == "write":
        paths = worktree_paths()
        MANIFEST.write_bytes(render(paths, worktree_read).encode("utf-8"))
        print(f"{len(paths)} canonical-LF files hashed")
        return

    if args.command == "verify":
        entries = parse_manifest(MANIFEST.read_bytes(), MANIFEST.name)
        paths = worktree_paths()
        verify(entries, paths, worktree_read, "worktree")
        print(f"verified {len(entries)} canonical-LF worktree files")
        return

    root, prefix = repository()
    manifest_relative = MANIFEST.relative_to(HERE)
    entries = parse_manifest(
        git_read(root, prefix, args.revision, manifest_relative),
        f"{args.revision}:{MANIFEST.name}",
    )
    paths = git_paths(root, prefix, args.revision)
    verify(
        entries,
        paths,
        lambda path: git_read(root, prefix, args.revision, path),
        f"Git revision {args.revision}",
    )
    print(f"verified {len(entries)} canonical-LF files at Git revision {args.revision}")


if __name__ == "__main__":
    main()
