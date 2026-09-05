# Preregistration — reverse_coarser_policy_v2 (WP39B-REVERSE-COARSER-POLICY-V2)

Frozen 2026-09-05 before the first cell. `protocol.json` carries the same
content in machine form; its hash is in `CHECKSUMS.sha256` and in
`summary.json`.

## Question

WP39 (`reverse_coarser_policy_v1`) found `ReverseCoarserPolicy::ZeroWeightBeyond`
exact but not faster (geomean 0.981x the shipped `StopOrbit`, 0.904x on the
four target models, `accel_gp` 0.61x) and identified why the comparison was
not the one intended: the shipped `CurrentCoarseEndpoint` statistic averages
`exp(-|dH|)` over every built leaf, and a zero-weight leaf is a built leaf,
so continuing past a failed leaf diluted its low value and dual averaging
installed a 3–30 % larger step on 16 of 17 models. The larger step
multiplied refined and failing leaves, which the policy then carried as
zero-weight tails (57 % of `accel_gp`'s built leaves).

Two questions, one study:

- **(a) Deployable.** `ZeroWeightBeyondAdaptSelected` (kernel `cfb1e93`)
  builds the same orbits but withholds the zero-weight tail from the step
  statistic, so the leaves that feed dual averaging are the weighted ones
  plus the failed leaf, the set `StopOrbit` averages over. Under the shipped
  adaptation, does it pay?
- **(b) Mechanism.** At an identical fixed step, does *not truncating the
  orbit* pay, as WP34's reading of the data predicted, separated from any
  step effect?

## Arms (`arms.rs`; everything else the shipped defaults)

| arm | policy | step |
|---|---|---|
| `stop` | `StopOrbit` (= `Tuning::default()`) | `Adaptation::default()` |
| `beyond-adapt` | `ZeroWeightBeyondAdaptSelected` | `Adaptation::default()` |
| `stop-fixed` | `StopOrbit` | fixed at the `stop` cell's median adapted step, same model and seed; mass adapted as the default does |
| `beyond-fixed` | `ZeroWeightBeyond` (bit-identical to `AdaptSelected` at a fixed step) | the same fixed step |

The fixed-step arms use `Adaptation::Custom(WarmupConfig::new(0.8)
.with_step_size_adaptation(false).with_mass_adaptation(true))` with the
default regularisation and exhaustion rule, so the warmup's mass windows
are unchanged and the initial step search is off.

## Protocol

As WP39: the `posteriordb_bench_v5` cell protocol on the 17 posteriors,
4 chains x 1,000/1,000, BridgeStan libraries reused from
`posteriordb_bench_v6`, ArviZ rank R-hat / bulk / tail ESS on the reference
parameters, gates rank R-hat <= 1.01, bulk and tail ESS >= 400, zero
sampling divergences. Statistic per cell: minimum over reference parameters
of bulk ESS per target call (warmup included), seed medians, ratios. Seeds
**92101, 92102, 92103** (grep-verified unused). Run order: models as listed;
`stop`, `beyond-adapt`, `stop-fixed`, `beyond-fixed`; seeds ascending;
sequential. 204 cells, then the funnel rows for `stop` and `beyond-adapt`
(6 rows). CmdStan cited from v5. Target models as in WP39: noncentered and
centered eight schools, `gp_pois_regr`, `accel_gp`; the other 13 are
controls.

## Predictions

- **P1.** `beyond-adapt`'s adapted `h` is within 0.95–1.05x of `stop`'s on
  every model (geomean within 0.98–1.02): the dilution was the whole cause
  of WP39's step rise.
- **P2.** `beyond-adapt` is 1.10–1.35x `stop` on the noncentered eight
  schools and `gp_pois_regr`, 0.95–1.10x on the controls, 0.8–1.2x on the
  centered eight schools and `accel_gp` (the zero-weight tail still costs
  gradients where the failure region is large); geomean over 17 in
  1.00–1.10, below C1.
- **P3.** `stop-fixed` is within 0.95–1.05x of `stop`: fixing the step at
  the adapted value costs nothing, so the fixed pair is a fair test.
- **P4.** `beyond-fixed` vs `stop-fixed`: the truncation hypothesis predicts
  >= 1.15x geomean on the four targets with controls within 0.95–1.05x; the
  alternative (the zero-weight tail costs what truncation saved) predicts
  0.9–1.1x on the targets with `accel_gp` below 1. Expected: the alternative
  on `accel_gp`, the hypothesis on the other three.
- **P5.** Funnel `|z| <= 2` on every seed for `stop` and `beyond-adapt`;
  `beyond-adapt` passes at least as many gates as `stop`.
- **Risk.** `accel_gp`: 58 % of `stop`'s transitions end in a
  reverse-coarser stop. At the same step `beyond-fixed` carries a large
  zero-weight tail; if leaves per orbit rise by more than 1/(1 − 0.58) the
  model loses even without the step confound.

## Decision rule (frozen)

**Deployable.** Flip the sampler default to `ZeroWeightBeyondAdaptSelected`
iff all of C1 geomean over 17 of `beyond-adapt`/`stop` >= **1.10**; C2 no
model < **0.90**; C3 `beyond-adapt` passes >= as many of the 51 gates as
`stop`; C4 funnel `|z| <= 2` on every seed for `beyond-adapt`; C5 geomean
over the four targets >= **1.15**. Otherwise `StopOrbit` stays the default.

**Mechanism (reported; no default consequence).** The truncation hypothesis
is supported iff M1 `beyond-fixed`/`stop-fixed` geomean over the four
targets >= **1.15** and M2 the controls' geomean is within **1.05x** of 1.

Report all cells; no reruns; failures are results; nothing tuned after
seeing results.
