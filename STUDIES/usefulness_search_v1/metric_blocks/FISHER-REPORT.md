# Dense Fisher numerical preflight fails; baseline not qualified

2026-10-30. The implementation of the published dense estimator is NOT ready for
performance comparison. All nine deliberately ill-conditioned Gaussian recovery
fixtures fail the frozen accuracy/permutation gate; singular/indefinite rejection
and explicitly regularized singular cases pass. The point clouds span coordinate
scales1e-3--1e3, independently of the target's covariance condition. Some formed
score covariances or transformed products lose numerical positive definiteness.

Cases that return a matrix can have tiny equation residuals but unacceptable
forward error: one two-dimensional condition10000 target has relative covariance
error about .986 despite relative S G S-C residual1.23e-13. A small residual alone
therefore cannot qualify this implementation under these conditions. No eigenvalue
clipping, undocumented ridge, tolerance relaxation or selective passing subset.

This is an implementation/stress-test result, NOT evidence that the published
estimator or its sampler is ineffective. No model sampling or performance claim
was attempted. Numerical stabilization and explicit conditioning/representability
checks remain necessary, potentially operating on QR/SVD factors rather than
forming products that square condition numbers. Revalidate on the unchanged
fixtures and preserve any remaining limits before actual-model comparisons.
The running fullshape02 protocol is unchanged and does not include this baseline.

Worker ended with failed-gate exit1 in .13s, process group drained, zero target
evaluations. Inputs rehashed at archive creation. Private10-member archive,
17,014bytes, SHA256
482e68046660dd94f553ae955d04b9ee23a698fb4e7ef671682e657fb8a2cfe5,
passed exact-version restore/member verification. Raw matrices, source and failure
checks are preserved. Production untouched; no baseline or novelty claim.
