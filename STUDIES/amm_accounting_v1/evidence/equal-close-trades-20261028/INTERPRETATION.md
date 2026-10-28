# Fixed historical trade probe

All nine requests returned HTTP 200. The original validator rejected seven
nonempty responses because trade sequences were not strictly descending.
Read-only reanalysis found unique sequences and descending timestamps, with
sequence-order variation within equal timestamps. The original failures remain
in REPORT.json; no response was replaced or refetched.

For all seven nonempty responses, the last price after ordering by timestamp
and sequence matches the historical candle close. Five report has_more=false;
two return 1,000 trades with has_more=true and remain incomplete intervals.
Both zero-volume bars returned no trades and has_more=false. This supports an
empty-interval interpretation for those two cases, conditional on the historical
service's coverage. It does not independently prove archival completeness or
establish the provider's carry-forward implementation.

The other seven zero returns coincide with actual returned transaction prices,
so a missing-bar correction cannot resolve every tie. The evidence still does
not prove a latent efficient-price rounding model. Pagination, volume-unit
reconciliation and boundary controls remain before claiming a full candle
reconstruction. These selected development anomalies are not confirmation data.

## Volume and OHLC reconciliation

The five nonempty responses with has_more=false all match candle open, close
and low. Summing inverse-contract quote amounts divided by transaction prices
matches base-currency candle volume within 3.75e-9, below the fixed 1e-8 check.
All observed transaction prices in these five responses lie on a half-dollar
grid; this establishes neither the minimum historical tick nor a rounding law.

Four highs also match. At bar index 2502, the full trade maximum is 95587.0
while the candle high is 95576.5. The sole trade above the candle high has
trade_id 408665073, combo_trade_id 408665071 and combo_id BTC-FS-27MAR26_PERP.
Excluding combo trades gives the reported high. The response contains three
combo trades, and volume agreement uses all trades. This is evidence consistent
with different trade inclusion rules for price extrema and volume, not proof
of a universal provider rule. Preserve the discrepancy; do not silently filter
combo trades from every field or alter the sealed candle data.
