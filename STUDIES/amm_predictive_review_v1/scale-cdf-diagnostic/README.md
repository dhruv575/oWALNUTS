# Analytic scale-CDF diagnostic on archived WP88 draws

**Post-hoc diagnostic only; no qualification verdict changed.** The plan was
committed at `c59fff66` before these outputs were computed. This uses previously
inspected data, three fixed ticks per dataset, and no new sampler cells.

At ticks 2,50,100 for sim-N250 and real-N250, all six reference origins and all
54 planned warm rows were available and processed. All input hashes remained
unchanged. Six analytic mixture fixtures passed before archived outcomes were
loaded; all inversion residuals were below the planned 1e-10 threshold.

For each stored posterior draw, the analytic mixture CDF integrates the future
Gaussian volatility innovation exactly, then Brent inversion obtains predictive
scale P50/P95. The original estimator adds one realization of that innovation per
draw. Both are evaluated on exactly the same compact draws against the same
analytic-CDF reference. These are **scale quantiles**, not return quantiles or
executable quotes. The compact files do not contain beta.

## Result

The analytic estimator falls within the descriptive 2% P50 / 5% P95 bands on
**45/54 rows**, versus **41/54** for the original noise-added estimator. Six rows
move inside the bands and two move outside. This is a small selected-origin
diagnostic, not a 95%-of-ticks qualification or a paired-significance test.

| Dataset | K | Rows | Noise-added within bands | Analytic CDF within bands | Median absolute P50 error, noise / CDF | Median absolute P95 error, noise / CDF |
|---|---:|---:|---:|---:|---:|---:|
| Sim | 50 | 9 | 5 | 6 | 1.422% / 1.170% | 4.369% / 3.333% |
| Sim | 100 | 9 | 9 | 9 | 0.271% / 0.540% | 1.678% / 1.234% |
| Sim | 200 | 9 | 9 | 9 | 0.450% / 0.243% | 1.456% / 0.752% |
| Real | 50 | 9 | 5 | 7 | 1.471% / 0.498% | 1.638% / 2.218% |
| Real | 100 | 9 | 5 | 7 | 1.184% / 0.737% | 2.697% / 3.205% |
| Real | 200 | 9 | 8 | 7 | 0.625% / 0.893% | 1.659% / 1.110% |

The mixed endpoint results matter: integrating the innovation removes that
simulation noise, but it does not remove posterior-sampling error. Nonlinear
quantile error need not decrease in every finite realization. In particular,
real K=200 loses one within-band row and real K=50/100 have larger median P95
errors. These results do not establish a smaller sufficient K or explain away
WP96's failed criteria.

## Reference uncertainty

These are shared, finite-draw, same-sampler references; an independent inference
algorithm was not validated here. Reference uncertainty is estimated from the
chain-aware MCSE of each draw's CDF contribution, divided by the mixture density
at the root. This asymptotic diagnostic is included in every successful warm row;
threshold indicators do not incorporate a confidence bound.

| Reference origin | Relative CDF-quantile MCSE P50 | Relative CDF-quantile MCSE P95 | Original reference noise-minus-CDF P50 | Original reference noise-minus-CDF P95 |
|---|---:|---:|---:|---:|
| Sim 2 | 0.068% | 0.164% | +0.027% | -0.044% |
| Sim 50 | 0.065% | 0.148% | +0.063% | -0.106% |
| Sim 100 | 0.059% | 0.146% | -0.024% | +0.050% |
| Real 2 | 0.094% | 0.211% | +0.117% | +0.058% |
| Real 50 | 0.101% | 0.204% | +0.092% | +0.070% |
| Real 100 | 0.102% | 0.198% | +0.174% | +0.139% |

Unlike the original WP88 score, both compared estimators here use the analytic
reference. Therefore these counts are not a reproduction or revision of the
original study's whole-stream pass shares. No latency, drift or sampling-health
qualification is applied by this diagnostic.

## Local computation and reproduction

The complete analysis took **0.557 seconds** after Python imports on this laptop;
per-origin processing took 0.080-0.094 seconds including reference diagnostics,
file reads/hashes and nine warm comparisons. Analytic warm-quantile processing
medians were 0.309-0.567 milliseconds across the six groups. These are single-run
local postprocessing measurements, not inference or production performance.
The original noise path generates its historical 4x20,000 innovation array even
for shorter warm chains; its timing is an artifact-reproduction cost and must not
be treated as a fair optimized-estimator benchmark.

From a checkout containing the WP88 untracked compact draws:

```console
python STUDIES/amm_predictive_review_v1/scale-cdf-diagnostic/analyze.py --repo-root C:/dev/owalnuts --out NEW_OUTPUT_DIRECTORY
```

The recorded environment is Python 3.14.7, NumPy 2.5.4, SciPy 1.18.1 and ArviZ
0.23.4 on Windows. Exact environment, plan/source/input SHA256s, original chain
selections, brackets, numerical residuals, timings and all row errors are in
`results.json`. `PLAN.md` fixes the selection, comparison and five-minute ceiling;
missing/invalid/budget-exhausted rows remain explicit in the full denominator.

The result supports further investigation of analytic scale marginalization as
one precision lever. It does not establish predictive calibration, AMM economics,
or a ready-to-ship accuracy policy. The proposed larger qualification remains
conditional on a passing adaptation policy and a new committed protocol.
