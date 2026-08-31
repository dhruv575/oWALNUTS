# Preregistration: outer-selection-bps-vs-multinomial-v1

Frozen 2026-08-31 before execution. Normative details are in `protocol.json`.

**Hypothesis (from the clean-room study).** On identical trajectories,
stopping, metric, and adaptation, the biased-progressive outer join
`min(1, W_new/W_old)` lowers lag-one autocorrelation and raises location bulk
ESS per target call relative to the exact normalized multinomial outer join
`W_new/(W_old+W_new)`, without degrading health, tail ESS, or
squared-functional ESS.

**Design.** Two arms differing only in `OuterOrbitSelection`. Exact v38
noncentered Eight Schools density, four frozen unconstrained starts, 4
sequential chains, 1,000 discarded + 1,000 retained, initial step 0.3,
depth 8, refinement levels 8, `max_error` 1.0, target acceptance 0.95 with
dual-averaged step and Welford diagonal mass. Fresh seeds 82001–82003.

**Primary estimand.** Geometric mean over the six unsquared functionals of the
BPS/multinomial ratio of bulk ESS per retained target call, each arm's
per-functional value first geometric-averaged over seeds.

**Advancement.** Ratio ≥ 1.10 and all safety gates (zero divergences/invalid
evaluations; depth-cap rate not increased by more than 0.5 points; minimum
tail-ESS/call ratio ≥ 0.95; minimum squared-functional bulk-ESS/call ratio
≥ 0.95).

**Mechanism checks.** Self-retention, lag-1 ACF, depth/leaf distributions,
E-BFMI.

**Because BPS is already the default**, this is a reverse ablation: it
measures what removing the mechanism costs. It cannot justify a source change
unless the multinomial arm is materially better; in that case the finding is
reported as a finding against the default, not acted on here.
