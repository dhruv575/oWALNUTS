# Common-functional MCMC audit

Exploratory evaluation of the 16 preserved public ODE validation runs against
the same q, q-squared and MAP-curvature tail functionals used in the importance
screen. No draws were regenerated, no thresholds adjusted, and the original
pilot results remain unchanged. Reference error and MCSE tolerances are common;
MCMC additionally requires its usual R-hat, ESS, divergence and depth gates,
while importance sampling uses weight ESS, Pareto k and density audits.

WALNUTS passes 6/8 overall: all eight meet diagnostic and reference-error
requirements, but two miss precision. NUTS passes 7/8 overall: all eight meet
reference-error and precision requirements, but one fails diagnostics.
The largest importance budget passes 7/8. These small, exploratory samples
do not prove equivalence or superiority. They remove the justification for
claiming that only WALNUTS addresses the observed Laplace tail discrepancies.

All 82 external input hashes match the previously verified full archives;
the remote audit source matches the committed local source. These new audit
files were added after the budget archive snapshot and are preserved in Git;
the original S3 snapshot is unchanged.

Next algorithm investigation must account for prior negative evidence: WP39B
found that continuing beyond failed reverse checks reduced ESS per gradient
(0.878 geomean over 17 models), even after addressing the adaptation confound.
Do not repeat that proposal as a new mechanism. The existing kernel_bench
provides allocation counts and exact draw fingerprints for profiling.
