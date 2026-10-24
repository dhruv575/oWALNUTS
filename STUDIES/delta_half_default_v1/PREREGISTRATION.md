# Preregistration — delta_half_default_v1 (WP42)

Frozen 2026-10-24 before the first evidence cell. `protocol.json` carries the
same content in machine form; its hash is in `CHECKSUMS.sha256` and in
`artifacts/summary.json`. Branch `wt/delta-half`, base commit `3583d130`.
The only cell run before this freeze was one harness smoke test of the funnel
binary on seed 1 (not an evidence seed; output kept outside the study).

## Question

`wiki/open-questions.md` item 3. At the sampler defaults (`delta = 1`, eight
refinement levels) Neal's funnel is unbiased but not efficient: one chain per
seed adapts to `h` near 0.01, never enters or never leaves the neck, and the
`omega` R-hat is 1.01–1.04 (WP28, WP32). `levels 8 + delta 0.5` was the better
funnel sampler in WP28 (R-hat 1.005–1.017, zero divergences, about 2.5x the
`omega` bulk ESS at 0.74x the calls) but cost 21 % per call on a 100-D
Gaussian and 9 % on Eight Schools, and it has **never been measured on the
17-model posteriordb screen**. Is `delta = 0.5` free (or better) on ordinary
posteriors, so that it can become the default? `delta = 0.75` is the middle
arm.

What is already known and not repeated: lower `delta` at **four** levels is
worse (WP28: 11,000–12,000 exhaustions, biased tail); `delta 0.5` combined with
a larger step (`da06-d05`, WP34) was 0.630x. Neither is the question here:
this study holds everything at the shipped defaults (eight levels, dual
averaging 0.8 on the coarse-endpoint statistic) and changes `delta` only.

## Arms

| arm | change | source |
|---|---|---|
| `d1` | none: `Adaptation::default()` + `Tuning::default()` (`delta = 1`) | the shipped default |
| `d075` | `Tuning::default().max_error(0.75)` | middle arm |
| `d05` | `Tuning::default().max_error(0.5)` | the WP28 funnel setting |

No kernel or sampler source changes; nothing tuned per model. The harness
(`src/`, `run_delta_half.py`) is `STUDIES/refinement_role_v1`'s, with the arm
set reduced to `delta`, the leaf-error trace switched off (it only runs when an
`h_ref` argument is passed, which the driver never does) and the funnel
efficiency statistic added.

## Protocol

* **posteriordb screen**: the 17 posteriors of `refinement_role_v1` /
  `posteriordb_bench_v5` at posteriordb `28f8d3d`, 4 chains x 1,000 / 1,000,
  `Init::uniform()` starts (shared across arms per seed by construction),
  `Metric::diagonal()`, `Limits::admit_worst_case()`, four threads,
  non-`STAN_THREADS` BridgeStan 2.9.0 compiled in this worktree, ArviZ 0.23.4,
  2,700 s cell timeout. Gates: rank R-hat <= 1.01, bulk and tail ESS >= 400 on
  every reference parameter, zero retained divergences, finite draws, no
  sampler error. Per cell: gradients (warmup included), warmup and retained
  calls, min bulk/tail ESS, R-hat, refined-leaf fraction (retained built
  leaves above level 0), per-level histogram, max refinement level built and
  selected, retained exhaustions, depth-cap stops, divergences,
  reverse-coarser stop fraction, final step per chain.
* **Funnel**: Neal's 10-D funnel at the sampler defaults plus the arm's
  `delta`, 4 x 2,000 / 20,000, starts `omega in {-3, -1, 1, 3}`, four threads.
  `P(omega < -5)` (exact 0.0478) with the ArviZ-style MCSE z (the WP28
  statistic). **Efficiency statistic** (the number this study exists for):
  minimum over the ten coordinates (`omega`, `x1..x9`) of bulk ESS divided by
  all target calls including warmup, geometric mean over the three seeds.
  Also per-chain final `h`, per-chain tail mass and `omega` mean, `omega` bulk
  and tail ESS and R-hat, divergences, exhaustions, depth caps.
