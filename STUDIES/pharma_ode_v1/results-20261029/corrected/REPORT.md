# Practical pharmacokinetic ODE pilot

Observed-data scope: Theoph subjects 1–3 selected by numeric ID; eight post-baseline training observations and two heldout observations per subject. The public Stan fixture is a computational benchmark with unverified clinical provenance.

Matched-accuracy validation is the primary comparison. An unqualified reference blocks a speed claim; failed seeds remain in the denominator. Speed ratios use only seed pairs that both qualify, so censored comparisons must not be generalized to all attempts.

| Target | Qualified reference | WALNUTS accuracy /8 | NUTS accuracy /8 | WALNUTS diagnostics /8 | NUTS diagnostics /8 | Paired kernel speedup | Sampler gate |
|---|---|---:|---:|---:|---:|---|---|
| stan_public | True | 8 | 7 | 8 | 7 | 1.65x [1.58, 1.73], 7 pairs | True |
| theoph_1 | False | 0 | 0 | 8 | 8 | Unavailable | False |
| theoph_2 | False | 0 | 0 | 8 | 7 | Unavailable | False |
| theoph_3 | False | 0 | 0 | 8 | 8 | Unavailable | False |

## Reference qualification

| Target | R-hat max | ESS min | Divergences | Depth hits | Separate means agree | Numerical audit | Qualified |
|---|---:|---:|---:|---:|---|---|---|
| stan_public | 1.0003235167799913 | 8628.044810738997 | 0 | 0 | True | True | True |
| theoph_1 | 1.0007625156296083 | 8064.190843756442 | 1 | 0 | True | True | False |
| theoph_2 | 1.0010791643788401 | 8118.302273939539 | 2 | 0 | False | True | False |
| theoph_3 | 1.0014460539591488 | 6446.674527682134 | 0 | 0 | False | True | False |
| linear_1 | 1.0006106052181187 | 9261.201291174357 | 0 | 0 | True | True | True |
| linear_2 | 1.000458200318463 | 10293.30779638536 | 0 | 0 | True | True | True |
| linear_3 | 1.0008369084794688 | 10021.646088911617 | 0 | 0 | True | True | True |

## Cheap approximation and model checks

Laplace accuracy is evaluated against the same qualified reference. Its diagnostic pass alone does not establish approximation accuracy. Forecast error ratio >1 exceeds a predeclared forecast bound (including reference Monte Carlo uncertainty).

| Target | Laplace completed | Full accuracy | Forecast error ratio | MAP + Gaussian draws (s) |
|---|---|---|---:|---:|
| theoph_3 | ok | False | None | 0.15116986801149324 |
| linear_1 | ok | False | 4.4165039094957335 | 0.010198318981565535 |
| theoph_1 | ok | False | None | 0.14824990200577304 |
| linear_2 | ok | False | 7.800270978177566 | 0.006642708991421387 |
| theoph_2 | ok | False | None | 0.07574283500434831 |
| stan_public | ok | False | 0.0736561605064988 | 0.08522636198904365 |
| linear_3 | ok | False | 4.487448120481593 | 0.008153303002472967 |

The linear model is a different posterior, not a sampler competitor. Heldout predictive log densities below are descriptive only: six observations cannot establish clinical benefit, and unqualified-reference scores must not be treated as converged estimates. Positive nonlinear-minus-linear values favor the nonlinear model.

| Subject | Nonlinear reference qualified | Linear reference qualified | Nonlinear log score sum | Linear log score sum | Difference |
|---|---|---|---:|---:|---:|
| 1 | False | True | -3.7249271608438814 | -3.043391396611476 | -0.6815357642324056 |
| 2 | False | True | -3.5671307322665697 | -2.283497409494302 | -1.2836333227722676 |
| 3 | False | True | -0.623210154279592 | -0.8724954943143288 | 0.2492853400347368 |

## Costs and completion

Unconditional median kernel times below include all successfully measured runs, even those that failed accuracy. They are workload descriptions, not matched-accuracy speedups. Cold totals include shared MAP preparation, Python startup, sampling, forecasting, diagnostics and serialization. Kernel times include warmup and exclude forecast evaluation.

| Target | Engine | Completed /8 | Median kernel (s) | Median total (s) | Median target calls |
|---|---|---:|---:|---:|---:|
| stan_public | walnuts | 8 | 43.512 | 46.969 | 107410.5 |
| stan_public | nuts | 8 | 72.976 | 76.306 | 180663.5 |
| theoph_1 | walnuts | 8 | 80.512 | 83.931 | 218581.0 |
| theoph_1 | nuts | 8 | 114.963 | 118.412 | 316170.0 |
| theoph_2 | walnuts | 8 | 90.405 | 93.807 | 235983.5 |
| theoph_2 | nuts | 8 | 162.108 | 165.536 | 436031.0 |
| theoph_3 | walnuts | 8 | 249.316 | 252.872 | 608182.0 |
| theoph_3 | nuts | 8 | 303.093 | 306.598 | 751456.5 |

## Limitations and provenance

The original direct-concentration forecast implementation produced nonfinite tail forecasts. It is retained separately. The recorded amendment integrates log concentration after the first positive observation, uses forecast tolerance 1e-10 and leaves the fitted likelihood and gradients unchanged. All calibration/reference/Laplace jobs were rerun; no exposed tuning result was reused. A separate aborted path-routing launch is also retained.

The primary training solver still uses tolerance 1e-8. Retained-reference auditing compares tighter BDF and RK45 gradients and predictions; numeric qualification failures block conclusions. Shared multistart local optimization cannot prove all modes were discovered. References use two parameterizations of NUTS, not independent exact truth. Priors are working assumptions, baseline measurement uncertainty is omitted, and subjects are fit individually without population pooling.

One calibration seed per configuration is a limited exploratory tuning budget. Speed bootstrap intervals are descriptive, conditional on matched passing seeds, and do not adjust for target exploration. Positive sampler gates alone do not satisfy the practical-success rule: cheap forecasts/model alternatives must also be inadequate. No clinical decision model, commercial demand test, profitability claim, deployment or trading is established.

See PROTOCOL.md, forecast_fix/AMENDMENT.md, SELECTION.json, REFERENCES.json, SUMMARY.json, compressed all-attempt rows, source-freeze manifests, resource receipts and full evidence archive verification.
