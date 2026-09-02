# funnel_defaults_v1 — preregistration (WP28)

Frozen 2026-09-02 before the first evidence cell. Kernel revision
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`, paper adaptation
`walnutpie-paper-adaptation-kquantile-gamma-v4`, `Sampler` at its 0.2.0
defaults (`Tuning::default()`: `h0 = 0.5`, depth 10, four refinement levels,
`delta = 1`; `Adaptation::DualAveraging { 0.8 }` with the WP24 warmup
exhaustion rule; adapted diagonal metric; cached initial evaluation;
worst-case admission).

## 1. Question

The README's headline funnel claim (tail mass 0.0474 vs exact 0.0478) is
measured at the *paper's* tuning (`h = 0.36`, `delta = 0.21`, ten levels) or
under Appendix C adaptation from `delta = 1, h = 0.1` with eight levels.
`STUDIES/freeze_mode_v1` measured the funnel at the **sampler defaults** and
found `P(omega < -5) = 0.0236 ± 0.014` (z = −1.7 at one seed) with 812
retained refinement exhaustions: about half the exact mass. A user who
follows the quick start on a funnel-like model may get biased tails. Which
cheap change to the defaults, if any, makes the default sampler unbiased on
Neal's funnel without losing throughput on ordinary targets?

## 2. Design

Target: Neal's 10-D funnel as in `examples/funnel_paper_adaptation.rs`
(`omega ~ N(0, 9)`, `x_i | omega ~ N(0, e^omega)`, nine `x_i`); exact
`P(omega < −5) = 0.047790`, `var(omega) = 9`. Starts `omega ∈ {−3, −1, 1, 3}`,
`x = 0`. 4 chains on 4 threads, 2,000 warmup, 20,000 retained per chain.
Seeds 82101, 82102, 82103 (verified unused in the repository by grep). The
metric is the sampler default (adapted diagonal) in every arm — this study
is about what `Sampler::new()` does, not about the paper's identity-metric
setting.

Arms (each is `Tuning::default()` / `Adaptation::default()` plus the override):

| arm | override |
|---|---|
| `defaults` | none (the 0.2.0 sampler defaults) |
| `levels8` | `max_refinement_levels(8)` |
| `delta0.5` | `max_error(0.5)` |
| `delta0.25` | `max_error(0.25)` |
| `levels8+delta0.5` | both |
| `paper-4` | `Adaptation::Paper(PaperAdaptationConfig::default())` from `h0 = 0.5`, `delta = 1`, four levels |
| `paper-8` | the same with eight levels |
| `stan-style` | `Adaptation::Custom(WarmupConfig::stan_style(0.8))` |
| `nuts-1` | `max_refinement_levels(1)`: no refinement, a NUTS-like control expected to show the NUTS bias |

Cost cells, same seeds, same arms: the noncentered Eight Schools of the
strict track (`STUDIES/eight_schools_v9_rebench_v1`: `mu, log tau, z[8]`,
starts `log tau ∈ {−2, −1, 0, 1}`) and a 100-D standard Gaussian from
`Init::uniform()` starts, 4 chains × 1,000 / 1,000. The strict track's own
tuning (depth 8, acceptance 0.95) is not used: the cost cells measure the
sampler defaults plus the arm's override, which is what a default change
would touch.

## 3. Measurements

Funnel, per cell: `P(omega < −5)` pooled over chains, its MCSE
(`diagnostics::mcse_mean` on the indicator, i.e. `sd / sqrt(ESS_mean)`, the
ArviZ estimator), `z = (estimate − 0.047790) / MCSE`; `var(omega)` against 9;
retained divergences, refinement exhaustions, depth-cap stops, invalid
evaluations; rank-normalised bulk and tail ESS on `omega` and `x_1` and the
maximum R-hat over coordinates; retained target calls; wall seconds of the
`run` call (4 threads); final `h` and `delta` per chain.

Cost cells, per cell: mean and minimum bulk ESS over coordinates, minimum
tail ESS, maximum R-hat, retained target calls, health counts, wall. The
cost figure is **mean bulk ESS over coordinates per retained target call**,
seed-median, as a ratio to the `defaults` arm.

Seed aggregation: medians over the three seeds; tail-mass `z` is reported
per seed and the qualification uses every seed.

## 4. Decision rule

Written before running.

1. An arm is **unbiased** if `|z| ≤ 2` on all three seeds for `P(omega < −5)`.
   (`nuts-1` is a control and is never chosen.)
2. An arm is **cheap** if its seed-median ESS/call ratio to `defaults` is
   ≥ 0.9 on both the Eight Schools and the 100-D Gaussian.
3. Choose the unbiased-and-cheap arm with the smallest seed-median funnel
   retained target calls. Apply it as `Tuning::default()` /
   `Adaptation::default()` in a labelled final commit (update
   `tests/sampler_api.rs`, README defaults table and quick start, CHANGELOG
   0.2.0 Changed, `wiki/release-0.2.0.md`). `tests/kernel_fingerprint.rs`
   pins the `walnutpie` defaults and must not change.
4. If no arm is both, choose the unbiased arm with the smallest funnel
   retained calls, apply it as the default, and report its cost ratios.
5. If no arm is unbiased, leave the defaults, add a prominent README note,
   and add a `Tuning::funnel()` preset that reaches `|z| ≤ 2` (the paper
   setting of `examples/funnel_paper_adaptation.rs` if none of the grid
   does).

`summarize` in `src/main.rs` applies rules 1–4 mechanically.

## 5. Predictions

* P1: `defaults` is biased low (`z < −2`) on at least two of three seeds,
  reproducing `freeze_mode_v1`, with hundreds of retained exhaustions per cell.
* P2: `nuts-1` is biased low on every seed with very few draws below −5.7
  (the paper's NUTS result), and has thousands of retained exhaustions.
* P3: eight levels alone (`levels8`) removes most retained exhaustions and
  brings the tail within `|z| ≤ 2`; the mechanism in `freeze_mode_v1` is that
  four halvings (`h / 16`) are not enough to enter the neck at the adapted `h`.
* P4: `delta0.5` and `delta0.25` alone help less than `levels8` (they lower
  `h` through dual averaging but keep the same finest micro step relative to
  `h`), and cost more calls on the Gaussian.
* P5: `paper-8` is unbiased (as in `paper_funnel_adaptive_v2` from `h = 0.1`)
  and `paper-4` is not; `paper-*` costs ≥ 10 % on the Gaussian relative to
  dual averaging (`adaptation_parity_v1`: 0.995 geomean on posteriordb, but
  the Gaussian is where dual averaging is tightest).
* P6: `levels8` costs nothing measurable on the Eight Schools or the
  Gaussian (no leaf refines past level 2 on those targets; the levels are a
  cap, not a cost).
* P7: `stan-style` is biased (its retained rule is the two-sided default at
  four levels, and its warmup produces a larger `h`).

## 6. Not done

No kernel change, no metric change, no min-micro-step arm (`M8` was unusable
on this target in `paper_funnel_reproduction_v1`), no change to
`RunConfig`/`KernelTuning` defaults.
