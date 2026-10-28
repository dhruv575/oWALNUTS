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
