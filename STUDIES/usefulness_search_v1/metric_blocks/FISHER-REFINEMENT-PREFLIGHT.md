# Fisher residual refinement preflight

Freeze before execution: start from fisher02 factor estimate. Up to five Newton
corrections solve (S G) delta + delta (G S) = C - S G S, computing residual
from raw factors to avoid covariance multiplication cancellation. Symmetrize
correction, require SPD, accept only strictly smaller factor residual, otherwise
stop. No changed estimator, ridge, eigenvalue clipping or threshold relaxation.
Replay identical fisher02 seeded fixtures/test order, ordinary parity, and invalid
input tests. Original formed-covariance residual<=1e-8, forward and permutation
errors<=1e-6 remain gates. Preserve fisher02's single residual failure. Limits
remain180s/2GiB/64MiB; save raw fixtures, immutable sources and supervision.
