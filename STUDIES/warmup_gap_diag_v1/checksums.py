#!/usr/bin/env python3
"""Write CHECKSUMS.sha256 over the study's code, notes and score tables."""
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = ["README.md", "LEDGER-ENTRY.md", "gen_sweep.py", "run_parallel.py", "analyze_sweep.py", "checksums.py", "Cargo.toml", "src/main.rs"]
paths = [HERE / f for f in FILES if (HERE / f).exists()] + sorted(p for p in (HERE / "artifacts").rglob("*") if p.is_file())
lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(HERE).as_posix()}" for p in paths]
(HERE / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(lines)} files hashed")
