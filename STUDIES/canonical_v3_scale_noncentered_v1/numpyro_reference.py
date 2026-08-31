#!/usr/bin/env python3
"""Arm N3: NumPyro NUTS external reference on the canonical-v3 density.

Independent of the Rust kernel. The JAX transcription of canonical-v2 is
parity-checked against the pinned Polyscope oracle first; the v3 transform
(scale-non-centered innovations with its (T-1) log sigma_x Jacobian) is then
checked for round trip and exact log-density relation before sampling.
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

import arviz as az
import jax

jax.config.update("jax_enable_x64", True)

import jax.numpy as jnp
import numpy as np
import numpyro
from jax.scipy.special import gammaln
from numpyro.infer import MCMC, NUTS

HERE = Path(__file__).resolve().parent
ORACLE = HERE / "fixtures" / "polyscope_parity.json"
PROTOCOL = json.loads((HERE / "protocol.json").read_text())
FIXTURES = PROTOCOL["fixtures"]
FUNCTIONALS = ("mu", "sigma_x", "alpha", "beta", "gamma", "nu", "x_terminal", "x_path_mean")


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


def v3_to_q(z):
    mu = z[0]
    sigma_x = jnp.exp(z[1])
    return jnp.concatenate((z[:7], mu + sigma_x * z[7:]))


def q_to_v3_np(q: np.ndarray) -> np.ndarray:
    z = q.copy()
    z[7:] = (q[7:] - q[0]) / np.exp(q[1])
    return z


def v3_log_prob(z, data):
    t_minus_one = z.shape[0] - 7
    return canonical_log_prob_q(v3_to_q(z), data) + t_minus_one * z[1]


def parity() -> dict:
    raw = json.loads(ORACLE.read_text())
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
    # v3 consistency on the oracle cases: lp_z == lp_q + (T-1) log sigma_x and round trip.
    v3_rows = []
    for case in raw["cases"]:
        q = np.asarray(case["params"], dtype=np.float64)
        z = q_to_v3_np(q)
        q_back = np.asarray(v3_to_q(jnp.asarray(z)))
        lp_q = float(canonical_log_prob_q(jnp.asarray(q), data))
        lp_z = float(v3_log_prob(jnp.asarray(z), data))
        expected = lp_q + (len(q) - 7) * q[1]
        ok = np.max(np.abs(q_back - q)) <= 1e-9 * (1 + np.max(np.abs(q))) and abs(lp_z - expected) <= 1e-8 * (1 + abs(expected))
        v3_rows.append({"name": case["name"], "round_trip_max_abs_error": float(np.max(np.abs(q_back - q))),
                        "jacobian_relation_abs_error": abs(lp_z - expected), "passed": bool(ok)})
    return {"oracle_sha256": sha256(ORACLE), "cases": rows, "v3_consistency": v3_rows,
            "passed": all(r["passed"] for r in rows) and all(r["passed"] for r in v3_rows)}


def functionals_from_z(samples_z: np.ndarray) -> dict:
    q = np.asarray(jax.vmap(jax.vmap(v3_to_q))(jnp.asarray(samples_z)))
    latent = q[..., 6, None] + np.concatenate(
        (np.zeros_like(q[..., 6, None]), np.cumsum(q[..., 7:], axis=-1)), axis=-1)
    return {"mu": q[..., 0], "sigma_x": np.exp(q[..., 1]), "alpha": np.exp(q[..., 2]),
            "beta": np.exp(q[..., 3]), "gamma": np.exp(q[..., 4]), "nu": 2 + np.exp(q[..., 5]),
            "x_terminal": latent[..., -1], "x_path_mean": latent.mean(-1)}


def run(fixture_key: str, seed: int, warmup: int, draws: int, target_accept: float,
        max_depth: int, out: Path) -> dict:
    entry = FIXTURES[fixture_key]
    fixture_path = HERE / "fixtures" / entry["file"]
    assert sha256(fixture_path) == entry["sha256"], "fixture hash mismatch"
    raw = json.loads(fixture_path.read_text())
    data = load_data(raw["data"])
    starts_doc = json.loads((HERE / "starts" / f"{fixture_key}.json").read_text())
    assert starts_doc["fixture_sha256"] == entry["sha256"]
    starts = np.stack([q_to_v3_np(np.asarray(s, dtype=np.float64)) for s in starts_doc["starts"]])
    kernel = NUTS(potential_fn=lambda z: -v3_log_prob(z, data),
                  target_accept_prob=target_accept, max_tree_depth=max_depth, dense_mass=False)
    mcmc = MCMC(kernel, num_warmup=warmup, num_samples=draws, num_chains=4,
                chain_method="sequential", progress_bar=False)
    started = time.perf_counter()
    mcmc.warmup(jax.random.PRNGKey(seed), init_params=jnp.asarray(starts),
                extra_fields=("num_steps", "diverging"), collect_warmup=False)
    jax.block_until_ready(mcmc.last_state.z)
    warm_seconds = time.perf_counter() - started
    sample_started = time.perf_counter()
    mcmc.run(mcmc.post_warmup_state.rng_key, init_params=mcmc.post_warmup_state.z,
             extra_fields=("num_steps", "diverging"))
    samples = mcmc.get_samples(group_by_chain=True)
    extra = mcmc.get_extra_fields(group_by_chain=True)
    jax.block_until_ready(samples)
    sample_seconds = time.perf_counter() - sample_started
    samples_z = np.asarray(samples)
    vals = functionals_from_z(samples_z)
    idata = az.from_dict(posterior=vals)
    diagnostics = {}
    for name in FUNCTIONALS:
        diagnostics[name] = {
            "rhat": float(az.rhat(idata, var_names=[name], method="rank")[name].values),
            "bulk_ess": float(az.ess(idata, var_names=[name], method="bulk")[name].values),
            "tail_ess": float(az.ess(idata, var_names=[name], method="tail")[name].values),
            "mean": float(vals[name].mean()),
            "sd": float(vals[name].std(ddof=1)),
        }
    steps = np.asarray(extra["num_steps"])
    divergent = np.asarray(extra["diverging"])
    depths = np.ceil(np.log2(np.maximum(steps, 1))).astype(int)
    hist = {str(k): int(v) for k, v in zip(*np.unique(depths, return_counts=True))}
    max_rhat = max(d["rhat"] for d in diagnostics.values())
    min_bulk = min(d["bulk_ess"] for d in diagnostics.values())
    min_tail = min(d["tail_ess"] for d in diagnostics.values())
    cap_rate = float((depths >= max_depth).mean())
    gates = {
        "max_rhat": {"limit": 1.01, "observed": max_rhat, "passed": max_rhat <= 1.01},
        "min_bulk_ess": {"limit": 400.0, "observed": min_bulk, "passed": min_bulk >= 400},
        "min_tail_ess": {"limit": 400.0, "observed": min_tail, "passed": min_tail >= 400},
        "divergences": {"limit": 0, "observed": int(divergent.sum()), "passed": not divergent.any()},
        "maximum_depth_rate": {"limit": 0.01, "observed": cap_rate, "passed": cap_rate <= 0.01},
    }
    stem = f"{fixture_key}-N3-{seed}"
    np.save(out / f"{stem}-functionals.npy", np.stack([vals[n] for n in FUNCTIONALS], axis=-1))
    result = {
        "arm": "N3", "backend": "numpyro", "model_revision": "polyscope-canonical-v3-scale-noncentered",
        "fixture": fixture_key, "fixture_sha256": entry["sha256"], "seed": seed,
        "dimension": int(samples_z.shape[-1]),
        "settings": {"chains": 4, "warmup": warmup, "draws": draws, "target_accept": target_accept,
                     "max_tree_depth": max_depth, "metric": "diagonal_adapted", "chain_method": "sequential"},
        "software": {"python": platform.python_version(), "jax": jax.__version__,
                     "numpyro": numpyro.__version__, "arviz": az.__version__},
        "functionals": diagnostics, "gates": gates,
        "all_gates_passed": all(g["passed"] for g in gates.values()),
        "sampler": {"divergences": int(divergent.sum()), "max_tree_depth": max_depth,
                    "depth_histogram": hist, "max_depth_rate": cap_rate,
                    "median_depth": int(np.median(depths)),
                    "retained_leapfrogs": int(steps.sum()),
                    "final_step_sizes": [float(s) for s in np.atleast_1d(mcmc.last_state.adapt_state.step_size)]},
        "timing_seconds": {"warmup": warm_seconds, "sampling": sample_seconds,
                           "end_to_end": time.perf_counter() - started},
        "functionals_file": f"{stem}-functionals.npy",
    }
    (out / f"{stem}.json").write_text(json.dumps(result, indent=1, allow_nan=False))
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", default="sspd-10,sspd-11,sspd-05")
    ap.add_argument("--out", type=Path, default=HERE / "artifacts" / "numpyro")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    n = PROTOCOL["arms"]["N3"]
    par = parity()
    (args.out / "parity.json").write_text(json.dumps(par, indent=1))
    if not par["passed"]:
        raise SystemExit("JAX transcription failed oracle parity or v3 consistency")
    print("parity passed", flush=True)
    for key in args.fixtures.split(","):
        seed = PROTOCOL["seeds"][key]
        stem = f"{key}-N3-{seed}"
        if (args.out / f"{stem}.json").exists():
            print("skip existing", stem, flush=True)
            continue
        print("running", stem, flush=True)
        t0 = time.perf_counter()
        r = run(key, seed, n["warmup"], n["draws"], n["target_accept"], n["max_tree_depth"], args.out)
        wall = time.perf_counter() - t0
        if wall > n["wall_cap_seconds"]:
            r["deviation"] = f"wall {wall:.0f}s exceeded cap {n['wall_cap_seconds']:.0f}s"
            (args.out / f"{stem}.json").write_text(json.dumps(r, indent=1, allow_nan=False))
        print(stem, "pass" if r["all_gates_passed"] else "FAIL",
              {k: round(v["observed"], 4) for k, v in r["gates"].items()},
              f"median depth {r['sampler']['median_depth']}", f"{wall:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
