#!/usr/bin/env python3
"""Write CHECKSUMS.sha256 over protocol, preregistration, sources, fixtures,
starts, and every artifact (including the large raw draws, which are hashed
but not committed)."""
from __future__ import annotations

import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
INCLUDE = ["protocol.json", "PREREGISTRATION.md", "README.md", "analyze.py", "checksums.py",
           "make_starts.py", "numpyro_state_space.py", "numpyro_funnel.py",
           "state_space/Cargo.toml", "state_space/Cargo.lock", "state_space/src/main.rs", "state_space/src/canonical.rs",
           "funnel/Cargo.toml", "funnel/Cargo.lock", "funnel/src/main.rs"]
DIRS = ["fixtures", "starts", "artifacts"]
REPO = HERE.parents[1]
EXTRA = [REPO / "src" / "walnutpie.rs", REPO / "src" / "kernel.rs", REPO / "Cargo.lock"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    lines = []
    files = [HERE / f for f in INCLUDE if (HERE / f).is_file()]
    for d in DIRS:
        files += sorted(p for p in (HERE / d).rglob("*") if p.is_file() and p.name != "CHECKSUMS.sha256")
    for p in files:
        lines.append(f"{sha(p)}  {p.relative_to(HERE).as_posix()}")
    for p in EXTRA:
        lines.append(f"{sha(p)}  {p.relative_to(REPO).as_posix()} (repository source)")
    (HERE / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(lines)} entries")


if __name__ == "__main__":
    main()
