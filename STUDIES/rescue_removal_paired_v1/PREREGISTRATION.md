# rescue_removal_paired_v1 (WP61): preregistration

Frozen 2026-10-25, before the first evidence cell. The machine-readable form
is `protocol.json`.

## Question

Does the WP36 removal of chain rescue explain the posteriordb v6 -> v7 drop
in oWALNUTS min-bulk-ESS per gradient (0.848 -> 0.708x CmdStan, fixed 16)?
WP36 set `DEFAULT_CHAIN_RESCUE = None`; v6 ran with `restart_from_best()`.
WP60 has already shown the WP52 start rule is not the cause: best_of_16 /
uniform = 1.061.

## What WP36 found (from `wiki/findings/chain-rescue.md`)

`restart_from_best` met WP33's preregistered rule: 25/27 vs 21/27 cells,
with `lotka_volterra` and `arma11` rescued. It then became the v6 default,
where v6 scored 45/51. WP36 (`chain_rescue_v2`) ran 7 models plus the funnel
on 12 seeds and found two problems:

- The log-density criterion fires on merely late chains at the first
  boundary, and on every fresh-seed second-mode `hmm_drive_0` draw.
- The `current` (immediate restart) arm made 117 restarts, including five
  mapped-origin overwrites and two unknown-origin actions. The frozen origin
  classifier found stable origins only for pathological ARMA and
  `lotka_volterra` starts, and zero HMM origins. So it could not show that
  the moved chains were nuisance rather than genuine modes.

`two_hit` failed its conjunctive gates and `current` hit its overwrite red
lines, so the mechanical decision was **no rescue**. A density rescue blinds
R-hat to the mode a chain found. Rescue remains an explicit opt-in.

## Design

Both arms run at main **`c8b4bb2d`**. Its `src/` differs from the v7 commit
`f097391c` only in documentation and in the WP59 `ChainWarning` reporting, so
the draws are the same. The driver checks the library source against the
commit.

Both arms are `Sampler::new()` with only the run shape and `admit_worst_case`
set, and both use `Init::default()` (best-of-16). They differ in rescue only:

- **`rescue_off`**: `Adaptation::default()`, which has no rescue.
- **`rescue_on`**: `Adaptation::Custom(WarmupConfig::new(0.8)`
  `.with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)`
  `.with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)`
  `.with_chain_rescue(ChainRescueConfig::restart_from_best()))`. This is what
  `Adaptation::default()` built under the WP33 default used by v6, and how
  WP36's `current` arm was built.

A smoke test (non-evidence seed 31, scratch output, centered Eight Schools)
confirmed two things:

- The arms' warmup configs are identical apart from `chain_rescue`.
- With no restart, the draws are identical.

`rescue_on` is *not* v6: v6 also used uniform starts and its own seeds.

Models, five in all:

- `accel_gp`, `one_comp` and `hmm_drive_0`.
- The two fixed-16 models with the largest v6 -> v7 drop other than those,
  from the v7 `versus_v6` table: centered Eight Schools (0.594) and `nes2000`
  (0.908).

Runs are 4 x 1,000/1,000 with 4 threads, on fresh seeds 610601–610605 paired
by seed. Order: models as listed; within a model, seeds ascending; within a
seed, `rescue_off` first. Strictly sequential; nothing is rerun. The house
gates apply, with reference z reported. Every non-`kept` rescue update is
recorded: criterion, source, transition and step before and after.

**Statistics.** The cell statistic is min bulk ESS / total gradients. The
model ratio is the geomean of the paired on/off ratios over the seeds. The
primary statistic is the geomean of the five model ratios, plus the counts
of models above and below 1.

## Hypotheses (frozen)

- **H1: rescue removal explains the drop.** The paired geomean is
  **>= 1.15**.
- **H0: it does not.** Fresh seeds explain the drop. The paired geomean is
  **< 1.05**.
- A geomean in [1.05, 1.15) is partial and supports neither.

## Decision rule (frozen)

**Attribution only.** No outcome leads to a default flip, or to a
recommendation to restore rescue, because the WP36 mode-hiding objection
stands regardless of efficiency. A failed cell is a result: that seed becomes
unpaired for its model, and the README reports the count.
