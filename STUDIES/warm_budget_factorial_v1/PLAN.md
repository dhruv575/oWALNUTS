# E72: two-budget, two-seed warm continuation diagnostic

Exploratory computation on the already exposed E66 December/January/February
panels. Twelve fixed paths: three months x two independent seed schedules x
K in {400,1600} transitions per chain per update. Four chains, unchanged target,
remap, initialization (1000 warmup/200 retained) and frozen metric/step settings.
Run every update in each month; score and retain full arrays only at the original
eight reference spots per month. Retain health and timing records at every tick.
No posterior pooling, resampling, retries, retuning, or origin replacement.

Paired budgets within a month/replicate share the declared initial/warm seed
schedule. Their chains diverge after differing numbers of transitions; shared
seeds do not imply equal posterior draws or independent budget arms. Replicates
use disjoint schedules. Initial seed=4072800000000000000+100000*(2*month_index+replicate);
warm seed=initial+10000; tick seed=warm+4*(tick-1), with four chain seeds per tick.
Reserve all initial chain and warm-tick seeds, including implicit +0..3, before
sampling. Month histories are separate, and market months are not independent
random replicates.

Use E70's fixed extended references; retain their two failures visibly. Primary
outputs are every spot's signed/absolute logpdf and PIT discrepancy, candidate
and reference MCSE separately, and complete per-path end-to-end cost/health.
Summaries for all 24 spots and the 22 passing references must be labelled.
No new success threshold; no selected-seed winner; no whole-path accuracy claim.
This tests resource/precision behavior, not predictive profitability or uniqueness
relative to other inference algorithms. No new historical forecast comparison.

Only two numerical source changes from inherited code: allow K=1600 in adapter
and runner validation. The worker passes K explicitly. Use the same scorer and
target as E66; check their frozen identities. Before market runs, fake-engine
shape/seed tests and a literal 250-return 2-update run at both K must pass.
Literal fixtures are development-only and not counted as scientific paths.

Schedule four jobs at a time on disjoint four-core groups, largest K first to
reduce the idle tail. Each job: 3600 seconds, sampled 4 GiB RSS, 512 MiB outputs.
Campaign: 10000 seconds, 22 GiB sampled RSS, 6 GiB output; require 10 GiB free disk
at admission. No new launches after containment/resource failure. Existing AWS
instance and pinned runtime only. Preserve completed and incomplete evidence.
