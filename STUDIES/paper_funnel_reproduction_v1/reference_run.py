"""Arm R0/R1: Flatiron walnutpie (PyPI 0.0.3) on the identical funnel.

Usage: python reference_run.py R0|R1 artifacts/R0.json
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import walnutpie as wp

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
D = PROTOCOL["target"]["dimension"]
CALLS = {"n": 0}


def logp(q):
    CALLS["n"] += 1
    v = q[0]
    iv = np.exp(-v)
    x = q[1:]
    ss = float(x @ x)
    g = np.empty_like(q)
    g[0] = -v / 9.0 - 0.5 * (D - 1) + 0.5 * iv * ss
    g[1:] = -iv * x
    return -v * v / 18.0 - 0.5 * (D - 1) * v - 0.5 * iv * ss, g


def main():
    name, out = sys.argv[1], Path(sys.argv[2])
    if out.exists():
        raise SystemExit("refusing to overwrite an arm artifact")
    arm = PROTOCOL["arms"][name]
    assert arm["sampler"].startswith("walnutpie")
    assert wp.__version__ == arm["sampler"].split("-")[1], wp.__version__
    inits = np.asarray(PROTOCOL["starts"], dtype=np.float64)
    started = time.time()
    fit = wp.walnuts_pyfunc(
        logp,
        num_params=D,
        inits=inits,
        num_chains=PROTOCOL["chains"],
        seed=arm["seed"],
        init_inv_metric=np.ones(D),
        save_inv_metric=True,
        min_warmup_iter=arm["min_warmup_iter"],
        max_warmup_iter=arm["max_warmup_iter"],
        min_sampling_iter=arm["sampling_iter"],
        max_sampling_iter=arm["sampling_iter"],
        max_trajectory_doublings=arm["max_trajectory_doublings"],
        max_step_halvings=arm["max_step_halvings"],
        min_micro_steps=arm["min_micro_steps"],
        max_hamiltonian_error=arm["max_hamiltonian_error"],
        step_size_init=arm["step_size_init"],
    )
    wall = time.time() - started
    report = {
        "schema": "owalnuts-paper-funnel-reproduction-arm/v1",
        "arm": name,
        "sampler": arm["sampler"],
        "settings": arm,
        "wall_seconds_including_warmup": wall,
        "target_calls_observed_total": CALLS["n"],
        "chains": [
            {
                "final_step_size": float(c.warmup.stepsize),
                "inv_metric": [float(v) for v in c.warmup.inv_metric],
                "retained": int(c.shape[0]),
            }
            for c in fit
        ],
        "samples": [np.asarray(c).tolist() for c in fit],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report), encoding="utf-8")
    print(f"arm {name} done in {wall:.1f}s, {CALLS['n']} callbacks, steps "
          f"{[round(float(c.warmup.stepsize), 4) for c in fit]}")


if __name__ == "__main__":
    main()
