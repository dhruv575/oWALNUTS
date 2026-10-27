#!/usr/bin/env python3
"""Write CHECKSUMS.sha256 over the protocol, code and artifacts (raw draws included, uncommitted)."""
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = ["protocol.json", "PREREGISTRATION.md", "README.md", "LEDGER-ENTRY.md", "analyze.py", "checksums.py",
         "audit_recovery.py", "test_audit_recovery.py", "RECOVERY-AUDIT.md",
         "make_protocol.py", "simulate.py", "run_cells.py", ".gitignore",
         "models/data-shift.json", "models/data-control.json",
         "rust/Cargo.toml", "rust/Cargo.lock", "rust/src/main.rs"]
paths = [HERE / f for f in FILES if (HERE / f).exists()]
paths += sorted(p for p in (HERE / "box").rglob("*") if p.is_file())
paths += sorted(p for p in (HERE / "artifacts").rglob("*") if p.is_file())
lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(HERE).as_posix()}" for p in paths]
(HERE / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(lines)} files hashed")
