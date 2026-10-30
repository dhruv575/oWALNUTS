# Training posterior reference, frozen before execution

Only GP-TRAIN.json SHA256
8c328146cfe6e1956256af63bb3b39cfc0d27be4b8ea7b796d842240056b5576.
Unchanged raw GP model: 79 observations, 81 parameters. No heldout labels.
Four independent groups, each four chains, 2000 warmup and 8000 retained:
native diagonal target_accept .999 maxdepth12 (groups0,1), and WAL dense
target_accept .95 (groups2,3). Seeds951200001 through951200004.
Native jitter0; WAL starts independently uniform(-2,2) using group seed.
These are reference settings, not a timing competition or production tuning.

All160 training functionals: rho,alpha,f79,exp(f)79. Every group must have
finite draws/statistics, rank Rhat<=1.01, bulk and tail ESS>=1000, and zero
retained divergences. Combined16 chains must have Rhat<=1.01, bulk ESS>=4000,
tail ESS>=2000 and maximum MCSE(mean)/SD<=.02. Every pair of groups must agree:
maximum mean difference/combined MCSE<=4, mean difference/pooled SD<=.05,
and relative SD difference (average pair SD denominator)<=.1. These are
diagnostic qualification rules, not a proof of exact posterior fidelity.

Four concurrent workers, four chain cores each, BLAS threads1. Each worker
bounded1200s,4GiB RSS,256MiB output via resource monitor. Require1.5GiB free
before dispatch; no retries or budget extensions. Preserve all failures.
Combined diagnostics run after workers under separate300s/4GiB/16MiB cap.
Runtime and source hashes checked before/after. Save raw draws, diagnostics,
physical functionals, counted calls and supervision. Independent raw audit
required before accepting reference. Future predictive quantities require
separate qualification and numerical-integration/MCSE protocol before scoring.
