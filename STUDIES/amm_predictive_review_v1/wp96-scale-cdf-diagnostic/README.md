# WP96: how much error comes from simulated predictive innovation?

**Post-hoc diagnostic, not a new qualification or a changed WP96 verdict.** The
selection/rules were committed in `c8182264` before these outputs. This uses every
original nonzero scored tick and every warm arm; no new sampling was performed.

All **160 reference origins and 1,280 warm rows** were processed in 24.63 seconds
of local analysis time. The original per-row errors, accuracy flags and stuck-chain
flags reproduced the archived report: maximum error discrepancy 4.44e-16, all
accuracy/stuck flags identical. Every input hash was unchanged after analysis.
Analytic fixtures passed and all warm CDF inversion residuals were <=2.42e-12.

## Result

Analytically integrating the future volatility innovation is a useful precision
lever, but **does not rescue any policy across both streams and both halves**.

The three comparisons deliberately separate the reference change from the warm
estimator change. Accurate means P50 error <=2%, P95 error <=5%, and no original
stuck-chain flag; latency was not part of WP96's accuracy rule.

| Comparison | Accurate rows / 1,280 |
|---|---:|
| Original noisy warm quantiles vs original noisy reference | 1,046 (81.72%) |
| Original noisy warm quantiles vs analytic-CDF reference | 1,053 (82.27%) |
| Analytic-CDF warm quantiles vs analytic-CDF reference | 1,198 (93.59%) |

Thus most of the observed improvement comes from changing the warm estimator,
not moving the finite reference. This is a realized paired comparison, not an
independent-replication significance test. The original innovation streams were
shared across arms/reference, successive ticks are dependent, and the two data
streams share innovations and their pre-shift history.

All groups below have 80 scheduled rows; each seed contributes 40. The last
column applies WP96's 76/80 pooled and >=36/40 per-seed thresholds descriptively
to the changed estimator. It cannot change the frozen study result.

| Stream | Policy | Half | Original accurate | Noisy warm vs CDF reference | CDF warm vs CDF reference | CDF per seed 960101 / 960102 | Descriptive half threshold |
|---|---|---|---:|---:|---:|---:|---|
| Shift | frozen | 1 | 67 | 67 | 77 | 38 / 39 | yes |
| Shift | frozen | 2 | 53 | 56 | 68 | 35 / 33 | no |
| Shift | m100 | 1 | 70 | 71 | 79 | 39 / 40 | yes |
| Shift | m100 | 2 | 57 | 58 | 71 | 35 / 36 | no |
| Shift | m500 | 1 | 71 | 70 | 77 | 37 / 40 | yes |
| Shift | m500 | 2 | 48 | 49 | 60 | 26 / 34 | no |
| Shift | trig | 1 | 69 | 69 | 77 | 38 / 39 | yes |
| Shift | trig | 2 | 50 | 52 | 69 | 35 / 34 | no |
| Control | frozen | 1 | 69 | 67 | 79 | 39 / 40 | yes |
| Control | frozen | 2 | 73 | 73 | 78 | 39 / 39 | yes |
| Control | m100 | 1 | 71 | 72 | 79 | 39 / 40 | yes |
| Control | m100 | 2 | 66 | 68 | 75 | 40 / 35 | no |
| Control | m500 | 1 | 71 | 71 | 77 | 37 / 40 | yes |
| Control | m500 | 2 | 69 | 69 | 75 | 35 / 40 | no |
| Control | trig | 1 | 70 | 69 | 79 | 39 / 40 | yes |
| Control | trig | 2 | 72 | 72 | 78 | 39 / 39 | yes |

The four shifted-half-2 shares improve from 66.25/71.25/60/62.5% to
85/88.75/75/86.25% for frozen/m100/m500/trig respectively. They all remain below
95% pooled, and most fail the per-seed floor too. Original and changed per-seed
shares, signed/absolute errors and MCSEs are all recorded in `summary.json`.

## Bias and Monte Carlo precision

For the frozen arm in shifted half 2:

| Quantity | Original noise-added | Analytic-CDF |
|---|---:|---:|
| Median estimated P50 relative MCSE | 1.688% | 1.169% |
| Median estimated P95 relative MCSE | 3.585% | 2.365% |
| Mean signed P50 error | +0.262% | +0.236% |
| Mean signed P95 error | +0.247% | +0.748% |
| Median absolute P50 error | 1.170% | 0.829% |
| Median absolute P95 error | 2.466% | 1.582% |

The analytic CDF removes innovation simulation conditional on the stored posterior
draws. It cannot remove finite posterior-sampling noise, dependence, incomplete
refresh or model error. The remaining MCSE relative to the tolerances makes a
precision-focused follow-up reasonable, but the estimates are asymptotic; these
numbers do not prove absence of warm-start bias. The P95 signed bias increases
even while its median absolute error falls, so improvement is not uniform.

The deterministic reference P50 relative MCSE spans 0.050-0.177%; P95 spans
0.141-0.355%. These are same-sampler finite-draw references shared by every arm
at an origin, without independent-sampler validation here. Reference uncertainty
is stored once per origin and linked from every warm row. MCSE uses chain-aware
mean-CDF uncertainty divided by the mixture density, not raw draw count or weight
ESS. The K=200 warm-chain approximation is diagnostic, not a stopping guarantee.

## Scope and artifacts

This computes predictive **scale** P50/P95. The compact draws contain mu,
log_sigma,h_last and omit beta; full predictive returns are not recoverable
without additional joint draws. No beta imputation is used. The original fixed
window, every-25th-tick scoring and re-adaptation selection limitations remain.

- `PLAN.md`: pre-output diagnostic plan, fixed selection and five-minute ceiling.
- `analyze.py`: read-only analysis using the sibling WP88 analytic-CDF code.
- `summary.json`: all 16 pooled groups and 32 seed groups for all three comparisons,
  versions, plan/source identities and compressed-detail checksum.
- `results.json.gz`: every row/origin, kept-chain/noise-row identities, original
  frozen-gate metadata, reference uncertainty, numerical brackets/residuals,
  original-score reproduction checks and all input hashes.

Reproduce with the isolated WP96 analysis environment or equivalent versions:

```console
python STUDIES/amm_predictive_review_v1/wp96-scale-cdf-diagnostic/analyze.py --study C:/dev/owalnuts-wt/warm-drift/STUDIES/warm_drift_v1 --artifacts C:/dev/owalnuts-wt/warm-drift/target/wp96-recovery-20261027/extracted/warm_drift_v1/artifacts --out NEW_OUTPUT_DIRECTORY
```

Recorded environment: Python 3.14.7, NumPy 2.5.4, SciPy 1.18.1, ArviZ 0.23.4 on
Windows. Per-origin local processing ranged 0.101-0.295 seconds, including one
reference and eight warm comparisons plus diagnostics; this is not sampler or
production latency. All original raw artifacts were read-only.

The next useful question is whether a larger, explicitly budgeted refresh with
analytic scale quantiles reaches the bar on fresh data and seeds. That needs a
separate committed protocol and real end-to-end timing. No re-adaptation policy
or sampler default is promoted by this diagnostic.
