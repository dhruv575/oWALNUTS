# Pre-acquisition implementation checks

2026-10-28: five circular-block bootstrap unit tests passed on both local Python
and the existing pinned AWS scientific environment. Tests cover exact enumerated
small-case block means, wrap/truncation, constant and full-length-block results,
paired columns, chunk-size reproducibility and missing/nonfinite rejection.
These validate implementation invariants, not empirical confidence coverage.

Two outcome-free calendar tests passed locally. They verify all 2,928 primary
origins, both 61-origin cap sensitivity panels, 250-return causal windows,
next-label timing, and within-schedule seed separation. Calendar source proposes
sampler reservation 398201000..398249799 and bootstrap 398300000..398300005.
These ranges are provisional until the global collision audit succeeds.

No September/October candidate outcomes were accessed. Full execution admission
still requires acquisition tests, metadata exposure closure, source/seed freeze,
resource and storage scheduling, and reviewed failure handling.
