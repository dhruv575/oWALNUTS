# August historical predictive comparison: draft before acquisition

Status: design for review, not authorization to fetch outcomes, run sampling,
restart AWS or create a service. No August returns have been inspected. Final
implementation/runtime/source/seed bindings and parent/reviewer approval precede
acquisition. Existing studies and user edits remain unchanged.

## Question and scope

Does the current fixed-window K400 SV forecast improve proper next-return scores
over the strong rolling250 Student-t5 MLE comparator on a fixed, newly acquired
historical month? The exact E60 EWMA Student-t5 filter is a secondary control.
This separates incremental forecast value from sampler agreement. Independent
posterior spot checks assess approximation error, not market calibration.

August2026 is selected by calendar and bounded exposure audit only. Its entire
1488 consecutive half-hour forecast grid is fixed; no volatility/news/regime
selection or favorable-window trimming. Historical replay remains subject to
bar publication/revision assumptions and is not a prospective live holdout.
No executable quotes, inventory, fees, transaction costs, P&L or deployment claim.

## Acquisition and exact causal indexing

Instrument BTC-PERPETUAL on Deribit; traded30-minute bar close, not mark, midpoint,
index or funding-adjusted total return. Use the established history.deribit.com
public/get_tradingview_chart_data endpoint, resolution="30". Exactly37 UTC-day
requests, July26 through August31 inclusive, each day start through dayend-1ms.
No option trades or other market series are needed. Save request metadata, raw
responses, status, retrieval time and SHA256 before conversion. Acquire once;
no alternative source/date or outcome-based retry. Transient failures preserve
the failed attempt and require a separately recorded recovery decision.

Require exactly48 unique ordered timestamps per day on the30-minute grid, equal
OHLC array lengths, positive finite prices, finite nonnegative volume and coherent
OHLC inequalities. Reject missing, duplicate, revised-overlap or out-of-order bars;
no forward-fill, interpolation, aggregation substitute or gap-dependent shortening.
If a scheduled bar cannot be validated, report acquisition incomplete and do not
run the scored campaign. Any extra returned timestamp is a schema failure.

Let C(t) be the close of the bar opening t-30minutes. Define R(t)=log C(t)-log
C(t-30minutes), available at t under the explicitly assumed zero publication lag.
Forecast origins t run August1 00:00 through August31 23:30UTC. Each origin scores
R(t+30minutes), so target-close timestamps span August1 00:30 through September1
00:00UTC; the last target bar opens August31 23:30 and is within the acquired month.

Use closes from July26 18:30UTC onward (the first relevant bar opens18:00). The
initial250 returns end July26 19:00 through July31 23:30UTC. Initial fitting sees
only those250. At first update observe R(August1 00:00), shift the window and
forecast R(August1 00:30). At each later origin, advance once using only the newly
matured return. In array form, initial y[:250], tick j=1..1488 observes y[249+j],
conditions on y[j:250+j] and scores y[250+j]. Exactly1739 relevant returns and
1740 closes are needed; all1776 acquired bars remain archived/exposed, with unused
early context identified rather than silently discarded from provenance.

Raw data is sealed before an isolated runner receives it. Model fitting functions
accept only causal windows/current observations, while the scoring layer receives
the next label. Reading a full historical file is not a live forecast issuance
claim; enforce the same boundary with deterministic future-perturbation fixtures.

## Frozen methods: no tuning on this month

Candidate: unchanged E61 resident250-window target, rho=.95,nu=5, intercept-only
beta; mu prior N(2log(.005),1), log_sigma N(log(.2),.5), beta N(0,.002), stationary
latent initial distribution. Four chains,1000 initial warmup/200 retained, then
K400 every update with original remap, appended innovation0/mass1 and no pooling,
re-adaptation or scheduled restart. Preserve exact tuning/guard/settings and
runtime from the reviewed resident implementation. One sampler path, all chains;
no seed averaging, discarded hard chains, changed K or repeated failed tick.

Primary comparator: exact E60 rolling250 t5 MLE and deterministic four starts,
solver limits/gradient checks and scale floor1e-8. Each fit uses precisely the
same latest250 returns as the candidate. Copy the validated baseline source into
the study with its original hash and fixtures; do not edit the archived E60 code.
Record every start, eligibility/failure and floor hit. All-start failure remains
an unavailable forecast, not an outcome-selected fallback.

Secondary comparator: exact E60 EWMA t5, lambda=.94, fitted initial250 mu0,s0,
v0=5*s0²/3, v_j=.94*v_(j-1)+.06*(new_return-mu0)², location fixedmu0, forecast
scale=max(1e-8,sqrt(3*v_j/5)). Initial fit uses the same initial250 as the candidate,
then every causal update is retained. Its information memory grows beyond250;
this is intentionally a longer-history control, not a matched-window filter.
The candidate and rolling MLE choose250-return memory although the causal archive
is available to all. Do not reset the EWMA or introduce another arm this cycle.

All three methods use the same realized labels and native log-return units.
Forecast density includes observation noise and parameter/latent mixing where
applicable. Fixed GH64/128 integration at the realized return, primary128,
absolute logpdf/PIT discrepancy tolerances1e-6; no adaptive order or root finding.
Keep the reviewed exact t5 kernel and source identity. Baseline densities/CDFs
are analytic. No interval-score or risk/quote endpoint is added after outcomes.

