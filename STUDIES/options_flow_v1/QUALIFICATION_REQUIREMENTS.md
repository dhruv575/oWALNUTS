# Qualification readiness and remaining gates

Independent read-only scientific review, 2026-10-03. No sampling or tests were
run during the active timing experiment. This is a proposed exact decision
design, not a frozen protocol and not achieved evidence. Current status:
**ready to select and freeze component protocols after the missing execution
contracts below are implemented; not ready to claim the full goal achieved.**

Scope clarification, 2026-10-03: the numerical thresholds and study sizes below
are proposed qualification designs, not additional user requirements. The user's
goal is a materially easier or faster useful, demanding uncertainty workflow.
Sampler correctness, endpoint accuracy, reliability, and measured workflow costs
must be established separately from whether a particular market's order flow
contains incremental predictive information. Positive financial alpha is not a
sampler acceptance requirement. A model comparison that reliably finds no flow
benefit can still be a useful inference workflow; it cannot support a claim of
improved market prediction.

## Keep four claims separate

1. The implementation targets the intended posterior and produces calibrated
   intervals under the declared generative model.
2. It reliably computes demanding long-path posteriors and interval endpoints.
3. It reaches that precision materially faster, or is demonstrably easier to use,
   than the best qualified matched alternative.
4. The resulting market workflow provides useful uncertainty estimates on real,
   chronologically held-out observations.

Small-model calibration is a tractable component of claim 1. It cannot replace
claims 2-4. Conversely, a healthy T=1000 benchmark cannot replace calibration.
No single aggregate pass should collapse these distinctions.

## A. Computational calibration: budget and exact scope

Freeze two separate model qualification claims: hierarchical volatility flow
model and exogenous-anchor local-level application model. The actual
empirical-Bayes application convention remains a separately labelled
computational-comparison target; ordinary prior-generative coverage cannot
validate its data-dependent prior.

Suggested calibration sizes: T=32, G=2 for the flow model; T=32 for local level.
Use 1,200 independent prior-generative datasets **per model**, with independent
generator, sampler and predictive RNG streams. The proposed deployed candidate
is the primary calibration arm; it need not duplicate a full calibration study
for every losing exploratory configuration. Baseline correctness is instead
checked independently on reference fixtures and demanding workloads below.

Freeze exactly six primary 90% interval functionals for each model:

| Flow model | Exogenous-anchor local level |
|---|---|
| beta_bar | initial latent log value |
| tau | terminal latent log value |
| mu_h | mean latent log value |
| sigma_h | sigma_obs |
| terminal h | sigma_rw |
| next observed y in group 0, x_next=0 | next observed log price at dt=1 |

For the last row, generate an independent future outcome from the same joint
generative fixture; include both future state and observation noise. This is
prior-predictive coverage, not a parameter SBC rank. Other quantities and levels
can be reported descriptively, explicitly outside this six-functional decision.
Adding a primary changes the multiplicity and power calculation.

For each functional, compute a two-sided exact Clopper-Pearson coverage interval
with tail probability .05/(2*6), and require the complete interval inside
[.85,.95]. At n=1200, saved `calibration-power.json` gives accepted counts
1053 through 1118 inclusive and per-functional pass probability
0.9949616376159662 when coverage is exactly .90. The union bound gives all-six
power at least 0.9697698256957972 without assuming independence among functionals.
At n=800, the corresponding conservative lower bound is only about .633.

Those are **per-model 95% familywise claims**. If the final headline asserts a
single simultaneous confidence statement across both model families, either
allocate alpha=.025 to each six-functional family or recompute at family_size=12.
Do not quote the saved family_size=6 power for this enlarged claim. Recompute and
archive exact operating characteristics at .90, .85, .95 and selected interior
alternatives after finalizing the family. Require conservative all-primary power
>=.90 at exact calibration. The +/-5-point margin is a declared initial
engineering tolerance, not evidence of +/-1-point financial calibration.

Fit failures remain failures: report attempted count from the frozen manifest,
not the number of report files found on disk. For a conservative unconditional
usable-and-covering calculation, count failed fits as noncoverage. Separately
require a one-sided 95% exact lower bound on usable-fit probability >=.99.
Report conditional coverage too, but it cannot alone pass the workflow gate.
All fits need the same frozen maximum tier/retry policy and resource budget.

SBC rank histograms are a complementary distribution check. The current
ESS-spacing/random-subsampling heuristic in `calibration.py` does not prove
independence and its KS p-values must remain exploratory. If a formal rank gate
is desired, implement and validate an autocorrelation-aware SBC method or obtain
independently simulated posterior samples and preregister its multiplicity and
power. Do not rename coverage-equivalence alone as full SBC validation. Numerical
parity, exact controls and external posterior agreement remain required even
when interval coverage passes.

## B. Demanding accuracy and time-to-interval performance

Suggested frozen demanding grid: flow (T,G)=(128,4),(1000,4) and local-level
T=128,1000. Include a regular and a predeclared difficult low-innovation/high-
observation-noise regime for each size; preserve priors and target definitions.
Use at least six fresh paired dataset/sampler seed pairs per workload after a
pilot-based variance/power estimate. Six is a starting allocation, not a claim
that the speedup confidence interval will be sufficiently narrow. Include the
original application's empirical-Bayes convention as an explicitly separate
port check. Its observed-price interval extension must be labelled an extension.

Compare frozen deployed oWALNUTS candidate, shipped-default oWALNUTS, matched
NumPyro centered/noncentered candidates selected by a rule fixed before evidence,
and the application's settings where relevant. Do not choose a baseline that
lost the pilot merely to increase the speed ratio. A candidate different from
the shipped default may qualify as an opt-in application recipe without
establishing that core defaults should change.

