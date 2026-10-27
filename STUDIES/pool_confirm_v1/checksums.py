#!/usr/bin/env python3
"""Write CHECKSUMS.sha256 over the protocol, code, data, box scripts and every file under artifacts (raw draws included)."""
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = ["protocol.json", "PREREGISTRATION.md", "README.md", "LEDGER-ENTRY.md", "make_protocol.py", "run_cells.py", "analyze.py",
         "checksums.py", ".gitignore", "models/data-sim.json", "models/data-real.json", "rust/Cargo.toml", "rust/Cargo.lock",
         "rust/src/main.rs", "box/env.sh", "box/build.sh", "box/lane.sh", "box/smoke.sh"]
paths = [HERE / f for f in FILES if (HERE / f).exists()] + sorted(p for p in (HERE / "artifacts").rglob("*") if p.is_file())
lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(HERE).as_posix()}" for p in paths]
(HERE / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(lines)} files hashed")
