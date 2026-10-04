# Correlated reference uncertainty resource study

This study asks whether the existing whole-fit bootstrap reference procedure
can resolve its declared endpoint tolerances with correlated draws at a larger,
fixed resource allocation. It is an analytic diagnostic for the forthcoming
actual-posterior bank, not evidence of market forecast calibration.

The authoritative configuration is `plan.json`, frozen from the independently
reviewed `plan-draft.json` before execution. The draft SHA-256 is
`a09be1246fbf4722289f11a0577d2830cfec275d47bea474393e0af77912c97c`.
The seed inventory records all 3,612 streams and prior allocated streams,
including previously unstarted cells. Preparation and audit sources are kept
alongside the plan.

There are four resource sentinels and 24 main trials: twelve Gaussian-AR null
trials with rho .9, four iid null trials, and four trials at each of shifts .1
and .5 with rho .9. Each backend has 32 independently initialized paths of
8,192 values. The 4,096 prefix is paired with the full path; 1,024 and 4,096
prefix diagnostics cannot select a different primary length after execution.
There are 30,000 whole-fit bootstrap resamples per trial.

Keep alpha .05, endpoint half-width .1 distribution widths, backend equivalence
.02 widths, length stability .1 widths, and minimum tail count 20. Exploratory
progression requires at least 9/12 correlated-null resolutions, 11/12 joint
truth coverages and zero resolved misses; iid requires at least 3/4 resolutions,
4/4 joint truth coverages and zero resolved misses. Neither shifted group may
have a resolution. All 24 main trials must complete with valid provenance.
Report exact binomial intervals; these small counts do not qualify calibration.

The prospective execution allowance is 3,600 seconds including a 15-second
cleanup reserve. Workers run on CPU 0 with a 2-GiB committed-memory cap. The
maximum full sentinel cost times 24 times four must fit the remaining allowance
before main trials begin. Every intended cell, failure, unstarted cell and
incurred cost stays in the denominator. No automatic retry is permitted.

An independent Gaussian-AR indicator covariance calculation checks the
finite-length variance scale. Its conversion to quantile covariance is a delta
approximation; numerical quadrature error estimates are not certified bounds.
Neither covariance agreement nor overlapping intervals proves equivalence or
posterior endpoint accuracy.

After this one bounded analytic study, proceed to the existing T1000/G4 actual
posterior resource pilot, retaining failures and achieved uncertainty. Failure
here does not authorize weakening tolerances or another automatic analytic
budget expansion. The subsequent posterior bank needs independent fits and a
separate frozen plan; the four-fit resource pilot cannot qualify its accuracy.
