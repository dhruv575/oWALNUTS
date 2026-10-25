# posteriordb v7 seed extension (WP62): preregistration

Frozen 2026-10-25, before the first evidence cell. The machine-readable form
is `protocol.json`.

## Question

What is the seed interval of v7's per-gradient headline? That headline is
oWALNUTS / CmdStan min-bulk-ESS per gradient, geomean over the fixed 16
models: 0.708 on 15/16 complete, 3 seeds. WP60 and WP61 attributed the v6 ->
v7 change (0.848 -> 0.708) to seeds, not to the start rule or to rescue
removal. This study measures how large that seed effect is.

## Design

- **Commit.** Main **`c5c60122`**. Against the v7 commit `f097391c`, its
  library adds only documentation, WP59 chain-warning reporting, and the
  research-feature-gated, default-`None`
  `WarmupConfig::with_initial_phase_max_depth` (WP57). The default sampler
  is therefore that of `f097391c`. The driver checks the library source
  against the commit.
- **Arms.** `owalnuts` (the v7 harness, unchanged; every default from the
  commit) and CmdStan 2.39.0 at its defaults. No nutpie.
- **Models.** The fixed 16 of v6/v7, the house set without `arma11`.
- **Runs.** 4 x 1,000/1,000 with 4 threads, on **3 new fresh seeds**
  (620601–620603) shared by arm. Order: models in protocol order, then
  `owalnuts` before CmdStan, then seeds ascending. Strictly sequential; no
  reruns. The house gates and v7's statistic apply unchanged. The cell code
  is v7's driver code.
- **Infrastructure.** The BridgeStan libraries and CmdStan executables are
  copied from `posteriordb_bench_v7/models`, and the posteriordb checkout is
  v7's. One smoke pair was run (non-evidence seed 41, scratch output).

## Analysis (frozen)

1. Per-model ratios and the geomean on the **3 new seeds alone**. This uses
   v7's inclusion rule: all three seeds must be ok on both arms.
2. The same over **all 6 seeds**: v7's three, read unchanged from
   `posteriordb_bench_v7/artifacts/cells`, plus the new three. A model is
   included if both arms have at least 5 of 6 ok cells.
3. **The seed interval.** Drop each of the six seeds in turn from both arms
   and recompute the pooled geomean, requiring at least 4 of 5 ok cells.
   Report the [min, max] range and its width.
4. Pass counts per arm: new seeds /48, and pooled /96. Also the |z| > 4
   check on every passing oWALNUTS cell.
5. **Seed-count recommendation.**
   - Primary: take the jackknife SE of the pooled geomean from the six
     leave-one-out values. Assuming SE scales as sqrt(6/n), recommend
     n = ceil(6 (2 SE / 0.05)^2) seeds. That is the count that gives an
     approximately 95 % interval of half-width 0.05 around a 0.75 gate.
   - Reported only: n from the log-scale SD of the six single-seed
     geomeans. A one-seed median cannot absorb competitor stuck chains, so
     this figure is dominated by them; in a smoke run on v7's seeds alone it
     gave n = 140.

## Predictions (frozen)

- **Q1.** The 3-new-seed geomean lies in **[0.65, 0.95]**.
- **Q2.** The 6-seed pooled geomean lies in **[0.72, 0.85]**.
- **Q3.** The leave-one-seed-out range is **wider than 0.08**.
- **Q4.** oWALNUTS passes **>= 40/48** on the new seeds.

## Decision rule (frozen)

This study reports and attributes only; it flips nothing. The README will
state:

- whether the pooled 6-seed geomean clears 0.75, the v6/v7 P3 threshold;
- the recommended seed count for future per-gradient release gates, by the
  primary rule above.

The v7 README gets one paragraph citing this extension. v7's verdict is not
rewritten.
