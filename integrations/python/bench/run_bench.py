"""Preregistered Python-target overhead benchmark (see ../BENCH.md).

Usage: python bench/run_bench.py [--quick] [--out artifacts]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import sys
import time
from pathlib import Path

import numpy as np

os.environ.setdefault("JAX_PLATFORMS", "cpu")
import arviz as az  # noqa: E402

import owalnuts  # noqa: E402

SEEDS = [93001, 93002, 93003]
Y = np.array([28.0, 8.0, -3.0, 7.0, -1.0, 1.0, 18.0, 12.0])
SE = np.array([15.0, 10.0, 16.0, 11.0, 9.0, 11.0, 10.0, 18.0])
LOG_2PI = math.log(2 * math.pi)
DATA_SEED = 2026083131
M0, TAU0, MU, SIGMA_X, OBS_BASE = 0.0, 1.0, 0.01, 0.08, 0.0125

ES_TUNING = owalnuts.Tuning(step_size=0.3, max_depth=8, min_micro_steps=1, max_refinement_levels=8, max_error=1.0)
ES_ADAPT = owalnuts.Adaptation(target_accept=0.95, adapt_mass=True)
ES_BUDGET = 20_000_000  # exact shared callback budget; v38 used the budgeted entry point
LL_TUNING = owalnuts.Tuning(step_size=0.1, max_depth=8, min_micro_steps=1, max_refinement_levels=3, max_error=1.0)
LL_ADAPT = owalnuts.Adaptation(target_accept=0.8, adapt_mass=False)


# ── Targets ──────────────────────────────────────────────────────────────


def es_numpy(q: np.ndarray) -> tuple[float, np.ndarray]:
    mu, log_tau, z = q[0], q[1], q[2:]
    tau = math.exp(log_tau)
    theta = mu + tau * z
    resid = Y - theta
    lg = resid / SE**2
    value = (-0.5 * LOG_2PI - math.log(5.0) - 0.5 * (mu / 5.0) ** 2
             + math.log(2.0 / (math.pi * 5.0 * (1.0 + (tau / 5.0) ** 2))) + log_tau
             + float(np.sum(-0.5 * LOG_2PI - np.log(SE) - 0.5 * (resid / SE) ** 2))
             + float(np.sum(-0.5 * LOG_2PI - 0.5 * z**2)))
    g = np.empty(10)
    g[0] = -mu / 25.0 + lg.sum()
    g[1] = 1.0 - 2.0 * tau * tau / (25.0 + tau * tau) + float(np.sum(lg * tau * z))
    g[2:] = -z + lg * tau
    return value, g


def es_jax_logp():
    import jax.numpy as jnp

    y, se = jnp.asarray(Y), jnp.asarray(SE)

    def logp(q):
        mu, log_tau, z = q[0], q[1], q[2:]
        tau = jnp.exp(log_tau)
        theta = mu + tau * z
        lp = -0.5 * LOG_2PI - jnp.log(5.0) - 0.5 * (mu / 5.0) ** 2
        lp = lp + jnp.log(2.0 / (jnp.pi * 5.0 * (1.0 + (tau / 5.0) ** 2))) + log_tau
        lp = lp + jnp.sum(-0.5 * LOG_2PI - jnp.log(se) - 0.5 * ((y - theta) / se) ** 2)
        lp = lp + jnp.sum(-0.5 * LOG_2PI - 0.5 * z**2)
        return lp

    return logp


def es_torch_logp():
    import torch

    y, se = torch.tensor(Y), torch.tensor(SE)

    def logp(q):
        mu, log_tau, z = q[0], q[1], q[2:]
        tau = torch.exp(log_tau)
        theta = mu + tau * z
        lp = -0.5 * LOG_2PI - math.log(5.0) - 0.5 * (mu / 5.0) ** 2
        lp = lp + torch.log(2.0 / (math.pi * 5.0 * (1.0 + (tau / 5.0) ** 2))) + log_tau
        lp = lp + torch.sum(-0.5 * LOG_2PI - torch.log(se) - 0.5 * ((y - theta) / se) ** 2)
        lp = lp + torch.sum(-0.5 * LOG_2PI - 0.5 * z**2)
        return lp

    return logp


def es_pymc_model():
    import pymc as pm

    with pm.Model() as model:
        mu = pm.Normal("mu", 0.0, 5.0)
        tau = pm.HalfCauchy("tau", 5.0)
        z = pm.Normal("z", 0.0, 1.0, shape=8)
        pm.Normal("y", mu + tau * z, SE, observed=Y)
    return model


def es_starts() -> np.ndarray:
    starts = np.zeros((4, 10))
    starts[:, 1] = [-2.0, -1.0, 0.0, 1.0]
    return starts


def es_functionals(samples: np.ndarray) -> dict[str, np.ndarray]:
    mu, log_tau, z = samples[..., 0], samples[..., 1], samples[..., 2:]
    tau = np.exp(log_tau)
    theta = mu[..., None] + tau[..., None] * z
    return {"mu": mu, "tau": tau, "mean_theta": theta.mean(-1), "sd_theta": theta.std(-1),
            "theta_1": theta[..., 0], "theta_8": theta[..., 7]}


def simulate_local_level(t: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(DATA_SEED + t)
    i = np.arange(t)
    spread = 0.02 + 0.03 * np.abs(np.sin(2 * np.pi * i / 37.0)) + np.where(rng.random(t) < 0.05, 0.15, 0.0)
    volume = np.exp(0.9 * rng.standard_normal(t))
    r = OBS_BASE * (1.0 + spread**2 + 1.0 / (volume + 1.0))
    x = np.empty(t)
    x[0] = M0 + TAU0 * rng.standard_normal()
    for k in range(1, t):
        x[k] = x[k - 1] + MU + SIGMA_X * rng.standard_normal()
    y = x + np.sqrt(r) * rng.standard_normal(t)
    return {"y": y, "r": r, "x": x}


def ll_numpy_factory(y: np.ndarray, r: np.ndarray):
    s2 = 1.0 / SIGMA_X**2
    ri = 1.0 / r

    def target(q: np.ndarray) -> tuple[float, np.ndarray]:
        d0 = q[0] - M0
        inn = np.diff(q) - MU
        res = y - q
        lp = -0.5 * d0 * d0 / TAU0**2 - 0.5 * s2 * float(inn @ inn) - 0.5 * float(res * res @ ri)
        g = res * ri
        g[0] -= d0 / TAU0**2
        g[1:] -= inn * s2
        g[:-1] += inn * s2
        return float(lp), g

    return target


def ll_jax_logp(y: np.ndarray, r: np.ndarray):
    import jax.numpy as jnp

    yj, rj = jnp.asarray(y), jnp.asarray(r)
    s2 = 1.0 / SIGMA_X**2

    def logp(q):
        d0 = q[0] - M0
        inn = jnp.diff(q) - MU
        res = yj - q
        return -0.5 * d0 * d0 / TAU0**2 - 0.5 * s2 * jnp.sum(inn * inn) - 0.5 * jnp.sum(res * res / rj)

    return logp


def ll_torch_logp(y: np.ndarray, r: np.ndarray):
    import torch

    yt, rt = torch.tensor(y), torch.tensor(r)
    s2 = 1.0 / SIGMA_X**2

    def logp(q):
        d0 = q[0] - M0
        inn = q[1:] - q[:-1] - MU
        res = yt - q
        return -0.5 * d0 * d0 / TAU0**2 - 0.5 * s2 * torch.sum(inn * inn) - 0.5 * torch.sum(res * res / rt)

    return logp


def ll_posterior_precision(r: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    t = r.size
    s2 = 1.0 / SIGMA_X**2
    diag = np.full(t, 2.0 * s2)
    diag[0] = 1.0 / TAU0**2 + s2
    diag[-1] = s2
    diag += 1.0 / r
    return diag, np.full(t - 1, -s2)


def ll_starts(t: int, seed: int) -> np.ndarray:
    starts = np.empty((4, t))
    for chain in range(4):
        rng = np.random.default_rng(seed * 1_000_003 + chain)
        x = np.empty(t)
        x[0] = M0 + TAU0 * rng.standard_normal()
        for k in range(1, t):
            x[k] = x[k - 1] + MU + SIGMA_X * rng.standard_normal()
        starts[chain] = x
    return starts


def ll_functionals(samples: np.ndarray) -> dict[str, np.ndarray]:
    t = samples.shape[-1]
    idx = np.linspace(0, t - 1, 8).round().astype(int)
    out = {f"x_{i}": samples[..., i] for i in idx}
    out["x_mean"] = samples.mean(-1)
    return out


# ── Helpers ──────────────────────────────────────────────────────────────


def per_call_us(target, q: np.ndarray, n: int = 2000) -> float:
    target(q)
    times = []
    for _ in range(5):
        t0 = time.perf_counter()
        for _ in range(n // 5):
            target(q)
        times.append((time.perf_counter() - t0) / (n // 5))
    return float(np.median(times) * 1e6)


def ess_table(functionals: dict[str, np.ndarray]) -> dict[str, float]:
    idata = az.from_dict(posterior={k: v for k, v in functionals.items()})
    ess = az.ess(idata)
    rhat = az.rhat(idata)
    return {"bulk_ess": {k: float(ess[k]) for k in functionals},
            "rhat": {k: float(rhat[k]) for k in functionals},
            "mean": {k: float(v.mean()) for k, v in functionals.items()},
            "sd": {k: float(v.std()) for k, v in functionals.items()}}


def summarize(result: owalnuts.SampleResult, functionals) -> dict:
    f = functionals(result.samples)
    table = ess_table(f)
    min_ess = min(table["bulk_ess"].values())
    calls = result.retained_target_calls
    depth = result.depth[:, result.config["warmup"]:]
    stops = np.stack([np.asarray(c["stop"])[result.config["warmup"]:] for c in result.chains])
    return {
        **table,
        "min_bulk_ess": min_ess,
        "max_rhat": max(table["rhat"].values()),
        "retained_target_calls": calls,
        "total_target_calls": result.target_calls,
        "wall_seconds": result.wall_seconds,
        "attached_seconds": result.target_attached_seconds,
        "attached_fraction": result.target_attached_seconds / result.wall_seconds if result.wall_seconds else None,
        "ess_per_call": min_ess / calls,
        "ess_per_second": min_ess / result.wall_seconds,
        "divergences": int(result.divergent[:, result.config["warmup"]:].sum()),
        "max_depth_rate": float((depth >= result.config["max_depth"]).mean()),
        "invalid_stops": int((stops == owalnuts.STOP_CODES.index("invalid_evaluation")).sum()),
        "final_step": result.final_step_size.tolist(),
        "samples_sha": _sha(result.samples),
    }


def _sha(a: np.ndarray) -> str:
    import hashlib

    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()[:16]


def numpyro_run(logp, starts: np.ndarray, warmup: int, draws: int, seed: int, target_accept: float,
                adapt_mass: bool, functionals) -> dict:
    import jax
    import jax.numpy as jnp
    from numpyro.infer import MCMC, NUTS

    jax.config.update("jax_enable_x64", True)
    kernel = NUTS(potential_fn=lambda q: -logp(q), target_accept_prob=target_accept, max_tree_depth=8,
                  adapt_mass_matrix=adapt_mass, dense_mass=False)
    out = {}
    for label in ("cold", "warm"):
        mcmc = MCMC(kernel, num_warmup=warmup, num_samples=draws, num_chains=starts.shape[0],
                    chain_method="sequential", progress_bar=False)
        t0 = time.perf_counter()
        mcmc.run(jax.random.PRNGKey(seed), init_params=jnp.asarray(starts), extra_fields=("num_steps", "diverging"))
        samples = np.asarray(mcmc.get_samples(group_by_chain=True))
        wall = time.perf_counter() - t0
        extra = mcmc.get_extra_fields(group_by_chain=True)
        steps = int(np.asarray(extra["num_steps"]).sum())
        table = ess_table(functionals(samples))
        min_ess = min(table["bulk_ess"].values())
        out[label] = {**table, "min_bulk_ess": min_ess, "max_rhat": max(table["rhat"].values()),
                      "retained_leapfrogs_proxy": steps, "wall_seconds": wall,
                      "ess_per_leapfrog_proxy": min_ess / steps, "ess_per_second": min_ess / wall,
                      "divergences": int(np.asarray(extra["diverging"]).sum())}
    return out


def agreement(ref: dict, other: dict) -> dict:
    z = {}
    for k in ref["mean"]:
        mcse = math.hypot(ref["sd"][k] / math.sqrt(max(ref["bulk_ess"][k], 1)),
                          other["sd"][k] / math.sqrt(max(other["bulk_ess"][k], 1)))
        z[k] = (other["mean"][k] - ref["mean"][k]) / mcse if mcse > 0 else 0.0
    return {"z": z, "max_abs_z": max(abs(v) for v in z.values())}


# ── Main ─────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(Path(__file__).with_name("artifacts")))
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--skip", default="", help="comma list of backends to skip")
    args = parser.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    skip = set(filter(None, args.skip.split(",")))
    seeds = SEEDS[:1] if args.quick else SEEDS

    import jax

    jax.config.update("jax_enable_x64", True)
    import torch

    torch.set_num_threads(1)

    report: dict = {
        "python": sys.version.split()[0], "platform": platform.platform(),
        "algorithm_revision": owalnuts.ALGORITHM_REVISION, "seeds": seeds,
        "packages": {m: __import__(m).__version__ for m in ("numpy", "jax", "numpyro", "torch", "pymc", "arviz")},
        "eight_schools": {}, "local_level": {},
    }

    # ---------------- Eight Schools ----------------
    es_targets = {
        "numpy": es_numpy,
        "jax": owalnuts.from_jax(es_jax_logp()),
        "torch": owalnuts.from_torch(es_torch_logp()),
    }
    pymc_target, _, _, _, _ = owalnuts.from_pymc(es_pymc_model())
    es_targets["pymc"] = pymc_target
    q0 = es_starts()[0]
    report["eight_schools"]["per_call_us"] = {name: per_call_us(t, q0) for name, t in es_targets.items() if name not in skip}
    report["eight_schools"]["per_call_us"]["native_reference_call"] = per_call_us(
        lambda q: owalnuts.eight_schools_logp_grad(Y, SE, q), q0)

    for seed in seeds:
        cell: dict = {}
        native = owalnuts.sample_native_eight_schools(Y, SE, init=es_starts(), warmup=1000, draws=1000, seed=seed,
                                                     tuning=ES_TUNING, adaptation=ES_ADAPT,
                                                     max_target_evaluations=ES_BUDGET)
        cell["native"] = summarize(native, es_functionals)
        native4 = owalnuts.sample_native_eight_schools(Y, SE, init=es_starts(), warmup=1000, draws=1000, seed=seed,
                                                      threads=4, tuning=ES_TUNING, adaptation=ES_ADAPT,
                                                      max_target_evaluations=ES_BUDGET)
        cell["native_threads4"] = summarize(native4, es_functionals)
        for name, target in es_targets.items():
            if name in skip:
                continue
            for threads in ((1, 4) if name == "numpy" else (1,)):
                key = name if threads == 1 else f"{name}_threads{threads}"
                r = owalnuts.sample(target, 10, init=es_starts(), warmup=1000, draws=1000, seed=seed, threads=threads,
                                    tuning=ES_TUNING, adaptation=ES_ADAPT, coerce=(name != "numpy"),
                                    max_target_evaluations=ES_BUDGET)
                cell[key] = summarize(r, es_functionals)
                cell[key]["agreement_vs_native"] = agreement(cell["native"], cell[key])
                cell[key]["bitwise_identical_to_native"] = cell[key]["samples_sha"] == cell["native"]["samples_sha"]
                print(f"ES seed {seed} {key}: wall {r.wall_seconds:.2f}s ess/call {cell[key]['ess_per_call']:.4f}", flush=True)
        if "numpyro" not in skip:
            cell["numpyro"] = numpyro_run(es_jax_logp(), es_starts(), 1000, 1000, seed, 0.95, True, es_functionals)
            for label in ("cold", "warm"):
                cell["numpyro"][label]["agreement_vs_native"] = agreement(cell["native"], cell["numpyro"][label])
            print(f"ES seed {seed} numpyro warm: {cell['numpyro']['warm']['wall_seconds']:.2f}s", flush=True)
        report["eight_schools"][str(seed)] = cell
        (out_dir / "summary.json").write_text(json.dumps(report, indent=1), encoding="utf-8")

    # ---------------- Local level ----------------
    for t in (100, 1000):
        data = simulate_local_level(t)
        y, r = data["y"], data["r"]
        draws = 2000 if t == 100 else 1000
        diag, off = ll_posterior_precision(r)
        masses = {"identity": None, "precision": owalnuts.tridiagonal_precision_mass(diag, off)}
        targets = {"numpy": ll_numpy_factory(y, r), "jax": owalnuts.from_jax(ll_jax_logp(y, r)),
                   "torch": owalnuts.from_torch(ll_torch_logp(y, r))}
        block: dict = {"per_call_us": {name: per_call_us(tg, ll_starts(t, 1)[0]) for name, tg in targets.items() if name not in skip}}
        for seed in seeds:
            cell = {}
            starts = ll_starts(t, seed)
            for mname, mass in masses.items():
                native = owalnuts.sample_native_local_level(y, r, init=starts, warmup=500, draws=draws, seed=seed,
                                                           tuning=LL_TUNING, adaptation=LL_ADAPT, mass=mass)
                cell[f"native_{mname}"] = summarize(native, ll_functionals)
                for name, target in targets.items():
                    if name in skip:
                        continue
                    if t == 1000 and name == "torch" and mname == "identity":
                        continue  # ~10 minutes per seed; measured on the precision arm only
                    rr = owalnuts.sample(target, t, init=starts, warmup=500, draws=draws, seed=seed, tuning=LL_TUNING,
                                         adaptation=LL_ADAPT, mass=mass, coerce=(name != "numpy"))
                    key = f"{name}_{mname}"
                    cell[key] = summarize(rr, ll_functionals)
                    cell[key]["agreement_vs_native"] = agreement(cell[f"native_{mname}"], cell[key])
                    cell[key]["bitwise_identical_to_native"] = cell[key]["samples_sha"] == cell[f"native_{mname}"]["samples_sha"]
                    print(f"LL T={t} seed {seed} {key}: wall {rr.wall_seconds:.1f}s ess/call {cell[key]['ess_per_call']:.5f}", flush=True)
            if "numpyro" not in skip:
                cell["numpyro_identity"] = numpyro_run(ll_jax_logp(y, r), starts, 500, draws, seed, 0.8, False, ll_functionals)
                for label in ("cold", "warm"):
                    cell["numpyro_identity"][label]["agreement_vs_native"] = agreement(cell["native_identity"], cell["numpyro_identity"][label])
                print(f"LL T={t} seed {seed} numpyro warm: {cell['numpyro_identity']['warm']['wall_seconds']:.1f}s", flush=True)
            block[str(seed)] = cell
            report["local_level"][str(t)] = block
            (out_dir / "summary.json").write_text(json.dumps(report, indent=1), encoding="utf-8")

    (out_dir / "summary.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("done", out_dir / "summary.json")


if __name__ == "__main__":
    main()
