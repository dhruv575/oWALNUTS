# Preregistration — refinement_role_v1 (WP34-REFINEMENT-ROLE-V1)

Frozen 2026-09-03 after the instrumentation phase (`artifacts/instrumentation/`,
arm `da` on the v5 seed 87101, one cell per model, run 16:10–16:17 local)
and before the first phase-2 cell. `protocol.json` carries the same content
in machine form; its hash is in `CHECKSUMS.sha256` and in `summary.json`.

## Question

On ordinary posteriors oWALNUTS runs as NUTS with a slightly worse
per-gradient efficiency (`posteriordb_bench_v5`: 0.67–0.95x CmdStan's minimum
bulk ESS per gradient on every healthy model, 0.82x geomean). The JMLR
paper's promise is the opposite: with refinement doing the local work, the
macro step `h` should be able to be **larger** than NUTS's step, and the
fixed cost of the rare refined leaf should be repaid by fewer leaves per
orbit elsewhere. Is that promise realisable on posteriordb, and what setting
of (`h` target, `delta`) realises it?

## What the instrumentation found (phase 1, before this freeze)

Arm `da` (the shipped defaults: `Tuning::default()` with `MomentumSum`,
eight levels, `delta = 1`; `Adaptation::default()` = dual averaging at 0.8
on the coarse-endpoint statistic with the Stan regularisation) on the 17
posteriordb models at the v5 seed 87101, with CmdStan's adapted step per
model taken as the median of the twelve v5 CmdStan chain steps (three seeds
x four chains). All 17 cells reproduced the v5 cells bit-for-bit (same
gradient counts, same minimum ESS), so the instruments are attached to the
validated run.

1. **`h_walnuts ≈ h_stan`.** Geometric mean of the per-model ratio of the
   median adapted `h` to CmdStan's step: **1.000** (range 0.79 on the
   centered eight schools to 1.23 on `accel_gp`; 0.87–1.12 on the fourteen
   healthy models). Dual averaging at 0.8 on the coarse-endpoint statistic
   installs Stan's step: the macro step behaves like a NUTS step.
2. **Refinement hardly engages.** Fraction of retained built leaves accepted
   above level 0: median **0.22 %**, range 0.00 % (`nes2000`) to 3.3 %
   (centered eight schools); 1.1 % on `one_comp`, 0.9 % on the noncentered
   eight schools, 0.5 % on `garch11`, below 0.3 % elsewhere. Gradients per
   built leaf 1.00–1.09 (1.41 on the centered eight schools).
