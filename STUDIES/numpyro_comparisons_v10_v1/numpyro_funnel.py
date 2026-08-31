#!/usr/bin/env python3
"""NumPyro NUTS on the 10-D Neal funnel (part 3 cells FN-N80 / FN-N95).

Same target, starts, warmup/retained counts and seeds as the oWALNUTS funnel
arms. A same-shape compile probe (seed 92000, non-evidence) runs first per
cell so evidence walls exclude compilation. Writes [omega, x_1] draws as
.npy (chains, draws, 2) plus a JSON cell artifact.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import time
from pathlib import Path

os.environ.setdefault("JAX_ENABLE_X64", "true")
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["XLA_FLAGS"] = "--xla_cpu_multi_thread_eigen=false intra_op_parallelism_threads=1"

import arviz as az  # noqa: E402
import jax  # noqa: E402

jax.config.update("jax_enable_x64", True)

import jax.numpy as jnp  # noqa: E402
import numpy as np  # noqa: E402
import numpyro  # noqa: E402
from numpyro.infer import MCMC, NUTS  # noqa: E402

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
PART = PROTOCOL["parts"]["3_funnel"]
DIM = PART["target"]["dimension"]


def funnel_potential(q):
    v = q[0]
    x = q[1:]
    # log p = -v^2/18 - (d-1) v / 2 - exp(-v) sum x^2 / 2
    return v * v / 18.0 + 0.5 * (DIM - 1) * v + 0.5 * jnp.exp(-v) * jnp.sum(x * x)


def run_cell(arm_key: str, seed: int, retained: int, out: Path, evidence: bool) -> dict:
    arm = PART["arms"][arm_key]
    assert arm["backend"] == "numpyro"
    starts = np.asarray(PART["starts"], dtype=np.float64)
    kernel = NUTS(potential_fn=funnel_potential, target_accept_prob=arm["target_accept"],
                  max_tree_depth=arm["max_tree_depth"], dense_mass=arm["dense_mass"],
                  adapt_mass_matrix=arm["adapt_mass_matrix"])
    mcmc = MCMC(kernel, num_warmup=arm["warmup"], num_samples=retained, num_chains=arm["chains"],
                chain_method=arm["chain_method"], progress_bar=False)
    started = time.perf_counter()
    mcmc.warmup(jax.random.PRNGKey(seed), init_params=jnp.asarray(starts),
                extra_fields=("num_steps", "diverging"), collect_warmup=True)
    warm_extra = mcmc.get_extra_fields(group_by_chain=True)
    jax.block_until_ready(warm_extra["num_steps"])
    warm_seconds = time.perf_counter() - started
    sample_started = time.perf_counter()
    mcmc.run(mcmc.post_warmup_state.rng_key, init_params=mcmc.post_warmup_state.z,
             extra_fields=("num_steps", "diverging"))
    samples = np.asarray(mcmc.get_samples(group_by_chain=True))
    extra = mcmc.get_extra_fields(group_by_chain=True)
    jax.block_until_ready(extra["num_steps"])
    sample_seconds = time.perf_counter() - sample_started
    total = time.perf_counter() - started
    omega = samples[:, :, 0]
    x1 = samples[:, :, 1]
    steps = np.asarray(extra["num_steps"])
    warm_steps = np.asarray(warm_extra["num_steps"])
    divergent = np.asarray(extra["diverging"])
    depths = np.ceil(np.log2(np.maximum(steps, 1))).astype(int)
    hist = {str(k): int(v) for k, v in zip(*np.unique(depths, return_counts=True))}
    diag = {}
    for name, x in (("omega", omega), ("x_1", x1)):
        diag[name] = {"rhat": float(az.rhat(x, method="rank")), "bulk_ess": float(az.ess(x, method="bulk")),
                      "tail_ess": float(az.ess(x, method="tail", prob=(0.05, 0.95))),
                      "mean": float(x.mean()), "variance": float(x.var(ddof=1))}
    pooled = omega.reshape(-1)
    stem = f"funnel-{arm_key}-{seed}"
    result = {
        "arm": arm_key, "backend": "numpyro", "part": "3_funnel", "seed": seed, "evidence": evidence,
        "chains": int(samples.shape[0]), "retained_per_chain": int(samples.shape[1]),
        "settings": {k: arm[k] for k in ("warmup", "chains", "chain_method", "target_accept", "max_tree_depth",
                                          "adapt_mass_matrix", "dense_mass")},
        "software": {"python": platform.python_version(), "jax": jax.__version__,
                     "numpyro": numpyro.__version__, "arviz": az.__version__, "numpy": np.__version__},
        "functionals": diag,
        "tail_mass": {str(t): float((pooled < t).mean()) for t in PART_THRESHOLDS()},
        "tail_mass_per_chain": {str(t): [float((c < t).mean()) for c in omega] for t in PART_THRESHOLDS()},
        "omega_quantiles": {"0.01": float(np.quantile(pooled, 0.01)), "0.005": float(np.quantile(pooled, 0.005))},
        "sampler": {"divergences": int(divergent.sum()), "divergences_per_chain": [int(c.sum()) for c in divergent],
                    "depth_histogram": hist, "max_depth_rate": float((depths >= arm["max_tree_depth"]).mean()),
                    "median_depth": int(np.median(depths)), "retained_leapfrogs": int(steps.sum()),
                    "warmup_leapfrogs": int(warm_steps.sum()),
                    "work_unit": "leapfrog num_steps (NumPyro proxy)",
                    "final_step_sizes": [float(s) for s in np.atleast_1d(np.asarray(mcmc.last_state.adapt_state.step_size))]},
        "timing_seconds": {"warmup": warm_seconds, "sampling": sample_seconds, "total_sampling": total,
                           "note": "after a same-shape compile probe; compile excluded"},
        "draws_file": f"draws/{stem}.npy",
        "draws_layout": "(chains, draws, [omega, x_1])",
    }
    if evidence:
        (out / "draws").mkdir(parents=True, exist_ok=True)
        np.save(out / "draws" / f"{stem}.npy", np.stack([omega, x1], axis=-1))
        (out / f"{stem}.json").write_text(json.dumps(result, indent=1, allow_nan=False))
    return result


def PART_THRESHOLDS():
    return PROTOCOL["gates"]["funnel"]["tail_mass_thresholds"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="FN-N80,FN-N95")
    ap.add_argument("--retained", type=int, default=PART["draws"]["retained_per_chain"])
    ap.add_argument("--probe-retained", type=int, default=2000)
    ap.add_argument("--out", type=Path, default=HERE / "artifacts" / "numpyro")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    probe_seed = PROTOCOL["seeds"]["compile_probe"]
    for arm_key in args.arms.split(","):
        # Probe at the evidence shape so the compiled function is reused.
        t0 = time.perf_counter()
        probe = run_cell(arm_key, probe_seed, args.retained, args.out, evidence=False)
        probe_wall = time.perf_counter() - t0
        (args.out / f"3_funnel-{arm_key}-compile-probe.json").write_text(json.dumps(
            {"seed": probe_seed, "evidence": False, "retained_per_chain": args.retained,
             "end_to_end_seconds_including_compile": probe_wall,
             "sampling_seconds": probe["timing_seconds"]["total_sampling"],
             "implied_compile_seconds": probe_wall - probe["timing_seconds"]["total_sampling"]}, indent=1))
        print(f"{arm_key} probe {probe_wall:.1f}s (sampling {probe['timing_seconds']['total_sampling']:.1f}s)", flush=True)
        for seed in PROTOCOL["seeds"]["evidence"]:
            stem = f"funnel-{arm_key}-{seed}"
            if (args.out / f"{stem}.json").exists():
                print("skip existing", stem, flush=True)
                continue
            r = run_cell(arm_key, seed, args.retained, args.out, evidence=True)
            print(stem, f"P(<-5)={r['tail_mass']['-5.0']:.4f}", f"P(<-6)={r['tail_mass']['-6.0']:.4f}",
                  f"var={r['functionals']['omega']['variance']:.3f}", f"div={r['sampler']['divergences']}",
                  f"wall={r['timing_seconds']['total_sampling']:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
