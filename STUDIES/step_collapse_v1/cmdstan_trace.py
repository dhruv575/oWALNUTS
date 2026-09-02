"""CmdStan 2.39.0 adaptation trace from the oWALNUTS starts of one study cell.

    python cmdstan_trace.py <telemetry.json> [out.json]

Reads the unconstrained starts recorded by the study driver, constrains them
with BridgeStan, runs CmdStan (defaults, 4 chains, 1000/1000, save_warmup)
from those starts with the cell's seed, and writes per-iteration
`stepsize__`, `accept_stat__`, `treedepth__`, `n_leapfrog__`, `divergent__`
per chain, the adapted inverse metric, and ArviZ bulk ESS / rank R-hat over
the model parameters of the retained draws.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CMDSTAN_HOME = Path(r"C:\dev\polyscope\STUDIES\matched_competitor_eight_schools_v38\cmdstan\cmdstan-2.39.0")


def nest(names: list[str], values: np.ndarray) -> dict:
    """BridgeStan constrained names ('beta.1', 'L.2.3') -> Stan init dict."""
    out: dict = {}
    for name, value in zip(names, values):
        parts = name.split(".")
        base = parts[0]
        idx = [int(p) - 1 for p in parts[1:]] if len(parts) > 1 and all(p.isdigit() for p in parts[1:]) else []
        if not idx:
            out[base] = float(value)
            continue
        out.setdefault(base, {})[tuple(idx)] = float(value)
    result = {}
    for base, value in out.items():
        if not isinstance(value, dict):
            result[base] = value
            continue
        shape = tuple(max(k[d] for k in value) + 1 for d in range(len(next(iter(value)))))
        arr = np.zeros(shape)
        for k, v in value.items():
            arr[k] = v
        result[base] = arr.tolist()
    return result


def main(cell: Path, out: Path | None) -> None:
    import bridgestan as bs
    import cmdstanpy

    cmdstanpy.set_cmdstan_path(str(CMDSTAN_HOME))
    payload = json.loads(cell.read_text(encoding="utf-8"))
    model = payload["model"].replace("_model", "")
    seed = int(payload["seed"])
    so = HERE / "models" / f"{model}_model.so"
    data = HERE / "models" / f"{model}.data.json"
    sm = bs.StanModel(str(so), str(data))
    names = sm.param_names()
    work = HERE / "artifacts" / "cmdstan" / f"{model}-{seed}"
    work.mkdir(parents=True, exist_ok=True)
    inits = []
    for c, start in enumerate(payload["starts"]):
        theta = np.asarray(start["start"], dtype=float)
        init = nest(names, sm.param_constrain(theta))
        path = work / f"init-{c}.json"
        path.write_text(json.dumps(init), encoding="utf-8")
        inits.append(str(path))
    cm = cmdstanpy.CmdStanModel(stan_file=str(HERE / "models" / "cmdstan" / f"{model}.stan"))
    t = time.perf_counter()
    fit = cm.sample(data=str(data), chains=4, parallel_chains=4, iter_warmup=1000, iter_sampling=1000,
                    seed=seed, inits=inits, save_warmup=True, output_dir=str(work), show_progress=False)
    wall = time.perf_counter() - t
    cols = list(fit.column_names)
    draws = fit.draws(inc_warmup=True)  # (iterations, chains, columns)
    trace = {}
    for key in ["stepsize__", "accept_stat__", "treedepth__", "n_leapfrog__", "divergent__", "lp__", "energy__"]:
        j = cols.index(key)
        trace[key] = [draws[:, c, j].tolist() for c in range(draws.shape[1])]
    metric = [np.asarray(m, dtype=float).tolist() for m in fit.metric]
    step = [float(s) for s in fit.step_size]
    import arviz as az

    param_idx = [i for i, n in enumerate(cols) if not n.endswith("__")]
    retained = draws[1000:, :, :][:, :, param_idx]  # (draws, chains, P)
    arr = np.transpose(retained, (1, 0, 2))
    ds = az.convert_to_dataset({"p": arr})
    bulk = np.asarray(az.ess(ds, method="bulk").p.values, dtype=float)
    tail = np.asarray(az.ess(ds, method="tail", prob=(0.05, 0.95)).p.values, dtype=float)
    rhat = np.asarray(az.rhat(ds, method="rank").p.values, dtype=float)
    n_leap = np.asarray(trace["n_leapfrog__"])
    result = {
        "schema": "step-collapse-v1-cmdstan-trace",
        "model": model, "seed": seed, "wall_seconds": wall,
        "param_names": [cols[i] for i in param_idx],
        "final_step_size": step, "inv_metric": metric,
        "gradients_total": int(n_leap.sum()), "gradients_sampling": int(n_leap[:, 1000:].sum()),
        "min_bulk_ess": float(np.nanmin(bulk)), "min_tail_ess": float(np.nanmin(tail)),
        "max_rhat": float(np.nanmax(rhat)),
        "retained_divergences": int(np.asarray(trace["divergent__"])[:, 1000:].sum()),
        "retained_depth_caps": int((np.asarray(trace["treedepth__"])[:, 1000:] >= 10).sum()),
        "trace": trace,
    }
    result["min_bulk_ess_per_gradient"] = result["min_bulk_ess"] / result["gradients_total"]
    out = out or (HERE / "artifacts" / "cmdstan" / f"{model}-{seed}.json")
    out.write_text(json.dumps(result), encoding="utf-8")
    print(f"{model} {seed}: h {['%.4g' % s for s in step]} min bulk ESS {result['min_bulk_ess']:.0f} "
          f"grads {result['gradients_total']} ESS/grad*1e3 {1e3 * result['min_bulk_ess_per_gradient']:.3f} "
          f"caps {result['retained_depth_caps']} wall {wall:.0f}s", flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else None)
