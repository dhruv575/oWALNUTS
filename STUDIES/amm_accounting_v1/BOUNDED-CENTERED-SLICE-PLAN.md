# Analytically centered independent stress control

This is a separate exploratory follow-up to the failed zero-centered rescaled
slice panel. Preserve all earlier failures. Same target and fixed cases: T=12,
y exactly zero, rho=.95, caps .5/1/2, four chains each. No NUTS draws are used
to choose the reference center, covariance, initialization or budget.

Let A map standard-normal z to a stationary unit-innovation AR path, w=A'1/T,
and k=(T-1)/2. In Gaussian-reference coordinates (standardized mu, prior quantile
for log_sigma, rescaled beta coordinate b, z), choose c=(-k,0,0,-k*cap*w).
Motivation: the rescaled all-zero likelihood has an explicit exp(-k*mean(h))
factor. Completing the square for its Gaussian linear tilt at sigma=cap suggests
this center. The remaining factors are not discarded, and this is not an exact
posterior mean or an approximation to the scientific target.

Use reference N(c,I). Residual log density equals the prior experiment's residual
minus c'core plus c'c/2. Together with N(c,I), this exactly reproduces the old
target. Ellipses are centered at c; covariance remains identity. Ten tests pass
for full density identity, independent AR-weight calculation and transition
ownership. No dependence on fitted NUTS moments or adaptive pilot is introduced.

Each chain starts at c, then 1,000 warmup and 4,000 retained sweeps, scalar mu/w/b
blocks and one 12-coordinate z block. Attempts capped at 1,000, abort on failure.
Seeds 398138000..398138011, audited before launch. No replacement seeds or budget
extension after results. Initialization changes are part of this declared
proposal-design experiment and preclude attributing differences solely to cost.

Twelve concurrent one-core chains on cores 0..11. Per-chain 600seconds,1GiB RSS,
64MiB output; outer 660seconds,14GiB RSS,512MiB output; admission 1GiB free disk.
Preserve full arrays, work counts, sources, audits and failures. Compare all
physical mu,log_sigma,beta,z to the frozen rescaled NUTS archive with verified
input hashes. Qualify only if both methods pass Rhat<=1.01,bulk/tail ESS>=400.
Report all cases and descriptive combined-MCSE differences without simultaneous
coverage claims. This cannot select a scientifically appropriate prior cap or
substitute for the pending real-market predictive and economic evaluation.
