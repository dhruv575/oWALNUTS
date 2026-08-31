# Neal funnel dual-averaging diagnostic v3

Status: preregistered and fully preflighted, but not authorized or sampled.

The frozen experiment has 12 seed-by-cell dispatches: three fresh seeds and a
2x2 crossing of restart-center multiplier `{1,10}` with adaptive-diagonal
versus fixed-identity metrics. Its compiled planning preflight proves that all
dispatch configurations fit the public admission machinery with exactly zero
target callbacks and reports `dispatch_ready=true`.

The generic instrumentation is implemented and identity-tested against
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v7`. Sampling remains a
separate authorization decision.

## Authorized execution

Standing authorization was checksum-bound and all 12 cells completed under
the one-billion callback and 300-second process caps. Center-10 adaptive
ESS/call ratios against center-1 were 3.807, 0.168, and 0.263; step-dispersion
reductions were -0.011, -0.536, and -2.118 log units. Thus restart centering
was falsified and no intervention advanced.

The fixed-identity center-1/center-10 pairs were bit-identical within seed, as
expected without metric restarts. Current coarse endpoint versus accepted-
trajectory acceptance correlations were only 0.31--0.44, supporting the
acceptance-noise mechanism. The preregistered metric-coupling rule held on two
seeds. The window-boundary movement rule did not hold. One center-1 adaptive
cell had two retained refinement exhaustions; corrected retained divergences
were zero in every cell. This is diagnostic evidence, not confirmation.
