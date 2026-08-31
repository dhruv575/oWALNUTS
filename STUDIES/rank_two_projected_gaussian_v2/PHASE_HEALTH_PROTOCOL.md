# Phase-separated depth-5 health replay

Frozen before execution on 2026-08-30.

Seeds 79001--79004. This restores target acceptance 0.8 and otherwise uses the
exact validated depth-5 target, algorithm, starts, pooled rank-two adaptation,
warmup=180, retained=300, windows and draws.

Health is versioned, not retroactively changed:

* retained divergences, invalid-evaluation stops, and refinement-exhaustion
  stops must each be zero;
* retained maximum-depth rate must be <=1% aggregate and per chain;
* warmup failures remain fully counted and persisted, with at most one
  divergence/refinement exhaustion per chain and none after initial-fast;
* prior moment and >=1.05 ESJD/inefficiency-improvement gates remain.

Passing authorizes only freezing a T=1000 manifest. It does not authorize
sampling it, and synthetic depth is not inherited automatically.
