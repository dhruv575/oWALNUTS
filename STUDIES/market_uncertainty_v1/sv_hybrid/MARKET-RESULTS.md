# Fixed market-window results

All 192 chains completed and drained within the declared limits. All 48
method/window reports and actual-label predictive calculations are available.
However, **all 48 fits have diagnostic flags** at the declared Rhat/ESS checks.
Operational completion is not posterior fidelity.

| Compact coordinate | Original flagged fits / 24 | Interwoven flagged fits / 24 |
|---|---:|---:|
| mu | 24 | 1 |
| log_sigma | 24 | 24 |
| beta | 4 | 6 |
| h_last | 24 | 24 |

Interweaving materially improved mu's diagnostics, but did not resolve scale
or terminal-volatility mixing. The worst bulk ESS for log_sigma was 19.74
original and 16.55 interwoven; maximum log_sigma Rhat was 1.14065 and 1.16897.
This is evidence against treating a good mu result as whole-posterior readiness.

| Method | Maximum absolute log-density discrepancy, all 24 refs | Same, 22 passing refs | Median candidate log-density MCSE, all refs | Maximum absolute PIT discrepancy, passing refs |
|---|---:|---:|---:|---:|
| Original | .296705 | .296705 | .021149 | .014890 |
| Interwoven | .130662 | .056945 | .021213 | .016869 |

The original method's worst passing-reference log-density discrepancy occurred
at December tick 1; the interwoven method's at December tick 638. Every window,
reference flag, posterior quantile, MCSE and signed difference is retained in
`evidence/market-result-20261028/`. The two flagged references are not silently
removed; both full and passing-reference summaries remain visible.

MCSE estimates from poorly mixing chains can be unreliable. These values are
descriptive and do not rescue the flagged fits. Literal-fixture corroboration
did not generalize to sufficient mixing at this market sampling budget.
There is no algorithm-superiority, predictive-control, whole-stream calibration,
decision-value or profitability conclusion. Cold-fit timing must not be compared
directly with E72's warm streaming-path timings.

The campaign took 323.72 seconds end-to-end on the existing 16-core instance.
Source, input and seed schedules were frozen; no chain was retried or excluded.
The downloaded reporting archive matches its remote SHA-256. Full sampling
evidence remains in the original and hash-verified sealed AWS directories;
its versioned S3 archive has now passed exact-version restore, whole-archive
SHA-256 and all 1,183 original-member hash checks. The redundant remote compressed
archive and redundant sealed tree were reclaimed after verification against
the preserved original tree and restored S3 archive. The original sampling tree
and source dependencies remain available.
