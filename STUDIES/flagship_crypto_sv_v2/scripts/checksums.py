"""Write CHECKSUMS.sha256 over the study's inputs, code, and artifacts."""

import hashlib
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
INCLUDE = ["PREREGISTRATION.md", "protocol.json", "README.md", "Cargo.toml",
           "src/main.rs"]
GLOBS = ["data/*.json", "scripts/*.py", "artifacts/runs/*.json",
         "artifacts/calibration/*.json", "artifacts/summary.json",
         "artifacts/RESULTS.md", "artifacts/parity-*.json",
         "artifacts/draws/*.npz", "artifacts/draws/*.f64", "figures/*.png"]


def main():
    paths = [ROOT / p for p in INCLUDE if (ROOT / p).exists()]
    for pattern in GLOBS:
        paths.extend(sorted(ROOT.glob(pattern)))
    lines = []
    for p in paths:
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        lines.append(f"{digest}  {p.relative_to(ROOT).as_posix()}")
    (ROOT / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n")
    print(f"hashed {len(paths)} files")


if __name__ == "__main__":
    main()
