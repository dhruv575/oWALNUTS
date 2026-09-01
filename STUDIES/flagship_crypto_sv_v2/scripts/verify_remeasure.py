"""A8 guard: re-measured cells must reproduce the evidence draws bit-for-bit.

Compares artifacts-remeasure/draws/* against artifacts/draws/* (native .f64 by
SHA-256; pymc .npz array-by-array equality) and prints wall before/after.
Exits 1 if any re-measured cell differs, so its wall must NOT be swapped in.
"""

import hashlib
import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
EV = ROOT / "artifacts"
RM = ROOT / "artifacts-remeasure"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    bad, rows = [], []
    for run in sorted((RM / "runs").glob("*.json")):
        stem = run.stem
        ev_meta = EV / "runs" / f"{stem}.json"
        if not ev_meta.exists():
            continue
        f64, npz = RM / "draws" / f"{stem}.f64", RM / "draws" / f"{stem}.npz"
        if f64.exists():
            same = sha(f64) == sha(EV / "draws" / f"{stem}.f64")
        elif npz.exists():
            a, b = np.load(npz), np.load(EV / "draws" / f"{stem}.npz")
            same = all(np.array_equal(a[k], b[k]) for k in a.files)
        else:
            same = False
        m1, m2 = json.loads(ev_meta.read_text()), json.loads(run.read_text())
        w1 = m1.get("wall_sampling", m1.get("wall_seconds"))
        w2 = m2.get("wall_sampling", m2.get("wall_seconds"))
        rows.append((stem, same, w1, w2))
        if not same:
            bad.append(stem)
    for stem, same, w1, w2 in rows:
        print(f"{stem:28s} identical={str(same):5s} wall {w1:7.1f} -> {w2:7.1f} s  ({w1 / w2:.2f}x)")
    print(f"\n{len(rows)} cells compared; {len(bad)} differ")
    (RM / "verify.json").write_text(json.dumps(
        {"cells": [{"stem": s, "identical": i, "wall_contended": a, "wall_quiet": b} for s, i, a, b in rows],
         "all_identical": not bad}, indent=1))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
