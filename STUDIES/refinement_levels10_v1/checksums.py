#!/usr/bin/env python3
"""Write CHECKSUMS.sha256 over the protocol, code and committed artifacts."""
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = ["protocol.json", "PREREGISTRATION.md", "AMENDMENTS.md", "README.md", "LEDGER-ENTRY.md", "run_study.py", "checksums.py",
         "Cargo.toml", "Cargo.lock", "src/bin/funnel.rs", "src/bin/pdb.rs", ".gitignore"]
paths = [HERE / f for f in FILES if (HERE / f).exists()] + sorted(
    p for p in (HERE / "artifacts").rglob("*") if p.is_file())
lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(HERE).as_posix()}" for p in paths]
(HERE / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(lines)} files hashed")
