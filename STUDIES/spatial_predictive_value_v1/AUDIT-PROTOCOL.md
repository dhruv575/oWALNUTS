# Post-evaluation audit; primary result and thresholds unchanged

The frozen primary evaluation fails its positive-value gate: the GP's log-score
gain over fixed independent-cell Gamma-Poisson is .0465 (<.05), descriptive
block lower bounds against both cellwise controls cross zero, and maximum
per-cell log-score MCSE is about .064 (> .02). Do not weaken any gate.

Audit analytic scores directly from saved per-cell results and recompute the
paired block comparisons using the original seeds. Identify numerical failures
and estimate the mean-log-score MCSE with the covariance across cells retained
(delta-method influence series, eight chains), to distinguish numerical from
spatial sampling uncertainty. This is explanatory, not a replacement gate.

Repeat only the GP's auxiliary Poisson predictive draws at four preselected
audit seeds 955000101..104, holding the posterior draws and heldout data fixed.
Report all four CRPS, coverage and interval-width estimates and their spread;
never select the best replicate or replace the frozen primary score. No new
model, fit, hyperparameter or heldout-based setting selection. Bound this audit
900s/2GiB under the same 64MiB lane cap and 1GiB disk floor.
