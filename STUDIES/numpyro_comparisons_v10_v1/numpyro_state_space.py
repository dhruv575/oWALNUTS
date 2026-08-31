#!/usr/bin/env python3
"""NumPyro NUTS cells for parts 1 (T-N, sspd-05) and 2 (R-N, rm48).

Independent of the Rust kernel. The JAX transcription of `polyscope-canonical-v2`
is parity-checked against the pinned oracle before any sampling. Starts are the
shared `starts/*.json` (innovation coordinates) mapped to the cell's
centeredness. Single-thread XLA/BLAS flags are set before importing JAX, as in
`matched-timing-v1`. A same-shape compile probe (seed 92000, non-evidence) runs
first so that evidence walls exclude compilation.
"""
from __future__ import annotations

import argparse
import hashlib
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
from jax.scipy.special import gammaln  # noqa: E402
from numpyro.infer import MCMC, NUTS  # noqa: E402

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
FUNCTIONALS = PROTOCOL["functionals"]["state_space"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_data(raw: dict):
    y = np.asarray(raw["y"], dtype=np.float64)
    volume = np.asarray(raw["v"], dtype=np.float64)
    positive = np.sort(volume[volume > 0])
    median = positive[len(positive) // 2] if len(positive) else 1.0
    return (
        jnp.asarray(np.log(y / (1.0 - y))),
        jnp.asarray(raw["s"], dtype=jnp.float64),
        jnp.asarray(volume / median),
    )


def to_innovations(y, a):
    def step(x, yi):
        innovation = yi - a * x
        return (1 - a) * x + yi, innovation

    _, innovations = jax.lax.scan(step, y[6], y[7:])
    return jnp.concatenate((y[:7], innovations))


def from_innovations_np(q: np.ndarray, a: float) -> np.ndarray:
    y = q.copy()
    x = q[6]
    for i in range(7, len(q)):
        y[i] = q[i] + a * x
        x = x + q[i]
    return y


def canonical_log_prob_q(q, data):
    logit_y, spread, volume = data
    mu, sigma_x, alpha, beta, gamma, eta = q[0], *jnp.exp(q[1:6])
    nu = 2 + eta
    lp = -0.5 * (mu / 0.1) ** 2 - jnp.log(0.1) - 0.5 * jnp.log(2 * jnp.pi)
    scales = jnp.array([0.1, 0.5, 0.5, 0.5])
    positive = jnp.array([sigma_x, alpha, beta, gamma])
    lp += jnp.sum(-0.5 * (positive / scales) ** 2 + jnp.log(2.0) - jnp.log(scales)
                  - 0.5 * jnp.log(2 * jnp.pi) + q[1:5])
    lp += q[5] - eta
    lp += -0.5 * (q[6] - logit_y[0]) ** 2 - 0.5 * jnp.log(2 * jnp.pi)
    innovations = q[7:]
    lp += jnp.sum(-0.5 * ((innovations - mu) / sigma_x) ** 2 - jnp.log(sigma_x)
                  - 0.5 * jnp.log(2 * jnp.pi))
    latent = jnp.concatenate((q[6:7], q[6] + jnp.cumsum(innovations)))
    variance = alpha ** 2 + beta ** 2 * spread ** 2 + gamma ** 2 / (volume + 1.0)
    sigma = jnp.sqrt(variance)
    z2 = ((logit_y - latent) / sigma) ** 2
    lp += jnp.sum(gammaln((nu + 1) / 2) - gammaln(nu / 2) - 0.5 * jnp.log(nu * jnp.pi)
                  - jnp.log(sigma) - 0.5 * (nu + 1) * jnp.log1p(z2 / nu))
    return lp


def parity() -> dict:
    oracle = HERE / "fixtures" / PROTOCOL["fixtures"]["polyscope_parity"]["file"]
    assert sha256(oracle) == PROTOCOL["fixtures"]["polyscope_parity"]["sha256"]
    raw = json.loads(oracle.read_text())
    data = load_data({"y": raw["data"]["y"], "s": raw["data"]["spread"], "v": raw["data"]["volume"]})
    vg = jax.jit(jax.value_and_grad(canonical_log_prob_q))
    rows = []
    for case in raw["cases"]:
        value, grad = vg(jnp.asarray(case["params"], dtype=jnp.float64), data)
        value, grad = float(value), np.asarray(grad)
        expected = np.asarray(case["gradient"])
        value_error = abs(value - case["log_prob"])
        grad_errors = np.abs(grad - expected)
        ok = (value_error <= 2e-12 + 5e-15 * abs(case["log_prob"])
              and np.all(grad_errors <= 2e-10 + 5e-15 * np.abs(expected)))
        rows.append({"name": case["name"], "value_abs_error": value_error,
                     "gradient_max_abs_error": float(grad_errors.max()), "passed": bool(ok)})
    return {"oracle_sha256": sha256(oracle), "cases": rows, "passed": all(r["passed"] for r in rows)}


def functionals_from_y(samples_y: np.ndarray, a: float) -> np.ndarray:
    q = np.asarray(jax.vmap(jax.vmap(lambda y: to_innovations(y, a)))(jnp.asarray(samples_y)))
    latent = q[..., 6, None] + np.concatenate(
        (np.zeros_like(q[..., 6, None]), np.cumsum(q[..., 7:], axis=-1)), axis=-1)
    cols = [q[..., 0], np.exp(q[..., 1]), np.exp(q[..., 2]), np.exp(q[..., 3]), np.exp(q[..., 4]),
            2 + np.exp(q[..., 5]), latent[..., -1], latent.mean(-1), q[..., 6]]
    return np.stack(cols, axis=-1)  # (chains, draws, 9)


def run_cell(part_key: str, arm_key: str, seed: int, out: Path, evidence: bool) -> dict:
    part = PROTOCOL["parts"][part_key]
    arm = part["arms"][arm_key]
    assert arm["backend"] == "numpyro"
    fixture_key = part["fixture"]
    entry = PROTOCOL["fixtures"][fixture_key]
    fixture_path = HERE / "fixtures" / entry["file"]
    assert sha256(fixture_path) == entry["sha256"], "fixture hash mismatch"
    raw = json.loads(fixture_path.read_text())
    data = load_data(raw["data"])
    a = float(arm["centeredness"])
    starts_doc = json.loads((HERE / "starts" / f"{fixture_key}.json").read_text())
    assert starts_doc["fixture_sha256"] == entry["sha256"]
    starts = np.stack([from_innovations_np(np.asarray(s), a) for s in starts_doc["starts"]])
    kwargs = dict(target_accept_prob=arm["target_accept"], max_tree_depth=arm["max_tree_depth"],
                  dense_mass=False, adapt_step_size=arm["adapt_step_size"],
                  adapt_mass_matrix=arm["adapt_mass_matrix"])
    frozen_meta = None
    if arm["metric"] == "frozen_diagonal":
        fpath = HERE / "fixtures" / arm["frozen_diagonal_file"]
        cov = np.asarray(json.loads(fpath.read_text()), dtype=np.float64)
        assert cov.shape == (starts.shape[1],)
        kwargs["inverse_mass_matrix"] = jnp.asarray(1.0 / cov)
        kwargs["step_size"] = arm["initial_step"]
        frozen_meta = {"file": arm["frozen_diagonal_file"], "sha256": sha256(fpath),
                       "rule": "inverse_mass_matrix = 1 / momentum covariance, elementwise, binary64"}
    kernel = NUTS(potential_fn=lambda y: -canonical_log_prob_q(to_innovations(y, a), data), **kwargs)
    mcmc = MCMC(kernel, num_warmup=arm["warmup"], num_samples=arm["draws"], num_chains=arm["chains"],
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
    samples = mcmc.get_samples(group_by_chain=True)
    extra = mcmc.get_extra_fields(group_by_chain=True)
    jax.block_until_ready(samples)
    sample_seconds = time.perf_counter() - sample_started
    total_seconds = time.perf_counter() - started
    samples_y = np.asarray(samples)
    vals = functionals_from_y(samples_y, a)
    steps = np.asarray(extra["num_steps"])
    warm_steps = np.asarray(warm_extra["num_steps"])
    divergent = np.asarray(extra["diverging"])
    depths = np.ceil(np.log2(np.maximum(steps, 1))).astype(int)
    max_depth = arm["max_tree_depth"]
    hist = {str(k): int(v) for k, v in zip(*np.unique(depths, return_counts=True))}
    stem = f"{fixture_key}-{arm_key}-{seed}"
    diagnostics = {}
    for j, name in enumerate(FUNCTIONALS):
        x = vals[:, :, j]
        diagnostics[name] = {"rhat": float(az.rhat(x, method="rank")), "bulk_ess": float(az.ess(x, method="bulk")),
                             "tail_ess": float(az.ess(x, method="tail", prob=(0.05, 0.95))),
                             "mean": float(x.mean()), "sd": float(x.std(ddof=1))}
    step_sizes = np.atleast_1d(np.asarray(mcmc.last_state.adapt_state.step_size))
    result = {
        "arm": arm_key, "backend": "numpyro", "part": part_key, "fixture": fixture_key,
        "fixture_sha256": entry["sha256"], "centeredness": a, "seed": seed, "evidence": evidence,
        "dimension": int(samples_y.shape[-1]),
        "settings": {k: arm[k] for k in ("warmup", "draws", "chains", "chain_method", "target_accept",
                                          "max_tree_depth", "adapt_step_size", "adapt_mass_matrix", "metric")},
        "frozen_diagonal": frozen_meta,
        "software": {"python": platform.python_version(), "jax": jax.__version__,
                     "numpyro": numpyro.__version__, "arviz": az.__version__, "numpy": np.__version__},
        "single_thread_env": {"OMP_NUM_THREADS": os.environ["OMP_NUM_THREADS"], "XLA_FLAGS": os.environ["XLA_FLAGS"]},
        "functional_names": FUNCTIONALS,
        "functionals": diagnostics,
        "sampler": {"divergences": int(divergent.sum()), "depth_histogram": hist,
                    "max_depth_rate": float((depths >= max_depth).mean()), "median_depth": int(np.median(depths)),
                    "retained_leapfrogs": int(steps.sum()), "warmup_leapfrogs": int(warm_steps.sum()),
                    "work_unit": "leapfrog num_steps (NumPyro proxy; not a fused target-call counter)",
                    "final_step_sizes": [float(s) for s in step_sizes]},
        "timing_seconds": {"warmup": warm_seconds, "sampling": sample_seconds, "total_sampling": total_seconds,
                           "note": "after a same-shape compile probe; compile excluded"},
        "functionals_file": f"draws/{stem}.npy",
    }
    if evidence:
        (out / "draws").mkdir(parents=True, exist_ok=True)
        np.save(out / "draws" / f"{stem}.npy", vals)
        (out / f"{stem}.json").write_text(json.dumps(result, indent=1, allow_nan=False))
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="1_sspd05_timing:T-N,2_rm48:R-N")
    ap.add_argument("--out", type=Path, default=HERE / "artifacts" / "numpyro")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    par = parity()
    (args.out / "parity.json").write_text(json.dumps(par, indent=1))
    if not par["passed"]:
        raise SystemExit("JAX transcription failed oracle parity")
    print("parity passed", flush=True)
    probe_seed = PROTOCOL["seeds"]["compile_probe"]
    for cell in args.cells.split(","):
        part_key, arm_key = cell.split(":")
        t0 = time.perf_counter()
        probe = run_cell(part_key, arm_key, probe_seed, args.out, evidence=False)
        probe_wall = time.perf_counter() - t0
        (args.out / f"{part_key}-{arm_key}-compile-probe.json").write_text(json.dumps(
            {"seed": probe_seed, "evidence": False, "end_to_end_seconds_including_compile": probe_wall,
             "sampling_seconds": probe["timing_seconds"]["total_sampling"],
             "implied_compile_seconds": probe_wall - probe["timing_seconds"]["total_sampling"]}, indent=1))
        print(f"{cell} compile probe {probe_wall:.1f}s (sampling {probe['timing_seconds']['total_sampling']:.1f}s)", flush=True)
        for seed in PROTOCOL["seeds"]["evidence"]:
            stem = f"{PROTOCOL['parts'][part_key]['fixture']}-{arm_key}-{seed}"
            if (args.out / f"{stem}.json").exists():
                print("skip existing", stem, flush=True)
                continue
            r = run_cell(part_key, arm_key, seed, args.out, evidence=True)
            print(stem, f"div={r['sampler']['divergences']}", f"cap={r['sampler']['max_depth_rate']:.4f}",
                  f"depth={r['sampler']['median_depth']}", f"wall={r['timing_seconds']['total_sampling']:.1f}s",
                  f"maxrhat={max(d['rhat'] for d in r['functionals'].values()):.4f}",
                  f"minbulk={min(d['bulk_ess'] for d in r['functionals'].values()):.0f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
