# Completion of two truncated historical intervals

All twelve fixed five-minute requests returned has_more=false. Their disjoint
unions contain 1,058 and 2,214 unique trades respectively. Each original
1,000-trade response is an exact record-level subset of its partition union.
Both reconstructed OHLC sets match the sealed candle values. Quote-amount /
transaction-price volume sums match the reported base volume within 4.48e-9.

Together with the earlier five complete nonempty responses, all seven
positive-volume equal-close intervals now have service-reported complete
trade lists and matching closes and volumes. The earlier combo-trade high
discrepancy remains; these two intervals match all four OHLC fields.

Coverage still depends on the same historical service. This is not independent
archival verification, proof of a latent rounding mechanism, or confirmatory
predictive data. The two zero-volume intervals remain separately recorded as
empty responses. No observations were dropped, jittered or modified.
