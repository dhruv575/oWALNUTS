# Predictive CDF uncertainty: short-chain MCSE is not an accuracy certificate

**Method diagnostic, not qualification.** All 27 settings and 5,400 independent
replicates completed in 10.82 seconds of local computation after imports, with
no invalid estimates. The plan was committed before execution (`da10e38e`),
followed by independent formula review and pre-execution implementation review.
The executed source is `55141937`; results record exact source/plan hashes and
environment. No SV sampler, market data or AWS compute was used.

Analytically integrating future innovation generally reduces predictive-scale
quantile error. It does not eliminate uncertainty from correlated posterior
draws, and its estimated MCSE can be substantially too small on short chains.
The strongest counterexample in this finite grid has four 50-draw chains,
AR(1) coefficient 0.98, and posterior-location SD twice future-innovation SD.
Its nominal 95% scale-Wald interval covers the true P95 in **124/200 replicates
(62%; marginal Wilson interval 55.1%-68.4%)**. Median estimated CDF-mean MCSE at
the *true* threshold is only **0.275 times** the analytically known standard
error. This separates a real uncertainty-estimation problem from errors caused
by evaluating the CDF at an estimated quantile.

Those chains are deliberately difficult, even though their starting values are
independent draws from the stationary marginal. No convergence filter is applied.
This is not evidence that a particular oWALNUTS run, or a policy with additional
diagnostic gates, has this coverage. It is a counterexample to using short-chain
MCSE alone as an accuracy certificate or unvalidated adaptive stopping rule.

## Exactly known target and dependence

Each chain samples M with marginal N(m0,tau^2) and AR(1) autocorrelation a^lag.
The future log scale is H=M+sZ, Z an independent standard normal, so H has
exact distribution N(m0,tau^2+s^2). The predictive scale is exp(H/2).
Here m0=2 log(.005), s=.2. The grid varies tau/s, a and draws K; every setting
has 200 independent replicates of four chains. Noise-added and analytic-CDF
quantiles use the same M draws in each replicate. No fitting or data reuse is
needed to know the correct quantiles.

For p in {0.5,0.95}, at the true log-scale quantile, let
g(M)=Phi((h_p-M)/s), z_p=Phi^-1(p), c=tau^2/(tau^2+s^2). Its covariance at lag l
is Phi2(z_p,z_p;c*a^l)-p^2. Equal-threshold Phi2 is computed with Owen's T.
Six independent quadrature moment checks pass to 1e-10, along with the
independent-chain limit and the P50 arcsine identity. Summing these covariances
gives exact finite-chain variance of the mean CDF, not exact quantile variance.

The estimated quantile MCSE uses ArviZ mean-MCSE of g at the estimated root,
divided by the mixture's **scale** density (including the factor 2/q). Its Wald
interval is q_hat +/- 1.96 SE on the scale itself. Delta-method inversion and
normal-Wald intervals remain approximations. We separately evaluate CDF-MCSE
at the known true root to assess uncertainty estimation without root error.
In the highlighted worst case the analytic P95 also has -5.46% relative bias,
so interval undercoverage cannot all be attributed to its MCSE estimate.
The true-threshold calculation independently demonstrates the MCSE weakness.

## Complete grid

Coverage is the fraction of all 200 replicates whose scale-Wald interval covers
the exact predictive quantile. There are no missing/invalid cases, so planned
and valid-estimate denominators coincide. SE ratio is the median estimated
mean-CDF MCSE at the true threshold divided by its exact finite-chain standard
error. RMSE ratio compares analytic-CDF with noise-added quantiles (below one
favors analytic integration). P50 and P95 values are shown separately.

