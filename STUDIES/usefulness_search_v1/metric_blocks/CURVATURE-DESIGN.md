# Proposed name-free stable-curvature selector

Mechanism supported by the exposed audit: regression coefficient precision has
stable shape while its scale changes. Global force regression can be poor even
when dense preconditioning has an obvious geometric opportunity. The original
per-coordinate R-squared block proposal is rejected; do not silently substitute
this different rule into its result.

Before any sampler change, evaluate the following explicit prototype on analytic
targets and saved snapshots. It is a research hypothesis, not a proven rule.

1. Use a small fixed number of warmup snapshots, charging central gradient probes
   at two finite-difference steps. Reject nonfinite or numerically inconsistent
   derivatives. Do not use parameter names, data-specific indices or references.
2. A coordinate is eligible only if its Hessian diagonal is positive at every
   probe. A pair is compatible when both its log diagonal-ratio range is at most
   log(1.25) and its normalized off-diagonal range is at most .05. These tolerances
   are prospective prototype choices, not efficacy thresholds inferred from a
   successful run. Record sensitivity in diagnostics rather than retuning them.
3. Enumerate pairwise-compatible blocks with a bounded search; a block must be
   positive definite at every probe and have diagonally normalized condition
   number at least 5 at every probe. Stop/fall back if the search budget is spent.
   Singletons and nearly independent blocks provide no dense-metric motivation.
4. Average trace-normalized block precisions (a convex combination of SPD
   matrices), invert, and normalize to a correlation matrix. Combine that shape
   with the incumbent marginal variance estimates. This proposes a positive
   block covariance without trusting possibly transient curvature magnitude.
   Keep cross-block entries zero and other coordinates diagonal. Validate the
   final matrix numerically; fall back to the incumbent on any failure.

What remains unresolved: snapshot timing and number, bounded dimension/search
limits, exact fallback rules, how the chosen shape is installed/adapted during
remaining warmup, and whether probe overhead pays off. Set these in a frozen
implementation protocol before performance experiments, not after results.
Every choice must be made before retained sampling; fixed SPD mass preserves
the existing kernel's target, but does not guarantee useful mixing.

Required tests: known correlated Gaussian with varying conditional scale,
uncorrelated Gaussian, nonlinear rotating/GP-like curvature, indefinite and
ill-conditioned probes; permutation equivariance where search is exhaustive;
and exact unchanged paths when no block qualifies. No novelty claim. If the
mechanism passes, use fresh independent seeds and a broader target set with
qualified posterior/functional accuracy, full probe/warmup cost and strong
incumbent controls. Do not promote this on the exposed regression rescues alone.
