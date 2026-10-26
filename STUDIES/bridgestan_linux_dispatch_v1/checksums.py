#!/usr/bin/env python3
"""Write CHECKSUMS.sha256 over the protocol, code and artifacts (uncommitted raw draws and heartbeats included)."""
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = ["protocol.json", "PREREGISTRATION.md", "AMENDMENTS.md", "README.md", "LEDGER-ENTRY.md", "run_bench.py",
         "run_latency.py", "run_stress.py", "build_models.py", "verdict.py", "checksums.py", "Cargo.toml", "Cargo.lock",
         ".gitignore", "src/main.rs", "src/bin/latency.rs", "src/bin/stress_child.rs"]
paths = [HERE / f for f in FILES if (HERE / f).exists()]
paths += sorted(p for p in (HERE / "artifacts").rglob("*") if p.is_file() and "cmdstan-output" not in p.parts)
lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(HERE).as_posix()}" for p in paths]
(HERE / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(lines)} files hashed")
