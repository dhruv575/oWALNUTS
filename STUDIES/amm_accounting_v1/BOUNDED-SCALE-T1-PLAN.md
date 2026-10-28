# Fixed one-observation independent reference panel

Caps .5,1,2, in that order; y=0 and rho=.95. Each case uses exactly one million
independent rejection proposals in batches of 10,000, retaining every accepted
draw. No accepted-count stopping or retries. Require at least 1,000 accepted
draws for a comparison; preserve an insufficient-reference result otherwise.

For case j, reference seed=398133000+3*j, NUTS sample seed one higher, Stan
model seed two higher. Audit the nine reserved seeds before launch. MCMC uses
four chains, 2,000 warmup and 4,000 retained draws, target_accept=.9,
maxdepth10, no low-rank/transform adaptation. Initial mean uses mu=2 log(.005),
sigma=.2, beta=z=0, with eta from inverse softplus(log(cap/.2)).

Save full NUTS warmup/retained traces, independent accepted arrays, all four
coordinate diagnostics, means/MCSEs, variances, and descriptive quantiles.
Require Rhat<=1.01, bulk/tail ESS>=400 and zero retained divergences for MCMC
diagnostic qualification. Report mean differences in combined MCSE units;
four is a descriptive flag, not a simultaneous statistical test. Independent
reference standard errors use iid accepted draws. This is T1 validation only,
not repeated-tie posterior qualification or scientific selection of a cap.

Three disjoint four-core jobs; each bounded to 600 seconds/4GiB/256MiB output;
outer 660 seconds/18GiB/1.25GiB. Require 3GiB free disk. Bind sources, versions,
seed inventory and completed process drain; preserve every failed slot.
