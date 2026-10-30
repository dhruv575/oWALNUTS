# Terminal audit and next mechanism

All20 new cells completed under their resource limits. No factor qualifies for
fresh replication under the frozen rule. Multiplier1 remains the best aggregate
of the five exposed factors, with full-workflow ESS/gradient ratio .7958; other
factors0.5/2/4/8 give .6621/.4955/.3375/.05384. Do not expand this ladder.

The first analysis attempt required exact equality between requested numeric
settings and Rust JSON output. It failed. Its source is preserved as
step_ladder01/ANALYZER-EXACT-AUDIT.py. Across every setting in all20 cells,
requested step multiplication was exact; maximum output discrepancy was one
float64 ULP for steps and one ULP for mass entries. The corrected audit permits
at most one ULP only for the Rust JSON round-trip. Original-versus-new input
masses, starts, seeds and requested step factors still require exact equality.
No sampling, accuracy threshold, selection criterion or data was changed.
This administrative amendment does not turn the negative result positive.

Next inspect duplicate target evaluations as a distinct mechanism, not another
step-size adjustment. Existing cached initial-evaluation support is already
present and must not be claimed as a new improvement. An observation-only,
memory-bounded exact-coordinate audit should count repeated requests and verify
identical results on deterministic targets. It must leave draws and evaluation
order unchanged and report any coverage truncation. Only a substantial measured
opportunity would justify a separate cache implementation and parity tests.
Approximate-coordinate reuse is outside this mechanism: it changes gradients.
This next idea is untested, not evidence of an improvement or novelty.
