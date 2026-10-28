# Live retarget equivalence check

Three fixed cases (T=2,12,250; four chains each) passed exact equality of
16 post-retarget draws per chain, all returned transition diagnostics and
target-call counts against a newly constructed session at the same remapped
state and matching effective chain seeds. The resident session first took
eight transitions on the old target, then retargeted without resetting its
call counter. Caller cell arrays were mutated after retarget; the fresh
control used independently compiled correct cells. Call-index and seed
assertions passed. Target calls were 1,988, 1,988 and 1,779 respectively.

The seed inventory audit records intentional paired seed reuse for exact
regression equality. This is not independent Monte Carlo replication. Tiny
unadapted trajectories with bounded depth do not establish posterior fidelity.
Fixed positive beta mass and step sizes are test settings, not fitted metrics.

The first launch failed during import, before constructing output or sampling,
because resource_monitor.py was absent from the uploaded bundle. Supplying
that transitive dependency allowed the unchanged checker to run. The complete
final source bundle and all draw/diagnostic arrays are preserved here; the
full downloaded archive and source hashes were verified. The successful
command ran with a 120-second timeout, four-core affinity and 4 GiB address
space cap; elapsed time including seed inventory audit was 22.874 seconds.

Next gate: a fixed warm-refresh budget versus independently seeded cold
reference fits on changed windows, checking all coordinates and predictive
functionals. Initial-price conditioning must be declared identically for both
routes. Market observation validity and economic evidence remain unestablished.
