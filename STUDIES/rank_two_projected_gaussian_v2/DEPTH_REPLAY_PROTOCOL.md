# Depth-3 trace-only replay protocol

Frozen before execution on 2026-08-30.

Seeds are 73001--73004. Target, starts, pooled adaptation, metric rank,
warmup=180, retained=300, windows, and depth=3 match v2. Preflight must complete
before sampling without invoking the target.

Depth+1 is supported only if at least 90% of adaptive maximum-depth transitions
are nondivergent, have finite maximum absolute energy error no greater than
0.1, and have a strictly positive final observed U-turn margin. The depth-3
maximum physical trajectory must also be below at least one analytically
computed Gaussian period. No shadow trajectory is permitted. Mixing gates
remain ESJD and lag-one inefficiency improvements of at least 1.05.
