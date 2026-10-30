# Staged curvature model screen v1

Frozen before execution, 2026-10-30. Four targets: earnings-logearn_interaction,
kidiq-kidscore_momhsiq, garch-garch11, gp_pois_regr-gp_pois_regr. Last two are
negative controls, not presumed application candidates. Four fresh seeds
928400001--928400004; four uniform[-2,2] starts per cell from NumPy PCG64(seed),
shared by all arms. Preserve any initialization failure, do not retry favorable
starts. Pinned existing BridgeStan model/data and posteriordb reference artifacts.

Unchanged v2 selector and staged schedule: 250 warmup + 100 discarded pilot
samples; states 0,24,49,99 per chain. Gradient central differences at 1e-4 and
5e-5 times (1+abs(qj)), 4*d*16 charged calls. Within-chain pilot variances,
floor 1e-8. Invert selected covariance, freeze mass, 750 step-only warmup and
2000 retained samples, stage-two seed+100000. No block uses diagonal fixed mass.
Controls: diagonal, full dense, auto Hessian-fit(window=2,gain=5,R2=.5), each
1100 warmup and 2000 retained, base seed. All arms have identical total discarded
iteration counts. Staged candidate includes pilot/probe/retained target calls.

Before interpreting performance, qualify reference draws: rank Rhat<=1.01 and
bulk/tail ESS>=400 for every archived reference coordinate. Compare constrained
coordinates in reference order, including transformed parameters when present.
Per cell require same diagnostic gates, zero retained divergences, maximum mean
discrepancy <=4.5 combined mean-MCSE and <=.1 reference SD, SD error <=.1.
Record all coordinates and all failures. No tuning or seed exclusions. This small
screen can reject a candidate; it cannot establish general usefulness.

Continuation gate: all four candidate cells pass on a regression model and
median paired minimum-bulk-ESS/total-call ratio >=1.2 against EACH of diag,dense,
auto, with no greater failure count. A failed control does not count as an
infinite speedup. Need valid matched comparisons. Negative-control regressions
and worst-cell costs must be reported. Wall times include sampler and selection
but not imports/process startup: do not claim end-to-end speed from them.
Any passing model requires larger fresh independent validation plus comparison
with cheap conjugate/approximation baselines before a useful-application claim.

Bound each sampler job at 180s, sampled 2GiB RSS/64MiB output. Sequential
four-thread runs, persistent per-job copies, preserved exceptions, input hashes,
verified private archive. No changes to production defaults, no trading/deploy.
