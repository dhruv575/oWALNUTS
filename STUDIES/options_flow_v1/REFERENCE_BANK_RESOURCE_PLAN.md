# Reference-bank resource allocation: proposed next feasibility experiment

Status: draft for review, not frozen and not authorization to execute. Prepared by static source/artifact review while the dense sampler campaign is running. No numerical imports, tests, fits or new power calculations were performed for this plan.

## What must change, and what must not

The existing 48-trial control completed, but every bank was unresolved: 0/24 valid-null banks and 0/24 shifted-backend banks. This is not useful discrimination. The failed gate was backend equivalence at .02 of interval width for both endpoints in every trial; the dependent controls also had length/precision failures. The original four fits/backend, paired lengths128/256 and1000 bootstrap resamples are inadequate evidence for an accuracy reference. The original artifact remains authoritative at `artifacts/reference-bank-controls-v1/REPORT.md`.

The next experiment varies independent fit count and retained length separately at equal total retained information. It does not loosen the .02 exploratory equivalence budget to manufacture passes. The earlier draft engineering claim uses a .001-width posterior reference requirement; it is not a user mandate. That particular claim retains .001 width, twelve endpoints, paired length agreement and independently checked predictive integration. Passing the experiment below only permits budgeting a better bank; it does not qualify candidate endpoint accuracy or authorize the 80-procedure posterior experiment.

## Prospective allocation, before looking at new results

Use known stationary Normal marginals, probabilities .05/.95, both endpoints of the same distribution. For each independent fit use a stationary initial draw and Gaussian AR1 innovations, with rho0 and rho.9 as separate strata. These are exact-marginal estimator controls, not posterior samplers. Generate literal disjoint fit, initialization and bootstrap seed inventories, collision checked against existing manifests and library offsets before freeze.

Compare three allocations per backend:

| Allocation | Independent fits/backend | Paired prefix lengths | Maximum values/backend |
|---|---:|---:|---:|
| More length | 8 | 2048/4096 | 32768 |
| Balanced | 16 | 1024/2048 | 32768 |
| More independent fits | 32 | 512/1024 | 32768 |

Each trial has two backends. Backend A is N(0,1); backend B is respectively N(0,1), N(.1,1), or N(.5,1). The two shifted cases deliberately violate the declared common target; .1 is above .02 times the known Normal90% width, while .5 is the existing gross-failure control. Do not regard a shifted mixture as new reference truth. All trials are independent across allocation/rho/shift; length comparisons alone use paired prefixes. Use eight outer trials per cell, totaling144 trials. This small count is a resource/operating-characteristic screen, not a coverage validation sample size.

Keep the original exploratory budgets: reference half-width .1W, paired-length equivalence .1W, backend equivalence .02W. Archive every component reason so these deliberately loose precision/length gates cannot be mistaken for production .001W gates. Both backend-difference interval ends must lie inside the equivalence band; merely containing zero fails.

Use30000 whole-fit bootstrap resamples, stratified by backend, with one common fit multiplicity vector applied to both probabilities and both lengths. At alpha.05 the existing two-endpoint tail is .05/(6*2), giving125 expected tail resamples. For a future twelve-endpoint family it gives about20.8, so declare minimum_tail_count20. Resample count addresses numerical quantile resolution, not the number of independent bank fits or validity of bootstrap coverage. Retain cached sorted per-fit distributions and weighted-CDF inversion; never sort full pooled arrays again for every resample.

## Bounded execution and acceptance

First run four disjoint timing-only sentinel trials: balanced allocation, each rho, shifts0/.5, with the full bootstrap count. These are an additional declared feasibility set, not replacements for failed144-trial cells. Record wall/CPU, peak memory, serialization volume and per-bootstrap costs; all failures remain in the denominator. Before launch, freeze a sequential-worker limit, a total30minute wall cap and2GiB process-memory cap including the sentinels. Do not silently reduce resamples or continue beyond the cap. Extrapolate144-trial cost from the slowest relevant sentinel with a2x contingency. Proceed within the same frozen campaign only if the estimate fits the remaining cap; otherwise terminate as resource unresolved and design a new campaign. Resource estimates are not sampler performance benchmarks.

For each allocation/rho report full-denominator valid-null resolution, shifted false resolution, simultaneous coverage of the two analytic quantiles, maximum actual endpoint error/known width, reference half-width, backend and length bounds, and all failure reasons. Report exact binomial uncertainty for rates; eight trials cannot establish a small false-resolution probability. Include finite returned bounds from unresolved banks in coverage diagnostics, clearly separate from usable resolved outputs.

A recipe advances only to a larger analytic validation design if, separately for each rho claimed:

- At least6/8 null trials resolve; all eight complete with finite valid estimates.
- Neither the .1 nor .5 shifted set resolves any bank (0/8 each).
- At least7/8 null trials contain both known endpoints in their returned simultaneous bounds, with no resolved trial whose exact endpoint error exceeds its declared uncertainty bound.
- Every identity, paired-prefix, seed, denominator, source/version and numerical-tail-resolution check passes, and the resource cap is respected.

These are explicit engineering screening criteria, not nominal95% coverage acceptance. A failed rho remains unsupported; do not pool it with iid cases. Select among passing allocations by recorded total cost only after presenting all allocations; freeze that choice and use new streams for validation. If none passes, keep the posterior bank unresolved. Do not adjust tolerances after outcomes.

