# Dense Fisher baseline algebra preflight

Frozen before execution, 2026-10-30; independent of running fullshape02. Implements
an existing estimator, not a novel contribution: Seyboldt, Carlson, Carpenter,
[section 2.4.2](https://arxiv.org/html/2603.18845v1). Given SPD position covariance
C and score covariance G, the covariance-shaped metric S solves S G S=C; install
momentum mass S^-1. If G=L L', solve S=L^-T sqrt(L' C L) L^-1. Symmetrize roundoff.
Reject nonfinite/non-SPD matrices. No undocumented ridge or eigenvalue clipping.
For explicitly requested gamma>=0, solve using C+gamma I and G+gamma I.

Tests: Gaussian exact recovery from arbitrarily distorted finite point clouds,
d=2,5,10; true covariance conditions 1,100,10000; point clouds additionally scaled
by1e-3--1e3 across coordinates. Use128 points and fixed seed928900000. Require
relative S error<=1e-6 and relative equation residual<=1e-8; deterministic
permutation checks. Test regularized rank-deficient inputs at gamma1e-3, reject
unregularized singular and indefinite inputs. Preserve numerical failures; no
tolerance adjustment after execution. These tests do not establish performance,
non-Gaussian accuracy or a replication of the published sampler's schedule.

No target evaluations.180s/2GiB/64MiB sampled worker limits. Archive sources,
matrices, outputs and supervision. No production/default changes.
