# Matched staged adaptation ablation

Frozen 2026-10-30 before sampling. Earnings is a mechanism test, not an application
requiring MCMC: the direct posterior baseline already qualifies. Sixteen fresh
paired seeds 928600001--928600016, four PCG64(seed) uniform[-2,2] starts per seed.
Same pilot as prior screens: diagonal, 250 warmup +100 discarded draws. Every
stage uses the pilot's final four states, seed+100000, 750 warmup +2000 retained.

Five stage arms: fixed diagonal from pooled within-chain variance (floor1e-8);
fixed empirical dense covariance (mean of four ddof=1 chain covariances);
fixed curvature-block covariance (unchanged v2 selector, 16 two-step Hessians);
adaptive dense; adaptive auto(window2,gain5,R2=.5). Empirical covariance uses
Stan-style regularization n=400, Creg=n/(n+5)*C +.001*5/(n+5)*I. Fixed matrices
are inverted then symmetrized; require finite SPD and inverse residual <=1e-7.
Stage arms share starts/seeds but have their own random trajectories. Pilot work
counts for EVERY arm; only curvature pays 320 gradient probes. Fixed empirical
setup and curvature setup timings are separately charged; no startup-time claim.

Same frozen reference gates as MODEL-SCREEN: Rhat<=1.01, bulk/tail ESS>=400,
zero retained divergences, mean discrepancies <=4.5 combined MCSE and <=.1
reference SD, SD error<=.1. Preserve all failed cells. A curvature-specific
signal requires all 16 curvature and empirical cells pass, geometric-mean paired
minimum-bulk-ESS/total-call ratio >=1.2 against fixed empirical and adaptive dense,
and lower two-sided 95% paired-bootstrap bound >1 for BOTH comparisons. Use
10000 resamples of log ratios, PCG64 seed928699999. Report every ratio, worst
seed, all controls and failures; no replacing failures by infinite speedups.
Failure rejects promotion, not the mathematical kernel. Passing still requires
negative controls and broader nonconjugate targets before a general claim.

Jobs bounded180s/2GiB RSS/64MiB output, four threads, sequential. Compress each
completed job to durable disk with SHA of compressed and uncompressed content;
keep full originals on dedicated tmpfs. Archive/verify all evidence. No library
or sampler default changes. No seed replacement or tuning after results.
