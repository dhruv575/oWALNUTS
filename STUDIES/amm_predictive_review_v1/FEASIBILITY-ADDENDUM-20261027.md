# Fresh qualification feasibility addendum — 2026-10-27

Design review only. This is not a preregistration, seed reservation, authorization
of a run, or a replacement for the original studies. No sampling or benchmarking
was performed for this review.

## Decision prerequisite

The original proposal's policy-selection prerequisite failed: all WP96 policies
failed their frozen accuracy rules. Analytic scale-CDF reanalysis improves many
rows but still does not rescue a policy. The ongoing fixed-K diagnostic may
nominate a candidate; it cannot retrospectively qualify one. If none of its fixed
budgets satisfies the proposed accuracy and practical-cost requirements, stop
qualification planning at an implementation/precision diagnostic. Do not invent
an MCSE stopping rule: the Gaussian diagnostic demonstrates that short correlated
chains can substantially understate their uncertainty.

## Smallest useful fresh design to consider

A proposed bounded alternative is two fresh independent innovation seeds, each
used for a paired stationary/shifted stream: four streams total, N=250, 512 updates,
shift entering at update 257. Pairing improves comparisons but gives only two
independent data replications per regime. Use exactly one candidate fixed K,
selected and documented before any fresh outputs. No pooling, re-adaptation search,
or second K selected after observing failures.

Twenty scheduled origins per stream give 80 references and a transparent 95%
per-stream fraction: [1,32,64,128,192,224,255,256,257,258,260,264,272,288,320,352,
384,448,507,512]. This includes shock onset and a fully replaced post-shift window.
A possible mechanical rule is at least 76/80 jointly accurate and at least 19/20
per stream, with missing/invalid references retained in the denominator. These are
proposed engineering thresholds, not confidence bounds or inherited qualification.
Keep scale P50/P95 relative bars at 2%/5%; separately predeclare return P5/P50/P95
error at 2% of reference 90% interval width and report all three errors. The original
0.4-second practical budget would apply to the complete refresh, not sampler time.
Record every-update latency and failure, not only these 80 origins.

Use independent nutpie corroboration at updates 256 and 512 in each stream (eight
fits), covering both regimes and fresh seeds. Share primary references across
paired estimator comparisons and expose their common uncertainty. Require the
original proposed global/endpoint convergence checks, retained divergences, and
long-reference functional precision checks. Independent sampler disagreement must
be retained, not averaged away. Freeze a simultaneous comparison rule and a finite
follow-up allowance before execution; eight fits do not validate all references.
This remains a narrow computational qualification, not convincing predictive
calibration or proof of every-tick accuracy.

Candidate data seeds 981801 and 981802 and independent-reference bases 981901 and
981902 had no exact matches in the searched warm-precision worktree STUDIES Python,
Markdown and JSON files. This is only an availability hint. It is not a complete
collision audit: all derived sampler/reference seeds, tracked artifacts, and other
active worktrees must be checked and frozen before any generation.

## Integration and reference readiness are actual blockers

The WP96 runner's compact output omits beta. A full predictive-return calculation
requires joint beta draws with mu, log_sigma and h_last. The existing WarmSession
API offers a plausible resident harness, but feasibility is not implementation:
validate its target, priors, noncentered boundary remap, sampler settings and chain
identity against the frozen runner before timing it. Time one resident call from
new observation/window construction through remapping, sampling, analytic scale
quantiles and numerically checked return quantiles. Include target rebuild, data
movement, checks and failures. Adding separately measured arithmetic to archived
sampler time is not an end-to-end measurement, nor is asynchronous file processing.

Local same-origin numerical work suggests return arithmetic can be inexpensive:
K200's 800 components took 34.62 ms at GH8, versus 419.62 ms at GH128. These are
single-origin Windows arithmetic timings, not Linux online latency or evidence to
choose GH8 globally. Broad-sigma fixtures matter. A candidate 8/16 comparison with
32/64/128 fallback requires validation, an explicit discrepancy policy, and its
full cost in the timer. Pair agreement is not a rigorous error bound. Preserve
CDF residual <=1e-8 and numerical cross-order discrepancy <=1e-6 or explicitly
justify a different rule before freezing; never relax it after seeing results.

Read-only remote inspection found nutpie 0.16.8, cmdstanpy 1.3.0, NumPy 2.5.4,
ArviZ 0.23.4 and a cached SV CmdStan executable at
/home/ubuntu/lanes/sv_stuck_chains_v1/work/cmdstan-exe/sv. Availability is not proof
of matching source, compilation readiness, or runtime. The checked-in SV Stan
model includes the stationary initial latent, beta prior and t likelihood needed
for an N250 window; compare exact input priors/data and source identities before
using a compiled artifact. No compilation or benchmark ran during current studies.

## Honest compute envelope

The smaller design still needs 80 primary references, eight independent fits and
2,048 online updates including full return summaries. The 80,000-component full
return reference on one local origin cost 68.5 seconds for GH64/128; GH8/16 alone
cost about 10.2 seconds. Thus reference postprocessing alone can consume roughly
14 minutes serial at that observed low-order workload, or much longer with required
higher-order checks. These extrapolations are illustrative, not Linux estimates.
Sampler and independent-fit costs, compilation and integrated summary costs remain
unmeasured. A 60-minute completion promise is therefore unsupported.

Only proceed after current timing lanes drain, correctness checks pass, and a
bounded development smoke measures the complete workload on the actual host.
Count compilation, smoke, sampling, references, postprocessing, validation and
archival inside a single 60-minute future-compute ceiling, with two four-core lanes
and no new instance. Absolute deadline remains 19:35 UTC. Reserve time for complete
artifact retrieval and stop the run before that deadline; do not spend the archive
reserve on extra origins. Never thin references merely to meet the budget.

If the measured upper-bound projection cannot fit with margin, the practical next
action is only an integrated harness/reference smoke on development seeds and a
later frozen study. A two-stream/20-origin-per-stream screen halves reference work
but provides only one independent stream pair and cannot substitute for the above
fresh qualification. No automatic reduction after inspecting outcomes is allowed.

## Scope and the bounded-history constraint

WP97 grows the history from 250 to 350 returns and weights stale particles only by
new likelihood factors. WP96 removes old observations and changes the stationary
window boundary. Transplanting WP97's weights unchanged is mathematically wrong:
removal likelihoods and boundary-prior density ratios must be derived and validated.
Its compact endpoint/global draws may not contain the required information. Keep
pooling excluded until a separate proper sliding-window reuse method exists.

Forecast interval coverage, proper scores and PIT from 512 dependent labels per
stream would be descriptive model checks. Compare a privileged generator oracle
and a causal rolling Student-t baseline; do not treat serial labels as independent
replications or equate posterior-reference agreement with calibration. Neither
study establishes executable quotes, inventory control, adverse-selection protection,
profitability, or deployment readiness.
