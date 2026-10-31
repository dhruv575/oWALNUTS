# Training-only terrain control, frozen 2026-10-31

Use only GP-TRAIN.json. Same three-coefficient Gaussian prior as spatial model:
beta ~ N(0,diag(25,4,4)), y_i ~ Poisson(.2 exp(X_i beta)). No spatial random
field. Assess 403 functionals: beta3, log intensity200, intensity200. This is
a competing model, not an approximation to the spatial GP posterior.

Find the mode with analytic gradient/Hessian; check derivatives by central
differences at the mode and two fixed perturbed points. Require scaled errors
<=1e-5 and positive Hessian eigenvalues. The prior makes negative log posterior
strictly convex. MAP scaled gradient norm <=1e-5.

Adaptive Gauss-Hermite integration in three dimensions, centered/scaled by
Laplace mode/covariance, orders16,24,32,48. Normalize exact posterior/proposal
ratios against Gaussian quadrature weights. Require last two levels' log
normalizers within1e-6, means within1e-4 posterior SD, SDs within1e-4 relative.
Save all quadrature levels. Agreement is a numerical check, not a rigorous bound.

Independent heavy-tail importance cross-check: two batches of65536 Student-t8
proposals with shape1.5^2 times Laplace covariance, seeds952300001..2.
Use raw weights for estimates; Pareto-k is a diagnostic only. Each requires
k<.7, weight ESS>=5000, all403 mean MCSE/SD<=.02, and mean disagreement with
order48 quadrature <=4 importance MCSE. Preserve proposals/log weights and
all checks, including failures. No reruns, tuning or heldout scores.

Report Laplace-versus-quadrature mean and SD discrepancies without claiming
predictive adequacy. Local single-BLAS-thread worker300s/2GiB/64MiB; root
workspace disk>=1GiB. Monitor wall time, process memory and output bytes.
Freeze source hashes before execution and verify at completion.
