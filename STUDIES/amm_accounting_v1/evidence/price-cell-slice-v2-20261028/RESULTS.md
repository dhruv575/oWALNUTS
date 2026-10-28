# Revised rejection envelope: execution succeeds, reference diagnostics fail

All sixteen chains completed in 71.443 seconds outer wall time, with sampled
peak RSS 983.83 MB and 163.59 MB final output. Processes drained and sources
remained unchanged. The cell-specific envelope removed the previous attempt-cap
failures, but that is not posterior-fidelity evidence.

All four slice/Gibbs fits fail the declared all-coordinate diagnostics. Both
T12 fits flag mu, log_sigma and all twelve z coordinates. Both T250 fits flag
mu, log_sigma and all 250 z coordinates. The corresponding NUTS fits have no
failed coordinates. The slice/Gibbs implementation is therefore not admitted
as a validated long-window reference at this budget.

Mean comparisons flag u[139] for T250 width .001 (absolute standardized
discrepancy 4.204) and z[240] for width .00001 (4.116). These flags are descriptive
across many coordinates, and failed mixing diagnostics weaken MCSE-based
interpretation. Neither the flags nor the other agreeing means establish
which sampler is correct. Preserve all coordinates in the CSV reports.

Next investigate the full-core ellipse's mixing and a mathematically valid
blocked update, rather than extending or relabeling this run. Full draws remain
remote pending off-instance archive verification; this checkpoint preserves
source, supervision and every coordinate summary/comparison.
