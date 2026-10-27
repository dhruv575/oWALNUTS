"""Pin study sources and recovered evidence, including uncommitted compact draws."""
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
lines = []
for path in sorted(HERE.rglob("*")):
    if not path.is_file() or path.name == "CHECKSUMS.sha256" or "__pycache__" in path.parts or path.suffix == ".pyc":
        continue
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024*1024), b""):
            digest.update(block)
    lines.append(f"{digest.hexdigest()}  {path.relative_to(HERE).as_posix()}")
(HERE/"CHECKSUMS.sha256").write_text("\n".join(lines)+"\n", encoding="utf-8", newline="\n")
print(f"{len(lines)} files hashed")
