# Defensive importance budget extension

All 16 bounded jobs completed with unchanged dependencies and drained process
groups. At 65,536 draws, 5/8 seeds pass; at 262,144, 7/8 pass. Median cold worker
times are 6.502 and 20.731 seconds, respectively. The larger budget meets the
exploratory screen threshold, not a confirmatory reliability claim.

The remaining large-budget failure (replicate 4) has maximum normalized reference
error 0.543, but Monte Carlo standard error is 2.148 times the allowed limit.
Its Pareto k is 0.583 and its density consistency audit passes. Across that
budget, minimum weight ESS is 24,052 and maximum Pareto k is 0.599. There were
38 target evaluation errors across proposals; these are retained in results.
The near-posterior value/gradient log-density discrepancy is at most 0.0000871.

This strengthens the cheap baseline and deprioritizes the four-parameter public
ODE benchmark as a distinctive application. Older WALNUTS timings are not a
new randomized comparison, and its draws have not yet been evaluated against
these new functional gates. Patient reference failures remain unchanged.
No practical-usefulness or algorithm-improvement success is established.

Full results and archive receipts: ../archive-budget-v1. The first archive
verification attempt discovered a dependency on the earlier audit source;
verification was extended to validate that dependency against the independently
verified screen archive, rather than ignoring it. Both external archive hashes
are recorded. Original remote evidence is retained.

GP provenance follow-up: the candidate dataset is synthetic. Published reference
metadata at pinned posteriordb commit 28f8d3d6 report ten NUTS chains using
adapt_delta 0.99 and max_treedepth 15 with zero divergences. Historical default
NUTS failures therefore do not establish a WALNUTS advantage. Numerical
conditioning and strong tuned baselines must precede any application claim.
