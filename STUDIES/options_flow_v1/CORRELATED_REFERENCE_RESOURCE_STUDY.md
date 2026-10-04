# One bounded correlated reference study

This implements the next analytic resource design. No campaign seeds, frozen
plan or full campaign have been created. It is an exploratory preparation for
an actual demanding-posterior bank, not a calibration qualification study.

Primary banks use 32 independent fits per backend, 8,192 values per fit, a
4,096-value paired prefix and 30,000 whole-fit bootstrap resamples. The existing
.02-width backend-equivalence, .1-width endpoint-uncertainty and .1-width
length-stability requirements remain unchanged. The shorter 1,024 and 4,096
prefixes provide descriptive scaling evidence; they cannot select another
primary length after seeing results.

The design has four timing sentinels and 24 main banks: twelve correlated-null
trials (rho .9), four iid-null trials and four correlated trials at each of
backend shifts .1 and .5. All 28 intended outcomes remain visible after failures,
source drift or a resource stop. The prospective allowance is 3,600 seconds,
including a 15-second cleanup reserve, with a 2-GiB committed-memory cap per
contained worker. The worst sentinel cost times 24 times four must fit the
remaining budget before the main trials start.

Exploratory progression requires at least 9/12 correlated-null resolutions,
11/12 simultaneous truth coverages and no resolved miss; iid requires 3/4
resolutions, 4/4 truth coverages and no resolved miss. Each shifted group must
have zero resolutions. Every main trial must complete with valid provenance.
Report wide binomial uncertainty intervals rather than treating these small
replicate counts as proof of reliable calibration.

`gaussian_ar_indicator.py` independently computes the finite-length Gaussian-AR
empirical-CDF covariance using Plackett integration and exact lag weights. Its
quantile delta covariance is approximate; quadrature error estimates are not
certified bounds. This independent calculation checks the variance calculation
and resource scaling without claiming an exact dependent-quantile interval.

Eleven integrated tests passed in 0.84 seconds. They cover iid closed forms,
median arcsine covariance, explicit small covariance matrices, numerical
convergence, plan/seed mutation, failure denominators, cleanup reserve and
missing or corrupt covariance output. A separate tiny contained worker exercised
the actual vectorized route eight times and passed output, covariance, CPU-0
containment and cleanup checks below the memory cap. Its exact source archive
and evidence are in `artifacts/correlated-reference-smoke-v2`; this smoke used
existing exploratory streams and is not the 28-cell campaign.

After this bounded experiment, move to the existing T1000 posterior resource
pilot. Failure here must not trigger an automatic sequence of increasingly
favorable analytic studies or a weaker equivalence tolerance.
