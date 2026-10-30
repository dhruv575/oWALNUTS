# Scale mismatch identified; exposed repair passes its mechanism check

The previous fresh hybrid continuation gate remains FAILED. This follow-up uses
saved evidence for hypothesis development and three exposed repairs, not a new
independent validation. No previous sources, outputs or thresholds were changed.

## Geometry and established criterion

The96-cell audit completed in32.34 seconds, peak RSS53.5MB, no new target calls.
All384 held-out-chain folds produced criteria. Bales et al.(2019), Eq13, was
implemented with four local Hessian snapshots and leave-one-chain-out splits;
four Gaussian/invariance/invalid-input tests pass. This is not the paper's full
warmup schedule or candidate set. [Original criterion and implementation details](https://arxiv.org/html/1905.11916v3).

For the three regression fallbacks, v4 covariance condition proxies relative to
reference unconstrained covariance are13.62,2.10,5.35. Fisher's are1.61,1.53,1.64.
Keeping the same stable block shape while using Fisher-derived diagonal scales
reduces the proxies to1.27,1.19,1.08. In the worst cell, v4 coefficient variances
are roughly14x reference while log-noise variance is1.07x; the relative mismatch
is more important than overall scale, which step-size adaptation can absorb.
These proxies alone are not performance evidence.

The held-out criterion prefers Fisher in all16 GP cases, including the three
previous Fisher accuracy failures. It also prefers Fisher in15/16 eight-schools
cases, where every method fails. It therefore cannot replace the reliability
gate on this evidence. Fixed diagonal/empirical candidate scores are not scores
for adaptive automatic/dense sampling. No sampler gain is credited to new choices.

## Three exposed sampler repairs

Same saved pilot states and second-stage seeds,750 warmup+2000 draws. Only scale
inputs to unchanged full-shape reconstruction change. All original pilot, scores,
probes and new sampler target calls are charged; original controls are reused.

| Seed | Accuracy | ESS/calls vs Fisher | vs prior hybrid |
|---|---|---:|---:|
| 929300005 | pass | 1.0445 | 7.1097 |
| 929300008 | pass | 1.1278 | 1.6738 |
| 929300009 | pass | 1.0534 | 3.1004 |

All three jobs drain; schedule, binary, cost and durable-file hashes verify.
All three ratios exceed the frozen .90 mechanism floor, so this exposed repair
check passes. It neither replaces the failed16-seed gate nor establishes general
usefulness, application value or novelty. Fresh validation must retain regression
and all strong comparators; do not drop difficult targets or change thresholds.

## Resource and timing limits

Sampler job folders are monitored in full. The audit harness accidentally sampled
only its monitor subdirectory for output bytes. Its complete final worker-root
size is independently audited below64MiB; time/RSS limits and group drain hold.
Preserve this enforcement-scope limitation. Future audit harnesses must monitor
the whole worker root. No end-to-end speed claim uses the component timers.

Next freeze a revised policy that changes only the scale reconstruction when the
score gate declines Fisher but stable blocks qualify. Test new seeds against the
old hybrid, v4, unconditional Fisher, dense and auto. Execute each policy's own
fitting work independently, recording invocation-through-output elapsed time and
separately reporting shared pilot/diagnostic scope. Keep the same accuracy and
comparative efficiency requirements and preserve any new failures.