## Primary endpoint, uncertainty and practical interpretation

Primary endpoint: mean paired log score difference SV-minus-rolling-t5 across all
1488 planned origins (higher is better). Secondary: SV-minus-EWMA on that same
fixed panel. Report both without selecting a winning comparator. Report point
effects in nats/origin and their scale relative to0.01nats/origin as a predeclared
practical reference (roughly1% geometric observed-density improvement), not money,
a qualification threshold or a retrospective change in endpoint.

Use10000 circular moving-block resamples of complete paired origin vectors.
Block lengths24,48,96 half-hour origins (12,24,48hours), with48 the designated
primary descriptive interval and24/96 reported sensitivity. A single frozen RNG
consumes resamples in ascending block-length order. Draw ceil1488/L blockstarts
uniformly from0..1487, wrap modulo1488, concatenate and truncate to1488. Same
indices apply to all methods/comparisons. Report2.5/97.5 percentiles, all31 daily
paired means, cumulative paired scores and fixed leave-one-day-out sensitivity.
These are dependent-series descriptive uncertainty estimates, not1488 iid tests;
circular boundaries/stationarity assumptions and one-month scope remain limits.

Report PIT ten-bin counts, mean, second moment, .05/.95 tails, central90 event
coverage and lag1/lag48 correlation for every arm. Use the same time-block index
sets for PIT mean/second-moment intervals; no iid KS tests or selected calibration
cutoffs. Do not aggregate multiple sampler seeds as new market observations.

Fair cost reporting: measure each method's forecast-production wall time in
serialized phases with fixed thread settings; separate cold imports/JIT/initial
fit, per-update native work, integration, baseline fitting, persistence and total
campaign wall. Include initial cost amortized over1488 separately. Record median,
p95 and maximum cost with validity denominators. No claim of online quote latency
or economic value from these offline component timings; any gain must be weighed
against the actual recorded computational burden, not assumed cheapness alone.

## Sparse reference audit and failures

Eight independent fits at fixed ticks1,213,426,638,851,1063,1276,1488. Exact same
250-return target/window, independent nutpie/Stan engine, four chains,2000warmup/
4000retained, no retries or extensions. Reuse validated E61 target/runtime/settings
and diagnostics: zero retained divergences; rankRhat<=1.01 and bulk/tailESS>=1000
for globals,h_last, per-draw predictive density/PIT; reference delta log-density
MCSE<=.01 and PITMCSE<=.005. Keep both candidate and reference chain-aware
MCSEs/diagnostics, including failures; no candidate deletion when reference fails.
These eight spot checks cannot certify all1488 posteriors or transfer E61's
32-update result into a1488-update claim without this new evidence.

Keep all1488 scheduled origins and4464 planned forecasts in the status ledger,
plus8 reference slots. Candidate failure poisons/stops its continuation; later
candidate origins remain not_started. Baseline phases run independently on valid
acquired data even if candidate sampling fails. Numerical failures retain raw
draws/diagnostics and missing scores; no clipping/replacing/fabricated penalty.
Full-panel paired means/intervals are null if any required score is unavailable;
available-pair summaries must be separate and explicitly denominated. Preserve
every attempted and unattempted origin, never shrink the panel to survivors.

## Seeds, resources and final admission

Proposed new initial/warm bases2026102708000000/2026102709000000; independent
reference bases302711000+1000*i for i0..7, model-data seedbase+1; bootstrap seed
2026102710000000. These are proposals, not yet reserved: audit all public/derived
chain/restart seeds against existing manifests and active worktrees before freeze.
No market outcomes are randomized, resampled to select periods, or regenerated.

Acquisition:300seconds,37requests, minimum.5seconds spacing, max2MiB/response,
16MiB cumulative, no requests beyond the fixed grid. Compute: proposed3600-second
internal/3720-second external envelope,4GiB sampled ownedRSS,1GiB outputs with
archive reserve. Fixed phases: candidate1800s, independent baselines300s,
references1200s (180s/fit but phase cap retained), reporting120s; remaining whole
time is teardown/admission margin. Reference failure/resource-cap expiry does not
trigger a smaller dataset or another fit. Serialize cores0–3, BLAS threads1.

Use the shared reviewed linear resident loop being prepared separately: immutable
per-tick rows/draws and bounded progress, no rewriting/re-hashing all previous
tick files. Retain full4x400x4 compact joint draws at every origin (~76MiB float64),
score arrays and native diagnostics. Exact implementation and literal-fixture
resource admission must be frozen before acquisition. No new study-data timing
pilot; reuse E61/runtime evidence or fixed literal fixtures, without choosing
settings from August outcomes. Parent owns AWS lifecycle/automatic stop guard.

Before execution: reviewer agrees this plan, bounded freshness claim and exact
acquisition contract; final seed/source/runtime/protocol hashes are committed;
causal/gap/denominator/scoring/cost fixtures pass; fixed resource envelope is
accepted. Parent authorizes acquisition and one campaign. No persistent collector
or service is proposed. A genuine future-window live evaluation remains a separate
later protocol if stronger forward-looking evidence is needed.
