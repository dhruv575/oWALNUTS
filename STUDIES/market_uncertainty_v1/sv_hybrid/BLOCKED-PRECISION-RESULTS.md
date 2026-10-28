# Fourfold blocked precision results

All 96 fresh chains completed without retry and all 24 fits passed all 254
declared coordinate diagnostics. The short-budget blocked study passed 10/24;
the original and interwoven studies passed 0/24 each. Thresholds and all windows
were retained. These diagnostics support readiness on this exposed panel, not
proof of exact convergence or out-of-sample superiority.

The fixed 4,000-warmup / 8,000-retained campaign took 735.90 seconds, versus
188.85 seconds for 1,000 / 2,000: approximately 3.90 times the end-to-end cost.
Peak monitored RSS was 1.42 GB; final output was 1.52 GB. All process groups
drained. Worst compact bulk ESS was 1066.80 for log_sigma and 5613.84 for h_last.

All 24 paired predictive MCSE estimates decreased for both log density and PIT.
Median log-density MCSE was 0.001939, versus 0.003863 at the short budget.
Absolute reference discrepancy improved on 17/24 density and 18/24 PIT pairs,
not universally. The maximum density discrepancy on the 22 passing references
was 0.019060, slightly above the short study's 0.018963; maximum PIT discrepancy
was 0.001248. Full and passing-reference summaries remain separate. The two
previous reference failures are not repaired by the candidate passing.

Both warmup and retention changed, with fresh external seeds; this study cannot
identify which change caused individual improvements. Short-run MCSE values
from flagged chains require caution. No relative-speed claim against another
algorithm, decision-value claim or profitability claim follows.

All reports and comparison rows are in `evidence/blocked-precision-result-20261028`.
The reporting archive matched remote SHA-256
`5a177b572e502d4fc0d68d04ae7fa8bffbe2f4baffc84b3992eef86ac720d337`.
The full raw archive was verified locally and after restoring exact S3 version
`8j46Ll2FHZ2PvJhO6QSdcjJzmoUUeQi_`. Checks covered all 96 chain-array hashes,
24 inputs and 31 frozen sources, as well as the whole-archive SHA-256. Receipts
are preserved alongside the reports; raw AWS copies remain available.

Next: establish a fair same-target computational comparison and then a declared
untouched predictive evaluation. Preserve fixed economic-identification and
integrability requirements; better posterior sampling alone cannot satisfy them.
