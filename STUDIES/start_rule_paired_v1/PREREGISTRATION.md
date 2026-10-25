# start_rule_paired_v1 (WP60): preregistration

Frozen 2026-10-25, before the first evidence cell. The machine-readable form
is `protocol.json`.

## Question

Is the drop in ESS per gradient from posteriordb v6 to v7 caused by the WP52
`Init::best_of(16)` start default? The statistic is oWALNUTS / CmdStan
min-bulk-ESS per gradient over the fixed 16 models, which fell from 0.848 to
0.708. WP56 could not attribute the drop because three things changed at once:
the seeds, the WP36 removal of chain rescue, and the WP52 start rule.

## Design

Both arms run at `f097391c`. The driver checks that the worktree's library
source equals that commit. Each arm is `Sampler::new()` with only the run
shape and `admit_worst_case` set, so every other setting is the commit
default. The arms differ in the start rule only:

- **`uniform`**: `Init::uniform()`.
- **`best_of_16`**: `Init::best_of(16)`, which is `Init::default()`.

Runs are 4 x 1,000/1,000 with 4 threads, on five fresh seeds (600601–600605)
paired by seed. Order: models as listed; within a model, seeds ascending;
within a seed, `uniform` first. Strictly sequential; nothing is rerun.

Models (six):

- `accel_gp`, `one_comp` and `hmm_drive_0`, named by the coordinator.
- The three models with the lowest best_of/uniform ratio in
  `init_rule_confirmation_v1/artifacts/summary.json` that are not already
  named: `earnings` (0.208), `eight_schools_centered` (0.524) and `kidiq`
  (0.835). `hmm_drive_0` (0.365) is the second-lowest and is already in the
  list, so the next model is taken.

**Selection bias.** Three of the six were picked because best_of looked worst
on WP52's seeds. On fresh seeds, regression to the mean pulls their ratios
back toward 1, while the selection itself biases the geomean toward H1. Both
effects are stated; neither is corrected.

Gates are the house gates on the posteriordb reference parameters, with z
reported.

**Statistics.** The cell statistic is min bulk ESS / total gradients. The
model ratio is the geomean of the paired best/uniform ratios over the seeds.
The primary statistic is the geomean of the six model ratios, plus the count
of models whose ratio is below 1.0.

**Mechanism telemetry.** Recorded per chain:

- start log density;
- end-of-warmup step, and the warmup step trace every 50 transitions;
- warmup and retained gradients;
- per-chain ESS;
- chain warnings.

## Hypotheses and predictions (frozen)

- **H1: the start rule causes the drop.** The paired geomean is **< 0.9**.
- **H0: it does not.** The fresh seeds and the WP36 rescue removal explain
  the drop. The paired geomean is **>= 0.95**.
- A geomean in [0.9, 0.95) supports neither.

## Decision rule (frozen)

- **Revert.** If the paired geomean is < 0.9 **and** at least 4 of the 6
  model ratios are below 1.0, recommend reverting the default to
  `Init::uniform()`, with `best_of` kept as an opt-in.
- **Keep.** If the paired geomean is >= 0.95, recommend keeping
  `Init::best_of(16)`.
- **Inconclusive.** Otherwise, including the case of < 0.9 with fewer than 4
  models below 1.0. Recommend keeping the default and documenting the
  number.

This study flips nothing. A failed cell is a result: that seed becomes
unpaired for its model, and the README reports the count.

## Pre-freeze smoke test (disclosed)

I ran the driver once on `kidiq` with the non-evidence seed 21. Its output
went to a scratch directory and is not committed. That one pair showed a
ratio of 0.76. No evidence seed has been run.
