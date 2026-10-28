# Fixed nine-case bounded-target WALNUTS panel

Use exactly the nine fixtures in BOUNDED-SCALE-MULTI-PLAN.md: caps .5/1/2 crossed
with T=12 all-zero, T=250 exactly-two-zero, and T=250 distinct sinusoidal values.
No data changes or case omission. All fits use the exact rescaled beta coordinate
with its original physical prior and Jacobian. Require the preserved 72-case
native parity report and matching source hashes before launch.

Four chains, 2,000 warmup, 4,000 retained, initial physical mu=2log(.005),sigma=.2,
beta=0,z=0. WALNUTS settings match the earlier finite-cell panel: step_size=.5,
max_depth10,min_micro_steps1,max_refinement_levels8,max_error1,divergence1000,
momentum_sum U-turn,stop exhaustion; target_accept .9, adapted step/mass, Stan
metric regularization and trapped-chain restart. Keep warmup and retained
diagnostic phases separate. Sample seed 398139000+16*j, reserve all 144 integers,
audit scalar seed inventories before launch; opaque internal RNG streams are
outside that collision audit.

Up to four fits, each on a dynamically assigned disjoint four-core group. Return
a group only after its process tree drains. Per-fit 900seconds,4GiB RSS,512MiB
output; outer 2760seconds,18GiB RSS,3GiB output; require 4GiB free disk. Preserve
all retained internal draws, full warmup/retained event arrays, sampler metadata,
source/runtime bindings and resource logs. Do not claim retained-draw arrays
contain warmup positions. No replacement seeds or tuning extensions on failure.

Report all physical mu,log_sigma,beta,z diagnostics and the extra b diagnostic;
Rhat<=1.01,bulk/tail ESS>=400, retained divergences and depth hits. Compare means
and combined MCSE against frozen references: the original six T=250 NUTS/slice
fits, and rescaled NUTS plus centered-slice for the three all-zero cases. Verify
reference hashes before analysis. Failed references cannot qualify a comparison.
Costs include separately reported native setup and sampling; computational
advantage needs precision matching, not just these elapsed times. This panel
does not select a prior cap or establish market prediction, decisions or profit.
