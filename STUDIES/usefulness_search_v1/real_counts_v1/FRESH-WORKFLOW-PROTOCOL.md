# Fresh serial workflow confirmation

After audited settings screen: raw WAL dense.9, native diagonal.99/maxdepth10,
and the unchanged exact-target conditional importance baseline. Two fresh seeds
951600001 and951600002 per method. MCMC4chains1100warmup4000retained,jitter0
native; importance4096 proposals with full1681-cell grid rebuilt per fit.
No reused reference draws, maps, fitted grids or inference state.

Serial order rep0:WAL,importance,native;rep1:native,importance,WAL. BLAS1, four
MCMC cores. Blocking child-process wall clock includes imports, setup, sampling,
diagnostics and writes; excludes wrapper startup and precompiled libraries.
No simultaneous research jobs on instance during these six timed workflows.
Per workflow300s/3GiB/128MiB;initial free disk>=1GiB,before each job>=512MiB.
No retries,budget extensions or settings changes. Runtime/source hashes fixed.

All160 training quantities compared with independently audited reference. Each
MCMC fit:finite,Rhat<=1.01,bulk/tail ESS>=400,zero retained divergences. Each
importance fit:finite,raw ESS>=1000,Pareto k<.7. Every fit: mean error<=.1refSD,
SD relative error<=.1,mean error/combined MCSE<=4,max MCSE(mean)/refSD<=.025.
Report achieved precision per method. Any failed fit suppresses aggregate
competitive ratios. Even if all pass, time ratios are descriptive with only two
replicates; a pair is precision-comparable only if largest/smallest worst MCSE
across the three methods<=1.5. Otherwise report cost/precision separately.

Independent raw-draw audit required. Importance densities replay on the original
AWS runtime: preserve prior local numerical-replay failure rather than silently
using platform-dependent reconstructed densities. This is a training accuracy
and workflow-cost study, not application/predictive validation. No holdout labels.
