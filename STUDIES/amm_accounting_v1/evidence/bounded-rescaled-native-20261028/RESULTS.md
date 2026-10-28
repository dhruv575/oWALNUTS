# Native exact-coordinate-change admission

All 72 deterministic comparisons passed between the native rescaled callback
and the analytic Python implementation previously checked against Stan. The
panel crosses three caps, T=1/12/250, all-zero and distinct observations, and
four states including eta +/-1000 and mu=-170. Maximum absolute density error
was 4.890e-9 and gradient error 5.457e-12, within declared absolute/relative tolerances.
Mutation isolation and nonfinite-input handling also passed.

The base native callback now exposes its compiled evaluator for exact composition;
the rescaled callback applies the physical-beta change, density Jacobian and
gradient chain rule. Frozen prior evidence retains the prior base implementation.
This check admits implementation only; no WALNUTS draws were generated here.

Executed on one AWS CPU with BLAS/OpenMP threads 1, a 300-second timeout and 4-GiB
virtual-memory limit. Elapsed 12.025 seconds. Source hashes are preserved in the
report and checked locally against these byte-preserved source copies.
