# Amendments (WP56)

Amendments cover only cells that have not been run, and each one is
committed before those cells. Phase 1 (132 CmdStan and nutpie cells) was
complete when A0 was written. No oWALNUTS cell and no funnel cell had been
run at A0 time.

## A0: the hash wait is extended (2026-10-25 04:44 local, before any oWALNUTS cell)

The coordinator asked for this extension at 04:43 local. Two sibling
default-flip studies, WP51 (dense defaults) and WP54 (`RejectLeaf`), are due
within about two hours. The commit under test should include them if they
pass. This amendment replaces the preregistered fallback in
`protocol.json` / `PREREGISTRATION.md`, which was "457119f4 if no message
within 1 hour of Phase 1 finishing, i.e. 05:32":

- Phase 2 does not start before the coordinator sends a hash or 06:45 local,
  whichever comes first.
- If no hash has arrived by 06:45, the commit under test is **the head of
  `main` at that moment**. At A0 time that head already includes the WP52
  `Init::best_of(16)` default flip (`d1fc2ab9`, a descendant of `457119f4`).
- The hash is recorded in `AMENDMENT-1.json`, which is committed before the
  first oWALNUTS cell, as the driver requires.
- The descriptive `owalnuts-dense` arm uses the same commit as the main arm.

Nothing else changes: models, seeds, gates, statistics, predictions P1–P8 and
the release rule are as frozen at `af2d364d`. A0 was written after the
Phase 1 competitor results were seen. Those results are CmdStan 34/51 + 7/15
and nutpie 26/51 + 3/15; P7 failed. A0 depends only on the coordinator's
schedule, not on those results, and it cannot touch the competitor cells,
which have all been run.

## A1: the commit under test is `f097391c` (2026-10-25 ~06:05 local, before any oWALNUTS or funnel cell)

The coordinator named `f097391c`, the head of `main` and a descendant of
`457119f4`, at about 06:03, which was before the A0 deadline. It was merged
into `wt/posteriordb-v7`, so the worktree's `src/`, `integrations/`,
`tests/` and `Cargo.toml` equal `f097391c`. The driver checks this before
every oWALNUTS run. Relative to `457119f4`, the commit carries three default
changes:

1. **WP52.** `Init::default()` is `Init::best_of(16)`. The starts differ from
   0.2.0; the kernel does not.
2. **WP54.** `sampler::Tuning::default()` uses
   `NonfinitePositionPolicy::RejectLeaf`. It is bit-identical whenever no
   nonfinite position occurs, and an overflow no longer aborts the run. The
   counter `WorkTotals::nonfinite_position_rejections` is now recorded per
   cell (retained and warmup) and per funnel chain.
3. **WP51 follow-up.** The `Metric::dense()` facade's warmup defaults are
   PerTransition seeding, Stan regularisation and symmetrised precision. This
   affects only the descriptive dense arm.

The diagonal kernel, `ALGORITHM_REVISION` and the fingerprints are unchanged.
The dense arm uses the same commit. The only harness change is the extra
counter, which is recorded but feeds no gate, statistic or prediction.
