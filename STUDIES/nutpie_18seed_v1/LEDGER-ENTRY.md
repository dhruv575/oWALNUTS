### WP76-NUTPIE-18SEED-V1: over the fixed 16 x 18 Linux seeds, oWALNUTS passes 239/288 against CmdStan 198 and nutpie 163, at 0.70x nutpie per gradient and 0.93x per second (statistic (c))

- **When and where.** 2026-10-26 on `wt/nutpie-18seed`, preregistered at
  `c7e39bb2` before the first cell.
  - 288 nutpie 0.16.8 cells at defaults, fixed 16 x the 18 Linux seeds of
    WP64/WP72, 4 x 1,000/1,000, v7 nutpie cell code and gates, one child per
    seed.
  - Ran 03:37–04:27 UTC on lane 1 (pinned, co-tenanted), no reruns.
  - oWALNUTS and CmdStan cells reused unchanged from WP64 and WP72.
- **Outcome**, statistic (c) with seed-bootstrap 95 % intervals.
  - **oWALNUTS / nutpie:** **0.699 [0.650, 0.962]** per gradient (15
    models) and **0.932 [0.865, 1.275]** per second.
  - **oWALNUTS / CmdStan:** 0.826 [0.789, 0.931] per gradient and 0.886
    [0.846, 1.000] per second.
  - **nutpie / CmdStan:** 1.174 per gradient and 0.949 per second.
- **Gates:** oWALNUTS **239**, CmdStan 198 (3 errors), nutpie **163**
  (7 `lotka_volterra` crashes).
  - nutpie loses on non-centered Eight Schools (2/18, divergences),
    `diamonds` (2/18), `lotka_volterra` (7/18) and `hmm_drive_0` (11/18).
  - `hmm_drive_0` stuck chains: oWALNUTS 1/18, CmdStan 5/18, nutpie 6/18.
- **Predictions.**
  - N1 (per gradient in [1.0, 1.4]) failed, as expected before running.
  - N1b ([0.55, 0.95]) held.
  - N2 (per second in [1.2, 1.8]) failed at 0.93.
  - N3 (nutpie gates < 239) held.
- **Same-seed repeat.** nutpie repeats WP64 bit-identically on 45/45 cells
  that completed both times.
- **Artifacts.** `STUDIES/nutpie_18seed_v1/{PREREGISTRATION.md,protocol.json,
  AMENDMENTS.md,README.md,run_nutpie18.py,analyze_nutpie18.py,run_lane.sh,
  artifacts/}`. Raw draws are uncommitted and checksummed.
- **Next decision.**
  - Headline reliability (most gates by far) with honest efficiency: 0.83x
    CmdStan and 0.70x nutpie per gradient; 0.89x and 0.93x per second on
    Linux.
  - The nutpie per-gradient gap (WP58: mass matrix and warmup) is the
    efficiency target.
  - No default change.
