# Fresh-data transport screen: frozen data design

Generate four new N=11 Poisson-GP count datasets on the original x grid. Fixed scenarios (rho,alpha)=(3,1),(3,2),(6,1),(6,2), seeds949400001..949400004. Draw eleven independent standard-normal latent coefficients, transform through the original verified compiled model's Cholesky representation, then draw Poisson counts with means exp(f) using the same RNG stream. Use the compiled transformation to avoid a differently rounded covariance factor. Keep every draw, including all-zero, extreme-count or difficult datasets; no rejection or seed replacement.

Save only N,x,k to inference data. Save generative truth separately for provenance, never for map training, tuning, proposal construction or posterior-reference selection. These are controlled synthetic stress cases, not real-data applications or prior-predictive calibration: hyperparameters are fixed deliberately, not drawn from the prior. Four cases do not establish broad generality.

Subsequent inference must use fresh pilot randomness and fresh map fits on each dataset, preserve failures, qualify all24 posterior quantities against independent references, and retain raw/affine native and conditional-importance baselines. The bounded map keeps K=4, ridge10 and400 training positions; no hyperparameter search on these datasets. Fit/setup/pilot costs remain part of the workflow. Data generation alone does not prove algorithm improvement or practical usefulness.

This protocol freezes data generation only. Reference, pilot and comparison budgets must be specified before sampling, with bounded workers and a full audit trail. Never use known generative truth as a posterior mean reference. No deployment/trading or goal-completion claim.
