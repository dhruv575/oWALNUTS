# Stronger baseline qualifies; no regression advantage remains

fisher02 QR/SVD evaluates the existing estimator from raw centered sample factors.
15/16 frozen checks pass; d2/condition10000 forward error3.72e-9 is acceptable but
equation residual9.16e-7 fails. fisher03 Newton refinement also passes15/16 but
corrupts that case's forward accuracy to .203 despite residual6.21e-9. Neither
double-precision implementation is qualified. All fixtures and failures preserved.

fisher04 computes the same estimator at80 decimal digits (mpmath1.3.0). All16
unchanged checks pass: maximum Gaussian relative forward error2.77e-9, maximum
formed-covariance residual4.66e-9, permutation error zero. Ordinary-input parity,
explicit regularization and invalid-input checks pass. Total worker elapsed1.06s.
This is numerical qualification of an existing estimator, not novelty or a full
replication of its published adaptation schedule. Exact private S3 restores verify
11,12,12 members for fisher02/03/04 respectively.

## Supplemental matched comparison

Reuse broad01's24 pilot/control cells; these are NOT new independent seeds.
Each Fisher arm uses400 charged score evaluations, all fitted metric time, the
same pilot last states and750+2000 second-stage schedule. 48 bounded jobs drained;
all24 schedules, charged costs and durable evidence hashes verify. All fits finish.

| Model | Fisher passes | Candidate / Fisher ESS per total call |
|---|---:|---:|
| ARMA | 4/4 | .809 |
| arK | 4/4 | .980 |
| Proper-prior regression | 4/4 | .977 |
| Centered eight schools | 0/4 | unqualified |
| GARCH | 4/4 | .672 |
| GP Poisson regression | 2/4 | unqualified |

Ratios are paired geometric means where every pair qualifies. The candidate
does not demonstrate target-call superiority over Fisher on any qualified model.
Its proper-prior regression ESS/second ratio1.565 reflects the expensive80-digit
implementation and cannot support superiority against an optimized Fisher solver.
Fisher's two GP failures remain accuracy failures; no ratio receives credit for
failed comparison arms. All methods still fail centered eight schools.

The existing estimator explains the large regression gains over automatic
adaptation. This weakens a novelty/advantage claim, in addition to the cheap
collapsed regression control. Candidate fallback has broader observed reliability
than unconditional fixed Fisher, but is not evidence of general superiority.
Archive239 members, exact S3 version restored and verified; parent archive receipt
and hashes retain the reused pilots and controls. No production/default changes.

Next investigate a conservative out-of-chain score-linearity gate for Fisher:
can it retain the gains on near-Gaussian targets while declining nonlinear GP
geometry? Audit existing pilots only as hypothesis development, then freeze a
fresh larger matched validation. Preserve full-shape and unconditional Fisher as
comparators. Remaining reference-backed low-dimensional models are mostly further
Gaussian regressions; the saved inventory prevents mistaking these for diverse
non-Gaussian applications. Wells variants currently lack supplied references.
