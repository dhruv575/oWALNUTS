# Market observation semantics audit, 2026-10-28

Primary documentation inspected:

- https://docs.deribit.com/api-reference/market-data/public-get_tradingview_chart_data
- https://docs.deribit.com/api-reference/market-data/public-get_instrument
- https://docs.deribit.com/specifications/deribit_openapi.json

The chart endpoint documents OHLC prices and per-candle volume, a millisecond
time axis, and supported minute resolutions including 30. Its schema names the
parameter `resolution`; the introductory prose instead says `chart_resolution`.
The acquisition's use of `resolution=30` agrees with the schema and examples.
This documentation inconsistency is not evidence of corrupted acquired bars.

The inspected chart page does not specify a no-trade carry-forward rule, a
historical tick-size schedule, or a latent continuous-price rounding mechanism.
The instrument endpoint exposes instrument metadata; present metadata alone
cannot establish the rule applied to December 2025 through February 2026.
Documentation absence is not proof that carry-forward did or did not happen.

The sealed data establish nine equal adjacent closes, seven with positive
current volume and two with zero volume. The zero-volume examples are compatible
with synthetic flat candles; that interpretation remains unverified. Positive
volume rules out an empty interval as the explanation for those seven cases,
but does not identify a nearest-grid latent measurement mechanism.

## Consequence for the candidate model

Do not describe tick-constrained transaction prices as known rounded observations
of a continuous efficient price. Price formation and reporting are different
mechanisms. A mathematically proper price-cell model can still be misspecified.
Its synthetic checks are necessary implementation evidence, not validation of
that market assumption. Likewise, omitting zero-volume bars assumes an ignorable
observation process and changes the inference problem.

The next empirical check should query a fixed bounded set of historical trades
around all nine already-identified equal-close intervals, preserving no-data and
pagination failures. Reconstruct last-trade closes where completeness is verified;
check timestamp boundaries, price lattice and volume units. Do not choose only
easy successful intervals. This would test chart construction, not establish a
latent rounding mechanism or provide untouched predictive confirmation.

An alternative is an explicitly declared coarsened forecast target: assign
observed prices to a fixed partition and score probabilities of those bins.
This avoids claiming that the exchange itself rounds an efficient price, but
changes the estimand and information set. It needs a justified economic
resolution, sensitivity analysis, consistent baseline scoring, and a defined
missing-bar policy. It cannot silently replace the original accuracy or
profitability objective merely because its posterior is easier to normalize.
