# Fixed independent long-window panel

Use exactly the four deterministic fixtures in PRICE-CELL-LONG-PLAN.md, in the
same order, with four independent slice/Gibbs chains per fixture. Seeds are
398126000 through 398126015, mapping job=4*fixture+chain; audit before launch.
Each chain starts with standardized core zero and price-cell midpoints, runs
1,000 warmup sweeps and retains 4,000 sweeps. Use the already T1-validated full
core ellipse and sequential physical-price conditional update without tuning.
Existing per-update attempt caps remain unchanged. Preserve all draws and work.

Sixteen one-core chains run concurrently on separate cores. Per-chain bounds:
600 seconds, 1 GiB process-tree RSS, 64 MiB output. Outer bounds: 660 seconds,
18 GiB RSS, 1.25 GiB output. Require 3 GiB free disk and bind sources/runtime.
Preserve incomplete chains and no posterior comparison for a fixture lacking
all four chains. Do not extend a failed chain or substitute a new seed.

Compare all coordinates with the preserved four-chain NUTS traces from the
same fixtures. Report separate rank Rhat, bulk/tail ESS and mean MCSE for each
method, plus combined-standard-error mean discrepancies. Diagnostics gate:
Rhat<=1.01 and bulk/tail ESS>=400 everywhere. Flag abs(z)>4 descriptively;
with hundreds of coordinates this is not a calibrated familywise hypothesis
test. Failed diagnostics preclude claiming a validated reference even when
means agree. No timing superiority claim: implementations and update counts
are not matched. Agreement would support these fixtures only, not general
posterior fidelity, calibration or market-model validity.
