# E65: Retrospective predictive-return risk limits

SV's P5/P95 limits have lower mean pinball loss in all twelve historical
comparisons. The primary 48-origin block intervals support an advantage over
rolling Student-t5 in five of six comparisons; May short risk remains unresolved.
None of the six primary comparisons against EWMA Student-t5 excludes zero.
These results support useful tail-risk information relative to rolling t5,
while leaving the incremental advantage over the stronger EWMA control uncertain.

This is exploratory reuse of the already inspected E64 April/May/June 2026
panels, not a fresh holdout or a trading-profit result. No market data, posterior
draws, model settings, fitted baseline parameters or tolerances were changed.

## Completion and methods

All 4,368 origins, 13,104 arm-origin slots and both tail scores are available.
All 24 fixed reference comparisons have both candidate-own and reference-own
precision available. All 27 jobs exited zero and drained; there were no missing
scores, numerical failures, precision failures, retries or replacement origins.
The parent independently verified all 9,256 archive file hashes. The separate
post-seal audit reproduced all twelve paired means and exceedance differences
from the complete ledgers without rerunning quantiles, scores or bootstrap.

Each origin uses all four chains of 400 stored candidate draws; references use
four chains of 4,000 draws. Equal weights, rho=0.95 and Student-t5 innovations
are unchanged. GH64/GH128 and the existing exact t5 CDF evaluate the full return
mixture. Saved rolling and EWMA location/scale parameters supply analytic t5
quantiles without another fit. P50 was neither computed nor scored.

Long loss is minus log return, with 95% limit -q05. Short loss is log return,
with 95% limit q95. The fixed pinball loss gives underprediction nineteen times
the marginal penalty of equal-sized overprediction. Limits are not clipped at
zero; strict exceedances exclude equality.

## All twelve paired comparisons

Positive advantage is baseline pinball loss minus SV pinball loss. Values below
are multiplied by 1,000,000 for readability; they retain log-return loss units.
Intervals are the prespecified 95% paired circular-bootstrap intervals from
10,000 resamples with 48-origin blocks.

| Month | Risk side | Baseline | Mean advantage x 1e6 | 48-origin interval x 1e6 |
|---|---|---|---:|---:|
| 2026-04 | long | rolling_t5 | 20.795 | [4.322, 39.108] |
| 2026-04 | short | rolling_t5 | 31.331 | [9.740, 60.328] |
| 2026-04 | long | ewma_t5 | 4.958 | [-4.110, 14.491] |
| 2026-04 | short | ewma_t5 | 8.693 | [-1.615, 21.482] |
| 2026-05 | long | rolling_t5 | 13.293 | [3.158, 24.208] |
| 2026-05 | short | rolling_t5 | 7.529 | [-3.768, 20.348] |
| 2026-05 | long | ewma_t5 | 6.847 | [-0.837, 14.936] |
| 2026-05 | short | ewma_t5 | 4.174 | [-3.372, 11.997] |
| 2026-06 | long | rolling_t5 | 48.670 | [19.997, 84.181] |
| 2026-06 | short | rolling_t5 | 53.771 | [20.568, 93.463] |
| 2026-06 | long | ewma_t5 | 9.569 | [-2.173, 22.570] |
| 2026-06 | short | ewma_t5 | 11.692 | [-1.950, 25.922] |

All 24/48/96-origin block intervals remain in the frozen monthly summaries.
The five rolling comparisons identified above exclude zero at all three block
lengths; May short risk does not. May long and June short versus EWMA have
slightly positive lower bounds only at 96 origins; these sensitivity results
do not replace the unresolved primary 48-origin comparisons. Daily, cumulative
and leave-one-day-out summaries are retained without selecting a winning period.

The aggregate descriptive advantages are 27.429 and 30.621 x 1e-6 against rolling
for long and short risk, and 7.122 and 8.142 x 1e-6 against EWMA. There is no pooled
interval. Adjacent months, shared initialization history and 250-return windows
remain dependent; the block lengths do not guarantee protection against longer
market dependence. No familywise or independent-regime success claim is made.

## Limits, loss and exceedances

Long / short entries are reported together. Pinball means are multiplied by
1,000,000; mean limits and interval widths are unscaled log returns. April and
June have 1,440 origins each, and May has 1,488.

| Month | Arm | Mean pinball x 1e6, long / short | Exceedances, long / short | Mean limit, long / short | Mean q95-q05 |
|---|---|---:|---|---:|---:|
| 2026-04 | candidate | 325.688 / 326.967 | 53 (3.68%) / 57 (3.96%) | 0.004443 / 0.004498 | 0.008941 |
| 2026-04 | rolling_t5 | 346.484 / 358.298 | 77 (5.35%) / 86 (5.97%) | 0.004032 / 0.004190 | 0.008222 |
| 2026-04 | ewma_t5 | 330.647 / 335.660 | 77 (5.35%) / 66 (4.58%) | 0.004135 / 0.004378 | 0.008513 |
| 2026-05 | candidate | 253.904 / 256.917 | 69 (4.64%) / 54 (3.63%) | 0.003632 / 0.003652 | 0.007284 |
| 2026-05 | rolling_t5 | 267.198 / 264.446 | 88 (5.91%) / 68 (4.57%) | 0.003332 / 0.003318 | 0.006650 |
| 2026-05 | ewma_t5 | 260.751 / 261.091 | 85 (5.71%) / 69 (4.64%) | 0.003373 / 0.003385 | 0.006758 |
| 2026-06 | candidate | 455.575 / 416.470 | 75 (5.21%) / 62 (4.31%) | 0.006001 / 0.005868 | 0.011869 |
| 2026-06 | rolling_t5 | 504.245 / 470.241 | 104 (7.22%) / 95 (6.60%) | 0.005427 / 0.005160 | 0.010587 |
| 2026-06 | ewma_t5 | 465.144 / 428.162 | 83 (5.76%) / 79 (5.49%) | 0.005748 / 0.005657 | 0.011406 |

