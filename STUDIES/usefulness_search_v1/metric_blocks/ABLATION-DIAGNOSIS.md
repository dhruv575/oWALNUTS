# Post-hoc diagnostic, separate from frozen promotion gate

After observing failures at seeds 928600006/7, inspect installed geometry against
the exact earnings posterior covariance. This diagnostic cannot change the gate
or count as fresh validation. Do not retune or rerun the batch based on it.

For unconstrained (beta,log sigma), beta covariance is b/(alpha-1)*(X'X)^-1;
log-sigma variance is trigamma(alpha)/4. Cross covariances are zero because
E[beta|sigma]=beta_hat. This is an exact covariance, not a Gaussian approximation
to the whole target. Compare the fixed diagonal, empirical and curvature
covariances with it using the condition number of L' C_exact^-1 L, where L is
the candidate covariance Cholesky factor. Also report marginal variance ratios
and each coordinate's retained ESS. A condition number is only a geometry proxy;
it does not prove the cause of a mixing failure or predict performance generally.
