# Adaptive defensive importance baseline

Freeze before seeing the long-run reference audit. Two independent seeds
936100001/2. Begin with 80% primary Laplace Gaussian, 10% primary Student-t(5)
and 10% secondary Student-t(5), t scales 1.5 times the respective Hessian factors.
Two 32768-draw adaptation rounds fit the Gaussian component's weighted mean and
covariance; retain both defensive components. Regularize covariance with 5% of
the original primary covariance and clip eigenvalues in primary-whitened space
to [0.1,100]. No reference draws are used to fit proposals.

Final independent proposal draws: 262144. Charge all adaptation and evaluation
work. Raw Laplace baseline: independent 262144 Gaussian draws, with no unnecessary
target evaluations. Report importance ESS, Pareto k, largest weight, mode mass,
mean/variance of the same 68 continuous functionals and their IS delta-method
MCSE (provisional unless the weight gate passes). Weight gate: ESS >=1000,
Pareto k <0.7. Qualified reference comparisons follow separately; a weight gate
alone is not accuracy validation. Per-subject withheld-time log scores are
exploratory because these data were already exposed in the model preflight.

Bound each of two jobs to 300 seconds, 2 GiB RSS and 64 MiB output; one core/job.
Store proposal fits, diagnostics and summaries; regenerate draws from frozen
source, dependency hashes and seeds. Do not assert a mode-mass bound from
unreliable importance weights. Preserve any failed baseline.
