# Held-out score prediction: definition and limits

This note describes the implemented diagnostic, not a new theorem establishing
sampler accuracy or a claim that the diagnostic is novel.

For each of four pilot chains, fit an affine least-squares map from position to
score using the other three chains. Center and scale training positions for
numerical conditioning. Let E be the held-out score prediction residual matrix,
including any mean prediction error. Let Y be the held-out score matrix centered
at its own held-out mean. With full column rank, define

    rho = sup_(v != 0) ||E v||^2 / ||Y v||^2,
    worst_direction_R2 = 1 - rho.

The denominator uses held-out empirical score variation. It is not the
least-squares training residual or an independent population variance estimate.
The diagnostic accepts Fisher only if every held-out fold has rho < 1. Invalid,
nonfinite, or numerically rank-deficient arrays decline Fisher. An unavailable
or unsafe Fisher metric also falls back, independently of this diagnostic.

Write the reduced QR decomposition Y=Q R. Substituting w=R v gives
rho=||E R^-1||_2^2 because Q has orthonormal columns. The implementation uses a
triangular linear solve expressed through numpy.linalg.solve, never an explicit
inverse of Y'Y. Retaining the residual mean in E penalizes extrapolation bias.
The same criterion is positive definiteness of Y'Y-E'E in exact arithmetic,
but forming that difference is not the implementation and may be less stable.

Under an invertible affine position change x'=x A+b, row-vector scores transform
as y'=y A^-T. The affine regression design spans the same training column space,
so exact-arithmetic predictions and residuals transform the same way. The
generalized Rayleigh quotient is unchanged by the bijection v'=A^T v.
Consequently each fold's rho, and hence the decision, is affine invariant in
exact arithmetic. Rank thresholds, roundoff and near-singularity can break this
property numerically. Existing tests check an affine-score case, coordinate
permutation and one well-conditioned invertible change; they do not certify
invariance for arbitrarily ill-conditioned numerical inputs.

For a Gaussian target, the score is affine in position. A full-rank exact
training design therefore predicts held-out scores exactly, regardless of
whether the pilot covariance is equilibrated, and rho=0. This explains why the
diagnostic can admit a Fisher estimate before covariance adaptation converges.
The argument does not establish that a short pilot has visited every relevant
region of a non-Gaussian target. A mixture or funnel can look locally linear
inside the visited region. Nor does rejection show Fisher will fail: nonlinear
scores may still yield a useful global preconditioner.

These are dependent MCMC draws and four cross-validation folds, not four
independent experiments. The zero threshold is a frozen predictive comparison
against empirical held-out score variation, not a confidence level, test size,
posterior-fidelity certificate, or profitability criterion. Accuracy and
efficiency are assessed separately using the frozen reference-backed sampling
experiments. In particular, centered eight-schools remains a negative control:
declining Fisher does not make the automatic fallback accurate.

The scale repair is a separate mechanism. When the diagnostic declines Fisher
but stable curvature blocks exist, replace the pilot marginal variance scales
by the diagonal of the valid Fisher covariance, preserving block selection and
shape. If safe installation fails, retain the old fallback. This can improve a
scale-distorted fallback without changing the score threshold. It requires its
own fresh comparison; the Gaussian score identity does not prove the repair.
