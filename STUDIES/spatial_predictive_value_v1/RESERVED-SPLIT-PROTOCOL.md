# Reviewed reserved-split continuation

Run the previously reserved point-thinning seed952000002, exposure .2/.8,
without changing the model, priors, grid, score definitions or cheap-control
selection rules. This is another split of the same already exposed forest,
not an independent site and not a replacement for the failed primary gate.

One native-grid NUTS group: seed955100002, four chains, 1000 warmup/4000 draws,
acceptance .99, depth12, diagonal mass, no step jitter. Save raw draws and all
405-functional diagnostics. Require Rhat<=1.01, bulk/tail ESS>=1000 and zero
divergences/depth hits to interpret its predictions. This single-engine group
does not constitute a new independently qualified reference.

Refit the same five cheap controls using only this split's training counts.
Use the unchanged thinning folds, bandwidth/shape grids and tie-breaking rules.
Terrain regression uses the same prior and order32/48 corrected quadrature.
Evaluate all retained outcomes once with the original marginal log score,
CRPS, RMSE, coverage and block-bootstrap definitions. Report all comparisons
as exploratory same-site split sensitivity, without a positive-value declaration.
No attempt to repair the primary result through split selection.

Separate lane, <=32MiB new output, 900s, 2GiB, four CPUs and 1GiB free disk
floor. Preserve source/hash freeze, exact masks, train/heldout counts, raw draws,
failures and summaries. Do not alter the original lane or delete evidence.
