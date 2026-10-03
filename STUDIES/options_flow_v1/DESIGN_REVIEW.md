# Independent evaluation design review

Status: proposed gates, not preregistration and not evidence of success. Written
2026-10-03 before inspecting options-flow sampling results. This review owns no
sampler defaults. A decision study must freeze its actual numerical protocol,
seeds, code revision and data hashes before its first evidence cell, following
[`wiki/methods.md`](../../wiki/methods.md).

## What would establish the user goal

The claim has three independently necessary parts: useful uncertainty estimates
on a demanding application; trustworthy computation of those estimates; and a
material improvement in time or effort over an established alternative. A
synthetic posterior benchmark can establish the second part and contribute to
the third. It cannot establish that options order flow predicts market outcomes.
The evaluation should report each part separately and leave missing parts
explicitly unqualified.

Suggested first estimand: the next non-overlapping period's underlying return,
conditional on options-flow information actually available at forecast time.
Return prediction is distinct from inference about the flow coefficient and
from option pricing. Predictive intervals must integrate parameter uncertainty,
future latent-state innovations and future observation noise. No inferred causal
interpretation of a flow coefficient is warranted by predictive performance.

## Data audit and attainable tracks

The repository search found no verified historical options trade/quote dataset.
This is a scoped repository finding, not a claim about the user's other files or
data access. Existing `flagship_crypto_sv_v2/data/*.json` contain daily crypto
closes with OKX provenance. The `numpyro_comparisons_v10_v1/fixtures/real_market_48h.json`
metadata explicitly says `real_prediction_market_curated_48h`; it contains
prediction-market observations, not options order flow. These are useful state
space controls, never substitutes for options-flow validation.

Implement now: synthetic fixtures, exact model contracts, ingest validation,
chronological splitting, comparison runners and a real-data report that refuses
qualification when provenance is absent. A supplied or openly licensed historical
flow dataset can later run through that same interface. A short live collection
can validate ingestion but cannot establish performance across market regimes.

A real input manifest must identify source and redistribution rights, timestamp
timezone, forecast cutoff, horizon, universe selection, aggregation, units and
missingness. Record event time and availability time when different. Direction
inferred from quotes must be labelled inferred; absence of opening/closing or
multi-leg linkage must be explicit. Do not synthesize unavailable fields and
describe them as observed. Training-only scaling, lag construction, survivorship
handling and split boundaries must be reproducible. Future target prices cannot
enter contemporaneous features or scaling.

### Existing application inspected read-only

`C:/dev/optionsWALNUTS` provides a concrete additional benchmark target. Its
`backend/src/price_inference.rs` fits hourly aggregated log option typical prices
with a Student-t(5) observation model and a centered Gaussian random-walk latent
path, with two log-scale globals (dimension T+2). Log observation/RW scales have
normal priors centered at log(.08)/log(.12), each with standard deviation 1;
the initial state has N(first observed log price, 1.5) prior. This data-dependent
initial prior means ordinary prior-generative SBC cannot be applied unchanged:
freeze an externally specified initial anchor for SBC or derive an explicitly
conditional model that excludes the anchor observation from the likelihood.
An exact port may retain the application convention for a matched computational
comparison, provided this convention is disclosed.

The application is not yet an order-flow model: volume weights price aggregation,
but signed flow is not a likelihood predictor. Its separate `inference.rs`
target is a four-dimensional quadratic log-IV smile with Student-t residuals.
The former is the relevant demanding application track; the latter is a small
integration/control track. Port them explicitly with source hashes and parity
checks; label the new hierarchical flow model as a new proposed model.

The current price forecast includes future random-walk innovation but omits
Student-t observation noise. Its interval is therefore for future latent value,
not for the next observed price. Test and label both separately. The fixed UTC
13:30-21:00 weekday session filter is not an exchange calendar; daylight-saving
changes/holidays and irregular missing-hour gaps need explicit treatment before
chronological market validation. The current transition treats every retained
hourly row as one step regardless of gap length. These are model/data-contract
issues, not kernel performance issues.

The inspected provider fixture has only three minute rows, including a malformed
row, and is a transport test. The tiny option-chain fixture is likewise not a
historical evaluation corpus. No root-level `.db` file was found; this does not
exclude data elsewhere or remote persistence. No credentials or environment
files were read. Historical availability remains unverified.

