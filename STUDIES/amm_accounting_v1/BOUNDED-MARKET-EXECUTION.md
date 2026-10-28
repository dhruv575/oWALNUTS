# Fixed bounded-market sampler execution

Apply BOUNDED-MARKET-DESIGN.md to the 24 frozen fixtures in preparation archive
f6b06c47d6262c15f550b1dd0b46f757b932dc0344b1f8f8549b25e04c9c5527. All 72 baseline
slots are complete before candidate sampling. Keep every origin and all three
caps; do not choose subsets or caps using new scores.

Cell j=3*fixture_index+cap_index, j=0..71, caps ordered .5/1/2. Reserve the full
integer interval 398141000..398142151. Cell base 398141000+16*j uses NUTS sample
seed=base, Stan data seed=base+1 and WALNUTS seed=base+4. Audit against other
seed-named inventories once before the first batch; preserve and bind the full
reservation for all later batches. Exclude no earlier external campaign. Engine
internal RNG derivations remain outside the scalar collision audit.

Run six fixed batches, each containing twelve consecutive cells, in order.
Within each batch dynamically allocate disjoint four-core groups, at most four
cells concurrently, releasing each group only after its process tree drains.
Both methods must be attempted in every cell; a method failure is recorded and
must not suppress the other method. It is not replaced by another seed.

NUTS: four chains, 2,000 warmup, 4,000 retained, target_accept .9,maxdepth10,
no low-rank or transform adaptation, exact rescaled Stan target. WALNUTS: the
same counts, admitted direct log-space callback, and the settings frozen in
BOUNDED-LOGSPACE-WALNUTS-PLAN.md. Both start at physical mu=2log(.005),sigma=.2,
beta=0,z=0. No tuning extensions or result-dependent initialization.

Save every retained internal coordinate, available NUTS warmup coordinates,
warmup/retained diagnostic-event arrays, runtime/source metadata, full physical
coordinate summaries, joint predictive components and per-draw predictive
functionals. Generated full h paths need not be stored redundantly: they are
exactly reconstructible from mu,log_sigma,z and fixed rho. WALNUTS warmup
positions are not exposed by the current API and must not be claimed preserved.
Record all thrown errors and warnings with their method/cell identity.

Compute fixed GH64/128 next-observation scores with a 60-second per-method scoring
deadline. Preserve integration failures. Record ArviZ Rhat/bulk/tail ESS for
stabilized density and PIT and delta-method MCSE(log mean density), plus physical
coordinate diagnostics. Qualified comparisons require both methods' physical and
functional Rhat<=1.01,bulk/tail ESS>=400 and zero retained divergences/depth hits.
Report unqualified scores separately with explicit counts; do not silently
filter them into a favorable headline. Keep all 72 cells in the accounting.

Per-cell bounds: 900seconds,5GiB process-tree RSS,192MiB output. Per-batch bounds:
2,760seconds,22GiB RSS,2.5GiB output. Require 3.5GiB free disk before each batch.
Sampled disk caps permit overshoot; monitor actual progress and free space.
Archive completed batches and verify exact-version S3 restores before reclaiming
their remote traces. Never delete active inputs or unverified evidence. A disk
admission failure delays later fixed batches; it does not reduce their scope.

Pre-launch implementation detail: each method runs in its own monitored child
process, limited to400seconds,4GiB RSS and96MiB output within the cell's budget.
Drain a failed/timed-out method before attempting the other method on the same
four-core group. This prevents the first method from consuming the entire cell
budget and silently suppressing its comparator. Record both method receipts;
resource failures remain failed slots, not replacement attempts.

Report setup, sampling, serialization/diagnostic and prediction costs separately.
This screen is not precision-matched performance evidence. Compare each method
to all three frozen baselines and preserve the exact model/inference-score
decomposition. Report monthly and per-origin results descriptively with missing
denominators; 24 development origins do not support a general calibration or
profitability claim. Untouched confirmation and economic evaluation remain open.
