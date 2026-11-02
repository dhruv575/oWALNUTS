# Spatial predictive value: useful uncertainty, modest advantage over cheap counts

The faster GP is computationally usable and improves several heldout metrics,
but this primary dataset **does not pass the frozen positive-value gate**.
The strongest cheap independent-cell models remain competitive. Do not turn
the large runtime improvement into a claim of unique application value.

## Actual task and evaluation

Predict the reserved 80% of a historical tree census from a fixed 20% sample,
in 200 equal 50m-square cells. The public Bei dataset is one forest rectangle,
not a future forecast, a new site or a blinded new dataset. Its pinned source
contains 3604 points although accompanying documentation says 3605; the existing
discrepancy and provenance remain unchanged. Primary split seed952000001.

Before opening heldout counts, freeze all predictors, scoring, precision rules,
spatial blocks and meaningful-improvement criteria. The new reference combines
two native-grid 4000-draw groups and two historical dense-WAL groups; all
individual, pairwise and combined 405-functional gates pass without relaxing
the historical thresholds. The old failed reference is not overwritten.

## Primary heldout results

Higher log score is better; lower CRPS and RMSE are better. CRPS measures the
quality of the entire count prediction distribution. Coverage and width refer
to central 90% predictive intervals, including count observation noise.

| Predictor | Mean log score | Mean CRPS | RMSE | 90% coverage | Mean 90% width |
|---|---:|---:|---:|---:|---:|
| Full grid GP | -2.934 | 3.453 | 7.039 | 92.5% | 18.90 |
| Fixed independent-cell Gamma-Poisson | -2.980 | 3.690 | 7.524 | 94.0% | 22.39 |
| Training-selected empirical Bayes | -3.013 | 3.760 | 7.632 | 93.5% | 21.96 |
| Training-selected spatial smoother | -3.504 | 3.647 | 7.043 | 68.5% | 10.76 |
| Terrain-only Poisson regression | -8.935 | 9.524 | 16.407 | 31.0% | 12.57 |
| Homogeneous Gamma-Poisson | -9.760 | 10.180 | 16.828 | 32.0% | 13.00 |
| GP Gaussian/Laplace approximation | -3.076 | 4.463 | unstable tail estimate | 98.0% | 54.00 |

Relative to fixed independent-cell counts, the GP has 6.4% lower CRPS, 6.5%
lower RMSE and 15.6% narrower intervals while retaining 92.5% observed coverage.
Relative to the best competitor's CRPS (the smoother), the improvement is 5.3%.
The smoother's point predictions are almost as accurate, but its plug-in
Poisson intervals under-cover badly. Count uncertainty is useful here; spatial
GP inference has not yet proved necessary to obtain most of that benefit.

## Why this is not a confirmed win

The log-score gain over fixed cell counts is only **0.0465 nats/cell**, below
the predeclared 0.05 minimum. Its multiplicity-adjusted descriptive block
interval is **[-0.0854, 0.1689]**; the empirical-Bayes comparison is also
inconclusive: gain0.0796, interval[-0.0294,0.1657]. The eight 250m-square blocks
all come from one spatial realization; these intervals are not independent-
site uncertainty and can retain between-block dependence.

Five of 200 cells miss the per-cell log-score MCSE requirement in each GP group;
the largest MCSE is0.064 against the .02 cap. Mean-rate precision and between-
group predictive agreement pass. An explanatory audit gives average-log-score
MCSE0.00056, much smaller than the block uncertainty. More MCMC alone is
unlikely to resolve the lack of a clear practical advantage; the failed
per-cell gate nevertheless remains failed.

The primary CRPS/interval calculation adds Poisson predictive sampling. Four
fixed audit replicates give GP CRPS3.4499–3.4527 and identical92.5% coverage;
the original frozen score is retained. Terrain order32/48 predictive log
scores agree within6.6e-14. Independent analytic count-score checks agree to
better than8e-13, and the paired block calculations reproduce exactly.

## Cheap GP approximation

The initial optimizer stopped at max gradient .00279, missing the .001 source
gate. A separately frozen, training-only Newton refinement before heldout
access reduced it to8.5e-7 in one step. Its Hessian is positive without clipping.
Defensive importance correction still collapses: weight ESS1.00 and1.57 out of
8192, Pareto-k9.47/9.75. It is not a qualified full-target approximation.
The Gaussian predictive approximation was nonetheless included as a competitor;
its finite-sample mean is dominated by extreme tail draws, so its RMSE is not
a stable practical prediction estimate. Preserve this failure rather than
claiming that approximation is an equivalent cheap replacement.

## Practical conclusion and continuation

A concrete candidate use case is probabilistic completion of a partial spatial
census on a regular grid. Fits take tens of seconds with the exact grid backend;
primary scoring of all seven predictors took11.8s after imports. This is
operationally feasible. This study does not establish that the richer GP is
worth its added complexity over a cheap count model, nor any decision benefit,
unique WALNUTS advantage or profitability.

The previously reserved split952000002 has now completed with unchanged model,
priors and training-only selection rules. It passes chain diagnostics (minimum
bulk ESS4069, Rhat1.0006, no divergences/depth hits), but the application gain
is smaller: GP CRPS3.818 versus the best cheap control3.873, only1.4% better;
90% coverage89%; RMSE8.558 versus the smoother8.037. Log-score gains over fixed
cell counts (.0338) and empirical Bayes (.0451) both have block lower bounds
below zero. Fit time31.5s, complete worker42.4s. This reinforces the conclusion
that the current evidence is not a compelling win over cheap counts.

Continue the remaining preplanned seeds952000003/4 under the same constraints.
These are exploratory same-site sensitivity checks, not replacements for the
primary failure or independent-site replication. Protocol:
`STUDIES/spatial_predictive_value_v1/RESERVED-SPLIT-PROTOCOL.md`.

Evidence: `STUDIES/spatial_predictive_value_v1/evidence01/`. All45 completed
snapshot files, including raw approximation proposals, were copied and verified
against remote SHA-256 hashes. Original GP raw draws remain in the algorithmic
study; heldout scoring source/data freezes and all failures are preserved.
Only the existing AWS instance was used, with bounded jobs and disk monitoring.
