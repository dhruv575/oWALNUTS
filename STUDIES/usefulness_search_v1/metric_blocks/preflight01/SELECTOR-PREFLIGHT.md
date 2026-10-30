# Stable-curvature selector preflight v1

Frozen before execution, 2026-10-30. Offline mechanism test only; no sampling
performance or automatic improvement claim. Use all 16 saved states per cell.
Future online snapshot timing and installation require a separate frozen protocol.

Accept dimensions 2--16 and at most 65,536 enumerated subsets. Require finite
two-step Hessians, relative Frobenius step/symmetry error <=1e-4, and positive
incumbent variances. Symmetrize the half-step Hessian. Eligible diagonals are
positive at every state. Pair log diagonal-ratio range <=log(1.25) and normalized
off-diagonal range <=.05. Enumerate every compatible subset of size >=2. Require
normalized precision eigenvalues >1e-10, condition number >=5 and <=1e8 at every
state. Retain inclusion-maximal qualifying blocks. If any maximal blocks overlap,
fall back entirely: no coordinate-order-dependent greedy resolution.

Average trace-normalized block precisions, invert, normalize to correlation,
and restore incumbent marginal variances. All other entries stay diagonal.
Require finite SPD output with normalized minimum eigenvalue >1e-10. Invalid
inputs, budget exhaustion, ambiguity or no block return the exact incumbent
diagonal matrix. Inputs contain no model names or coordinate labels.

Analytic gates: recover the covariance correlation of a known correlated block
under 1--1000 precision scaling; reject independent, rotating, indefinite,
ill-conditioned and inconsistent probes; preserve positive marginal variances;
verify permutation equivariance and unit-rescaling equivariance. Exposed saved
states assess discovery, not efficacy. Report every cell, including failure.
No tuning based on these outcomes. Bounds: 180 seconds, 2 GiB sampled RSS,
64 MiB sampled output, one worker. Preserve input hashes, supervision and output.
