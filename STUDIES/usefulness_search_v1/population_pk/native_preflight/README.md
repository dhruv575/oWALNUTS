# Native target and mode preflight

Shared native gradient target and analytic value-only density pass the recorded
checks. The primary Hessian has eigenvalues .967--4449. A secondary rate-order
mode qualifies after scaling the optimization objective by96 (same optimum,
better line search). The unscaled optimizer false convergence is preserved.
Rate exchange preserves all zero-baseline trajectories to7e-15, but not the
three subjects with nonzero baselines (max log prediction difference .0585).
The initial all-subject symmetry assertion failed and is retained.

The secondary Hessian is positive definite (min eigenvalue .949). Local
Laplace log mass ratio is -21.87, not a qualified global probability bound.
Four-chain pilot initialization therefore covers both modes. The pilot is
implementation/mixing evidence only; it cannot qualify posterior accuracy.
