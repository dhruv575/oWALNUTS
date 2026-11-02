# Spatial predictive value, frozen before opening heldout counts

Use the existing public Bei partial-census primary split, unchanged 20x10 grid,
training exposure .2 and reserved exposure .8. This is historical same-site
partial-census prediction, not future forecasting or independent-site validation.
Preserve the source's documented 3605 versus parsed 3604 point discrepancy.
No settings will be chosen or changed using the heldout counts.

## Training inference gate

Create a separately labeled reference qualification, leaving the historical
failed reference unchanged. Use the two native-grid 4000-draw groups with seeds
954100004 and 954100005 plus the two historical dense-WAL 2000-draw groups
952200003/4. Every group's original full 405-functional statistics must satisfy
Rhat <=1.01, bulk/tail ESS >=1000 and no divergences. Check all six pairs:
maximum mean discrepancy <=4 combined MCSE and <=.05 pooled SD, relative SD
discrepancy <=.10. For equal-length combined-chain diagnostics, deterministically
retain every other native-grid draw, retaining all WAL draws. Require combined
Rhat <=1.01, bulk ESS >=4000, tail ESS >=2000, max MCSE/SD <=.02. These are
diagnostic and numerical checks, not a mathematical proof of exactness.
Reconstruct native physical functionals and verify saved summaries. Heldout
scoring is blocked if these gates fail; do not weaken them or pick passing pairs.

## Predictors, fixed before evaluation

1. Full grid GP: equal-weight mixture of all 32000 draws from the two native
   4000-draw groups. Report each group separately for numerical stability.
2. Terrain-only Poisson regression: existing qualified order48 quadrature;
   repeat predictive log scoring at order32 to check numerical convergence.
3. Homogeneous conjugate Gamma-Poisson.
4. Fixed independent-cell Gamma-Poisson.
5. Training-selected empirical-Bayes Gamma-Poisson.
6. Training-selected spatial kernel smoother, plug-in Poisson.
The latter four use exactly the existing frozen training-selected parameters.
7. Full-target Laplace GP approximation: three training-only optimizer starts,
   log rho=0, log alpha=-1/0/1, terrain coefficients and zero latent field;
   L-BFGS up to 2000 iterations, choose greatest finite target density. Compute
   a central-difference Hessian (step 1e-4); require positive eigenvalues without
   clipping. A failed fit is recorded, not silently repaired after evaluation.
   Generate 8192 Gaussian approximation draws, seed955000010. Include it as an
   approximate predictor, not an exact posterior, if numerically valid.
   Independently test two 8192-draw defensive importance batches, seeds955000011/12,
   proposal .9 Gaussian + .1 Student-t8 with shape2.25*covariance. Require both
   k<.7 and ESS>=1000 before treating correction as qualified. Save failures.
   Importance is a fidelity check, not an extra predictor selected by heldout.

## Scoring and uncertainty

Primary: mean marginal heldout log predictive probability per cell (higher
is better). Secondary: count CRPS (lower), RMSE of predictive means, central
50%/90% predictive interval coverage and mean interval width. Evaluate predictive
count distributions, not intervals for latent rates. Include Poisson observation
noise. Conjugate and plug-in scores are analytic; GP and terrain probabilities
integrate their posterior. Report predictive variance including parameter
uncertainty. Marginal scoring is not a joint spatial log score.

For mixture intervals/CRPS, draw one Poisson count per posterior/quadrature
particle, using fixed independent seeds 955000020+predictor index. Use exact
weighted empirical CRPS (sorted-sample identity) and weighted quantiles;
report this additional numerical sampling uncertainty. Analytic controls use
their exact discrete CDF, with CRPS summation tail <=1e-10.
GP per-cell log-score MCSE (delta method applied to probability chains) <=.02;
mean-rate MCSE/mean <=.01. Native group log-score differences <=max(.05,
4 combined MCSE) per cell. Terrain order32/48 log scores differ <=.02 per
cell and <=.005 on average. If numerical scoring gates fail, retain scores
but do not make a positive predictive-value claim or tune model settings.

Use eight fixed nonoverlapping 5x5-cell spatial blocks (250m squares), 10000
paired block-bootstrap resamples, seed955000030. Report all comparator score
differences; one-sided lower percentile bounds use alpha=.05/6 (six competitors,
including Laplace even if it fails), to limit multiple-comparison optimism.
These intervals are descriptive: eight blocks in one spatial realization are
not independent-site evidence, and between-block dependence can remain.

Call this dataset a positive predictive-value pilot only if numerical gates
pass, GP improves mean log score by >=.05 nats/cell over every available
competitor, every paired lower bound is >0, and GP mean CRPS is >=5% lower
than the best competitor. Report failures and tradeoffs rather than changing
the endpoint. Coverage is a separate descriptive calibration check, not a
guarantee. No decision value, uniqueness, conservation impact or profit claim.

## Execution

Existing EC2 only. Training preparation/reference and scoring each bounded
900s/2GiB; one BLAS thread; total new lane output <=64MiB. Monitor a 1GiB free
disk floor. Freeze source/data hashes before execution and verify afterwards.
Keep heldout unopened until source and scoring rules freeze and training gates
finish. Preserve all source, logs, failures, seeds, raw approximation proposals
and per-cell scores. No deletion, deployment, trading or new instances.
