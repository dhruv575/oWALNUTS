# Small-factor high-precision Fisher preflight

Frozen before execution. Keep the running local scaled-policy study unchanged.
Existing float64 QR/SVD Fisher failed one original stress fixture; Newton repair
corrupted forward accuracy despite a small residual. The full80-digit covariance
implementation passed, but is an expensive comparator. Test a computational
representation change, not a new statistical estimator or sampling policy.

Center/normalize samples in float64 and QR both factors, A=QR and B=QT. Convert
only the small triangular R,T matrices to80-digit arithmetic. Form C=R'R and
G=T'T there and solve the same S G S=C expression. Return symmetrized float64 S;
reject invalid/rank-deficient factors and non-SPD output. Explicit gamma augments
the factors with sqrt(gamma)I. No clipping, undocumented ridge, or tolerance change.
Float64 QR may lose information: high precision after QR cannot recover it.

First replay the identical16 original checks, including d2/5/10, target conditions
1/100/10000, distorted point clouds1e-3--1e3, permutation, ordinary parity, invalid
input and explicit regularization. Forward error<=1e-6, formed covariance
residual<=1e-8, permutation error<=1e-6; ordinary parity<=1e-10. Preserve failures.
If any fails, do not qualify or install this implementation. Never use a small
residual alone to certify forward accuracy.

Only after algebra passes, compare saved exposed hybrid01 pilot/scores against
the full80-digit oracle on all24 cells. No target calls, no new sampling, no
independent statistical evidence. Require SPD and relative whitened covariance
error<=1e-7 in every cell. Time three alternating paired fits per cell, single
BLAS thread; report distributions rather than one fastest measurement. Require
the paired geometric fitting-time gain>=2 for a useful numerical candidate.
No runtime claim for a sampler until independent full-policy validation.

Run only after the current local queue stops, to avoid timing contention.
Each stage180s/2GiB/64MiB, monitor the whole output root, preserve source/input
hashes, supervise process-group drain, then archive and read back every member.