| tau/s | AR coefficient | K | Coverage P50 / P95 | SE ratio P50 / P95 | RMSE ratio P50 / P95 |
|---:|---:|---:|---:|---:|---:|
| 0.5 | 0 | 50 | 93.0% / 94.0% | 0.981 / 0.972 | 0.372 / 0.247 |
| 0.5 | 0 | 200 | 96.0% / 95.0% | 1.002 / 1.007 | 0.350 / 0.238 |
| 0.5 | 0 | 800 | 91.5% / 94.0% | 1.003 / 1.007 | 0.381 / 0.251 |
| 0.5 | 0.8 | 50 | 93.5% / 91.5% | 1.062 / 0.917 | 0.793 / 0.552 |
| 0.5 | 0.8 | 200 | 92.5% / 93.0% | 0.976 / 0.939 | 0.743 / 0.560 |
| 0.5 | 0.8 | 800 | 92.5% / 92.0% | 0.994 / 0.991 | 0.715 / 0.616 |
| 0.5 | 0.98 | 50 | 87.5% / 83.5% | 0.833 / 0.623 | 0.920 / 0.832 |
| 0.5 | 0.98 | 200 | 93.0% / 87.5% | 1.041 / 0.885 | 0.982 / 0.885 |
| 0.5 | 0.98 | 800 | 97.0% / 93.5% | 1.073 / 1.029 | 0.957 / 0.883 |
| 1 | 0 | 50 | 94.0% / 94.0% | 0.980 / 0.993 | 0.588 / 0.450 |
| 1 | 0 | 200 | 95.5% / 96.5% | 1.006 / 0.993 | 0.574 / 0.393 |
| 1 | 0 | 800 | 96.0% / 97.5% | 1.004 / 1.005 | 0.541 / 0.445 |
| 1 | 0.8 | 50 | 93.5% / 88.0% | 1.084 / 0.858 | 0.864 / 0.770 |
| 1 | 0.8 | 200 | 96.0% / 91.0% | 0.975 / 0.981 | 0.907 / 0.780 |
| 1 | 0.8 | 800 | 95.0% / 95.5% | 1.005 / 0.978 | 0.901 / 0.828 |
| 1 | 0.98 | 50 | 80.5% / 72.0% | 0.850 / 0.550 | 0.957 / 0.954 |
| 1 | 0.98 | 200 | 94.0% / 88.0% | 1.121 / 0.787 | 0.974 / 0.981 |
| 1 | 0.98 | 800 | 93.5% / 91.0% | 1.045 / 0.895 | 0.978 / 0.978 |
| 2 | 0 | 50 | 94.5% / 93.5% | 0.981 / 0.966 | 0.744 / 0.756 |
| 2 | 0 | 200 | 93.5% / 94.0% | 1.003 / 1.005 | 0.742 / 0.675 |
| 2 | 0 | 800 | 97.0% / 96.0% | 1.007 / 1.011 | 0.764 / 0.715 |
| 2 | 0.8 | 50 | 95.0% / 85.0% | 1.032 / 0.811 | 0.983 / 0.900 |
| 2 | 0.8 | 200 | 93.0% / 88.0% | 0.982 / 0.911 | 0.970 / 0.979 |
| 2 | 0.8 | 800 | 94.5% / 94.5% | 0.995 / 1.000 | 0.944 / 0.935 |
| 2 | 0.98 | 50 | 83.5% / 62.0% | 0.878 / 0.275 | 0.991 / 0.974 |
| 2 | 0.98 | 200 | 90.5% / 82.5% | 1.080 / 0.764 | 1.005 / 0.984 |
| 2 | 0.98 | 800 | 95.5% / 88.0% | 1.051 / 0.916 | 0.995 / 0.977 |

## Interpretation and limits

At independent draws, integrating future innovation often removes a large
fraction of RMSE. With strong posterior autocorrelation, both estimators retain
almost the same underlying posterior uncertainty, so the relative improvement
can be small. A finite-realization RMSE ratio can exceed one; no result was
discarded or rerun. At the strongest-correlation, largest-location-uncertainty
setting, even K=800 gives P95 interval coverage 88% in this diagnostic.

All 54 empirical CDF-mean variances divided by their exact counterparts range
from 0.744 to 1.243. These are estimates from 200 replicates, not numerical
identity checks; tail-probability error is skewed and empirical variances are
themselves noisy. The exact covariance formulas were checked independently.
Do not treat the reported coverage intervals across the entire grid as a
simultaneous family-wise guarantee. Repeated adaptive stopping was not tested.

This motivates fixed-budget accuracy experiments and separately validated
precision monitoring. It does not supply a calibrated stopping threshold,
forecast calibration, a qualified SV update policy, or profitable AMM quotes.

## Reproduce

`run.py` requires NumPy, SciPy and ArviZ; the executed versions are recorded in
`results.json.gz`. Run with the pinned WP96 analysis environment (ArviZ 0.23.4)
or reproduce the recorded package versions. It writes `results.json`, refusing
to overwrite an existing one. The original uncompressed output remains local
and the lossless compressed output is committed. Every replicate, RNG spawn
key, formula check, summary, provenance and finite-grid failure denominator is
retained. SHA256 checksums cover the committed record.

```console
python STUDIES/predictive_mcse_diagnostic_v1/run.py
```
