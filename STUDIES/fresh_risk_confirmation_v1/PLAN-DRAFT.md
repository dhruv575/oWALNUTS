# Three historical panels for predictive-return risk limits

Status: pre-acquisition scientific draft. All dates, methods, comparisons and
failure rules below are chosen before requesting or inspecting new outcomes.
The question is whether the E65 exploratory tail-loss advantage persists on
other calendar periods, especially against the stronger EWMA Student-t5 control.
This is inference and risk-limit research, not deployment or profit qualification.

## Exposure and fixed acquisition

Use December 2025, January 2026 and February 2026: the latest three complete
calendar months before March, which is already exposed by earlier acquisitions.
Dates are selected by the calendar and access history, not volatility, returns
or market news. The bounded metadata audit found no acquisition overlap with
November 25, 2025 through February 28, 2026, including all initialization context.
Its 1,692 metadata files, eight archive members, 968 distinct metadata hashes
and 792 request intervals are recorded in EXPOSURE-METADATA.json. This is not a
universal proof of no exposure: raw payloads, unexpanded archives, external
accounts and browser histories are outside that audit. These are historical
holdouts by bounded project access, not prospective live observations.

Acquire one contiguous 96-day interval, November 25 through February 28, from
the unchanged Deribit history get_tradingview_chart_data endpoint, BTC-PERPETUAL,
resolution 30. Require all 4,608 bars on the exact 30-minute grid, 48 per UTC day.
One request per day; no retries, venue substitution, date replacement, gap fill
or outcome-dependent trimming. Preserve raw responses before admission. Reject
internal duplicate/conflicting timestamps; no claim that a single acquisition
detects vendor revisions. Historical tick-as-bar-open and close availability
at open plus 30 minutes remain disclosed conventions, not guaranteed live timing.

| Panel | Origins | Relevant close start index in acquisition | Relevant returns | Fixed reference ticks |
|---|---:|---:|---:|---|
| December 2025 | 1,488 | 36 | 1,739 | 1,213,426,638,851,1063,1276,1488 |
| January 2026 | 1,488 | 1,524 | 1,739 | 1,213,426,638,851,1063,1276,1488 |
| February 2026 | 1,344 | 3,012 | 1,595 | 1,193,385,577,768,960,1152,1344 |

For N origins, use N+252 closes and N+251 log returns. Initialize from y[:250].
At tick t=1..N, assimilate y[249+t]; SV and rolling t5 fit y[t:250+t], and the
next label is y[250+t]. Origins span the complete calendar month, 00:00 on day 1
through 23:30 on its last day; final labels close at the following month's
00:00. Reset posterior and EWMA state independently for every month. Later
months' context overlaps earlier labels causally, so panels are not independent.

## Fixed methods and primary question

Reuse the E64 fixed-window resident SV target, priors, K400, four chains,
initialization/guard, remapping and numerical options without model or speed
tuning. Preserve every current unpooled four-by-400 compact draw array. Independent
references at the eight listed ticks use the unchanged four-chain, 2,000-warmup,
4,000-retained configuration and original diagnostic gates. The E64 observed-y
density/PIT arithmetic remains a development/diagnostic byproduct of the shared
worker, not an additional primary endpoint or a new selection criterion.

Baselines remain the exact rolling250 Student-t5 MLE and longer-memory EWMA
Student-t5 with lambda 0.94, initialized by that month's first 250 returns.
All methods have the same causal observations available; SV and rolling choose
a 250-return memory, while EWMA retains history since the initial fit. No new
baseline, reset-EWMA, optimizer setting or data preprocessing is introduced.

After inference drains, reuse E65's full-return mixture P5/P95 calculation on
all stored draws. No thinning, pooling, sampled future innovations or P50.
Preserve exact t5 CDF, GH64/GH128, chunk512, 64MiB rule cache, dynamic bracket,
Brent xtol=rtol=1e-12, own-root residual <=1e-8, cross-CDF <=1e-6, and endpoint
agreement normalized by the positive GH128 90% interval width <=1e-6.
Baseline quantiles reuse the saved fit parameters; no second optimizer fit.

