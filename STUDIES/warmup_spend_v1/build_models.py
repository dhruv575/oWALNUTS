#!/usr/bin/env python3
"""WP73: build every library and executable before the first cell (infrastructure, not evidence).

A copy of STUDIES/accel_gp_gap_v1/build_models.py (WP70) for the 17 house models of protocol.json,
with a third kind for nutpie:

    python build_models.py [workers]

* `models/<short>.data.json` and `models/src/<short>.stan` from posteriordb (protocol commit).
* `models/nothreads/<short>_model.so`: BridgeStan 2.9.0 make, no STAN_THREADS (the v7 build and the
  WP65-qualified replicated dispatch), in the lane's BridgeStan tree `bs-nothreads/bridgestan-2.9.0`.
* `models/nutpie/<short>_model.so`: the same make with `STAN_THREADS=true`, in the separate tree
  `bs-threads/bridgestan-2.9.0`. This is the make call `nutpie.compile_stan_model` makes through
  `bridgestan.compile_model(stan, make_args=["STAN_THREADS=true"])` (v7 / WP64 recipe), run here
  directly so that nothing is written outside the lane.
* `models/cmdstan/<short>` executables via cmdstanpy 1.3.0 defaults against the lane's byte copy
  of CmdStan 2.39.0.

The first library of each tree is built alone (it also builds TBB and the Stan Math libraries
in that tree); the rest run on a small process pool. Writes artifacts/build-manifest.json.
Run under `taskset -c 4-7`.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
LANE = Path(os.environ.get("WP73_LANE", "~/lanes/warmup_spend_v1")).expanduser()
PDB = Path(os.environ.get("WP73_POSTERIORDB", "~/infra/posteriordb")).expanduser() / PROTOCOL["posteriordb"]["path"]
TREES = {"nothreads": LANE / "bs-nothreads" / "bridgestan-2.9.0", "nutpie": LANE / "bs-threads" / "bridgestan-2.9.0"}
MAKE_ARGS = {"nothreads": [], "nutpie": ["STAN_THREADS=true"]}
CMDSTAN_HOME = LANE / "cmdstan-2.39.0"
MODELS = HERE / "models"


def short(model: str) -> str:
    return model.replace("-", "__")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_sources(models: list[str]) -> dict:
    from posteriordb import PosteriorDatabase

    db = PosteriorDatabase(str(PDB))
    out = {}
    (MODELS / "src").mkdir(parents=True, exist_ok=True)
    for m in models:
        p = db.posterior(m)
        stan = MODELS / "src" / f"{short(m)}.stan"
        shutil.copyfile(p.model.code_file_path("stan"), stan)
        data = MODELS / f"{short(m)}.data.json"
        data.write_text(json.dumps(p.data.values()), encoding="utf-8")
        out[m] = {"stan_sha256": sha256(stan), "data_sha256": sha256(data)}
    return out


def build_bridgestan(build: str, model: str) -> tuple[str, str, dict]:
    t = time.perf_counter()
    d = MODELS / build
    d.mkdir(parents=True, exist_ok=True)
    stan = d / f"{short(model)}.stan"
    shutil.copyfile(MODELS / "src" / f"{short(model)}.stan", stan)
    so = d / f"{short(model)}_model.so"
    if so.exists():
        return build, model, {"status": "present", "sha256": sha256(so)}
    cmd = ["make", "-C", str(TREES[build]), *MAKE_ARGS[build], str(so)]
    cp = subprocess.run(cmd, capture_output=True, text=True)
    if cp.returncode != 0 or not so.exists():
        return build, model, {"status": "error", "cmd": cmd, "stderr": cp.stderr[-3000:]}
    return build, model, {"status": "compiled", "cmd": cmd, "seconds": round(time.perf_counter() - t, 1),
                          "bytes": so.stat().st_size, "sha256": sha256(so)}


def build_cmdstan(model: str) -> tuple[str, str, dict]:
    import cmdstanpy

    t = time.perf_counter()
    cmdstanpy.set_cmdstan_path(str(CMDSTAN_HOME))
    d = MODELS / "cmdstan"
    d.mkdir(parents=True, exist_ok=True)
    stan = d / f"{short(model)}.stan"
    shutil.copyfile(MODELS / "src" / f"{short(model)}.stan", stan)
    try:
        m = cmdstanpy.CmdStanModel(stan_file=str(stan))
        exe = Path(m.exe_file)
        return "cmdstan", model, {"status": "compiled", "seconds": round(time.perf_counter() - t, 1),
                                  "exe": exe.name, "sha256": sha256(exe)}
    except Exception as e:  # noqa: BLE001
        return "cmdstan", model, {"status": "error", "error": str(e)[-3000:]}


def tool_versions() -> dict:
    def sh(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip()
        except Exception as e:  # noqa: BLE001
            return f"unavailable: {e}"
    return {"gxx": sh(["g++", "--version"]).splitlines()[:1], "make": sh(["make", "--version"]).splitlines()[:1],
            "bridgestan_trees": {b: str(t) for b, t in TREES.items()}, "cmdstan_home": str(CMDSTAN_HOME),
            "bridgestan_stanc": {b: sh([str(t / "bin" / "stanc"), "--version"]) for b, t in TREES.items()},
            "bridgestan_tarball_sha256": (LANE / "logs" / "bridgestan-tarball.sha256").read_text().strip()
            if (LANE / "logs" / "bridgestan-tarball.sha256").exists() else None}


def main() -> None:
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    models = PROTOCOL["house_models"]
    manifest_path = HERE / "artifacts" / "build-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"sources": prepare_sources(models), "libraries": {}, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    def record(kind, model, st):
        manifest["libraries"].setdefault(kind, {})[model] = st
        print(f"[{time.strftime('%H:%M:%S')}] {kind} {model}: {st.get('status')} {st.get('seconds', '')} {st.get('stderr', st.get('error', ''))[-500:]}", flush=True)
        manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    first = models[0]
    for build in TREES:  # first build alone per tree (TBB, Stan Math libraries)
        record(*build_bridgestan(build, first))
    record(*build_cmdstan(first))  # alone: may build CmdStan's shared objects in the lane copy
    tasks = [("bs", b, m) for m in models[1:] for b in TREES] + [("cmd", "cmdstan", m) for m in models[1:]]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(build_bridgestan, b, m) if k == "bs" else pool.submit(build_cmdstan, m) for k, b, m in tasks]
        for f in as_completed(futures):
            record(*f.result())
    manifest["tools"] = tool_versions()
    manifest["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
