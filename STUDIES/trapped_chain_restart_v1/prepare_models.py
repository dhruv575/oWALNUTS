#!/usr/bin/env python3
"""WP67 model preparation on the Linux box (`STUDIES/trapped_chain_restart_v1`).

    taskset -c 12-15 ~/venv/bin/python prepare_models.py <bridgestan-src-dir>

Copies each posterior's Stan program and data out of the shared, read-only
posteriordb checkout (`protocol.json` -> posteriordb.path, pinned commit) into
`models/`, then builds every BridgeStan library with the BridgeStan 2.9.0
makefile (`make -j4 models/<short>_model.so`, no `STAN_THREADS`, the house
build: `ReplicatedStanTarget` loads one library copy per thread on Linux).
Writes `artifacts/models.json` with sha256 of every source, data file and
library. Reads posteriordb files directly (no `posteriordb` package on the box).
Not an evidence cell; it may be rerun.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
PDB = Path(os.path.expanduser(PROTOCOL["posteriordb"]["path"]))
MODELS = HERE / "models"


def short(model: str) -> str:
    return model.replace("-", "__")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def posterior_info(name: str) -> dict:
    return json.loads((PDB / "posteriors" / f"{name}.json").read_text(encoding="utf-8"))


def read_zip_json(path: Path):
    with zipfile.ZipFile(path) as z:
        inner = [n for n in z.namelist() if n.endswith(".json")][0]
        return json.loads(z.read(inner).decode("utf-8"))


def main() -> None:
    bs_src = Path(sys.argv[1]).resolve()
    MODELS.mkdir(exist_ok=True)
    models = [PROTOCOL["lotka_model"]] + PROTOCOL["regression_models"]
    record = {"bridgestan_src": str(bs_src), "posteriordb": str(PDB), "models": {}}
    for m in models:
        info = posterior_info(m)
        stan = MODELS / f"{short(m)}.stan"
        data = MODELS / f"{short(m)}.data.json"
        src = PDB / "models" / "stan" / f"{info['model_name']}.stan"
        stan.write_bytes(src.read_bytes())
        data.write_text(json.dumps(read_zip_json(PDB / "data" / "data" / f"{info['data_name']}.json.zip")), encoding="utf-8")
        so = MODELS / f"{short(m)}_model.so"
        t0 = time.time()
        if not so.exists():
            cp = subprocess.run(["make", "-j4", str(so)], cwd=bs_src, capture_output=True, text=True)
            if cp.returncode != 0:
                print(cp.stdout[-3000:], cp.stderr[-3000:])
                raise SystemExit(f"build failed: {m}")
        record["models"][m] = {"stan_sha256": sha(stan), "data_sha256": sha(data), "so_sha256": sha(so),
                               "model_name": info["model_name"], "data_name": info["data_name"],
                               "reference_posterior_name": info.get("reference_posterior_name"),
                               "build_seconds": round(time.time() - t0, 1)}
        print(m, record["models"][m], flush=True)
    (HERE / "artifacts").mkdir(exist_ok=True)
    (HERE / "artifacts" / "models.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
