# E70: independent-reference precision extension

All 24 new fits completed. The fourfold retained-draw budget approximately halved log-density MCSE (median new/old ratio 0.49588), but 22/24 pass the unchanged joint diagnostics, the same count as the original E66 references. This is exploratory reference evidence, not fresh predictive validation or a revision of E66.

December tick 1 now passes (log-density MCSE 0.008888 versus 0.017919). December tick 851 remains just above the 0.01 precision limit at 0.010294, with zero divergences in the new fit. February tick 1344 has one retained divergence and therefore fails despite improved precision. No gate was relaxed and no failed point was replaced.

All new functionals meet Rhat/ESS thresholds: maximum Rhat 1.000501, minimum bulk ESS 12,905 and tail ESS 17,595. These finite diagnostics are not proof of posterior accuracy. The largest new-minus-old absolute logscore discrepancy is 0.043867 nats at December tick 851, where both references fail their joint gates. Reference uncertainty must not be confused with variation in realized forecast performance.

| Month | Tick | Original pass | Extended pass | Original logpdf MCSE | Extended logpdf MCSE | Extended divergences |
|---|---:|---|---|---:|---:|---:|
| 2025-12 | 1 | False | True | 0.017919 | 0.008888 | 0 |
| 2025-12 | 213 | True | True | 0.000936 | 0.000448 | 0 |
| 2025-12 | 426 | True | True | 0.002188 | 0.001071 | 0 |
| 2025-12 | 638 | True | True | 0.001702 | 0.000859 | 0 |
| 2025-12 | 851 | False | False | 0.021760 | 0.010294 | 0 |
| 2025-12 | 1063 | True | True | 0.002179 | 0.001045 | 0 |
| 2025-12 | 1276 | True | True | 0.001631 | 0.000791 | 0 |
| 2025-12 | 1488 | True | True | 0.001665 | 0.000843 | 0 |
| 2026-01 | 1 | True | True | 0.001437 | 0.000736 | 0 |
| 2026-01 | 213 | True | True | 0.001534 | 0.000744 | 0 |
| 2026-01 | 426 | True | True | 0.001208 | 0.000650 | 0 |
| 2026-01 | 638 | True | True | 0.001599 | 0.000793 | 0 |
| 2026-01 | 851 | True | True | 0.001278 | 0.000613 | 0 |
| 2026-01 | 1063 | True | True | 0.001882 | 0.000909 | 0 |
| 2026-01 | 1276 | True | True | 0.001662 | 0.000806 | 0 |
| 2026-01 | 1488 | True | True | 0.001139 | 0.000598 | 0 |
| 2026-02 | 1 | True | True | 0.001419 | 0.000683 | 0 |
| 2026-02 | 193 | True | True | 0.001815 | 0.000899 | 0 |
| 2026-02 | 385 | True | True | 0.001315 | 0.000676 | 0 |
| 2026-02 | 577 | True | True | 0.000938 | 0.000501 | 0 |
| 2026-02 | 768 | True | True | 0.001536 | 0.000776 | 0 |
| 2026-02 | 960 | True | True | 0.001618 | 0.000806 | 0 |
| 2026-02 | 1152 | True | True | 0.001384 | 0.000701 | 0 |
| 2026-02 | 1344 | True | False | 0.001251 | 0.000622 | 1 |

## Methods, execution and limitations

The same 250-return targets, data, parameterization, warmup and engine options were used at all original 24 points, with fresh reserved seeds and 4x16,000 retained draws rather than 4x4,000. No candidate or historical score was replaced. All original reference JSON hashes were checked against their sealed manifest; report.py independently recomputes the joint gate from recorded diagnostics.

The four-queue campaign completed in 172.28 seconds; outer admission, supervision and teardown took 186.04 seconds. Sampled peak owned RSS was 7.99 GB and final outer outputs were 111.18 MB before packaging. Every job exited zero and all owned processes drained. Four-core affinities were enforced; compilation and diagnostics make actual CPU utilization phase-dependent. These are whole workflow observations, not a matched-performance sampler benchmark.

The first operational attempt stopped before sampling because the monitor received an integer rather than a core-allocation mapping. Its receipt is preserved in evidence/attempt01. After fixing this interface, the adapter forwarding and Linux containment tests passed; attempt02 ran once in a new directory. Scientific settings and seeds were unchanged. Fresh retries of failed scientific points were not performed.

The full evidence archive is target/reference-extension-evidence-20261028.tar.gz; its local checksum and member-verification receipt is evidence/attempt02/ARCHIVE-VERIFIED.json. Compact result comparison and the frozen source manifest are included alongside it. New-source and inherited runtime hashes were checked before launch. Original E66 remains 22/24 and these 24 points do not certify the full posterior path.

Next: distinguish sampler geometry/diagnostic failures from finite Monte Carlo precision and evaluate same-target methods under comparable resource budgets. A reference budget extension is not evidence that oWALNUTS uniquely improves market decisions.
