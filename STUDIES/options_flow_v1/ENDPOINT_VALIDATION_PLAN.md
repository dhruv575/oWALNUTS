# Independent validation of reported interval-endpoint precision

Draft design, 2026-10-03. This document records a read-only review and proposed
experiment. No numerical imports, fits, benchmarks, or power calculations were
run to prepare it. It is not a frozen qualification protocol or a passing result.

## The claim being tested

On a **fixed posterior target**, repeat the complete inference procedure with
independent initialization, sampler, and prediction streams. Test whether the
dispersion and error of its reported 5th and 95th percentiles agree with their
reported Monte Carlo standard errors (MCSE), and whether its first-passing
precision policy actually delivers the declared endpoint accuracy.

This is computational repeatability and accuracy, not 90% coverage of generating
parameters or future market outcomes. Those remain separate calibration and
real-data experiments in `QUALIFICATION_REQUIREMENTS.md`.

## What the current code establishes, and what it does not

`precision_screen` is a function in `precision_tiers.py`, not a separate file.
It checks `max(endpoint_mcse)/estimated_interval_width <= .02`, together with
the caller's computational health flag. `evaluate.py` and `run_local_level.py`
obtain each MCSE through `arviz.mcse(method='quantile', prob=.05/.95)`. Tail ESS
is a separate health check. Thus the implementation is **not simply substituting
bulk ESS, or the single reported minimum tail ESS, into a quantile formula**.
The installed ArviZ version and exact quantile-MCSE implementation must be
archived at freeze; this review does not claim to have inspected that dependency.

The weakest inference is treating one fit's autocorrelation-based quantile-MCSE
estimate as evidence of its actual endpoint error. Specific gaps are:

- Good within-fit diagnostics do not exclude a shared missed region or common
  initialization bias. The MCSE estimator does not estimate model bias or
  nonstationary initialization error.
- Estimated endpoints, estimated width, and estimated MCSE use the same finite
  draws. A favourable width or downward MCSE fluctuation can trigger a pass.
- The first-passing rule selects using those estimates. Fixed-length agreement
  alone cannot validate the stopped output. Full-restart and continuation
  policies also have different dependence structures and need separate checks.
- Predictive evaluation adds one future latent-state and one observation-noise
  realization per posterior draw. This adds simulation variability and may make
  predictive draws appear weakly autocorrelated even when an important latent
  functional mixes poorly. It does not remove posterior sampling uncertainty.
- Checking each endpoint's estimated standard error does not create a joint
  95% guarantee for every endpoint, group, and horizon. Multiplicity and the
  distinction between standard error and a probability bound must remain explicit.

Current rejection of nonfinite/nonpositive-width intervals is appropriate and
must remain a failure. Valid but unhealthy fits must not disappear from the
denominator while measuring the supposedly reliable stopping rule.

## Fixed targets and primary endpoint family

Before any new outcome is inspected, freeze eight dataset fixtures: flow and
exogenous-anchor local level, each at T=128 and T=1000, each in the regular and
predeclared low-innovation/high-observation-noise regime. Use G=4 for flow.
Specify the generating parameters of the difficult regimes in the manifest;
the regime names alone are not a reproducible specification. Keep all fixture
data fixed within a target throughout this experiment. Do not choose targets
because a candidate already passes them or because estimated MCSE looks suspect.

Use the six primary functionals per model listed in
`QUALIFICATION_REQUIREMENTS.md`, with both endpoints: twelve scalar endpoints
per target/arm/policy. The predictive functional is exactly one next observation
(flow group 0 with x_next=0; local observed log price with dt=1). Hold the
forecast definition fixed. Additional horizons and groups are descriptive,
unless a new primary family and its power allocation are frozen in advance.

Candidate selection is completed using existing exploratory evidence before
these fixtures are generated. Freeze one proposed deployed oWALNUTS recipe and
the strongest matched reference recipe per model, not a new best arm selected
from these repetitions. Do not pool model families or regimes to hide a failure.
The empirical-Bayes application convention can be added as a separately named
fixed-target check; it is not covered by exogenous-anchor generative calibration.

## Independent streams and initial states

Store every integer seed, not only a master seed or an algorithm description.
A proposed reservation, subject to a collision check against existing manifests,
is the following for target d in 0..7, arm a in 0..1, replicate r in 0..399:

- Dataset: `2101000000 + d`.
- Sampler: `2102000000 + 100000*a + 1000*d + r`.
- Initialization: `2103000000 + 1000*d + r`, shared physically across paired arms.
- Primary prediction: `2104000000 + 100000*a + 10000*d + 10*r`.
- Additional predictive replay j in 1..8: primary prediction seed plus j.
- Reference-bank streams: a separate `2110000000` namespace with an explicit
  collision-free allocation recorded before launch.

