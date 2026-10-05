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
