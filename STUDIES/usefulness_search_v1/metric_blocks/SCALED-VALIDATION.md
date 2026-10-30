# Fresh scale-corrected policy validation

Frozen before fresh execution. Six targets unchanged from HYBRID-VALIDATION.md.
Fresh seeds929500001..929500016; eight immutable2-seed chunks. Shared discarded
pilot250 warmup+100 draws, four uniform[-2,2] starts; every second stage750 warmup
+2000 draws, same pilot endpoints and seed+100000. Six arms: scaled candidate,
old hybrid, v4, unconditional Fisher, adaptive dense, automatic.
Within each cell, rotate this six-arm order by the fresh seed index modulo6;
the rotation is fixed before results and does not use target names or outcomes.

Candidate changes only old hybrid's rejected-Fisher stable-block fallback: if
Fisher fit is numerically valid, reconstruct the same blocks with Fisher diagonal
scales, including unselected-coordinate scales. Require unchanged block selection
and safe SPD installation, otherwise retain old v4 fallback. The cross-chain gate,
block discovery, Fisher estimator, thresholds and automatic fallback stay fixed.
No model names enter policy. All old failed gates remain failed historical results.

Every arm executes its own required fitting work; no fitted scores/probes/metrics
are shared between arms. Fisher charges400 scores, v4 charges64d probes, both
hybrids charge400+64d. All arms charge pilot and sampler calls. Adaptive controls
perform no extra fitting. Whole policy invocation (Python startup, model loading,
fitting, sampler invocation and output) is measured by the process supervisor.
Total operational sampler time is that elapsed time plus separately measured
shared pilot invocation. Common reference/ArviZ diagnostics and controller IO
are explicitly excluded. Report this scope, process-monitor overhead and the
expensive80-digit solver; no claim against an optimized Fisher implementation.

Same reference/accuracy gates: rankRhat<=1.01, bulk/tailESS>=400, retaineddiv0,
means within4.5 combinedMCSE and .1 referenceSD, relativeSDerror<=.1.
Continuation requires no paired candidate accuracy loss vs auto,v4 or old hybrid;
at least one ARMA/GARCH/GP/eight-schools target with all16 candidate/auto/v4 cells
qualified and geometric ESS/total-call ratios>=1.2 vs both auto and v4,95% paired
bootstrap lower bounds>1; no fully qualified candidate/Fisher target ratio<.90.
Use10000 paired bootstrap replicates, seed929599999. Exploratory per-target
intervals, not simultaneous inference. Failed arms earn no ratio credit. Report
old-hybrid contrasts and operational times even if unfavorable. Passing this
continuation gate is not proof of general usefulness, novelty or application.

Before fresh work, port parity on exposed seed929300005: old hybrid must match
its archived non-timing sampler output, scaled must match the exposed repair.
Check actual gradient counters against charged calls. No fresh runs until parity
passes; preserve failures. Each pilot/policy worker180s/2GiB/64MiB with full job
folder monitoring and process-group drain; root floor1GiB. Archive, exact-version
restore and verify each chunk before reclaiming redundant results and admitting
the next. Source/target hashes fixed across chunks. No threshold changes or reruns.
