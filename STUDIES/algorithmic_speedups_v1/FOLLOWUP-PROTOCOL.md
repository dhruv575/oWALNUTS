# Followups after initial pilot observations

The frozen triangular map passes value, gradient, inverse and balance checks.
All initially completed transported physics methods pass reference, precision
and convergence gates; affine/raw native controls frequently miss precision
at 1000 draws. Run all six native engine/coordinate combinations at 4000
retained draws, unchanged 500 warmup, same two seeds. This is a labeled
post-pilot precision followup, not an independent replication. Charge original
transport preparation to every transported job. Use at most two CPU workers.
Retain and report the short failures rather than comparing only passing rows.

The first grid-to-Stan physical conversion missed the 1e-5 density gate at
rho=2, with 4e-7 field error after converting through an independently formed
near-singular Cholesky factor. Extract the actual compiled Stan Cholesky
factor via basis-field evaluations to distinguish conversion error from
target mismatch. Preserve the original result; do not loosen the gate.
