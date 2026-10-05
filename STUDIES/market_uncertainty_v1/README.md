# Market uncertainty workflow exploration

This study tests whether pooled option flow helps forecast the distribution of
future BTC perpetual returns, and whether oWALNUTS can make that inference useful
and affordable. It is exploratory. It does not establish calibrated market
intervals, causal price impact, profitable trading, or U.S. options performance.

The earlier per-contract trade target was too sparse. A chronological diagnostic
on its archived data covered 49 of 64 scoreable returns with nominal 90% intervals,
for both zero-return and flow-ridge predictors. Missing outcomes remained in the
764-cell scheduled denominator. A separate discovery-day diagnostic found 9,457
eligible option prints across 536 contracts and pooled index anchors at all 46
examined origins. Those trade-time index observations are not a regular price feed.
Original exploratory evidence remains in `target/market-validation-route-v1/`
and `target/market-model-route-v1/`; these are not committed study artifacts yet.

## Runnable data path

`receipt_collector/collector.py` records all BTC option trade notifications plus
independent BTC-PERPETUAL ticker notifications. It preserves receipt clocks,
instrument metadata, subscription acknowledgments, reconnect gaps and raw messages.
Its README gives the bounded command. Ten collector tests pass in the repository
location. The original two-minute live smoke recorded 120 ticker and 13 trade
notifications with no detected gaps; a notification may contain multiple trades.
This is access evidence, not a training sample or independent price-change count.

`receipt_features/features.py` creates 15-minute received-flow sums and delayed
30-minute midpoint-return labels. Missing connection coverage produces unknown
flow, not zero. Midpoints are quoted prices, not executable fills. A two-hour
collection can test horizon maturation but cannot establish calibration across
market regimes. Longer chronological development, calibration and test periods
are still required before a persuasive market utility claim.

The actual collector-to-feature smoke is preserved in
`artifacts/receipt-pipeline-smoke-v1.zip` with member hashes. Its separately
labelled two-second configuration produced 59 known received-flow windows and
58 matured labels; the default configuration produced zero origins. Receipt
tampering was rejected without an output. Five feature tests pass in the
repository location. These are pipeline checks, not forecast accuracy tests.

## Inference route

The separate bounded prototype in `target/market-compute-route-v1/` compares exact
blocked scale-mixture/latent-path updates with generic samplers on the same robust
state-space model. This is a synthetic persistent-return-mean model, not yet the
full stochastic-volatility market model. Include oWALNUTS, a strong NumPyro
parameterization and the specialized algorithm. Compare accuracy and endpoint
precision before interpreting timings; preserve failures and total workflow cost.

The completed single-fixture pilot is now archived at
`artifacts/structured-inference-pilot-v1/`. Its 49 checksummed files preserve
failed and corrected runs, exact executed sources and runtime identities.
Large raw arrays remain external and hash-pinned. The portable exact blocked
prototype is in `blocked_prototype/`; three dense-Gaussian oracle and missing-data
checks passed in the repository location.

At the tested fixed lengths, contained worker times were approximately 25.73s
for oWALNUTS, 47.13s for centered NumPyro, 56.71s for noncentered NumPyro, and
21.50s for specialized Gibbs with 16,000 retained draws per chain. These runs
passed their health and endpoint-precision checks. The initial 4,000-draw Gibbs
run failed endpoint precision. The first oWALNUTS adapter preflight failed on a
constant normalization offset and was corrected without relaxing the tolerance.
These are not optimized time-to-precision ratios: earlier stopping tiers were
not tested, and source correction/development costs are separately retained.
No general sampler advantage or market coverage follows from this pilot.

The subsequent demanding T1000/G4 continuation experiment is preserved at
`artifacts/parallel-continuation-latency-v1/`. Two one-/four-thread pairs reached
the same passing tiers (4,000 and 2,000 draws) with byte-identical retained raw
artifacts, diagnostics, adaptation metadata and work counts. Whole-process
latency ratios were 1.924 and 1.939 in favor of four threads. This demonstrates
a continuation latency improvement on this model, using more concurrent CPU
resources. It is a two-pair development result; an equally parallel NumPyro
comparison is separate and market calibration remains unestablished.

