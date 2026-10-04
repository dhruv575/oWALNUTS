# Fresh paired uncertainty-workflow comparison

Status: DRAFT. No candidate fits have started. This document becomes operative
only with a complete, independently checked protocol.json and a pre-execution
commit binding the protocol, harness, resampling arrays and artifact manifests.

## Question and scope

Does the public mixed-slopes block-32 continuation workflow reduce full cost per
usable uncertainty estimate by more than 20 percent relative to associative
mixed NumPyro (target acceptance 0.9), while satisfying the same accuracy and
reliability requirements on the demanding T1000/G4 posterior?

The speed ratio is reference/public, with a threshold of 1.25. This study tests
repeatability on one fixed posterior. It does not establish market calibration,
frequentist interval coverage, default-sampler superiority, or model adequacy.
The prediction is that the public workflow may be faster, but earlier variable
results leave the outcome uncertain. Failure of any required gate is reportable.

## Intended experiment

Use 36 adjacent pairs, alternating which backend executes first. Each pair has
one independently generated set of four physical chain starts, shared exactly
between backends. Initialization streams are distinct across pairs; all sampler
and prediction streams are distinct across fits and disjoint from initialization
and analysis streams. Literal identities, seeds, starts and historical seed
exclusion evidence must be bound in protocol.json before execution.

Both workflows use 1,000 warmup draws and stop at the first passing retained
tier of 1,000, 2,000, 4,000 or 8,000 draws. Preserve the existing full health and
precision gates over 1,012 coordinates, 14 physical functionals and four
forecasts. The target and group-0 next-flow covariate must match the audited
posterior reference bank. No failed or unstarted fit is replaced or omitted.

Each fit has a 1,800-second containment timeout on CPU 0. The campaign has a
21,600-second admission budget, including validation and normalization; reserve
15 seconds for cleanup. This is not an independent hard controller deadline.
Any total-budget overrun, unstarted fit, unknown cost or integrity failure makes
the runtime conclusion unresolved. Record all intended outcomes regardless.

## Separate decision families

Reliability: each backend's one-sided 97.5-percent exact Clopper-Pearson lower
bound for usable completion probability must exceed 0.90. This is a separate
95-percent family for the two backend probabilities. With only 36 repetitions,
the rule is deliberately sensitive to failures and is not a high-power design.

Accuracy: for each of 12 endpoints in each backend, the signed mean-error
interval must lie wholly within +/-0.02 W_low and the RMS-error upper bound must
not exceed 0.04 W_low. W_low is fixed from the audited reference bank. Allocate
0.05/48 to each of 24 two-sided mean checks and 24 one-sided RMS checks: each
mean tail receives 0.05/96. Use 40,000 prospectively frozen paired bootstrap
resamples, exceeding 20 observations per smallest nominal tail. Each resample
uses one joint reference-bank vector shared across all candidate repetitions,
endpoints and backends. Widen by the audited numerical envelope separately;
do not add candidate MCSE again. Accuracy is conditional on usable fits and the
bootstrap uncertainty is approximate, not certified coverage.

Runtime: divide each backend's total measured workflow cost by its number of
usable completions. Include failed-attempt costs, setup, validation and
postprocessing, with shared controller overhead allocated by a frozen rule.
Preserve complete pairs in resampling. The separate approximate 95-percent
paired-bootstrap interval for reference/public cost per usable completion must
lie wholly above 1.25. A practical-speed conclusion also requires both accuracy
and reliability gates. This conjunction is not an overall 95-percent claim.

Report reference-bank construction separately, including amortization assumptions.
The bank is an approximate reference: joint bootstrap vectors cannot account for
shared missed modes, common implementation errors or model misspecification.

## Freeze and reporting

Before launch, bind exact target, starts, seed-audit evidence, runtime, harness
and decision sources, bank provenance, scales, numerical envelopes, pair mapping,
literal resampling arrays and cost allocation. Independently verify readiness
and commit these artifacts. Changes after freeze require a dated amendment
before affected evidence is interpreted; never relabel pilot output as fresh.

Report every intended fit, all gate results, achieved interval errors, complete
costs, uncertainty and unresolved conditions. Retain immutable raw artifacts
locally with size-and-hash inventories. Chronological market evaluation and
repeated-data calibration remain outstanding requirements of the broader goal.
