### WP72-POSTERIORDB-RATIO-ROBUSTNESS-V1: over 18 Linux seeds the fixed-16 per-gradient headline is 0.83x CmdStan [0.79, 0.94] (median of paired ratios); WP64's 1.21 was a six-seed excess of CmdStan stuck chains

- **When and where.** 2026-10-26 on `wt/ratio-robustness`, preregistered at
  `0e42b648` before the first cell.
  - 384 cells: the fixed 16 x oWALNUTS (`c5c60122` defaults) and CmdStan
    2.39.0 x 12 fresh seeds (720701–720712), 4 x 1,000/1,000.
  - Ran 02:25–03:25 UTC on the c7a.4xlarge box, lane 1 (cores 0-3, pinned,
    co-tenanted). v7 harness and gates, no reruns.
  - Pooled with WP64's six Linux seeds.
- **Outcome on 18 seeds,** with seed-bootstrap 95 % intervals:
  - (a) v7 pooled geomean **0.822** [0.776, 0.892];
  - (b) joint-pass **0.870** [0.833, 0.891], 12 models;
  - (c) median of paired ratios **0.826** [0.789, 0.935];
  - (d) (a) without `hmm_drive_0` **0.824** [0.775, 0.880].
- **Predictions.**
  - Q1 ((b) in [0.80, 0.95]) held.
  - Q2 ((c) in [0.80, 0.95]) held.
  - Q3 ((a) > 1 only because of `hmm_drive_0`) failed: (a) is 0.822, because
    CmdStan's `hmm_drive_0` stuck-chain rate fell from 4/6 to 1/12 on the new
    seeds (5/18 overall, oWALNUTS 1/18).
  - Q4 (rule selects (c)) held: leave-one-model-out influence 0.055 against
    0.063 for (a).
- **Single-model sensitivity.** The most influential model is now
  `one_comp`, where CmdStan fails 18/18 (ratio about 2). The worst ratios are
  oWALNUTS's own failures, `accel_gp` 0.48 and centered Eight Schools 0.39.
- **Gates.** oWALNUTS 157/192 new and 239/288 pooled; CmdStan 136/192 and
  198/288. The oWALNUTS `hmm_drive_0` 720707 second-mode chain fails its
  gates and was named by `chain_warnings`.
- **Six-seed intervals.** (a) and (c) span 0.7–1.6 on both platforms over
  six seeds. (b) stays at 0.85–0.90 on every pool.
- **Artifacts.** `STUDIES/posteriordb_ratio_robustness_v1/{PREREGISTRATION.md,
  protocol.json,AMENDMENTS.md,README.md,run_robustness.py,
  analyze_robustness.py,run_lane.sh,build_harness.sh,src/,artifacts/}`. Raw
  draws and CmdStan output are uncommitted and checksummed.
- **Next decision.**
  - Adopt (c) with its seed interval over at least 12 seeds as the v8
    per-gradient headline: 0.83x [0.79, 0.94].
  - Report (b) 0.87x beside it.
  - Retire the six-seed 0.76 / 1.21 figures.
  - No default change.
