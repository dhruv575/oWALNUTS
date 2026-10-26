# nutpie 18-seed (WP76): preregistration

Frozen before the first evidence cell. The machine-readable form is
`protocol.json`.

## Question

WP72 fixed the per-gradient headline against CmdStan at 0.83x, using
statistic (c) over 18 Linux seeds. How does oWALNUTS compare with nutpie
0.16.8 on the same models and the same 18 seeds, on ESS per gradient, on ESS
per second, and on gates?

## Design

- **nutpie arm (run here).** nutpie 0.16.8 at defaults on WP62's fixed 16
  models, for all 18 Linux seeds: WP64's six (560561–560563 and
  620601–620603) and WP72's twelve (720701–720712). It runs 4 chains x 1,000
  tune / 1,000 draws. The nutpie cell code is v7's, unchanged
  (`nutpie_model`, `run_nutpie`, `metrics`, the gates).
- **oWALNUTS and CmdStan cells are reused, not rerun.**
  - They are read unchanged from WP64 (`posteriordb_bench_v7_linux_v1/artifacts/{v7,ext}/cells`)
    and WP72 (`posteriordb_ratio_robustness_v1/artifacts/cells`).
  - The comparison is same-seed. All three arms ran on lane 1 (cores 0-3)
    of the same box.
  - nutpie is run on all 18 seeds, including the three where WP64 already
    has Linux nutpie cells. Those 48 WP64 cells serve only as a reported
    same-seed repeat check.
- **One change to orchestration.** Each (model, seed) gets its own child
  process; v7 used one child per (model, all seeds). The reason is the
  `lotka_volterra` panic seen in v7 and WP64 ("Failed to constrain", then a
  poisoned mutex). With one child per model, a panic marks the later seeds
  as crashed without running them. The per-child timeout is 2,700 + 600 s.
  All changes are listed in `AMENDMENTS.md`.
- **Binaries.** The 16 nutpie libraries are copied from WP64's Linux build.
  Their TBB runtime is copied byte-identically into this lane and loaded
  through `LD_LIBRARY_PATH`.
- **Order.** Models in WP62 order, seeds ascending. Strictly sequential, no
  reruns.

**Platform.** AWS c7a.4xlarge, lane 1: `taskset -c 0-3` with
`RAYON_NUM_THREADS=4` and `OMP_NUM_THREADS=1`. Other pinned lanes share the
L3 cache and memory bandwidth, so walls are **"pinned, co-tenanted"**. Pass
counts and ESS per gradient are not affected by co-tenancy.

**Caveat on ESS per second, stated now.** The oWALNUTS and CmdStan walls were
taken in WP64 and WP72. The nutpie walls are taken here. All are on the same
lane and cores, but with whatever other lanes were running at the time. The
oWALNUTS wall excludes its start search (v7's rule), and nutpie's wall
includes its own initialisation.

## Statistics

The statistic is WP72's **(c)**. For each model:

1. Take the per-seed ratio oWALNUTS / nutpie on seeds where both cells are
   status ok.
2. Take the median across seeds. A model enters only if it has at least 15
   of 18 paired seeds.
3. Take the geomean over models.

It is computed on:

- **ESS per gradient**: `min_bulk_ess_per_gradient`, with gradients counted
  including warmup (nutpie: `n_steps`);
- **ESS per second**: `min_bulk_ess_per_second`.

Each value gets a seed bootstrap (10,000 resamples, rng seed 76, 2.5–97.5 %)
and its leave-one-model-out influence.

Also reported:

- **Other ratios.** (c) oWALNUTS vs CmdStan, per gradient (a check against
  WP72's 0.826) and per second; nutpie vs CmdStan, per gradient and per
  second.
- **Gates.** Per arm /288, per model, with the non-ok cells listed.
- **Stuck chains.** WP72's rule (a chain mean more than 5 reference sd from
  the posteriordb reference mean). Reported for nutpie on every model, and
  per seed on `hmm_drive_0` beside oWALNUTS and CmdStan.
- **The same-seed repeat check** against WP64's nutpie cells.

## Predictions (fixed before execution)

| | prediction | source |
|---|---|---|
| N1 | per-gradient (c) oWALNUTS / nutpie in **[1.0, 1.4]** | coordinator, "given WP58" |
| N1b | per-gradient (c) oWALNUTS / nutpie in **[0.55, 0.95]** | this study |
| N2 | per-second (c) oWALNUTS / nutpie in **[1.2, 1.8]** | WP64's house-17 ESS/s vs nutpie, 1.454 |
| N3 | nutpie passes **fewer than 239/288**, oWALNUTS's count | WP64, WP72 |

**Our expectation, stated before running: N1 fails low and N1b holds.**
WP58 found nutpie **ahead** per gradient: 1.70x oWALNUTS, from warmup spend
and its mass matrix. v7's all-22 per-gradient geomean oWALNUTS / nutpie was
0.645 on Windows and 0.837 on Linux (WP64). N1 is registered as the
coordinator stated it. If it was meant as nutpie / oWALNUTS, it is the same
as oWALNUTS / nutpie in [0.714, 1.0], and that reading is reported beside it.

## Execution rules

- `PREREGISTRATION.md` and `protocol.json` are committed before the first
  cell. The driver refuses cells otherwise.
- **Smoke test, before this freeze.** It ran at non-evidence seed 11 into
  scratch output, which is not committed. First a single
  `eight_schools_noncentered` cell: it reproduced WP64's seed-11 nutpie smoke
  exactly (56,790 gradients). Then, by mistake rather than by design, the
  full `run` loop in smoke mode, over all 16 models at seed 11 only. That
  exercised the per-seed child orchestration end to end. No evidence seed
  has been run.
- Cells run sequentially. Failures, crashes and timeouts are results. There
  are no reruns and no tuning after results.
  - A driver crash may be relaunched.
  - Only an interrupted cell without a completed artifact may be rerun from
    scratch with the same seed, and the deviation is recorded.
- Raw draws are checksummed and not committed.
