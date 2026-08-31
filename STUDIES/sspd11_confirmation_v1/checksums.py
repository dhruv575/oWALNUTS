#!/usr/bin/env python3
"""Write CHECKSUMS.sha256 over protocol, sources, fixtures, starts, artifacts and the kernel source."""
from __future__ import annotations

import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
INCLUDE = ["PREREGISTRATION.md", "README.md", "analyze.py", "checksums.py",
           "primary/protocol.json", "primary/Cargo.toml", "primary/Cargo.lock", "primary/src/main.rs", "primary/src/canonical.rs",
           "stock_watson/protocol.json", "stock_watson/Cargo.toml", "stock_watson/Cargo.lock", "stock_watson/src/main.rs"]
GLOBS = ["primary/fixtures/*.json", "primary/starts/*.json", "primary/artifacts/*.txt",
         "primary/artifacts/primary-v1/*.json", "primary/artifacts/primary-v1/draws/*.f64",
         "stock_watson/artifacts/*.json", "stock_watson/artifacts/*.log", "artifacts/*.json", "artifacts/*.md"]
KERNEL = ["src/kernel.rs", "src/walnutpie.rs", "Cargo.lock"]


def main() -> None:
    files = [HERE / f for f in INCLUDE if (HERE / f).exists()]
    for g in GLOBS:
        files.extend(sorted(HERE.glob(g)))
    lines, seen = [], set()
    for f in files:
        rel = f.relative_to(HERE).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        lines.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {rel}")
    for k in KERNEL:
        p = REPO / k
        if p.exists():
            lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  ../../{k}")
    (HERE / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(lines)} files")


if __name__ == "__main__":
    main()
