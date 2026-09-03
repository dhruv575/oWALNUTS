"""CmdStan 2.39.0 reference run for one study model: adapted step, inverse
metric and post-warmup positions per chain, for the matched-condition
harness.

    python cmdstan_reference.py <model-short> [seed]

Runs CmdStan (defaults: 4 chains, 1000 warmup / 1000 sampling, random
inits) on `models/<model-short>.stan`, and writes
`artifacts/cmdstan/<model-short>.json` with, per chain, `stepsize__`, the
adapted inverse metric (posterior variance, `M^-1`), and the first retained
draw in unconstrained coordinates (BridgeStan `param_unconstrain`), plus
CmdStan's own sampling statistics (leapfrogs per orbit, tree depth, minimum
bulk ESS over the constrained parameters via ArviZ, ESS per gradient).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CMDSTAN_HOME = Path(r"C:\dev\polyscope\STUDIES\matched_competitor_eight_schools_v38\cmdstan\cmdstan-2.39.0")
DEFAULT_SEED = 84200


def main(model: str, seed: int) -> None:
    import arviz as az
    import bridgestan as bs
    import cmdstanpy

    cmdstanpy.set_cmdstan_path(str(CMDSTAN_HOME))
    so = HERE / "models" / f"{model}_model.so"
    data = HERE / "models" / f"{model}.data.json"
    sm = bs.StanModel(str(so), str(data))
    names = list(sm.param_names())
    work = HERE / "artifacts" / "cmdstan" / model
    work.mkdir(parents=True, exist_ok=True)
    cm = cmdstanpy.CmdStanModel(stan_file=str(HERE / "models" / "cmdstan" / f"{model}.stan"))
    t = time.perf_counter()
    fit = cm.sample(data=str(data), chains=4, parallel_chains=4, iter_warmup=1000, iter_sampling=1000,
                    seed=seed, output_dir=str(work), show_progress=False)
    wall = time.perf_counter() - t
    cols = list(fit.column_names)
    draws = fit.draws(inc_warmup=False)  # (iterations, chains, columns)
    def cmdstan_name(name: str) -> str:
        base, *index = name.split(".")
        return f"{base}[{','.join(index)}]" if index else base
    idx = [cols.index(cmdstan_name(n)) for n in names]
    chains = []
    for c in range(draws.shape[1]):
        constrained = draws[0, c, idx]
        theta = sm.param_unconstrain(np.asarray(constrained, dtype=float))
        chains.append({
            "step_size": float(fit.step_size[c]),
            "inv_metric": np.asarray(fit.inv_metric[c], dtype=float).tolist(),
            "start_unconstrained": np.asarray(theta, dtype=float).tolist(),
            "n_leapfrog": draws[:, c, cols.index("n_leapfrog__")].tolist(),
            "treedepth": draws[:, c, cols.index("treedepth__")].tolist(),
            "divergent": int(draws[:, c, cols.index("divergent__")].sum()),
        })
    param_idx = [i for i, n in enumerate(cols) if not n.endswith("__")]
    arr = np.transpose(draws[:, :, param_idx], (1, 0, 2))
    ds = az.convert_to_dataset({"p": arr})
    bulk = np.asarray(az.ess(ds, method="bulk").p.values, dtype=float)
    n_leap = np.asarray([c["n_leapfrog"] for c in chains])
    result = {
        "schema": "kernel-gap-v1-cmdstan-reference",
        "model": model, "seed": seed, "wall_seconds": wall,
        "param_names_unconstrained": names,
        "param_names_constrained": [cols[i] for i in param_idx],
        "dimension": int(sm.param_unc_num()),
        "chains": chains,
        "sampling": {
            "transitions": int(n_leap.size),
            "gradients": int(n_leap.sum()),
            "leapfrogs_per_orbit": float(n_leap.mean()),
            "mean_treedepth": float(np.asarray([c["treedepth"] for c in chains]).mean()),
            "depth_caps": int((np.asarray([c["treedepth"] for c in chains]) >= 10).sum()),
            "divergences": int(sum(c["divergent"] for c in chains)),
            "min_bulk_ess": float(np.nanmin(bulk)),
            "bulk_ess": bulk.tolist(),
            "min_bulk_ess_per_gradient": float(np.nanmin(bulk) / n_leap.sum()),
            "min_bulk_ess_per_orbit": float(np.nanmin(bulk) / n_leap.size),
        },
    }
    out = HERE / "artifacts" / "cmdstan" / f"{model}.json"
    out.write_text(json.dumps(result), encoding="utf-8")
    s = result["sampling"]
    print(f"{model}: h {[round(c['step_size'], 4) for c in chains]} leapfrogs/orbit {s['leapfrogs_per_orbit']:.1f} "
          f"depth {s['mean_treedepth']:.2f} min bulk ESS {s['min_bulk_ess']:.0f} ESS/grad*1e3 "
          f"{1e3 * s['min_bulk_ess_per_gradient']:.3f} wall {wall:.0f}s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_SEED)
