# Real options-data access investigation

Exploratory access check, 2026-10-03. No model has been fitted to these records.

## Verified access and remaining scope

A bounded, unauthenticated request to Deribit's production public API returned
two BTC option trades with instrument, time, price, size and direction. The exact
response, retrieval time, URL and SHA-256 are archived in
`artifacts/market-data-access-probe-v1/`. This verifies a public access path only;
it does not establish a complete historical dataset or usable forecasts.

The [official trade endpoint documentation](https://docs.deribit.com/api-reference/market-data/public-get_last_trades_by_instrument_and_time)
defines direction as the taker's side and distinguishes instrument-local trade
sequence numbers from currency-level trade IDs. It also describes block/combo
identifiers, historical records with missing contract counts, and base-coin
amounts for options. Those distinctions must survive ingestion.

For U.S. listed options, [Cboe Option Trades](https://datashop.cboe.com/option-trades)
describes OPRA trade prints with execution price/size, exchange and prevailing
NBBO, and provides a downloadable sample. The sample link resolved to a ZIP
response, which the web reader could not parse; its content has not been
inspected. This investigation has not obtained a licensed historical panel.

Crypto options and U.S. equity options remain separate market scopes. A Deribit
experiment would be an explicitly named first real-data component, not evidence
of U.S. equity-market usefulness. No purchase or external account action occurred.

## Proposed next acquisition and evaluation contract

Before collecting a training/evaluation panel, freeze a calendar range,
instrument-universe rule, expiration exclusions, forecast horizon and target.
Select instruments using information available at that time, including expired
instruments; do not pick contracts after inspecting successful fits or outcomes.

For a trade-flow experiment, archive raw responses and request parameters, then
verify pagination, deduplication, sequence coverage and timestamp boundaries.
Time-only pagination must not silently drop trades sharing a timestamp. Preserve
block/combo flags and specify exclusion or aggregation rules before fitting.
Trade direction alone does not identify investor intent, opening versus closing
positions, or a complete multi-leg strategy.

Trade timestamps do not establish historical receipt or publication latency.
If a historical source lacks availability timestamps, declare that limitation
and freeze an explicit lag assumption; do not invent observed availability.
Define a feature-availability clock independently of the outcome clock. Signed
executed quantity in a completed window can be a candidate flow feature; observed
future returns, marks or implied volatilities cannot enter that window's inputs.
Price currency, contract multiplier, missing trades and inactive contracts require
explicit handling. A no-trade window must not automatically become a zero return.

Freeze chronological development and held-out periods and fit scaling using
training observations only. Compare the same flow model with flow coefficients
disabled, plus a declared simple forecast baseline. Measure coverage, interval
width and proper predictive score together with computation failures and total
workflow cost. Posterior parameter intervals and future-observation intervals
answer different questions; evaluate and label them separately.

This access investigation removes one uncertainty about obtaining a public
options feed. Historical completeness, suitable market scope, interval accuracy
and economic usefulness remain unestablished.
