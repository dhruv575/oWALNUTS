"""Evidence orchestrator for v2: calibrate + native + pymc cells, resumable.

Usage: python scripts/run_evidence.py <ARM>   (ARM in {B, C}, frozen by A3)

Runs, per asset in {BTC, ETH, XRP, BNB, SOL} and per seed in {98001..98003}:
  1. stage-A calibration (native binary, seed-tied) if missing;
  2. native-v2 cell (run2 <arm> label "native") if missing;
  3. pymc-v2 cell (run_python_cells.py pymc <sym> <seed> <ARM>) if missing.
External nutpie/numpyro cells are NOT run (v1 references, cited by hash).
"""

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BIN = ROOT / "target" / "release" / "flagship-crypto-sv-v2.exe"
PY = ROOT.parents[1] / "integrations" / "python" / ".venv" / "Scripts" / "python.exe"
SYMBOLS = ["BTC", "ETH", "XRP", "BNB", "SOL"]
SEEDS = [98001, 98002, 98003]


def run(cmd):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True)


def done(sym, cell, seed):
    return (ROOT / "artifacts" / "runs" / f"{sym}-{cell}-{seed}.json").exists()


def main():
    arm = sys.argv[1]
    assert arm in ("B", "C", "E"), "frozen evidence arm must be B, C or E (A3/A4)"
    for sym in SYMBOLS:
        data = ROOT / "data" / f"{sym}.json"
        for seed in SEEDS:
            cal = ROOT / "artifacts" / "calibration" / f"{sym}-{seed}.json"
            if not cal.exists():
                run([BIN, "calibrate", data, ROOT / "artifacts", seed])
            if not done(sym, "native", seed):
                run([BIN, "run2", data, ROOT / "artifacts", seed, cal, arm, "native"])
            if not done(sym, "pymc", seed):
                run([PY, ROOT / "scripts" / "run_python_cells.py", "pymc", sym, seed, arm])
    print("evidence grid complete")


if __name__ == "__main__":
    main()
