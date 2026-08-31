"""Evidence orchestrator: calibrate + all cells for every asset, sequentially.

Usage: python scripts/run_all.py [SYMBOL ...]
"""

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PY = ROOT.parents[1] / "integrations" / "python" / ".venv" / "Scripts" / "python.exe"
BIN = ROOT / "target" / "release" / "flagship-crypto-sv-v1.exe"
SYMBOLS = sys.argv[1:] or ["BTC", "ETH", "XRP", "BNB", "SOL"]
NATIVE_SEEDS = [97001, 97002, 97003]
EXTERNAL_SEED = 97001


def run(cmd):
    print(">>", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True)


def done(sym, cell, seed):
    return (ROOT / "artifacts" / "runs" / f"{sym}-{cell}-{seed}.json").exists()


def main():
    for sym in SYMBOLS:
        data = ROOT / "data" / f"{sym}.json"
        for seed in NATIVE_SEEDS:
            cal = ROOT / "artifacts" / "calibration" / f"{sym}-{seed}.json"
            if not cal.exists():
                run([BIN, "calibrate", data, ROOT / "artifacts", seed])
            if not done(sym, "native", seed):
                run([BIN, "run", data, ROOT / "artifacts", seed, cal])
            if not done(sym, "pymc", seed):
                run([PY, ROOT / "scripts" / "run_python_cells.py", "pymc", sym, seed])
        if not done(sym, "nutpie", EXTERNAL_SEED):
            run([PY, ROOT / "scripts" / "run_python_cells.py", "nutpie", sym, EXTERNAL_SEED])
        if not done(sym, "numpyro", EXTERNAL_SEED):
            run([PY, ROOT / "scripts" / "run_python_cells.py", "numpyro", sym, EXTERNAL_SEED])


if __name__ == "__main__":
    main()
