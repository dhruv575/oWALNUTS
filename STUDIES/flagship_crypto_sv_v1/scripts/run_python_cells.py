"""Python cells of the flagship crypto SV study.

Cells:
  pymc    - owalnuts via from_pymc(gil_free=True) + one-shot precision metric
  nutpie  - nutpie on the identical PyMC model
  numpyro - NumPyro NUTS on a JAX transcription of the identical density
            (parity-checked against the Rust reference before sampling)

Usage:
  python scripts/run_python_cells.py <cell> <SYMBOL> <seed> [pilot]

All cells read data/<SYMBOL>.json and the stage-A calibration file
artifacts/calibration/<SYMBOL>-<seed_cal>.json (seed_cal = evidence seed).
Outputs: artifacts/runs/<SYMBOL>-<cell>-<seed>.json and
artifacts/draws/<SYMBOL>-<cell>-<seed>.npz (functionals + h quantiles only).
"""

import json
import pathlib
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHAINS = 4
WARMUP_OWALNUTS = 1000
WARMUP_EXTERNAL = 1000
DRAWS = 3000
MAX_DEPTH_OWALNUTS = 9
REFINEMENT_LEVELS = 6
INITIAL_STEP = 0.1
TARGET_ACCEPT = 0.8
NUMPYRO_TARGET_ACCEPT = 0.9
NUMPYRO_MAX_DEPTH = 12
RESEARCH_LIMIT = 1_000_000_000

# Priors (must match src/main.rs).
MU_MEAN, MU_VAR = -10.0, 25.0
BETA_A, BETA_B = 20.0, 1.5
HALF_NORMAL_SCALE = 0.5


def load_returns(symbol: str) -> np.ndarray:
    doc = json.loads((ROOT / "data" / f"{symbol}.json").read_text())
    closes = np.array([row[1] for row in doc["closes"]], dtype=np.float64)
    r = np.log(closes[1:] / closes[:-1])
    assert np.isfinite(r).all()
    return r


def load_calibration(symbol: str, seed: int) -> dict:
    path = ROOT / "artifacts" / "calibration" / f"{symbol}-{seed}.json"
    return json.loads(path.read_text())


GLOBAL_COV_INFLATION = 2.0


def precision_mass(r: np.ndarray, cal: dict):
    """Must mirror src/main.rs build_mass exactly."""
    import owalnuts

    phi, s2 = cal["phi_hat"], cal["sigma_hat"] ** 2
    h_mean = np.asarray(cal["h_mean"])
    t = len(r)
    diag = np.full(t, (1.0 + phi * phi) / s2)
    diag[0] = diag[-1] = 1.0 / s2
    diag += 0.5 * r * r * np.exp(-h_mean)
    off = np.full(t - 1, -phi / s2)
    # Tridiagonalized 3x3 global precision from the inflated calibration cov.
    cov = GLOBAL_COV_INFLATION * np.asarray(cal["global_cov"]).reshape(3, 3)
    prec = np.linalg.inv(cov)
    gdiag = np.array([prec[0, 0], prec[1, 1], prec[2, 2]])
    goff = np.array([prec[0, 1], prec[1, 2]])
    try:
        gblock = owalnuts.tridiagonal_precision_mass(gdiag, goff)
    except Exception:
        gblock = owalnuts.tridiagonal_precision_mass(1.0 / np.diag(cov), np.zeros(2))
    return gblock + owalnuts.tridiagonal_precision_mass(diag, off)


def starts_matrix(cal: dict, t: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed * 1_000 + 17)
    base = np.concatenate(
        [[cal["mu_hat"], cal["a_hat"], cal["s_hat"]], np.asarray(cal["h_mean"])]
    )
    jitter_scale = np.concatenate([[0.5, 0.5, 0.3], np.full(t, 0.5)])
    return base[None, :] + jitter_scale[None, :] * rng.standard_normal((CHAINS, t + 3))


def functionals(draws: np.ndarray) -> dict:
    """draws: (chains, draws, dim) unconstrained."""
    a = draws[:, :, 1]
    return {
        "mu": draws[:, :, 0],
        "a": a,
        "s": draws[:, :, 2],
        "phi": 2.0 / (1.0 + np.exp(-a)) - 1.0,
        "sigma": np.exp(draws[:, :, 2]),
        "h_T": draws[:, :, -1],
        "mean_h": draws[:, :, 3:].mean(axis=2),
    }


