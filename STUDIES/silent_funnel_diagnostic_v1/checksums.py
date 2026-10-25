#!/usr/bin/env python3
"""Write CHECKSUMS.sha256 over the protocol, code and committed artifacts (raw draws excluded)."""
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = ["protocol.json", "PREREGISTRATION.md", "README.md", "LEDGER-ENTRY.md", "run_study.py", "make_reference.py", "posthoc.py", "compile_refs.py", "checksums.py",
         "Cargo.toml", "Cargo.lock", "src/main.rs", ".gitignore", "reference_models/seeds_ncp_reference.stan", "reference_models/radon_ncp_reference.stan"]
paths = [HERE / f for f in FILES if (HERE / f).exists()]
paths += sorted(p for p in (HERE / "artifacts").rglob("*") if p.is_file() and "raw" not in p.parts and "draws" not in p.parts)
lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(HERE).as_posix()}" for p in paths]
(HERE / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(lines)} files hashed")
