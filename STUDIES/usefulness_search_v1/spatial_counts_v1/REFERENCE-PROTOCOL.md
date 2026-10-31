# Spatial training reference attempt, frozen 2026-10-31

Use unchanged 200-cell, 205-parameter target and primary training data from
the qualified spatial smoke. No heldout counts or prediction scores are inputs.
Four independent groups of four chains, 2000 warmup and 2000 retained draws:
native diagonal NUTS target_accept .999, maxdepth 12, jitter 0 (groups 0,1),
WAL dense target_accept .95 (groups 2,3). Seeds 952200001 through 952200004.
WAL starts uniform(-2,2), generated separately by each group seed.

All 405 functionals (rho, alpha, three beta, 200 log intensities and 200
intensities) must have finite statistics, rank Rhat <=1.01, bulk/tail ESS >=1000
and zero retained divergences in every group. Combined 16 chains: Rhat <=1.01,
bulk ESS >=4000, tail ESS >=2000, maximum mean MCSE/SD <=.02. Every pair:
mean difference / combined MCSE <=4, mean difference / combined SD <=.05,
relative SD difference <=.10. These diagnostic gates do not prove exactness.
This smaller retained budget than the earlier temporal study may fail; retain
the failure without relaxing gates or automatically extending the run.

Four concurrent workers, each four exclusive cores, BLAS threads 1. Per worker:
2400 seconds including transformation/diagnostics, 4 GiB summed RSS, 128 MiB
sampled output cap. Require 1.6 GiB initial free disk; stop owned workers if
free disk drops below 1 GiB. Monitor heartbeat every 15 seconds, aggregate CPU,
memory, free disk and completed groups. Combined summary: 300s/4GiB/16MiB.
No retries. Preserve raw draws, warmup/native diagnostics, WAL output, call
counts, source hashes and terminal supervision. Audit before accepting reference.
Worker output caps are sampled, not hard filesystem quotas.

The earlier smoke is copied off-host and hashes verified before launch.
No evidence deletion or additional AWS instance. No timing winner can be
inferred from these reference configurations. Next work is training-only
approximation controls and qualified terrain-only inference, then separately
frozen predictive checks and scoring; reference failure blocks accuracy claims.
