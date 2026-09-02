"""Compile the two study models with BridgeStan exactly as posteriordb_bench_v2 did (no STAN_THREADS)."""
import os, sys, time
from pathlib import Path
os.environ.setdefault("MAKE", "mingw32-make")
import bridgestan as bs
HERE = Path(__file__).resolve().parent
for name in sys.argv[1:] or ["arma__arma11", "hudson_lynx_hare__lotka_volterra"]:
    stan = HERE / "models" / f"{name}.stan"
    so = stan.with_name(f"{stan.stem}_model.so")
    if so.exists():
        print("exists", so); continue
    t = time.perf_counter()
    bs.compile_model(stan, make_args=[])
    print(f"compiled {name} in {time.perf_counter()-t:.1f}s", flush=True)
