"""PyMC entry-point comparison: owalnuts.from_pymc vs NumPyro vs nutpie.

Same Eight Schools model, seeds 93001-93003, 1,000 tune / 1,000 draws, four
chains, target_accept 0.95. Chain methods differ by backend and are recorded;
ESS per gradient uses each backend's own work counter (owalnuts: exact fused
calls; numpyro/nutpie: leapfrog proxies) and is labelled.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import arviz as az
import numpy as np

import owalnuts

SEEDS = [93001, 93002, 93003]
Y = np.array([28.0, 8.0, -3.0, 7.0, -1.0, 1.0, 18.0, 12.0])
SE = np.array([15.0, 10.0, 16.0, 11.0, 9.0, 11.0, 10.0, 18.0])
FUNCTIONALS = ("mu", "tau", "theta_1", "theta_8")


def model():
    import pymc as pm

    with pm.Model() as m:
        mu = pm.Normal("mu", 0.0, 5.0)
        tau = pm.HalfCauchy("tau", 5.0)
        z = pm.Normal("z", 0.0, 1.0, shape=8)
        pm.Deterministic("theta", mu + tau * z)
        pm.Normal("y", mu + tau * z, SE, observed=Y)
    return m


def stats(idata, wall: float, work: int | None, work_kind: str) -> dict:
    post = idata.posterior
    f = {
        "mu": post["mu"].values,
        "tau": post["tau"].values,
        "theta_1": post["theta"].values[..., 0],
        "theta_8": post["theta"].values[..., 7],
    }
    ess = az.ess(az.from_dict(posterior=f))
    rhat = az.rhat(az.from_dict(posterior=f))
    min_ess = min(float(ess[k]) for k in FUNCTIONALS)
    out = {
        "wall_seconds": wall,
        "min_bulk_ess": min_ess,
        "max_rhat": max(float(rhat[k]) for k in FUNCTIONALS),
        "ess_per_second": min_ess / wall,
        "work": work,
        "work_kind": work_kind,
        "ess_per_work": (min_ess / work) if work else None,
        "divergences": int(np.asarray(idata.sample_stats["diverging"]).sum()) if "diverging" in idata.sample_stats else None,
        "mean": {k: float(f[k].mean()) for k in FUNCTIONALS},
    }
    return out


def run_owalnuts(m, seed: int) -> dict:
    target, dim, q0, names, unravel = owalnuts.from_pymc(m)
    starts = np.zeros((4, dim))
    starts[:, 1] = [-2.0, -1.0, 0.0, 1.0]  # tau_log__ dispersion; PyMC order mu, tau_log__, z
    t0 = time.perf_counter()
    r = owalnuts.sample(
        target, dim, init=starts, chains=4, warmup=1000, draws=1000, seed=seed,
        tuning=owalnuts.Tuning(step_size=0.3, max_depth=8, max_refinement_levels=8),
        adaptation=owalnuts.Adaptation(target_accept=0.95),
        max_target_evaluations=20_000_000, coerce=False,
    )
    wall = time.perf_counter() - t0
    q = r.samples
    parts = unravel(q)
    mu = parts["mu"][..., 0]
    tau = np.exp(parts["tau_log__"][..., 0])
    z = parts["z"]
    theta = mu[..., None] + tau[..., None] * z
    idata = az.from_dict(posterior={"mu": mu, "tau": tau, "theta": theta},
                         sample_stats={"diverging": r.divergent[:, 1000:]})
    return stats(idata, wall, r.retained_target_calls, "fused_calls_exact")


def run_numpyro(m, seed: int) -> dict:
    import pymc as pm

    t0 = time.perf_counter()
    idata = pm.sample(model=m, draws=1000, tune=1000, chains=4, cores=1, random_seed=seed,
                      nuts_sampler="numpyro", target_accept=0.95, progressbar=False,
                      compute_convergence_checks=False)
    wall = time.perf_counter() - t0
    steps = int(np.asarray(idata.sample_stats["n_steps"]).sum()) if "n_steps" in idata.sample_stats else None
    return stats(idata, wall, steps, "leapfrog_proxy")


def run_nutpie(m, seed: int) -> dict:
    import nutpie

    t0 = time.perf_counter()
    compiled = nutpie.compile_pymc_model(m, backend="numba")
    compile_wall = time.perf_counter() - t0
    t0 = time.perf_counter()
    idata = nutpie.sample(compiled, draws=1000, tune=1000, chains=4, cores=4, seed=seed,
                          target_accept=0.95, progress_bar=False)
    wall = time.perf_counter() - t0
    steps = int(np.asarray(idata.sample_stats["n_steps"]).sum()) if "n_steps" in idata.sample_stats else None
    out = stats(idata, wall, steps, "leapfrog_proxy")
    out["compile_seconds"] = compile_wall
    out["cores"] = 4
    return out


def main() -> None:
    out_path = Path(__file__).with_name("artifacts") / "pymc-compare.json"
    out_path.parent.mkdir(exist_ok=True)
    report: dict = {"note": "owalnuts cores=1 sequential; nutpie cores=4 parallel (its design); numpyro via pm.sample cores=1"}
    for seed in SEEDS:
        m = model()
        cell = {"owalnuts_from_pymc": run_owalnuts(m, seed)}
        try:
            cell["nutpie_numba"] = run_nutpie(m, seed)
        except Exception as e:  # noqa: BLE001
            cell["nutpie_numba"] = {"error": str(e)}
        try:
            cell["pymc_numpyro"] = run_numpyro(m, seed)
        except Exception as e:  # noqa: BLE001
            cell["pymc_numpyro"] = {"error": str(e)}
        report[str(seed)] = cell
        for k, v in cell.items():
            if "error" not in v:
                print(f"seed {seed} {k}: wall {v['wall_seconds']:.2f}s minESS {v['min_bulk_ess']:.0f} "
                      f"ess/s {v['ess_per_second']:.0f} rhat {v['max_rhat']:.4f}", flush=True)
            else:
                print(f"seed {seed} {k}: ERROR {v['error'][:200]}", flush=True)
        out_path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("done", out_path)


if __name__ == "__main__":
    main()