Long log-return loss is -r with limit -q05; short loss is r with limit q95.
Use the same 95% pinball loss and strict exceedances as E65, without clipping
negative limits. Both tails against EWMA are primary in every month: six
mandatory primary comparisons. Both tails against rolling t5 are six mandatory
secondary comparisons. Report all twelve; no selected side, month or comparator.
Positive advantage is baseline mean pinball loss minus SV mean pinball loss.
Also report relative mean-loss reduction, that difference divided by baseline
mean pinball loss, as an effect-size description. If the denominator is not
strictly positive and finite, report the ratio unavailable, not an alternative.
There is no economic-profit threshold or qualification/pass-count rule.

## Frozen summaries and interpretation

Per month, use 10,000 paired circular-bootstrap resamples with 24/48/96-origin
blocks, 48 primary. The same sampled indices serve every arm, tail and comparison.
Three distinct bootstrap seeds and all native/reference seeds must be reserved
and audited before execution. Report the raw and relative mean-loss effects;
the relative effect is descriptive, with no newly introduced ratio interval.
Retain all block intervals, daily means, cumulative advantage and leave-one-day-
out means. No choice of block length or endpoint after observing results.

Report each arm's mean limit, width, pinball loss, exceedance count/rate and
signed rate minus 5%, with the unchanged exceedance intervals and paired
differences. At all 24 reference spots retain candidate-minus-reference limits
and per-tail candidate-own/reference-own CDF/density delta MCSE. These are
diagnostics, not replacement gates or adaptive precision rules.

All 4,320 origins, 12,960 arm-origin slots and both tails are mandatory. Missing
scores keep their planned denominators and make affected full-panel comparisons
null. Aggregate origin-weighted means are descriptive only: no pooled interval,
FWER-adjusted inference, familywise success claim or independent-regime claim.
Block intervals have serial-dependence limitations, especially overlapping
250-return windows and possible longer market memory. Historical selection by
access does not make the study a live deployment test.

Log-return limits do not establish fills, fees, adverse-selection costs,
inventory-policy performance or P&L. The Student-t return model has infinite
E[exp(R)], so finite expected-price or unbounded-short dollar-loss claims are
unavailable. Bounded utility and bounded positive long downside are distinct.
No unrestricted-hierarchy integrability claim is required for realized pinball.

## Failures, resources and admission

Native-state failure poisons/stops that month's candidate state. A downstream
numerical-score failure preserves its draws and continues causal state updates.
Persistence failures stop the affected job. Independent months, baselines and
references continue only while process/resource integrity permits. Preserve
all numerical, native, precision, infrastructure and admission failures. No
reruns, replacements, tolerance relaxation or partial-panel success claims.

Acquisition is local and separately frozen: 600 seconds whole-process,
512MiB sampled owned RSS, 96MiB output, maximum 2MiB per response/48MiB total
responses, 20-second request inactivity timeout and 0.5-second request spacing.
Only exited-zero, drained, fully sealed and hash-bound acquisition is admitted.
Acquired outcomes remain quarantined until the entire compute plan is frozen.

Proposed fixed compute queue: three candidate processes on disjoint four-core
sets; drain; three baseline jobs; 24 references in four fixed four-core queues;
drain; twelve one-core candidate-tail shards; drain; twelve one-core reference-
tail shards; three monthly reports and metadata finalization. No new statistical
method depends on that operational layout. Ops will bind exact seed maps,
runtime, sources and 57-slot scheduling before launch. Proposed phase caps are
1,800/120/600/600/180/120 seconds, inside 3,600 internal/3,720 external seconds,
12GiB aggregate RSS and 2GiB output. Each reference fit is capped at 180 seconds.
Existing tail origin caps remain 10/60 seconds after literal kernel startup.

Readiness must exercise four simultaneous full reference fits and the same
shared tail deadlines on fixed development inputs, not on new-period outcomes.
No cap-driven subset or reduced reference is allowed. Timing reports separate
native inference, cached-draw quantiles and end-to-end campaign throughput; no
sum of separately measured cached stages is described as measured live latency.
The parent owns AWS lifecycle; the standing preference is a productive reviewed
research queue, without automatic shutdown at each study boundary.
