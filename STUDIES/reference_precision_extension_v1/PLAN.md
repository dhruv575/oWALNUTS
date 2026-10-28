# E70: fixed-budget independent-reference precision extension

Exploratory follow-up to E66, motivated by two failed references. All original
24 reference points are included, not just failures. Original E66 results remain
unchanged and no candidate forecast is replaced. No fresh-market confirmation.

Same frozen 250-return target, data, parameterization, nutpie engine, target_accept
0.8, maxdepth 10, four chains and 2,000 warmup per chain. Increase retained draws
from 4,000 to 16,000 per chain. Use new seeds 703028000+1000*j for ordered month
then reference index j=0..23; model-construction seed is sample seed+1. This is a
new fit, not continuation or repair of the original. No retries, no alternate
target, no seed replacement, no threshold relaxation after seeing outcomes.

Retain the original log-density delta-MCSE<=0.01 and PIT MCSE<=0.005, Rhat<=1.01,
bulk/tail ESS>=1000 on the six original functionals, and zero retained divergence
gates. These are diagnostics, not posterior accuracy guarantees. Report all 24
new and original results, numerical availability, costs and discrepancies.
Passing this extension cannot retroactively turn E66's 22/24 into 24/24.

The new adapter changes only retained count/shape from the original adapter.
Reuse the original reference evaluator and capture actual compilation provenance.
Hash-check inherited sources/runtime and sealed acquisition before execution.
Save new source hashes, manifest and per-job logs/monitor receipts.

Four queues of four CPU cores on the existing 16-vCPU instance. Per job 480s,
4 GiB sampled RSS and 1 GiB output; maximum campaign 3,000s plus cleanup. Stop
new launches after a containment/resource failure. Retain unavailable jobs in
the denominator. Compilation and numerical work count toward elapsed time.
Use existing interpreter; no installs or SDK changes. Require at least 8 GiB
free disk at admission. Total output ceiling 4 GiB, sampled during execution.

Seed collision audit covers explicit literals in current project source/metadata;
opaque internal RNG seeds and universal historical independence are not claimed.
The schedule is fixed before sampling. This engineering/scientific follow-up
tests whether a larger independent-reference budget addresses the observed
precision limitation; it does not compare sampler efficiency or AMM profitability.
