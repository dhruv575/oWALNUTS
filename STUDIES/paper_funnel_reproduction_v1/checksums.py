"""Write CHECKSUMS.sha256 for protocol, source, binary, and artifacts."""
import hashlib
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
files = [HERE / "protocol.json", HERE / "posthoc.json", HERE / "PREREGISTRATION.md",
         HERE / "src" / "main.rs", HERE / "Cargo.toml", HERE / "Cargo.lock",
         HERE / "reference_run.py", HERE / "reference_fixed36.py", HERE / "analyze.py",
         HERE / "posthoc_analyze.py", HERE / "target" / "release" / "paper-funnel-reproduction-v1.exe",
         ROOT / "src" / "walnutpie.rs", ROOT / "src" / "kernel.rs", ROOT / "Cargo.lock"]
files += sorted((HERE / "artifacts").glob("*.json"))
lines = []
for f in files:
    if f.is_file():
        rel = f.relative_to(ROOT).as_posix()
        lines.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {rel}")
(HERE / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
