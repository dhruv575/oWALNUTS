# Depth-5 divergence trace-persistence replay

Frozen before execution on 2026-08-30.

Seeds 77001--77004. Depth, target, starts, pooled adaptation, warmup=180,
retained=300, windows, step search, baseline, health, truncation, moment and
efficiency gates are identical to the depth-5 intervention. Adaptive and
baseline preflights must each leave the target callback counter unchanged.

Adaptive and baseline divergence ownership and counts are reported separately.
Every divergent transition is persisted with seed, chain, warmup/retained
phase, transition index, Hamiltonian extrema and maximum delta, effective
macro step, metric-window membership, refinement level/attempts, depth,
trajectory length, stop, and target-call count. No intervention is
preauthorized by this replay.