## Shared reference uncertainty and predictive endpoints

Preserve joint bootstrap endpoint vectors and source/raw manifests. In downstream replicate analysis apply one shared bank-resample vector to all candidate repetitions in a bootstrap realization. Never redraw an independent bank error per candidate, or divide bank uncertainty by sqrt(candidate count). Include a nondegenerate analytic check with20 repeated candidate outputs: the common-bank covariance contribution must remain unchanged. This algebra/control check is additional to actual outer-trial coverage assessment.

The allocation controls above cover parameter quantiles only. Before a posterior bank can resolve its predictive endpoint, separately validate the existing observed-only mixture CDF against independent quadrature controls. Bind x_next0 for flow group0 and dt1 for local observed log price, with no held-out label or latent truth in target identity. Freeze GH16/32/64/128 and grid/refinement checks; propagate explicit estimated inversion/quadrature errors into endpoint, backend and paired-length intervals. Distinguish numerical resolution under declared checks from a formally verified error bound. Neither is exact posterior truth.

## Escalation toward the intended accuracy claim

The prior pilot's inverse-square-root extrapolation suggested roughly18x iid and137x rho.9 information to reach .02 backend width from its tiny bank. The equal-information allocations above supply32x as many values/backend (old4 fits times256 =1024; proposed32768) as that pilot, but this is not a guarantee: dependence, independent fit count and bootstrap conservatism differ. Moving from .02 to .001 at unchanged efficiency suggests another400x information. Multiplicity grows from two to twelve endpoints, so this is an optimistic arithmetic scaling, not a runtime promise.

After an allocation passes, first prospectively validate its finite-bank uncertainty coverage with enough new analytic trials to estimate the desired coverage/false-resolution rates; choose that count and acceptance rule before launch, with explicit binomial power and family allocation. Then run only a bounded posterior resource pilot on the two predeclared regular T128 targets, independently initialized backends and two paired lengths. No convenient passing target may be substituted. Record actual effective endpoint precision and cost; project to .001 using measured uncertainty only as a budgeting calculation. A separate approved/frozen maximum determines whether to grow fit count, length or both. If the .001 simultaneous uncertainty and equivalence gates cannot fit that cap, report reference unresolved and restrict80-replicate analysis to repeatability/MCSE dispersion, not independent accuracy.

No32-fit posterior bank, new fixture selection, seed inventory or execution plan is frozen by this document.

## A practical alternative estimand, declared before new results

The .001-width rule belongs to one proposed engineering design, not a necessary definition of accurate inference. Keep it intact when claiming that design passed. A separately frozen analysis may instead estimate candidate bias, RMS error and usable-output accuracy with the reference bank's uncertainty explicitly included, and return intervals rather than a binary qualification verdict. Do not choose between these claims after seeing which one passes.

Let u be the simultaneous reference endpoint uncertainty half-width and W_low the conservative interval-width lower bound. Conditional on that reference uncertainty event, each candidate endpoint's absolute error is bounded by max(0,abs(q_candidate-q_ref)-u) and abs(q_candidate-q_ref)+u. This gives informative partial identification without declaring q_ref exact. Propagate one common bank error through all candidate replicates, retain covariance between endpoints and uncertainty in W_low, and combine candidate-replication sampling uncertainty separately. Reference uncertainty does not shrink just because twenty candidates share the same bank. Report conditional coverage assumptions and the finite-bank bootstrap approximation; these expressions do not prove the bank bounds have their advertised coverage.

Relative bank half-widths .002W, .005W and .01W respectively contribute uncertainty scales of10%,25% and50% of a candidate's .02W reported MCSE. These percentages compare different quantities (bank uncertainty half-width versus candidate standard error); they are scale comparisons, not coverage, power or variance-addition calculations. At each level:

- .002W may permit fairly narrow bias/error bounds, but cannot certify a proposed .005W bias tolerance when the observed discrepancy plus all uncertainties crosses that boundary.
- .005W already uses the entire proposed .005W bias allowance when the observed discrepancy is zero; a nonzero discrepancy or candidate sampling uncertainty prevents that strict claim. Larger bias thresholds or interval-valued conclusions must be prospectively named as different claims.
- .01W can still expose discrepancies well above bank uncertainty and estimate repeatability independently of the bank. It generally leaves small biases poorly resolved. It does not automatically prevent bounding RMS error or usable-output accuracy if the data leave sufficient margin, but no such margin or power has been measured here.

For all three, the actual .02W RMS-error and .04W absolute-error usability criteria, if retained, must be evaluated using propagated conservative error bounds and full failed-procedure denominators. A reported MCSE of .02W is not itself an absolute-error guarantee. Near-boundary outcomes can remain unresolved even with a .001W bank. Repeatability/MCSE calibration, known-marginal estimator controls, posterior diagnostic reliability, and market predictive utility remain different claims.

A resource-limited prospective alternative would freeze a maximum bank budget, publish endpoint-wise reference uncertainty at that cap, and report identified bias/RMS/usability intervals at their achieved resolution. It can support statements such as an explicit upper bound on computational endpoint error, or detection of a discrepancy larger than the reference uncertainty, only when the resulting intervals justify them. It cannot silently claim the earlier .001-width design passed. This alternative should be selected for scientific usefulness and available resources before new outcomes, with its own uncertainty method and claim scope, rather than requiring unbounded reference computation.
