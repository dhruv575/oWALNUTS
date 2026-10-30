# Pinned native Fisher-HMC baseline qualification

Prepare a separate local environment with nutpie0.16.11, whose CPython3.14 Linux
wheel SHA256 is recorded in local_recovery/nutpie_baseline/DOWNLOAD.json. Preserve
the existing validation environment. Run only after the current timed queue and
numerical preflight are terminal. Pin scientific dependencies to the qualified
local environment where compatible; preserve any dependency conflict explicitly.

First qualify the native BridgeStan bridge using the already archive-verified
sblrc model library/data/source. Construct the pinned CompiledStanModel wrapper
around that library, matching the constructor in the inspected wheel. No source
model change, recompilation, alternate likelihood or dropped prior. Verify its
dimension and hash all model/data/source/library inputs.

Exercise three maintained native NUTS adaptation modes: draw_diag, diag and
low_rank. For the low-rank mode use the published benchmark cutoff2 and gamma1e-5,
rather than silently taking the package's documented cutoff100. All arms use
four chains/cores,1100 warmup,2000 retained draws,target_accept.8,maxdepth10,
seed929800001, default initialization around zero. These are native full schedules,
not the staged fixed metrics; starts and random streams are not exactly matched
to WALNUTS. The1100 transient transitions correspond to the candidate's250 warmup
+100 discarded pilot draws+750 second-stage warmup. Charge all actual runtime.

Require the unchanged reference gates in every arm: rankRhat<=1.01,
bulk/tailESS>=400, retained divergences0, mean error<=4.5 combinedMCSE and.1refSD,
relativeSDerror<=.1. Save unconstrained draws and warmup/retained diagnostics.
Counted integrator steps are NOT a complete target-call count; do not label them
as such or use them for target-call superiority claims. This preflight is backend
qualification, not a performance win or independent application validation.

Each full native sampling invocation180s/2GiB/64MiB, whole job monitored, BLAS1,
process-group drain verified. Preserve failures and sources; locally archive and
read back every member. Only after qualification freeze a separate six-target
comparison including published-schedule controls and complete measured runtime.
Do not retroactively add this comparator to the already frozen local gate.
