#!/usr/bin/env python3
"""WP55 reference draws for the two positives that posteriordb has no reference for.

    python make_reference.py seeds   # seeds_data-seeds_centered_model via its non-centred rewrite
    python make_reference.py radon   # radon_all-radon_hierarchical_intercept_centered via posteriordb's
                                     # radon_hierarchical_intercept_noncentered (same posterior)

Frozen procedure (protocol.json "references"): CmdStan 2.39.0 NUTS, 10 chains, 1,000 warmup,
10,000 sampling iterations thinned by 10 (10 x 1,000 draws, the posteriordb reference shape),
adapt_delta 0.95, seed from the protocol. Written: artifacts/reference/<key>.json (per-parameter
mean, sd, MCSE, bulk/tail ESS, R-hat, plus run diagnostics). The draws themselves go to
artifacts/reference/draws/ (ignored). The reference is accepted only if max rank R-hat <= 1.01,
min bulk ESS >= 2,000 and zero divergences; otherwise the cells of that model are analysed
gates-only and that is reported.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
OUT = HERE / "artifacts" / "reference"


def main(key: str) -> None:
    import arviz as az
    import bridgestan as bs
    import cmdstanpy

    spec = PROTOCOL["references"]["models"][key]
    proc = PROTOCOL["references"]["procedure"]
    cmdstanpy.set_cmdstan_path(PROTOCOL["references"]["cmdstan_home"])
    stan = HERE / spec["stan"]
    data = HERE / spec["data"]
    # parameter names of the CENTRED model the cells sample (params + transformed params)
    bs.compile.windows_dll_path_setup()
    so = HERE / "models" / f"{spec['cell_model'].replace('-', '__')}_model.so"
    sm = bs.StanModel(str(so), data=(HERE / "models" / f"{spec['cell_model'].replace('-', '__')}.data.json").read_text(encoding="utf-8"), seed=1)
    names = []
    for n in sm.param_names(include_tp=True, include_gq=False):
        parts = n.split(".")
        names.append(parts[0] if len(parts) == 1 else f"{parts[0]}[{','.join(parts[1:])}]")
    model = cmdstanpy.CmdStanModel(stan_file=str(stan))
    t = time.perf_counter()
    fit = model.sample(data=str(data), chains=proc["chains"], parallel_chains=proc["parallel_chains"],
                       iter_warmup=proc["warmup"], iter_sampling=proc["sampling"], thin=proc["thin"],
                       adapt_delta=proc["adapt_delta"], seed=spec["seed"], show_progress=False,
                       output_dir=str(OUT / "draws" / key))
    wall = time.perf_counter() - t
    draws = fit.draws(concat_chains=False)  # (draws, chains, columns)
    cols = list(fit.column_names)
    missing = [n for n in names if n not in cols]
    if missing:
        raise SystemExit(f"reference columns missing: {missing[:5]}")
    arr = np.transpose(draws[:, :, [cols.index(n) for n in names]], (1, 0, 2)).astype(np.float64)
    ds = az.convert_to_dataset({"p": arr})
    flat = arr.reshape(-1, arr.shape[-1])
    stats = {
        "mean": flat.mean(0), "sd": flat.std(0, ddof=1),
        "mcse": np.asarray(az.mcse(ds, method="mean").p.values, dtype=float),
        "bulk_ess": np.asarray(az.ess(ds, method="bulk").p.values, dtype=float),
        "tail_ess": np.asarray(az.ess(ds, method="tail", prob=(0.05, 0.95)).p.values, dtype=float),
        "rhat": np.asarray(az.rhat(ds, method="rank").p.values, dtype=float),
    }
    div = int(np.asarray(fit.method_variables()["divergent__"]).sum())
    acc = PROTOCOL["references"]["acceptance"]
    ok = (float(np.nanmax(stats["rhat"])) <= acc["max_rank_rhat"]
          and float(np.nanmin(stats["bulk_ess"])) >= acc["min_bulk_ess"] and div <= acc["max_divergences"])
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "silent-funnel-diagnostic-v1-reference", "key": key, "cell_model": spec["cell_model"],
        "stan": spec["stan"], "seed": spec["seed"], "procedure": proc, "wall_seconds_contended": wall,
        "draw_shape": list(arr.shape), "divergences": div,
        "max_rank_rhat": float(np.nanmax(stats["rhat"])), "min_bulk_ess": float(np.nanmin(stats["bulk_ess"])),
        "min_tail_ess": float(np.nanmin(stats["tail_ess"])), "accepted": bool(ok),
        "names": names, **{k: [float(x) for x in v] for k, v in stats.items()},
    }
    (OUT / f"{key}.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"{key}: accepted {ok} rhat {payload['max_rank_rhat']:.4f} bulk {payload['min_bulk_ess']:.0f} "
          f"tail {payload['min_tail_ess']:.0f} div {div} wall {wall:.0f}s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
