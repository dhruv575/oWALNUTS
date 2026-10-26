### WP64-POSTERIORDB-BENCH-V7-LINUX-V1: E26/E28 on Linux. Gate counts reproduce to within one cell (oWALNUTS 44/51, 7/15, 41/48), no draw is bit-identical, and the per-gradient ratio swings to 1.21x CmdStan because of CmdStan stuck chains

- **When and where.** 2026-10-26 UTC on `wt/linux-bench`, preregistered at
  `44546ec0` before the first cell. 312 sampling cells plus the funnel ran
  00:56–02:10 UTC.
  - Box: AWS c7a.4xlarge (AMD EPYC 9R14), Ubuntu 24.04, lane 1 pinned to
    cores 0-3, with three other lanes active. Walls are "pinned,
    co-tenanted".
  - Same commits as the Windows record: `f097391c` for E26, `c5c60122` for
    E28. Same seeds, models, gates and analysis, read from the frozen v7 and
    WP62 protocols.
  - The harness crate is byte-identical to v7's. All binaries were compiled
    on Linux. No reruns, no amendments after the freeze.
- **Pass counts, Linux (Windows).**
  - oWALNUTS: **44/51 (43)** house, **7/15 (6)** new five, **41/48 (40)**
    extension seeds, 82/96 (80) pooled fixed-16.
  - CmdStan: 33 (34), 5 (7), 31 (30).
  - nutpie: 27 (26), 5 (3).
- **Bit-identity.** 0/114 oWALNUTS cells, 0/3 funnel seeds and 0 competitor
  cells are bit-identical. The oWALNUTS start search matches to 1e-12 in
  114/114 cells, and the warmup traces part by iteration 50 in 131 of 132
  oWALNUTS cells (dense included) and by iteration 100 in the last one.
  Seven oWALNUTS cells flip, all near-gate and all non-identical:
  `gp_pois_regr` (one cell, -1), `one_comp` (four cells, net +2),
  `accel_gp` (one cell, +1) and `seeds_centered` (one cell, +1).
  - CmdStan `lotka_volterra` errors on the same seeds with the same messages
    (560562, 620602).
  - The nutpie `lotka_volterra` crash recurs.
- **Predictions.**
  - L1 (exact oWALNUTS counts) failed: off by one in each block, attributed
    by the frozen rule to platform floating point.
  - L2 (competitors within 3) held.
  - L3 (pooled six-seed ESS/gradient in [0.740, 0.822]) failed at **1.206**.
    CmdStan `hmm_drive_0` has second-mode chains on 4/6 Linux seeds
    against 2/6 on Windows, so its per-model ratio is 133. Post hoc, without
    `hmm_drive_0` the figure is 0.862 against Windows 0.749 on the same 14
    models.
  - L4 (wall/gradient vs CmdStan <= 1) was unevaluable (CmdStan
    `lotka_volterra` error). The value is 0.942 on 15/16 (Windows 1.849).
  - v7: P1, P2, P5 and P8 held. **P6 failed on Linux:** `seeds_centered`
    passes 560562. P7 failed.
  - WP62: Q1 and Q2 failed, Q3 and Q4 held.
  - Dense arm 18/18 at 12.2x.
- **Timings.** Linux/Windows wall per gradient is 0.20 for oWALNUTS (4
  replicas against the owned serialised worker), 0.39 for CmdStan and 0.16
  for nutpie. ESS/s against CmdStan is 1.215 (Windows 0.398) and against
  nutpie 1.454 (1.226).
- **Artifacts.** `STUDIES/posteriordb_bench_v7_linux_v1/{PREREGISTRATION.md,
  protocol.json,AMENDMENTS.md,README.md,run_posteriordb.py,run_extension.py,
  prepare_competitors.py,compare_windows.py,run_lane.sh,build_harness.sh,
  src/,artifacts/}`. Raw draws and CmdStan output stay on the box,
  uncommitted.
- **Next decision.** No default change.
  - Add Linux rows to E26/E28.
  - Report gate counts as reproducible to about +/-1 cell across platforms.
  - Retire the bare "0.76x CmdStan per gradient" headline in favour of a
    preregistered robust statistic, because CmdStan stuck-chain seeds move
    with libm.
  - Restate the `seeds_centered` silent funnel as "fails on most seeds".
  - Quote oWALNUTS walls from Linux.