* **Eight Schools strict track** (secondary, reported, not in the rule):
  `eight_schools_v9_rebench_v1` settings as in `refinement_role_v1` (`h 0.3`,
  depth 8, eight levels, 4 x 1,000/1,000, one thread, `walnutpie` facade,
  `WarmupConfig::new(0.95)` with mass adaptation, three bit-identical
  repetitions), with the arm's `delta` replacing 1; min over the six v38
  functionals of bulk ESS per callback, geomean over seeds, ratio to `d1`.
* **Seeds 942101, 942102, 942103** (`git grep -w` over the repository and the
  sibling worktrees' study files: unused).
* **Run order**, strictly sequential, one sampling process at a time:
  (1) funnel, arms `d1, d075, d05`, seeds ascending; (2) Eight Schools, same
  order; (3) posteriordb, models in protocol order, arms `d1, d075, d05`,
  seeds ascending.
* CmdStan is cited from `posteriordb_bench_v5` (seeds 87101–87103), not rerun,
  and only reported.
* Contention: ten agents share 16 cores. Walls are recorded and labelled as
  contended; gradients, ESS, R-hat and z are the evidence.

## Decision rule (frozen)

Flip the sampler default to the **lowest-delta arm** (`d05` first, then
`d075`) that meets **all** of, against `d1` on these seeds:

* **R1** geometric mean over the 17 models of the per-model ratio of
  seed-median minimum bulk ESS per gradient (arm / `d1`) **>= 0.95**;
* **R2** no model's ratio **< 0.85**;
* **R3** cells passing all gates **>= `d1`'s**;
* **R4** funnel `|z| <= 2` on **every** seed;
* **R5** funnel efficiency statistic **>= 1.3x `d1`**.

A missing or errored posteriordb cell makes R1/R2 unevaluable for that model,
which counts as not met. If no arm qualifies, `delta = 1` stands. A qualifying
arm is a **recommendation**: per the shared brief, `Tuning::default()` is not
changed on this branch (the flip would alter retained draws under the
existing defaults); it would be a separate labelled change.

## Predictions (numeric, written before any evidence cell)

* **P1 refinement**: median (over models) refined-leaf fraction rises from
  about 0.002 at `d1` to 0.003–0.008 at `d075` and 0.006–0.03 at `d05` (the
  WP34 trace has `P(|dH| > 0.5)` about 6x `P(|dH| > 1)` at the adapted step).
  Median reverse-coarser stop fraction rises from about 0.03 to 0.04–0.08
  (`d075`) and 0.06–0.15 (`d05`). Max refinement level built at `d1` is <= 3
  on at least 14 of 17 models; at `d05` it is at least one level higher on at
  least 8 models.
* **P2 step**: adapted `h` (geomean over models of the seed-median ratio to
  `d1`) within 0.90–1.02x for both arms.
* **P3 cost**: `d05` geomean ESS/gradient vs `d1` in 0.75–0.92 (fails R1);
  `d075` in 0.88–0.98. Largest losses on `accel_gp`, `gp_pois_regr`, the
  noncentered eight schools and `diamonds`; at least one of them below 0.85 at
  `d05` (fails R2). Gradient overhead at `d05`: `accel_gp` 1.15–1.6x `d1`,
  `gp_pois_regr` 1.1–1.4x, median model 1.02–1.15x.
* **P4 gates and health**: gates at `d05` and `d075` within −4..+2 of `d1`
  (`d1` expected 42–45 of 51). Retained exhaustions zero on at least 14 of 17
  models in every arm; depth-cap stops unchanged except on `diamonds`.
* **P5 funnel**: every arm `|z| <= 2` on every seed. Efficiency statistic
  `d05` 1.5–4x `d1`, `d075` 1.1–2.5x. At `d1` at least two of three seeds
  have a chain with final `h < 0.02`; at `d05` at most one seed does.
* **P6 Eight Schools**: `d05` 0.85–0.95x `d1`, `d075` 0.92–1.0x.
* **P7 decision**: no arm meets the rule — `d05` passes R4 and R5 but fails
  R1 and/or R2; `d075` fails at least one of R1, R2, R5. `delta = 1` stands,
  `delta = 0.5` stays the documented opt-in for funnel-like targets.

## Reporting

All cells are reported; no reruns; failures are results; nothing tuned after
seeing results. A driver crash is relaunched and the interrupted cell re-run
from scratch (seeded), recorded as a deviation. The README states the verdict
first and which predictions held and failed.
