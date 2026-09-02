"""Build the three wall-gap models under several BridgeStan make configurations.

    python build_variants.py <variant> [<variant> ...]

Variants (make_args passed to bridgestan.compile_model):
  v1                      STAN_THREADS=true                       (the v1 study build)
  nothreads               (none)                                  (CmdStan's default)
  nothreads-native        CXXFLAGS_OPTIM=-march=native
  nothreads-optims        STAN_CPP_OPTIMS=true STAN_NO_RANGE_CHECKS=true
  nothreads-native-optims both of the above
  threads-native          STAN_THREADS=true CXXFLAGS_OPTIM=-march=native
Outputs go to STUDIES/posteriordb_bench_v1/models/wallgap/<variant>/ (gitignored).
"""
import os
import shutil
import sys
import time
from pathlib import Path

import bridgestan as bs

os.environ.setdefault("MAKE", "mingw32-make")
HERE = Path(__file__).resolve().parent
STUDY = HERE.parent.parent
SRC = Path(os.environ.get("WALLGAP_SRC", r"C:\dev\owalnuts-wt\posteriordb-bench\STUDIES\posteriordb_bench_v1\models"))
MODELS = ["arK__arK", "hmm_example__hmm_example", "eight_schools__eight_schools_noncentered"]
VARIANTS = {
    "v1": ["STAN_THREADS=true"],
    "nothreads": [],
    "nothreads-native": ["CXXFLAGS_OPTIM=-march=native"],
    "nothreads-optims": ["STAN_CPP_OPTIMS=true", "STAN_NO_RANGE_CHECKS=true"],
    "nothreads-native-optims": ["CXXFLAGS_OPTIM=-march=native", "STAN_CPP_OPTIMS=true", "STAN_NO_RANGE_CHECKS=true"],
    "threads-native": ["STAN_THREADS=true", "CXXFLAGS_OPTIM=-march=native"],
}
for variant in sys.argv[1:]:
    out = STUDY / "models" / "wallgap" / variant
    out.mkdir(parents=True, exist_ok=True)
    for m in MODELS:
        for ext in (".stan", ".data.json"):
            if not (out / (m + ext)).exists():
                shutil.copyfile(SRC / (m + ext), out / (m + ext))
        so = out / f"{m}_model.so"
        if so.exists():
            continue
        t = time.perf_counter()
        bs.compile_model(out / f"{m}.stan", make_args=VARIANTS[variant])
        print(f"[{variant}] {m} built in {time.perf_counter() - t:.0f}s", flush=True)
