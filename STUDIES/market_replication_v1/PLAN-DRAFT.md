# Three mandatory historical replication panels

Status: draft, before acquisition or outcome inspection. All three panels and
methods must be frozen together. This is inference research, not deployment or
profit qualification. The scientific question is whether the E62 observed-return
forecast advantage survives other calendar periods under unchanged methods.

## Fixed data and causal indexing

Use BTC-PERPETUAL traded OHLC bars from the existing Deribit history endpoint,
resolution 30, one request per UTC day. Acquire March 26 through June 30, 2026:
97 days, 4,656 exact-grid bars. No alternate venue, instrument, dates, gap filling,
retry, missing-day replacement or outcome-based period selection. Preserve raw
responses before validation and all failure records. Historical bar-open ticks
and close availability at open + 30 minutes retain E62's disclosed conventions;
no live-publication or vendor-revision guarantee is inferred.

| Mandatory panel | Context begins | Forecast origins | Labels close through | Relevant returns | Reference ticks |
|---|---|---:|---|---:|---|
| April 2026 | March 26 | 1,440 | May 1 00:00 UTC | 1,691 | 1,207,412,618,823,1029,1234,1440 |
| May 2026 | April 25 | 1,488 | June 1 00:00 UTC | 1,739 | 1,213,426,638,851,1063,1276,1488 |
| June 2026 | May 26 | 1,440 | July 1 00:00 UTC | 1,691 | 1,207,412,618,823,1029,1234,1440 |

Each panel takes its context-plus-month bars, discards the first 36 bar closes,
and differences log closes. For N origins, retain N+252 closes and N+251 returns.
Initialize from y[:250]. Tick t=1..N assimilates y[249+t], uses y[t:250+t],
and scores next return y[250+t]. Origins begin month day 1 00:00 and end last
day 23:30 UTC. No future label enters any fit. All three models/baselines reset
independently at their declared initialization; no posterior or EWMA state crosses
panel boundaries. May/June warmup observations overlap earlier planned labels;
this is causal and explicitly prevents treating months as independent samples.

## Unchanged E62 methods

Reuse the exact E62 fixed-window resident SV target, priors, K400/four chains,
initial warmup/retained draws, initial guard, remapping, numerical options and
current unpooled posterior draws. No speed, model, K, quadrature, baseline or
adaptation tuning. Baselines are the exact E60/E62 rolling250 Student-t5 MLE and
longer-memory EWMA Student-t5 lambda 0.94, with its location and initial variance
fit from that month's initial 250 returns. All methods have identical causal data
availability; SV/rolling choose 250-return memory while EWMA retains history since
that panel's initial fit. No reset-EWMA or additional comparator is introduced.

Compute log density and PIT at the observed next return with the exact GH64/128
module and E62 tolerances/roundoff policy. Fixed independent references at the
listed eight evenly spaced ticks per month retain four chains/2,000 warmup/
4,000 draws and all E62 diagnostic/MCSE gates. Reference failures do not replace
candidate scores. Candidate and reference delta-density/PIT MCSE remain separate
from time-series uncertainty and are diagnostic, not stopping/adaptation rules.

Native-state failure poisons/stops that panel's candidate loop. A downstream
scoring failure after successful native advance preserves draws and continues
causal state evolution. Persistence failures stop the affected job. Other months
and baseline/reference arms continue if process/resource integrity permits.
No retries, reruns, score replacements or relaxed thresholds. Every planned slot
remains represented: 4,368 origins, 13,104 arm scores and 24 reference slots.

## Fixed reporting and serial uncertainty

For EACH month, primary endpoint is mean paired SV-minus-rolling t5 logscore;
SV-minus-EWMA is secondary. Report all three months and both comparisons regardless
of signs. Repeat E62's 10,000 circular paired-origin bootstrap draws with block
lengths 24/48/96 (12/24/48hours), primary 48. All arms share bootstrap indices within
a month. Use separate prespecified bootstrap seed per month. Keep daily means,
cumulative scores, leave-one-day-out means, PIT histograms/moments/tails/ACF 1 and 48,
measured costs, numerical failures and all reference discrepancies/uncertainties.
The only panel-size changes are calendar day count and reference tick positions.

Per-month intervals are descriptive, not a family-wise replication decision or
independent repeated significance tests. Adjacent months, overlapping context,
market dependence and 250-return windows preclude IID month pooling. Report the
origin-weighted aggregate paired mean only as descriptive, with no pooled CI,
p-value, meta-analysis, best-month selection or pass-count qualification. Require
complete scores in all planned panels for that aggregate; otherwise null it and
retain explicit available counts. Per-month complete-panel rules match E62.
The 0.01-nat practical reference remains contextual, not a new gate. No profit,
execution-cost or AMM deployment conclusion follows from density scores alone.

## Bounded execution and freeze

Acquisition is a separate local phase before compute, with outcomes quarantined
until all code/source/runtime/data/seed bindings are frozen and reviewed. Proposed
acquisition envelope: 600 seconds whole, 512 MiB owned RSS, 96 MiB total outputs,
2 MiB per response and 48 MiB raw-response total, 20-second inactivity timeout,
0.5-second minimum request spacing, no redirects/retries. Complete/draindown and
sealed byte hashes are mandatory for compute admission; file existence is not.

Reuse the existing verified runtime and shared linear loop, numerical modules,
baseline implementations and process monitor. Only calendar parameterization,
fixed three-panel orchestration and reporting adapters are new. Ops agent owns
combined seed-role audit. The fixed schedule is three concurrent
candidate jobs on disjoint cores0-3/4-7/8-11, all drained before 24 serial reference
jobs, then reports; baseline jobs run serially between candidates and references.
Shared-host candidate timings
are explicitly not isolated E62 latency comparisons. Preserve per-panel original
failure rules and all denominators. Fixed batch bounds are 3,600 seconds internal
and 3,720 seconds external, 4 GiB sampled owned RSS and 2 GiB outputs. Candidate
phase cap is 1,800 seconds, baselines 300 seconds aggregate, references 1,200
seconds aggregate (180 per job), reports 120 seconds aggregate. Reference slots
that cannot start within the fixed remaining budget stay explicitly not started.
No AWS
start, acquisition call, sampler invocation or scientific RNG consumption is
authorized by this draft. Parent owns lifecycle and separate execution approval.
