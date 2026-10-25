# Preregistration — adaptive_delta_v1 (WP49)

Frozen 2026-10-24, after the implementation, its tests and a non-evidence
Gaussian calibration of one constant, and before the first evidence cell.
`protocol.json` carries the same content in machine form (arms, seeds, rule,
numeric predictions scored mechanically by `run_study.py analyze`).

## Question

`wiki/open-questions.md` item 4. Fixed `delta = 2` was the WP34 near miss
(1.070x over 17 posteriordb models at the shipped step, the same 42 gates)
that lost `accel_gp` (0.68x against the 0.85 clause) and failed WP37A's funnel
gross-safety gate (retained divergences on 6/12 seeds). The paper's Appendix C
`delta` rule installs `delta ~ 0` from bad starts (WP22/23) and after the v4
robust guards is at parity, not better. **Can a warmup-time rule that adapts
`delta` from the observed level-0 leaf-error distribution keep the `delta = 2`
gain where it exists and fall back to `delta <= 1` where the leaf-error tail is
heavy (funnel neck, `accel_gp`)?** Long shot; a clean negative is a fine
outcome.

## What the rule must respond to (WP34)

At the adapted `h` the level-0 `|dH|` distribution is one smooth population
on the healthy models (q99/q50 ~ 10, q99 0.67–1.01, `P(|dH| > 1)` 0.4–3.5 %);
the models where refinement does real work have a heavier tail: q99 1.1–2.1
on `garch11`, `one_comp`, `gp_pois_regr`, the noncentered eight schools, 4.0
on `accel_gp`, ~1,000 on the centered eight schools. Dual averaging pins the
bulk (`E exp(-|dH|) = 0.8` sets q50 ~ 0.08 everywhere), so a **tail
quantile** at the adapted step is a scale-free measure of tail heaviness.

## A design observation made before freezing

The two candidate rules in the task are both *increasing* in the tail: R1 as
written, `delta = clamp(c * q_0.9, 0.5, 2)`, and R2, a controller holding the
refined-leaf fraction at 1–2 % (whose fixed point is `delta = q_{1-f}`), each
install a *larger* `delta` where the tail is heavier. That is the opposite of
the mapping the question asks for: they would put `accel_gp` and the funnel
at `delta = 2` and the light-tailed models at or below 1. R1 is therefore
frozen in its inverse form (the tolerance falls as the tail grows), with
`p = 0.99` because `q_0.9` is bulk-dominated once dual averaging has pinned
the bulk; R2 is kept as the task wrote it (target 1.5 %) as the direct test of
the "tolerance tracks the error" hypothesis.

## Change under test (library, opt-in)

`WarmupConfig::with_adaptive_delta(AdaptiveDeltaConfig)`; off in every
default, `Tuning::default()`, `Adaptation::default()`, `RunConfig` and the
`walnutpie` defaults unchanged, kernel fingerprints unchanged (`cargo test
--release` green, log in `artifacts/cargo-test.log`).

- New kernel telemetry: `MacroLeafOutcome::level_zero_energy_error`, the
  endpoint error of the level-0 integration, the statistic first tested
  against `delta`, carried on the trace events that warmup already uses
  (infinite for an invalid level-0 evaluation). Telemetry only; no
  arithmetic, RNG or branch of the kernel changes.
- Every leaf attempted during a slow metric window (built or rejected)
  enters a fixed log histogram (16 bins per decade over `[1e-8, 1e8]` plus
  under/overflow). At every slow-window end the empirical `p`-quantile `q`
  (geometric interpolation in the bin) is mapped by the rule and clamped.
- Guards copied from the v4 robust paper rule (`paper_adaptation_robust_v1`):
  finite clamp so `delta` can never collapse; nothing installed in the
  initial fast phase; nothing installed before the diagonal metric was
  installed at an *earlier* boundary (the first slow window, which ends at
  the first metric installation, is `Deferred`); a window with fewer than
  100 leaves is skipped. Dual averaging of `h` continues through installs.