Posterior coefficient credible intervals, future-return predictive intervals and
repeated-sample confidence intervals answer different questions. The first market
deliverable is a predictive distribution issued using only information received by
its origin. Compare price-only and flow-augmented models on identical scheduled
origins; measure availability, coverage, width and proper interval score together.
Sampler convergence cannot by itself establish market calibration.

## Exact forecast baseline

`forecast_baseline/forecast.py` consumes 30-minute feature rows and emits a
price-history-only or flow-augmented conjugate Bayesian regression prediction.
Only matured past labels enter fitting and scaling. The Gaussian observation
model has an exact Student-t posterior predictive distribution; this is not
a heavy-tailed Student-t observation likelihood or a stochastic-volatility model.
Observation predictive intervals and coefficient credible intervals are separate.
At least 20 eligible labels are required, so the two-hour capture is expected to
return insufficient-history statuses rather than a trained market forecast.

Eleven tests plus 15 parameterized subtests passed. An actual synthetic CLI run
produced all 60 intended outputs: 18 forecasts and 42 explicit no-forecast
statuses. Its inputs, outputs and executed source are preserved in
`artifacts/forecast-synthetic-cli-v1.zip` with member hashes. This baseline is
an analytic reference and pipeline component, not evidence of market calibration
or a replacement for the demanding inference objective.

## New routes under development

The equally parallel reference experiment is preserved in
`artifacts/parallel-reference-latency-v1/`. Both reference fits passed at 2,000
draws, taking 31.08s and 31.72s versus oWALNUTS at 56.09s and 35.15s. A narrow
precision miss forced the first public fit to 4,000 draws; compilation and
adaptation also matter. The comparison retains its two reused development seeds,
complete costs, and limits. Finer continuation increments are a separate pilot,
not a changed interpretation of these results.

The completed finer-tier mechanism pilot is in
`artifacts/finer-continuation-pilot-v1/`. Keeping the same precision gates,
oWALNUTS passed at 2,500/2,000 draws in 45.88s/35.31s; the parallel reference
passed at 2,000/2,000 in 33.49s/33.59s. All eight shared 1k/2k raw prefixes
matched the previous runs byte-for-byte. The selected first public case improved
from 56.09s, but the reference remained faster. The original launcher import
failure and its costs are retained: corrected run 148.73s, failed attempt 80.03s.
These are reused development seeds and a changed 4k resource cap, not a fresh
speed or reliability qualification.

`sv_prototype/` implements a normalized heavy-tailed return model where option
flow can affect expected return and latent volatility separately. Its analytical
gradient is checked against finite differences of a centered-density oracle.
This is a research target, not a fitted market model. The four intended ablations
are neither, mean-only, scale-only, and both flow effects. Numeric market priors,
sampler integration and prospective predictive checks remain open.

`delayed_scoring/` scores immutable issuance records after collector termination.
It binds inputs, reconciles late gaps, retains missing/nonissuance outcomes, and
reports predictive interval coverage, width and proper score without refitting.
The exact baseline remains the first live pipeline component; the demanding
stochastic-volatility target will need its own validated forecast adapter.

[The model design](SV_MODEL_DESIGN.md) explains the proposed flow-in-volatility
hypothesis, the four ablations, and the exact conditional blocks available for a
future hybrid sampler. Gaussian FFBS applies to a conditional linear state block;
it does not directly solve nonlinear log volatility. A hybrid would require an
explicit conditional-target cache reset and frozen retained-sampling tuning.

`online_issuance/` now provides a one-shot issuer and a bounded scheduler; 15
tests passed. A frozen standalone copy was launched against the 48-hour capture
under `target/market-online-issuance-launch-v1`, with actual records under
`target/market-online-issuance-run-v1`. Its 95 planned origins require the target
horizon to end by the planned capture end. The first, already missed origin is
explicitly recorded; future origins are never backdated. An issuance attempt
without 20 matured eligible labels records no forecast. The scheduler has a
12GiB disk admission floor and stops further attempts on source drift or capture
termination. Inspect its actual process/ledger for current status; launch is
not evidence that an interval was issued.

An immutable prefix from the separate two-hour capture exercised the default
15-minute flow window and 30-minute target: two origins had known flow (73 and
60 trades), and the first had a matured midpoint return while the second did not.
This is a causal historical-prefix pipeline check, not a prospective forecast or
calibration result; final collector gaps still require reconciliation.
