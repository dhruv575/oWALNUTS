# Preserve tiny predictive probabilities in log form

Original predictive batch completed33/36 jobs. Three importance jobs stopped at
the per-draw strict positivity assertion. Reproduction on screen0 found finite
probabilities with106 (128nodes) /105 (256nodes) zeros, no probability above1,
across7 extreme proposal draws. The first diagnostic used a180s timeout/BLAS1;
it did not enforce separate RSS/output caps. Original failures remain preserved.

Reviewed numerical repair applies only to failed deterministic jobs24,25,34,
using identical posterior/proposal samples, models, labels,128/256-node rules,
accuracy gates and budgets. Save log probabilities as well as exponentiated
probabilities; allow numerical zero only when log probability<=log(float64 tiny).
Do not clip/renormalize/drop samples or alter weights. Every zero's represented
quadrature probability is bounded above by2.23e-308, so total omitted weighted
absolute probability per year is bounded by2.23e-308 for normalized weights.
This bound is about floating-point representation,not quadrature error; the
unchanged weighted128/256 convergence gate still applies. Aggregated posterior
probabilities must remain strictly positive. Preserve zeros in archived arrays.

Separate repair01 output,3workers,each300s/768MiB/32MiB,BLAS1. Record repaired
worker hash and original job identity. No new inference or scientific tuning.
The original33 successful outputs are reused unchanged.
