"""Verify the pre-execution snapshot; later result files are not in this list."""
import hashlib
from pathlib import Path


def verify():
    root = Path(__file__).resolve().parent
    failures = []
    lines = (root / "CHECKSUMS.sha256").read_text(encoding="utf-8").splitlines()
    for line in lines:
        expected, relative = line.split("  ", 1)
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            failures.append(relative)
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            failures.append(relative)
    print(f"Checked {len(lines)} pre-execution files; {len(failures)} failures")
    if failures:
        raise SystemExit("\n".join(failures))


if __name__ == "__main__":
    verify()
