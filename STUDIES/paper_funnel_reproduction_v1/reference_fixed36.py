"""Post-hoc arm R36: walnutpie 0.0.3, zero warmup, four single-chain runs whose
initial step search lands exactly on h=0.36 (identity inverse metric),
so that the reference and arm F share h, delta, halvings and depth.
Usage: python reference_fixed36.py artifacts/posthoc-R36.json
"""
import json, sys, time
from pathlib import Path
import numpy as np
import walnutpie as wp
from reference_run import logp, D, PROTOCOL, CALLS

out = Path(sys.argv[1])
if out.exists():
    raise SystemExit("refusing to overwrite")
RET = 30000
chains, steps, seeds = [], [], []
started = time.time()
seed = 81001
while len(chains) < 4 and seed < 81040:
    inits = np.zeros((1, D)); inits[0, 0] = -1.0
    fit = wp.walnuts_pyfunc(logp, num_params=D, inits=inits, num_chains=1, seed=seed,
        init_inv_metric=np.ones(D), save_inv_metric=True,
        min_warmup_iter=0, max_warmup_iter=0, min_sampling_iter=RET, max_sampling_iter=RET,
        max_trajectory_doublings=10, max_step_halvings=9, min_micro_steps=1,
        max_hamiltonian_error=0.21, step_size_init=0.36)
    st = float(fit[0].warmup.stepsize)
    print("seed", seed, "step", st, flush=True)
    if abs(st - 0.36) < 1e-12:
        chains.append(np.asarray(fit[0]).tolist()); steps.append(st); seeds.append(seed)
    seed += 1
wall = time.time() - started
report = {"schema": "owalnuts-paper-funnel-reproduction-arm/v1", "arm": "R36", "sampler": "walnutpie-0.0.3",
          "settings": {"step_size": 0.36, "max_hamiltonian_error": 0.21, "max_step_halvings": 9, "max_trajectory_doublings": 10,
                       "warmup": 0, "retained": RET, "start_omega": -1.0, "seeds_used": seeds, "seeds_tried_from": 81001},
          "wall_seconds_including_warmup": wall, "target_calls_observed_total": CALLS["n"],
          "chains": [{"final_step_size": s, "inv_metric": [1.0] * D, "retained": RET} for s in steps],
          "samples": chains}
out.write_text(json.dumps(report), encoding="utf-8")
print("done", len(chains), "chains", wall, "s")
