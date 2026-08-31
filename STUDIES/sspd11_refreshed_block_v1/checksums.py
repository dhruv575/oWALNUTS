#!/usr/bin/env python3
"""Regenerate CHECKSUMS.sha256 (draw files hashed but not committed)."""
import hashlib
import os

lines, draws = [], []
for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in ("target", "__pycache__")]
    for f in sorted(files):
        p = os.path.join(root, f)
        rel = os.path.relpath(p, ".").replace(os.sep, "/")
        if rel == "CHECKSUMS.sha256":
            continue
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        if rel.endswith(".f64"):
            draws.append(f"{h}  {rel}  (raw draws, hashed, not committed)")
        else:
            lines.append(f"{h}  {rel}")
with open("CHECKSUMS.sha256", "w", newline="\n") as out:
    out.write("\n".join(sorted(lines) + sorted(draws)) + "\n")
print(len(lines), "files,", len(draws), "draw files hashed")
