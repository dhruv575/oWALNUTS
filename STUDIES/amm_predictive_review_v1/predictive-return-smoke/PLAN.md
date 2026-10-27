# One-origin full predictive-return processing smoke

Prepared 2026-10-27 before any WP97 draw processing in this directory. Diagnostic
only; no new sampler cells, remote computation or qualification. Fixture checks
may run locally now. No multi-origin plan is authorized by this processor.

The eventual fixed smoke input is WP97 `ref-real-lo`, tick 2, using its recorded
successful attempt and kept chains. Missing/failed data remain unavailable; no
replacement origin or thinning. Parent must first verify recovered file identity
and explicitly initiate this one-origin diagnostic when it is available.

Read all compact mu,log_sigma,beta,h_last draws as little-endian float32 promoted
to float64. Preserve joint beta/volatility dependence. For each draw,
m=mu+rho*(h_last-mu), sigma_h=exp(log_sigma), and

F_return(x)=mean(E_Z[T_nu((x-beta)*exp(-(m+sigma_h*Z)/2))]), Z~N(0,1).

Use positive Gauss-Hermite rules with 64 and 128 nodes, chunked over posterior
draws. Cache quadrature nodes and at most 128 MiB of inverse-scale matrices;
stream additional chunks rather than exceeding that allocation budget. This is
an array-cache limit, not a promised process RSS ceiling. Invert the full mixture
CDF for return P5/P50/P95 with dynamic two-sided bracketing and Brent's method.

Before any input draw is read, validate small fixed mixtures against independent
adaptive integration over Z, with quad error estimates checked and recorded.
Include a symmetric-location fixture whose median is known exactly. Require
finite parameters, positive sigma_h and valid normalized positive quadrature
weights. Reject unsupported floating-point scale overflow instead of silently
altering the distribution. Verify numeric monotonicity and root residual <=1e-8.

For the smoke record both rules' quantiles, 128-node CDF at each 64-node root,
absolute CDF discrepancy (diagnostic target <=1e-6), and endpoint difference
relative to the 128-node 90% interval width. Node agreement is a convergence
diagnostic, not a proof of quadrature error; large disagreement is an explicit
failure and does not trigger unplanned node increases or component subsampling.
No endpoint MCSE or automatic adaptive sampling policy is inferred.

Five-minute local ceiling after imports, checked inside every CDF chunk. Persist
status and partial timing on failure/timeout. Record per-node CDF evaluations,
Student-t evaluation count, cached bytes, total processing wall, and original
kept-chain/attempt identities. Hash protocol, raw file, records, executed source
and this plan; verify inputs unchanged afterward. Do not overwrite output files
on a repeated invocation. Local timings are neither sampler timings nor an
optimized production benchmark. No calibration, quote or profitability claim.

Only after this full-size one-origin workload is measured may a separate bounded
multi-origin diagnostic be proposed and committed. The processor's presence is
not evidence that WP97 ran or that full predictive processing fits its budget.