3. **But its reverse-coarser stop is not rare on the hard models.** The
   fraction of retained transitions that end because a refined leaf's
   reverse coarsening passed: 0.8–7 % on the regressions and time-series
   models (kernel_gap_v1's 3–7 %), **10 % on the noncentered eight schools,
   20 % on `gp_pois_regr`, 21 % on the centered eight schools, 54 % on
   `accel_gp`** — the four models where oWALNUTS is furthest behind CmdStan
   per gradient (0.75, 0.75, —, 0.47x in v5).
4. **The level-0 error grows too fast with `h` for a larger macro step to be
   repaid.** The trace (fresh momenta at every second retained draw, one
   macro step at multiples of the adapted `h`, endpoint error `|H_end -
   H_start|`, the statistic the kernel tests against `delta`): at `h` the
   fraction of leaves with `|dH| > 1` is 0.4–6 % (median 0.9 %); at 1.5`h`
   it is 12–27 %; at 2`h` 28–62 %; at 3`h` 60–97 %. The median `|dH|` goes
   0.08 → 0.3 → 0.9 → 8 (h^3–h^4 in the tail) and the 99th percentile
   0.7–2 at `h` on the healthy models (1,000 on the centered eight schools,
   4 on `accel_gp`). The distribution is one smooth population: the ratio
   q99/q50 at `h` is ~10 on every healthy model. There is no separate
   "stiff" subpopulation for refinement to absorb; the whole posterior has
   the same stiffness, so the leaf error is limited globally, exactly as in
   NUTS. At 2`h` a level-1 leaf (two micro-steps) would bring `|dH| > 1`
   back to 0.4–5 %, but a level-1 leaf costs the same two gradients as two
   level-0 leaves at `h`, plus its reverse check, and once a third to a half
   of the leaves refine, the reverse-coarser stop that already ends 10–54 %
   of transitions on the hard models would end most of them.
5. **Stan's statistic at Stan's step is 0.90–0.95, not 0.8.** CmdStan's
   `accept_stat__` target of 0.8 is over the accumulated trajectory error;
   the per-leaf `min(1, exp(-dH))` at CmdStan's step is 0.90–0.95 on the
   healthy models, and the coarse-endpoint `E exp(-|dH|)` at the adapted
   `h` is 0.84–0.90 on the retained draws. Both statistics land on the
   same `h` because the per-leaf error at the step where the accumulated
   error gives 0.8 is a few percent of `delta`.

Arm (f) follows from 3: the residual on the hard models is refinement's
reverse-coarser stop at `delta = 1`, not the step. `delta = 2` at the
default target (`da-d2`) leaves `h` where it is and halves the fraction of
leaves that refine (the trace: `P(|dH| > 2)` at `h` is 0.0–1.4 % on the
healthy models against `P(|dH| > 1)` of 0.4–4 %, 11 % against 15 % on the
centered eight schools, 3 % against 6 % on `accel_gp`). `da06-d2` combines
it with the larger step of arm (b).

## Arms (all on the shipped defaults otherwise; `arms.rs`)

| arm | step rule | `delta` | task label |
|---|---|---|---|
| `da` | `Adaptation::default()`: dual averaging 0.8, coarse-endpoint statistic | 1 | (a) |
| `da06` | dual averaging 0.6, coarse-endpoint statistic | 1 | (b) |
| `da06-d05` | dual averaging 0.6, coarse-endpoint statistic | 0.5 | (c) |
| `paper08` | `Adaptation::Paper(PaperAdaptationConfig::default())`: Appendix C, Gamma 0.8, K-quantile `delta` (Delta 2, p 0.95), the v4 robust rule (`exhausted_transitions_as_zero`, wide step band) | adapted from 1 | (d) |
| `paper06` | Appendix C with Gamma 0.6, otherwise as `paper08` | adapted from 1 | (d) |
| `stanacc` | dual averaging 0.8 on `DualAveragingAcceptance::MeanTrajectoryAcceptance` (Stan's `accept_stat__`), same warmup exhaustion rule and regularisation | 1 | (e) |
| `da-d2` | dual averaging 0.8, coarse-endpoint statistic | 2 | (f) |
| `da06-d2` | dual averaging 0.6, coarse-endpoint statistic | 2 | (f) |

`da` is literally `Adaptation::default()` + `Tuning::default()`; the coarse
arms use `Adaptation::DualAveraging { target_accept }` and
`Tuning::default().max_error(delta)`; `stanacc` is `Adaptation::Custom` of
the same `WarmupConfig` with the statistic switched. No kernel or sampler
source changes; nothing tuned per model.

## Protocol

`posteriordb_bench_v3` / v5 verbatim: 17 posteriors (`28f8d3d`), 4 chains x
1,000 / 1,000, `Init::uniform()` starts (shared across arms per seed by
construction), `Metric::diagonal()`, `Limits::admit_worst_case()`, four
threads on a non-`STAN_THREADS` BridgeStan 2.9.0 build (compiled here; the
`wt/posteriordb-v4` worktree no longer exists), gates rank R-hat <= 1.01,
bulk and tail ESS >= 400 on every reference parameter, zero sampling
divergences, ArviZ 0.23.4 estimators, 2,700 s cell timeout, strictly
sequential run order: models in protocol order, arms in the table order,
seeds ascending. **Seeds 89101, 89102, 89103** (grep-verified unused before
this freeze). CmdStan is cited from v5 (seeds 87101–87103), not rerun; the
per-model reference step for the trace is the median of its twelve chain
steps. Every cell also runs the leaf-error trace (excluded from the wall and
from `gradients_total`).

Side checks, every arm, the same three seeds: Neal's 10-D funnel at the
sampler defaults (4 x 2,000 / 20,000, starts `omega in {-3, -1, 1, 3}`,
per-seed MCSE z of `P(omega < -5)`, exact 0.0478); the Eight Schools strict
track (`eight_schools_v9_rebench_v1` settings: `h 0.3`, depth 8, eight
levels, 4 x 1,000 / 1,000, threads 1, `walnutpie` facade, three repetitions
that must be bit-identical) with the arm's step rule replacing
`WarmupConfig::new(0.95)` where the arm changes it (a dual-averaging target
other than 0.8 replaces 0.95; the Stan statistic is switched on at 0.95; the
paper arms replace dual averaging) and the arm's `delta` replacing 1. The
task asked for the side checks on the arms that beat (a); all arms are run
because they are cheap and the table is more useful complete.

## Metrics

Per cell: minimum over reference parameters of bulk ESS per target call
(warmup included; the protocol's `gradients_total`), gates, adapted `h` per
chain and its median over chains divided by CmdStan's v5 step, fraction of
retained built leaves above level 0 and the per-level histogram, fraction
of retained transitions ending in a reverse-coarser stop, leaves per
transition, gradients per leaf, final `delta` per chain, divergences, depth
caps, frozen chains, max |z|. Per model: seed medians; ratio to `da`.
Across models: geometric mean of the per-model ratios over all 17 (the
decision statistic) and over the fourteen CmdStan-healthy models
(reported); ratio to the v5 CmdStan medians (reported).

## Decision rule (pre-written by the task)

Flip the `sampler` default to an arm iff, against `da` on these seeds:
C1 geomean min-bulk-ESS/gradient >= 1.15 over the 17 models; C2 no model
< 0.85; C3 cells passing all gates >= `da`'s; C4 funnel |z| <= 2 on every
seed; C5 Eight Schools strict-track min-bulk-ESS/call >= 0.9x `da`. If
several arms meet the rule the one with the highest C1 is flipped, in a
labelled final commit with `tests/sampler_api.rs` updates. Otherwise no
default changes; `tests/kernel_fingerprint.rs` is untouched in every case.

## Predictions

P1 (the promise as stated, arms b/c): `da06` installs `h` 1.3–1.6x
CmdStan's (the trace puts `E exp(-|dH|) = 0.6` between 1.5`h` and 2`h`),
refines 10–25 % of its leaves, and is **below** `da` per gradient (geomean
0.6–0.9) with more reverse-coarser stops; `da06-d05` refines 25–45 % and is
lower still. Neither meets C1.

P2 (arm e): `stanacc` installs `h` within 0.9–1.1x CmdStan's and is within
0.9–1.1x `da` per gradient: the choice of acceptance statistic is not what
pins `h`, the per-leaf error is.

P3 (arm d): the paper arms install `h` 1.2–1.8x CmdStan's with `delta`
adapted to 1–3 and 15–35 % of leaves refined; geomean vs `da` below 1.15
(expected 0.7–1.1), with at least one model below 0.85. `paper06` is below
`paper08`.

P4 (arm f): `da-d2` keeps `h` within 0.95–1.05x `da`'s, halves the
reverse-coarser stop fraction on the noncentered/centered eight schools,
`gp_pois_regr` and `accel_gp`, and is 1.0–1.1x `da` geomean with its
largest gains (1.1–1.3x) on those four; it does not reach C1 (1.15) because
on the other thirteen models the stop fraction is already 1–7 %. Its funnel
tail mass is the risk: `delta = 2` refines fewer neck leaves; predicted
|z| <= 2 on at least two of three seeds, not guaranteed on all three.
`da06-d2` behaves like `da06`.

P5 (the answer): no arm meets the rule; the promise is not realisable on
these posteriors because their level-0 leaf-error distribution is a single
smooth population whose refinement demand rises from ~1 % to ~50 % within a
factor of two of `h`, so there is no rare stiff leaf for refinement to
absorb, and a refined leaf costs what the NUTS micro-steps it replaces would
have cost.

## Reporting

All cells are reported; no reruns; failures are results. A driver crash is
relaunched and the interrupted cell re-run from scratch (seeded), recorded
as a deviation. The README states plainly whether the promise is realisable
and which arm, if any, realises it.