def save_outputs(symbol, cell, seed, draws, meta):
    f = functionals(draws)
    h = draws[:, :, 3:]
    flat_h = h.reshape(-1, h.shape[2])
    qs = np.percentile(flat_h, [5.0, 50.0, 95.0], axis=0)
    np.savez_compressed(
        ROOT / "artifacts" / "draws" / f"{symbol}-{cell}-{seed}.npz",
        **{k: v for k, v in f.items()},
        h_q05=qs[0],
        h_q50=qs[1],
        h_q95=qs[2],
    )
    (ROOT / "artifacts" / "runs" / f"{symbol}-{cell}-{seed}.json").write_text(
        json.dumps(meta)
    )
    print(symbol, cell, seed, json.dumps({k: meta[k] for k in ("wall_sampling", "work", "work_unit", "divergences")}))


def build_pymc_model(r: np.ndarray):
    import pymc as pm
    import pytensor.tensor as pt

    t = len(r)
    with pm.Model() as model:
        mu = pm.Normal("mu", MU_MEAN, np.sqrt(MU_VAR))
        phi_raw = pm.Beta("phi_raw", BETA_A, BETA_B)
        phi = 2.0 * phi_raw - 1.0
        sigma = pm.HalfNormal("sigma", HALF_NORMAL_SCALE)
        pm.AR(
            "h",
            rho=[mu * (1.0 - phi), phi],
            sigma=sigma,
            constant=True,
            init_dist=pm.Normal.dist(mu, sigma / pt.sqrt(1.0 - phi**2)),
            shape=t,
        )
        pm.Normal("r", 0.0, pt.exp(model["h"] / 2.0), observed=r)
    return model


def parity_check(target, dim, label, tol=1e-5):
    """Compare gradients (and shift-invariant logp) against the Rust reference."""
    pts_path = ROOT / "artifacts" / "parity-points-BTC.json"
    ref_path = ROOT / "artifacts" / "parity-rust-BTC.json"
    if not pts_path.exists() or not ref_path.exists():
        raise SystemExit("parity reference missing; run the Rust parity mode first")
    pts = json.loads(pts_path.read_text())["points"]
    ref = json.loads(ref_path.read_text())["rows"]
    if len(pts[0]) != dim:
        print(f"[parity] skipped for {label}: dim mismatch (points are for BTC)")
        return None
    shifts, max_grad = [], 0.0
    for q, row in zip(pts, ref):
        lp, grad = target(np.asarray(q))
        shifts.append(lp - row["logp"])
        scale = 1.0 + np.abs(np.asarray(row["grad"])).max()
        max_grad = max(max_grad, float(np.abs(np.asarray(grad) - np.asarray(row["grad"])).max() / scale))
    shift_sd = float(np.std(shifts))
    print(f"[parity] {label}: grad max rel dev {max_grad:.2e}, logp shift sd {shift_sd:.2e}")
    if max_grad > tol or shift_sd > tol:
        raise SystemExit(f"parity FAILED for {label}")
    return {"grad_max_rel_dev": max_grad, "logp_shift_sd": shift_sd}


