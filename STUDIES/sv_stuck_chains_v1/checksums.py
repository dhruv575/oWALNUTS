#!/usr/bin/env python3
"""Write CHECKSUMS.sha256 over the protocol, code, models and every committed artifact file. The telemetry
.json.gz and draws .npz files stay on the study machine, out of git; their sha256 manifest
(artifacts/telemetry-hashes.sha256, written on the box with sha256sum) is committed and hashed here."""
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = ["protocol.json", "PREREGISTRATION.md", "README.md", "LEDGER-ENTRY.md", "run_study.py", "mechanism.py", "strip_draws.py",
         "checksums.py", "Cargo.toml", "Cargo.lock", ".gitignore", "src/bin/sv_cell.rs", "src/bin/pdb_cell.rs",
         "src/bin/funnel.rs", "models/data.json", "models/sv.stan", "models/simulate.py"]
SKIP = {"draws", "telemetry", "raw-tmp", "stan-tmp"}
paths = [HERE / f for f in FILES if (HERE / f).exists()] + sorted(
    p for p in (HERE / "artifacts").rglob("*") if p.is_file() and not (SKIP & set(p.parts)))
lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(HERE).as_posix()}" for p in paths]
(HERE / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(lines)} files hashed")