SV limits are wider on average than both controls. Its long exceedance rates
are 3.68%, 4.64% and 5.21%; short rates are 3.96%, 3.63% and 4.31%. Lower
exceedance rates are not automatically better calibration: the nominal target
is 5%, and broader limits can cover more while constraining inventory more.
Pinball loss addresses this tradeoff. Frozen summaries retain signed deviations
from 5%, exceedance intervals and all paired exceedance-difference intervals.

## Numerical and reference checks

All candidate and reference tail roots passed the original gates. Across these
outputs the largest own-root CDF residual and cross-CDF discrepancy were both
1.393e-11; the largest normalized GH64/GH128 endpoint difference was 1.713e-15.
These arithmetic checks do not establish posterior sampling accuracy.

At the 24 fixed reference origins, candidate-minus-reference q05 differences
range from -0.000092109 to 0.000110729 log return; q95 differences range from
-0.000119622 to 0.000104268. Maximum candidate-own quantile delta MCSE is
0.000102247 for q05 and 0.000101945 for q95; corresponding reference maxima are
0.000036917 and 0.000036914. The calculation preserves chain/draw axes and divides
chain-aware mean-CDF MCSE by predictive density at each distribution's own root.
All per-tail records remain in the packet. These are diagnostic uncertainty
estimates, not new pass gates, and eight reference spots per month cannot certify
the entire path. The original reference diagnostic pass records are retained.

## Cost and practical limits

The complete twelve-shard campaign took 241.757 seconds, with sampled peak owned
RSS 6,083,375,104 bytes (5.67 GiB), and 56,927,373 final output bytes. The earlier
twelve-way literal readiness completed separately; its records are preserved.
Candidate median per-origin postprocessing was 0.5685 / 0.5690 / 0.5688 seconds
in April/May/June. Median saved-fit baseline postprocessing was about 0.00090 to
0.00094 seconds for rolling and 0.00076 to 0.00078 seconds for EWMA. These figures
include each arm's recorded input-read/arithmetic work on a shared host; labels
are loaded separately. They are quantile-only postprocessing of cached draws,
not combined live inference/update/quote latency. No archived inference time
has been added and represented as a measured end-to-end refresh.

This supports a bounded risk-limit calculation, with uncertain incremental
value over EWMA and substantially greater arithmetic cost. It does not test
fills, fees, adverse selection, inventory-control actions or P&L. Log-return
limits are not dollar-loss estimates. For the Student-t log-return
model, E[exp(R)] is infinite; finite expected-price or unbounded-short dollar-loss
claims are therefore unavailable. Bounded utility and bounded positive long
downside are different quantities and need not share that divergence. See the
[decision-contract moment analysis](../amm_decision_contract_v1/README.md).
Realized finite-label pinball and the fixed finite stored-draw mixture's expected
absolute log return are finite; no unproved integrability assertion is made
about the unrestricted posterior hierarchy.

## Evidence and provenance

- [Frozen plan](PLAN-DRAFT.md) and [settings](COMPUTE-DRAFT.json).
- [Arithmetic audit](evidence-20261027/POST-SEAL-ARITHMETIC-AUDIT.json).
- [April summary](evidence-20261027/campaign01/batch/reports/2026-04/summary.json),
  [May summary](evidence-20261027/campaign01/batch/reports/2026-05/summary.json),
  [June summary](evidence-20261027/campaign01/batch/reports/2026-06/summary.json).
- [Aggregate](evidence-20261027/campaign01/batch/aggregate.json),
  [terminal supervision](evidence-20261027/campaign01/BATCH-SUPERVISION.json) and
  [provenance](evidence-20261027/PROVENANCE.json).

Authorized production manifest SHA256:
`aeb6e3c8fd676d057142945df0b2e2315c10433dddfd91a486921124f6a9d136`.
Archive SHA256:
`94434e4fe6abb30e1f66c699fbee9c250a3888bbe39b9dd31d11fdf09cd0e5d6`
(8,077,968 bytes; 9,256 verified files).
The full archive is `C:/dev/owalnuts/target/return-tail-20261027-evidence.tar.gz`;
the verified expansion is
`C:/dev/owalnuts/target/return-tail-verified-20261027/return-tail-20261027`.
Full per-origin ledgers and numerical records remain there, rather than being
duplicated into Git. The original E64 draw archive remains separately pinned.
AWS remains available for the next reviewed research queue under the user's
standing preference; this study does not shut down the host.
