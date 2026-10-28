# Synthetic latent-increment CDF comparison

Post-hoc analysis of all saved warm/cold draws evaluated next latent-increment
CDFs at -.005, 0 and .005, integrating the next Gaussian volatility innovation.
Every functional passed rank Rhat<=1.01 and bulk/tail ESS>=400 for both methods.
Maximum absolute mean discrepancies in combined MCSE units were 1.257,1.753,
1.731,2.019 across fixed fixture order. No discrepancy exceeded four.

Every draw was evaluated using 64- and 128-node Gauss-Hermite integration.
The largest difference was 2.947e-10. For each fixture/method/threshold, the
draw with the largest difference was also evaluated by independent adaptive
quadrature; maximum discrepancy from 128-node integration was 3.020e-14.
This is a numerical stability check on the saved draws, not a global error
bound. All 24 numerical checks passed the declared 1e-6 tolerance.

The analysis reloaded and hash-checked all eight full traces, checked shapes
and finiteness, and reproduced every saved coordinate summary to 1e-11
absolute/relative tolerance. This uses the same ArviZ implementation, so it is
reproduction of the analysis, not independent validation of the diagnostics.
The source-bound complete analysis archive was downloaded and hash-verified.
Elapsed time was 27.482 seconds with a 300-second timeout, four-core affinity,
single-threaded numerical libraries and a 4 GiB address-space cap.

These are latent-return probabilities conditional on a synthetic target.
They do not score future observed cells or establish empirical calibration,
predictive superiority, decision value, profitability, or useful update speed.
