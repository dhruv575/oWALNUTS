# Bounded historical-access diagnosis

Six queries were declared before execution; all completed. Currency/time probes
for September 25, September 30 and October 2 UTC returned no trades. October 3
returned a trade and has_more=true. The known BTC-30OCT26-84000-P instrument also
returned no September 25 trades but did return an October 3 trade.

The same collector can retrieve recent trades. This weakens a general request
formatting explanation for the failed week-long panel, but does not establish
an exact retention cutoff, absence of historical trading, or historical
completeness. No dates were substituted into the failed panel. No model was fit.

All six request/response pairs are retained with response hashes and retrieval
clocks. A short recent panel could test schema and missingness handling, but
would not replace the intended chronological multi-day market evaluation.
Longer public-history access or prospective capture remains necessary unless an
authorized historical dataset becomes available.