Each measured fit must satisfy four chains, rank R-hat<=1.01, bulk and tail
ESS>=400 on every canonical coordinate and every primary functional, zero
retained divergences, and the endpoint precision rule. Record depth caps,
failures and full intended denominator. Apply independent posterior agreement
checks to the demanding workloads; two unhealthy fits are not an accuracy
reference. Exact small Gaussian controls and target/gradient parity remain
separate controls for the numerical implementation.

Proposed endpoint precision gate: both endpoints of each primary 90% interval
have estimated MCSE <= 0.02 times that interval's estimated width; require the
same for next-observation predictive endpoints. This is a scale-invariant
engineering precision gate, distinct from market utility. Declare handling of
zero width and nonfinite estimates as failure. Record MCSE in original units
too. Endpoint-MCSE estimates must be checked against dispersion across independent
replicate fits on a pilot reference, especially for heavy-tailed predictions;
one noise draw per posterior draw must not silently conceal poor posterior
mixing. Quantile precision cannot be inferred from bulk ESS alone.

Freeze retained-length tiers such as 1000,2000,4000,8000 per chain, warmup length,
initialization, maximum duration and the exact first-passing rule. If a worker
cannot resume without redoing warmup, every restart/tier cost counts. If it can
resume, validate adaptation remains frozen and archive checkpoints. Checking
estimated precision repeatedly is part of the declared procedure; report its
observed stability rather than retrospectively selecting a favourable checkpoint.

Primary clock: from invocation to checked, serialized interval output, including
imports, initialization, JIT, all attempted warmup/retention tiers, diagnostics
and prediction. Report one-time install/Rust build separately and give an
amortized comparison at a frozen fit count. Add a steady-state repeated-fit
track in a persistent process so cold JIT alone cannot support a repeated-use
headline. Run timing arms sequentially with balanced order and matched cores.

Suggested speed rule: paired geometric-mean ratio >=1.25, paired 95% interval
excluding 1.0, no workload geometric mean below .90, and no reduced healthy-fit
rate. Freeze the resampling unit as independent dataset/seed pair, stratified
by workload; never bootstrap individual posterior draws as independent timing
replications. Pairwise healthy-only speed is secondary. Timeouts are censored
failures, not removable slow observations; a failed workload fails qualification
unless a separately prespecified reliability-aware statistic handles it.

## C. Real-market usefulness remains a required, separate track

The subsequently acquired `artifacts/deribit-access-panel-v3` contains an audited
historical crypto-options trade panel. Its feature audit preserves 335 scheduled
origins across four contracts, with only 18 development, four validation, and
68 evaluation observations. This supports a sparse computational demonstration,
not a sufficiently powered market qualification. Exchange event timestamps and
an assumed availability lag do not establish historical receipt availability.
Neither synthetic replicates nor a local option-price port can fill those gaps.
Before market freeze identify licensed/source-verifiable data, one estimand,
forecast issuance, horizon, universe, flow-classification quality and trading
calendar. A provider-shaped fixture is not evidence of historical authenticity.

Implement rolling forecast origins using only data available at each origin.
The existing fixed-training posterior with later realized covariates is a
retrospective conditional forecast; it becomes operational only if those
covariates are known at issuance or are explicitly forecast/integrated out.
Training-only scaling must be repeated inside each training window. Calendar
gaps, contract expiry and instrument rollover need declared treatment.

Require a no-flow model with identical noise/volatility structure and a simple
historical baseline. Freeze primary 90% proper interval score, with secondary
50/80/95% intervals, widths and calibration by regime. Use paired time-block
uncertainty with concurrent underlyings grouped together. Select independent
block count from a declared detectable score improvement and coverage tolerance,
not raw row count. A claim of incremental flow predictive value should require
improvement relative to the no-flow model with a paired interval excluding zero,
while coverage lies
within a practically chosen equivalence range. Choose that range before seeing
held-out results; synthetic +/-5 points is not automatically an acceptable
application margin. Absence of incremental flow information is a model/data
finding, not something a faster sampler can cure. That outcome must remain in
the report and must not be treated as a failure of the sampler's computational
usefulness when matched accuracy, reliability, and workflow gains are established.

## D. Feasibility and freeze blockers

With two candidate-only 1,200-replicate calibration families there are 2,400
four-chain fits before retries. At 15 seconds per complete fit this is 10 serial
hours; at 60 seconds it is 40 hours. These are transparent budget examples, not
measured projections. Adding a complete baseline calibration doubles them.
Independent calibration workers can run concurrently when not used for timing;
avoid repeated JAX compilation by a validated persistent worker per target
shape, and cap memory/threads. The demanding timing grid must remain isolated.
Compute the real budget from a pilot including generation, reporting and failed
tiers before launch, and archive that estimate.

Before freezing, implement the missing exact calibration decision and intended
manifest denominator, predictive coverage truth, local-level aggregation,
precision-tier execution, full elapsed timing, baseline selection and original-
unit reporting. Existing `calibration.py` reports unadjusted descriptive coverage
intervals and `compare.py` explicitly lacks time-to-target stopping; neither is
the qualification implementation. Freeze seeds disjoint from exploratory runs,
source/build attestations, dependency versions and checksums in committed
preregistration files. A human usability claim additionally needs observed
independent onboarding; a runnable example proves reproducibility, not ease.

The staged design controls cost while preserving the full objective: extensive
small-model calibration, demanding long-path accuracy/performance, and real
market usefulness all remain necessary evidence with distinct completion flags.
