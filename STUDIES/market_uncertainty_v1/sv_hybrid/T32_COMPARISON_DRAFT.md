# Bounded T32 transition/posterior comparison (DRAFT, NOT EXECUTED)

Purpose: detect bias or catastrophic global/path mixing before attempting any
long-path or rolling market comparison. This is a development diagnostic, not a
qualification decision or evidence of exact independent posterior samples.

Freeze one T32 both-flow prior-generative fixture with the existing illustrative
native-return priors, rho .9, nu 5, and fixed known covariates. Declare and audit
new generation, missing-mask, initialization, hybrid, reference and prediction
seeds before generation. Keep one independently drawn 10% missing mask and every
latent transition. Generate four prior-scale physical starts independent of truth;
reuse them in hybrid and the prior-whitened full-joint NumPyro reference.

Prospective ceiling: 300 seconds per arm, four chains, 1000 warmup sweeps/draws,
2000 retained sweeps/draws; no retries or changed priors after seeing results.
Hybrid also has a 2,000,000 started-density-call ceiling across all chains;
EvaluationBudget counts initial, rejected and accepted ESS/slice calls. Count
exact Gamma and Gaussian block draws separately in runner metadata; these are
not included in density calls and must not be confused with free computation.
All compilation, adaptation, diagnostics, predictions and failures stay charged.
Any cap or numerical exception aborts that arm and retains its partial work.

Use the existing same-model normalized-density/JAX parity check at the starts.
Store canonical q for both arms. Require reported rank Rhat<=1.01 and bulk/tail
ESS>=400 on every coordinate and existing eight functionals before interpreting
agreement. Report both .05/.95 endpoint estimates and MCSE, not just means;
show differences normalized by sqrt(MCSE_hybrid²+MCSE_reference²), treating
Monte Carlo uncertainty as estimated. One noisy reference run is not truth.
All disagreement or failed mixing remains an outcome; no speed ratio unless
both arms pass the same declared health and endpoint-precision conditions.
A failure is enough to stop this prototype route for diagnosis, not permission
to quietly increase its budget.

Existing controls: six tests, including 4000 independent posterior-initialized
one-step Gaussian ESS and scalar-slice transitions with fixed seeds and tolerant
known-moment checks. Those check invariance, not convergence from arbitrary
starts. The four original algebra/edge tests remain. Nothing above has launched.
