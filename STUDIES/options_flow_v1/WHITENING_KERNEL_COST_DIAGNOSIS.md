# Prospective diagnosis of the slow conditional-whitening candidate

Case05's long pre-report runtime is an observation, not an established kernel
failure mechanism. No recipe, kernel default, warmup schedule or live experiment
is changed by this document.

The usual default adaptation statistic is the coarsest leaf attempt's
`exp(-abs(delta_H))` (`DualAveragingAcceptance::CurrentCoarseEndpoint`,
`walnutpie.rs`), set at level zero in `macro_leaf_in_workspace` (`kernel.rs`).
Ordinary accepted refinement therefore does not conceal coarse-step error.
However, sampler-default warmup exhaustion is `AcceptUnlessDivergent`. If the
finest attempt still exceeds max_error but is accepted by that exhaustion rule,
the kernel replaces the adaptation value with `exp(-resolved_rise)`. An
energy-decreasing endpoint can then contribute a high signal despite expensive
refinement. Its actual frequency and relation to step inflation are unmeasured.

Eight refinement levels request 1,2,4,...,128 forward microsteps, potentially
255 across retries, then up to 127 reverse-coarsening steps per accepted leaf.
Tree expansion multiplies leaf work; expensive PyTensor target evaluations add
another factor. Compilation, refinement, tree depth and target cost must be
separated before claiming causality or choosing a kernel modification.

After a frozen diagnostic plan and validated tooling, measure:

* Phase timing: compile/parity, warmup, retained transitions, evaluation/output.
* Per-chain/per-transition step size and adaptation statistic, depth, leaves
  built/attempted, selected refinement level, refinement/reverse rejection counts.
* Per-phase forward/reverse callback counts and microsteps, built-level
  histograms, exhausted transitions, divergences and metric-update history.
* The exceptional finest-level adaptation override frequency. High selected
  refinement alone does not identify that override; existing research trace
  observations may be needed to associate the signal and energy condition.
* Fixed-position target-only PyTensor value/gradient cost in relevant coordinate
  regimes, separately from sampler work. Earlier JAX target timings do not
  establish PyTensor target cost.

`TransitionDiagnostics`, `WorkTotals` and `RunTelemetry` already contain much
of this. The prototype continuation bridge now serializes all nine transition
fields exposed by the ordinary Python adapter; its Rust chunk retains full
diagnostics/telemetry, including additional research details. Do not silently substitute a
shorter warmup: the window schedule depends on the configured discarded count.

Once validated, `session.adapt(); session.draw(1)` yields the exact first
retained prefix with the original warmup1000 and fixed lifetime retained
budget, but adapt still completes all warmup before responding. Internally a
research driver could call `ChainRun::advance(k)` at predetermined warmup
checkpoints while preserving config.discarded=1000 and the same RNG/cached state.
That is a static design, not an implemented public partial-warmup feature.
Any observer or recording overhead must be measured/labeled, and completed
request snapshots must not be described as live progress.
