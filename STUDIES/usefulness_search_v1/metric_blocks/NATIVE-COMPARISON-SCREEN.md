# Native comparison screen

Frozen before execution. Use all six existing reference-backed targets and new
seeds940600001--940600004. Four immutable one-seed chunks. This is an exposed
model-family screen, not confirmatory application evidence or a goal-completion
criterion. Preserve all target/arm failures; no score-threshold retuning.

Seven arms: WALNUTS automatic; original scaled policy with full-sample80-digit
Fisher fitting; scaled policy with qualified QR/small-matrix80-digit fitting;
unconditional fixed Fisher with the QR solver; native nutpie draw_diag, diag,
low_rank. Native low_rank uses cutoff2,gamma1e-5. Other policy and gate choices
are unchanged. All engines use the same qualified threaded target library;
native calls pass through the verified counting wrapper of that library.

WALNUTS arms share a250-warmup+100-draw discarded pilot from four uniform[-2,2]
unconstrained starts. Their second stages use the shared endpoints,750 warmup,
2000 draws, seed+100000. Native arms use their full1100-warmup+2000-draw schedule,
four chains/cores, target_accept.8,maxdepth10, native default initialization and
the base seed. Transient transition counts match, but starts, random streams,
adaptation schedules and kernels do not. These are complete workflow controls,
not a same-kernel causal experiment. Rotate seven-arm order by(seed_index+
target_index)mod7, fixed in advance.

Primary costs: all attempted gradient evaluations, including pilot, fitting,
initialization and warmup. Record native value/Hessian/HVP counts separately;
require zero non-gradient counts before calling the denominator gradient-only.
Use the verified C-ABI counter for native runs and metric fitting; retain the
sampler's audited target counter for WALNUTS subprocesses. No step-count proxy.

Run one complete cell per supervised worker. Import dependencies before arm
timers. Record post-import operation time through unconstrained draws ready,
including model construction, fitting, sampler/API conversion and the current
WALNUTS subprocess/file transport. Charge the shared pilot's full operation time
to each WALNUTS arm. Exclude common reference diagnostics, final evidence writes
and archives from arm clocks; report full cell supervision separately. Do not
infer per-arm cold-start times from a shared worker, or kernel speed from these
implementation-level times. Preserve component timing and arm order.

Use unchanged reference gates: rankRhat<=1.01,bulk/tailESS>=400,retaineddiv0,
means within4.5 combinedMCSE and.1refSD, relativeSDerror<=.1. Report passes and
paired ESS/gradient and ESS/post-import-second ratios only when all four paired
cells qualify. Report all controls, including unfavorable results. Exploratory
paired bootstrap10000 replicates, seed940699999; no simultaneous inference.

A promising efficiency screen needs a non-Gaussian target (ARMA,GARCH,GP-Poisson,
centered eight-schools) with four accurate fast-scaled/automatic cells and
geometric gains>=1.2 in BOTH primary cost measures versus automatic and every
fully-qualified native arm; at least one native arm must fully qualify. Also
require no paired fast-scaled accuracy loss to automatic across the full screen.
Failed native arms are not infinite-efficiency wins. Any signal needs a new
larger replication and new model-family/application tests, including appropriate
approximation/model-specific controls. No signal means do not rescue this policy
by lowering thresholds; use the results to choose a different research direction.

Before fresh runs, generic wrapper qualification on all six models must show
correct explicit gradient counts and short native retained-trajectory parity
with/without instrumentation. Use exposed qualification seed940500001,200warmup
+100draws, all three native modes. Those short runs are not accuracy evidence.
Workers180s/2GiB/64MiB, one at a time, BLAS1; both workspace and build-disk floors
1GiB. Preserve and locally archive/read-back each chunk before its successor.