These numbers are proposals, not a claim that the namespace is already free.
Freeze a manifest-wide collision check, including any library/controller offsets.
Avoid using the existing `seed+130000` convenience rule without checking the
resulting complete seed inventory.

Generate dispersed canonical initial matrices independently of the observed
values, fixture truth, and posterior draws using a declared initialization rule.
Supply the identical physical starts to paired arms and transform them exactly.
Reference-bank initialization is independently dispersed. Fresh independent
fits, rather than chunks of a single chain, are the replication unit.

## An accuracy reference that is not silently exact

For each fixed target, create a separate reference bank before scoring candidate
replications: eight independent long fits from each of two independently checked
backends, with dispersed starts and no shared candidate streams. Freeze initial
reference length and one allowed deterministic doubling schedule, including a
maximum budget. Include density/gradient parity and exact Gaussian controls;
two implementations agreeing can still share a model or exploration error.

The bank must pass the same health checks. Backend-specific endpoint estimates
must agree after accounting for their independently estimated uncertainty.
Define parameter q_ref as the quantile of the pooled bank with equal weight per
independent fit (and equal draw weight within each fit), after the backend
agreement gate; define predictive q_ref by the correspondingly weighted mixture
CDF. Recompute that same estimator in each reference-bank resample, rather than
substituting the average of fit-level quantiles.
Estimate reference uncertainty by resampling **whole independent fits**, with
within-fit dependence retained, and compare endpoint estimates across the two
prespecified length levels. Never bootstrap individual correlated draws as if
independent. Cross-fit bootstrap uncertainty is approximate and its finite-bank
limitations must be reported; use analytic/iid controls below to check that part
of the analysis too.

Require each reference endpoint's uncertainty half-width to be at most .001 of
the reference 90% interval width, and the prespecified length-doubling comparison
to be compatible within that error budget. If the bank cannot establish this
before its frozen cap, label the target **reference unresolved**, do not declare
candidate agreement or remove the target. A long bank is not automatically true.

For predictive reference endpoints, avoid depending solely on another set of
one-noise-draw predictions. At one horizon, condition on each posterior draw,
integrate the future Gaussian innovation, average the Student-t conditional CDF,
then invert the mixture CDF. For flow, integrate over the future normal log
volatility; for local level, integrate over the future normal latent log price.
Gauss-Hermite orders 16,32,64,128 are a proposed deterministic convergence ladder.
Require successive endpoint differences below .0002 of reference width, with a
predeclared cap and failure handling. This provides an independent prediction
calculation and reduces nested simulation noise; it does not make the posterior
bank exact. Keep quadrature error in the reference uncertainty budget.

Let q_ref be a reference endpoint, u_ref its simultaneous uncertainty bound, and
W_ref the associated reference interval width. For conservative error scaling,
use `W_low = (upper_ref-u_upper) - (lower_ref+u_lower)`; nonpositive W_low fails.
The single bank is shared across repetitions. Its error is therefore a common
uncertainty component, not independent noise to redraw separately for every fit.

## Three complementary experiments

1. **Exact/iid controls.** Use known Gaussian and Student-t quantiles to validate
   empirical quantile, MCSE-report parsing, uncertainty calculations, and stopping
   analysis. Include correlated Gaussian sequences with known marginals and
   several frozen persistence values. Treat these as estimator controls, not as
   proof that the posterior chains share their dependence structure.
2. **Fixed-length replication.** Independently repeat four-chain fits at frozen
   retained lengths 1000,2000,4000,8000, with a frozen warmup and resource cap.
   Archive all tiers even when an earlier tier passes. This characterizes MCSE
   calibration without conditioning on first passage. Prefix analysis of a
   frozen-adaptation run and independent full restarts must be labelled separately.
3. **Operational stopping replication.** Independently repeat the actual deployed
   first-passing policy. Reproduce its exact checks, prediction seeds, restart or
   continuation semantics, and maximum tier. Score the selected output and charge
   all attempted work. Validate each policy for which a time-to-precision claim
   will be made; one policy's success cannot qualify the other.

At each primary replicate save its endpoint estimate q_r, reported s_r, width,
health diagnostics, selected tier, all attempted tiers, complete elapsed time,
and failure state. Separately recompute prediction eight times on its **same**
posterior draws with independent future-noise seeds. The primary report remains
the first designated prediction; never select the best replay or pool replays
and call them eight independent fits. Within-fit replay variance estimates nested
prediction noise; across-fit variability reveals the additional posterior-sampling
component. An apparent improvement obtained only by increasing prediction draws
must be charged and independently revalidated as a new execution policy.

## Metrics and a proposed decision rule