## Computational correctness and calibration

1. Validate independent target implementations at dispersed points, including
   boundaries. Compare log densities up to a parameter-independent constant and
   gradients with both independent autodiff and finite differences. Document
   every transformation/Jacobian and the initial-state distribution.
2. Simulated data used for SBC must draw parameters from the very same normalized
   prior as the fitted target. Fixed-parameter repeated simulation is a separate
   recovery test, not SBC. Save truth, generator seed and data hash; inference
   must not receive truth-dependent starts or metrics.
3. Use four independent chains and require rank R-hat <= 1.01 and bulk/tail ESS
   >= 400 on every model parameter and preregistered predictive functional,
   with zero retained divergences. Record depth saturation and errors. Finite
   output alone is not a healthy fit. These thresholds are an initial screen,
   not a guarantee of accurate extreme quantiles.
4. Check an exact small Gaussian control and a healthy external sampler on each
   demanding fixture. Two failing samplers do not establish correctness. Use
   combined Monte Carlo uncertainty for posterior agreement, with a frozen
   simultaneous rule across the declared comparisons.
5. SBC ranks require effectively independent posterior draws or an explicitly
   autocorrelation-aware procedure. Pooling thousands of correlated draws into
   an ordinary uniform-rank test gives misleading confidence. Record all failed
   replicate fits; dropping them conditions calibration on sampler success.

Start with a small diagnostic screen, then a power-sized calibration study. For
orientation, with independent replicates and true coverage 0.90, the binomial
standard error is 0.030 at 100 replicates and 0.015 at 400; at coverage 0.95 it is
0.022 and 0.011 respectively. These are precision calculations, not achieved
power claims. A 10-20 replicate smoke run cannot qualify coverage. Freeze a
practically meaningful coverage error and compute operating characteristics of
the chosen simultaneous acceptance rule before selecting the final count.
Failure to reject a uniform-rank null is not proof of calibration; report
uncertainty bands and detectable effect size.

## Matched performance experiment

Keep the model, priors, likelihood constants where meaningful, data, starts,
precision, hardware allocation and stopping rule matched. Match transformed
starts when samplers use different coordinates. Different RNG algorithms need
not share trajectories. Do not compare a hand-optimized Rust density against a
slow Python callback and attribute the whole gap to the kernel: report both the
practical end-to-end comparison and the decomposition of target/backend cost.

Run competitors sequentially for timing, with a frozen order balanced across
seeds. Archive version, commit, compiler, thread settings, build flags and
machine metadata. Separate first-install/build, first-fit compile, warmup,
sampling, prediction and total time. For repeated-fit claims include amortized
timing at a declared fit count, never silently remove compilation.

Primary practical statistic: elapsed time to healthy posterior and predictive
endpoint precision at a prespecified tolerance, including warmup and unsuccessful
attempts under a fixed retry policy. Estimate endpoint MCSE using an appropriate
quantile method or replicated fits. If noisy predictive simulation dominates,
increase conditional predictive integration precision equally across arms;
R-hat on added independent future noise alone can conceal unmixed parameters.
Report ESS per density/gradient call including warmup as a secondary mechanism
statistic, and tail-functional precision per second. Preserve timeout/error
cells and the entire intended denominator. Gate failures cannot be replaced by
fresh seeds until the table becomes favourable.

Proposed qualification rule to preregister after the diagnostic screen: at least
1.25x geometric-mean speedup in time to precision over the best qualified matched
baseline across the frozen workload, a paired uncertainty interval excluding
1.0, no workload below 0.90x, and no lower healthy-fit rate. These thresholds are
product choices, not established scientific constants. Report workload-level
results even if the aggregate passes. A speed claim applies only to the measured
sizes, regimes, backend and operating system.

## Real-market usefulness

Freeze rolling or expanding training windows and chronological test blocks;
purge overlapping target horizons at split boundaries. Include a no-flow model
with the same volatility/noise structure and a simple historical-volatility
forecast. Score 50%, 80%, 90% and 95% predictive intervals, widths and a proper
interval score; report predictive scores and PIT diagnostics. Coverage alone can
be improved by making intervals uselessly wide. Declare the primary level and
score before evaluation to avoid choosing the favourable endpoint afterwards.

