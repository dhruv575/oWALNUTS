# Earnings has a qualified direct posterior sampler

2026-10-30. Four fresh replicates, each 32,768 independent posterior draws, pass
every frozen reference and exact-moment gate. The model has N=1192, p=4, full-rank
design and flat priors on beta and positive sigma. QR gives SSE/2=461.2717868241;
sigma^2 is inverse-gamma with shape 593.5 and that scale, and beta conditional on
sigma is normal with least-squares mean and covariance sigma^2 (X'X)^-1.

Across 64 preflight states, the closed-form unconstrained density (including
log-sigma Jacobian) agrees with Stan up to an additive constant: maximum centered
log-density difference 8.53e-13, scaled gradient discrepancy 6.24e-11. Production
began only after those checks passed. This establishes the algebraic connection
in addition to empirical agreement; the simulation checks alone would not prove it.

QR/moment setup took .000633 seconds; independent generation took .00289--.00428
seconds per 32,768-draw replicate. Sampling uses zero target calls; the separate
verification used 64. Imports, process startup and diagnostics are not included
in these compute timings and no end-to-end speed ratio is claimed. Entire bounded
worker completed in 2.61 seconds, sampled peak RSS ~363 MB, process group drained,
inputs unchanged. Raw draws and every diagnostic are preserved.

This disqualifies the exact earnings model as a compelling application needing
WALNUTS. The earlier 3x median metric-adaptation signal is only algorithm-development
evidence, with a .379 worst ratio and schedule confounding. Next perform a matched
fresh-seed ablation to determine whether curvature information itself helps; any
general improvement must survive broader nonconjugate targets and strong controls.
No actual application, novelty or general algorithm advantage has been established.

Private archive: 20 members, 5,387,212 bytes, SHA256
531a011d5cb62d0c5cd6e8598ab50b3cd56de9f929e4397edb5198cc286d00b2.
Exact-version S3 restore and member checks passed. Archive includes model/source,
data, reference summary, environment, protocol, raw direct draws and supervision;
the full original reference artifact remains in the verified 408-member parent
model screen archive. Production library unchanged; usefulness goal active.
