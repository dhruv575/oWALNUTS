# Deterministic future GP quantities, before scoring

Extend the unchanged raw Stan model only with data N_future,x_future and
deterministic generated quantities. Future years1931..1961, x=20*(year-1851)/79.
No future labels are read. Let L be the training covariance Cholesky, B the
training/future covariance, A=L^{-1}B. Conditional future log intensity has
mean A' f_tilde and marginal variance alpha^2+1e-10-columns_dot_self(A).
Future nugget matches the training1e-10 convention. Only marginal variances
are needed for pointwise predictive scores; this does not define independence
between future years or a joint sequence score.

Compile with existing BridgeStan2.9.0,STAN_THREADS=true,-j1. At16 evenly spaced
draws from the already qualified WAL reference group2 plus8 normal(0,.25)
points seed951700001: verify unchanged parameter names and raw log density/
gradient to absolute1e-8, physical parameters to1e-8. Independently reconstruct
L via79 basis evaluations of the original compiled model and check future mean
and variance using SciPy triangular solves to absolute1e-6. Require finite
nonnegative variances. Save all points and numerical differences.

One local BLAS1 build/check process300s/4GiB/256MiB (new build-directory output).
Preserve failure; no automatic retries. This only qualifies the deterministic
predictive calculation. Quadrature, predictive Monte Carlo accuracy, scoring
rules and model comparison require a separate frozen protocol before scoring.
