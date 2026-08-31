#!/usr/bin/env python3
"""Write CHECKSUMS.sha256 over protocol, sources, fixtures, starts and artifacts."""
from __future__ import annotations

import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
INCLUDE = ["PREREGISTRATION.md", "protocol.json", "Cargo.toml", "Cargo.lock", "src/main.rs", "src/canonical.rs",
           "make_starts.py", "numpyro_reference.py", "analyze.py", "README.md"]
GLOBS = ["fixtures/*.json", "starts/*.json", "artifacts/numpyro/*.json", "artifacts/numpyro/*.npy",
         "artifacts/owalnuts-v*/*.json", "artifacts/owalnuts-v*/*.md", "artifacts/owalnuts-v*/draws/*.f64",
         "artifacts/*.txt", "artifacts/owalnuts-v*/log.txt"]


def main() -> None:
    files = [HERE / f for f in INCLUDE if (HERE / f).exists()]
    for g in GLOBS:
        files.extend(sorted(HERE.glob(g)))
    lines = []
    seen = set()
    for f in files:
        rel = f.relative_to(HERE).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        lines.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {rel}")
    (HERE / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(lines)} files")


if __name__ == "__main__":
    main()