Use paired time-block uncertainty for score differences and coverage, clustering
across underlyings exposed to the same market period. A large row count does not
imply many independent outcomes. Predefine calm/volatile and liquidity strata
using information available before the forecast; report their sample sizes and
uncertainty. For an incremental flow claim require the flow model to improve the
declared proper score relative to the no-flow model with uncertainty excluding
zero, while meeting the declared calibration tolerance. Lack of flow improvement
is a model/data result, not automatically a sampler defect.

## Ease of use and improvement loop

Provide a reproducible input-to-interval command, pinned dependencies, honest
unhealthy-fit reporting and an example that never requires users to understand
research-only metric internals. Measure clean-install success and elapsed setup
time; distinguish automated reproducibility from actual usability. A credible
ease-of-use claim ultimately needs intended users executing the workflow without
the author repairing it silently. Record manual interventions and configuration
changes for every sampler, including the incumbent.

If the sampler fails, first classify model/gradient bugs, backend failures,
unidentified posterior structure, warmup, and retained mixing. The wiki supports
structured path metrics and investigation of global-to-path coupling, while
full scale noncentring and generic acceptance-statistic sweeps have negative
evidence. Diagnose on exploratory seeds, freeze a new candidate, then confirm on
fresh seeds and the existing Gaussian, funnel and state-space controls. Never
change core defaults solely because one application fixture improves.

Completion requires actual archived evidence for computational correctness,
adequate calibration, qualified matched speed or measured usability improvement,
and a real-data usefulness evaluation. Missing historical flow data must remain
visible as incomplete application evidence; it must not be turned into a
synthetic success claim.

## Implementation audit, 2026-10-03 exploratory harness

This records issues at inspection time, not assertions that later edits retain
them. Concrete fixes were communicated to the evaluation owner and parent.

- `reference.py` separately compiled a value-and-gradient callable that NUTS
  never consumed. That adds gratuitous baseline work to cold-process timing.
  Remove this measurement-only compilation; sampler compilation can remain
  honestly included in warmup where the public API does not separate it.
- The initial reference only supported centered NumPyro while Rust offered a
  noncentered candidate. Include a matched noncentered reference before claiming
  that the proposed sampler beats the best qualified alternative. Initial
  canonical positions currently agree across coordinates, but all chains start
  identically; introduce frozen dispersed matched starts for confirmation.
- `run.py` recorded hashes of source files present at invocation, plus an
  executable hash. These alone do not prove that the executable was built from
  those sources. Preserve a build manifest binding executable and complete
  recursive source/dependency hashes. Dirty HEAD plus current top-level study
  files also misses dirty sampler-library changes.
- Validate worker output dimensions, coordinate convention, arm, seed and run
  lengths before diagnostics. A healthy posterior from an accidentally wrong
  worker or truncated chain must not receive the requested run's label.
- The report's process time covers worker startup/imports, sampling and raw
  serialization, but excludes parent diagnostics and prediction. Name this
  scope accurately and add separately timed evaluation plus complete elapsed
  inference-to-interval time. Rust worker sampling time likewise is not total
  application time or source-build time.
- The ingest adapter initially stamped `source=real` on any CSV with nonempty
  metadata. This is a declaration, not independent verification. Keep dataset
  authenticity/rights unverified until evidence is reviewed. Input SHA-256
  proves byte identity, not provenance, availability time or real market origin.
- The adapter appropriately uses training-only scaling, checks timestamp
  timezone/availability, rejects overlapping horizons and unbalanced panels,
  and records its compressed market-time assumption. It cannot establish that
  an upstream feature builder respected those declared timestamps; audit that
  builder separately. Fixed-origin forecasts condition on later supplied x;
  they are retrospective conditional forecasts, not operational fixed-origin
  predictions when those x values were unavailable at the initial origin.

Positive checks at this inspection: diagnostics cover every canonical parameter
as well as reported functionals; the computational screen requires four chains;
runner health includes zero retained divergences; raw correlated ranks remain
descriptive; qualification and operational-forecast flags remain false.
Thirteen workflow, ingestion and calibration-design tests passed during review.
Those tests establish their named contracts, not SBC, real-data coverage or
comparative speed. The exact coverage planner correctly reports per-functional
equivalence power and discloses that joint power depends on dependence.
