# Confirmation analysis specification, before acquisition

Status: fixed statistical specification; acquisition and execution admission
still require the exposure audit, implementation tests and source/seed freeze.
This file must be committed before any September/October 2025 outcome inspection.

## Primary target and denominator

Evaluate BTC-PERPETUAL half-hour origins throughout September and October 2025:
1,440 and 1,488 origins, respectively. Fit the proper bounded-scale model at cap
1, rho .95 and Student-t degrees of freedom 5, with unchanged priors and exact
beta rescaling. Cap 1 is the central member of the existing sensitivity grid;
it is not the best development-score cap. Reset each month's state independently.
Use all 250 most recent returns, with the same observed-information and next-label
indexing as the development study. No jitter, deleted ties or altered recording.

Both NUTS and WALNUTS run the existing four-chain, 2,000-warmup, 4,000-retained
configuration on every primary origin. Keep failed slots and original seeds;
do not rerun with replacement seeds or extend budgets after inspecting outcomes.
Every comparison requires the frozen physical and predictive diagnostic gates.
Any missing/unqualified primary slot prevents an unqualified confirmation claim;
report available-case summaries separately without imputing favorable scores.

## Endpoints and success rule

Primary comparisons are NUTS predictive mixture log density minus causal
rolling250 t5 and EWMA t5 (lambda .94), separately in each month. NUTS separates
model value from WALNUTS approximation. Four primary monthly contrasts are fixed.
Use log of mean predictive density and the existing GH64/128 numerical gate.
NIG AR1 is a secondary comparator; do not substitute it for a failed primary.

For each primary contrast, report all-origin mean, median, positive fraction,
and paired circular moving-block bootstrap uncertainty. Resample contiguous
96-origin blocks (two days), preserving each sampler/baseline pair. Concatenate
sampled blocks and truncate to the original month length. Use 20,000 bootstrap
replicates and a separately reserved reproducible seed, frozen in the execution
manifest before acquisition. Do not pool months as independent replications.

The screen supports predictive confirmation only if all four one-sided 98.75%
percentile lower bounds exceed zero and all four point estimates exceed 0.01
nats per origin. The 0.01 threshold is a declared research relevance criterion,
not a dollar-profit threshold or an externally validated business requirement.
The four marginal error levels sum to .05; dependence within data and limited
block-bootstrap accuracy remain limitations, not exact finite-sample coverage.
Sensitivity block lengths 48 and 336 are mandatory, with no replacing the primary
length. If sensitivity conclusions differ, report that fragility prominently.

## Sampler fidelity and secondary sensitivity

Report WALNUTS-minus-NUTS at every origin, combined log-score MCSE, monthly mean
differences and descriptive standardized discrepancies. An inference-equivalence
claim additionally requires two-sided 95% block-bootstrap intervals for monthly
mean score differences entirely inside [-0.01,+0.01] nats, alongside complete
diagnostic qualification. This is predictive-functional equivalence only, not
proof of full posterior equality or a precision-matched speed advantage.

At the first origin of every UTC day, also run both engines at caps .5 and 2
with unchanged budgets. These 61 calendar-fixed origins per cap are sensitivity
cases, never independent replicas of primary observations and never candidates
for replacing cap 1. Keep their full failure denominator. Report tail influence,
PIT and separate setup/sampling/diagnostic costs descriptively; no post hoc
endpoint promotion or optional stopping on favorable significance.

## Operational and scientific boundaries

All 3,050 primary-plus-sensitivity origin/cap cells must fit a pre-reviewed
bounded batch schedule with exact seed reservations. Preserve full raw traces
in private versioned S3, verify exact-version restores before cleanup, and keep
sources, reports and manifests locally. Do not retain the full study on EC2.
The previous 72-case study suggests roughly eight to ten hours of sampling at
the same concurrency, excluding compilation variance and archive overhead; this
is planning evidence, not a promised runtime or algorithmic speed claim.

No market outcome is fetched by this specification. Acquisition validation,
serial-bootstrap tests, failure accounting and the full execution manifest
must pass review first. This historical project-access study cannot establish
prospective live performance, fee/execution models, economic decision value,
profitability or publication readiness on its own.
