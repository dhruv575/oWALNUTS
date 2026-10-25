#!/usr/bin/env python3
"""Build the competitor binaries before the first evidence cell (infrastructure, not evidence).

- CmdStan 2.39.0 executables in models/cmdstan/ via cmdstanpy 1.3.0 defaults.
  Three (diamonds, gp_pois_regr, accel_gp) were copied from the sibling WP48
  build of the same source; the other 19 are compiled here.
- nutpie 0.16.8 BridgeStan libraries in models/nutpie/: exactly the call that
  `nutpie.compile_stan_model(filename=...)` makes (`bridgestan.compile_model`
  with `make_args=["STAN_THREADS=true"]` on the same posteriordb Stan program),
  but into a persistent directory so that the cells can load it instead of
  recompiling. The cell then builds the same `CompiledStanModel` object that
  `compile_stan_model` returns (see run_posteriordb.py::nutpie_model).

Runs a small process pool (compilation only; no sampling happens here) and
writes artifacts/compile-status.json.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("MAKE", "mingw32-make")
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8")) if (HERE / "protocol.json").exists() else None
MODELS = PROTOCOL["models"] if PROTOCOL else [
    "eight_schools-eight_schools_noncentered", "eight_schools-eight_schools_centered", "diamonds-diamonds",
    "earnings-logearn_interaction", "mesquite-logmesquite_logvash", "kidiq-kidscore_momhsiq", "sblrc-blr",
    "nes2000-nes", "arK-arK", "arma-arma11", "garch-garch11", "gp_pois_regr-gp_pois_regr",
    "hmm_example-hmm_example", "bball_drive_event_0-hmm_drive_0", "one_comp_mm_elim_abs-one_comp_mm_elim_abs",
    "hudson_lynx_hare-lotka_volterra", "mcycle_gp-accel_gp",
    "GLMM_Poisson_data-GLMM_Poisson_model", "seeds_data-seeds_centered_model", "kilpisjarvi_mod-kilpisjarvi",
    "science_irt-grsm_latent_reg_irt", "radon_all-radon_hierarchical_intercept_centered",
]
COPIED = ("diamonds-diamonds", "gp_pois_regr-gp_pois_regr", "mcycle_gp-accel_gp")
CMDSTAN_HOME = Path(r"C:\dev\polyscope\STUDIES\matched_competitor_eight_schools_v38\cmdstan\cmdstan-2.39.0")
PDB = HERE / "posteriordb" / "posterior_database"
CMD = HERE / "models" / "cmdstan"
NUT = HERE / "models" / "nutpie"


def source(model: str) -> Path:
    from posteriordb import PosteriorDatabase

    return Path(PosteriorDatabase(str(PDB)).posterior(model).model.code_file_path("stan"))


def build(kind: str, model: str) -> tuple[str, str, dict]:
    short = model.replace("-", "__")
    t = time.perf_counter()
    try:
        if kind == "cmdstan":
            import cmdstanpy

            cmdstanpy.set_cmdstan_path(str(CMDSTAN_HOME))
            stan = CMD / f"{short}.stan"
            if not stan.exists():
                shutil.copyfile(source(model), stan)
            if (CMD / f"{short}.exe").exists():
                return kind, model, {"status": "present", "source": "copied from sibling WP48 build" if model in COPIED else "compiled here"}
            cmdstanpy.CmdStanModel(stan_file=str(stan))
        else:
            import bridgestan

            stan = NUT / f"{short}.stan"
            if not stan.exists():
                shutil.copyfile(source(model), stan)
            if stan.with_name(f"{short}_model.so").exists():
                return kind, model, {"status": "present", "source": "compiled here"}
            bridgestan.compile_model(stan, make_args=["STAN_THREADS=true"], stanc_args=[])
        return kind, model, {"status": "compiled", "seconds": round(time.perf_counter() - t, 1), "source": "compiled here"}
    except Exception as e:  # noqa: BLE001
        return kind, model, {"status": "error", "error": str(e)[-1500:]}


def main() -> None:
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    CMD.mkdir(parents=True, exist_ok=True)
    NUT.mkdir(parents=True, exist_ok=True)
    status_path = HERE / "artifacts" / "compile-status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
    tasks = [(k, m) for m in MODELS for k in ("cmdstan", "nutpie")]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(build, k, m) for k, m in tasks]
        for f in as_completed(futures):
            kind, model, st = f.result()
            status.setdefault(kind, {})[model] = st
            print(f"[{time.strftime('%H:%M:%S')}] {kind} {model}: {st}", flush=True)
            status_path.write_text(json.dumps(status, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
