# Neal funnel dual-averaging diagnostic v3

## Evidence-backed hypotheses

V2 falsified 8,000 warmup plus repeated initial-step search: robust/base
dispersed ESS-per-call ratios were 1.13, 0.90, and 0.28, while robust
zero/dispersed sensitivity ratios were 0.23, 0.38, and 4.38. Corrected
divergence and refinement health were clean, so this is an adaptation
stability problem rather than insufficient refinement capacity.

The implementation uses standard dual-averaging constants
`gamma=0.05`, `t0=10`, and `kappa=0.75`. Initial construction centers
`mu=log(10*step)`, matching Stan and NumPyro. After every installed metric,
however, `DualAveraging::restart` centers `mu=log(step)`. NumPyro instead
finds a reasonable step under the new metric and initializes its dual state at
`log(10*step)`; Stan likewise resets dual state around a nominal step after
slow windows. The factor-of-ten restart-center discrepancy is the primary,
general-purpose hypothesis.

The adaptation input is also nonstandard. oWALNUTS averages
`adaptation_value` across traced leaf events. Each value is computed from the
coarsest level's absolute endpoint Hamiltonian error, including leaves that
later refine or reject. Standard HMC adaptation uses a trajectory proposal
acceptance probability. Rejection-conditioned or high-variance values can
drive chain-specific dual updates even when accepted trajectories are healthy.

Finally, diagonal metrics are estimated independently by chain. Funnel chains
can occupy different scale regions during a slow window, producing different
mass estimates and therefore different stable macro steps. Window-boundary
restarts may amplify this coupling.

## Minimum experiment

A 2x2 design crosses only:

1. restart centering multiplier 1 versus 10;
2. adaptive diagonal metric versus fixed identity metric.

This is the smallest design that identifies the centering effect both with and
without metric changes, provides no-window controls for boundary effects, and
measures whether chain-specific metrics increase step dispersion. Acceptance
noise is measured by two statistics on the same transitions, avoiding another
behavioral arm.

All other controls remain at the healthy v1/v2 values: dispersed starts,
target acceptance 0.90, 2,000 warmup, refinement 12, `max_error=0.5`,
minimum microsteps 1, depth 10, and 10,000 retained draws.

## Implemented prerequisite (still not authorization)

Shared code now exposes warmup-only typed telemetry for dual state,
instantaneous/averaged step, window/restart events, metric vectors, and both
adaptation-statistic definitions. It must also provide research-only,
checksum-recorded controls for restart multiplier `{1,10}` and mass adaptation
on/off. The production default remains multiplier 1.

Instrumentation is tested for:

- bitwise sample/RNG/work identity when enabled versus disabled;
- exact checkpoint indices and no retained-phase allocation;
- dual-state recurrence against a hand-computed sequence;
- restart multiplier 1 reproducing current behavior;
- multiplier 10 matching a fresh standard dual initialization;
- missing-statistic and reverse/refinement conditioning;
- diagonal metric checkpoint identity;
- sequential/parallel identity and target-budget accounting.

No claim that multiplier 1 is defective is made before this diagnostic. The
code discrepancy is a falsifiable mechanism hypothesis.
