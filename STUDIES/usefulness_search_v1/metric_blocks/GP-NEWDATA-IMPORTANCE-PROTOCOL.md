# Fresh-data conditional importance comparison

Use all four frozen gp_fresh_data01 datasets and their qualified references.
No change to the conditional_v3 proposal, grid bounds, Newton tolerances,
defensive mixtures or exact importance weights. Rebuild the 1681-cell grid and
run the original density/gradient/proposal equivalence preflight for each job.
Two independent proposal seeds per dataset: 950000001+2*scenario+rep.
Each job draws 16384 proposals. Require finite weighted quantities, importance
ESS >=400, Pareto k<.7, max mean error <=.1 reference SD, relative SD error <=.1,
and combined-reference MCSE z<=4 across all 24 quantities. Keep all failures;
no retries, extensions, dataset exclusion or tuning. All eight must qualify.
Setup counts, proposal counts and raw weights are preserved separately; no
comparison of importance ESS with MCMC ESS and no runtime claim from concurrent
clocks. This is accuracy evidence, not application utility or uniqueness.
Two workers maximum, BLAS1, 300s/2GiB/128MiB per job; 2GiB local free space.
Do not use TRUTH.json for inference. Sources and inputs hashed before launch.