Compute each endpoint separately, with dependence among endpoints and paired
arms retained by resampling whole replicate identifiers. The primary calibration
statistic `sqrt(sample_variance(q_r)/mean(s_r^2))` measures repeatability against
reported variance without needing an exact reference. Report its uncertainty,
the distribution of s_r, and heterogeneity by selected tier. Bias relative to
q_ref and squared error address different questions; a variance match can coexist
with a common biased endpoint.

Also report studentized errors, empirical coverage of `q_r +/- 1.96*s_r`, signed
bias/W_low, RMS endpoint error/W_low, and the probability of error <=.04*W_low.
The .04 rule is a separate operational tolerance, not the definition of 2% MCSE.
Account for the reference bank once in each resampling draw and add its uncertainty
conservatively when classifying error/coverage. Report ambiguous classifications
as lower/upper possible rates rather than assuming q_ref is truth.

Proposed frozen component criteria for each target/arm/policy:

- A one-sided usable-output probability bound must exceed .99. Every attempted
  failed, timed-out, nonfinite, unhealthy, or maximum-tier nonpassing fit is an
  unusable outcome. Reference-unresolved targets cannot pass.
- The upper uncertainty bound for the variance-calibration ratio must be <=1.25.
  Ratios much below one are reported as conservatism, not precision failure.
- The entire signed-bias interval, including reference uncertainty, must lie in
  [-.005,.005] times W_low.
- The upper bound on actual endpoint RMS error must be <=.02*W_low for outputs
  selected by the 2% precision policy. Allowing a 1.25 MCSE-calibration ratio alone
  would otherwise silently turn a 2% claim into a 2.5% claim.
- A conservative one-sided bound on the unconditional probability of an
  **usable** output with endpoint error <=.04*W_low must be >=.90. Count unusable
  outputs as failures here. Report conditional error summaries too, but they
  cannot replace this full-denominator requirement.

These are proposed engineering tolerances, not attained guarantees. Freeze exact
uncertainty procedures, simultaneous alpha allocation and acceptance counts before
launch. Suggested scope is a per-target/arm/policy component claim: allocate .025
to reliability and .025 across its twelve endpoints and primary accuracy tests.
A combined claim across targets or policies needs an additional declared family
allocation. Do not present unadjusted marginal intervals as simultaneous evidence.

Use exact binomial bounds for rates and a predeclared outer-replicate bootstrap
for dispersion/bias/RMS, jointly resampling the independent reference bank. The
bootstrap is approximate; inspect exact-control coverage and freeze a sufficient
replication count before it is used as a qualification gate. Resolve finite-sample
power for all primary tests without using confirmatory posterior outcomes.

## Tractable implementation and execution order

First implement an analysis-only adapter consuming saved canonical draws and
reports, plus a manifest of expected replicate IDs. It must preserve failed IDs,
verify endpoint names/scales and reference provenance, store all predictive replay
seeds, and emit reference-unresolved rather than manufacturing a comparison.
Implement conditional predictive-CDF inversion independently of the existing
sample-and-quantile predictor. Add deterministic tests with analytic quantiles,
synthetic biased endpoints, deliberately understated MCSE, missing runs, and
shared-reference uncertainty. These are the immediate implementation tasks.

Then run a clearly exploratory feasibility stage: twenty independent replicates
for one flow and one local T=128 target, both arms, plus exact controls and
reference-bank pilots. Its role is to reveal computation cost, estimator failure,
and analysis bugs; it cannot establish the proposed reliability claim. Do not
retune tolerances after seeing these outcomes. If methods change, date the change,
use new streams, and freeze the resulting design before confirmatory execution.

A proposed confirmatory allocation is 400 independent stopped-procedure replicates
per target/arm, subject to exact reliability power and Monte Carlo uncertainty
operating-characteristic calculations **before freeze**. The eight-target,
two-arm allocation would already require 6,400 procedures plus reference banks
and fixed-length controls: at 30 seconds per procedure that is approximately
53 serial hours, at 120 seconds approximately 213 hours. These are arithmetic
budget examples, not measured forecasts. Independent computational-validation
replicates can run concurrently with declared worker limits; do not mix their
timings into isolated performance measurements.

Stage T=128 and T=1000 work separately for feasibility, but a smaller-target result
does not qualify long-path endpoint accuracy. If the frozen sample size or compute
budget cannot support the proposed bounds, report the component as incomplete
rather than weaken a criterion or replace the fixed intended denominator.

Open before freeze: exact regime parameters, independent-reference budgets,
reference-bank bootstrap adequacy, precise simultaneous error allocation,
acceptance counts and joint power, selected execution policies, and final
collision-checked seeds. No confirmatory execution is specified by this draft
alone; the outstanding methods decisions must first become a committed manifest.