def cell_pymc(symbol: str, seed: int, pilot: bool):
    import owalnuts

    r = load_returns(symbol)
    cal = load_calibration(symbol, seed)
    t = len(r)
    model = build_pymc_model(r)
    target, dim, _q0, _names, _unravel = owalnuts.from_pymc(model, gil_free=True)
    assert dim == t + 3, (dim, t + 3)
    # Parity on the GIL path (same compiled logp); BTC points only.
    gil_target, *_ = owalnuts.from_pymc(model)
    parity = parity_check(gil_target, dim, f"pymc[{symbol}]") if symbol == "BTC" else None
    mass = precision_mass(r, cal)
    starts = starts_matrix(cal, t, seed)
    draws = 500 if pilot else DRAWS
    warmup = 300 if pilot else WARMUP_OWALNUTS
    began = time.perf_counter()
    result = owalnuts.sample(
        target,
        dim,
        init=starts,
        chains=CHAINS,
        warmup=warmup,
        draws=draws,
        seed=seed,
        threads=4,
        tuning=owalnuts.Tuning(
            step_size=INITIAL_STEP,
            max_depth=MAX_DEPTH_OWALNUTS,
            min_micro_steps=1,
            max_refinement_levels=REFINEMENT_LEVELS,
            max_error=1.0,
        ),
        adaptation=owalnuts.Adaptation(
            target_accept=TARGET_ACCEPT,
            adapt_mass=False,
            paper=owalnuts.PaperAdaptation(),
        ),
        mass=mass,
        max_target_evaluations=RESEARCH_LIMIT,
    )
    wall = time.perf_counter() - began
    meta = {
        "schema": "flagship-crypto-sv-v1/run",
        "symbol": symbol,
        "cell": "pymc",
        "seed": seed,
        "pilot": pilot,
        "chains": CHAINS,
        "discarded": warmup,
        "retained_per_chain": draws,
        "algorithm_revision": result.algorithm_revision,
        "wall_sampling": result.wall_seconds,
        "wall_cell": wall,
        "work": result.target_calls,
        "work_retained": result.retained_target_calls,
        "work_unit": "fused target calls (exact)",
        "divergences": int(result.divergent.sum()),
        "max_depth_rate": float((result.depth >= MAX_DEPTH_OWALNUTS).mean()),
        "final_step_sizes": result.final_step_size.tolist(),
        "final_max_errors": result.final_max_error.tolist(),
        "parity": parity,
    }
    save_outputs(symbol, "pymc", seed, result.samples, meta)


def cell_nutpie(symbol: str, seed: int, pilot: bool):
    import nutpie

    r = load_returns(symbol)
    model = build_pymc_model(r)
    compiled = nutpie.compile_pymc_model(model)
    draws = 500 if pilot else DRAWS
    tune = 300 if pilot else WARMUP_EXTERNAL
    began = time.perf_counter()
    idata = nutpie.sample(
        compiled, draws=draws, tune=tune, chains=CHAINS, cores=4, seed=seed,
        progress_bar=False,
    )
    wall = time.perf_counter() - began
    post = idata.posterior
    t = len(r)
    # Reassemble unconstrained draws in the Rust layout [mu, a, s, h...].
    phi_raw = np.asarray(post["phi_raw"])
    a = np.log(phi_raw / (1.0 - phi_raw))
    s = np.log(np.asarray(post["sigma"]))
    draws_arr = np.concatenate(
        [
            np.asarray(post["mu"])[:, :, None],
            a[:, :, None],
            s[:, :, None],
            np.asarray(post["h"]),
        ],
        axis=2,
    )
    stats = idata.sample_stats
    n_steps = int(np.asarray(stats["n_steps"]).sum()) if "n_steps" in stats else -1
    meta = {
        "schema": "flagship-crypto-sv-v1/run",
        "symbol": symbol,
        "cell": "nutpie",
        "seed": seed,
        "pilot": pilot,
        "chains": CHAINS,
        "discarded": tune,
        "retained_per_chain": draws,
        "backend_version": nutpie.__version__,
        "wall_sampling": wall,
        "wall_cell": wall,
        "work": n_steps,
        "work_unit": "retained leapfrog steps (proxy)",
        "divergences": int(np.asarray(stats["diverging"]).sum()),
        "max_depth_rate": float((np.asarray(stats["maxdepth_reached"]).mean()) if "maxdepth_reached" in stats else 0.0),
        "settings": {"target_accept": "nutpie default", "max_depth": "nutpie default"},
    }
    save_outputs(symbol, "nutpie", seed, draws_arr, meta)
    _ = t


