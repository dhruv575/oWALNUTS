# Same-target reference cost results

All 24 NUTS fits completed, passed every declared coordinate diagnostic and had
zero divergences. All predictive reports are available. Each fit used four
chains, 4,000 warmup and 8,000 retained draws, the same target and windows as the
blocked precision panel. New external seeds and all windows were retained.

| Observed campaign metric | Blocked specialist | NUTS |
|---|---:|---:|
| Fits passing all declared diagnostics | 24/24 | 24/24 |
| End-to-end campaign seconds | 735.90 | 196.46 |
| Median log-density MCSE | 0.001939 | 0.001113 |
| Maximum absolute density discrepancy, 22 passing references | 0.019060 | 0.003133 |
| Maximum absolute PIT discrepancy, 22 passing references | 0.001248 | 0.000624 |

On this fixed development panel, the reference implementation took about 27%
of the specialist's campaign time and had better aggregate predictive-precision
metrics. This is evidence against claiming a computational advantage for this
specialist on this workload. It is not a universal ranking of inference methods,
and the specialist is not WALNUTS. No uniquely favorable WALNUTS use case has
been established by these controls.

NUTS timings include separate per-fit compilation: median compilation 14.05
seconds and sampling 7.31 seconds. These are medians over different concurrent
fits and must not be added or divided to reconstruct campaign time. Compiled
model reuse could improve the baseline further; it was not measured here.
The two implementations have different internals, initializations and parallel
schedules. Equal retained counts do not mean equal effective precision.

The all-24-reference maximum density discrepancy was 0.011413; the two previously
flagged extended references remain flagged and are not reclassified using these
results. Diagnostic passing is not exact posterior certification. The original
long reference, these independent fits and specialist results remain separately
identified. Predictive performance on untouched data, economic value and
profitability remain unproven.

The complete reporting archive matched remote SHA-256
`bbe11ab1658ff304632e2052e2a36e96b1fc40aec49d595981c0fb7585dfae81`.
All reports are retained in `evidence/market-reference-result-20261028`.
The full 4,431,480,889-byte archive was streamed off AWS and verified against
the sealed 587-file manifest, including all 24 full traces and 24 draw files.
Its SHA-256 is `c15b7ef141ca7345d3d70e96ff571a4c95f5db9625d0faf5a5e0384ba122cf35`.
S3 upload is underway; no S3 restore verification is claimed yet. Original AWS
evidence remains intact.
