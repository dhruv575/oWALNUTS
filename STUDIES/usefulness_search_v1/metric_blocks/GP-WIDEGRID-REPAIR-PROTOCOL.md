# Fresh-data wider-grid conditional importance repair

The original gp_newdata_importance01 remains failed (6/8 qualified). Its sparse
scenario had about 10% normalized weight below alpha=.1 from only 27-29 proposals.
Test exactly one motivated change: lower alpha grid endpoint from .1 to .0001.
Keep rho [.5,20], alpha upper 10, 41x41 cells, 95% grid/5% hyperprior mixture,
90% Gaussian/10% Student conditional proposal, Newton and all exact weights.
The wider grid trades resolution for low-alpha coverage; it need not succeed.
All four exposed datasets, two fresh seeds 950100001+2*scenario+rep, 16384
proposals/job. Rebuild grid and run density/gradient/proposal preflight each job.
Same 24-functional reference accuracy gates as the original: ESS>=400,k<.7,
mean and SD errors<=.1 reference SD/relative SD, combined MCSE z<=4, finite.
All eight must qualify; no seed exclusion, retries or extension. This is a
repair on exposed data, not unseen-data validation or WALNUTS superiority.
Run on existing AWS host, max eight BLAS1 workers; each 300s/2GiB/128MiB,
minimum 1GiB free disk, total bounded output ~1GiB worst case. Freeze and verify
bundle hashes before/after. Preserve setup counts, raw weights and failures.
Concurrent clocks cannot establish runtime superiority. No deployment/trading.
