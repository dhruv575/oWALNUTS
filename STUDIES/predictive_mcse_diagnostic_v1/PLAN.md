# Predictive CDF Monte Carlo uncertainty diagnostic

2026-10-27. Implementation/method diagnostic, not a qualification study. No
market data, oWALNUTS runs, new AWS cells, default changes or trading claims.

WP96 failed its accuracy criteria with healthy saved reference coordinates and
small signed errors. Analytic predictive CDF integration removes future-noise
simulation, but posterior Monte Carlo error remains. Before using its estimated
MCSE to stop a refresh, test that uncertainty estimate against a known answer.

Use four independent stationary Gaussian AR(1) chains as an exactly specified
posterior-draw process: M has marginal N(m0, tau^2), autocorrelation a^lag,
m0=2 log(.005), and future log scale H=M+s Z with independent Z~N(0,1), s=.2.
The predictive scale is exp(H/2); its distribution is known analytically.
This models correlated draws of a predictive location, not SV posterior geometry.

Grid fixed before simulation: tau/s in {.5,1,2}, a in {0,.8,.98}, retained
draws per chain in {50,200,800}, 200 independent replicates per setting (27
settings). All chains start in their stationary marginal; no adaptation, warmup,
selection or removal. SeedSequence entropy 99271001, one spawned child per
setting in the written grid order. Source/protocol/wiki exact-word search found
no prior use; this is a diagnostic seed, not a future qualification reservation.

On the same posterior draws compare (a) one independent future innovation per
draw with empirical quantiles and (b) analytic-mixture CDF inversion, at P50/P95.
For (b), estimate mean-CDF MCSE with ArviZ 0.23.4 and divide by mixture density
at the estimated quantile. Report relative RMSE, signed error, marginal 95%
Wald interval coverage, invalid estimates and the distribution of estimated
MCSE relative to exact finite-chain *CDF-mean* uncertainty at the true quantile.
Do not conflate exact CDF variance with exact quantile variance: inversion's
delta method is approximate, especially with short highly correlated chains.

An independent analytic covariance check uses the bivariate Gaussian CDF:
Cov(g(M_i),g(M_j)) = Phi2(z_p,z_p;c*a^lag)-p^2, where
g(M)=Phi((h_p-M)/s), c=tau^2/(tau^2+s^2), and z_p=Phi^-1(p).
Evaluate equal-threshold Phi2 using Owen's T, and check lag-zero moments with
independent numerical quadrature. For four K-long chains, variance of the mean
is [K*gamma0+2*sum((K-lag)*gamma_lag)]/(4*K^2). For the noisy indicator the
same cross-lag covariance applies, but gamma0=p*(1-p). At a=0 these must reduce
to independent-sample variance. At p=.5, gamma0=asin(c)/(2*pi).

All 27 settings remain in the report, including missing/timeout outcomes. Cap
local computation at 180 seconds after imports, write partial results on timeout.
Preserve executed source hash, plan hash, package/platform versions, RNG spawn
keys, every replicate's errors and uncertainty, and aggregate tables. No
post-outcome threshold or seed adjustment, and no automatic stopping rule is
qualified by this diagnostic. Marginal coverage counts are descriptive, not
family-wise guarantees across repeated adaptive checks.
