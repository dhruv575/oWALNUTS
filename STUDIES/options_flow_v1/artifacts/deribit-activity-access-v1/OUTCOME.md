# Activity-selected access attempt: insufficient universe

The frozen September 11-18, 2026 BTC-options acquisition stopped with collector
exit 2 after 21.08 seconds, 31 requests and 6,175,791 raw response bytes. Its
first-day discovery completed; the full seven-day panel did not. Containment
and cleanup succeeded. No fitting is permitted on this incomplete acquisition.

Independent review found 16 complete discovery leaf windows spanning the first
day and 9,788 deduplicated trades. Of 536 instruments represented by eligible
trades, none met all frozen activity thresholds. Every instrument missed the
required 36 fresh-anchor bins out of 47; the maximum was 32. There were also
535 instruments below 24 active-feature bins and 517 below 96 eligible trades.
These rejection counts overlap. No metadata requests, final contract selection,
or subsequent instrument-history collection occurred.

The protocol was frozen and committed before collection. It requires activity
appropriate to repeated 30-minute decisions, rather than ranking by volume
alone. This is a negative feasibility result for this fixed week and workload,
not a finding about every Deribit period or every options-market use case.
Thresholds, dates and budgets were not changed after seeing the result.

All requests/responses, ranking and rejection evidence, source snapshots, terminal
summary, and independent audit are retained here. The sibling hardware, exit and
process-log artifacts preserve the entire attempt. Discovery completeness is
relative to the checked API responses and pagination rules; it does not establish
historical exchange-feed completeness or actual receipt times.

The practical data path remains unresolved. A denser source, quote-based target,
or a different decision frequency would require an explicitly justified new
workflow and protocol. Meanwhile, computational accuracy and repeated-fit testing
can continue on the existing verified fixtures.