- Installs happen only during discarded transitions, so **`delta` never
  moves during the retained phase** (`tests/adaptive_delta.rs` checks the
  retained `delta` equals the last installed value). With the default
  schedule (1,000 warmup) the boundaries are transitions 100 (deferred),
  150, 250, 450 and 950; the 500-transition final slow window decides the
  retained `delta`. The trajectory (`RunTelemetry::adaptive_delta_updates`:
  leaves, quantile, candidate, `delta` before/after, step, fraction of
  leaves above the prior `delta`) is recorded per chain per window in every
  cell.

## Arms

| arm | `delta` | role |
|---|---|---|
| `da` | 1 — `Adaptation::default()` + `Tuning::default()` | baseline |
| `d2` | fixed 2 — WP34 `da-d2`, rerun on these seeds | control, never recommended |
| `r1` | `clamp(1.8 / q_0.99(|dH_0|), 1, 2)` per slow window, start 1 | candidate |
| `r2` | `clamp(q_0.985(|dH_0|), 0.5, 2)` per slow window, start 1 | candidate |

`r1`/`r2` use `Adaptation::Custom(WarmupConfig::new(0.8)` + the default warmup
exhaustion rule and regularisation + the rule`)`, bit-identical to
`Adaptation::default()` when the option is off (tested).

**Calibration of the one constant (non-evidence).** `r1` at scale 1.6 and
`r2` on standard Gaussians, D = 10 and 100, `Init::uniform()`, 4 x 1,000 /
1,000, seeds 1 and 2 (`artifacts/calibration.log`): the final-window q0.99
was 0.93–1.12 (median ~0.99) on all 16 chains (larger than the WP34
retained-draw trace because the window includes dual averaging's
post-restart exploration). Scale **1.8** puts an ordinary Gaussian at
`delta` 1.6–1.95 (median ~1.8), inside the task's 1.5–2 band. `r2` put the
same Gaussians at 0.84–0.92. **Pre-freeze smoke tests (pipeline checks, non-evidence seed 5, not
reported as evidence):** the funnel binary under `r1` and `r2`, and the
posteriordb cell harness on the noncentered eight schools under `r1`. On the
funnel the 2,000-transition warmup's final slow window (transitions
850–1,950) gave `r1` a q0.99 of only 1.30–1.36 and final `delta` 1.04–1.39
per chain (with 3 retained divergences on two chains), and `r2` 1.19–2.0;
the noncentered eight schools gave `r1` q0.99 5.6, `delta` 1.0. The funnel
part of P1 below was written after this smoke test; **no rule constant was
changed after it** (the scale was fixed by the Gaussian calibration alone).
No Eight Schools strict-track run and no study-seed run was made before this
freeze.

## Protocol

`posteriordb_bench_v5` / WP34 cell protocol verbatim (harness copied from
`refinement_role_v1`): 17 posteriors at posteriordb `28f8d3d`, 4 chains x
1,000 / 1,000, `Init::uniform()`, `Metric::diagonal()`,
`Limits::admit_worst_case()`, four threads, non-`STAN_THREADS` BridgeStan
2.9.0 compiled in this worktree, gates rank R-hat <= 1.01, bulk and tail ESS
>= 400 on every reference parameter, zero retained divergences, ArviZ 0.23.4,
2,700 s cell timeout. **Seeds 94901, 94902, 94903** (grep: no prior use as a
seed; see `protocol.json` `seed_check`). Run order: models in protocol order,
arms `da, d2, r1, r2`, seeds ascending, strictly sequential; then the funnel,
then Eight Schools. Every cell also runs the WP34 leaf-error trace (excluded
from wall and gradients). CmdStan is cited from v5, not rerun.

Side checks, every arm:

- **Funnel** (decisive): Neal's 10-D funnel at the sampler defaults plus the
  arm's rule, 4 x 2,000 / 20,000, starts `omega in {-3, -1, 1, 3}`; MCSE z
  of `P(omega < -5)` (exact 0.0478) and **WP37A F3 gross safety** per seed
  (no error, finite, zero retained divergences, rank R-hat <= 1.05,
  `|P5 - exact| <= 0.025`, `|P6 - exact| <= 0.015`, Var omega in `[5, 13]`).
  Decisive on the three study seeds; seeds 94904–94912 are a descriptive
  extension so the 12-seed WP37A counts (|z| <= 2, gross-safe,
  divergence-free, F4-healthy) can be compared.
