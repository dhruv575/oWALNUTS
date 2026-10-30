# High precision Fisher oracle preflight

Frozen before execution. fisher03 Newton refinement reduces residual but corrupts
forward accuracy in the difficult d2/condition10000 case; preserve it as failed.
Use mpmath1.3.0 at80 decimal digits to form C/G directly from input sample floats
and solve the original Cholesky/eigensquare-root expression. Convert final SPD S
to float64. No statistical estimator, gates or fixtures change; rerun the identical
fisher02/fisher03 fixtures, permutations and invalid/parity cases. Retain forward
error<=1e-6, formed-covariance residual<=1e-8, permutation error<=1e-6. Record full
cost. This is a numerical oracle/possible expensive baseline, not a fast method,
novel estimator or published-sampler replication. Bound180s/2GiB/64MiB and archive
the pinned wheel, implementation, raw samples, failures/successes and supervision.
