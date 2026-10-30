# Frozen GP approximation audit, 2026-10-30

Synthetic benchmark only; no application claim. Freeze before execution.
Four deterministic BFGS starts (seed943000001), centered at log(rho)=log6,
log(alpha)=log2, whitened f=0, plus N(0,.2^2) perturbations for starts1--3.
At most1000 iterations/start; accept only finite log density, max gradient<1e-3
and positive definite finite-difference negative Hessian. Choose highest density
among qualified starts, preserving all failures. No eigenvalue clipping.
Compare Hessians at h=1e-4 and2e-4 (relative Frobenius error<.002). Check gradients
against central density differences at10 curvature-scaled nearby points
(max error/(1+abs(gradient))<1e-4). All target work and setup time charged.

Reference: preserved PosteriorDB draws, ten chains,1000 draws each. Recompute
rank Rhat, bulk/tail ESS and mean MCSE for rho,alpha,11 latent log intensities,
and11 intensities exp(f). Require Rhat<=1.01, bulk/tail ESS>=400 and finite
moments; otherwise approximation comparisons remain unqualified.

Four independent approximation seeds943100001..943100004,32768 draws each.
Raw Laplace: Gaussian at unconstrained MAP with inverse-Hessian covariance.
Defensive importance proposal: equal mixture of that Gaussian and multivariate
t5 with scale factor1.5*Cholesky(cov). Use full normalized mixture log density,
value-only target for weights, no posterior/reference-based proposal tuning.
Keep proposal q, normalized/log weights, transformations, failures and timings.
Separate raw-Laplace and importance random streams within each replicate.

Report mean and SD errors for all24 physical/intensity functionals, importance
ESS and Pareto k, reference MCSE and importance delta-method mean MCSE. Gate
each importance replicate: ESS>=400,k<.7,max mean error<=.1 reference SD,
max relative SD error<=.2, and max mean discrepancy<=4 combined MCSE. Require
all four plus qualified reference for cheap-approximation admission. MCSE is
not credible when weight diagnostics fail; do not use it to excuse errors.
This is a small exploratory adequacy screen, not a universal approximation
guarantee or predictive validation. Preserve raw-Laplace failure separately.

Preparation180s; each approximation600s;2GiB sampled RSS/64MiB output,4 workers.
Use tmpfs, root free>=1GiB,tmpfs>=2GiB,RAM>=10GiB. Hash frozen inputs; preserve
process drain and all failures. Failed numerical preflight blocks sampling.