def cell_numpyro(symbol: str, seed: int, pilot: bool):
    import jax

    jax.config.update("jax_enable_x64", True)
    import jax.numpy as jnp
    import numpyro
    from numpyro.infer import MCMC, NUTS

    r = load_returns(symbol)
    cal = load_calibration(symbol, seed)
    t = len(r)
    logp = make_jax_logp(r)
    if symbol == "BTC":
        vg = jax.jit(jax.value_and_grad(logp))

        def target(q):
            v, g = vg(jnp.asarray(q))
            return float(v), np.asarray(g)

        parity = parity_check(target, t + 3, f"numpyro-jax[{symbol}]", tol=1e-6)
    else:
        parity = None

    def potential(q):
        return -logp(q)

    starts = starts_matrix(cal, t, seed)
    draws = 500 if pilot else DRAWS
    tune = 300 if pilot else WARMUP_EXTERNAL
    kernel = NUTS(
        potential_fn=potential,
        target_accept_prob=NUMPYRO_TARGET_ACCEPT,
        max_tree_depth=NUMPYRO_MAX_DEPTH,
        dense_mass=False,
    )
    mcmc = MCMC(
        kernel,
        num_warmup=tune,
        num_samples=draws,
        num_chains=CHAINS,
        chain_method="sequential",
        progress_bar=False,
    )
    began = time.perf_counter()
    mcmc.run(
        jax.random.PRNGKey(seed),
        init_params=jnp.asarray(starts),
        extra_fields=("num_steps", "diverging"),
    )
    wall = time.perf_counter() - began
    draws_arr = np.asarray(mcmc.get_samples(group_by_chain=True))
    extra = mcmc.get_extra_fields(group_by_chain=True)
    n_steps = int(np.asarray(extra["num_steps"]).sum())
    divergences = int(np.asarray(extra["diverging"]).sum())
    meta = {
        "schema": "flagship-crypto-sv-v1/run",
        "symbol": symbol,
        "cell": "numpyro",
        "seed": seed,
        "pilot": pilot,
        "chains": CHAINS,
        "discarded": tune,
        "retained_per_chain": draws,
        "backend_version": numpyro.__version__,
        "wall_sampling": wall,
        "wall_cell": wall,
        "work": n_steps,
        "work_unit": "retained leapfrog steps (proxy)",
        "divergences": divergences,
        "max_depth_rate": float((np.asarray(extra["num_steps"]) >= 2**NUMPYRO_MAX_DEPTH - 1).mean()),
        "settings": {"target_accept": NUMPYRO_TARGET_ACCEPT, "max_depth": NUMPYRO_MAX_DEPTH},
        "parity": parity,
    }
    save_outputs(symbol, "numpyro", seed, draws_arr, meta)


def make_jax_logp(r):
    import jax
    import jax.numpy as jnp
    from jax.scipy.special import gammaln

    rj = jnp.asarray(r)
    ln2pi = jnp.log(2.0 * jnp.pi)
    ln_beta_norm = gammaln(BETA_A) + gammaln(BETA_B) - gammaln(BETA_A + BETA_B)
    c2 = HALF_NORMAL_SCALE**2

    def logp(q):
        mu, a, s = q[0], q[1], q[2]
        h = q[3:]
        p = jax.nn.sigmoid(a)
        phi = 2.0 * p - 1.0
        sigma2 = jnp.exp(2.0 * s)
        one_m_phi2 = 1.0 - phi * phi
        lp = -0.5 * (mu - MU_MEAN) ** 2 / MU_VAR - 0.5 * jnp.log(MU_VAR) - 0.5 * ln2pi
        lp += BETA_A * jnp.log(p) + BETA_B * jnp.log1p(-p) - ln_beta_norm
        lp += jnp.log(2.0) - 0.5 * jnp.log(2.0 * jnp.pi * c2) - sigma2 / (2.0 * c2) + s
        d1 = h[0] - mu
        lp += (
            -0.5 * jnp.log(sigma2 / one_m_phi2)
            - 0.5 * ln2pi
            - d1 * d1 * one_m_phi2 / (2.0 * sigma2)
        )
        e = h[1:] - mu - phi * (h[:-1] - mu)
        n = e.shape[0]
        lp += -0.5 * n * jnp.log(sigma2) - 0.5 * n * ln2pi - jnp.sum(e * e) / (2.0 * sigma2)
        w = rj * rj * jnp.exp(-h)
        lp += jnp.sum(-0.5 * h - 0.5 * w - 0.5 * ln2pi)
        return lp

    return logp


def main():
    cell, symbol, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
    pilot = len(sys.argv) > 4 and sys.argv[4] == "pilot"
    (ROOT / "artifacts" / "runs").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts" / "draws").mkdir(parents=True, exist_ok=True)
    {"pymc": cell_pymc, "nutpie": cell_nutpie, "numpyro": cell_numpyro}[cell](symbol, seed, pilot)


if __name__ == "__main__":
    main()
