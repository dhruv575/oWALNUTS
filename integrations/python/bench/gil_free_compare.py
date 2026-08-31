"""GIL-free rebench (preregistered in BENCH.md, section "GIL-free rebench").

Eight Schools PyMC model: owalnuts GIL vs cfunc transport vs nutpie vs
NumPyro; local-level T=1000 with the tridiagonal posterior-precision metric
via a numba cfunc. Fresh seeds 96001-96003.
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import arviz as az
import numpy as np

import owalnuts
import run_bench as rb

SEEDS = [96001, 96002, 96003]
ES_KEYS = ("mu", "tau", "theta_1", "theta_8")
ARTIFACTS = Path(__file__).parent / "artifacts"


def es_stats(samples: np.ndarray, wall: float, work: int, work_kind: str) -> dict:
    f = {k: v for k, v in rb.es_functionals(samples).items() if k in ES_KEYS}
    idata = az.from_dict(posterior=f)
    ess, rhat = az.ess(idata), az.rhat(idata)
    min_ess = min(float(ess[k]) for k in ES_KEYS)
    return {
        "wall_seconds": wall,
        "min_bulk_ess": min_ess,
        "max_rhat": max(float(rhat[k]) for k in ES_KEYS),
        "ess_per_second": min_ess / wall,
        "work": work,
        "work_kind": work_kind,
        "ess_per_work": min_ess / work if work else None,
        "mean": {k: float(f[k].mean()) for k in ES_KEYS},
        "sd": {k: float(f[k].std()) for k in ES_KEYS},
    }


def idata_stats(idata, wall: float, work: int | None, work_kind: str) -> dict:
    post = idata.posterior
    f = {
        "mu": post["mu"].values,
        "tau": post["tau"].values,
        "theta_1": post["theta"].values[..., 0],
        "theta_8": post["theta"].values[..., 7],
    }
    ess = az.ess(az.from_dict(posterior=f))
    rhat = az.rhat(az.from_dict(posterior=f))
    min_ess = min(float(ess[k]) for k in ES_KEYS)
    return {
        "wall_seconds": wall,
        "min_bulk_ess": min_ess,
        "max_rhat": max(float(rhat[k]) for k in ES_KEYS),
        "ess_per_second": min_ess / wall,
        "work": work,
        "work_kind": work_kind,
        "ess_per_work": (min_ess / work) if work else None,
        "divergences": int(np.asarray(idata.sample_stats["diverging"]).sum())
        if "diverging" in idata.sample_stats
        else None,
        "mean": {k: float(f[k].mean()) for k in ES_KEYS},
        "sd": {k: float(f[k].std()) for k in ES_KEYS},
    }


def es_model():
    import pymc as pm

    with pm.Model() as m:
        mu = pm.Normal("mu", 0.0, 5.0)
        tau = pm.HalfCauchy("tau", 5.0)
        z = pm.Normal("z", 0.0, 1.0, shape=8)
        pm.Deterministic("theta", mu + tau * z)
        pm.Normal("y", mu + tau * z, rb.SE, observed=rb.Y)
    return m


def owalnuts_es(target, dim: int, seed: int, threads: int) -> dict:
    t0 = time.perf_counter()
    r = owalnuts.sample(
        target,
        dim,
        init=rb.es_starts(),
        chains=4,
        warmup=1000,
        draws=1000,
        seed=seed,
        threads=threads,
        tuning=owalnuts.Tuning(step_size=0.3, max_depth=8, max_refinement_levels=8),
        adaptation=owalnuts.Adaptation(target_accept=0.95),
        max_target_evaluations=20_000_000,
    )
    wall = time.perf_counter() - t0
    out = es_stats(r.samples, wall, r.retained_target_calls, "fused_calls_exact")
    out["divergences"] = int(r.divergent[:, 1000:].sum())
    out["threads"] = threads
    return out


def run_nutpie(m, seed: int, cores: int) -> dict:
    import nutpie

    t0 = time.perf_counter()
    compiled = nutpie.compile_pymc_model(m, backend="numba")
    compile_wall = time.perf_counter() - t0
    t0 = time.perf_counter()
    idata = nutpie.sample(
        compiled,
        draws=1000,
        tune=1000,
        chains=4,
        cores=cores,
        seed=seed,
        target_accept=0.95,
        progress_bar=False,
    )
    wall = time.perf_counter() - t0
    steps = (
        int(np.asarray(idata.sample_stats["n_steps"]).sum())
        if "n_steps" in idata.sample_stats
        else None
    )
    out = idata_stats(idata, wall, steps, "leapfrog_proxy")
    out["compile_seconds"] = compile_wall
    out["cores"] = cores
    return out


def run_numpyro(m, seed: int) -> dict:
    import pymc as pm

    t0 = time.perf_counter()
    idata = pm.sample(
        model=m,
        draws=1000,
        tune=1000,
        chains=4,
        cores=1,
        random_seed=seed,
        nuts_sampler="numpyro",
        target_accept=0.95,
        progressbar=False,
        compute_convergence_checks=False,
    )
    wall = time.perf_counter() - t0
    steps = (
        int(np.asarray(idata.sample_stats["n_steps"]).sum())
        if "n_steps" in idata.sample_stats
        else None
    )
    return idata_stats(idata, wall, steps, "leapfrog_proxy")


def cfunc_per_call_us(target: "owalnuts.CFuncTarget", q: np.ndarray, n: int = 2000) -> float:
    import ctypes

    proto = ctypes.CFUNCTYPE(
        ctypes.c_double,
        ctypes.c_ssize_t,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_void_p,
    )
    caller = proto(target.address)
    q = np.ascontiguousarray(q, dtype=np.float64)
    g = np.zeros(target.dim)
    qp = q.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    gp = g.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    caller(target.dim, qp, gp, None)
    times = []
    for _ in range(5):
        t0 = time.perf_counter()
        for _ in range(n // 5):
            caller(target.dim, qp, gp, None)
        times.append((time.perf_counter() - t0) / (n // 5))
    return float(np.median(times) * 1e6)


def ll_cfunc_target(y: np.ndarray, r: np.ndarray):
    import numba

    n = int(y.size)
    s2 = 1.0 / rb.SIGMA_X**2
    itau2 = 1.0 / rb.TAU0**2
    m0, mu = rb.M0, rb.MU
    yy = np.ascontiguousarray(y, dtype=np.float64)
    ri = np.ascontiguousarray(1.0 / r, dtype=np.float64)
    sig = owalnuts.numba_raw_signature()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        @numba.cfunc(sig, nopython=True)
        def raw(dim, x_ptr, g_ptr, _ud):
            q = numba.carray(x_ptr, (n,))
            g = numba.carray(g_ptr, (n,))
            d0 = q[0] - m0
            lp = -0.5 * d0 * d0 * itau2
            for i in range(n):
                g[i] = 0.0
            g[0] -= d0 * itau2
            for i in range(1, n):
                inn = q[i] - q[i - 1] - mu
                lp -= 0.5 * inn * inn * s2
                g[i] -= inn * s2
                g[i - 1] += inn * s2
            for i in range(n):
                res = yy[i] - q[i]
                lp -= 0.5 * res * res * ri[i]
                g[i] += res * ri[i]
            return lp

    target = owalnuts.from_cfunc(raw, n)
    return target, (raw, yy, ri)


def owalnuts_ll(target, data, seed: int, threads: int, mass) -> dict:
    t = data["y"].size
    t0 = time.perf_counter()
    r = owalnuts.sample(
        target,
        t,
        init=rb.ll_starts(t, seed),
        chains=4,
        warmup=500,
        draws=2000,
        seed=seed,
        threads=threads,
        tuning=owalnuts.Tuning(step_size=0.5, max_depth=8, max_refinement_levels=3),
        adaptation=owalnuts.Adaptation(target_accept=0.8, adapt_mass=False),
        mass=mass,
        max_target_evaluations=60_000_000,
    )
    wall = time.perf_counter() - t0
    f = rb.ll_functionals(r.samples)
    idata = az.from_dict(posterior=f)
    ess, rhat = az.ess(idata), az.rhat(idata)
    min_ess = min(float(ess[k]) for k in f)
    return {
        "threads": threads,
        "wall_seconds": wall,
        "min_bulk_ess": min_ess,
        "max_rhat": max(float(rhat[k]) for k in f),
        "ess_per_second": min_ess / wall,
        "work": r.retained_target_calls,
        "work_kind": "fused_calls_exact",
        "ess_per_work": min_ess / r.retained_target_calls,
        "divergences": int(r.divergent[:, 500:].sum()),
        "mean_x_mean": float(f["x_mean"].mean()),
    }


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    report: dict = {
        "preregistration": "BENCH.md section 'GIL-free rebench (preregistered before execution; WP18)'",
        "algorithm_revision": owalnuts.ALGORITHM_REVISION,
        "seeds": SEEDS,
        "eight_schools": {},
        "local_level_t1000": {},
        "per_call_us": {},
    }

    m = es_model()
    gil_target, dim, q0, names, _ = owalnuts.from_pymc(m)
    cf_target, dim2, _, _, _ = owalnuts.from_pymc(m, gil_free=True)
    assert dim2 == dim
    report["per_call_us"]["pymc_gil"] = rb.per_call_us(gil_target, q0)
    report["per_call_us"]["pymc_cfunc"] = cfunc_per_call_us(cf_target, q0)

    for seed in SEEDS:
        cell: dict = {}
        cell["owalnuts_pymc_gil_t1"] = owalnuts_es(gil_target, dim, seed, 1)
        cell["owalnuts_pymc_cfunc_t1"] = owalnuts_es(cf_target, dim, seed, 1)
        cell["owalnuts_pymc_cfunc_t4"] = owalnuts_es(cf_target, dim, seed, 4)
        cell["nutpie_cores4"] = run_nutpie(m, seed, 4)
        cell["nutpie_cores1"] = run_nutpie(m, seed, 1)
        cell["numpyro"] = run_numpyro(m, seed)
        report["eight_schools"][str(seed)] = cell
        print(
            f"ES {seed}: gil {cell['owalnuts_pymc_gil_t1']['ess_per_second']:.0f}"
            f" cfunc-t1 {cell['owalnuts_pymc_cfunc_t1']['ess_per_second']:.0f}"
            f" cfunc-t4 {cell['owalnuts_pymc_cfunc_t4']['ess_per_second']:.0f}"
            f" nutpie4 {cell['nutpie_cores4']['ess_per_second']:.0f}"
            f" numpyro {cell['numpyro']['ess_per_second']:.0f} ESS/s",
            flush=True,
        )

    data = rb.simulate_local_level(1000)
    diag, off = rb.ll_posterior_precision(data["r"])
    mass = owalnuts.tridiagonal_precision_mass(diag, off)
    ll_target, _keep = ll_cfunc_target(data["y"], data["r"])
    report["per_call_us"]["ll1000_cfunc"] = cfunc_per_call_us(
        ll_target, rb.ll_starts(1000, SEEDS[0])[0]
    )
    numpy_target = rb.ll_numpy_factory(data["y"], data["r"])
    for seed in SEEDS:
        cell = {
            "cfunc_precision_t1": owalnuts_ll(ll_target, data, seed, 1, mass),
            "cfunc_precision_t4": owalnuts_ll(ll_target, data, seed, 4, mass),
        }
        if seed == SEEDS[0]:
            cell["numpy_precision_t1_control"] = owalnuts_ll(
                numpy_target, data, seed, 1, mass
            )
        report["local_level_t1000"][str(seed)] = cell
        print(
            f"LL {seed}: cfunc-t1 {cell['cfunc_precision_t1']['ess_per_second']:.0f}"
            f" cfunc-t4 {cell['cfunc_precision_t4']['ess_per_second']:.0f} ESS/s",
            flush=True,
        )

    out = ARTIFACTS / "gil-free-compare.json"
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"wrote {out}", flush=True)


if __name__ == "__main__":
    main()
