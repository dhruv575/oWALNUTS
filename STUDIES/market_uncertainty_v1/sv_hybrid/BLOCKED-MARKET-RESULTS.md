# Fixed blocked-path market results

All 96 chains and all 24 analyses completed. Sampling drained normally after
188.85 seconds, with peak monitored RSS 1.14 GB. No sampling retry or budget
extension was used. Completion does not establish posterior fidelity.

Ten of 24 fits passed all 254 coordinate checks. Fourteen remained flagged:
log_sigma was flagged on 13 windows; mu, beta and terminal volatility passed
on all 24. The remaining flags include latent-state diagnostics. Worst compact
bulk ESS was 189.41 for log_sigma and 1662.41 for terminal volatility.
Both previous variants had flags on all 24 windows.

| Predictive summary | All 24 references | 22 passing references |
|---|---:|---:|
| Maximum absolute log-density discrepancy | 0.069844 | 0.018963 |
| Maximum absolute PIT discrepancy | 0.003308 | 0.003308 |
| Median candidate log-density MCSE | 0.003863 | 0.003863 |

The previous interwoven variant had maximum passing-reference log-density
discrepancy 0.056945 and median MCSE 0.021213. These descriptive improvements
do not override the remaining diagnostics. Estimates of Monte Carlo error may
be unreliable in poorly mixed fits. All windows were development-exposed, and
the fixed block size was not tuned within this campaign. No unseen-data,
algorithm-superiority, economic-value or profitability conclusion follows.

Full per-window reports, reference flags, signed differences and chain receipts
are retained in `evidence/blocked-market-result-20261028`. The reporting archive
SHA-256 is `b0c3800c19d7d6cb49d6ddfb6ba11f34b14fda7b20d04b307a8e3ac46598573b`;
the downloaded bytes matched the remote digest. Raw sampling arrays remain on
AWS pending the complete archive transfer and verification.

The next inference question is whether the remaining scale/latent diagnostics
resolve at a separately declared larger budget, with every window retained.
That is a new precision study, not an extension or retry of these completed fits.
