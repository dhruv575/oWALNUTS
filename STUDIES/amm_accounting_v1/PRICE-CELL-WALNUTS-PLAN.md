# Fixed WALNUTS candidate-target sampling panel

This is the first sampling admission of the native price-cell callback, after
12 density/gradient parity fixtures passed. Use the four deterministic fixtures
from PRICE-CELL-LONG-PLAN.md in their existing order. Historical observation
semantics remain unresolved; these are synthetic stress cases, not market fits.

Four chains per fit, 2,000 warmup and 4,000 retained draws per chain. Explicit
four-chain center arrays use mu=2 log(.005), log_sigma=log(.2), beta=z=u=0.
WALNUTS settings: step_size=.5, max_depth=10, min_micro_steps=1,
max_refinement_levels=8, max_error=1, divergence_threshold=1000,
u_turn_rule=momentum_sum, exhaustion_rule=stop; target_accept=.9, adaptive
diagonal mass and step size, Stan metric regularization, trapped-chain restart
enabled. These are fixed before results. Seeds 398129000 through 398129003;
audit seed-named inventories and record the limitation concerning opaque
internal streams. Preserve actual chain seeds and all returned diagnostics.

Use disjoint four-core groups, per-fit 600 seconds/4 GiB RSS/256 MiB output,
outer 660 seconds/18 GiB RSS/1.25 GiB output, with 3 GiB free disk admission.
Save complete retained draws, config, chain diagnostics, warnings, native
binary and Python facade hashes, fixture and callback snapshot hashes. The
sample API does not provide complete warmup position traces; preserve its
warmup diagnostics and final adaptation metadata and declare this limitation.

Evaluate every coordinate using rank Rhat<=1.01 and bulk/tail ESS>=400, requiring
finite diagnostics and zero divergences. Report depth saturation separately.
Preserve failed slots and bounded terminations, without replacement seeds.
Compare to existing NUTS and blocked-slice results afterward, retaining the
short narrow-cell slice diagnostic failure. Equal iterations do not establish
equal precision or fair speed advantage. This does not establish predictive
accuracy, decision value, profitability, or warm retarget correctness.
