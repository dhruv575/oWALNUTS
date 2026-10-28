# First shifted-window posterior comparison

Four fixed fixtures retain the existing order T=12/250, width=.001/.00001.
Shift each old cell array one place and append the nearest-width cell around
.003*sin(.17*T)+.001*sin(.61*T). Preserve the coordinate origin and set the
new initial price to exactly zero for all chains and both methods. This is a
declared synthetic conditioning experiment, not a model of historical rolling
boundary prices. No market data or predictive/economic claim is admitted.

Warm WALNUTS starts from each saved static fit's last draws, final diagonal
masses and step sizes, remapped by price_cell_remap.shift. Verify those inputs
against a copied frozen manifest. Use 4 chains, 4,000 refresh draws, no discard
or new adaptation, and the original tuning (.5 initial setting, depth10,
refinement8, max_error1, momentum_sum U-turn, stop exhaustion). All warm draws
count, including initial transient bias. Cold NUTS uses 4 chains, 2,000 warmup,
4,000 retained, target_accept=.9, depth10, no low-rank or transform adaptation,
and the previously declared central initialization. Save full cold warmup.

For fixture j, warm base seed=398131000+16*j (four explicit chain seeds),
cold seed=base+8, model seed=base+9. Reserve/audit the whole 64-integer interval;
opaque internal engine streams remain outside the inventory audit scope.
Each four-core job executes warm then cold sequentially; four disjoint jobs
run concurrently. Bound each to 600s/4GiB/256MiB and the outer campaign to
660s/18GiB/1.25GiB with 3GiB free disk admission. No replacement or budget
extension after viewing results. Preserve incomplete method pairs.

Report all-coordinate Rhat<=1.01, bulk/tail ESS>=400, retained divergences,
depth saturation, combined-MCSE mean discrepancies and actual costs. A fixed
4,000-draw budget is initial geometry assessment, not evidence of a useful
low-latency update. Equal draw counts are not equal accuracy or cost. Further
budget and predictive-functional studies need a separate declared design.
