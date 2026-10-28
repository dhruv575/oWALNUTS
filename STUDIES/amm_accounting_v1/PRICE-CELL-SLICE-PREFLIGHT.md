# Independent transition preflight

The physical-price rejection update and Gaussian-prior elliptical slice core
are implemented separately from Stan/autodiff. Deterministic tests compare
conditional likelihood ratios, neighboring-return indexing, stationary initial
state, prior scaling and the physical-to-logistic Jacobian identity. Attempt
caps abort instead of silently emitting a truncated update. These tests do not
establish finite-run mixing or independent posterior agreement.

Next fixed check: T1 cell [-.0005,.0005), initial=0, four independent chains,
1,000 warmup sweeps and 4,000 retained sweeps. Start standardized core at zero
and physical price at the cell midpoint. Seeds 398125000 through 398125003,
subject to the existing inventory audit. Each sweep performs a full core
elliptical update then one physical-price Gibbs sweep. Caps are 1,000 slice
proposals per update and 10,000 rejection proposals per price coordinate.

Compare all five physical/logistic coordinates with the already preserved
74,311-draw rejection reference. Use the same diagnostic gates (rank Rhat<=1.01,
bulk/tail ESS>=400) and flag absolute mean discrepancy above four combined
standard errors. Report proposal counts, all failed slots and wall time. This
is one fixed correctness fixture, not a performance comparison or SBC.

Bound each chain to 300 seconds, 1 GiB RSS and 32 MiB output, four one-core
chains concurrently; outer limits 360 seconds, 6 GiB RSS and 256 MiB output.
Bind sources and runtime before launch. No long-window campaign is admitted
until this independent transition passes the existing reference check.
