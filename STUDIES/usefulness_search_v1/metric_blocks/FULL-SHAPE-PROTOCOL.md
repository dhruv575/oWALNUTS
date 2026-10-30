# Full block shape preflight v3

Frozen before execution, 2026-10-30. Existing v2 discovery remains unchanged.
For each discovered block, average trace-normalized symmetrized half-step
precisions and invert to B. Replace independent marginal substitutions by a
single positive multiplier exp(median(log(v_i)-log(B_ii))). Install that multiple
of B. Unselected coordinates remain diagonal. Symmetrize output; reject nonfinite
or nonpositive blocks and normalized output eigenvalues <=1e-10. Any failure
returns the original diagonal incumbent. No change to discovery thresholds.

Analytic checks: distorted incumbent variances cannot alter recovered relative
block shape for proportional Gaussian precision snapshots; correct inverse
orientation; SPD; exact diagonal fallback; permutation equivariance and coordinate
unit equivariance for exactly proportional shapes. Variable-shape unit invariance
is NOT claimed. Common block scale can still be wrong, and fixed unselected
coordinates can still be poorly adapted.

Exposed audit: apply to all sixteen saved ablation matrices, report old/new
exact-covariance condition proxies and discovery consistency. Require each of
the three previously failed curvature seeds to reduce that proxy by at least
10x as a mechanism gate. This threshold is a prospective diagnostic choice,
not fresh efficacy. No new target calls or sampling. Passing does not rehabilitate
v2 and does not establish MCMC improvement. Use 180s/2GiB/64MiB sampled limits,
hash inputs and preserve all outcomes. Fresh broader tests remain mandatory.
