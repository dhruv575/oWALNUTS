# Proper-prior regression shortcut preflight

Frozen after broad01, before numerical results. This is a model-specific control,
not a replacement for fresh general sampler validation. Integrate beta analytically
under its N(0,100 I) prior, then integrate log sigma numerically. Use an SVD of X
and retain the half-normal(10) sigma prior and log-coordinate Jacobian.

First qualify marginal moments, not sampling: compare adaptive quadrature on
mode +/-12 and +/-16 log units, epsabs/epsrel 1e-10. Require moment agreement
within 1e-7 reference SD and reported quadrature relative error below 1e-7.
Require 64 joint target density/gradient comparisons with centered density error
<=1e-6 and scaled gradient error <=1e-7. Compare exact-mixture marginal means
to qualified reference within 4.5 reference MCSE and .1 SD, SD within 10%.
Record all failures, setup/integration time and evaluations. Four fresh IID
sampling replicas require a separately frozen numerical CDF accuracy protocol;
this preflight alone cannot claim IID generation or a sampler speed comparison.
Bound worker to 180 seconds, 2 GiB RSS, 64 MiB output and preserve supervision.
