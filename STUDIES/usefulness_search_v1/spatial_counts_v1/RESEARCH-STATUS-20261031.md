# Spatial partial-census research checkpoint

## Verified controls

The terrain-only Poisson model has a numerically qualified training posterior
for403 quantities: beta3, log intensities200, intensities200. Order32/48 Gaussian
quadrature agrees to1.23e-11 posterior SD on means and4.75e-10 relative on SDs.
Two65536-proposal Student-t checks pass: ESS36557/36465, Pareto-k approximately
-.69, maximum MCSE/SD .00432, mean disagreement below1 MCSE. A separate audit
verified all131072 proposals, density ratios, moments and an independent Hermite
convention. No heldout outcomes were opened.

Calculation took1.570s after imports; supervised invocation16.501s, peakRSS
226.6MB. Independent audit24.218s including startup. These local WSL times are
not matched AWS sampler speed comparisons. Laplace means differ by up to.05883
posterior SD and SDs by.752%; direct integration is cheap for this3D model.
Expensive sampling must justify itself through verified richer-model value or
a matched computational advantage.

Four additional controls are prepared: homogeneous conjugate counts, fixed
independent cell rates, empirical-Bayes shrinkage and spatial Gaussian smoothing.
Five fixed training-thinning folds select shrinkage shape1 and25m bandwidth.
The bandwidth is the smallest tested, not a continuous optimum. Full grids are
retained. Internal selection scores do not establish heldout gains. Conjugate
normalization/moment, fold conservation and kernel constant-preservation checks
pass. Invocation5.906s, peakRSS100.2MB.

## Active AWS attempt

Four groups of four chains sample the205-parameter spatial GP: two native NUTS
and two WALNUTS,2000warmup/2000retained, strict405-functional gates. Group0 lives
in spatial-counts-reference-20261031; groups1..3 in the same path with suffix
-v2. All16 CPUs observed busy; approximately28.9GiB available memory and1.61GiB
free disk. Inspect LIVE.json/STATUS.json for current state, not this snapshot.

Three original groups failed before sampling on ArviZ's shared warning-cache
rename. Failures remain; a separately frozen repair isolates caches while
retaining unused seeds/settings. No inferential outcome prompted repair. Each
worker is bounded40minutes/4GiB RSS/128MiB output, with1GiB free-disk floor.
No inference retries. A distinct watcher at spatial-counts-reference-audit-
20261031 waits at most45minutes after repaired launch, then runs a bounded
10-minute raw audit and writes AUDIT.json/RESULT.md or failure receipt. It
does not start another sampler. All source freezes remain intact.

## Evidence and next decisions

All19 prior smoke files copied from AWS and SHA256-verified locally. Controls
retain raw proposals and summaries. AWS CLI login expired; no new S3 upload or
evidence deletion. Larger campaigns require additional verified disk headroom.

Review terminal reference/audit results. Failure requires diagnosis and a new
protocol, not weaker gates. If qualified, test conditional Laplace/defensive
importance on the same spatial target. Freeze predictive precision and heldout
scoring before opening test outcomes; compare against all cheap controls.
No verified AMM success, application advantage, uniqueness or profitability.