- **Eight Schools strict track** (secondary, reported): the WP37A amended
  track (h0 0.3, depth 8, eight levels, DA 0.95 with AcceptUnlessDivergent
  warmup exhaustion and Stan regularisation, threads 1, `walnutpie` facade,
  three bit-identical repetitions) with the arm's rule; min over six
  functionals of bulk ESS per callback, geomean over seeds, ratio to `da`.

Wall-clock numbers are contended (ten agents on 16 cores) and are labelled as
such; the evidence is gradient counts, ESS, R-hat and z.

## Decision rule (frozen; from the task)

Recommend a candidate (`r1` or `r2`) as the default iff **all** of:

- **C1** geomean over the 17 models of the per-model ratio (seed-median min
  bulk ESS per gradient, warmup included, arm / `da`) **>= 1.10**;
- **C2** no model below **0.85x** (`accel_gp` included; a model without a
  ratio fails C1 and C2);
- **C3** cells passing all gates >= `da`'s;
- **C4** funnel |z| <= 2 on every study seed;
- **C5** funnel gross safety passed on every study seed.

If both qualify, the higher C1. `d2` is evaluated on the same criteria for
reference only. A qualifying arm is a recommendation; no default changes on
this branch. All cells are reported; no reruns; failures are results; nothing
is tuned after the first evidence cell. A driver crash is relaunched and the
interrupted cell re-run from scratch (seeded), recorded as a deviation.

## Predictions (numeric; scored mechanically from `protocol.json`)

Model classes from the WP34 trace q0.99 at `h`: **light** (q99 <= 1.01:
diamonds, earnings, mesquite, kidiq, sblrc, nes2000, arK, arma11,
hmm_example, hmm_drive_0, lotka_volterra), **moderate** (1.1–2.1: noncentered
eight schools, garch11, gp_pois_regr, one_comp), **heavy** (>= 4: centered
eight schools, accel_gp).

- **P1 (where `delta` lands, median over the class of the per-model median
  final `delta`)**: `r1` light 1.45–2.0 (point ~1.7), moderate 1.0–1.5
  (~1.15), heavy 1.0–1.1 (~1.0); funnel 1.0–1.5 (the funnel's neck is
  visited ~5 % of the time, so its 1 % tail is only moderately heavy). `r2`
  light 0.65–1.0 (~0.85), moderate 1.0–2.0 (~1.5), heavy 1.8–2.0 (~2);
  funnel 1.2–2.0.
- **P2 (efficiency)**: geomean vs `da`: `d2` 1.00–1.10 (WP34 1.070), `r1`
  1.00–1.08 (point ~1.04: it keeps part of the `d2` gain on the light class
  and none elsewhere), `r2` 0.85–1.00 (more refinement on the light class).
- **P3 (`accel_gp`)**: `d2` 0.55–0.90, `r1` 0.85–1.15 (it lands at ~1, the
  default), `r2` 0.55–0.90 (it lands at ~2).
- **P4 (rule)**: neither candidate meets the rule; `r1` is expected to fail
  C1 (the light-class `d2` gains in WP34 are 1.0–1.7x per model but come from
  a 3-seed median and are diluted by the six models that fall back to 1),
  `r2` to fail C1 and C2.
- **P5 (funnel)**: `r1` sits between `da` and `d2` (delta 1.0–1.5): |z| <= 2
  on the study seeds and a 12-seed divergence-free count within two of
  `da`'s; `r2` and
  `d2` (delta ~2) reproduce WP37A's pattern of retained divergences spread
  over at least as many of the 12 seeds as `da`. Gross safety on all three
  study seeds is a coin-flip for every arm (WP37A: fixed 1 had divergences
  on 4/12 seeds).

## Reporting

README verdict first; every cell, the per-chain per-window `delta`
trajectory, which predictions held and failed with values; `LEDGER-ENTRY.md`
in the house style; `CHECKSUMS.sha256` from `checksums.py`.
