# posteriordb ratio robustness (WP72): preregistration

Frozen before the first evidence cell. The machine-readable form is
`protocol.json`.

## Question

How much of the fixed-16 per-gradient headline (oWALNUTS / CmdStan
min-bulk-ESS per gradient) is seed noise, and how much is a competitor
failing on one model?

WP64 found that the WP62 six-seed pooled geomean is **1.206 on Linux and
0.761 on Windows** at the same seeds and commits. The gap comes from
`hmm_drive_0`, where CmdStan has a chain in a second mode on 4 of 6 Linux
seeds, so that model's ratio is 133. Without `hmm_drive_0` the figures are
0.862 and 0.749. This study adds 12 seeds and asks which statistic should
carry the v8 headline.

## Design

- **Runs.** 12 further fresh seeds (720701–720712) on WP62's fixed 16
  models, Linux only. Arms: oWALNUTS (defaults) and CmdStan 2.39.0 (defaults).
  4 chains x 1,000 / 1,000 with 4 threads. Gates, gate parameters, cell code
  and the 2,700 s timeout are v7's / WP62's.
- **Commit.** **`c5c60122`**, WP62's commit, whose default sampler is v7's.
  The harness crate is byte-identical to `posteriordb_bench_v7`'s. It is
  built from a clean sparse worktree of that commit.
- **Binaries.** The BridgeStan libraries and CmdStan executables are copied
  from WP64's Linux build, as WP62 copied v7's.
- **Order.** Models in WP62 order, oWALNUTS then CmdStan, seeds ascending.
  Strictly sequential, no reruns.
- **Pool.** The 18 Linux seeds are WP64's six (its committed cells, read
  unchanged) plus these 12. The driver changes are listed in `AMENDMENTS.md`.
- **Platform.** AWS c7a.4xlarge, lane 1. Every process runs under
  `taskset -c 0-3` with `RAYON_NUM_THREADS=4` and `OMP_NUM_THREADS=1`. Other
  pinned lanes share the L3 cache and memory bandwidth, so walls are
  **"pinned, co-tenanted"**. Pass counts and ESS per gradient are not
  affected by co-tenancy.

## The four statistics (computed over all 18 Linux seeds)

The per-cell quantity is v7's: min bulk ESS over the gate parameters divided
by `gradients_total`, on status-ok cells. A model enters (a), (c) and (d)
only if both arms have at least ceil(5n/6) ok cells (15 of 18). That is
WP62's 5-of-6 rule, generalised.

- **(a) v7 pooled geomean.** For each model and arm, take the median over
  ok cells. The model ratio is the oWALNUTS median over the CmdStan median.
  Take the geomean over models. This is WP62's statistic.
- **(b) Joint-pass.** As (a), but each model uses only the seeds where both
  arms' cells pass every gate. A model needs at least 3 such seeds to enter.
- **(c) Median of paired ratios.** For each model, compute the per-seed ratio
  oWALNUTS / CmdStan on seeds where both cells are ok. Take the median across
  seeds, then the geomean over models.
- **(d) (a) without `hmm_drive_0`.**

Each statistic gets a **seed bootstrap**: 10,000 resamples of the seeds with
replacement (all models and both arms of a seed move together), rng seed 72,
and a 2.5–97.5 % percentile interval. Each also gets its **leave-one-model-out
influence**: the largest |ln change| from dropping one model, with that model
named.

## Proposed v8 headline, stated before any cell: (c)

The criterion is to be least sensitive to one model's competitor failure
while still counting oWALNUTS's own failures.

- **(b) is ineligible.** It drops every cell where oWALNUTS fails a gate, so
  it does not count oWALNUTS's own failures. It is reported as "efficiency
  when both samplers work".
- **(d) is ineligible.** It removes a model chosen after seeing results. It
  diagnoses (a); it is not a rule that would handle the next stuck
  competitor.
- **(c) is proposed.** It pairs the arms on the same seed and takes a median
  across 18 seeds. A competitor's stuck chain on a minority of a model's
  seeds changes only those seeds' ratios, and the median absorbs them.
  oWALNUTS's failures still count: every ok cell enters, a low oWALNUTS ESS
  lowers that seed's ratio, and persistently failing models (`accel_gp`,
  centered Eight Schools, `one_comp`) stay in at their measured ratios.
- **Stated limitation.** If a competitor fails on half or more of a model's
  seeds, no median absorbs it. CmdStan's `hmm_drive_0` rate on Linux so far
  is 4/6. The leave-one-model-out influence makes this visible.

**Frozen selection rule.** The v8 headline is whichever of (a) and (c) has the
smaller leave-one-model-out influence on the 18-seed pool. Ties go to (c).

## Predictions (fixed before execution)

| | prediction |
|---|---|
| Q1 | (b) lies in **[0.80, 0.95]** |
| Q2 | (c) lies in **[0.80, 0.95]** |
| Q3 | (a) stays above 1.0 **only because of `hmm_drive_0`**: (a) > 1.0 and (d) <= 1.0 |
| Q4 | the frozen selection rule picks **(c)** |

Also reported:

- **Other pools.** All four statistics, with intervals and influence, on the
  12 new seeds alone, on WP64's six Linux seeds, and on the six Windows seeds
  (WP56 + WP62 cells).
- **Per model.** The per-model ratios.
- **Gates.** Pass counts per arm, /192 on the new seeds and /288 pooled.
- **Stuck chains.** Per-seed stuck-chain counts on `hmm_drive_0` for both arms
  (CmdStan and oWALNUTS), and per-model totals for all 16. A chain is stuck if
  any gate parameter's chain mean lies more than 5 reference sd from the
  posteriordb reference mean. The threshold was calibrated on WP64's six
  already-published `hmm_drive_0` cells, where stuck CmdStan chains sit at
  68–280 sd and every other chain at <= 0.1 sd. The Windows cells have no
  retained draws, so they get no stuck count.

## What was done before this freeze

- The analysis code was exercised once on the Windows cells, printing only
  the already-published Windows (a) value (0.7614, which matches WP62). No
  (b), (c) or (d) value on any pool has been looked at.
- WP64's six Linux `hmm_drive_0` cells were inspected to calibrate the
  stuck-chain threshold. Those cells are already published.
- No cell at 720701–720712 has been run. One smoke test ran at non-evidence
  seed 11 on `eight_schools_noncentered`, both arms, into scratch output that
  is not committed. It reproduced WP64's seed-11 smoke exactly (73,588 and
  70,007 gradients), so the copied binaries and the rebuilt harness behave as
  WP64's. The rebuilt harness's sha256 differs from WP64's because the build
  path is embedded in the binary; the source is identical.

## Execution rules

- `PREREGISTRATION.md` and `protocol.json` are committed before the first
  cell. The driver refuses cells otherwise, and refuses oWALNUTS cells unless
  the source tree is a clean `c5c60122`.
- Cells run sequentially. Failures and timeouts are results. There are no
  reruns and no tuning after results.
  - A driver crash may be relaunched.
  - Only an interrupted cell without a completed artifact may be rerun from
    scratch with the same seed, and the deviation is recorded.
- Raw draws and CmdStan output are checksummed and not committed.
