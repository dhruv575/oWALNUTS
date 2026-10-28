# Independent blocked-slice T1 admission

Three caps .5,1,2, y=0, rho=.95; four one-core chains per cap, fixed seeds
398134000 through 398134011 in cap-major order. Start every standardized
Gaussian-prior coordinate at zero. Run 1,000 warmup sweeps and 4,000 retained
sweeps; each sweep updates three scalar hyperparameters and then latent blocks
of size at most 16. In T1 all four blocks are scalar. Slice proposals have a
fixed 1,000-attempt cap; a failure aborts and is preserved, never a self-loop.

The scale-prior coordinate is transformed using the normalized truncated-normal
inverse CDF, evaluated in log-probability space. Gaussian prior coordinates
enable elliptical slice sampling without gradients. Save physical mu,
log_sigma,beta,z and all warmup/retained draws and proposal work. A finite-
precision inverse CDF can round to the cap at extreme inputs; no clipping is
introduced. This limitation must remain visible, particularly in tail studies.

Bound each chain to 600 seconds/1GiB/64MiB output and the campaign to
660 seconds/18GiB/1.25GiB. Require 3GiB free disk. Compare all coordinates to
the already frozen independent rejection reference, converting its eta to
log_sigma. Use Rhat<=1.01, bulk/tail ESS>=400 and descriptive four-combined-MCSE
mean flags. Preserve every chain/coordinate failure and avoid resampling.
This is admission for a multi-observation control, not repeated-tie validation.
