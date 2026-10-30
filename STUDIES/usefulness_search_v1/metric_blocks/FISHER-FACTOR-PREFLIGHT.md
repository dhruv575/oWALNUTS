# Factor-based Fisher estimator preflight

Frozen before execution. Preserve fisher01 failure; change numerical representation,
not estimator. Center position/score samples and QR their factors A=QR, B=QT,
so C=R'R and G=T'T. If R T'=U D V', solve S=R' U V' T^-T,
symmetrizing roundoff. This is algebraically S G S=C without explicitly forming
covariances or squaring the cross-factor condition. No clipping or implicit ridge.
Explicit gamma augments both factors by sqrt(gamma) I. Reject rank deficiency.

Repeat d=2,5,10 and true conditions 1,100,10000, 128-point coordinate scales
1e-3--1e3, seed928900000, drawing permutation before evaluating each method so
failures cannot alter subsequent fixtures. This is the same stress family, not
identical archived fisher01 matrices where exceptions changed random consumption.
Retain forward error<=1e-6, equation residual<=1e-8, permutation error<=1e-6.
Also test rank deficient rejection, explicit regularization, nonfinite inputs,
and ordinary random full-rank samples against the existing covariance estimator.
Save raw points, scores and outputs. This qualifies algebra only, not sampler
performance or replication of the published adaptation schedule. Bound execution
to180s/2GiB/64MiB with terminal group drain; preserve failures.
